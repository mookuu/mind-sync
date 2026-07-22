# 第十六组：Web 快照与 UI 微调

### 76. Web 源多 URL 共享目录——URL hash 命名

**症状**：每个 web 源的输出文件固定为 `index.md`，多个 web 源指向同一目录时文件互相覆盖。

**根因**：`_sync_web_source_fetch`（`source_sync.py`）用固定文件名 `index.md` 和 `meta.json` 存储快照，不支持多 URL 共享同一目录。

**修复**：导入 `hashlib`，对 URL 做 sha256 取前 12 位作为文件名前缀：
```python
url_hash = hashlib.sha256(url.encode()).hexdigest()[:12]
index_path = out_dir / f"{url_hash}.md"
meta_path = out_dir / f"{url_hash}.json"
```
`meta.json` 同样改为 hash 命名，条件请求（304）逻辑不受影响。

**教训**：单一固定文件名的设计在扩展为多 URL 场景时必须改为基于内容特征的命名。URL hash 是自然的选择——同一 URL 永远映射到同一文件，不会冲突。

---

### 77. Web 快照管理 API

**症状**：添加 web 快照需要手动编辑 `sources.yaml`，对非技术用户不友好。

**修复**：在 `admin.py` 中新增三个端点：
- `GET /api/admin/web-snapshots` — 列出所有 type:web 源
- `POST /api/admin/web-snapshots` — 添加（id, url, path 默认 web_snapshots）
- `DELETE /api/admin/web-snapshots/{id}` — 删除

添加时自动写入 `sources.yaml`，设置默认值 `fetch_confirmed: true`、`order: 80`。

**教训**：YAML 手工配置的操作应提供 UI 封装。CRUD 型 API 是对配置文件的薄封装，不引入新的持久化层。

---

### 78. Web 快照管理前端页面

**修复**：新建 `WebSnapshots.vue`（路由 `/admin/web-snapshots`，adminOnly），包含：
- 表格：ID、URL、存储路径、删除按钮
- 添加弹窗：ID + URL + 路径（可选）
- 路径默认 `~/data/mind-sync-data/web_snapshots`

侧边栏"系统管理"菜单新增 `Web 快照` 入口（AppSidebar.vue）。

**教训**：新功能的管理页面应与现有管理页面风格一致（表格+弹窗），路径显示用 `displayPath()` 转 `~` 格式。

---

### 79. 侧边栏源码节点简化

**症状**：侧边栏树中每个库节点显示库名 + 文档计数 `(N)` + sourceId 标签，信息冗余。

**修复**：`TreeBranch.vue` 删除 `branch-count` 和 `branch-source-id` span 及对应 CSS，节点仅显示库名。

**教训**：侧边栏空间有限，精简到核心信息（库名）即可，文档数等统计数据不应挤占导航区域。

---

### 80. NotifyBar 重复 toast 清理

**症状**：管理员操作成员库共享后，成员页面同时出现顶部通知条和左下角 toast 弹窗。

**根因**：`NotifyBar.vue` 的 `loadNotices()` 中对高亮通知额外调用了 `toast.warning()`，加上 `api/index.js` 之前已删除的通用 500 toast，仍然存在一层重复。

**修复**：删除 `loadNotices()` 中 `toast.warning()` 调用和 `toast` import，新通知仅通过顶部通知条展示。

**教训**：同一事件不应在多个 UI 通道同时呈现。通知条（NotifyBar）覆盖持续性消息，toast 覆盖即时操作反馈，各司其职。

---

### 81. 素材管理页添加时间修复

**症状**：素材管理页所有库的添加时间均显示 "—"。

**根因**：`admin_sources_status` 从 `documents` 表的 `MIN(updated_at)` 取值，新库若无文档则值为 0。

**修复**：
- 默认三库（obsidian/wiki/web_snapshots）使用管理员用户的 `created_at`
- 其他库使用 `MIN(updated_at)`（即索引中最早文档时间，近似于库的首次同步时间）

**教训**：时间字段的语义需区分——"创建时间"对默认库应是系统/用户创建时间，对动态添加的库应是首次索引时间。二者数据来源不同。

---
