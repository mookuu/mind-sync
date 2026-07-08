# PRD: mind-sync v2 — 产品需求文档

> **正式版本 PRD**，融合全部历史文档 + 改善需求用户故事 + Phase 0 角色统一。
> 基于 `docs/.archive/` 归档文档交叉验证，2026-07 产出。

---

## 1. 产品概述

mind-sync 是**多用户个人学习知识库系统**。将多源 Markdown/代码索引到 SQLite FTS5，通过 Web UI / REST API / CLI / MCP 四种方式提供全文搜索与 LLM 问答，在 `data/wiki` 维护结构化摘要。

**核心能力**：

| 能力 | 说明 |
|------|------|
| 多源索引 | 本地目录、GitHub 仓库、Web 快照 — 统一 SQLite FTS5 索引 |
| 全文搜索 | BM25 排序 + jieba 中文分词 + 文件名权重提升 |
| LLM 问答 | 检索增强生成（RAG），支持 SiliconFlow / Ollama，无 LLM 时降级为检索摘要 |
| 知识沉淀 | Wiki 摘要 + 问答记录 + 链接图谱 + 质检 Lint |
| 多用户 RBAC | admin / member 角色，per-user 同步，共享/私有源隔离 |
| 多端接入 | Web (Vue 3)、CLI、MCP (Cursor/Claude Code)、REST API |

---

## 2. 系统架构

```
┌──────────────────────────────────────────────────────────────┐
│ Gateway: Web:8080 (Vue 3) | CLI | MCP | REST API:8000       │
├──────────────────────────────────────────────────────────────┤
│ API 层: FastAPI (main.py) — auth / CSRF / 限速 / 后台任务   │
├──────────────────────────────────────────────────────────────┤
│ Services: indexer / fts / sync_engine / library / wiki / …  │
├──────────────────────────────────────────────────────────────┤
│ Data: SQLite FTS5 (mind_sync.db) | sources/ | data/wiki/    │
└──────────────────────────────────────────────────────────────┘
```

**技术栈**：Python 3.12+ / FastAPI / SQLite FTS5 + jieba / Vue 3 + Vite / Docker Compose

---

## 3. 功能清单

### 3.1 核心功能

| ID | 功能 | 说明 | 版本 |
|----|------|------|------|
| F01 | 多源索引 | local/GitHub/Web 源，按 include 模式收集文件，增量 upsert | v0.1 |
| F02 | 全文搜索 | BM25 + jieba 分词 + 文件名权重 + LIKE 回退 | v0.1 |
| F03 | LLM 问答 | RAG: 搜索 → 证据 → LLM → 带置信度标签的回答 | v0.1 |
| F04 | Wiki 管理 | 摘要/问答沉淀 + index.md 自动生成 + 链接图谱 + Lint 质检 | v0.1 |
| F05 | 文档库浏览 | 按源→目录→文件层级浏览，Markdown 渲染 + 代码高亮 | v0.1 |
| F06 | 同步引擎 | 增量同步 / 全量重建 / 定时自动同步 / 同源配对 | v0.1 |

### 3.2 多用户与权限

| ID | 功能 | 说明 | 版本 |
|----|------|------|------|
| F07 | 用户管理 | CRUD + 重置密码 + 软删除 + 显示名 + 登录锁定 | v0.1 |
| F08 | RBAC 角色 | admin / member，角色权限隔离 | v0.1 → Phase 0 |
| F09 | 源隔离 | source_owner 标记，共享源 / 私有源 / 共享个人源 | v0.1 |
| F10 | Per-user 同步 | 每个用户独立管理同步范围，结果仅自己可见 | 2026-07 |
| F11 | 权限菜单 | 管理员专属菜单不可见；URL 直接访问拦截 | 2026-07 |

### 3.3 素材管理

