# 用户隔离与角色边界

## 核心约束

### 1. 必须登录

系统不面向匿名/未登录用户。所有 API 端点（除 `/api/auth-mode`、登录、health）均需认证。

- Web 端：session cookie（`ms_token`）
- CLI/MCP：`x-api-key` header

代码中 `localStorage` 匿名分支（如 `mind_sync_last_search` 裸键）仅作为**防御兜底**，正常业务流程下不会被写入。

### 2. 同步/重建是用户级隔离

`POST /api/sync` 和 `POST /api/rebuild-index` 虽然触发的是全局索引任务，但**搜索结果缓存按用户隔离**。

- 用户 `alice` 触发重建 → 只应清除 `alice` 自己的搜索缓存（`mind_sync_last_search_alice`）
- 用户 `bob` 的缓存**不受影响**
- 前端 `SyncControl.vue` 和 `Library.vue` 清除搜索缓存时，键名必须带用户名后缀，与 `Search.vue` 写入的键名保持一致

### 3. admin 角色的边界

admin 不是「超级用户」，而是拥有**额外管理功能**的成员：

| admin 额外能力 | 说明 |
|---|---|
| 用户管理（`/admin/users`） | 创建、删除、修改角色、重置密码 |
| 素材管理（`/admin/sources`） | 查看所有用户库、共享/取消共享、删除 |
| 全局库管理 | 添加/删除全局共享源（`owner=null`） |
| Wiki 全局编辑 | 写入 `shared/` 路径 |
| 系统配置 | 规则约束（purpose）、Lint |

| admin **不能**做的事 | 说明 |
|---|---|
| 查看他人私有文档 | 私有源仅本人 + admin 可见是权限模型的例外，但 admin 触发重建不应当清除他人缓存 |
| 修改他人同步设置 | 每个用户的 `sync_source_ids` 是独立的 |
| 替他人保存 Wiki 私有页 | `users/{username}/` 仅本人可写 |

### 4. 前端缓存隔离原则

所有 `localStorage` 中按用户区分的数据，键名必须包含 `username`。以下是完整清单：

| 键名 | 来源文件 | 内容 | 用途 | 隔离 |
|---|---|---|---|---|
| `mind_sync_last_page_{user}` | `App.vue` | 路由路径 | 登录后跳回上次页面 | 按用户 |
| `mind_sync_last_doc_{user}` | `App.vue` | `doc_id` | 服务器重启后恢复文档 | 按用户 |
| `mind_sync_last_search_{user}` | `Search.vue` | `{q, items[], ts}` | 搜索缓存，10 分钟过期 | 按用户 |
| `sync_all_backup_{user}` | `SyncSources.vue` | `[sourceId...]` | 全选前备份勾选，取消时恢复 | 按用户 |
| `sync_local_all_{user}` | `SyncSources.vue` | `"true"/"false"` | 非管理员「全部同步」开关 | 按用户 |
| `sync_sections_{user}` | `SyncSources.vue` | `{shared, private, ...}` | 素材页分区展开/折叠 | 按用户 |
| `sync_private_groups_{user}` | `SyncSources.vue` | `{group: bool}` | 私有库分组展开/折叠 | 按用户 |
| `mind_sync_kbd_mode_{user}` | `Library.vue` | `"scroll"/"highlight"` | 文档库键盘操作模式 | 按用户 |

> **规则**：所有 localStorage 键均按用户隔离（`_{username}` 后缀），匿名/未登录时回退裸键兜底。不同用户在同一浏览器切换登录时各自拥有独立的 UI 偏好，互不干扰。

---

## 相关文件

| 层 | 文件 | 职责 |
|---|---|---|
| 前端 | `Search.vue` → `searchCacheKey()` | 搜索结果缓存键（带用户名） |
| 前端 | `SyncControl.vue` → `searchCacheKey()` | 同步/重建后清除**当前用户**缓存 |
| 前端 | `Library.vue` → `searchCacheKey()` | 文档 404 时清除**当前用户**缓存 |
| 后端 | `sync_engine.py` | 同步引擎（全局索引任务） |
| 后端 | `permissions.py` | RBAC 角色守卫 |
| 后端 | `auth.py` | 用户解析、session 管理 |
