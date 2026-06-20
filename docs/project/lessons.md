# Lessons Learned — mind-sync 开发踩坑记录

> **归档日期**：2026-06-17（更新：2026-07-15）
> **整理缘由**：开发过程中遇到的问题、根因与修复方案，供后续维护参考。
> **概要**：涵盖认证重写、权限边界、路径一致性、状态持久化、跨用户隔离、前端数据流、UI 交互、Docker/环境兼容性、索引重建、树组件渲染、缓存策略、权限分离、CSRF 防护等多个方面，共 53 条踩坑记录 + 通用原则总结。

---

## 目录

- [第一组：认证与 Session](#第一组认证与-session)
  - [1. 认证重写：模块级 DB 调用导致表未创建](#1-认证重写模块级-db-调用导致表未创建)
  - [2. 认证重写：返回值解构错误导致 cookie 写入元组](#2-认证重写返回值解构错误导致-cookie-写入元组)
  - [3. 认证重写：auth-mode 缺少 authenticated 字段](#3-认证重写auth-mode-缺少-authenticated-字段)
  - [4. 认证重写：旧格式 token 未被识别](#4-认证重写旧格式-token-未被识别)
  - [5. 记住我 session 仍受空闲超时限制](#5-记住我-session-仍受空闲超时限制)
  - [6. 登录 session 堆积导致多条其他设备](#6-登录-session-堆积导致多条其他设备)
- [第二组：路径与数据一致性](#第二组路径与数据一致性)
  - [7. 路径不一致：写入与读取用不同路径](#7-路径不一致写入与读取用不同路径)
  - [8. 路径缺少 segment](#8-路径缺少-segment)
  - [9. 源计数口径错误](#9-源计数口径错误)
  - [10. 前端 enrichment 覆盖了后端已提供的数据](#10-前端-enrichment-覆盖了后端已提供的数据)
  - [11. 后端 API 未返回前端需要的字段](#11-后端-api-未返回前端需要的字段)
- [第三组：前端状态与数据流](#第三组前端状态与数据流)
  - [12. 状态未持久化到 localStorage](#12-状态未持久化到-localstorage)
  - [13. 页面初始化时状态恢复条件不全](#13-页面初始化时状态恢复条件不全)
  - [14. 前端数据过滤条件过窄](#14-前端数据过滤条件过窄)
  - [15. 列表未按角色过滤](#15-列表未按角色过滤)
  - [16. 非管理员应只看到管理员选中的源](#16-非管理员应只看到管理员选中的源)
  - [17. syncPreset=all 时 syncSourceIds 为空](#17-syncpresetall-时-syncsourceids-为空)
- [第四组：权限与安全](#第四组权限与安全)
  - [18. 管理员接口被非管理员调用](#18-管理员接口被非管理员调用)
  - [19. update_settings 权限过严导致非管理员设置不生效](#19-update_settings-权限过严导致非管理员设置不生效)
  - [20. 同名函数被后续 import 覆盖](#20-同名函数被后续-import-覆盖)
- [第五组：UI 与交互](#第五组ui-与交互)
  - [21. Sidebar 子菜单渲染位置错误](#21-sidebar-子菜单渲染位置错误)
  - [22. Sidebar 无 hover 展开收起](#22-sidebar-无-hover-展开收起)
  - [23. 同步范围 DEFAULT_IDS 回退导致 checkbox 自动选中](#23-同步范围-default_ids-回退导致-checkbox-自动选中)
  - [24. 全部同步灰掉时 checkbox 状态丢失](#24-全部同步灰掉时-checkbox-状态丢失)
- [第六组：环境与配置](#第六组环境与配置)
  - [25. Docker 镜像源限流](#25-docker-镜像源限流)
  - [26. MSYS2 路径翻译导致 Docker 数据目录错误](#26-msys2-路径翻译导致-docker-数据目录错误)
  - [27. 配置文件重复行](#27-配置文件重复行)
  - [28. 循环导入风险](#28-循环导入风险)
  - [29. API Key 缺少删除接口](#29-api-key-缺少删除接口)
  - [30. 预设 ID 被 is_known_sync_key 过滤导致勾选丢失](#30-预设-id-被-is_known_sync_key-过滤导致勾选丢失)
- [第七组：索引重建与数据同步](#第七组索引重建与数据同步)
  - [35. 全量重建后文档 ID 变化导致缓存 404](#35-全量重建后文档-id-变化导致缓存-404)
  - [36. include 模式默认过窄导致文件未被索引](#36-include-模式默认过窄导致文件未被索引)
  - [37. 删除源后未清理索引文档](#37-删除源后未清理索引文档)
  - [38. load_ordered_sources 缺少用户参数](#38-load_ordered_sources-缺少用户参数)
- [第八组：前端树组件](#第八组前端树组件)
  - [39. 语言分组树导致目录结构失真](#39-语言分组树导致目录结构失真)
  - [40. TreeNode 不渲染根级文件](#40-treenode-不渲染根级文件)
  - [41. TreeBranch defaultExpanded 不响应 prop 变化](#41-treebranch-defaultexpanded-不响应-prop-变化)
  - [42. 侧边栏树缓存导致过期数据](#42-侧边栏树缓存导致过期数据)
- [第九组：UI 优化与缓存策略](#第九组ui-优化与缓存策略)
  - [43. 代码文件 escapeHtml 未调用 highlight.js](#43-代码文件-escapehtml-未调用-highlightjs)
  - [44. 浏览器 confirm() 风格不统一](#44-浏览器-confirm-风格不统一)
  - [45. 搜索结果 localStorage 缓存过期](#45-搜索结果-localstorage-缓存过期)
  - [46. 新增库在 preset=all 时自动勾选](#46-新增库在-presetall-时自动勾选)
  - [47. 删除/增加库后侧边栏树未同步更新](#47-删除增加库后侧边栏树未同步更新)
  - [48. 路径无效的库仍展示在文档树](#48-路径无效的库仍展示在文档树)
  - [49. etag 缓存提速文档库树加载](#49-etag-缓存提速文档库树加载)
- [第十组：权限分离与安全](#第十组权限分离与安全)
  - [50. CSRF cookie 丢失导致 POST 请求 403](#50-csrf-cookie-丢失导致-post-请求-403)
  - [51. 并发 DB 写入导致 auth-mode 瞬态失败](#51-并发-db-写入导致-auth-mode-瞬态失败)
  - [52. 全局同步设置跨用户覆盖](#52-全局同步设置跨用户覆盖)
  - [53. 管理员删除他人库未通知拥有者](#53-管理员删除他人库未通知拥有者)
- [通用原则总结](#通用原则总结)

---

## 第一组：认证与 Session

### 1. 认证重写：模块级 DB 调用导致表未创建

**症状**：Docker 构建时 API 容器启动失败，日志 `no such table: users`。

**根因**：`auth.py` 末尾有模块级调用 `_seed_users_to_db()`，但该函数执行时 `init_db()` 还未运行，`users` 表尚未创建。

**修复**：将 `_seed_users_to_db()` 从 `auth.py` 移至 `db.py` 的 `init_db()` 中，在表创建完成后调用。

```diff
- auth.py 删除函数 + 删除模块级调用
+ db.py 新增函数 + init_db() 末尾调用
```

**教训**：模块级副作用（module-level side effect）要谨慎——导入顺序不可控，不要在模块加载时依赖 DB。

---

### 2. 认证重写：返回值解构错误导致 cookie 写入元组

**症状**：登录后 cookie `ms_token` 的值是 `('82eeceb8…', 'default', 'admin')` 这样的 Python 元组字符串表示。

**根因**：`auth.py` 中 `login_user()` 返回 `(session_id, username, role)` 三元组，但 `main.py` 写成了：

```python
session_id = login_user(...)  # 拿到的是整个元组！
```

然后 `set_cookie("ms_token", session_id, ...)` 将元组的 `str()` 表示写入了 cookie。后续请求 `_get_session_id()` 读到非 64 位 hex 字符串 → 判定为无效 → 401。

**修复**：解构赋值

```python
session_id, _, _ = login_user(...)
```

**教训**：函数签名与调用方要保持一致。返回值类型变了，所有调用点都要同步更新。

---

### 3. 认证重写：auth-mode 缺少 authenticated 字段

**症状**：登录成功，但 F5 刷新页面后立刻回到登录页。cookie 和服务端 session 都还在。

**根因**：`/api/auth-mode` 返回了 `role`、`can_write`、`username`，但没有 `authenticated`。前端 `checkSession()` 依赖此字段：

```javascript
isLoggedIn.value = data.authenticated || false;
//                    undefined  →  false  ← 始终不成立
```

即使 session 有效、cookie 正常携带，`isLoggedIn` 也始终为 `false`。

**修复**：在 `auth-mode` 响应中加 `"authenticated": True`。

**教训**：前端后端字段契约要对应。后端的 `Depends(require_any_auth)` 只负责拦截未认证请求，不负责告诉前端"已认证"——需要显式返回。

---

### 4. 认证重写：旧格式 token 未被识别

**症状**：auth 重写前已登录的用户，重写后 token 不识别。

**根因**：旧 `ms_token` 是 `itsdangerous.URLSafeSerializer` 签名的字符串（如 `Im9rIiwiY...`），新系统用 `secrets.token_hex(32)` 生成 session_id。旧 token 不匹配任何 DB session。

**修复**：`_get_session_id()` 检测 token 格式——非 64 位 hex 字符串直接视为无效：

```python
if sid and (len(sid) != 64 or not all(c in "0123456789abcdef" for c in sid)):
    return ""
```

同时 login 端点先 `delete_cookie()` 再 `set_cookie()`，确保旧 cookie 被覆盖。

**教训**：系统迁移时要考虑旧 token/db 数据的兼容。不能静默识别旧格式，会给出混淆的错误信息。

---

### 5. 记住我 session 仍受空闲超时限制

**症状**：勾选"记住我"登录后，30 分钟无操作再刷新页面，仍然回到登录页。

**根因**：`get_session()` 中空闲超时检查对"记住我" session 也生效。session 的 TTL 虽然是 30 天，但空闲超时（默认 30 分钟）会在无请求时将 session 删除。

**修复**：当 `remember_me = 1` 时跳过空闲超时检查：

```python
if sess.get("remember_me", 0) != 1:
    idle_max = settings.session_idle_timeout_seconds
    if idle_max > 0 and (now - sess["last_active_at"]) > idle_max:
        _delete_session(conn, session_id)
        return None
```

**教训**："记住我"的语义是"长期保持登录"——空闲超时对它不应适用。功能实现时要同步考虑所有约束条件的优先级。

---

### 6. 登录 session 堆积导致多条其他设备

**症状**：账户页面的活跃会话列表显示多条"其他设备"，包括已经过期的测试 session。

**根因**：每次登录创建新 session，旧的 session 不会被清理。开发测试过程中反复登录，session 表不断累积。

**修复**：在 `login` 端点中，创建新 session 后：

1. `cleanup_expired_sessions()` — 清理已过期的 session
2. 对每个用户保留最近 5 条 session，删除更早的

```python
rows = conn.execute("SELECT session_id FROM sessions WHERE username = ? ORDER BY last_active_at DESC", (account,))
if len(rows) > 5:
    keep = {r["session_id"] for r in rows[:5]}
```

**教训**：无限制的 session 创建迟早会成为问题。即使是简单的个人项目，也应该有 session 数量的上限。

---

## 第二组：路径与数据一致性

### 7. 路径不一致：写入与读取用不同路径

**症状**：个人源在素材管理页面不可见。`user_manager.py` 写入 `/data/config/user_sources.yaml`，而 `indexer.py` 从 `/data/user_sources.yaml` 读取，两个完全不同的文件。

```python
# user_manager.py（写入方）
_USER_SOURCES_FILE = Path(settings.data_dir) / "config" / "user_sources.yaml"

# indexer.py（读取方）
user_src_file = Path(settings.data_dir) / "user_sources.yaml"    # 少了 config/
```

**教训**：同一份数据的读写路径必须共享同一个常量或配置值，不要在两处各自拼写。

**修复**：`indexer.py` 改为 `/data/config/user_sources.yaml`，与 `user_manager.py` 一致。

---

### 8. 路径缺少 segment

**症状**：个人源路径显示为 `~/data/moku/default`，正确应为 `~/data/mind-sync-data/users/moku/default`。

```python
# 错误：有 DATA_ROOT 时直接取值，丢了 "users" 段
_USER_ROOT = Path(settings.data_root) if settings.data_root else Path(settings.data_dir) / "users"

# 正确：无论是否有 DATA_ROOT，都应追加 /users
_USER_ROOT = Path(settings.data_root) / "users" if settings.data_root else Path(settings.data_dir) / "users"
```

**教训**：条件表达式的两条分支必须语义等价。fallback 路径有 `/users`，主路径也必须有。

---

### 9. 源计数口径错误

**症状**：管理员的「源数量」统计了所有 yaml 中的源（包括其他用户的私有源），显示 8 条；后改为只统计 `sources.yaml` 中的源（3 条），用户反馈漏了 "web 快照"。

```python
# 第一次修复：用 load_sources() 统计，漏了预设中的条目
source_count = sum(1 for s in all_sources if s.owner is None or s.owner == username)

# 第二次修复：用 list_sync_presets() 统计，但包含了 "all" 和 "custom"
admin_source_count = sum(1 for p in all_presets if p.get("owner") is None)

# 最终：排除系统预设
admin_source_count = sum(1 for p in all_presets
                       if p.get("owner") is None and p.get("id") not in ("all", "custom"))
```

**教训**：统计口径必须与页面展示的条目数一致。管理员看到的源是 `list_sync_presets()` 中 `owner=None` 且排除 `all`/`custom` 的条目，代码应直接复用同一口径。

---

### 10. 前端 enrichment 覆盖了后端已提供的数据

**症状**：`example_web` 路径有效性在前端素材管理页始终检测不到，同步控制页却能正确显示。

```javascript
// 错误：enrich 无条件覆盖，导致后端返回的 path_exists 被 undefined 覆盖
return filtered.map(p => ({
  ...p,
  path_exists: srcMap[p.id] ? srcMap[p.id].path_exists : undefined,
}));

// 正确：保留后端已有值，仅在后端未提供时才补充
return filtered.map(p => ({
  ...p,
  path_exists: p.path_exists !== undefined
    ? p.path_exists
    : (srcMap[p.id] ? srcMap[p.id].path_exists : undefined),
}));
```

**教训**：前端 enrichment 应遵循「后端优先」原则——后端已返回的字段不应被前端覆盖。spread 顺序很重要：`{ ...enrichment, ...backend }` vs `{ ...backend, ...enrichment }`。

---

### 11. 后端 API 未返回前端需要的字段

**症状**：`sharedPresets`（来自 `/api/settings` 的 `syncPresets`）不含 `path_exists`，而前端需要它来渲染路径有效性。

**教训**：如果前端某个 computed 需要从多个 API 拼凑数据才能得到正确结果，说明后端 API 的响应模型应该直接包含该字段。先在后端加字段，比在前端做脆弱的数据合并更可靠。

**修复**：在 `list_sync_presets()` 中为每个预设条目增加 `path_exists` 字段。

```python
items.append({
    "id": sk,
    "path": spath,
    "path_exists": Path(spath).exists() if spath and not spath.startswith(('http://', 'https://')) else None,
})
```

---

## 第三组：前端状态与数据流

### 12. 状态未持久化到 localStorage

**症状**：非管理员勾选「全部同步」后 F5 刷新，状态丢失。

```javascript
// 错误：只存到变量，未写入 localStorage
backupIds.value = [...syncSourceIds.value];
localAllMode.value = true;

// 正确：变量 + localStorage 双写
backupIds.value = [...syncSourceIds.value];
localStorage.setItem(BACKUP_KEY, JSON.stringify(backupIds.value));
localAllMode.value = true;
localStorage.setItem(LOCAL_ALL_KEY, "true");
```

**教训**：任何需要在 F5 后保留的 UI 状态，必须同时写入 localStorage。`ref` 只活在内存中。

---

### 13. 页面初始化时状态恢复条件不全

**症状**：F5 后 `backupIds` 只对管理员恢复，非管理员不恢复。

```javascript
// 错误：只检查 admin 的 syncPreset
if (syncPreset.value === "all") {
  const saved = localStorage.getItem(BACKUP_KEY);
  ...
}

// 正确：所有用户都应尝试恢复
const saved = localStorage.getItem(BACKUP_KEY);
if (saved) {
  try { backupIds.value = JSON.parse(saved); } catch { ... }
}
```

**教训**：数据恢复逻辑应考虑所有用户角色，不能只覆盖一种场景。

---

### 14. 前端数据过滤条件过窄

**症状**：非管理员 `loadPrivateSources()` 只返回 `is_owned` 的源，导致其他用户共享的源无法显示在「🌐 共享知识库」中。

```javascript
// 错误：只拿了用户自己的源
privateSources.value = data.sources.filter(s => s && s.is_owned);

// 正确：自己的源 + 其他人共享的源
privateSources.value = data.sources.filter(s => s && (s.is_owned || s.shared));
```

**教训**：过滤条件要覆盖所有需要展示的数据场景。先列出所有应该出现的条目，再写 filter。

---

### 15. 列表未按角色过滤

**症状**：被共享的个人源同时出现在「我的知识库」和「共享知识库」中。

```javascript
// 错误：groupedPrivateSources 对所有来源不区分 owner
const groupedPrivateSources = computed(() => {
  const list = privateSourceList.value;  // 包含其他人的共享源
  ...
});

// 正确：非管理员只保留自己的源
const groupedPrivateSources = computed(() => {
  const list = isAdmin.value
    ? privateSourceList.value
    : privateSourceList.value.filter(p => p.owner === currentUser.value);
  ...
});
```

**教训**：一个数据列表用于多个展示区域时，每个区域应有自己的过滤逻辑，确保数据不串区。

---

### 16. 非管理员应只看到管理员选中的源

**症状**：「📚 全局知识库」对非管理员显示了所有可用的源，包括管理员未选中的。

**修复**：当 `syncPreset !== "all"` 时，只显示 `syncSourceIds` 中存在的预设。

```javascript
if (!isAdmin.value) {
  if (syncPreset.value === "all") {
    // 全部同步 → 显示全部源
  } else {
    const activeKeys = new Set(syncSourceIds.value || []);
    filtered = filtered.filter(p => activeKeys.has(p.id));
  }
}
```

---

### 17. syncPreset=all 时 syncSourceIds 为空

**症状**：管理员选「全部同步」后，非管理员登录时全局知识库全空（`syncSourceIds` 为 `[]`）。

**根因**：`setPreset("all")` 将 `syncSourceIds` 置为 `[]`。当 `syncPreset === "all"` 时，后端无视 `syncSourceIds`，但前端 filter 逻辑直接拿空数组做匹配。

**修复**：在非管理员逻辑中先判断 `syncPreset`：

```javascript
if (syncPreset.value === "all") {
  // 不过滤，显示全部 + 全部预勾选
  customPresetIds = sharedPresets.map(p => p.id);
} else {
  // 只显示 syncSourceIds 中的源
  filtered = filtered.filter(p => activeKeys.has(p.id));
}
```

**教训**：`syncPreset === "all"` 和 `syncPreset === "custom"` 是互斥的语义。当处理 `syncSourceIds` 时，必须考虑它为空是否因为 preset 是 "all"（有效空）还是真的没有选择任何源（无效空）。

---

## 第四组：权限与安全

### 18. 管理员接口被非管理员调用

**症状**：非管理员用户的 `formatOwnerLabel` 始终只显示用户名，从未显示表示名。

```javascript
// loadUserDisplayNames 内部调用了 /api/admin/users（require_admin），非管理员拿到 403
async function loadUserDisplayNames() {
  if (!isAdmin.value) return;  // ← 直接跳过
  ...
}
```

**教训**：

- 非管理员不能调用 `/api/admin/*` 端点
- 如果需要公共用户信息，要么创建公开 API，要么在已有的公开响应中附带该数据

**修复**：在 `/api/user/sources` 响应中加 `owner_display_name` 字段，前端直接从 sources 数据中获取。

---

### 19. update_settings 权限过严导致非管理员设置不生效

**症状**：非管理员用户在"素材管理"勾选同步范围后，界面上看起来选中了，F5 刷新后还原。

**根因**：`update_settings` 使用 `Depends(require_admin)`，非管理员调用返回 403。前端 `setCustomSources()` 在 API 调用前已更新本地响应式状态，视觉上"成功"了，但后端 DB 没保存。

**修复**：`require_admin` → `require_any_auth`，允许所有已登录用户保存同步偏好。

**教训**：前端本地状态更新不能作为操作成功的依据。API 返回 403 时应回滚本地状态。但更优雅的做法是让后端接受非管理员的合法请求。

---

### 20. 同名函数被后续 import 覆盖

**症状**：`authenticate` 函数正常工作（`password_util.verify_password` 返回 True），但登录始终 401。

**根因**：`main.py` 中有两处 import：

```python
from .services.auth import ..., authenticate     # 新的 DB+env 版本
from .services.permissions import authenticate    # ← 覆盖！只检查 .env
```

后导入的 `permissions.authenticate` 覆盖了 `auth.authenticate`。登录调用的实际上是旧的、只查 `.env` 的版本。

**修复**：`from .services.permissions import authenticate` → 改为 `from .services.permissions import can_write`（只导入需要的函数）。

**教训**：同名函数被覆盖是 Python 的常见陷阱。用 IDE 或 linter 的 import 检查可以避免。建议保持模块函数命名的区分度。

---

## 第五组：UI 与交互

### 21. Sidebar 子菜单渲染位置错误

**症状**：点击"文档库"后，"全部文档"子菜单出现在"同步运维"下面，看起来像是"同步运维"的子项。

**根因**：`AppSidebar.vue` 采用分组渲染——先渲染所有父级菜单，再渲染所有子菜单。DOM 顺序与视觉顺序脱节。

**修复**：改为按固定顺序排列，每个父级紧随其子菜单作为一个整体渲染（`.nav-group`）。

**教训**：这种"先分组后渲染"的模式在简单的列表中可以，但一旦有父子结构，DOM 顺序就与视觉顺序脱节。DOM 顺序应等于视觉顺序。

---

### 22. Sidebar 无 hover 展开收起

**症状**：需要点击父级菜单才能展开子项，移走光标后不会自动收起。

**修复**：添加 `mouseenter`/`mouseleave` 事件处理，200ms 防抖 + 点击锁定展开。

**教训**：桌面端 UI 的 hover 交互是用户预期行为。子菜单用 hover 展开/收起能显著提升导航效率，但要注意防抖。

---

### 23. 同步范围 DEFAULT_IDS 回退导致 checkbox 自动选中

**症状**：选中选项 2、3、4 → 取消 3、4 → 取消 2 时，3、4 又被自动选中。

**根因**：`onTogglePreset` 末尾有 `setCustomSources(ids.length ? ids : DEFAULT_IDS)`。当最后一个选项被取消时回填了默认值。

**修复**：去掉 `DEFAULT_IDS` 回退，传入用户实际选择的列表（可为空）。

**教训**："防呆"逻辑（不允许空选择）如果实现方式不当，反而会让用户困惑。

---

### 24. 全部同步灰掉时 checkbox 状态丢失

**症状**：切换到"全部同步"时，其他选项的勾选状态消失了（全部变为未勾选）。

**根因**：`setPreset("all")` 清空了 `syncSourceIds`，而 checkbox 的 `:checked` 绑定依赖于 `syncSourceIds`。

**修复**：引入 `backupIds` 独立 ref，`isAll` 时用 `backupIds` 驱动显示。

**教训**：UI 的"展示状态"和"数据状态"应该分离。灰掉是视觉状态，勾选是数据状态——灰掉不应该清除数据。

---

## 第六组：环境与配置

### 25. Docker 镜像源限流

**症状**：`docker compose build` 失败，日志 `429 Too Many Requests from docker.xuanyuan.me`。

**根因**：配置的 Docker 镜像源被限流。

**修复**：等待重试 / 换镜像源 / 临时直连 Docker Hub。

**教训**：国内 Docker 镜像源不稳定，可配置多个 fallback 镜像源。

---

### 26. MSYS2 路径翻译导致 Docker 数据目录错误

**症状**：Docker 容器中 `settings.data_dir` 值为 `C:/Program Files/Git/data` 而非预期的 `/data`。

**根因**：

1. `.env` 文件是 Windows `CRLF` 换行符：`DATA_DIR=/data\r`
2. Docker Compose 读入后 `\r` 被保留
3. MSYS2/Git Bash 的路径翻译（`/data` → `C:/Program Files/Git/data`）

```
.env → DATA_DIR=/data\r → Docker env → settings.data_dir = '/data\r'
                                                           ↓
                                              Path('/data\r').resolve()
                                                           ↓
                                              'C:/Program Files/Git/data'
```

**修复**：`config.py` 添加 `@field_validator("data_dir")` 自动剥离 MSYS2 的 Windows 路径前缀。`.gitattributes` 确保 `.env` 保持 LF 换行。

**教训**：Windows + Docker + Git Bash 的组合下，路径相关的环境变量要格外小心。

---

### 27. 配置文件重复行

**症状**：`.env` 中 `DATA_DIR=/data` 出现了两次（重复行）。

**教训**：配置文件编辑后应做一次快速 review 检查重复/遗漏。尤其是在经历多次环境变量调整后。

---

### 28. 循环导入风险

**症状**：将 `_seed_users_to_db()` 从 `auth.py` 移到 `db.py` 时，需要在 `db.py` 中导入 `permissions.py`。

**修复**：在 `db.py` 的函数体内部**局部导入**，而非模块级导入：

```python
def _seed_users_to_db(conn):
    from .services.permissions import load_auth_users  # 局部导入
```

**教训**：跨模块的工具函数迁移时，需要检查导入链是否形成循环。Python 的局部导入可以打破循环。

---

### 29. API Key 缺少删除接口

**症状**：可以在账户页面生成新 API Key，但无法删除已有 Key。

**修复**：后端加 `DELETE /api/api-keys/{id}`，前端 Account.vue 展示 Key 列表 + 每行"删除"按钮。

**教训**：CRUD 的 D 经常被忘记。提供创建接口时就要考虑资源回收。

---

### 30. 预设 ID 被 is_known_sync_key 过滤导致勾选丢失

**症状**：选中"Obsidian 剪藏"、"Web 快照"、"Wiki"三个共享库 → F5 刷新 → "Web 快照"变成未选中。

**根因**：`update_settings` 中用 `is_known_sync_key` 过滤 `sync_source_ids`。预设 `web_snapshots` 的 ID 不是实际来源 ID（实际来源是 `example_web:web`），被判定为"未知"而过滤掉。

```
前端发送 → sync_source_ids: ["obsidian", "web_snapshots", "wiki"]
                                   ↓
is_known_sync_key("web_snapshots", sources) → False
                                   ↓
后端 DB 存储 → sync_source_ids: ["obsidian", "wiki"]  ← web_snapshots 被丢掉了
```

**修复**：在 `update_settings` 中，也接受来自 `list_sync_presets()` 的有效预设 ID：

```python
valid_preset_ids = {p["id"] for p in list_sync_presets() if p.get("source_ids")}
ids = [x for x in ids if is_known_sync_key(x, all_src) or x in valid_preset_ids]
```

**教训**：预设 ID 和实际来源 ID 是两个不同的命名空间。后端在做 ID 合法性校验时，两个命名空间都要考虑。

---

### 31. localStorage key 跨用户污染

**症状**：用户 moku 设置"全部同步"后，用户 kan 在同一浏览器登录，看到 moku 的勾选状态。moku 取消某个源勾选，kan 刷新后该源也被取消。

**根因**：`BACKUP_KEY = "sync_all_backup"` 是固定字符串，localStorage 按 origin 隔离，同一浏览器不同用户共享同一个 localStorage key。

**修复**：`backupKey()` 改为 `"sync_all_backup_" + username`，按用户作用域。

```javascript
// 错误：全局共享
const BACKUP_KEY = "sync_all_backup";

// 正确：按用户隔离
function backupKey() {
  return `sync_all_backup_${currentUser.value || 'anon'}`;
}
```

**教训**：localStorage 是 per-origin，不是 per-user。所有用户作用域的数据必须在 key 中包含用户标识。

---

### 32. app_settings 全局表导致同步设置跨用户覆盖

**症状**：kan 勾选复选框后，moku 的同步设置在刷新后也被覆盖为 kan 的选择。所有用户的 `sync_preset`/`sync_source_ids` 互相影响。

**根因**：`app_settings` 表中 `sync_preset` 和 `sync_source_ids` 的 key 是全局的（无用户前缀）。任何用户保存同步设置时，都写入同一个 key。

```
DB schema:
app_settings(key TEXT PRIMARY KEY, value TEXT)
  key = "sync_preset"        -- 全局，所有用户共享！
  key = "sync_source_ids"    -- 全局，所有用户共享！
```

**修复**：读写时在 key 前加用户名前缀 `{username}:sync_preset` / `{username}:sync_source_ids`。

```python
# 读取（get_settings）
st["sync_preset"] = _user_setting(conn, username, "sync_preset") or st.get("sync_preset", "all")

# 写入（update_settings）
_save_user_setting(conn, updater_username, "sync_preset", preset)
```

**教训**：凡是需要 per-user 状态的配置，表设计时必须包含用户维度。全局 key 只适合真正全局的配置。

---

### 33. 同一请求内两次 get_db() 导致 database locked

**症状**：`POST /api/settings` 返回 500 Internal Server Error，日志显示 `sqlite3.OperationalError: database is locked`。

**根因**：`update_settings` 先打开一个 DB 连接（`conn = get_db()`），然后在函数内部调用 `resolve_current_user(request)`，后者又调用 `get_session()` → `get_db()` 打开第二个连接。SQLite 的默认锁模式不允许同一进程中两个连接同时写入。

**修复**：将 `resolve_current_user(request)` 移到 `conn = get_db()` 之前执行，确保 session 读取的 DB 连接在进入主函数时已关闭。

```python
def update_settings(..., request: Request, ...):
    updater_username, _ = resolve_current_user(request)  # ← 先解析用户（内部 get_db → close）
    conn = get_db()                                       # ← 再打开主连接
```

**教训**：FastAPI 的 Dependency 链和业务函数内不要交叉使用 `get_db()`。在函数体 opening connection 之前，所有需要 DB 的依赖解析应已完成。

---

### 34. bind mount 路径映射导致 Path.is_relative_to() 验证假阳性

**症状**：用户 kan 添加路径 `/home/moku/data/mind-sync-data/users/kan/kdir2`，后端返回「只能在你的用户目录下添加源」。

**根因**：容器内有两个 mount 映射到同一物理目录：

- `/data` → `/home/moku/data/mind-sync-data`
- `/home/moku` → `/home/moku` (ro)

`get_user_dir("kan")` 返回 `/data/users/kan/default`（容器路径），用户输入的路径是 `/home/moku/...`（宿主机路径）。`Path.resolve()` + `.is_relative_to()` 跨 mount 点比较失败。

**修复**：放弃绝对路径比较，改为字符串匹配 `/users/<username>/` 段。

```python
user_segment = f"/users/{username}/"
if user_segment not in str(path):
    raise HTTPException(400, "只能在你的用户目录下添加源")
```

**教训**：Docker bind mount 会让同一磁盘位置有多个入口路径。路径验证不要依赖 `resolve()` 或 `is_relative_to()`，用语义化的路径段匹配更可靠。

---

### 35. Vue 3 中 v-if 优先级高于 v-for 导致子菜单全隐藏

**症状**：侧边栏所有子菜单项（规则约束、审计等）对所有用户不可见。

**根因**：`<router-link v-for="child in items" v-if="!child.admin || isAdmin">`。Vue 3 中 `v-if` 优先级高于 `v-for`，`v-if` 求值时 `child` 变量尚未被 `v-for` 赋值，表达式 `!child.admin` 抛出但不阻断，整体求值为 falsy。

**修复**：用 `<template v-for>` 包裹，`v-if` 放在内部元素上。

```html
<!-- 错误 -->
<router-link v-for="child in items" v-if="!child.admin || isAdmin">

<!-- 正确 -->
<template v-for="child in items">
  <router-link v-if="!child.admin || isAdmin">
```

**教训**：Vue 2 → Vue 3 迁移时 `v-if`/`v-for` 优先级反转是常见陷阱。永远用 `<template v-for>` + 内部 `v-if`。

---

### 36. pointer-events: none 阻止了 hover 触发的悬浮按钮

**症状**：失效源（`path_invalid`）的删除按钮 hover 时不出现。

**根因**：`.preset-row.path-invalid-row { pointer-events: none; }` 阻止了所有鼠标事件，包括 hover。删除按钮通过 CSS hover 显示（`opacity: 0 → 0.4`），无法触发。

**修复**：移除 `path-invalid-row` 的 `pointer-events: none`，仅对按钮内部设置 `pointer-events: auto`。

```css
.preset-row.path-invalid-row { opacity: 0.5; }
.preset-row.path-invalid-row .delete-source-btn,
.preset-row.path-invalid-row .share-source-btn { pointer-events: auto; }
```

**教训**：`pointer-events: none` 是核武器——它会禁用该元素及其所有子元素的一切鼠标交互。如果子元素需要 hover/click，必须单独恢复。

---

### 37. localeCompare 默认字典序导致 dir10 排在 dir2 前面

**症状**：素材管理页面和同步控制页面中，`dir10` 排在 `dir2` 前面，不符合自然阅读习惯。

**根因**：`String.localeCompare()` 默认按字典序（lexicographic）排序，"1" < "2"，所以 "dir10" < "dir2"。

**修复**：传入 `{ numeric: true }` 选项启用自然排序。

```javascript
// 错误：字典序
a.localeCompare(b)

// 正确：自然序
a.localeCompare(b, undefined, { numeric: true, sensitivity: 'base' })
```

**教训**：凡是涉及数字编号的字符串排序，默认字典序会让 `10 < 2`。必须显式启用 `numeric: true`。

---

### 38. 同步设置 global vs per-user 作用域混淆

**症状**：将 `sync_preset`/`sync_source_ids` 改为 per-user 后，管理员勾选的全局知识库无法同步给个人用户。个人用户看到的全局知识库状态与管理员不一致。

**根因**：全局知识库的选中状态应该是「管理员配置，所有用户继承」。个人用户的个性化同步选择只适用于个人源。将两者都 per-user 化，切断继承关系。

**修复**：回退 per-user 化。`sync_preset`/`sync_source_ids` 保持全局 key，管理员可写，个人用户只读。个人用户不能修改共享源 checkbox（`disabled: !isAdmin`）。跨用户 localStorage 污染问题通过 `backupKey()` 按用户名隔离即可。

**教训**：不是所有设置都需要 per-user 作用域。全局配置（如管理员选择哪些共享源）应该保持全局 key；只有真正 per-user 的数据（如个人源的勾选偏好）才需要用户隔离。先分析数据归属，再做作用域设计。

---

### 39. 页面描述文字布局调整

**症状**：多处页面标题下方的描述文字（如「勾选要同步的来源，修改后立即生效」）使用独立的 `<p class="subtle">` 标签，占用额外空间。

**修复**：将描述文字改为 `<span class="shared-tag">` 内嵌在 `<h3>` 内，小号灰色字体。

```html
<!-- 之前 -->
<h3>同步范围</h3>
<p class="subtle">勾选要同步的来源，修改后立即生效</p>

<!-- 之后 -->
<h3>同步范围 <span class="shared-tag">勾选要同步的来源，修改后立即生效</span></h3>
```

**教训**：页面内的辅助描述文字应尽量贴合主标题，通过字号/颜色区分层次，减少垂直空间的浪费。

---

## 第七组：索引重建与数据同步

### 35. 全量重建后文档 ID 变化导致缓存 404

**症状**：全量重建（rebuild）后，点击之前的搜索结果或树中的文档，返回 404 Not Found。重新搜索后跳转正常。

**根因**：`run_rebuild_job` 流程是 `clear_source_index` → `index_single_source_force`。前者 DELETE 文档行，后者 INSERT 新行（`ON CONFLICT(source_id, rel_path) DO UPDATE`，但旧行已删除 → 无冲突 → 新行获得新的自增 ID）。

```python
# clear_source_index:
DELETE FROM documents WHERE source_id = ?  # 旧 doc_id=1029 被删除

# index_single_source_force:
INSERT INTO documents(...) VALUES(...)   # 新行获得 doc_id=2050
```

前端搜索结果缓存在 localStorage 中，树缓存在 Vue 响应式变量中，都持有旧的 doc_id → 404。

**修复**：
1. 侧边栏树：移除 `if (catTrees[catKey]) return` 缓存保护，每次展开都重新加载
2. 搜索结果：缓存加 `ts` 时间戳，超过 10 分钟过期
3. 同步/重建触发时：主动 `localStorage.removeItem('mind_sync_last_search')`
4. 兜底：`Library.vue` 的 `openDoc` 检测到 404 时也清除缓存

**教训**：自增 ID 不可靠——任何可能导致行被删除后重建的操作都会改变 ID。对外暴露的引用（URL、缓存）应使用稳定标识符（如 `source_id + rel_path`）。

---

### 36. include 模式默认过窄导致文件未被索引

**症状**：添加全局库后，库内的 Java/JSON/JS 等文件无法被搜索到，文档树中也无该库。

**根因**：`admin_add_custom_source` 和 `user_add_source` 的 `include` 默认值分别是 `["**/*.md", "**/*.py"]` 和 `["**/*.md"]`（通过 `item.get("include", ["**/*.md"])`）。`collect_files` 只用这些 glob 模式匹配文件，其他后缀的文件全部跳过。

**修复**：将默认 include 扩展到 18 种常见文本文件类型：

```python
"include": [
    "**/*.md", "**/*.py", "**/*.java", "**/*.txt",
    "**/*.json", "**/*.yaml", "**/*.yml", "**/*.xml",
    "**/*.html", "**/*.css", "**/*.js", "**/*.ts",
    "**/*.sh", "**/*.bash", "**/*.sql",
    "**/*.cfg", "**/*.ini", "**/*.toml",
],
```

**教训**：默认值应该覆盖最常见的场景，宁可多索引不可漏索引。用户手动排除比手动追加容易。

---

### 37. 删除源后未清理索引文档

**症状**：从素材管理删除库后，文档库子菜单仍能看到该库的文档。

**根因**：`admin_delete_source` 和 `user_delete_source` 只从 YAML 配置中移除条目并 `reload_sources_config()`，但没有清理 SQLite 中已索引的文档行。

**修复**：在删除端点中，YAML 删除后调用 `clear_source_index(conn, source_id)` 删除 `documents` 和 `documents_fts` 表中的相关行。

```python
# admin_delete_source:
cleanup_id = parsed_id or source_id
conn = get_db()
clear_source_index(conn, cleanup_id)
conn.commit()
```

**教训**：资源删除要考虑级联：配置删了 → 索引也要删。任何一对多的数据关系，删除"一"时必须处理"多"。

---

### 38. load_ordered_sources 缺少用户参数

**症状**：非管理员用户添加私有库后，文档库「原始素材」中看不到该库。管理员能看到。

**根因**：`build_library_index` 中补充空源时调用 `load_ordered_sources()` 未传 `username`/`role` → 默认 `username=None, role=None` → `load_sources_for_user` 只返回 `owner=None` 的共享源，过滤掉了所有私有源。

```python
# 错误：未传用户上下文
all_srcs = load_ordered_sources()  # → username=None → 只返回 ownerless 源

# 正确：传入当前请求的用户
all_srcs = load_ordered_sources(username=username, role=role)
```

**修复**：
1. library 端点增加 `request: Request` 参数，`resolve_current_user` 获取用户
2. `build_library_index` 签名增加 `username, role` 参数并传递给 `load_ordered_sources`

**教训**：任何需要区分用户可见数据的 API 端点，都必须把用户上下文传递到底层数据查询函数。默认参数只适用于无需用户区分的场景。

---

## 第八组：前端树组件

### 39. 语言分组树导致目录结构失真

**症状**：文档库树中同一个源的目录结构被拆成多份（Python 树、Java 树、Markdown 树），每份只显示该语言的文件，整体结构与源的实际目录不一致。

**根因**：`_build_lang_groups` 按 `lang` 字段分组文档，每组独立构建一棵树。共享的目录路径在每个语言组里被复制一份但内容不全。

```python
# 旧逻辑：按语言分组 → 每个语言独立一棵树
by_lang: dict[str, list] = {}
for doc in docs:
    by_lang.setdefault(doc["lang"], []).append(doc)
for lang, lang_docs in by_lang.items():
    lang_groups.append({"tree": _build_lang_tree(lang_docs)})
```

**修复**：改为 `_build_lang_tree(docs)` 直接构建统一目录树，所有文件共享同一棵树，`lang` 保留为文件属性用于图标显示。

API 响应结构：`"languages": [...]` → `"tree": [...]`（源级别直接挂树，去掉中间语言分组层）。

**教训**：分组视图不应破坏原始层级结构。如果分组会导致路径重复且内容不完整，说明分组维度选错了——应该在保留源目录树的前提下通过颜色/图标区分文件类型。

---

### 40. TreeNode 不渲染根级文件

**症状**：源的根目录下的文件（如 `README.md`）在树中不可见。

**根因**：TreeNode 模板遍历 `node.children` 来渲染子节点：

```html
<template v-for="item in node.children || []" :key="item.path">
  <TreeBranch v-if="item.type === 'dir'" ...>
  <button v-else-if="item.type === 'file'" ...>
</template>
```

当 `node` 本身是文件（`type === 'file'`）时，`node.children` 为 `undefined`，`v-for` 无事可迭代 → 文件不渲染。

**修复**：在 TreeNode 模板开头加顶层文件节点的渲染分支：

```html
<button v-if="node.type === 'file'" type="button" class="file-item" ...>
  <span class="file-icon">{{ langIcon(node.lang) }}</span>
  <span class="file-name">{{ node.title || node.name }}</span>
</button>
<template v-else v-for="item in node.children || []" ...>
```

同时更新 `treeContains` 函数，检查节点自身是否匹配（不仅是 children）。

**教训**：递归组件的边界条件最容易遗漏——顶层节点和递归节点的数据结构可能不同，组件必须同时处理两种形状。

---

### 41. TreeBranch defaultExpanded 不响应 prop 变化

**症状**：从搜索页点击结果跳转到文档库后，侧边栏树的祖先节点不会自动展开到目标文档。

**根因**：TreeBranch 的 `expanded` 由 `ref(props.depth === 0 || props.defaultExpanded)` 初始化，但之后 `defaultExpanded` prop 变化时，`expanded` 不会更新。

```javascript
const expanded = ref(props.depth === 0 || props.defaultExpanded);
// props.defaultExpanded 后续变化 → expanded 不响应
```

**修复**：添加 `watch` 监听 prop 变化：

```javascript
import { watch } from "vue";
watch(() => props.defaultExpanded, (val) => {
  if (val) expanded.value = true;
});
```

**教训**：Vue 的 `ref(initialValue)` 只在组件创建时执行一次。如果需要响应 prop 变化，必须显式 `watch`。

---

### 42. 侧边栏树缓存导致过期数据

**症状**：删除库后切回文档库，已展开的树仍显示被删除的库，需要手动点击两次（收起→展开）才能刷新。

**根因**：`catTrees` 是 Vue 响应式变量，数据加载后就一直存在内存中。`toggleCatTree` 中的 `if (catTrees[catKey]) return` 阻止了重新加载。删除库后虽然 DB 数据已清，但内存中的 `catTrees` 未更新。

**修复**：
1. 移除 `if (catTrees[catKey]) return` 缓存检查
2. 在路由 watcher 中检测从其他页面进入 `/library` 时，自动收起再展开已展开的树
3. 引入 API 响应的 `etag` 指纹，etag 未变时跳过 DOM 重建（保留性能优化）

**教训**：内存缓存的数据没有过期机制就会成为过期数据源。缓存的正确做法是「缓存 + 失效策略」，而不是「缓存没有任何失效策略」。

---

## 第九组：UI 优化与缓存策略

### 43. 代码文件 escapeHtml 未调用 highlight.js

**症状**：代码文件（如 `.py`、`.java`）在文档阅读区显示为纯文本灰色块，无任何语法高亮颜色。HTML 中有 `class="language-python"` 但无 `<span class="hljs-*">` 标签。

**根因**：`Library.vue` 的 `renderedContent` 对非 markdown 文件只用了 `escapeHtml` 转义，包了一层 `<pre class="hljs"><code class="language-xxx">`，但从未调用 `hljs.highlight()`。

```javascript
// 错误：只转义，不高亮
const content = markdownIt.utils.escapeHtml(doc.content || "");
return `<pre class="hljs"><code class="language-${codeLang}">${content}</code></pre>`;
```

**修复**：从 `markdown-it.js` 导出 `hljs`，代码文件路径调用 `hljs.highlight()`：

```javascript
import { hljs } from "../markdown-it.js";
// ...
return `<pre class="hljs"><code class="language-${codeLang}">${hljs.highlight(content, { language: codeLang, ignoreIllegals: true }).value}</code></pre>`;
```

**教训**：CSS 类名只是样式约定，不等于实际高亮行为。highlight.js 的 `class="language-xxx"` + `class="hljs"` 只是约定，实际颜色来自 `<span>` 标签——必须调用 `hljs.highlight()` 才会生成这些 span。

---

### 44. 浏览器 confirm() 风格不统一

**症状**：全量重建使用 `confirm("全量重建将清空索引...")` 弹出浏览器原生对话框，与系统其他确认操作（删除用户、删除库、重置密码）的组件式 modal 风格不一致。

**修复**：替换为 Vue 组件式弹窗：

```html
<div v-if="showRebuildConfirm" class="modal-overlay" @click.self="showRebuildConfirm = false">
  <div class="confirm-dialog">
    <p>确认执行<strong>全量重建</strong>？</p>
    <p class="subtle">将清空全部索引并强制重扫所有文件...</p>
    <div class="btn-row">
      <button class="btn btn-ghost" @click="showRebuildConfirm = false">取消</button>
      <button class="btn btn-danger btn-sm" @click="doRebuild">确认重建</button>
    </div>
  </div>
</div>
```

**教训**：项目中应保持交互模式统一。`confirm()` / `alert()` / `prompt()` 是不可定制、不可主题化的浏览器原生控件，只适合快速原型。生产代码用组件式 modal。

---

### 45. 搜索结果 localStorage 缓存过期

**症状**：全量重建后，从搜索页点击之前的搜索结果跳转到文档 → 404。

**根因**：Search.vue 的 `doSearch` 将搜索结果缓存到 `localStorage`，`restoreCachedSearch` 在页面加载时恢复。rebuild 后文档 ID 变化，缓存中的 ID 已失效。

**修复**：
1. 缓存加 `ts` 时间戳，超过 10 分钟过期
2. 增量同步/全量重建开始时主动 `localStorage.removeItem('mind_sync_last_search')`
3. `Library.vue` 的 `openDoc` 返回 404 时也清缓存（兜底）

**教训**：跨会话缓存的数据必须有失效策略（TTL、事件驱动清除、版本号）。不能依赖"用户会手动刷新"。

---

### 46. 新增库在 preset=all 时自动勾选

**症状**：素材管理添加新库后，其 checkbox 默认处于勾选状态。

**根因**：`syncPreset === "all"` 时，所有源的 checkbox 都显示为已勾选。新增库后 preset 仍为 "all"，新库也被自动勾选。

**修复**：在 `addCustomPath` / `addPrivateSource` 中，若旧 `syncPreset === "all"`，reload 后转为 `"custom"` 模式并将所有源（排除新库）加入自定义列表：

```javascript
if (oldPreset === 'all') {
  const allIds = syncPresets.value
    .filter(p => p.id !== 'all' && p.id !== 'custom' && p.id !== `${newSourceId}:local`)
    .map(p => p.id);
  await setCustomSources(allIds);
}
```

**教训**：「全选」是一种隐式包含，新增条目会被自动纳入。如果需要用户显式 opt-in，应在添加操作后退出全选模式。

---

### 47. 删除/增加库后侧边栏树未同步更新

**症状**：从素材管理删除或增加库后，切回文档库，已展开的分类树仍显示旧数据，需要手动点击两次（收起→展开）刷新。

**根因**：侧边栏 `catTrees` 数据加载后保留在 Vue 内存中。路由切换不销毁 AppSidebar 组件（它在 layout 中），数据不会自动刷新。

**修复**：在 `watch(route.path)` 中检测从非 `/library` 页面进入时，自动收起再展开已展开的分类树，触发重新加载：

```javascript
if (newPath.startsWith('/library') && oldPath && !oldPath.startsWith('/library')) {
  nextTick(() => {
    for (const catKey of ['source', 'summary', 'query']) {
      if (catExpanded[catKey] && catTrees[catKey]) {
        catExpanded[catKey] = false;
        nextTick(() => toggleCatTree(catKey));  // 重新加载
      }
    }
  });
}
```

**教训**：SPA 中不销毁的全局组件需要主动感知数据变化。监听路由变化是一种轻量的事件驱动刷新方式。

---

### 48. 路径无效的库仍展示在文档树

**症状**：素材管理中标为「⚠ 路径无效」的库，在文档库树中仍然显示（count=0）。

**根因**：`build_library_index` 补充空源时未检查路径是否真实存在。

**修复**：在补充空源的循环中加路径存在性检查：

```python
spath = (src.path or "").strip()
if spath and not spath.startswith(("http://", "https://", "git@")):
    if not Path(spath).exists():
        continue  # 路径无效 → 跳过
```

**教训**：展示数据前应做完整性校验。路径无效的源无法提供任何文档，展示出来只会让用户困惑。

---

### 49. etag 缓存提速文档库树加载

**症状**：每次展开分类树都重建 DOM，即使数据未变化也有轻微闪烁。

**优化**：后端在 library API 响应中添加 `etag` 字段（源 ID + 文档数的 MD5 指纹），前端比对——相同则跳过 `catTrees = nodes` 赋值，避免 Vue 触发 DOM 重渲染。

```python
# 后端
etag_src = sorted((sid, len(dlist)) for sid, dlist in by_source.items())
etag = hashlib.md5(json.dumps(etag_src).encode()).hexdigest()[:8]
```

```javascript
// 前端
if (data.etag && catTrees[catKey] && data.etag === catTreesETag[catKey]) {
  return;  // 跳过 DOM 重建
}
catTrees[catKey] = nodes;
catTreesETag[catKey] = data.etag;
```

**教训**：数据变更频率远低于查询频率的场景，用轻量指纹做缓存验证可以消除无意义的 DOM 更新。不增加额外 API 调用，仅需 8 字符的 hash 字段。

---

## 第十组：权限分离与安全

### 50. CSRF cookie 丢失导致 POST 请求 403

**症状**：素材管理添加库时返回 `CSRF validation failed`。GET 请求正常，POST/PUT/DELETE 全部 403。

**根因**：CSRF cookie `ms_csrf` 只在登录时设置一次，无刷新机制。浏览器可能因存储清理、隐私策略等原因清除该 cookie。一旦丢失，所有变更类请求的 CSRF header 值为空 → `enforce_csrf` 中 `expected != provided` → 403。

```python
def enforce_csrf(request):
    expected = csrf_cookie_token(request)  # cookie → 可能为空
    provided = request.headers.get(csrf_header_key(), "").strip()  # header → 可能为空
    if not expected or not provided or expected != provided:
        raise HTTPException(status_code=403, detail="CSRF validation failed")
```

**修复（三层）**：

1. **后端自动补发**：`auth-mode` 端点检测 CSRF cookie 缺失时生成新 token 并返回 JSON
2. **前端写入 cookie**：`checkSession()` 收到 `csrf_token` 时写入 `document.cookie`
3. **请求层自动恢复**：`api/index.js` 检测到 403 "CSRF" 错误时自动调 `auth-mode` 刷新 token 并重试原请求

**教训**：登录态 cookie 和 CSRF cookie 的生命周期应保持一致。如果有任何一个 cookie 可以在另一个之后失效，需要自动恢复机制。CSRF 是「双通道验证」（cookie + header），两条通道中的任何一条断裂都会导致请求失败。

---

### 51. 并发 DB 写入导致 auth-mode 瞬态失败

**症状**：用户 A 在素材管理勾选/取消勾选库（触发 `POST /api/settings` 写入 `app_settings`），同时用户 B 刷新页面 → 退出登录（进入登录界面）。

**根因**：`POST /api/settings` 写入时持有 DB 写锁，用户 B 的 `auth-mode` 请求中 `get_session()` 也要写 `last_active_at`。SQLite WAL 模式下读写可并发，但两个写操作不可并发。在极端情况下（写锁持有时间超 `busy_timeout` 或系统负载高），后到的请求可能失败。

**修复**：`checkSession()` 加一次自动重试（500ms 后），覆盖瞬态故障：

```javascript
for (let attempt = 0; attempt < 2; attempt++) {
  try {
    const data = await api("/api/auth-mode");
    // ... success ...
    return true;
  } catch (e) {
    if (attempt === 0) {
      await new Promise(r => setTimeout(r, 500));
      continue;
    }
    // 两次都失败 → 真正登出
  }
}
```

**教训**：分布式/并发环境下的瞬态故障（DB 锁、网络抖动）不应直接判定为认证失败。关键操作加一次退避重试，可以显著降低误判率。

---

### 52. 全局同步设置跨用户覆盖

**症状**：管理员勾选的全局知识库无法同步给个人用户；用户 A 改勾选后用户 B 的设置被覆盖；F5 刷新后其他用户的设置丢失。

**根因**：`sync_preset` 和 `sync_source_ids` 存储在 `app_settings` 的全局键下（无用户前缀）。任何用户保存同步设置时都写入同一个 key → 后写覆盖先写。早期尝试过 per-user 化（key 加用户名前缀），但因"管理员全局配置无法同步给个人用户"而回退。

**最终方案**：Per-user sync，每个用户独立管理自己的同步范围。

```sql
-- 旧：全局键
INSERT INTO app_settings(key, value) VALUES('sync_preset', 'all');

-- 新：用户键
INSERT INTO app_settings(key, value) VALUES('moku:sync_preset', 'custom');
```

配合 DB 迁移 V7：旧全局键复制到所有 admin 用户键下，保证平滑过渡。

**教训**：全局 vs per-user 的作用域决策需要从数据归属出发。**全局配置**（管理员选哪些源作为共享库）和**用户配置**（当前用户要同步哪些库）是两个不同的概念，应该分开存储。混合在一起会导致「管理员配置」和「个人偏好」互相覆盖。

---

### 53. 管理员删除他人库未通知拥有者

**症状**：管理员从素材管理删除某个用户的私有库后，该用户下次登录完全不知道库已被删除，文档库树中该库消失（因索引被清），用户无法理解原因。

**根因**：`admin_delete_source` 只做了 YAML 删除 + `clear_source_index`，没有产生任何用户可见的通知。

**修复**：

1. 创建 `user_notifications` 表（V7 迁移）
2. `admin_delete_source` 中检测被删源的 `owner`，若非当前管理员本人 → 调用 `_add_notification(target_owner, message, action_link, highlight=True)` 写入高亮通知
3. 前端 `NotifyBar` 组件轮询 `/api/user/notifications`，高亮通知显示在页面顶部
4. 用户点击高亮通知 → 跳转同步控制页
5. 用户执行增量/全量同步后 → 通知可被标记已读

**教训**：管理员操作涉及其他用户数据时，必须有通知机制。删除操作是破坏性的，被影响方需要有明确的告知和操作指引（如「请通过同步控制页面更新库信息」）。

---

## 通用原则总结

| # | 原则 | 归类 |
|---|------|------|
| 1 | **数据源唯一**：同一数据的读写路径应共享常量，不各自拼写 | 数据一致性 |
| 2 | **分支等价**：条件表达式的所有分支应语义等价，fallback 有某路径则主路径也有 | 数据一致性 |
| 3 | **状态双写**：内存 + localStorage 都要写，缺一不可 | 前端状态 |
| 4 | **恢复全覆盖**：数据恢复逻辑对所有用户角色生效 | 前端状态 |
| 5 | **后端优先**：前端 enrichment 不覆盖后端已返回的字段 | 前后端协作 |
| 6 | **API 完备**：前端需要的字段后端直接返回，不靠多 API 拼凑 | 前后端协作 |
| 7 | **过滤全覆盖**：写 filter 前先列出所有应出现的条目 | 数据流 |
| 8 | **权限边界**：非管理员不能调 admin API，公共数据应通过公共端点暴露 | 安全 |
| 9 | **口径一致**：统计计数与展示条目用同一数据源和同一过滤条件 | 数据一致性 |
| 10 | **区域隔离**：同一数据用于多个展示区域时各自过滤，不串区 | 数据流 |
| 11 | **空值判语义**：空数组可能是有效状态（preset=all），需结合上下文判断 | 逻辑判断 |
| 12 | **签名契约**：函数返回值类型变了，所有调用点同步更新 | 代码维护 |
| 13 | **显式声明**：后端的认证中间件不自动告知前端"已认证"，需显式返回字段 | 前后端协作 |
| 14 | **防呆不防智**：不让用户取消所有选项的"防呆"逻辑，反而让用户困惑 | UX |
| 15 | **视图数据分离**：灰掉是视觉状态，勾选是数据状态，灰掉不应清除数据 | 前端架构 |
| 16 | **ID 不稳定**：自增 ID 在 DELETE + INSERT 后会变，对外引应用稳定标识符 | 数据一致性 |
| 17 | **默认即覆盖**：include/file-type 默认值应覆盖最常见场景，宁可多不可漏 | 数据完整性 |
| 18 | **级联删除**：删除"一"时必须处理关联的"多"（源 → 文档） | 数据完整性 |
| 19 | **用户上下文穿透**：需要区分用户可见数据的函数必须接收 username/role | 安全/数据隔离 |
| 20 | **分组不破结构**：分组视图不能破坏原始层级结构，应用颜色/图标区分而非拆分树 | UI/数据组织 |
| 21 | **递归组件边界**：顶层节点和递归节点的数据形状可能不同，组件需处理所有形状 | 前端架构 |
| 22 | **prop 初始化 ≠ 响应**：ref(prop.value) 只在创建时执行，后续变化需 watch | Vue 响应式 |
| 23 | **缓存配失效**：内存缓存必须配过期策略（事件驱动 / TTL / 版本号） | 性能/数据一致 |
| 24 | **类名 ≠ 行为**：CSS class 只是约定，实际效果需要调用对应的 JS 函数 | 前后端协作 |
| 25 | **UI 模式统一**：confirm()/alert() 不可定制，生产代码用组件式 modal | UX |
| 26 | **隐式包含需显式退出**：「全选」模式新增条目自动纳入，需在添加后退出全选 | UX |
| 27 | **校验后展示**：展示数据前应做完整性校验，路径无效的源不应展示 | 数据质量 |
| 28 | **指纹缓存**：数据变更频率远低于查询频率时，用轻量指纹跳过无意义更新 | 性能优化 |
| 29 | **双通道验证**：CSRF cookie + header 任一断裂都导致失败，需自动恢复 | 安全 |
| 30 | **瞬态重试**：DB 锁/网络抖动不应直接判定认证失败，关键操作加退避重试 | 可靠性 |
| 31 | **作用域归属**：全局配置和用户配置分表/分键存储，不混合 | 数据架构 |
