# 架构说明

mind-sync 是**本机部署**的个人学习知识库：把多源 Markdown/代码索引到 SQLite FTS，通过 Web / API / CLI / MCP 搜索与带证据问答，并在 `data/wiki` 维护结构化摘要。

## 系统边界

```
┌─────────────┐   Cookie / API Key   ┌──────────────┐
│ Web :8080   │ ───────────────────► │ API :8000    │
│ CLI / MCP   │                      │ FastAPI      │
└─────────────┘                      └──────┬───────┘
                                            │
         ┌──────────────────────────────────┼──────────────────────────┐
         ▼                  ▼                 ▼                          ▼
   sources.yaml      ./sources/*         ./data/wiki              SQLite FTS
   (配置)            (素材卷)            (摘要/queries)          mind_sync.db
         │                  │                 │
         └──── sync ────────┴── ingest ───────┘
```

- **不依赖** Obsidian 运行时；Obsidian 仅可作为剪藏目录（local 源）。
- **LLM 可选**：无 `LLM_API_KEY` 时问答降级为检索摘要；可配 `OLLAMA_BASE_URL`。

## 数据流

### 1. 素材层（sources）

由 `sources.yaml` 声明，类型见 [SOURCES.md](./reference/sources.md)：

| type | 同步时行为 |
|------|------------|
| `local` | 扫描 `path` 下匹配 `include` 的文件 |
| `github` | `git clone/pull` 到 `path`，再扫描 |
| `web` | HTTP 抓取 `url` → Markdown 快照 → 扫描 |

另有 **Vault Git**（`VAULT_GIT_URL`）：同步前 pull / 可选 push `wiki/` + `purpose.md`，与 sources 独立。

### 2. 索引层（SQLite）

- 表 + FTS5 虚拟表，键为 `(source_id, rel_path)`。
- **增量**：比较 mtime/size（及 sha1）跳过未变文件。
- **全量重建**：按源删除索引条目后强制重读每个文件（不拉远程）。

核心模块：`services/indexer.py`、`services/fts.py`。

### 3. 知识层（wiki）

| 路径 | 说明 |
|------|------|
| `data/purpose.md` | 研究方向，注入问答 prompt |
| `data/wiki/SCHEMA.md` | Agent 维护约定 |
| `data/wiki/summaries/` | 人工/Agent 整理的学习摘要 |
| `data/wiki/queries/` | 问答沉淀（`save_to_wiki`） |
| `data/wiki/index.md` | 自动目录（sync/query/lint/rebuild 后更新） |
| `data/wiki/log.md` | 事件日志 |

导航维护：`services/wiki_nav.py`。质检：`services/lint_engine.py`（含 stale-summary）。

## 同步引擎

`services/sync_engine.py` 的 `run_sync_job` 顺序：

1. （可选）Vault pull  
2. `sync_all_sources` — GitHub pull、Web 抓取、同源配对计划  
3. 按 **sync_source_order** 逐个源扫描索引  
4. （可选）Vault push、写 `sources-manifest.json`、更新 `wiki/log.md`

**同源配对**（`services/source_pairing.py`）：GitHub + local 同 id / 同 path / 仓库名=local id 时只索引一次；GitHub 失败则 warnings + 回退 local。

**并发**：全局 `SYNC_LOCK`，同时仅一个 sync/rebuild 任务。

## 索引操作对照

| 入口 | 模块 | 远程拉取 |
|------|------|----------|
| `POST /api/sync` | `sync_engine` | 是 |
| `POST /api/ingest` | `main.ingest` → indexer | 否 |
| `POST /api/rebuild-index` | `rebuild_engine` | 否 |
| 定时任务 | `scheduler.AutoSyncScheduler` | 同 sync |

## 问答链路

1. `search_for_query`（FTS）取 citations  
2. `build_evidence_items` 打置信度标签  
3. `generate_structured_answer`（可选 LLM）  
4. 可选 `save_query_page_with_nav` 写入 `queries/` 并索引  

模块：`query_engine.py`、`evidence.py`、`wiki_query.py`。

### 搜索排序

默认 FTS 查询带 `ORDER BY bm25(documents_fts)`；可选 `sort=mtime_desc` 按文件 mtime。  
环境变量 `SEARCH_CATEGORY_WEIGHTS`（如 `summary=1.2,query=1.1,source=1.0`）可在 Python 侧对 bm25 分数加权，默认略提升摘要类结果。

## 鉴权与权限

| 机制 | 模块 |
|------|------|
| Cookie 会话 + CSRF | `services/auth.py` |
| API Key（视为 admin） | `services/auth.py` |
| RBAC admin / viewer | `services/permissions.py` |
| 登录 / API 限速 | `auth.py`、`rate_limit.py` |
| 审计 | `services/audit.py` |

写操作（同步、wiki 编辑、Vault、settings 等）需 **admin**；详见 [SECURITY.md](../SECURITY.md)。

## Web 源合规

`services/web_fetch_policy.py`：robots.txt、User-Agent、域名限速、allowlist、源级 `fetch_confirmed`。  
在 `source_sync.sync_web_source` 中于 HTTP GET 前执行。

## 后端目录（`apps/api/app/`）

| 路径 | 职责 |
|------|------|
| `main.py` | 路由装配 |
| `config.py` | 环境变量 |
| `db.py` | SQLite、种子数据 |
| `models.py` | 请求/Source 模型 |
| `services/indexer.py` | 扫描、upsert、load_sources |
| `services/sync_engine.py` | 后台 sync |
| `services/rebuild_engine.py` | 全量重建 |
| `services/source_sync.py` | GitHub / Web 拉取 |
| `services/vault_git.py` | Vault 双向 Git |
| `services/web_extract.py` | HTML → Markdown |
| `services/web_fetch_policy.py` | Web 抓取合规 |
| `services/source_pairing.py` | GitHub/local 配对 |
| `services/sync_backoff.py` | 远程源同步失败指数退避 |
| `services/password_util.py` | AUTH_USERS bcrypt 校验 |
| `services/categories.py` | 分类浏览 |
| `services/link_graph.py` | Wiki 链接图 |
| `services/lint_engine.py` | Lint 报告 |
| `services/wiki_nav.py` | index.md / log.md |
| `services/wiki_util.py` | Wiki 路径安全 |
| `source_adapters/` | 各源 path 解析 |

## 前端（`apps/web/`）

静态 HTML + `app-shared.js` / `auth-ui.js` / `search-ui.js` / `sync-ui.js` / `graph-ui.js` / `query-ui.js` / `app.js` / `ui.js` / `wiki-editor.js`；通过 Cookie + CSRF 调 API。  
viewer 角色隐藏「同步/全量重建/Lint」按钮；写操作以 API 403 为准。

## 运维注意

- ingest 与同源配对对齐；`index.md` / `log.md` / `SCHEMA.md` 不可 API 编辑
- Vault pull **覆盖**本地 `wiki/`（日志 WARNING；部署前备份）

## 刻意不做的能力

见 [workflow.md](./workflow.md)「刻意不实现」：Obsidian 插件复刻、Agent 替代 FTS、LLM 语义 lint 等。
