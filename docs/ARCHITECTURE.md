# 架构说明

mind-sync 是**本机部署**的个人学习知识库：把多源 Markdown/代码索引到 SQLite FTS，通过 Web / API / CLI / MCP 搜索与带证据问答，在 `data/wiki` 维护结构化摘要。

---

## 系统边界

```
┌──────────────────────────────────────────────────────────────────────┐
│                           Gateway 层                                 │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────────────┐    │
│  │ Web:8080 │  │  CLI     │  │  MCP     │  │ Cursor Skills     │    │
│  │ (Vue 3)  │  │  (终端)  │  │  (AI)    │  │ ingest/query/lint │    │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘  └────────┬─────────┘    │
│       │             │             │                   │              │
│       └─────────────┴─────┬───────┴───────────────────┘              │
│                           │ Cookie / API Key                        │
├───────────────────────────┼──────────────────────────────────────────┤
│                     ┌─────▼──────┐                                  │
│                     │  API:8000  │    API 层 (FastAPI)               │
│                     │  main.py   │                                  │
│                     └─────┬──────┘                                  │
├───────────────────────────┼──────────────────────────────────────────┤
│                           │                                          │
│         ┌─────────────────┼──────────────────┐                      │
│         ▼                 ▼                  ▼                      │
│   sources.yaml      ./sources/*        ./data/wiki              Services 层
│   (配置)            (素材卷)           (摘要/queries)
│         │                 │                  │                      │
│         └── sync ─────────┴── ingest ───────┘                      │
│                           │                                          │
│                           ▼                                          │
│                    SQLite FTS5                                     │
│                    mind_sync.db              Data 层                │
└──────────────────────────────────────────────────────────────────────┘
```

- **不依赖** Obsidian 运行时；Obsidian 仅可作为剪藏目录（local 源）
- **LLM 可选**：无 `LLM_API_KEY` 时问答降级为检索摘要；可配 `OLLAMA_BASE_URL`
- **前端**：Vue 3 + Vite，Nginx 反向代理，详见下文"前端架构"

---

## 分层架构

### 1. Gateway 层（访问入口）

| 方式 | 端口 | 技术栈 | 鉴权 | 适用场景 |
|------|------|--------|------|----------|
| **Web** | 8080 | Vue 3 + Vite → Nginx | Cookie Session | 人工搜索、浏览、设置 |
| **API** | 8000 | FastAPI (uvicorn) | `x-api-key` / Session | 程序集成、自动化 |
| **CLI** | — | Python `argparse` | `--api-key` | 终端工作流 |
| **MCP** | — | Python `mcp` SDK | `MINDSYNC_API_KEY` | Cursor / Claude Code |

### 2. API 层（`apps/api/app/main.py`）

FastAPI 应用，负责：

- **路由装配**：~40 个端点，按功能分组（同步、搜索、问答、管理）
- **依赖注入**：`require_any_auth` / `require_admin` 等 auth 守卫
- **CORS / CSRF / 限速**：全局中间件
- **后台任务**：同步、全量重建通过 `BackgroundTasks` 异步执行

### 3. Services 层（`apps/api/app/services/`）

按职责分 7 组：

#### 索引与同步

| 模块 | 职责 |
|------|------|
| `indexer.py` | 扫描文件、upsert 索引、load_sources |
| `sync_engine.py` | 后台 sync 编排（Vault → GitHub/Web 拉取 → 索引） |
| `rebuild_engine.py` | 全量重建：清空 → 强制重扫 |
| `source_sync.py` | GitHub clone/pull、Web HTTP 抓取 |
| `source_pairing.py` | GitHub + local 同源配对（只索引一次） |
| `source_sync_key.py` | 源标识生成与匹配（`id:type` 格式，如 `PythonBasic:local`） |
| `chinese_tokenizer.py` | jieba 中文分词：索引预分词 + 搜索查询分词 + 自定义词典 |
| `user_manager.py` | 用户目录管理、私有源注册、索引清理 |
| `sync_settings.py` | 同步范围预设（per-user sync_preset/sync_source_ids） |
| `sync_backoff.py` | 远程源失败指数退避 |
| `scheduler.py` | 定时自动同步 |

