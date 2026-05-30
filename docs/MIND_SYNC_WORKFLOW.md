# mind-sync 工作流指南

本文说明如何在 **Web、CLI、Cursor MCP** 之间协作，维护个人可信知识库。

## 核心理念

```
可信来源 (sources) → 学习摘要 (wiki/summaries) → 带证据问答 (query + evidences)
```

- **sources**：你亲自整理或信任的仓库内容（笔记、代码、官方文档摘录）
- **summaries**：对 sources 的结构化摘要，便于检索与问答
- **queries**：问答会话的沉淀，便于回顾与二次检索

## 目录结构

数据目录挂载为 Docker 卷 `./data:/data`：

| 路径 | 说明 |
|------|------|
| `/data/purpose.md` | 研究方向；首次初始化自动种子，问答时注入 LLM |
| `/data/wiki/summaries/{topic}/*.md` | 学习摘要，如 `summaries/harness/pipeline-basics.md` |
| `/data/wiki/queries/*.md` | 问答沉淀（frontmatter `type: query`） |

摘要模板：`templates/wiki/summary-template.md`

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

## 日常维护清单

- [ ] 新增摘要后执行同步
- [ ] 定期 `lint_wiki` 修复断链与孤儿页
- [ ] 更新 `purpose.md` 反映当前学习方向
- [ ] 重要问答勾选保存，形成 queries 沉淀
