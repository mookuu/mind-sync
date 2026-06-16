# mind-sync 与 Karpathy LLM Wiki 理念对照

> Andrej Karpathy 在 2025 年提出了一种 **LLM-optimized Wiki** 知识库模式：
> 让 AI Agent 按规范维护结构化摘要，人类专注于阅读与提问，形成可信知识沉淀。
>
> mind-sync 从设计上借鉴了这一理念，并根据本地部署的实际场景做了取舍。

---

## 核心映射

| Karpathy 理念 | mind-sync 实现 | 位置 |
|:---|:---|:---|
| **SCHEMA.md** — Agent 维护规范 | `data/wiki/SCHEMA.md`（初始化时从 `templates/wiki/SCHEMA.md` 复制） | 知识库根目录 |
| **Purpose / 研究方向** — 约束 LLM 回答行为 | `data/purpose.md`（Web "同步运维 → 规则约束" 页面可编辑） | 知识库根目录 |
| **index.md** — 自动目录 | sync / query / lint / rebuild 后自动更新 | `data/wiki/index.md` |
| **log.md** — 事件日志 | sync / query / lint 事件自动追加 | `data/wiki/log.md` |
| **Ingest** — 素材→摘要 | `mind-sync-ingest` Skill + `POST /api/ingest` | `.cursor/skills/` + API |
| **Query** — 带证据问答 | `mind-sync-query` Skill + `POST /api/query` | `.cursor/skills/` + API |
| **Lint** — 质量检查 | `mind-sync-lint` Skill + `POST /api/lint` | `.cursor/skills/` + API |
| **stale-summary** — 源新摘要旧检测 | `lint_wiki` 内置检测 | `services/lint_engine.py` |

---

## 两条约束体系（关键区别）

Karpathy 模式中有一个容易混淆的点：**约束规则分为两层**，各自约束不同的对象。

```
┌─────────────────────────────────────────────────┐
│                  SCHEMA.md                        │
│  约束对象：AI Agent（Cursor Skill）               │
│  内容：frontmatter 格式、Ingest/Query/Lint 流程   │
│  链接约定、哪些文件自动生成不可手改                │
│  作用时机：Agent 维护 wiki 时                      │
├─────────────────────────────────────────────────┤
│               purpose.md（规则约束）               │
│  约束对象：LLM（问答时注入 prompt）                │
│  内容：回答原则、置信度要求、研究方向、优先主题     │
│  作用时机：每次 LLM 问答                           │
└─────────────────────────────────────────────────┘
```

### SCHEMA.md — 约束 Agent "怎么做"

路径：`data/wiki/SCHEMA.md`

告诉 AI Agent（Cursor Skill）如何正确维护知识库：

- 摘要 frontmatter 必须包含哪些字段（type、topic、sources、confidence、updated）
- Ingest → Query → Lint 三步工作流顺序
- Wiki 内部链接约定（`[[summaries/topic/page]]`）
- 哪些文件是系统自动生成的，不可手动修改（index.md、log.md）

### Purpose.md（规则约束）— 约束 LLM "关注什么"

路径：`data/purpose.md`

> Web 界面入口：**左侧边栏 → 🔄 同步运维 → 📋 规则约束**

在 Web 的"规则约束"页面编辑，保存后即写入 `data/purpose.md`。
问答时注入 LLM prompt 最前面，作为优先遵循的上下文约束：

```markdown
规则约束（优先遵循）：
- 所有摘要必须引用可靠来源（sources），不可编造
- 置信度分级：extracted > inferred > ambiguous > unverified
- 问答必须检索库内证据，不可靠对话记忆
```

**重要**：这个"规则约束"页面不是 SCHEMA.md 的编辑入口。两者关系是：

| | SCHEMA.md | Purpose.md（规则约束） |
|---|---|---|
| **管什么** | Agent 维护 wiki 的流程规范 | LLM 回答的方向与原则 |
| **出现时机** | ingest/query/lint 操作前 | 每次 LLM 问答时 |
| **谁读** | Agent（Cursor Skill） | LLM（回答 prompt） |
| **类比** | 操作手册 | 指令清单 |
| **Web 入口** | 无（直接编辑 `data/wiki/SCHEMA.md`） | 同步运维 → 规则约束 |

---

## 两条独立的 LLM 链路

Karpathy 模式常被误解为"把知识库作为 MCP/Skill 导入 Cursor 的 LLM"。
实际上 mind-sync 有两条独立的 LLM 通路，**规则约束只影响其中一条**：

```
链路 A：mind-sync 自身问答
────────────────────────────────────────────────────
你（Web 知识查询 / CLI query / MCP query_wiki）
  │  POST /api/query
  ▼
mind-sync 后端（FastAPI）
  │  ① 搜索 SQLite FTS 索引 → 相关文档片段
  │  ② 拼接 purpose.md（规则约束）+ 片段 + 问题
  │  ③ 调外部 LLM API（如 SiliconFlow / Ollama）
  ▼
外部 LLM → 生成结构化回答
  │
  ✅ purpose.md 规则约束在此生效


链路 B：Cursor Agent 调 MCP 工具
────────────────────────────────────────────────────
你在 Cursor 对话
  │  "用 mind-sync 的 search_docs 搜索…"
  ▼
Cursor 的 LLM（如 Claude / GPT）
  │  调 .cursor/mcp.json 中的 mind-sync MCP 服务器
  ▼
MCP 服务器 → 返回搜索结果给 Cursor 的 LLM
  │
  ❌ purpose.md 规则约束不会传入 Cursor 的 LLM
```

> **链路 A 降级**：未配置 `LLM_API_KEY` 时，问答自动降级为检索摘要
> （FTS 片段直接拼成结论/依据/引用/不确定性结构，不调用 LLM），此时规则约束也不生效。

---

## 刻意不实现的 Karpathy 能力

保留在工程范围外、明确不做的事项（摘录自 `docs/workflow.md`）：

| 能力 | 放弃理由 |
|:---|:---|
| Obsidian 插件复刻 / Sync / 图谱 UI | Obsidian 仅作为剪藏目录，不依赖其运行时 |
| Agent 替代 SQLite FTS 检索 | FTS 是确定性检索，比 LLM 幻觉更可靠 |
| LLM 语义 lint（页间矛盾检测） | 成本高、误报多，lint 保持规则驱动 |
| Canvas / Marp / Dataview 插件 | 保持 Web UI 轻量，不绑定 Obsidian 插件生态 |

---

## 数据流

```
sources.yaml（素材配置）
    │
    ▼
sync / ingest ──→ SQLite FTS5（索引）
    │
    ├── SCHEMA.md 指导 Agent 如何整理
    │
    ▼
data/wiki/summaries/（结构化摘要）
    │
    ▼
query + purpose.md（规则约束）──→ LLM 问答
    │                                        └ evidences 置信度标签
    ▼
data/wiki/queries/（可选沉淀）
```

---

## 参考链接

- [docs/workflow.md](./workflow.md) — 日常使用流程
- [docs/architecture.md](./architecture.md) — 系统架构与模块
- [templates/wiki/SCHEMA.md](../templates/wiki/SCHEMA.md) — Agent 维护规范原文
- [templates/wiki/summary-template.md](../templates/wiki/summary-template.md) — 摘要模板
- `.cursor/skills/mind-sync-{ingest,query,lint}/` — Cursor Skills 实现
