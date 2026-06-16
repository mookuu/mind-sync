# Mind-Sync 优化路线图

> 基于 2025-06 会话整理：团队知识库 + 私有源 + 用户管理 + 中文搜索
>
> **全部 Phase 1~4 已于 2025-06 实施完成。** 以下内容为执行记录与后续建议。

---

## 快速回顾：已修复的 Bug

| # | 问题 | 修复内容 | 状态 |
|---|------|----------|------|
| B1 | 删除按钮挤压行宽 | CSS `position: absolute` 悬浮 | ✅ 已完成 |
| B2 | 删除失败「来源不存在: PythonBasic:local」 | 后端 `parse_sync_key()` 复合 key 匹配 | ✅ 已完成 |

---

## 总体架构

```
┌─ 用户层 ──────────────────────────────────────┐
│  admin: 管理用户 + 管理共享源 + 可见全部        │
│  member: 管理私有源 + 只读共享源                │
│  未登录: 仅共享源（只读）                       │
└───────────────────────────────────────────────┘
        │
┌─ 源层 (sources.yaml) ─────────────────────────┐
│  owner: null  → 共享源（admin 维护）             │
│  owner: alice → 私有源（alice 维护）             │
│  type: local|github|web|smb                    │
└───────────────────────────────────────────────┘
        │
┌─ 索引层 (SQLite FTS5) ────────────────────────┐
│  source_owner 列 → 按用户过滤                   │
│  jieba 预分词 → 中文词组匹配                    │
└───────────────────────────────────────────────┘
        │
┌─ Wiki 层 ──────────────────────────────────────┐
│  /wiki/shared/     → 共享知识库                  │
│  /wiki/users/{u}/  → 用户私有知识库              │
└───────────────────────────────────────────────┘
```

---

## 执行优先级

### P0 — 核心基础（必须先做，否则后续依赖）

| ID | 任务 | 涉及文件 | 预估工时 |
|----|------|----------|----------|
| P0-1 | **Source 模型加 `owner` 字段** | `models.py` | 0.5h |
| P0-2 | **sources.yaml 解析加 `owner`** | `indexer.py` | 0.5h |
| P0-3 | **`load_sources_for_user()` 按用户过滤** | `indexer.py` | 1h |
| P0-4 | **DB 迁移：documents 表加 `source_owner` 列** | `db.py`, migration | 1h |
| P0-5 | **FTS 表重建（加 `source_owner` 列）** | `db.py` | 0.5h |
| P0-6 | **索引时写入 `source_owner`** | `indexer.py` | 0.5h |
| P0-7 | **搜索加用户权限过滤** | `fts.py`, `main.py` | 1h |
| P0-8 | **API 端点加用户上下文** | `main.py` | 1h |

**依赖链**：P0-1 → P0-2 → P0-3 → P0-4/P0-5 → P0-6 → P0-7 → P0-8

**验收标准**：登录后只能看到共享源 + 自己的源；搜索只返回有权访问的文档

---

### P1 — 中文搜索

| ID | 任务 | 涉及文件 | 预估工时 |
|----|------|----------|----------|
| P1-1 | **`chinese_tokenizer.py` — jieba 分词封装** | `services/chinese_tokenizer.py` **新文件** | 1h |
| P1-2 | **索引时预分词** | `indexer.py`（调 `tokenize()`） | 0.5h |
| P1-3 | **搜索查询分词** | `fts.py`（调 `tokenize_query()`） | 0.5h |
| P1-4 | **筛选没有中文时不走 jieba（保持英文性能）** | `chinese_tokenizer.py` | 0.5h |
| P1-5 | **重新索引全部数据** | 一次性脚本 | 2h |
| P1-6 | **jieba 自定义词典（领域术语）** | `chinese_tokenizer.py` + 词典文件 | 0.5h |

**依赖**：P1-1 独立。P1-2/P1-3 可与 P0 并行做，但需等 P0-4/P0-5（FTS 重建）完成才能落地。

**验收标准**：
```
搜索 "知识库工程" → 命中 "知识库工程最佳实践.md"
搜索 "知识工程"  → 也能命中（jieba 分词出"知识"+"工程"的跨词匹配）
英文搜索不受影响
```

