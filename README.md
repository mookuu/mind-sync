# mind-sync

本机 Docker 的个人学习知识库（Web + API + CLI + MCP）。

## 启动

1. 复制环境变量文件：`cp .env.example .env`
2. 修改 `.env` 中密码和密钥（尤其是 `AUTH_PASSWORD`、`API_KEY`、`LLM_API_KEY`）
3. 启动：`docker compose up --build -d`
4. 打开：
   - Web: `http://localhost:8080`
   - API: `http://localhost:8000/docs`

## 访问方式（3种并存）

### 1) Web（面向人）

- 登录后可一键同步、搜索、预览文档
- 入口：`http://localhost:8080`

### 2) API（面向程序 / AI）

- Web Cookie 鉴权与 API Key 鉴权兼容
- API Key 默认来自 `.env` 的 `API_KEY`
- LLM 默认模型：`deepseek-ai/DeepSeek-V4-Flash`
- OpenAI 兼容参数来自 `.env`：
  - `LLM_BASE_URL`（默认 `https://api.siliconflow.cn/v1`）
  - `LLM_API_KEY`
  - `LLM_MODEL`
- 支持接口：
  - `POST /api/sync`
  - `GET /api/sync-status`
  - `GET /api/search?q=...`
  - `GET /api/document/{id}`
  - `POST /api/ingest`
  - `POST /api/query`
  - `POST /api/lint`

示例（API Key）：

```bash
curl -H "x-api-key: mind-sync-dev-key" "http://localhost:8000/api/search?q=python&limit=5"
```

```bash
curl -X POST "http://localhost:8000/api/query" \
  -H "x-api-key: mind-sync-dev-key" \
  -H "Content-Type: application/json" \
  -d "{\"question\":\"PlanAndSolve 是什么\",\"limit\":5,\"save_to_wiki\":true}"
```

### 3) CLI（面向终端工作流）

```bash
pip install -r apps/cli/requirements.txt
python apps/cli/mind_sync_cli.py --api-key mind-sync-dev-key search "django middleware"
python apps/cli/mind_sync_cli.py --api-key mind-sync-dev-key sync
python apps/cli/mind_sync_cli.py --api-key mind-sync-dev-key sync-status
python apps/cli/mind_sync_cli.py --api-key mind-sync-dev-key query "PlanAndSolve 核心思想" --save
python apps/cli/mind_sync_cli.py --api-key mind-sync-dev-key query "Django 路由机制" --model "deepseek-ai/DeepSeek-V4-Flash"
# Windows 终端乱码时，建议直接输出 UTF-8 文件
python apps/cli/mind_sync_cli.py --api-key mind-sync-dev-key search "闭包" --output-file result.json
```

### 4) MCP（面向 Cursor / Codex / Claude Code）

```bash
pip install -r apps/mcp/requirements.txt
set MINDSYNC_BASE_URL=http://localhost:8000
set MINDSYNC_API_KEY=mind-sync-dev-key
python apps/mcp/server.py
```

MCP 提供工具：

- `health`
- `list_sources`
- `sync_sources`
- `sync_status`
- `search_docs`
- `get_document`
- `query_wiki`
- `ingest_source`
- `lint_wiki`

## 当前能力

- 同步本地 3 个源仓库的 `.md/.py/.java`
- 增量索引与全文搜索（SQLite FTS5）
- 文档内容预览（Markdown 渲染）
- Query/ingest/lint 的 API 能力
- 搜索过滤（`source_id` / 文件类型）
- 自动定时同步（可在设置中开启，默认关闭）
- 页面显式展示“下次自动同步时间 / 最近一次自动同步状态”
