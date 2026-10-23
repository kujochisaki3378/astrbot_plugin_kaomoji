# Changelog

## 0.6.2 — 2026-10-23

- 效果图裁掉聊天昵称区域，只保留 bot 回复本体（避免暴露个人信息）
- `_conf_schema.json` 里会话白名单示例中的真实 QQ 号换成占位符

## 0.6.1 — 2026-10-23

- 补充效果截图（`docs/effect-private.png`、`docs/effect-group.png`），README 增加「效果」一节

## 0.6.0 — 2026-10-23

- **数据目录规范化**：数据改存 `data/plugin_data/astrbot_plugin_kaomoji/`，首次运行自动从插件目录复制 `kaomoji.json`，不再往插件安装目录写文件（插件市场规范要求）
- 阻塞 IO（数据加载/保存、向量索引落盘）改为 `asyncio.to_thread`，避免卡事件循环
- 补充 `LICENSE`、`CHANGELOG`、数据来源声明；`kaomoji.json` 增加 `provenance` 字段
- `metadata.yaml` 更正描述与仓库地址，`astrbot_version` 收紧到 `>=4.28.0`

## 0.5.1 — 2026-10-23

- 移除 `streaming_mode=prompt` 直出模式及两个专属配置项，流式只剩 `followup` / `off`

## 0.5.0 — 2026-10-23

- **修复**：数据指纹由内置 `hash()` 改为 `sha256`。内置 hash 每个进程随机加盐，导致每次重载都被判定数据变化、白白重建 26 条向量（26 次 embedding 调用 + 约 2 秒）
- 合并关键词兜底与语义兜底为 `_auto_append` / `_choose_category`，装饰、流式补发、`/kaomoji test` 三处复用
- 缓存 embedding provider，删除旧 `〈mood:…〉` 标记解析与查询缓存等死代码

## 0.4.0 — 2026-10-23

- 配置面板按【基础】【流式】【提示词】【匹配】【兜底】【高级】分组排序
- 新增颜文字库管理命令：`/kaomoji cats`、`list`、`add`、`del`、`reload`
- 改动原子写回 JSON 并自动重载索引

## 0.3.0 — 2026-10-23

- 流式输出改为「结束后单独补发一条颜文字消息」（`streaming_mode=followup`）
- 修复标记独占一行时替换后留下空行的问题
- 新增 `remind_in_user_message`：在用户消息末尾追加标记提醒

## 0.2.0 — 2026-10-23

- 标记格式由 `&&分类键&&` 改为 `{{分类键}}`，避开 meme_manager 的标记解析（两个插件都用 `&&` 会互相吃掉）
- 规则对齐 meme_manager：工具说明 + 分类表 + 内部资料不披露
- 支持清理旧 `&&中文类目&&` 残留，保留 `&&英文键&&` 交给 meme_manager

## 0.1.x — 2026-10-23

- 初版：`〈mood:…〉` 标记 → 向量匹配 26 个类目 → 替换
- 支持关键词兜底、语义兜底、概率与冷却、`/kaomoji` 系列命令
- 装饰阶段只处理 LLM 回复，不碰指令/工具输出