---

### P2 — 用户管理

| ID | 任务 | 涉及文件 | 预估工时 |
|----|------|----------|----------|
| P2-1 | **`GET /api/admin/users` — 列出用户** | `main.py` | 0.5h |
| P2-2 | **`POST /api/admin/users` — 创建用户（含目录）** | `main.py`, `services/user_manager.py` **新文件** | 1.5h |
| P2-3 | **`DELETE /api/admin/users/{name}` — 删除用户及其私有源** | `main.py`, `services/user_manager.py` | 1h |
| P2-4 | **`PUT /api/admin/users/{name}/role` — 修改角色** | `main.py` | 0.5h |
| P2-5 | **`GET /api/user/me` — 当前用户信息** | `main.py` | 0.5h |
| P2-6 | **`PUT /api/user/password` — 修改密码** | `main.py`（已有端点，需加当前密码验证） | 0.5h |
| P2-7 | **创建用户时自动生成专属目录 + 注册私有源** | `services/user_manager.py` | 1h |
| P2-8 | **删除用户时清理索引数据** | `services/user_manager.py`, `indexer.py` | 1h |

**依赖**：P2 全部依赖 P0-1~P0-3（Source owner 基础）。

**验收标准**：admin 在 API 层面能创建/删除用户，新用户有自己的目录和私有源。

---

### P3 — 用户私有源管理 API

| ID | 任务 | 涉及文件 | 预估工时 |
|----|------|----------|----------|
| P3-1 | **`GET /api/user/sources` — 用户可见源列表** | `main.py` | 0.5h |
| P3-2 | **`POST /api/user/sources` — 添加私有源** | `main.py` | 1h |
| P3-3 | **`DELETE /api/user/sources/{id}` — 删除私有源** | `main.py` | 0.5h |
| P3-4 | **`require_own_source()` 依赖 — 校验源归属** | `services/auth.py` | 0.5h |
| P3-5 | **`/api/admin/sources` 与 `/api/user/sources` 路由分离** | `main.py` | 0.5h |

**依赖**：P2（用户存在）+ P0（owner 过滤）。

**验收标准**：member 可通过 API 添加/删除自己的源，不能动别人的。admin 可删任何源。

---

### P4 — Wiki 用户隔离

| ID | 任务 | 涉及文件 | 预估工时 |
|----|------|----------|----------|
| P4-1 | **Wiki 路径区分 shared / users/{name}** | `services/wiki_util.py` | 1h |
| P4-2 | **Wiki 读写端点加路径权限校验** | `main.py` | 1h |
| P4-3 | **用户 Wiki 目录自动创建** | `services/user_manager.py` | 0.5h |

**依赖**：P2（用户存在）。

---

### P5 — Web UI

| ID | 任务 | 涉及文件 | 预估工时 |
|----|------|----------|----------|
| P5-1 | **素材管理页分区：共享 vs 我的知识库** | `SyncSources.vue` | 2h |
| P5-2 | **添加私有源 UI（路径输入 + 归属标签）** | `SyncSources.vue` | 1h |
| P5-3 | **用户管理页面（admin 专用）** | `UsersAdmin.vue` **新文件** | 3h |
| P5-4 | **用户设置页（改密码 + 查看自己的源）** | `UserSettings.vue` **新文件** | 2h |
| P5-5 | **文档搜索结果标注源归属** | `SearchResults.vue`（或其他搜索结果组件） | 1h |
| P5-6 | **私有源图标/标签（🔒 私有的 vs 📚 共享的）** | CSS + 模板 | 0.5h |
| P5-7 | **文件缺失警告提示** | `SyncSources.vue` 或文档库页面 | 1h |

**依赖**：P5-1 依赖 P3；P5-3/P5-4 依赖 P2。

---

### P6 — 管理端增强（可选）

| ID | 任务 | 涉及文件 | 预估工时 |
|----|------|----------|----------|
| P6-1 | **管理员 Dashboard：用户统计、源占用** | `main.py`, 新 Vue 组件 | 2h |
| P6-2 | **批量重新索引** | `main.py` | 0.5h |
| P6-3 | **数据导出/备份** | 脚本 | 2h |

