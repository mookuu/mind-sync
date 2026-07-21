# 第十五组：用户软删除

### 71. 软删除时移除用户源配置导致库数归零、共享源消失

**症状**：注销用户后，该用户在用户管理页面的库数和文档数显示为 0，其他用户也看不到该用户的共享目录，素材管理页面中该用户的源消失。

**根因**：`admin_delete_user`（`admin.py`）在设置 `deleted_at` 后调用了 `remove_user_source_from_yaml()` + `reload_sources_config()`，将已注销用户的源从 `user_sources.yaml` 中物理移除。

软删除的语义是「禁止登录，保留数据和共享关系」，但代码错误地执行了物理清理。

**修复**：
1. `admin_delete_user` 移除 `remove_user_source_from_yaml()` 和 `reload_sources_config()` 调用，仅设置 `deleted_at` + 清除 sessions
2. `admin_list_users` 的 `source_count` 改为从 `user_sources.yaml` 计数（不再依赖已移除的数据）
3. `load_sources_for_user` 中已注销超 30 天用户的共享源做过滤

**教训**：软删除 = 禁止访问，不应销毁业务数据。源配置、共享关系、索引文档都应保留，直到宽限期结束后物理删除。

---

### 72. 恢复用户时未重建默认库源条目

**症状**：恢复已注销用户后，该用户库数仍为 0，无法同步。

**根因**：`admin_restore_user`（`admin.py`）只清除了 `deleted_at`，没有检查用户的默认库源是否仍然存在于 `user_sources.yaml` 中。之前软删除时若错误调用了 `remove_user_source_from_yaml`，恢复后源条目仍然缺失。

**修复**：`admin_restore_user` 在恢复后检查 `user_sources.yaml` 中是否有该用户的源条目，若无则调用 `ensure_user_dir` + `build_user_source_entry` + `append_user_source_to_yaml` 重建默认库。

**教训**：注销-恢复是成对操作，恢复时必须确保被注销期间可能丢失的配置得到重建。防御式检查比假设「一切未变」更可靠。

---

### 73. 已注销用户共享源 30 天窗口可见性

**症状**：用户注销后，其共享的库应立即对其他用户不可见还是保留一段宽限期？需求文档明确：30 天内共享继续有效，超期后物理删除。

**根因**：原 `load_sources_for_user` 对所有 `shared=True` 且 `owner≠None` 的源无条件放行，未考虑已注销用户的状态。

**修复**（`indexer.py` `load_sources_for_user`）：
```python
cutoff = time.time() - 30 * 86400
expired_owners = {r["username"] for r in conn.execute(
    "SELECT username FROM users WHERE deleted_at > 0 AND deleted_at < ?", (cutoff,)
).fetchall()}
# 过滤超 30 天已注销用户的共享源
return [s for s in all_sources if ... or (s.shared and s.owner not in expired_owners)]
```

**教训**：宽限期策略要落实到数据访问层而非仅 UI 层。共享源可见性规则必须与用户状态联动。

---

### 74. 用户列表库数/文档数统计口径反复

**症状**：新用户库数显示 0（应至少 1 个默认库），已注销用户库数显示 0。

**根因**：`admin_list_users` 的统计来源经历了三次反复：
1. 最初从 `user_sources.yaml` 计数 ✅
2. 改为从 `documents` 表聚合 `COUNT(DISTINCT source_id)` —— 新用户未同步时文档表为空 → 0 ❌
3. 改回 `user_sources.yaml` 计数 ✅，文档数保留从 `documents` 表查询

**修复**：最终采用双源策略：
- `source_count`：从 `user_sources.yaml` 计数（反映实际配置的库数）
- `doc_count`：从 `documents` 表 `COUNT(1)` 按 `source_owner` 聚合

**教训**：库数和文档数是两个不同概念——库数 = 配置了几条源，文档数 = 索引了多少文件。新用户未同步时文档数为 0 是正常的，但库数不应为 0。统计口径要对齐概念定义。

---

### 75. 素材管理页下拉筛选框互斥

**症状**：素材管理页（`SyncSourcesAdmin.vue`）的四个筛选下拉框（用户/类型/状态/共享）可以同时打开多个，UI 混乱。

**根因**：每个下拉框使用独立的 `ref(false)` toggle，互不知晓对方状态。

**修复**：将四个 boolean ref 合并为一个 `openDropdown` 字符串 ref，值可为 `"owner"` / `"type"` / `"status"` / `"share"` / `""`：
```javascript
const openDropdown = ref("");
function toggleDropdown(name) {
  openDropdown.value = openDropdown.value === name ? "" : name;
}
```
`onClickOutside` 简化为 `if (openDropdown.value) openDropdown.value = ""`。

**注意**：Python 批量编辑时引号转义出错，`openDropdown = ""` 被写成三引号 `"""`，后续修复又截断了 HTML 属性闭合引号。最终格式：`@click="openDropdown = ''"`（Vue 模板属性双引号内用单引号）。

**教训**：互斥 UI 组件应用单一状态源管理，避免多 bool 同步问题。批量文本替换后必须逐行检查引号完整性。

---
