# 第十二组：重构与前端架构

## 第十二组：重构与前端架构

### 56. router 子包相对导入层级错位

**症状**：Docker compose 启动后 `router/admin.py` 等 4 个文件导入失败，容器显示 `ModuleNotFoundError`，但本地 `uvicorn` 开发运行正常。

**根因**：将 $main.py 中的端点代码迁移到 `app/routers/*.py` 子包时，代码中的相对导入未同步更新。

```
迁移前 (app/main.py):  from .db import          → app/db.py ✅
迁移后 (app/routers/*.py):  from .db import     → routers/db.py ❌
                             from ..db import    → app/db.py    ✅
```

`.` = 当前包（`routers/`），`..` = 父包（`app/`）。共 6 处需要修正。

**为什么 docker 报错而本地不报**：本地 `uvicorn app.main:app` 启动时路由模块是惰性加载（lazy import），直到匹配请求才触发导入。Docker 的某些启动路径或 pytest 配置更早触发路由模块加载，暴露了导入错误。

**修复**：`from .db` → `from ..db`；`from .services` → `from ..services`

**涉及文件**：`app/routers/knowledge.py`（4 处）、`app/routers/content.py`（2 处）

### 57. router 提取时模块映射错误

**症状**：修复第 56 条后 Docker 仍报 `ImportError: cannot import name X from module Y`，多次逐个修复。

**根因**：将 `main.py` 的端点提取为独立 router 文件时，手动编写的导入语句将函数名映射到了错误的源模块。

| 函数/变量 | 错误写入 | 正确模块 |
|-----------|---------|---------|
| `load_ordered_sources` | `services.indexer` | `services.sync_settings` |
| `SYNC_PRESETS` | `services.sync_engine` | `services.sync_settings` |
| `enrich_settings_response` | `services.settings` | `services.sync_settings` |
| `resolve_ingest_sources` | `services.ingest` | `services.source_pairing` |
| `SCHEDULER` | `services.scheduler` | `app/state.py`（新建单例） |

**修复**：
- 新建 `app/state.py` 存放 `SCHEDULER` 全局单例，供 `main.py` 和 `knowledge.py` 共享
- `admin.py`/`user.py`/`content.py`：`load_ordered_sources` 改从 `sync_settings` 导入
- `knowledge.py`：`SYNC_PRESETS`/`enrich_settings_response` 改从 `sync_settings`，`SCHEDULER` 改从 `state`
- `content.py`：`resolve_ingest_sources` 改从 `source_pairing`，反斜杠转义修正

**教训**：提取代码块到新文件时，不要凭记忆写 import，应 grep 确认每个函数在源项目中的实际定义模块。

### 58. Docker 环境更严格加载路由模块

**症状**：本地 `uvicorn` 开发一切正常，但 `docker compose up` 报 ImportError。

**根因**：`uvicorn` 在 reload 模式下（`--reload`）惰性加载路由——只有当 HTTP 请求匹配到路由时才 import 对应模块。Docker 生产模式（无 `--reload`）启动时即全量加载所有路由，立即暴露 import 错误。

**教训**：本地测试通过 ≠ Docker 能跑。任何涉及模块拆分的重构，应在提交前至少执行一次 `docker compose run --rm api python -c "from app.main import app"`。

### 59. auth.py 遗漏 parse_api_keys 导入

**症状**：管理端所有页面空白，`/api/auth-mode` 返回 500。浏览器抓包显示 `Internal Server Error`。

**根因**：`routers/auth.py` 的 `auth_mode()` 函数中使用了 `parse_api_keys()` 检查是否有 API Key，但该函数未在文件顶部 import。Python 在运行时找不到名称 → `NameError` → 500。

```python
# auth_mode() 内：
"api_key_enabled": bool(parse_api_keys() or ...)  # NameError!
```

但 `parse_api_keys` 在从 `..services.auth` 导入的列表中遗漏了。

**修复**：在 `routers/auth.py` 顶部 import 中添加 `parse_api_keys`。

**教训**：提取 router 文件后，逐个检查被提取函数中使用的每个函数名是否都在 imports 中。

### 60. git merge 导致 main.py router 注册丢失

