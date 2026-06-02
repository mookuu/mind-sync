# mind-sync 工作流指南

> 文档索引：[docs/README.md](./README.md) · 架构：[ARCHITECTURE.md](./ARCHITECTURE.md) · 源配置：[SOURCES.md](./SOURCES.md)

本文说明如何在 **Web、CLI、Cursor MCP** 之间协作，维护个人可信知识库。

## 核心理念

```
可信来源 (sources) → 学习摘要 (wiki/summaries) → 带证据问答 (query + evidences)
```

- **sources**：你亲自整理或信任的仓库内容（笔记、代码、官方文档摘录）
- **summaries**：对 sources 的结构化摘要，便于检索与问答
- **queries**：问答会话的沉淀，便于回顾与二次检索

## 索引操作分类

| 操作 | API / MCP | 远程拉取 | 索引策略 |
|------|-----------|----------|----------|
| **增量同步** | `POST /api/sync` · MCP `sync_sources` | Vault / GitHub / Web | 按 mtime/sha1 跳过未变文件 |
| **增量索引** | `POST /api/ingest` · MCP `ingest_source` | 否 | 同上 |
| **真全量重建** | `POST /api/rebuild-index` · MCP `rebuild_index` | 否 | 先清空所选源索引，再强制重扫每个文件 |

- 同步范围与顺序沿用 Web **设置 → 同步**（preset / 自定义勾选 / `sync_source_order`）。
- 全量重建**不会**删除 `data/wiki` 等磁盘文件，只重建 SQLite 索引。
- `GET /api/sync-status` 对三类任务共用，`job_mode` 为 `sync` 或 `rebuild`；`warnings` 含 GitHub 回退等提示。

### GitHub + local 同源

当 GitHub 源与 local 源 **id 相同**、**path 相同**、或 **GitHub 仓库名与 local 的 id 相同** 时视为同源（只索引一次）：

1. 同步时 **优先** `git clone/pull`
2. 失败则写入 `warnings`，local 目录有文件时 **回退本地**继续索引
3. 单个源失败 **不阻断**其他源

示例：`sources.example.yaml` 中 `PythonBasic` 的 github + local 双条目。

## 目录结构

数据目录挂载为 Docker 卷 `./data:/data`：

| 路径 | 说明 |
|------|------|
| `/data/purpose.md` | 研究方向；首次初始化自动种子，问答时注入 LLM |
| `/data/wiki/SCHEMA.md` | Agent 维护规范（ingest / query / lint 约定） |
| `/data/wiki/index.md` | **自动生成**的摘要/问答目录 |
| `/data/wiki/log.md` | **自动生成**的 sync/query/lint 事件日志 |
| `/data/wiki/summaries/{topic}/*.md` | 学习摘要，如 `summaries/harness/pipeline-basics.md` |
| `/data/wiki/queries/*.md` | 问答沉淀（frontmatter `type: query`） |

摘要模板：`templates/wiki/summary-template.md`

## Karpathy 模式借鉴（已实现）

| 能力 | 实现 |
|------|------|
| SCHEMA 维护规范 | `data/wiki/SCHEMA.md` |
| index + log 导航层 | sync / query / lint / rebuild 后自动更新 |
| Ingest / Query / Lint 三操作 | MCP + `.cursor/skills/mind-sync-*` |
| stale-summary 质检 | `lint_wiki` 检测源新摘要旧 |

## Cursor Skills

| Skill | 说明 |
|-------|------|
| `mind-sync-ingest` | 素材 → 摘要 |
| `mind-sync-query` | 带证据问答 |
| `mind-sync-lint` | wiki 质检 |

路径：`.cursor/skills/`。Rule：`.cursor/rules/mind-sync.mdc`。

## Obsidian 协作（可选）

1. Obsidian Web Clipper 保存到 `./sources/obsidian/`（见 `sources.yaml` 的 `obsidian` 源）
2. 在 mind-sync Web 点「同步」索引剪藏
3. 用 **ingest skill** 或 MCP 整理为 `summaries/`
4. Obsidian 可打开 `data/wiki` 或 `sources/obsidian` 阅读，**索引与问答仍走 mind-sync**

## Web 源抓取合规

Web 源（`type: web`）同步时会 HTTP 抓取并转为 Markdown，工程内提供**合规向开关**（不替代法律意见）：

| 配置（`.env`） | 默认 | 说明 |
|----------------|------|------|
| `WEB_FETCH_ENABLED` | `true` | 全局关闭则跳过所有 web 抓取 |
| `WEB_FETCH_RESPECT_ROBOTS` | `true` | 同步前读 `robots.txt`（404/失败时放行） |
| `WEB_FETCH_USER_AGENT` | `mind-sync/0.1` | 请求头 User-Agent |
| `WEB_FETCH_CONTACT` | 空 | 追加联系邮箱，如 `you@example.com` |
| `WEB_FETCH_MIN_INTERVAL_SECONDS` | `5` | 同一域名两次抓取最小间隔 |
| `WEB_FETCH_MAX_BYTES` | `5000000` | 单次 HTTP 响应体上限 |
| `WEB_FETCH_ALLOWLIST` | 空 | 逗号分隔域名；非空时仅允许列表内 |
| `WEB_FETCH_REQUIRE_ALLOWLIST` | `false` | 为 `true` 时必须配置 allowlist |
| `WEB_FETCH_REQUIRE_OPT_IN` | `false` | 为 `true` 时源须 `fetch_confirmed: true` |

