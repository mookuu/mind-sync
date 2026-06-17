# 踩坑记录

> 开发过程中遇到的问题、根因与修复方案。供后续维护参考。

---

## 1. 认证重写：`_seed_users_to_db()` 在模块导入时执行

**现象**：Docker 构建时 API 容器启动失败，日志 `no such table: users`。

**根因**：`auth.py` 末尾有模块级调用 `_seed_users_to_db()`，但该函数执行时 `init_db()` 还未运行，`users` 表尚未创建。

**修复**：将 `_seed_users_to_db()` 从 `auth.py` 移至 `db.py` 的 `init_db()` 中，在表创建完成后调用。

```
auth.py 删除函数 + 删除模块级调用
db.py   新增函数 + init_db() 末尾调用
```

**教训**：模块级副作用（module-level side effect）要谨慎——导入顺序不可控，不要在模块加载时依赖 DB。

---

## 2. 认证重写：`login_user()` 返回元组，却被当字符串赋值

**现象**：登录后 cookie `ms_token` 的值是 `('82eeceb8…', 'default', 'admin')` 这样的 Python 元组字符串表示。

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

## 3. 认证重写：`/api/auth-mode` 缺少 `authenticated` 字段

**现象**：登录成功，但 F5 刷新页面后立刻回到登录页。cookie 和服务端 session 都还在。

**根因**：`/api/auth-mode` 返回了 `role`、`can_write`、`username`，但没有 `authenticated`。前端 `checkSession()` 依赖此字段：

```javascript
isLoggedIn.value = data.authenticated || false;
//                    undefined  →  false  ← 始终不成立
```

即使 session 有效、cookie 正常携带，`isLoggedIn` 也始终为 `false`。

**修复**：在 `auth-mode` 响应中加 `"authenticated": True`。

**教训**：前端后端字段契约要对应。后端的 `Depends(require_any_auth)` 只负责拦截未认证请求，不负责告诉前端"已认证"——需要显式返回。

---

## 4. 认证重写：旧格式 token 未被识别

**现象**：auth 重写前已登录的用户，重写后 token 不识别。

**根因**：旧 `ms_token` 是 `itsdangerous.URLSafeSerializer` 签名的字符串（如 `Im9rIiwiY...`），新系统用 `secrets.token_hex(32)` 生成 session_id。旧 token 不匹配任何 DB session。

**修复**：`_get_session_id()` 检测 token 格式——非 64 位 hex 字符串直接视为无效：

```python
if sid and (len(sid) != 64 or not all(c in "0123456789abcdef" for c in sid)):
    return ""
```

同时 login 端点先 `delete_cookie()` 再 `set_cookie()`，确保旧 cookie 被覆盖。

**教训**：系统迁移时要考虑旧 token/db 数据的兼容。不能静默识别旧格式，会给出混淆的错误信息。

---

## 5. "记住我" session 仍然受空闲超时限制

**现象**：勾选"记住我"登录后，30 分钟无操作再刷新页面，仍然回到登录页。

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

## 6. Sidebar：子菜单渲染位置错误

**现象**：点击"文档库"后，"全部文档"子菜单出现在"同步运维"下面，看起来像是"同步运维"的子项。

**根因**：`AppSidebar.vue` 采用分组渲染——先渲染所有父级菜单，再渲染所有子菜单：

```html
<!-- 所有父级 -->
<template v-for="item in navItems">...</template>
<!-- 所有子菜单 -->
<template v-for="item in navItems">...</template>
<!-- 所有平级菜单 -->
<template v-for="item in flatItems">...</template>
```

DOM 顺序是：文档库 → 同步运维 → 全部文档（文档库的子菜单）→ 同步控制… → 搜索 → 知识查询 → Wiki 图谱。

**修复**：改为按固定顺序排列，每个父级紧随其子菜单作为一个整体渲染（`.nav-group`）。

**教训**：这种"先分组后渲染"的模式在简单的列表中可以，但一旦有父子结构，DOM 顺序就与视觉顺序脱节。DOM 顺序应等于视觉顺序。

---

## 7. Sidebar：无 hover 展开/收起

**现象**：需要点击父级菜单才能展开子项，移走光标后不会自动收起。

**修复**：添加 `mouseenter`/`mouseleave` 事件处理：
- 移入父级区域 → 200ms 防抖后展开子菜单
- 移出 → 延迟 200ms 收起（避免移入子菜单时闪烁）
- 点击锁定展开（点其他父级或切视图时解锁）
- 同一时间只有一个父级 hover 展开

