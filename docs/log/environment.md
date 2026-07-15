# 第六组：环境与配置

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

**症状**：同步素材页面和同步控制页面中，`dir10` 排在 `dir2` 前面，不符合自然阅读习惯。

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