| ID | 功能 | 说明 | 版本 |
|----|------|------|------|
| F12 | 素材管理 UI | 全局知识库 / 我的知识库 / 共享知识库 三区布局 | 2026-07 |
| F13 | 默认库置顶 | Obsidian/Web快照/Wiki 默认勾选且排在全局库最前 | 2026-07 |
| F14 | 新增库不自动勾选 | preset=all 时添加后自动转 custom | 2026-07 |
| F15 | 路径有效性检测 | 无效路径标记 ⚠，不出现在文档库树中 | 2026-07 |
| F16 | include 扩展 | 18 种常见文本类型覆盖 | 2026-07 |

### 3.4 通知与审计

| ID | 功能 | 说明 | 版本 |
|----|------|------|------|
| F17 | 通知系统 | user_notifications 表 + NotifyBar 组件 + 轮询；顶栏铃铛+角标 ⬜ | 2026-07 |
| F18 | 删除通知 | 管理员删他人库 → 高亮通知 → 点击跳转同步控制 | 2026-07 |
| F19 | 操作记录 | 审计→操作记录，角色过滤，高亮跳转 | 2026-07 |

### 3.5 UI/UX

| ID | 功能 | 说明 | 版本 |
|----|------|------|------|
| F20 | 代码高亮 | highlight.js 支持 Python/Java/JS 等 12+ 语言 | 2026-07 |
| F21 | 图片显示 | Markdown 本地图片通过 asset 端点加载 + 深色底图增强 | 2026-07 |
| F22 | 统一 modal | 全量重建/删除确认等使用组件式弹窗 | 2026-07 |
| F23 | 搜索跨页面保持 | 搜索结果缓存 + TTL 10 分钟 + 重建自动清空 | 2026-07 |
| F24 | 搜索跳转展开树 | 搜索结果点击 → 侧边栏自动展开定位文档 | 2026-07 |
| F25 | 子菜单秒切 | 树缓存 + sync 后 event 精准清空 | 2026-07 |

### 3.6 安全

| ID | 功能 | 说明 | 版本 |
|----|------|------|------|
| F26 | CSRF 自动恢复 | cookie 丢失时 auth-mode 补发 + 前端重试 | 2026-07 |
| F27 | 登录瞬态重试 | checkSession 失败时退避重试 | 2026-07 |

### 3.7 待实施功能（已写入 UX 规范，PRD 中确认）

| ID | 功能 | 说明 | 状态 |
|----|------|------|------|
| F28 | Toast 通知系统 | 顶部居中 toast：成功/错误/警告，自动消失，可手动关闭 | ⬜ |
| F29 | Skeleton 加载占位符 | 首次加载时骨架屏代替空白/loading 文字 | ⬜ |
| F30 | 搜索增强交互 | 重置按钮 + 键盘 ↑↓ 高亮关键字跳转 + 首个高亮自动居中 | ⬜ |
| F31 | 问答流式输出 | SSE token-by-token 逐字显示 + DeepSeek-R1 推理过程折叠 | ⬜ |

---

## 4. 用户角色与权限

### 4.1 角色定义

| 角色 | 标识 | 能力 |
|------|------|------|
| **管理员 (admin)** | `admin` | 全部功能：同步、素材管理、用户管理、系统管理、Wiki 编辑、所有操作记录 |
| **成员 (member)** | `member` | 搜索、文档库、知识查询、同步（仅自己的源）、素材管理（个人库）、操作记录（仅自己） |

### 4.2 页面权限矩阵

| 页面 / 菜单 | admin | member |
|---|---|---|
| 搜索 | ✅ | ✅ |
| 文档库 | ✅ | ✅ |
| 知识查询 | ✅ | ✅ |
| 同步控制 | ✅ | ✅ |
| 素材管理 | ✅ | ✅（个人库+共享） |
| 操作记录 | ✅ 全部 | ✅ 仅自己 |
| 规则约束 | ✅ | ❌ 不可见 |
| Wiki 图谱 | ✅ | ❌ 不可见 |
| 系统管理 | ✅ | ❌ 不可见 |

