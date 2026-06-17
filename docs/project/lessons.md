# Lessons Learned — mind-sync 开发踩坑记录

> **归档日期**：2026-06-17  
> **整理缘由**：开发过程中遇到的问题、根因与修复方案，供后续维护参考。  
> **概要**：涵盖认证重写、权限边界、路径一致性、状态持久化、前端数据流、UI 交互、Docker/环境兼容性等多个方面，共 25 条踩坑记录 + 通用原则总结。

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