#### 搜索与问答

| 模块 | 职责 |
|------|------|
| `fts.py` | SQLite FTS5 全文搜索 + BM25 排序 |
| `query_engine.py` | 问答链路编排 + 外部 LLM 调用 |
| `evidence.py` | 证据置信度标签（EXTRACTED / INFERRED / AMBIGUOUS / UNVERIFIED） |
| `wiki_query.py` | 问答保存到 `wiki/queries/` |
| `classify.py` | 启发式文档分类 |

#### Wiki 管理

| 模块 | 职责 |
|------|------|
| `wiki_nav.py` | `index.md` / `log.md` 自动生成 |
| `wiki_util.py` | Wiki 路径安全校验 |
| `wiki_source.py` | Wiki 源/保护页管理 |
| `link_graph.py` | Wiki 链接图谱分析（hubs / orphans / 断链） |
| `lint_engine.py` | 质检报告（断链、孤岛、过期摘要） |

#### 鉴权与安全

| 模块 | 职责 |
|------|------|
| `auth.py` | Server-side session 管理、API Key 校验、CSRF、限速、`resolve_current_user()`、`require_own_source()` |
| `session_store.py` | Session CRUD（SQLite）、滑动过期、空闲超时 |
| `permissions.py` | RBAC admin/member 角色 + 用户配置解析 |
| `password_util.py` | bcrypt 哈希 + 明文兼容迁移 |
| `rate_limit.py` | API 限速（按 IP/Key + 桶） |
| `audit.py` | 审计日志（登录/同步/设置变更） |
| `security.py` | 安全警告（默认 key 检测、安全头） |

#### 工具模块

| 模块 | 职责 |
|------|------|
| `categories.py` | 分类浏览（原始素材 / 学习摘要 / 问答沉淀） |
| `library.py` | 层级目录树（source → dir → file，统一树，不再按语言分组） |
| `vault_git.py` | Vault Git 双向同步（`wiki/` + `purpose.md`） |
| `git_ops.py` | Git 底层操作（clone / pull / status） |
| `web_extract.py` | HTML → Markdown 转换 |
| `web_fetch_policy.py` | Web 抓取合规（robots、UA、域名限速、allowlist） |
| `purpose.py` | `purpose.md`（规则约束）读写 |
| `source_health.py` | 各源状态收集 |
| `source_spec_util.py` | Source 配置序列化 |
| `assets.py` | 文档附件处理 |
| `source_adapters/` | 各源 path 解析适配器 |

### 4. 数据层

| 存储 | 路径 | 说明 |
|------|------|------|
| **SQLite** | `data/mind_sync.db` | FTS5 索引、sessions、users、api_keys、审计、限速 |
| **素材卷** | `./sources/<id>` | local / GitHub clone / Web 快照 |
| **Wiki** | `data/wiki/` | 摘要、问答沉淀、index、log、SCHEMA |
| **规则约束** | `data/purpose.md` | 注入 LLM 的上下文规则 |
| **配置** | `sources.yaml` | 索引来源声明 |

---

## 核心流程

### 同步引擎

`sync_engine.run_sync_job` 顺序：

1. （可选）Vault pull
2. `sync_all_sources` — GitHub pull、Web 抓取、同源配对
3. 按 `sync_source_order` 逐个源扫描索引
4. （可选）Vault push、写 `sources-manifest.json`、更新 `wiki/log.md`

**同源配对**（`source_pairing.py`）：GitHub + local 同 id / 同 path / 仓库名=local id 时只索引一次；GitHub 失败则 warnings + 回退 local。

**并发**：全局 `SYNC_LOCK`，同时仅一个 sync/rebuild 任务。

### 索引操作对照