`sources.yaml` 单源可选：

```yaml
- id: example_web
  type: web
  url: "https://example.com"
  fetch_confirmed: true      # 配合 WEB_FETCH_REQUIRE_OPT_IN
  respect_robots: true       # 省略则用全局 WEB_FETCH_RESPECT_ROBOTS
```

策略摘要：`GET /api/health` → `web_fetch`；`GET /api/sources` → `web_fetch_policy`。

- 响应体上限：`WEB_FETCH_MAX_BYTES`（默认 5MB）
- 条件请求：复用 `meta.json` 中的 `etag` / `last_modified`，服务器返回 304 时跳过写盘

## Wiki 系统页保护

以下路径由服务自动维护，**不可**通过 `PUT /api/wiki-content` 编辑：

- `index.md`、`log.md`、`SCHEMA.md`

## ingest 与同源配对

`POST /api/ingest` 与 sync 一样跳过已配对的 **local** 源，只索引 github 条目；响应 `warnings` 会说明跳过的 id。若对 paired local 单独 ingest 返回 **409**。

## 刻意不实现（Obsidian 侧能力）

- Obsidian 插件 / Sync / 图谱 UI 复刻
- obsidian-wiki 式 `raw/` 双轨与 Vault 内 Skill 主库
- 用 Agent 替代 SQLite FTS 检索
- LLM 语义 lint（页间矛盾检测）
- Canvas / Marp / Dataview 插件

## 摘要 frontmatter 示例

```yaml
---
type: summary
topic: harness
tags: [pipeline, ci]
sources:
  - knowledge_engineering/notes/harness-intro.md
confidence: extracted
updated: 2026-05-30
---
```

## Web 工作台

1. 登录 → **一键同步** 索引最新文件
2. **搜索**：支持分类（原始素材 / 学习摘要 / 问答沉淀）、主题、来源、文件类型
3. **分类浏览**：按当前筛选加载文档列表
4. **可信问答**：勾选「保存到 wiki/queries」可将问答写入知识库
5. **设置**：查看 `purpose.md` 预览与审计日志

## API 要点

| 接口 | 用途 |
|------|------|
| `GET /api/categories` | 分类与主题统计 |
| `GET /api/browse?category=&topic=` | 分类浏览 |
| `GET /api/search?q=&category=&topic=` | 全文搜索 |
| `GET /api/purpose` | 读取研究方向 |
| `POST /api/query` | 问答；`save_to_wiki=true` 写入 queries |
| `POST /api/lint` | 断链、孤儿页、过期摘要检查 |

## Cursor + MCP

1. 安装依赖：`pip install -r apps/mcp/requirements.txt`
2. 项目已含 `.cursor/mcp.json` — 详见 **`docs/CURSOR_MCP_SETUP.md`**
3. 启用项目 Rule：`.cursor/rules/mind-sync.mdc`

常用工具：

- `sync_sources` / `sync_status` — 同步与进度
- `search_docs` — 支持 `category`、`topic` 过滤
- `browse_docs` — 按分类浏览
- `query_wiki` — 问答 + 可选保存
- `list_categories` / `get_purpose` — 元信息
- `lint_wiki` — 质量检查

## 证据置信度

问答返回的每条 evidence 包含：

| 级别 | 含义 |
|------|------|
| EXTRACTED | 与原文高度匹配 |
| INFERRED | 基于上下文的合理推断 |
| AMBIGUOUS | 信息不足，需人工确认 |
| UNVERIFIED | 低置信，不应作为事实陈述 |

## 移动端 / 外网 HTTPS

生产或手机访问建议：

1. 使用反向代理（Caddy / Nginx）终止 TLS
2. `.env` 设置：
   - `COOKIE_SECURE=true`
   - `SECURITY_HSTS_ENABLED=true`
   - `CORS_ALLOW_ORIGINS=https://your-domain.example`
3. Web 已使用响应式布局；窄屏下搜索栏自动换行

示例 Caddyfile 片段：

```
your-domain.example {
  reverse_proxy localhost:8080
}
```

API 若需单独暴露，可为 `localhost:8000` 增加子路径或子域名代理，并保持 `x-api-key` 鉴权。

## 权限（RBAC）

| 角色 | 能力 |
|------|------|
| **admin** | Wiki 编辑、同步/全量重建、Vault 拉推、purpose/设置、Lint、问答保存到 wiki |
| **viewer** | 搜索、浏览、图谱、问答（**不可**保存到 wiki、不可改磁盘内容） |

- 单用户：仅配置 `AUTH_PASSWORD`，登录用户名为 `default`（Web 用户名可留空），角色为 admin。
- 多用户：`.env` 中设置 `AUTH_USERS`；密码推荐 bcrypt（`python scripts/generate_secrets.py hash-password '...'`），例如  
  `AUTH_USERS=admin:$2b$12$...:admin,reader:$2b$12$...:viewer`
- MCP / CLI 的 `API_KEY` 始终视为 **admin**。

## 日常维护清单

- [ ] 新增摘要后执行同步
- [ ] 定期 `lint_wiki` 修复断链与孤儿页
- [ ] 更新 `purpose.md` 反映当前学习方向
- [ ] 重要问答勾选保存，形成 queries 沉淀