**教训**：桌面端 UI 的 hover 交互是用户预期行为。子菜单用 hover 展开/收起能显著提升导航效率，但要注意防抖，避免鼠标划过时频繁切换。

---

## 8. API Key：缺少删除接口

**现象**：可以在账户页面生成新 API Key，但无法删除已有 Key。

**修复**：后端加 `DELETE /api/api-keys/{id}`，前端 Account.vue 展示 Key 列表 + 每行"删除"按钮。

**教训**：CRUD 的 D 经常被忘记。提供创建接口时就要考虑资源回收。

---

## 9. 同步范围：`DEFAULT_IDS` 回退导致 checkbox 自动选中

**现象**：选中选项 2、3、4 → 取消 3、4 → 取消 2 时，3、4 又被自动选中。

**根因**：`onTogglePreset` 和 `onToggleSource` 末尾有：

```javascript
setCustomSources(ids.length ? ids : DEFAULT_IDS);
```

当最后一个选项被取消时，`ids.length` 为 0，自动回填了 `DEFAULT_IDS`（obsidian, web_snapshots, wiki）。

**修复**：去掉 `DEFAULT_IDS` 回退，传入用户实际选择的列表（可为空）：

```javascript
setCustomSources(ids);
```

**教训**："防呆"逻辑（不允许空选择）如果实现方式不当，反而会让用户困惑。用户取消所有选项应该被允许，或至少给明确提示。

---

## 10. 同步范围："全部同步"灰掉时 checkbox 状态丢失

**现象**：切换到"全部同步"时，其他选项的勾选状态消失了（全部变为未勾选）。

**根因**：`setPreset("all")` 清空了 `syncSourceIds`，而 checkbox 的 `:checked` 绑定依赖于 `syncSourceIds`。虽然加了灰掉样式，但勾选标记不见了。

**修复**：引入 `backupIds` 独立 ref，`isAll` 时用 `backupIds` 驱动显示，不依赖 `syncSourceIds`：

```javascript
const displayIds = computed(() => isAll.value ? backupIds.value : syncSourceIds.value);
```

**教训**：UI 的"展示状态"和"数据状态"应该分离。灰掉是视觉状态，勾选是数据状态——灰掉不应该清除数据。

---

## 11. Docker 镜像源限流（429 Too Many Requests）

**现象**：`docker compose build` 失败，日志 `429 Too Many Requests from docker.xuanyuan.me`。

**根因**：配置的 Docker 镜像源 `docker.xuanyuan.me` 被限流。

**修复**：
1. 等待几分钟重试
2. 换镜像源（如 `docker.m.daocloud.io`、`hub-mirror.c.163.com`）
3. 临时直连 Docker Hub
4. 只构建 API（node 基础镜像已缓存则不需要拉取）

**教训**：国内 Docker 镜像源不稳定，可配置多个 fallback 镜像源。

---

## 12. 循环导入风险：`auth.py` 和 `db.py` 相互引用

**现象**：将 `_seed_users_to_db()` 从 `auth.py` 移到 `db.py` 时，需要在 `db.py` 中 `from .services.permissions import load_auth_users`，而 `permissions.py` 又引用了 `config.py`——不会形成循环但需要小心。

**修复**：在 `db.py` 的函数体内部**局部导入**，而非模块级导入：

```python
def _seed_users_to_db(conn):
    from .services.permissions import load_auth_users  # 局部导入，避免循环
    ...
```

**教训**：跨模块的工具函数迁移时，需要检查导入链是否形成循环。Python 的局部导入可以打破循环，但也会略慢。权衡放在 `_run_migrations` 这类低频函数中是可以接受的。

---

## 13. MSYS2 路径翻译导致 Docker 数据目录错误（Windows 特有）

**现象**：Docker 容器中 `settings.data_dir` 值为 `C:/Program Files/Git/data` 而非预期的 `/data`。导致 API 连接到错误的 SQLite 文件，用户表和其他数据表各自在不同文件中，登录失败。

**根因**：

1. `.env` 文件是 Windows `CRLF`（`\r\n`）换行符：`DATA_DIR=/data\r`
2. Docker Compose 读入后，`\r` 被保留在环境变量值中
3. MSYS2/Git Bash 的路径翻译（`/data` → `C:/Program Files/Git/data`）加剧了问题

