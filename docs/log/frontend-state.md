# 第三组：前端状态与数据流

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

### 18. onActivated 静默刷新时无条件重置分页

**症状**：素材管理页面切换到第 2 页 → 切到其他 tab → 切回来，分页回到第 1 页。用户管理/Web 快照等页面不存在此问题（无分页或无需 onActivated 刷新）。

**根因**：`SyncSourcesAdmin.loadSources()` 中 `page.value = 1` 无条件执行。`onActivated` 时通过 keep-alive 切回组件，虽 DOM 仍在，但 `loadSources()` 第一行就 `loading.value = true`（模板 `v-if="loading"` 导致表格瞬闪），随后 `page.value = 1` 丢弃了用户之前选择的分页位置。

```javascript
// 修复前
async function loadSources() {
  loading.value = true;        // 瞬闪根因
  try {
    const data = await api("/api/admin/sources-status");
    sources.value = data.sources || [];
    page.value = 1;             // ← 切回 tab 时无条件重置
  } ...
}

onActivated(() => { loadSources(); });   // keep-alive 切回时触发
```

**修复**：`loadSources(silent)` — `onMounted` 及手动「刷新」调 `loadSources()` 正常设 loading + 重置分页；`onActivated` 调 `loadSources(true)` 跳过 `loading` 和 `page` 重置，已有表格原地保留，数据静默刷新。

```javascript
// 修复后
async function loadSources(silent = false) {
  if (!silent) loading.value = true;
  try { ...
    sources.value = data.sources || [];
    if (!silent) page.value = 1;    // 仅首次/手动刷新时重置
  } ...
}

onActivated(() => { loadSources(true); });
```

**教训**：keep-alive 组件的 `onActivated` 刷新策略应区分「首次挂载」和「切回刷新」——前者需要 loading 态 + 状态重置，后者应在保留现有 UI 的前提下静默更新数据。`loading` 和分页位置都属于 UI 状态，不应在背景刷新时被重置。