### 4.3 全部同步作用域

| 角色 | 范围 |
|------|------|
| admin | 所有全局库 + 所有个人库 + 已勾选共享库 |
| member | 所有个人库 + 已勾选全局库 + 已勾选共享库 |

---

## 5. 用户故事（全部）

### US-01~11：v2 重构计划（PRD Phase 0-4）

| ID | 故事 | 优先级 | 状态 |
|----|------|--------|------|
| US-01 | 角色统一：admin/member，消除 viewer | P0 | ✅ done |
| US-02 | member 搜索只能看到共享+自己的文档 | P0 | ✅ done |
| US-03 | member 无法读取他人私有 Wiki | P0 | ⬜ |
| US-04 | API Key 审计追溯到用户 | P0 | ⬜ |
| US-05 | 环境变量 AUTH_USERS 识别 member | P0 | ✅ done |
| US-06 | main.py 拆分为 routers/ | P1 | ⬜ |
| US-07 | Swagger 补充 Pydantic response_model | P1 | ⬜ |
| US-08 | 删除重复工作流文档 | P2 | ✅ done |
| US-09 | ROADMAP 反映代码现状 | P2 | ⬜ |
| US-10 | API Key 绑定用户 | P3 | ⬜ |
| US-11 | 权限测试补充 | P4 | ⬜ |

### S1-US-01~04：文档库树

| ID | 故事 | 状态 |
|----|------|------|
| S1-01 | 目录树与源目录结构一致（统一树，不分语言） | ✅ |
| S1-02 | 根级文件（无父目录）在树中可见 | ✅ |
| S1-03 | 只显示已同步的源（同步后出现） | ✅ |
| S1-04 | 路径无效的源不显示 | ✅ |

### S2-US-01~02：代码/图片渲染

| ID | 故事 | 状态 |
|----|------|------|
| S2-01 | 代码文件语法高亮 | ✅ |
| S2-02 | Markdown 本地图片正确显示 | ✅ |

### S3-US-01~03：全文搜索

| ID | 故事 | 状态 |
|----|------|------|
| S3-01 | 搜索结果跨页面保持 | ✅ |
| S3-02 | 同步后搜索缓存自动清空；F5 保留 | ✅ |
| S3-03 | 搜索结果点击 → 侧边栏树自动展开 | ✅ |

### S4-US-01~05：素材管理

| ID | 故事 | 状态 |
|----|------|------|
| S4-01 | 管理员三区布局（全局/我的/共享） | ✅ |
| S4-02 | 默认库置顶勾选 | ✅ |
| S4-03 | 新增库不自动勾选 | ✅ |
| S4-04 | 删除他人库通知 | ✅ |
| S4-05 | include 覆盖 18 种文件类型 | ✅ |

### S5-US-01~04：同步控制

| ID | 故事 | 状态 |
|----|------|------|
| S5-01 | 全员可同步，结果 per-user | ✅ |
| S5-02 | 全部同步作用域精确化 | ✅ |
| S5-03 | 全量重建使用 modal 弹窗 | ✅ |
| S5-04 | 删除源后树同步更新 | ✅ |

### S6-US-01~03：权限与菜单

| ID | 故事 | 状态 |
|----|------|------|
| S6-01 | 管理员专属菜单完全不可见 | ✅ |
| S6-02 | URL 直接访问拦截 + 提示 | ✅ |
| S6-03 | 角色定义统一 admin/member | ✅ |

### S7-US-01~02：操作记录

| ID | 故事 | 状态 |
|----|------|------|
| S7-01 | 角色过滤（admin 全部/member 仅自己） | ✅ |
| S7-02 | 被删库记录高亮 + 点击跳转 | ✅ |

### S8-US-01~02：子菜单性能

| ID | 故事 | 状态 |
|----|------|------|
| S8-01 | 子菜单切换秒开 | ✅ |
| S8-02 | 仅 sync/rebuild 后清缓存 | ✅ |

