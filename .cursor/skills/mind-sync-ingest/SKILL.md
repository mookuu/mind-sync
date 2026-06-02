---
name: mind-sync-ingest
description: 将已索引素材整理为 wiki 学习摘要（遵循 SCHEMA.md，sync + update_wiki_page + lint）
---

# mind-sync Ingest（素材 → 摘要）

在 Cursor 中把 **sources 原始素材** 整理为 `data/wiki/summaries/` 学习摘要。

## 前置

1. 阅读 `data/wiki/SCHEMA.md`（或容器内 `/data/wiki/SCHEMA.md`）
2. 模板：`templates/wiki/summary-template.md`
3. MCP 已配置且 API 可达

## 步骤

1. **同步素材**：`sync_sources()` 或提示用户在 Web 点「同步」
2. **定位素材**：`search_docs(q=..., category="source")` 或 `get_document(id=...)`
3. **建议路径**：必要时参考 `GET /api/classify-suggest?q=...` 的 `recommended` 路径
4. **撰写摘要**：frontmatter 含 `type/topic/sources/confidence/updated`；正文含 wikilink
5. **写入 wiki**：`update_wiki_page(path="summaries/{topic}/{slug}.md", content=...)`
6. **重新索引**：`sync_sources(preset="wiki")` 或全量 sync
7. **质检**：`lint_wiki()`，修复 `stale-summary` / 断链 / 孤儿页

## 禁止

- 不要跳过 `sources:` 引用编造结论
- 不要用 Obsidian 插件或外部 vault skill 替代 mind-sync MCP 写库
- 不要复制 obsidian-wiki 的 `raw/` 双轨目录（本工程用 `sources.yaml` + `summaries/`）

## MCP 工具

`sync_sources`, `search_docs`, `get_document`, `update_wiki_page`, `lint_wiki`, `list_categories`
