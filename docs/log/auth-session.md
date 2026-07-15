# 第一组：认证与 Session

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