| 入口 | 主模块 | 远程拉取 | 索引策略 |
|------|--------|----------|----------|
| `POST /api/sync` | `sync_engine` | 是 | 增量 upsert（mtime/size/sha1） |
| `POST /api/ingest` | `indexer` | 否 | 增量 upsert |
| `POST /api/rebuild-index` | `rebuild_engine` | 否 | 清空所选源 → 强制重扫 |
| 定时同步 | `scheduler.AutoSyncScheduler` | 同 sync | 同 sync |

### 问答链路

```
问句 → search_for_query (FTS) → citations
                                   ↓
                         build_evidence_items → 置信度标签
                                   ↓
                  ┌── 有 LLM_API_KEY ──→ generate_structured_answer (外部 LLM)
                  ├── 有 OLLAMA_BASE_URL → 同上（本地模型）
                  └── 无 LLM ──────────→ 检索摘要降级
                                   ↓
                         save_query_page_with_nav (可选)
```

**搜索排序**：默认 `ORDER BY bm25(documents_fts)`，可选 `sort=mtime_desc`。
环境变量 `SEARCH_CATEGORY_WEIGHTS` 可在 Python 侧对 bm25 分数加权，默认略提升摘要类结果。

---

## 鉴权体系

```
┌───────────────┐     ┌─────────────────────────────────────────┐
│  请求到达       │     │  cookie: ms_token = <session_id>       │
│               │     │  header: x-api-key = <key>              │
└──────┬────────┘     └─────────────────────────────────────────┘
       │
       ▼
┌─────────────────────────────────────────────────────────────────┐
│                    auth.require_any_auth                         │
│                                                                  │
│  ├─ 有 x-api-key? → parse_api_keys() → 匹配 → 视为 admin       │
│  │                                                                 │
│  └─ 有 ms_token?  → session_store.get_session()                  │
│       ├─ 不存在?       → 401                                    │
│       ├─ expires_at 过期? → 404 （已清理）                      │
│       ├─ 空闲超时?     → 404 （last_active_at > 30min）         │
│       └─ 有效         → 更新 last_active_at → 放行              │
│                                                                  │
│  写操作额外: enforce_csrf() 校验 header vs cookie               │
└─────────────────────────────────────────────────────────────────┘
```

### 数据库表

| 表 | 用途 |
|----|------|
| `sessions` | Server-side session（session_id, username, role, ip, user_agent, last_active_at, expires_at, remember_me） |
| `users` | 本地用户凭据（username, password_hash, role），启动时从 env 自动种子 |
| `api_keys` | Web UI 生成的持久化 API Key |
| `session_revocations` | （已废弃，保留兼容）不再使用 |
| `login_failures` | 登录限速计数器 |
| `api_usage` | API 限速桶 |
| `user_notifications` | 用户通知（共享状态变更、库删除等） |
| `app_settings` | 应用设置（per-user 键前缀 `{username}:sync_*`） |

### 角色

| 角色 | 能力 |
|------|------|
| **admin** | 同步、全量重建、同步素材、wiki 编辑、Vault、purpose、lint、操作记录、系统管理 |
| **member** | 搜索、文档库、知识查询、同步控制、同步素材（个人库）、操作记录（仅自己） |

> Per-user 同步：每个用户独立管理自己的同步范围（`{username}:sync_preset` / `{username}:sync_source_ids`），同步/重建结果只对当前用户可见。

详见 [SECURITY.md](../SECURITY.md)。

---

## 前端架构

> **Vue 3 + Vite**，2026-06 从原生 HTML/JS 迁移。