---

## 依赖关系图

```
P0 (核心基础)
  ├── P0-1~P0-3 Source + owner 模型
  ├── P0-4~P0-6 索引层
  └── P0-7~P0-8 API 过滤
       │
       ├── P1 (中文搜索) ← 可并行，但 FTS 重建需等 P0-4
       │
       ├── P2 (用户管理) ← 依赖 P0-3
       │    │
       │    ├── P3 (私有源 API) ← 依赖 P2
       │    │    │
       │    │    └── P5-1~P5-2 (UI 分区) ← 依赖 P3
       │    │
       │    ├── P4 (Wiki 隔离) ← 依赖 P2
       │    │
       │    └── P5-3~P5-4 (UI 用户管理 + 设置) ← 依赖 P2
       │
       └── P5-5~P5-7 (UI 其他) ← 依赖 P0
```

---

## 执行状态

```
Phase 1 ── 核心基础 + 中文搜索          ✅ 已完成
  ├─ P0-1 Source 模型加 owner 字段      ✅ models.py
  ├─ P0-2 sources.yaml 解析加 owner     ✅ indexer.py
  ├─ P0-3 load_sources_for_user()       ✅ indexer.py
  ├─ P0-4 DB 迁移                       ✅ db.py
  ├─ P0-5 FTS 表重建                    ✅ db.py
  ├─ P0-6 索引时写入 source_owner       ✅ indexer.py
  ├─ P0-7 搜索加用户权限过滤            ✅ fts.py
  ├─ P0-8 API 端点加用户上下文          ✅ main.py + auth.py
  ├─ P1-1 chinese_tokenizer.py          ✅ 新文件
  ├─ P1-2 索引时预分词                  ✅ indexer.py
  ├─ P1-3 搜索查询分词                  ✅ fts.py
  ├─ P1-4 无中文不走 jieba             ✅ 内置
  ├─ P1-5 重新索引脚本                  ✅ scripts/reindex.py
  └─ P1-6 jieba 自定义词典              ✅ apps/api/app/data/jieba_dict.txt

Phase 2 ── 用户管理                     ✅ 已完成
  ├─ P2-1 GET /api/admin/users          ✅ main.py
  ├─ P2-2 POST /api/admin/users         ✅ main.py + user_manager.py
  ├─ P2-3 DELETE /api/admin/users/{name} ✅ main.py + user_manager.py
  ├─ P2-4 PUT /api/admin/users/{name}/role ✅ main.py
  ├─ P2-5 GET /api/user/me              ✅ main.py
  ├─ P2-6 PUT /api/user/password        ✅ 已有（含当前密码验证）
  ├─ P2-7 用户目录 + 默认源            ✅ user_manager.py
  └─ P2-8 清理索引数据                  ✅ user_manager.py

Phase 3 ── 私有源 API + UI             ✅ 已完成
  ├─ P3-1 GET /api/user/sources         ✅ main.py
  ├─ P3-2 POST /api/user/sources        ✅ main.py
  ├─ P3-3 DELETE /api/user/sources/{id} ✅ main.py
  ├─ P3-4 require_own_source()          ✅ auth.py
  ├─ P3-5 admin/user 路由分离           ✅ main.py
  ├─ P5-1 UI 分区（共享 vs 我的）       ✅ SyncSources.vue
  ├─ P5-2 添加私有源 UI                ✅ SyncSources.vue
  └─ P5-6 私有源图标/标签              ✅ SyncSources.vue

Phase 4 ── Wiki 隔离                    ✅ 已完成
  ├─ P4-1 Wiki 路径 shared/users/{name}  ✅ wiki_util.py
  ├─ P4-2 读写端点权限校验              ✅ main.py
  └─ P4-3 用户 Wiki 目录自动创建        ✅ user_manager.py

Phase 5 ── UI + 管理功能                ✅ 已完成
  ├─ P5-3 UsersAdmin.vue 用户管理页     ✅ 新文件
  ├─ P5-4 Account.vue 扩展              ✅ 用户信息卡片
  ├─ P5-5 搜索结果标注源归属            ✅ Search.vue 🔒 标签
  ├─ P5-7 文件缺失警告                  ✅ SyncControl.vue
  ├─ P6-1 Admin Dashboard               ✅ AdminDashboard.vue
  ├─ P6-2 批量重索引 API + 按钮         ✅ /api/admin/reindex
  └─ P6-3 数据备份脚本                  ✅ scripts/backup.py

待办（需服务器环境）：
  └─ 运行 scripts/reindex.py（需 jieba 已安装）
```

