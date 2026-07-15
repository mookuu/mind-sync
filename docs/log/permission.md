# 第四组：权限与安全

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

**症状**：非管理员用户在"同步素材"勾选同步范围后，界面上看起来选中了，F5 刷新后还原。

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