```
.env → DATA_DIR=/data\r → Docker env → settings.data_dir = '/data\r'
                                                           ↓
                                              Path('/data\r').resolve()
                                                           ↓
                                              'C:/Program Files/Git/data'
```

**修复**：

- `config.py` 添加 `@field_validator("data_dir")` 自动剥离 MSYS2 的 Windows 路径前缀
- 同时修复 `sources_file` 等路径字段
- 项目根加 `.gitattributes` 确保 `.env` 保持 LF 换行

**教训**：Windows + Docker + Git Bash 的组合下，路径相关的环境变量要格外小心。两种手段同时用最好：代码层面做防御性清洗（validator），配置层面保证文件格式正确（`.gitattributes`）。

---

## 14. 同名函数被后续 import 覆盖

**现象**：`authenticate` 函数正常工作（`password_util.verify_password` 返回 True），但登录始终 401。

**根因**：`main.py` 中有两处 import：

```python
from .services.auth import ..., authenticate     # 新的 DB+env 版本
from .services.permissions import authenticate    # ← 覆盖！只检查 .env
```

后导入的 `permissions.authenticate` 覆盖了 `auth.authenticate`。登录调用的实际上是旧的、只查 `.env` 的版本，DB 用户（moku/kan）自然无法登录。

**修复**：`from .services.permissions import authenticate` → 改为 `from .services.permissions import can_write`（只导入需要的函数）。

**教训**：同名函数被覆盖是 Python 的常见陷阱。用 IDE 或 linter 的 import 检查可以避免。建议保持模块函数命名的区分度。

---

## 15. `update_settings` 权限过严导致非管理员设置不生效

**现象**：非管理员用户在"素材管理"勾选同步范围后，界面上看起来选中了，F5 刷新后还原。

**根因**：`update_settings` 使用 `Depends(require_admin)`，非管理员调用返回 403。前端 `setCustomSources()` 在 API 调用前已更新本地响应式状态，视觉上"成功"了，但后端 DB 没保存。

**修复**：`require_admin` → `require_any_auth`，允许所有已登录用户保存同步偏好。

**教训**：前端本地状态更新不能作为操作成功的依据。API 返回 403 时应回滚本地状态。但更优雅的做法是让后端接受非管理员的合法请求。

---

## 16. 预设 ID 被 `is_known_sync_key` 过滤导致勾选丢失

**现象**：选中"Obsidian 剪藏"、"Web 快照"、"Wiki"三个共享库 → F5 刷新 → "Web 快照"变成未选中。

**根因**：`update_settings` 中用 `is_known_sync_key` 过滤 `sync_source_ids`。预设 `web_snapshots` 的 ID 不是实际来源 ID（实际来源是 `example_web:web`），被判定为"未知"而过滤掉。DB 中只存了 `["obsidian", "wiki"]`。

```
前端发送 → sync_source_ids: ["obsidian", "web_snapshots", "wiki"]
                                   ↓
is_known_sync_key("web_snapshots", sources) → False
                                   ↓
后端 DB 存储 → sync_source_ids: ["obsidian", "wiki"]  ← web_snapshots 被丢掉了
```

**修复**：在 `update_settings` 中，除了 `is_known_sync_key`，也接受来自 `list_sync_presets()` 的有效预设 ID：

```python
valid_preset_ids = {p["id"] for p in list_sync_presets() if p.get("source_ids")}
ids = [x for x in ids if is_known_sync_key(x, all_src) or x in valid_preset_ids]
```

**教训**：预设 ID 和实际来源 ID 是两个不同的命名空间。后端在做 ID 合法性校验时，两个命名空间都要考虑。前端 fallback 只能解决"显示"问题，解决不了"存储"问题。

---

## 17. 登录 session 堆积导致"多条其他设备"

**现象**：账户页面的活跃会话列表显示多条"其他设备"，包括已经过期的测试 session。

**根因**：每次登录创建新 session，旧的 session 不会被清理。开发测试过程中反复登录，session 表不断累积。

**修复**：在 `login` 端点中，创建新 session 后：
1. `cleanup_expired_sessions()` — 清理已过期的 session
2. 对每个用户保留最近 5 条 session，删除更早的

```python
rows = conn.execute("SELECT session_id FROM sessions WHERE username = ? ORDER BY last_active_at DESC", (account,))
if len(rows) > 5:
    keep = {r["session_id"] for r in rows[:5]}
    # DELETE ... NOT IN (...)
```

**教训**：无限制的 session 创建迟早会成为问题。即使是简单的个人项目，也应该有 session 数量的上限。