### S9-US-01~02：CSRF/登录稳定性

| ID | 故事 | 状态 |
|----|------|------|
| S9-01 | CSRF cookie 丢失自动恢复 | ✅ |
| S9-02 | 并发 DB 锁导致登录检查失败时重试 | ✅ |

### S10-US-01~04：待实施交互增强

| ID | 故事 | 状态 |
|----|------|------|
| S10-01 | Toast 通知系统：成功/错误/警告顶部居中提示 | ⬜ |
| S10-02 | Skeleton 加载占位符替代 loading 文字 | ⬜ |
| S10-03 | 搜索页：重置按钮 + 键盘 ↑↓ 高亮跳转 + 首个高亮居中 | ⬜ |
| S10-04 | 问答页：SSE 流式输出 + DeepSeek-R1 推理过程折叠 | ⬜ |

---

## 6. API 端点

### 6.1 健康与认证

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/health` | 系统健康检查 |
| GET | `/api/auth-mode` | 认证模式 + CSRF token 补发 |
| POST | `/api/login` | 密码登录 |
| POST | `/api/logout` | 登出 |
| POST | `/api/change-password` | 修改密码 |

### 6.2 搜索与浏览

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/search?q=&limit=&sort=&category=` | 全文搜索（per-user 过滤） |
| GET | `/api/library?category=` | 文档库树（per-user 过滤） |
| GET | `/api/document/{id}` | 获取文档内容 |
| GET | `/api/document/{id}/asset` | 文档附件（图片） |
| GET | `/api/categories` | 分类统计 |

### 6.3 同步

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/sync` | 增量同步（per-user） |
| POST | `/api/rebuild-index` | 全量重建（per-user） |
| GET | `/api/sync-status` | 同步进度 |

### 6.4 素材管理

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/sources` | 用户可见源列表 |
| POST | `/api/admin/sources/custom` | 添加全局库 |
| POST | `/api/admin/sources/delete` | 删除源（有 owner 时通知） |
| POST | `/api/admin/sources/reload` | 重载配置 |
| GET | `/api/user/sources` | 用户私有源列表 |
| POST | `/api/user/sources` | 添加私有源 |
| DELETE | `/api/user/sources/{id}` | 删除私有源 |
| PUT | `/api/user/sources/{id}/share` | 切换共享状态 |

### 6.5 用户管理

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/user/me` | 当前用户信息 |
| PUT | `/api/user/display-name` | 修改表示名 |
| GET | `/api/admin/users` | 列出所有用户 |
| POST | `/api/admin/users` | 创建用户 |
| DELETE | `/api/admin/users/{username}` | 删除用户 |
| PUT | `/api/admin/users/{username}/role` | 修改角色 |
| POST | `/api/admin/users/{username}/reset-password` | 重置密码 |

### 6.6 通知与操作记录

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/user/notifications` | 未读通知 |
| POST | `/api/user/notifications/{id}/read` | 标记已读 |
| GET | `/api/audit-events?limit=N` | 操作记录（角色过滤） |

