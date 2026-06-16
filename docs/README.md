# mind-sync 文档索引

本目录为工程级说明。快速上手见仓库根目录 [README.md](../README.md)。

## 按角色阅读

| 你想… | 文档 |
|--------|------|
| 启动 Docker、备份、HTTPS | [deployment.md](./deployment.md) |
| 理解整体架构与模块 | [architecture.md](./architecture.md) |
| Karpathy 理念对照 | [concepts/karpathy-comparison.md](./concepts/karpathy-comparison.md) |
| 配置 `sources.yaml`、多源类型 | [reference/sources.md](./reference/sources.md) |
| 日常维护：同步 / ingest / 问答 / lint | [workflow.md](./workflow.md) |
| Cursor MCP 与 Skills | [reference/mcp-setup.md](./reference/mcp-setup.md) |
| 本地开发、测试、模块路径 | [development.md](./development.md) |
| API 端点参考 | [api/endpoints.md](./api/endpoints.md) |
| 鉴权、RBAC、限速、合规 | [SECURITY.md](../SECURITY.md) |
| 待办事项 | [project/todo.md](./project/todo.md) |
| 变更日志 | [project/changelog.md](./project/changelog.md) |

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

- **用户向流程**（怎么用）→ `workflow.md`
- **运维向**（怎么部署）→ `deployment.md`
- **开发向**（代码在哪）→ `development.md` + `architecture.md`
- **配置参考**（sources / env）→ `reference/sources.md` + `.env.example`
- **API 参考** → `api/endpoints.md`
- 根 `README.md` 保持简短：启动步骤 + 能力概览 + 指向本索引

## docs/ 目录结构

```
docs/
├── README.md            ← 本索引
├── architecture.md      ← 系统架构
├── workflow.md          ← 数据流与工作流
├── deployment.md        ← 部署指南
├── development.md       ← 开发指南
├── concepts/            ← 设计理念
│   └── karpathy-comparison.md ← Karpathy 理念对照
├── reference/           ← 配置参考
│   ├── sources.md       ← sources.yaml 说明
│   └── mcp-setup.md     ← MCP 配置
├── api/
│   └── endpoints.md     ← API 端点参考
└── project/
    ├── todo.md           ← 待办事项
    └── changelog.md      ← 变更日志
```
