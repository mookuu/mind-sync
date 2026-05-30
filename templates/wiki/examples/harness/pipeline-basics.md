---
type: summary
topic: harness
tags: [pipeline, ci, cd, harness]
sources:
  - knowledge_engineering/notes/harness-intro.md
confidence: extracted
updated: 2026-05-30
---

# Harness Pipeline 基础

> 示例摘要：首次初始化时复制到 `data/wiki/summaries/harness/`。可按你的笔记修改后同步索引。

## 核心结论

- Harness Pipeline 是 CI/CD 编排单元，由 **Stage → Step** 组成，可串行或并行执行。
- **Execution** 是一次具体运行；可在 Harness UI 或触发器（Webhook、Cron、Artifact）下启动。
- 常用 Step 类型：`Run`（脚本）、`BuildAndPush`（镜像）、`K8sDeploy`（部署）、`Approval`（人工审批）。
- 变量与表达式：`${{ }}` 引用运行时输入、密钥、上一步输出；敏感值走 Harness Secret / Connector。
- 失败策略可配置重试、忽略、或阻断后续 Stage。

## 细节说明

### Stage 与 Step

- **Stage**：逻辑阶段（如 build、test、deploy），Stage 内 Step 默认并行，除非用 `strategy` 控制。
- **Step**：最小执行单元，绑定具体 Action 或 Plugin。

### 与 Connector 的关系

Pipeline 不直接保存云账号密码，而是通过 **Connector** 引用外部系统（Git、Docker Registry、K8s、AWS 等）。详见 [[connectors-overview]]。

## 关联

- 相关摘要：[[connectors-overview]]
- 原始笔记：`knowledge_engineering/...`（请替换为你的实际路径）

## 待核实

- 具体 Step 类型名称以你使用的 Harness 版本文档为准（v0 / v1 pipeline 语法略有差异）