```
apps/web-new/
├── index.html               # Vite 入口
├── vite.config.js           # 开发代理 /api → localhost:8000
├── package.json
├── Dockerfile               # 多阶段构建：node build → nginx serve
├── nginx.conf               # 静态文件 + /api/ 反向代理 api:8000
└── src/
    ├── main.js              # Vue 3 入口（Router 初始化）
    ├── App.vue              # 根组件：登录页 + 侧边栏 + 顶栏 + router-view
    ├── router/index.js      # 10 个路由（含懒加载）
    ├── api/index.js         # API 客户端（fetch + 自动 CSRF）
    ├── markdown-it.js       # Markdown 渲染（markdown-it + task-lists）
    ├── composables/
    │   ├── useAuth.js       # 登录/登出/session 检查/remember_me
    │   ├── useSyncSettings.js  # 同步范围共享状态（DB 持久化 + 本地 reactive）
    │   └── useMarkdown.js   # Markdown 渲染封装
    ├── components/
    │   ├── AppSidebar.vue   # 侧边栏导航（角色感知菜单）
    │   ├── NotifyBar.vue    # 顶部通知条（共享状态变更/库删除）
    │   ├── TreeView.vue     # 递归文档树容器
    │   ├── TreeBranch.vue   # 树分支（可展开/收起，响应 activeDocId）
    │   └── TreeNode.vue     # 树节点（文件/目录递归，含根级文件渲染）
    └── views/
        ├── Library.vue      # 文档库（代码高亮 + 图片 + 权限拦截提示）
        ├── Search.vue       # 全文搜索（per-user 源过滤 + 缓存 TTL）
        ├── QA.vue           # LLM 问答
        ├── Graph.vue        # Wiki 图谱（Canvas 力导向图，仅管理员）
        ├── Account.vue      # 账户（个人信息、改密码、会话管理）
        ├── SyncControl.vue  # 同步控制（per-user 增量/全量）
        ├── SyncSources.vue       # 同步素材（radio 范围 + 全局/我的/共享折叠区）
        ├── SyncSourcesAdmin.vue  # 素材管理（admin 专属表格：分页+筛选+操作）
        ├── SyncVault.vue         # 仓库管理
        ├── SyncPurpose.vue  # 规则约束（仅管理员）
        └── SyncAudit.vue    # 操作记录（角色过滤 + 高亮 + 跳转）
        ├── UsersAdmin.vue   # 用户管理 + 系统概览（统计卡片 + 用户 CRUD，仅管理员）
        └── ApiKeys.vue      # API key 管理（仅管理员）
```

构建输出为 `dist/` 静态文件，由 Nginx 容器 serve。
开发时 Vite 自动代理 `/api` → `localhost:8000`。

---

## 目录约定

| 路径 | 说明 |
|------|------|
| `apps/api/` | FastAPI 后端（`app/main.py` 路由，`app/services/` 业务模块，`app/source_adapters/` 源适配器） |
| `apps/web-new/` | Vue 3 前端（构建后由 Nginx serve） |
| `apps/cli/` | CLI 工具（`mind_sync_cli.py`） |
| `apps/mcp/` | MCP 服务器（`server.py`，Cursor / Claude Code） |
| `data/` | 持久化数据（SQLite、wiki、purpose.md） |
| `sources/` | 素材目录（local / GitHub clone / Web 快照） |
| `docs/` | 工程文档 |
| `templates/` | wiki 摘要模板、SCHEMA 示例 |
| `scripts/` | 自检/冒烟/辅助脚本 |
| `tests/` | pytest 测试 |

---

## 运维注意

- ingest 与同源配对对齐；`index.md` / `log.md` / `SCHEMA.md` 不可 API 编辑
- Vault pull **覆盖**本地 `wiki/`（日志 WARNING；部署前备份）
- 修改 `sources.yaml` 后：Web 设置 → 重新加载，或 `POST /api/admin/sources/reload`
- Web 源合规开关（robots、allowlist、限速）配置在 `.env`，见 `docs/workflow.md`

---

## 参考

- [docs/workflow.md](./workflow.md) — 日常使用流程
- [docs/deployment.md](./deployment.md) — 部署与迁移
- [docs/development.md](./development.md) — 本地开发
- [docs/concepts/karpathy-comparison.md](./concepts/karpathy-comparison.md) — Karpathy 理念对照
- [SECURITY.md](../SECURITY.md) — 鉴权与安全
