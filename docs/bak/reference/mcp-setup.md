# Cursor MCP 配置（mind-sync）

文档索引：[docs/README.md](./README.md) · 工作流：[../workflow.md](./../workflow.md)

## 一键启用（推荐）

项目已包含 `.cursor/mcp.json`。在 Cursor 中打开本仓库后：

1. 确保 API 已启动：`docker compose up -d api`（或本地 `uvicorn`）
2. 安装 MCP 依赖（本机 Python 3.12 推荐）：
   ```bash
   pip install -r requirements-tools.txt
   ```
   或仅 MCP：`pip install -r apps/mcp/requirements.txt`
3. 打开 **Cursor Settings → MCP**，确认 `mind-sync` 服务器已加载且为绿色
4. 若 API Key 不是默认值，修改 `.cursor/mcp.json` 中 `MINDSYNC_API_KEY`，与 `.env` 的 `API_KEY` 保持一致

## 环境变量

| 变量                | 说明                        | 默认                    |
| ------------------- | --------------------------- | ----------------------- |
| `MINDSYNC_BASE_URL` | API 地址                    | `http://localhost:8000` |
| `MINDSYNC_API_KEY`  | 与 `.env` 中 `API_KEY` 相同 | `mind-sync-dev-key`     |

## 可用工具

- `sync_sources` / `sync_status` — 增量同步与进度
- `rebuild_index` — 全量重建索引
- `ingest_source` — 仅增量索引

## Cursor Skills

项目内 Skills（与 MCP 配合）：

- `.cursor/skills/mind-sync-ingest/` — 素材 → 摘要
- `.cursor/skills/mind-sync-query/` — 带证据问答
- `.cursor/skills/mind-sync-lint/` — wiki 质检

Rule：`.cursor/rules/mind-sync.mdc`

- `search_docs` — 全文搜索（可传 `category`、`topic`）
- `browse_docs` — 分类浏览
- `list_categories` / `get_purpose` / `update_purpose` — 规则约束读写
- `audit_events` — 最近审计事件（登录/同步/设置）
- `vault_sync` — Vault Git 拉取/推送（需配置 `VAULT_GIT_URL`）
- `update_wiki_page` — 更新 `wiki/` 下 Markdown
- `query_wiki` — 问答（`save_to_wiki=true` 写入 queries）
- `wiki_graph` / `lint_wiki` — 图谱与质量检查

## 验证

在 Cursor Agent 对话中尝试：

> 调用 mind-sync 的 health，再 browse_docs category=summary topic=harness

或：

> 用 query_wiki 问「Harness Pipeline 有哪些 Stage 概念」，并 save_to_wiki

## 常见问题

**MCP 红叉 / 启动失败**

- 本机 `python` 是否在 PATH 中（Windows 可改用 `py -3` 并改 `mcp.json` 的 `command`）
- 是否已 `pip install -r apps/mcp/requirements.txt`
- API 是否在 `8000` 端口可达

**401 / API Key 错误**

- 对齐 `.env` 与 `mcp.json` 中的 `API_KEY` / `MINDSYNC_API_KEY`

**搜索不到 harness 摘要**

- 重启 API 容器以触发 `init_db` 种子复制（或删除 `data/wiki/summaries/harness/` 后重启）
- 执行 `sync_sources` 索引 wiki 源

## 工作流 Rule

同时启用 `.cursor/rules/mind-sync.mdc`，Agent 会优先走 sources → summaries → query 流程。