---

## 文件变更清单（完整）

### 新增文件

| 文件 | 用途 | 属于 Phase |
|------|------|-----------|
| `apps/api/app/services/chinese_tokenizer.py` | jieba 分词封装 | Phase 1 |
| `apps/api/app/services/user_manager.py` | 用户目录管理、源清理 | Phase 2 |
| `data/jieba_dict.txt` | jieba 自定义词典 | Phase 1 |
| `apps/web-new/src/views/UsersAdmin.vue` | 用户管理页面 | Phase 4 |
| `apps/web-new/src/views/UserSettings.vue` | 用户设置页面 | Phase 4 |

### 修改文件

| 文件 | 改动 | 属于 Phase |
|------|------|-----------|
| `apps/api/app/models.py` | `Source` dataclass 加 `owner` 字段 | P0-1 |
| `apps/api/app/services/indexer.py` | 解析 owner + 索引时预分词 + 写入 source_owner | P0-2, P0-6, P1-2 |
| `apps/api/app/services/source_sync_key.py` | `_VALID_TYPES` 加新 type | P0-2 |
| `apps/api/app/services/fts.py` | 搜索加用户权限过滤 + 查询分词 | P0-7, P1-3 |
| `apps/api/app/services/auth.py` | `resolve_username()`, `require_own_source()`, `require_any_role()` | P0-8, P3-4 |
| `apps/api/app/db.py` | DB 迁移：documents 加 source_owner 列，FTS 重建 | P0-4, P0-5 |
| `apps/api/app/main.py` | 新 API 端点（用户管理、私有源管理、搜索过滤接入） | 多 Phase |
| `apps/web-new/src/views/SyncSources.vue` | 分区显示共享/私有源 | Phase 3 |
| `apps/web-new/src/api/index.js` | 按需新增请求函数 | Phase 3-4 |

### 不修改（现有功能不受影响）

- `sources.yaml` 格式兼容（`owner: null` 保持向后兼容）
- 现有 API 端点（`/api/settings`、`/api/sources`、`/api/search` 等）签名不变
- 现有认证 Cookie/API Key 机制不变
- viewer 角色行为不变（合并到 member）

---

## 关键决策记录

| 决策 | 选项 | 选择 | 理由 |
|------|------|------|------|
| FTS 中文分词 | C 扩展 vs 预分词 | **预分词（jieba）** | 纯 Python，跨平台，零编译 |
| sources 存储 | 单文件 + owner 字段 vs 每用户文件 | **单文件 + owner** | 管理简单，reload 一致 |
| 用户目录 | `/data/users/{name}/` | **统一前缀** | 权限隔离清晰，备份方便 |
| 新角色 | admin/viewer vs admin/member | **admin + member** | viewer 语义模糊，合并为 member |
| Wiki 隔离 | 路径前缀 vs 独立表 | **路径前缀** | 无需改 schema，URL 直观 |
| 搜索性能 | 纯 FTS vs 混合向量 | **FTS + LIKE fallback** | 团队规模下 FTS 足够 |

---

## 回滚策略

每个 Phase 完成后，如果线上出问题：

- **P0 回滚**：`sources.yaml` 去掉 owner 字段即可（现有不设 owner 的源自动视为共享）
- **P1 回滚**：恢复 FTS 表为无 `tokenchars` 版本，重新索引
- **P2 回滚**：用户管理的 API 是新增的，不影响已有端点
- **P3 回滚**：私有源 API 是新增的，`/api/admin/sources/*` 不变
- **P4/P5 回滚**：前端可单独回退 Vue 编译产物
