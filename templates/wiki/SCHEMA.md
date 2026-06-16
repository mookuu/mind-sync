# mind-sync Wiki 维护规范（SCHEMA）

Agent 与人工维护 `data/wiki/` 时请遵循本文件。规则约束见 `/data/purpose.md`。

## 页面类型

| type      | 目录                     | 用途                          |
| --------- | ------------------------ | ----------------------------- |
| `summary` | `summaries/{topic}/*.md` | 基于 sources 的结构化学习摘要 |
| `query`   | `queries/*.md`           | 问答沉淀（`derived: true`）   |

## 摘要 frontmatter（必填）

```yaml
type: summary
topic: harness
tags: [pipeline]
sources:
  - knowledge_engineering/notes/intro.md
confidence: extracted # extracted | inferred | ambiguous | unverified
updated: 2026-06-02
```

## Ingest 工作流（素材 → 摘要）

1. 确认素材已入库：`sync_sources` 或 `/api/sync`
2. `search_docs` / `get_document` 阅读原始素材
3. 按 `templates/wiki/summary-template.md` 写摘要
4. `update_wiki_page` 写入 `summaries/{topic}/{slug}.md`
5. 再次 `sync_sources` 索引 wiki
6. 可选 `lint_wiki` 检查断链与过期摘要

## Query 工作流

1. `query_wiki(question=..., save_to_wiki=true)` 获取带 evidences 的回答
2. 重要结论可手工提炼为新的 `summary` 页

## Lint 工作流

1. `lint_wiki()` — 断链、孤儿页、薄内容、**源新摘要旧**（stale-summary）
2. 按报告修复 wikilink 与 `sources:` 引用
3. 更新摘要 `updated:` 字段

## 链接约定

- Wiki 内链：`[[summaries/topic/page]]` 或 Markdown 相对路径
- 引用原始素材：frontmatter `sources:` 中写 `source_id/rel_path`（与索引一致）

## 导航文件（自动生成，勿手改）

- `index.md` — 摘要/问答目录
- `log.md` — sync / query / lint 事件时间线
