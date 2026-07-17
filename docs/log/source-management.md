# 第十四组：素材管理重构

### 66. 全局库增加共享机制——非管理员只可见已共享源

**症状**：全局库对所有用户可见，管理员无法控制哪些全局库对角色用户开放。

**根因**：`load_sources_for_user()` 中非管理员条件 `s.owner is None` 无条件返回全部全局源；admin 共享 API 拒绝全局源（owner=None 直接 400）。

**修复**：
1. 后端 `admin_toggle_source_share`（`admin.py`）移除全局源拒绝逻辑，改为修改 `sources.yaml` 中的 `shared` 字段
2. `load_sources_for_user`（`indexer.py`）改为 `s.owner is None and s.shared`，非管理员只看到已共享的全局源
3. `list_sync_presets()`（`sync_settings.py`）暴露 `shared` 字段给前端
4. 前端 `SyncSources.vue` 全局库行增加共享按钮（🔒/🔓），调用 `POST /api/admin/sources/{id}/share`
5. `sharedPresets` computed 过滤：非管理员只显示 `p.shared === true`

```python
# indexer.py — 非管理员仅显示已共享全局源
return [s for s in all_sources
        if (s.owner is None and s.shared) or s.owner == username or (s.shared and s.owner is not None)]
```

**教训**：全局配置（如 sources.yaml）和用户配置（user_sources.yaml）都应支持 `shared` 字段。可见性规则要显式编码，不要靠"管理员手动勾选"作为间接控制手段。

---

### 67. 角色用户「我的知识库」冗余用户信息标签

**症状**：非管理员在同步素材页看到 `👤 moku 当前用户(5)` 标签，而该区域只有自己的库，标签信息冗余。

**根因**：模板中 `owner-group-label` 对非管理员自己的私有源也渲染了分组标签（含 `getOwnerRoleLabel` 返回"当前用户"）。

**修复**：移除 `owner-group-label` div 及 `role-tag` span，非管理员私有源直接平铺在列表中以节省空间。

**教训**：分组标签仅在多用户混排时有意义。单用户视图下应去除冗余的层级嵌套。

---

### 68. 全局库和共享库空内容时隐藏标签

**症状**：没有共享中的全局库时，"📚 全局知识库" 标签仍然显示，展开后无内容。

**根因**：section label 无条件渲染，未检查数据是否为空。

**修复**：全局库标签加 `v-if="sharedPresets.length > 0"`；共享库标签加 `v-if="groupedSharedPublicSources.length > 0"`。

**教训**：UI 标签/折叠区应与其内容联动——内容为空时整个区块应隐藏，而非显示空壳。

---

### 69. 素材管理页共享状态与 SyncSources 不一致

**症状**：`SyncSourcesAdmin.vue`（素材管理）对 admin 拥有的源显示 "—" 而非共享状态，且共享按钮对 admin 源不可用；全局源 `owner=null` 未被识别。

**根因**：旧逻辑假设"admin 的源不需要共享管理"，但全局源（owner=null）也需要共享控制。

**修复**：
1. 拥有者列：`owner === null` 显示"全局"标签，`owner === 'admin'` 显示"admin"
2. 共享状态列：移除 `owner === 'admin'` 特判，所有源统一显示 🔓/🔒
3. 共享按钮：移除 `v-if="s.owner !== 'admin'"`，所有源均可操作

**教训**：前后端共享状态逻辑应对齐。一处 `v-if` 特判可能导致另一处状态不可管理。

---

### 70. 同步范围改为 radio button 模式

**症状**：原来"全部同步"是一个 checkbox toggle，逻辑复杂：切换全部→自定义需恢复备份 ID，且默认状态不明确。

**根因**：单 checkbox 承载两种模式切换，状态管理依赖 `backupIds` + `localStorage`，容易出错。

**修复**：
1. 将单 checkbox 替换为两个 `<input type="radio">`：**全部同步** / **自定义**
2. 两个 radio 互斥，默认均不选中
3. `onToggleAll()` → 切换到全部同步（`setPreset("all")`），备份当前勾选
4. `onToggleCustom()` → 切换到自定义，从备份恢复
5. 选"全部同步"时库列表 `v-show="!isAll"` 隐藏
6. CSS：`.sync-range-radios` flex 布局，两 radio 等宽居中

**教训**：互斥选项用 radio button，语义强于 checkbox toggle。默认不选中 avoids 隐性预设，迫使用户主动选择。

---
