# 第十组：权限分离与安全

## 第十组：权限分离与安全

### 50. CSRF cookie 丢失导致 POST 请求 403

**症状**：同步素材添加库时返回 `CSRF validation failed`。GET 请求正常，POST/PUT/DELETE 全部 403。

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

**症状**：用户 A 在同步素材勾选/取消勾选库（触发 `POST /api/settings` 写入 `app_settings`），同时用户 B 刷新页面 → 退出登录（进入登录界面）。

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

**症状**：管理员从同步素材删除某个用户的私有库后，该用户下次登录完全不知道库已被删除，文档库树中该库消失（因索引被清），用户无法理解原因。

**根因**：`admin_delete_source` 只做了 YAML 删除 + `clear_source_index`，没有产生任何用户可见的通知。

**修复**：

1. 创建 `user_notifications` 表（V7 迁移）
2. `admin_delete_source` 中检测被删源的 `owner`，若非当前管理员本人 → 调用 `_add_notification(target_owner, message, action_link, highlight=True)` 写入高亮通知
3. 前端 `NotifyBar` 组件轮询 `/api/user/notifications`，高亮通知显示在页面顶部
4. 用户点击高亮通知 → 跳转同步控制页
5. 用户执行增量/全量同步后 → 通知可被标记已读

**教训**：管理员操作涉及其他用户数据时，必须有通知机制。删除操作是破坏性的，被影响方需要有明确的告知和操作指引（如「请通过同步控制页面更新库信息」）。

---
