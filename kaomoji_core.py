# -*- coding: utf-8 -*-
"""颜文字库：加载数据、关键词兜底、向量匹配、抽样。不依赖 AstrBot，可本地单测。"""
from __future__ import annotations

import hashlib
import json
import math
import os
import random
import re

MARK_RE = re.compile(r"〈\s*mood\s*[:：]\s*([^〉\n]{1,60}?)\s*〉")
# 标记格式：{{分类键}}。刻意避开 meme_manager 的 &&分类键&&，否则会被它先吃掉
TAG_RE = re.compile(r"\{\{\s*([^{}\n]{1,16}?)\s*\}\}")
# 旧版 &&中文类目&& 只用于清理残留，英文键（meme_manager 的）不碰
LEGACY_TAG_RE = re.compile(r"&&\s*([^&\n]{1,16}?)\s*&&")
CJK_RE = re.compile(r"[\u4e00-\u9fff]")


class KaomojiIndex:
    def __init__(self, data_path: str, emb_path: str):
        self.data_path = data_path
        self.emb_path = emb_path
        self.categories: dict[str, dict] = {}
        self.order: list[str] = []
        self.embeddings: dict[str, list[float]] = {}
        self.dim = 0
        self.version = ""
        self._recent: dict[str, list[str]] = {}

    # ---------------- 数据 ----------------
    def load(self) -> None:
        with open(self.data_path, encoding="utf-8") as f:
            data = json.load(f)
        self.categories = {}
        for name, info in data.get("categories", {}).items():
            items = [t for t in info.get("items", []) if t]
            if not items:
                continue
            self.categories[name] = {
                "desc": info.get("desc", ""),
                "avoid": info.get("avoid", ""),
                "triggers": info.get("triggers", []),
                "examples": info.get("examples", [])[:3],
                "special": bool(info.get("special", False)),
                "items": items,
                "search_text": info.get("search_text") or name,
            }
        # 特殊池默认不参与自动选择
        self.order = [c for c, v in self.categories.items() if not v["special"]]
        self.version = self._fingerprint()
        self.load_embeddings()

    def _fingerprint(self) -> str:
        """数据指纹：类目 + search_text 变化时重建向量索引。

        必须用稳定哈希：Python 内置 hash() 每个进程随机加盐，
        会导致每次插件重载都被判定"数据变了"、白白重建一次向量索引。
        """
        raw = "|".join(f"{c}:{self.categories[c]['search_text']}" for c in sorted(self.categories))
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:12]

    # ---------------- 索引 ----------------
    def load_embeddings(self) -> bool:
        if not os.path.exists(self.emb_path):
            return False
        try:
            with open(self.emb_path, encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            return False
        if data.get("version") != self.version or not data.get("vectors"):
            return False
        vecs = data["vectors"]
        self.dim = int(data.get("dim") or 0)
        self.embeddings = {c: [float(x) for x in v] for c, v in vecs.items() if c in self.categories}
        return len(self.embeddings) == len(self.categories)

    def save_embeddings(self) -> None:
        tmp = self.emb_path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump({"version": self.version, "dim": self.dim, "vectors": self.embeddings}, f, ensure_ascii=False)
        os.replace(tmp, self.emb_path)

    @property
    def ready_for_embedding(self) -> bool:
        return bool(self.embeddings) and len(self.embeddings) == len(self.categories)

    # ---------------- 匹配 ----------------
    @staticmethod
    def cosine(a: list[float], b: list[float]) -> float:
        if not a or not b or len(a) != len(b):
            return 0.0
        dot = sum(x * y for x, y in zip(a, b))
        na = math.sqrt(sum(x * x for x in a))
        nb = math.sqrt(sum(y * y for y in b))
        return dot / (na * nb) if na and nb else 0.0

    def match_embedding(self, vec: list[float], threshold: float) -> tuple[str, float] | None:
        best_cat, best_score = None, -1.0
        for cat, ev in self.embeddings.items():
            s = self.cosine(vec, ev)
            if s > best_score:
                best_cat, best_score = cat, s
        if best_cat is None or best_score < threshold:
            return None
        return best_cat, best_score

    def match_keyword(self, text: str) -> tuple[str, float] | None:
        """按 triggers 命中打分：命中词越长权重越高。"""
        scores: dict[str, float] = {}
        for cat, info in self.categories.items():
            if info["special"]:
                continue
            for trig in info["triggers"]:
                if trig and trig in text:
                    scores[cat] = scores.get(cat, 0.0) + (0.5 + len(trig) * 0.25)
        if not scores:
            return None
        cat = max(scores, key=lambda c: scores[c])
        # 归一成 0~1 的粗略置信度（命中一个双字触发词≈0.5）
        score = min(1.0, scores[cat] / 2.0)
        return cat, score

    # ---------------- 抽样 ----------------
    def pick(self, cat: str, rng: random.Random | None = None) -> str | None:
        info = self.categories.get(cat)
        if not info:
            return None
        rng = rng or random
        items = info["items"]
        recent = self._recent.setdefault(cat, [])
        pool = [t for t in items if t not in recent] or items
        choice = rng.choice(pool)
        recent.append(choice)
        if len(recent) > max(2, len(items) // 3):
            recent.pop(0)
        return choice

    def search_text(self, cat: str) -> str:
        return self.categories.get(cat, {}).get("search_text", cat)

    # ---------------- 标记 ----------------
    @staticmethod
    def extract_marks(text: str) -> list[tuple[int, int, str]]:
        """返回 [(start, end, phrase), ...]"""
        return [(m.start(), m.end(), m.group(1).strip()) for m in MARK_RE.finditer(text)]

    @staticmethod
    def strip_marks(text: str) -> str:
        return MARK_RE.sub("", text)

    # ---------- &&分类键&& 标记（对齐 meme_manager） ----------
    def extract_tags(self, text: str) -> list[tuple[int, int, str]]:
        """只返回属于本插件类目的 &&标记&&。"""
        out = []
        for m in TAG_RE.finditer(text):
            name = m.group(1).strip()
            if name in self.categories:
                out.append((m.start(), m.end(), name))
        return out

    def strip_our_tags(self, text: str) -> str:
        """清掉属于本插件的标记；meme_manager 的 &&英文键&& 原样保留。"""
        def repl_new(m):
            name = m.group(1).strip()
            if name in self.categories or CJK_RE.search(name):
                return ''
            return m.group(0)

        def repl_old(m):
            name = m.group(1).strip()
            if name in self.categories or CJK_RE.search(name):
                return ''
            return m.group(0)

        text = TAG_RE.sub(repl_new, text)
        return LEGACY_TAG_RE.sub(repl_old, text)