### 6.7 系统管理

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/settings` | 读取当前用户设置（per-user） |
| POST | `/api/settings` | 更新当前用户设置（per-user） |
| GET | `/api/admin/stats` | 系统概览 |
| GET | `/api/purpose` | 规则约束 |
| POST | `/api/purpose` | 更新规则约束 |
| GET | `/api/vault-status` | Vault 状态 |
| POST | `/api/vault-sync` | Vault 同步 |

---

## 7. 数据模型

### 7.1 核心表

| 表 | 用途 |
|----|------|
| `documents` | 索引文档（id, source_id, rel_path, content, lang, source_owner, …） |
| `documents_fts` | FTS5 全文索引 |
| `users` | 用户（username, password_hash, role, display_name, …） |
| `sessions` | 服务端 Session |
| `api_keys` | API Key |
| `app_settings` | 应用设置（per-user 键 `{username}:sync_*`，全局键如 `auto_sync_*`） |
| `user_notifications` | 用户通知 |
| `audit_events` | 操作记录 |

### 7.2 Schema 版本历史

| 版本 | 内容 |
|------|------|
| V1 | documents 加 size 列 |
| V2 | sessions/users/api_keys 表 |
| V3 | source_owner 列 + FTS 重建 |
| V4 | users 加 display_name |
| V5 | users 加 locked_until |
| V6 | users 加 deleted_at (软删除) |
| V7 | per-user app_settings + user_notifications 表 |
| V8 | viewer→member 角色迁移 |

---

## 8. 前端架构

```
apps/web-new/src/
├── App.vue                    # 根组件
├── router/index.js            # 路由 + adminOnly 标记
├── api/index.js               # API 客户端 (CSRF + 403 重试)
├── markdown-it.js             # Markdown 渲染 + hljs
├── composables/
│   ├── useAuth.js             # 登录/登出/session (重试)
│   └── useSyncSettings.js     # 同步范围状态
├── components/
│   ├── AppSidebar.vue         # 角色感知菜单
│   ├── NotifyBar.vue          # 顶部通知条
│   ├── TreeBranch.vue         # 树分支
│   └── TreeNode.vue           # 树节点 (递归 + 根文件)
└── views/
    ├── Library.vue            # 文档库 (高亮 + 图片 + 权限提示)
    ├── Search.vue             # 全文搜索 (缓存 TTL)
    ├── QA.vue                 # LLM 问答
    ├── Graph.vue              # Wiki 图谱 (仅 admin)
    ├── Account.vue            # 账户
    ├── SyncControl.vue        # 同步控制 (全员可用)
    ├── SyncSources.vue        # 素材管理 (3 区布局)
    ├── SyncAudit.vue          # 操作记录 (角色过滤)
    ├── SyncPurpose.vue        # 规则约束 (仅 admin)
    ├── SyncVault.vue          # 仓库管理
    ├── AdminDashboard.vue     # 系统概览 (仅 admin)
    └── UsersAdmin.vue         # 用户管理 (仅 admin)
```

---

## 9. 环境与部署

### 9.1 快速启动

```bash
# 配置 .env (从 .env.example 复制)
cp .env.example .env

# 构建并启动
docker compose up -d --build

# 访问
http://<host>:8080  # Web 前端
http://<host>:8000  # API 直接访问
```

### 9.2 关键环境变量

| 变量 | 说明 |
|------|------|
| `AUTH_USERS` | 用户配置 CSV: `user:pass:role,...` |
| `AUTH_PASSWORD` | 默认 admin 密码 |
| `API_KEY` | API Key |
| `LLM_BASE_URL` | LLM API 地址 |
| `LLM_API_KEY` | LLM API Key |
| `LLM_MODEL` | LLM 模型名 |
| `DATA_ROOT` | 数据持久化目录 |
| `SOURCES_FILE` | sources.yaml 路径 |

---

## 10. 项目状态

### 已完成

- ✅ 全部核心功能（F01-F27）
- ✅ Phase 0 角色统一（viewer→member）
- ✅ 改善需求 S1-S9 全部用户故事
- ✅ 踩坑记录 55 条 + 通用原则 33 条

### 待实施

| 优先级 | 内容 |
|--------|------|
| P0 | US-03 Wiki 隔离、US-04 API Key 审计 |
| P1 | US-06 main.py 拆分、US-07 响应模型 |
| P2 | US-09 ROADMAP 更新 |
| P3 | US-10 API Key 绑定用户 |
| P4 | US-11 权限测试补充 |
| P4 | S10-01 Toast 通知系统 |
| P4 | S10-02 Skeleton 加载占位符 |
| P4 | S10-03 搜索增强交互 |
| P4 | S10-04 问答流式输出 |
