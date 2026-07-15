# 第二组：路径与数据一致性

## 第二组：路径与数据一致性

### 7. 路径不一致：写入与读取用不同路径

**症状**：个人源在同步素材页面不可见。`user_manager.py` 写入 `/data/config/user_sources.yaml`，而 `indexer.py` 从 `/data/user_sources.yaml` 读取，两个完全不同的文件。

```python
# user_manager.py（写入方）
_USER_SOURCES_FILE = Path(settings.data_dir) / "config" / "user_sources.yaml"

# indexer.py（读取方）
user_src_file = Path(settings.data_dir) / "user_sources.yaml"    # 少了 config/
```

**教训**：同一份数据的读写路径必须共享同一个常量或配置值，不要在两处各自拼写。

**修复**：`indexer.py` 改为 `/data/config/user_sources.yaml`，与 `user_manager.py` 一致。

---

### 8. 路径缺少 segment

**症状**：个人源路径显示为 `~/data/moku/default`，正确应为 `~/data/mind-sync-data/users/moku/default`。

```python
# 错误：有 DATA_ROOT 时直接取值，丢了 "users" 段
_USER_ROOT = Path(settings.data_root) if settings.data_root else Path(settings.data_dir) / "users"

# 正确：无论是否有 DATA_ROOT，都应追加 /users
_USER_ROOT = Path(settings.data_root) / "users" if settings.data_root else Path(settings.data_dir) / "users"
```

**教训**：条件表达式的两条分支必须语义等价。fallback 路径有 `/users`，主路径也必须有。

---

### 9. 源计数口径错误

**症状**：管理员的「源数量」统计了所有 yaml 中的源（包括其他用户的私有源），显示 8 条；后改为只统计 `sources.yaml` 中的源（3 条），用户反馈漏了 "web 快照"。

```python
# 第一次修复：用 load_sources() 统计，漏了预设中的条目
source_count = sum(1 for s in all_sources if s.owner is None or s.owner == username)

# 第二次修复：用 list_sync_presets() 统计，但包含了 "all" 和 "custom"
admin_source_count = sum(1 for p in all_presets if p.get("owner") is None)

# 最终：排除系统预设
admin_source_count = sum(1 for p in all_presets
                       if p.get("owner") is None and p.get("id") not in ("all", "custom"))
```

**教训**：统计口径必须与页面展示的条目数一致。管理员看到的源是 `list_sync_presets()` 中 `owner=None` 且排除 `all`/`custom` 的条目，代码应直接复用同一口径。

---

### 10. 前端 enrichment 覆盖了后端已提供的数据

**症状**：`example_web` 路径有效性在前端同步素材页始终检测不到，同步控制页却能正确显示。

```javascript
// 错误：enrich 无条件覆盖，导致后端返回的 path_exists 被 undefined 覆盖
return filtered.map(p => ({
  ...p,
  path_exists: srcMap[p.id] ? srcMap[p.id].path_exists : undefined,
}));

// 正确：保留后端已有值，仅在后端未提供时才补充
return filtered.map(p => ({
  ...p,
  path_exists: p.path_exists !== undefined
    ? p.path_exists
    : (srcMap[p.id] ? srcMap[p.id].path_exists : undefined),
}));
```

**教训**：前端 enrichment 应遵循「后端优先」原则——后端已返回的字段不应被前端覆盖。spread 顺序很重要：`{ ...enrichment, ...backend }` vs `{ ...backend, ...enrichment }`。

---

### 11. 后端 API 未返回前端需要的字段

**症状**：`sharedPresets`（来自 `/api/settings` 的 `syncPresets`）不含 `path_exists`，而前端需要它来渲染路径有效性。

**教训**：如果前端某个 computed 需要从多个 API 拼凑数据才能得到正确结果，说明后端 API 的响应模型应该直接包含该字段。先在后端加字段，比在前端做脆弱的数据合并更可靠。

**修复**：在 `list_sync_presets()` 中为每个预设条目增加 `path_exists` 字段。

```python
items.append({
    "id": sk,
    "path": spath,
    "path_exists": Path(spath).exists() if spath and not spath.startswith(('http://', 'https://')) else None,
})
```

---
