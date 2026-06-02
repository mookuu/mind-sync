---
name: mind-sync-lint
description: mind-sync wiki 健康检查（断链、孤儿页、源新摘要旧 stale-summary）
---

# mind-sync Lint（wiki 质检）

定期或在 ingest 后检查 wiki 健康度。

## 步骤

1. 确保 wiki 已索引：`sync_sources(preset="wiki")` 或全量 sync
2. 运行：`lint_wiki(stale_days=180)`
3. 处理 issue 类型：
   - `wiki-broken-link` / `wiki-orphan` — 修复 wikilink 或补链
   - `stale-summary` — 摘要 `sources:` 中的素材比摘要 `updated:` 更新，需修订摘要
   - `stale-doc` — 长期未更新的页面
   - `thin-content` — 内容过短
4. 修复后更新摘要 frontmatter 的 `updated:` 字段
5. 再次 `lint_wiki()` 验证

## 说明

- Lint **不调用 LLM**（不做语义矛盾检测，那是 Obsidian/Karpathy 高级模式，本工程不实现）
- 报告同时写入 `data/lint-reports/`，并追加 `wiki/log.md`

## MCP 工具

`lint_wiki`, `wiki_graph`, `browse_docs`, `update_wiki_page`, `sync_sources`
