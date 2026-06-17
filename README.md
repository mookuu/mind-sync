# mind-sync

> 本机 Docker 的个人学习知识库 — Web + API + CLI + MCP

把多源 Markdown/代码索引到 SQLite FTS5，通过 Web / API / CLI / MCP 搜索与带证据问答，在 `data/wiki` 维护结构化摘要。

---

## 快速启动

```bash
# 1. 配置环境变量
cp .env.example .env
# 修改 .env 中 AUTH_PASSWORD、SECRET_KEY、API_KEY 等

# 2. 配置来源
cp sources.example.yaml sources.yaml

# 3. 启动
docker compose up --build -d
```

- Web 界面: `http://localhost:8080`
- API 文档: `http://localhost:8000/docs`

> 非 Docker 开发环境见 [docs/development.md](docs/development.md)。

---

## 能力概览

| 能力           | 说明                                                                               |
| -------------- | ---------------------------------------------------------------------------------- |
| **多源索引**   | local / GitHub / Web 三种来源，统一 SQLite FTS5 全文搜索                           |
| **增量同步**   | 按 mtime/size/sha1 跳过未变文件；GitHub pull、Web 抓取、Vault Git                  |
| **带证据问答** | LLM 可选；搜索结果打置信度标签（EXTRACTED / INFERRED / AMBIGUOUS / UNVERIFIED）    |
| **知识管理**   | `wiki/summaries/`（摘要） + `wiki/queries/`（问答沉淀） + `purpose.md`（规则约束） |
| **Wiki 质检**  | 断链检测、孤儿页、过期摘要（stale-summary）                                        |
| **RBAC**       | admin / member 两角色；API Key 始终视为 admin；成员可管理私有源                      |
| **私有知识库** | 每个成员有自己的私有源（owner 隔离），仅自己可见和搜索                               |
| **中文搜索**   | 基于 jieba 分词的 FTS5 中文全文搜索；支持自定义领域词典                              |
| **用户管理**   | 管理员可在 API 层面创建/删除用户；新建用户自动生成专属目录                            |
| **Wiki 隔离**  | `wiki/shared/` 全局知识库 + `wiki/users/{name}/` 私有 Wiki 页                        |
| **安全**       | 登录限速、CSRF、审计日志、Session TTL、可配 CORS/HSTS                              |
| **自动同步**   | 可选定时同步，展示下次同步时间与最近状态                                           |

> 详细架构说明见 [docs/architecture.md](docs/architecture.md)。

---

## 访问方式

| 方式    | 入口                               | 鉴权                 | 适用场景                     |
| ------- | ---------------------------------- | -------------------- | ---------------------------- |
| **Web** | `http://localhost:8080`            | Cookie 会话          | 人工搜索、浏览、设置         |
| **API** | `http://localhost:8000`            | `x-api-key` / Cookie | 自动化、程序集成             |
| **CLI** | `python apps/cli/mind_sync_cli.py` | `--api-key`          | 终端工作流                   |
| **MCP** | `apps/mcp/server.py`               | `MINDSYNC_API_KEY`   | Cursor / Claude Code / Codex |

各方式详细用法见 [docs/workflow.md](docs/workflow.md)。

---

## 目录结构

```
data/                        # 持久化数据卷
├── mind_sync.db             # SQLite FTS 索引
├── purpose.md               # 规则约束（问答时注入 LLM）
└── wiki/
    ├── SCHEMA.md             # Agent 维护规范
    ├── index.md              # 自动目录
    ├── log.md                # 事件日志
    ├── summaries/{topic}/*.md  # 学习摘要
    └── queries/*.md          # 问答沉淀

sources/                     # 素材目录
├── obsidian/                # Obsidian Web Clipper 剪藏
├── web_snapshots/<id>/      # Web 源抓取快照
└── <source_id>/             # local / GitHub 克隆

docs/                        # ⬇ 完整文档入口
├── README.md                # 文档索引（建议从这里进）
├── workflow.md              # 日常使用指南
├── architecture.md          # 系统架构
├── deployment.md            # 部署、备份、HTTPS
├── development.md           # 本地开发与测试
├── reference/sources.md     # sources.yaml 配置参考
├── reference/mcp-setup.md   # Cursor MCP / Skills
└── api/endpoints.md         # API 端点参考
```

> 文档索引详见 [docs/README.md](docs/README.md)。

---

## 文档导航

| 文档                                                       | 说明                                      |
| ---------------------------------------------------------- | ----------------------------------------- |
| [docs/README.md](docs/README.md)                           | **文档索引**（分角色阅读）                |
| [docs/workflow.md](docs/workflow.md)                       | 日常使用：同步、问答、lint、Obsidian 协作 |
| [docs/architecture.md](docs/architecture.md)               | 架构与模块说明                            |
| [docs/deployment.md](docs/deployment.md)                   | Docker、备份、HTTPS、迁移                 |
| [docs/development.md](docs/development.md)                 | 本地开发、测试、模块速查                  |
| [docs/reference/sources.md](docs/reference/sources.md)     | `sources.yaml` 配置参考                   |
| [docs/reference/mcp-setup.md](docs/reference/mcp-setup.md) | Cursor MCP / Skills 配置                  |
| [docs/api/endpoints.md](docs/api/endpoints.md)             | API 端点全集                              |
| [SECURITY.md](SECURITY.md)                                 | 鉴权、RBAC、安全清单                      |
| [docs/project/changelog.md](docs/project/changelog.md)     | 变更日志                                  |

---

## 本地 Python 依赖

| 文件                     | 用途                              |
| ------------------------ | --------------------------------- |
| `requirements.txt`       | API 运行时（FastAPI、索引、同步） |
| `requirements-tools.txt` | CLI + MCP                         |
| `requirements-dev.txt`   | 开发/CI（pytest、pip-audit）      |

推荐 **Python 3.12**。Windows 一键安装：`.\scripts\install-deps.ps1 -Tools`

---

## 安全要点

- 默认 key 需替换：`AUTH_PASSWORD`、`API_KEY`、`SECRET_KEY`
- Web 源抓取合规（robots、allowlist、限速）见 [docs/workflow.md](docs/workflow.md#web-源抓取合规)
- 完整安全策略见 [SECURITY.md](SECURITY.md)

---

## 相关资源

- 摘要模板: `templates/wiki/summary-template.md`
- 来源示例: `sources.example.yaml`
- 环境变量全集: `.env.example`
- Cursor Skills: `.cursor/skills/mind-sync-{ingest,query,lint}/`
- Cursor Rule: `.cursor/rules/mind-sync.mdc`
