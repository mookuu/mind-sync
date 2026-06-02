---
name: mind-sync-query
description: 基于 mind-sync 知识库带证据问答，可选保存到 wiki/queries
---

# mind-sync Query（带证据问答）

用库内证据回答问题，并可选沉淀到 `wiki/queries/`。

## 前置

- `get_purpose()` 了解研究方向（问答时会注入 LLM）
- 若刚改笔记/摘要，先 `sync_sources()`

## 步骤

1. **可选预检**：`search_docs(q=..., category="summary")` 看是否已有摘要
2. **问答**：`query_wiki(question="...", save_to_wiki=true, limit=8)`
3. **解读结果**：
   - 答案中的 `[n]` 对应 `evidences[n]`
   - 置信度：EXTRACTED > INFERRED > AMBIGUOUS > UNVERIFIED
4. **引用规范**：向用户说明时标注 `source_id/rel_path`，不编造 evidences 外内容
5. **沉淀**：`save_to_wiki=true` 时自动写入 `queries/` 并更新 `index.md` / `log.md`

## 禁止

- 不要用对话记忆替代库内检索
- 不要把 UNVERIFIED 证据表述为确定事实

## MCP 工具

`query_wiki`, `search_docs`, `browse_docs`, `get_purpose`, `sync_sources`
