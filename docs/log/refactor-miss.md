# 第十一组：重构遗漏与过度工程

## 第十一组：重构遗漏与过度工程

### 54. 权限开放后 sync/rebuild 端点忘记改 require_any_auth

**症状**：权限分离重构将同步控制页对所有角色开放后，非管理员点击"增量同步"按钮无响应。控制台无报错，按钮可点击但不触发任何操作。

**根因**：权限分离重构时做了大量改动（per-user settings、路由守卫、菜单权限），但遗漏了 sync/rebuild 端点的 auth 依赖。端点仍使用 `Depends(require_admin)`，非管理员调用 → 403。前端 `SyncControl.vue` 中 `startSync()` 有 `if (!canWrite.value) return` 保护 → 403 被静默吃掉。

```python
# 遗漏点
@app.post("/api/sync")
def sync(..., _: Any = Depends(require_admin)):  # ← 没改
```

**修复**：`require_admin` → `require_any_auth`，同时移除前端 `canWrite` 限制。

**教训**：大规模重构时，权限变更的波及面要逐端点排查。路由守卫（前端）+ 菜单权限（前端）+ API 鉴权（后端）三层都要覆盖，遗漏任何一层都会导致功能断裂。

---

### 55. 树缓存过度失效导致子菜单切换延迟

**症状**：文档库子菜单切换时（原始素材⇄学习摘要⇄问答沉淀）每次出现"加载中"闪烁，有明显的加载延迟。

**根因**：之前为修复"删除库后树未更新"问题，采用了过度激进的缓存失效策略：

1. 移除了 `if (catTrees[catKey]) return` 缓存保护 → 每次展开都调 API
2. 添加了 etag 指纹比对跳过 DOM 重建 → API 调用仍在，"加载中"仍在
3. 添加了路由 watcher 回到 library 时清缓存重载 → 额外的 API 调用

而实际上，树数据只在 sync/rebuild 后才会变化。其他操作（增删源、页面切换）都不改变已索引的文档。

**修复（渐进式简化）**：

1. 恢复 `if (catTrees[catKey]) return` 缓存保护
2. sync/rebuild 完成后 `dispatchEvent('mind-sync-tree-refresh')` → AppSidebar 监听清缓存
3. 删除 etag 比对逻辑（缓存命中后根本不需要调 API）
4. 删除路由 watcher 中的清缓存重载逻辑（源增删不影响树）

最终流程极简：
```
首次展开 → API 加载 → 缓存（1 次）
子菜单切换 → 直接复用（0 API）
sync/rebuild 完成 → event 清缓存 → 下次展开 API 加载
```

**教训**：缓存失效策略要与数据变更的实际触发点对齐。不要因为"万一数据变了"就过度失效。找到真正的变更源（sync/rebuild），只在那个点精准清缓存。事件驱动优于轮询，精准失效优于全量失效。

---
