# mind-sync

本机 Docker 的个人学习知识库（Web + API + CLI + MCP）。

## 启动

1. 复制环境变量文件：`cp .env.example .env`
2. 修改 `.env` 中密码和密钥（尤其是 `AUTH_PASSWORD`、`API_KEY`、`LLM_API_KEY`）
3. 启动：`docker compose up --build -d`
4. 打开：
   - Web: `http://localhost:8080`
   - API: `http://localhost:8000/docs`

## 本地 Python 依赖（非 Docker 跑 API / CLI / MCP 时）

| 文件 | 用途 |
|------|------|
| `requirements.txt` | API 运行时（FastAPI、索引、同步） |
| `requirements-tools.txt` | CLI + MCP（仅 `requests` / `mcp`） |
| `requirements-dev.txt` | 开发/CI（pytest、pip-audit，可选） |

推荐 **Python 3.12**（与 Docker/CI 一致）。在 3.14 上若 `pip` 长时间无输出，多半在编译 `pydantic-core`，可先：

```bash
pip install --only-binary=:all: pydantic-core
pip install -r requirements.txt
```

Windows 一键安装（API + 可选工具）：

```powershell
.\scripts\install-deps.ps1 -Tools
```

安装后自检（不跑 pytest）：

```bash
python scripts/check_test_env.py
```

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
  - `GET /api/search?q=...&category=&topic=`
  - `GET /api/categories`
  - `GET /api/browse?category=&topic=`
  - `GET /api/purpose`
  - `POST /api/purpose`
  - `GET /api/document/{id}`
  - `POST /api/ingest`
  - `POST /api/query`
  - `POST /api/lint`
  - `GET /api/audit-events?limit=50`（审计日志，需鉴权）
  - `GET /api/vault-status`、`POST /api/vault-sync`（Vault Git，需 `VAULT_GIT_URL`）
  - `PUT /api/wiki-content`（编辑 wiki Markdown）
  - `GET /api/classify-suggest?q=...`（归档路径建议）

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
pip install -r requirements-tools.txt
# 或仅 CLI：pip install -r apps/cli/requirements.txt
python apps/cli/mind_sync_cli.py --api-key mind-sync-dev-key search "django middleware"
python apps/cli/mind_sync_cli.py --api-key mind-sync-dev-key sync
python apps/cli/mind_sync_cli.py --api-key mind-sync-dev-key sync-status
python apps/cli/mind_sync_cli.py --api-key mind-sync-dev-key query "PlanAndSolve 核心思想" --save
python apps/cli/mind_sync_cli.py --api-key mind-sync-dev-key query "Django 路由机制" --model "deepseek-ai/DeepSeek-V4-Flash"
python apps/cli/mind_sync_cli.py --api-key mind-sync-dev-key wiki-graph
python apps/cli/mind_sync_cli.py --api-key mind-sync-dev-key categories
python apps/cli/mind_sync_cli.py --api-key mind-sync-dev-key browse --category summary
python apps/cli/mind_sync_cli.py --api-key mind-sync-dev-key library
python apps/cli/mind_sync_cli.py --api-key mind-sync-dev-key purpose get
python apps/cli/mind_sync_cli.py --api-key mind-sync-dev-key audit-events --limit 10
# Windows 终端乱码时，建议直接输出 UTF-8 文件
python apps/cli/mind_sync_cli.py --api-key mind-sync-dev-key search "闭包" --output-file result.json
```

### 4) MCP（面向 Cursor / Codex / Claude Code）

**Cursor 项目内已配置** `.cursor/mcp.json`（详见 `docs/CURSOR_MCP_SETUP.md`）。

手动启动（调试）：

```bash
pip install -r requirements-tools.txt
# 或仅 MCP：pip install -r apps/mcp/requirements.txt
set MINDSYNC_BASE_URL=http://localhost:8000
set MINDSYNC_API_KEY=mind-sync-dev-key
python apps/mcp/server.py
```

MCP 提供工具：

- `health`
- `list_sources`
- `list_library`
- `sync_sources`
- `sync_status`
- `search_docs`（支持 `category` / `topic` / `source_id` 过滤）
- `list_categories`
- `browse_docs`
- `get_purpose`
- `update_purpose`
- `audit_events`
- `vault_sync`
- `update_wiki_page`
- `get_document`
- `wiki_graph`
- `query_wiki`
- `ingest_source`
- `lint_wiki`

## 知识库目录（wiki）

数据卷 `./data` 映射容器内 `/data`：

```
data/
  purpose.md                 # 研究方向（问答时注入 LLM）
  wiki/
    summaries/{topic}/*.md   # 学习摘要（如 harness/）
    queries/*.md             # 问答沉淀（save_to_wiki）
```

- 摘要模板：`templates/wiki/summary-template.md`
- 工作流详解：`docs/MIND_SYNC_WORKFLOW.md`
- Cursor Rule：`.cursor/rules/mind-sync.mdc`

首次启动 API 时会从 `apps/api/app/seed/` 复制示例摘要到 `data/wiki/summaries/`（如 `harness/pipeline-basics.md`），**仅当目标文件不存在时**写入。仓库根目录 `templates/wiki/examples/` 为同内容的文档副本。

`sources.yaml` 已包含 `wiki` 源（`/data/wiki`），同步后摘要与 queries 均可被搜索与问答引用。

## 当前能力

- 同步本地源仓库与 wiki 的 `.md/.py/.java`
- **GitHub 源**：`type: github` 时自动 shallow clone/pull 到 `data/repos/<id>`（`GITHUB_TOKEN`）
- **Vault Git**：`VAULT_GIT_URL` 跨设备同步 `wiki/` + `purpose.md`（设置 → Vault / 一键同步）
- **Web 源**：`type: web` 抓取 URL 快照到 `data/web-cache/<id>/`
- 增量索引与全文搜索（SQLite FTS5）；搜索支持 `sort=mtime_desc` 与浏览器搜索历史
- **文档分类**：原始素材 / 学习摘要 / 问答沉淀；按主题浏览（`/api/categories`、`/api/browse`）
- 搜索过滤（`source_id` / 文件类型 / `category` / `topic`）
- 文档内容预览（Markdown 渲染，markdown-it 14 内置 GFM 表格/删除线 + task-lists 插件）
- Query/ingest/lint 的 API 能力；问答证据四档置信度（EXTRACTED / INFERRED / AMBIGUOUS / UNVERIFIED）
- 问答可选保存到 `wiki/queries/`（frontmatter 结构化），**保存后自动索引**
- `purpose.md` 研究方向可在 Web 设置页编辑（`/api/purpose` POST）
- Wiki 页面 Web 内编辑（`PUT /api/wiki-content`）与 MCP `update_wiki_page`
- 无 `LLM_API_KEY` 时问答降级为检索摘要；可配置 `OLLAMA_BASE_URL` 使用本地模型
- `/api/classify-suggest` 启发式归档路径建议（无需 LLM）
- 部署与路径迁移见 `docs/DEPLOYMENT.md`；来源示例见 `sources.example.yaml`
- 自动定时同步（可在设置中开启，默认关闭）
- 页面显式展示“下次自动同步时间 / 最近一次自动同步状态”
- 设置页展示最近审计事件（登录/登出/同步/设置变更，只读）
- 同步状态面板展示当前进度与最近一次同步汇总（新增/更新、跳过、删除；与审计 `sync_requested` / `sync_completed` 对应）
- P2：证据对象化（`evidences`）、wiki 链接图分析（`/api/wiki-graph`）、source adapter 分层
- 同步性能优化：先用 `mtime + size` 快速跳过未变文件，再按需计算 hash

## API 模块结构（后端）

`apps/api/app/main.py` 仅保留路由与装配；核心逻辑已拆分：

- `config.py` — 环境配置
- `db.py` — SQLite 连接与初始化
- `models.py` — 请求模型
- `services/auth.py` — 会话、CSRF、API Key、登录限速
- `services/audit.py` — 审计日志
- `services/sync_engine.py` — 同步状态与后台同步任务
- `services/indexer.py` — 文件扫描、索引写入、来源解析

## L1 安全强化（已支持）

- 登录失败限速（按 IP + 用户名，窗口与次数可配；记录持久化到 SQLite，重启不丢）
- 问答/同步/Lint API 限速（`API_RATE_LIMIT_*`，默认 30/10/20 次/小时）
- 审计日志（登录/登出/同步/设置变更；`GET /api/audit-events`，保留天数可配 `AUDIT_RETENTION_DAYS`）
- Session Cookie 安全属性可配（`HttpOnly` + `Secure` + `SameSite` + `max_age`）
- Session 支持 TTL 过期控制（`SESSION_TTL_SECONDS`）
- 支持服务端登出接口（`POST /api/logout`，会撤销当前会话 token）
- CORS 白名单可配置（`CORS_ALLOW_ORIGINS`）
- Cookie 鉴权写操作默认启用 CSRF 校验（请求头默认 `x-csrf-token`，可用 `CSRF_HEADER_NAME` 改名）
- API Key 支持逗号分隔多值（便于平滑轮换）
- 默认安全响应头（`X-Content-Type-Options`、`X-Frame-Options`、`Referrer-Policy`、`Permissions-Policy`）

推荐在公网或隧道场景启用：

- `COOKIE_SECURE=true`
- `SECURITY_HSTS_ENABLED=true`（仅 HTTPS 场景）

安全冒烟检查（登录/CSRF/登出/会话撤销）：

```bash
python scripts/smoke_auth.py --base-url http://localhost:8000 --password "<你的 AUTH_PASSWORD>"
```

> `smoke_auth.py` 已统一委托给 `smoke_all.py` 的 `auth` 模式，避免两套逻辑分叉。

统一冒烟回归（登录/同步/搜索/文档预览/登出）：

```bash
python scripts/smoke_all.py --base-url http://localhost:8000 --password "<你的 AUTH_PASSWORD>"
# 若只想跳过同步阶段（更快）
python scripts/smoke_all.py --base-url http://localhost:8000 --password "<你的 AUTH_PASSWORD>" --skip-sync
```

登录限速 + 审计持久化检查（多次错误登录触发 429，并验证 audit-events）：

```bash
python scripts/smoke_auth_meta.py --base-url http://localhost:8000 --password "<你的 AUTH_PASSWORD>"
```

## 移动端与外网访问

- Web 界面支持窄屏布局（搜索与筛选自动换行）
- 外网 HTTPS 建议：反向代理 + `.env` 中 `COOKIE_SECURE=true`、`SECURITY_HSTS_ENABLED=true`
- 详见 `docs/MIND_SYNC_WORKFLOW.md` 中的 Caddy 示例与 CORS 配置
