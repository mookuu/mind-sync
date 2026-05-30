---
type: summary
topic: harness
tags: [connector, git, kubernetes, secrets]
sources:
  - knowledge_engineering/notes/harness-intro.md
confidence: inferred
updated: 2026-05-30
---

# Harness Connector 概览

> 示例摘要：与 [[pipeline-basics]] 配套，演示 wiki 内链与分类浏览。

## 核心结论

- **Connector** 封装对外部系统的认证与连接配置，Pipeline Step 通过 Connector 引用而非硬编码凭据。
- 常见类型：Git、Docker Registry、Kubernetes Cluster、AWS/Azure/GCP、Vault 等。
- Connector 可在 Account / Org / Project 层级创建，Project 级 Connector 最常用。
- Secret 与 Connector 配合：Secret 存敏感字符串，Connector 存连接元数据 + Secret 引用。
- 轮换 API Key 时只需更新 Connector/Secret，无需改 Pipeline YAML。

## 细节说明

### 在 Pipeline 中使用

Step 配置里指定 `connectorRef`（或 UI 选择 Connector），运行时 Delegate 使用该 Connector 访问目标系统。

### Delegate

部分 Connector 类型需要 **Delegate** 在目标网络内执行（例如内网 K8s、私有 Git）。Delegate 未连通时，Execution 会在对应 Step 失败。

## 关联

- 相关摘要：[[pipeline-basics]]
- Lint 可检查 `[[wikilink]]` 断链：同步后运行 `lint_wiki` 或 Web/API `POST /api/lint`

## 待核实

- 你的 Harness 账号是否已注册 Delegate、Connector 命名规范需与团队一致
