# 第七组：索引重建与数据同步

## 第七组：索引重建与数据同步

### 35. 全量重建后文档 ID 变化导致缓存 404

**症状**：全量重建（rebuild）后，点击之前的搜索结果或树中的文档，返回 404 Not Found。重新搜索后跳转正常。

**根因**：`run_rebuild_job` 流程是 `clear_source_index` → `index_single_source_force`。前者 DELETE 文档行，后者 INSERT 新行（`ON CONFLICT(source_id, rel_path) DO UPDATE`，但旧行已删除 → 无冲突 → 新行获得新的自增 ID）。

```python
# clear_source_index:
DELETE FROM documents WHERE source_id = ?  # 旧 doc_id=1029 被删除

# index_single_source_force:
INSERT INTO documents(...) VALUES(...)   # 新行获得 doc_id=2050
```

前端搜索结果缓存在 localStorage 中，树缓存在 Vue 响应式变量中，都持有旧的 doc_id → 404。

**修复**：
1. 侧边栏树：移除 `if (catTrees[catKey]) return` 缓存保护，每次展开都重新加载
2. 搜索结果：缓存加 `ts` 时间戳，超过 10 分钟过期
3. 同步/重建触发时：主动 `localStorage.removeItem('mind_sync_last_search')`
4. 兜底：`Library.vue` 的 `openDoc` 检测到 404 时也清除缓存

**教训**：自增 ID 不可靠——任何可能导致行被删除后重建的操作都会改变 ID。对外暴露的引用（URL、缓存）应使用稳定标识符（如 `source_id + rel_path`）。

---

### 36. include 模式默认过窄导致文件未被索引

**症状**：添加全局库后，库内的 Java/JSON/JS 等文件无法被搜索到，文档树中也无该库。

**根因**：`admin_add_custom_source` 和 `user_add_source` 的 `include` 默认值分别是 `["**/*.md", "**/*.py"]` 和 `["**/*.md"]`（通过 `item.get("include", ["**/*.md"])`）。`collect_files` 只用这些 glob 模式匹配文件，其他后缀的文件全部跳过。

**修复**：将默认 include 扩展到 18 种常见文本文件类型：

```python
"include": [
    "**/*.md", "**/*.py", "**/*.java", "**/*.txt",
    "**/*.json", "**/*.yaml", "**/*.yml", "**/*.xml",
    "**/*.html", "**/*.css", "**/*.js", "**/*.ts",
    "**/*.sh", "**/*.bash", "**/*.sql",
    "**/*.cfg", "**/*.ini", "**/*.toml",
],
```

**教训**：默认值应该覆盖最常见的场景，宁可多索引不可漏索引。用户手动排除比手动追加容易。

---

### 37. 删除源后未清理索引文档

**症状**：从同步素材删除库后，文档库子菜单仍能看到该库的文档。

**根因**：`admin_delete_source` 和 `user_delete_source` 只从 YAML 配置中移除条目并 `reload_sources_config()`，但没有清理 SQLite 中已索引的文档行。

**修复**：在删除端点中，YAML 删除后调用 `clear_source_index(conn, source_id)` 删除 `documents` 和 `documents_fts` 表中的相关行。

```python
# admin_delete_source:
cleanup_id = parsed_id or source_id
conn = get_db()
clear_source_index(conn, cleanup_id)
conn.commit()
```

**教训**：资源删除要考虑级联：配置删了 → 索引也要删。任何一对多的数据关系，删除"一"时必须处理"多"。

---

### 38. load_ordered_sources 缺少用户参数

**症状**：非管理员用户添加私有库后，文档库「原始素材」中看不到该库。管理员能看到。

**根因**：`build_library_index` 中补充空源时调用 `load_ordered_sources()` 未传 `username`/`role` → 默认 `username=None, role=None` → `load_sources_for_user` 只返回 `owner=None` 的共享源，过滤掉了所有私有源。

```python
# 错误：未传用户上下文
all_srcs = load_ordered_sources()  # → username=None → 只返回 ownerless 源

# 正确：传入当前请求的用户
all_srcs = load_ordered_sources(username=username, role=role)
```

**修复**：
1. library 端点增加 `request: Request` 参数，`resolve_current_user` 获取用户
2. `build_library_index` 签名增加 `username, role` 参数并传递给 `load_ordered_sources`

**教训**：任何需要区分用户可见数据的 API 端点，都必须把用户上下文传递到底层数据查询函数。默认参数只适用于无需用户区分的场景。

---

### 39. 同步完成后前端「上次同步」显示「尚未执行」

**症状**：增量同步或全量重建完成后，「同步控制」页面的「上次同步」始终显示「尚未执行」，无法看到同步完成时间。同步本身正常（文档已入库）。

**根因**（两层）：

1. **关键层——Pydantic 响应模型丢弃字段**：`SyncStatusResponse`（`responses.py`）缺少 `last_completed`、`source_backoff`、`warnings` 三个字段定义。FastAPI 的 `response_model` 会对返回 dict 做 Pydantic 校验/序列化，未声明的字段被**静默丢弃**。`get_sync_status_payload()` 虽然返回了 `last_completed`，但到达前端时已不存在。

```python
# 修复前：SyncStatusResponse 缺少 last_completed
class SyncStatusResponse(BaseModel):
    running: bool
    ...
    error: str | None = None
    # ← last_completed 未声明 → 被 FastAPI 丢弃

# 修复后：补齐缺失字段
class SyncStatusResponse(BaseModel):
    ...
    last_completed: dict[str, Any] | None = None
    source_backoff: list[dict[str, Any]] | None = None
    warnings: list[str] | None = None
```

2. **辅助层——状态更新竞态**：`run_sync_job` / `run_rebuild_job` 中 `SYNC_STATE["running"] = False` 在 `finalize_sync_run`（更新 `LAST_SYNC_SUMMARY`）之前执行。即使模型字段完整，轮询若在这两个操作之间的窗口命中，仍会拿到 `running=false` + 过期 `last_completed`。

```python
# 修复前（sync_engine.py）：
finally:
    with SYNC_LOCK:
        SYNC_STATE["running"] = False  # ① 先标记完成
    ...
result = {...}
finalize_sync_run(...)                 # ② 后更新 last_completed → 窗口期数据不一致

# 修复后：先持久化摘要，再标记完成
result = {...}
finalize_sync_run(...)                 # ① 先更新 LAST_SYNC_SUMMARY
with SYNC_LOCK:
    SYNC_STATE["running"] = False      # ② 后标记完成
```

`rebuild_engine.py` 同样修复，且补上了 `finalize_sync_run` 缺失的 `username` 参数（原代码 `finalize_sync_run(trigger, started_at, result)` 未传 username，导致 `LAST_SYNC_SUMMARY` 的内存键与 DB 键不一致）。

**教训**：
- FastAPI 的 `response_model` 是一把双刃剑——它能自动过滤、校验，但也会**静默丢弃**未声明的字段。API 返回 dict 新增字段时，必须同步更新 Pydantic 模型。
- 共享状态的写入顺序决定读取端看到的快照是否一致。`running=False` 是"任务结束"的信号，必须在所有收尾数据（`last_completed`）写入完成之后再发出。
