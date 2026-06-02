# mind-sync 文档索引

本目录为工程级说明。快速上手见仓库根目录 [README.md](../README.md)。

## 按角色阅读

| 你想… | 文档 |
|--------|------|
| 启动 Docker、备份、HTTPS | [DEPLOYMENT.md](./DEPLOYMENT.md) |
| 理解整体架构与模块 | [ARCHITECTURE.md](./ARCHITECTURE.md) |
| 配置 `sources.yaml`、多源类型 | [SOURCES.md](./SOURCES.md) |
| 日常维护：同步 / ingest / 问答 / lint | [MIND_SYNC_WORKFLOW.md](./MIND_SYNC_WORKFLOW.md) |
| Cursor MCP 与 Skills | [CURSOR_MCP_SETUP.md](./CURSOR_MCP_SETUP.md) |
| 本地开发、测试、模块路径 | [DEVELOPMENT.md](./DEVELOPMENT.md) |
| 鉴权、RBAC、限速、合规 | [../SECURITY.md](../SECURITY.md) |

## 概念速查

```
sources.yaml（素材）  →  sync / ingest  →  SQLite FTS 索引
                              ↓
                    data/wiki/summaries（摘要）
                              ↓
                    query + evidences → queries/（可选沉淀）
```

| 操作 | 是否拉远程 | 是否改磁盘索引 |
|------|------------|----------------|
| `POST /api/sync` | 是（Vault / GitHub / Web） | 增量 upsert |
| `POST /api/ingest` | 否 | 增量 upsert |
| `POST /api/rebuild-index` | 否 | 清空所选源后强制重扫 |

## 仓库内其他 Markdown

| 路径 | 用途 |
|------|------|
| `templates/wiki/SCHEMA.md` | Agent 维护 wiki 的规范（init 时复制到 `data/wiki/`） |
| `templates/wiki/summary-template.md` | 学习摘要 frontmatter 模板 |
| `sources.example.yaml` | 来源配置示例（含 github / web / obsidian / 同源配对） |
| `.env.example` | 环境变量全集 |
| `.cursor/skills/mind-sync-*/SKILL.md` | Cursor Agent 工作流 |

## 文档维护约定

- **用户向流程**（怎么用）→ `MIND_SYNC_WORKFLOW.md`
- **运维向**（怎么部署）→ `DEPLOYMENT.md`
- **开发向**（代码在哪）→ `DEVELOPMENT.md` + `ARCHITECTURE.md`
- **配置参考**（sources / env）→ `SOURCES.md` + `.env.example`
- 根 `README.md` 保持简短：启动步骤 + 能力概览 + 指向本索引