**症状**：管理员登录后系统概览显示 `-`，用户管理页显示"暂无用户"。`/openapi.json` 仅 11 条路由（只含 auth + audit），admin/user/knowledge/content 路由全部丢失。

**根因**：git merge 冲突时 `main.py` 的 router 注册代码被回退。合并结果中只剩 `from .routers.auth import router as auth_router` 和 `app.include_router(auth_router)`，其余 4 个 router 的 import + include 语句全部消失。

**教训**：git merge 完成后不能只确认"没有 conflict marker"，还要验证功能完整性。关键文件（如 main.py 的路由注册）应在 merge 后立即做 smoke test。

### 61. __pycache__ 脏字节码导致容器使用旧代码

**症状**：修改了 router 文件中的 import 路径，`docker compose restart` 后仍报相同的 ImportError，日志中显示的行号对应旧代码。

**根因**：Docker 的 volume mount `./apps/api/app:/app/app` 将宿主机目录映射到容器。宿主机目录中的 `__pycache__/*.pyc` 文件由容器内 Python 生成（所有者 root），包含旧代码的编译结果。即使 Python 源码已更新，`uvicorn` 优先加载 `.pyc` 文件。

**修复**：`docker compose exec -u root api rm -rf /app/app/__pycache__ /app/app/routers/__pycache__`

**教训**：volume mount 会保留容器生成的 pyc 缓存。源码修改后不生效时，先清理 pycache。

### 62. 页面切换瞬闪——从 Vue Router 到 keep-alive 的排障全链路

**症状**：所有页面切换时出现瞬闪——先显示"初始化页面"（空数据、骨架），再加载显示有数据页面。`<transition>`、`eager import` 均无效。

**第一次尝试：`<transition mode="out-in">` 交叉淡入淡出**

思路：移除 App.vue 中的 `<component :is="Component" :key="$route.fullPath" />`，改用 `<transition name="page-fade" mode="out-in">` 包裹 `<router-view />`。

结果：**恶化**。`mode="out-in"` 先执行旧组件淡出 → 空白间隙 → 新组件淡入。空白间隙反而被动画拉长，瞬闪更明显。

**第二次尝试：移除 transition，eager import**

思路：将 router 中所有 `() => import(...)` 异步懒加载改为顶层 `import`，消除异步 JS chunk 加载延迟。同时改用同步淡入淡出（移除 `mode="out-in"`，用 `position: absolute` 叠加新旧组件）。

结果：仍无效。因为即使组件 JS 已就绪，Vue Router 仍然会销毁旧组件 → 创建新组件。新组件 `onMounted` 中才发起 API 请求，在数据返回前组件渲染的是空态（如 `ref([])`、null），这才是用户看到的"初始化骨架"。

**第三次尝试（最终方案）：`<keep-alive>` + `onActivated`**

根因分析：瞬闪本质是 Vue Router 的「销毁 → 重建 → 加载数据」三阶段。无论 CSS 动画多快，都无法消除"新组件空态渲染"的几帧。

解决：
```
1. App.vue: <router-view v-slot="{ Component }">
             <keep-alive>
               <component :is="Component" />
             </keep-alive>
           </router-view>
           
2. 5 个需要刷新数据的组件加 onActivated() 钩子：
   - Account.vue       → loadUserInfo() + loadSessions()
   - AdminDashboard.vue → loadStats()
   - SyncControl.vue    → loadStatus()
   - SyncAudit.vue      → refresh()
   - UsersAdmin.vue     → loadUsers()
```

原理：
- `<keep-alive>` 缓存已访问组件的 DOM + 数据，切回时直接唤醒，零销毁重建开销。
- `onActivated` 在组件从缓存中激活时触发，自动刷新数据，确保不会显示过期内容。
- 首次访问仍有一次空态（不可避免），后续访问都是**显示缓存内容 → 后台刷新 → 无缝更新**。

**教训**：Vue Router 页面切换瞬闪的根因通常不是"JS 加载慢"或"CSS 动画不够快"，而是组件销毁重建导致的数据空态。`<keep-alive>` + `onActivated` 是治本的组合拳。


---
