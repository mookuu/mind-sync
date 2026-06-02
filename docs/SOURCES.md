# sources.yaml 配置说明

索引来源由仓库根目录 `sources.yaml`（或环境变量 `SOURCES_FILE`）定义。修改文件后：

- **推荐**：管理员在 Web 设置 → 源列表点击 **重新加载**（`POST /api/admin/sources/reload`），或调用该 API，无需重启容器。
- API 进程另有 30 秒 LRU 缓存；reload 接口会立即清缓存。

Web 设置页为只读展示（不可在此编辑 YAML 内容）。

完整示例：[sources.example.yaml](../sources.example.yaml)。

## 通用字段

| 字段 | 必填 | 说明 |
|------|------|------|
| `id` | 是 | 唯一标识，索引与搜索中的 `source_id` |
| `type` | 是 | `local` · `github` · `web` |
| `path` | local/github/web 建议有 | 扫描或写入目录（容器内路径） |
| `include` | 否 | glob 列表，默认 `["**/*.md"]` |
| `order` | 否 | 同步处理顺序（小者优先；不影响搜索排序） |
| `url` | github/web 必填 | 仓库 URL 或网页 URL |
| `branch` | 否 | GitHub 分支，默认 `main` |

### Web 源专用

| 字段 | 说明 |
|------|------|
| `fetch_confirmed` | `true` 表示管理员确认抓取；`WEB_FETCH_REQUIRE_OPT_IN=true` 时必填 |
| `respect_robots` | 覆盖全局 `WEB_FETCH_RESPECT_ROBOTS` |

## 源类型

### local

本地目录，典型用途：

- 自研笔记仓库（`SOURCE_*` 卷映射到 `/sources/<id>`）
- **Obsidian 剪藏**：`id: obsidian`，path 指向 `/sources/obsidian`

```yaml
- id: obsidian
  type: local
  order: 10
  path: "/sources/obsidian"
  include: ["**/*.md"]
```

### github

Shallow clone / pull 到 `path`（默认 `/sources/<id>`），需可写挂载；私有仓配 `GITHUB_TOKEN`。

```yaml
- id: PythonBasic
  type: github
  order: 40
  url: "https://github.com/you/PythonBasic.git"
  branch: main
  path: "/sources/PythonBasic"
  include: ["**/*.md", "**/*.py"]
```

### web

同步时对 **单个** `url` 发 HTTP GET，转为 Markdown 写入 `path`（如 `/sources/web_snapshots/<id>/index.md`），再索引。

合规开关见 [MIND_SYNC_WORKFLOW.md](./MIND_SYNC_WORKFLOW.md#web-源抓取合规) 与 `.env` 中 `WEB_FETCH_*`。

```yaml
- id: example_web
  type: web
  order: 60
  url: "https://example.com"
  path: "/sources/web_snapshots/example_web"
  fetch_confirmed: true
  include: ["**/*.md"]
```

策略查询：`GET /api/health` → `web_fetch`；`GET /api/sources` → `web_fetch_policy`。

## 同源配对（GitHub + local）

满足以下任一条件视为**同一素材**，只索引一次：

1. 两条目 `id` 相同  
2. 两条目 `path` 相同  
3. GitHub 仓库名（URL 最后一段）与 local 的 `id` 相同  

同步行为：

1. 优先 GitHub pull  
2. 失败 → `warnings`，local 目录有文件则回退继续索引  
3. 不阻断其他源  

示例见 `sources.example.yaml` 中 `PythonBasic` 的 github + local 双条目。

**注意**：同 `id` 的 github/local 在 Web「自定义同步」与「同步顺序」中用 **`id:type`** 区分（如 `PythonBasic:local` / `PythonBasic:github`），避免勾选混淆。仅选 local 时不会触发 GitHub pull。

## wiki 源

通常保留一条指向知识库本身，便于搜索摘要与 queries：

```yaml
- id: wiki
  type: local
  order: 100
  path: "/data/wiki"
  include: ["**/*.md"]
```

## Docker 卷映射

`.env` / `docker-compose` 中常见变量：

| 变量 | 挂载到 |
|------|--------|
| `SOURCE_OBSIDIAN` | `/sources/obsidian` |
| `SOURCE_WEB_SNAPSHOTS` | web 快照父目录 |
| `SOURCE_*` | 各 local/github 源 |

`./data` → `/data`（wiki、SQLite、purpose.md）。

## 同步范围（Web 设置）

与 `sources.yaml` 正交，存于 SQLite `app_settings`：

- `sync_preset`：all / wiki / sources / custom  
- `sync_source_ids`：custom 时勾选的 id 列表  
- `sync_source_order`：覆盖默认 order  

由 `services/sync_settings.py` 解析；`POST /api/sync` 与全量重建共用该范围。

## 常见问题

**Q：改了 yaml 为什么 Web 里看不到？**  
A：在设置 → 源列表点击 **重新加载**，或 `POST /api/admin/sources/reload`（需 admin）。也可等待约 30 秒缓存过期或重启 API。

**Q：Web 源同步报 blocked / robots？**  
A：检查 `WEB_FETCH_*` 与 `fetch_confirmed`；查看 sync warnings 与 `/api/health`.

**Q：ingest 与 sync 区别？**  
A：ingest 只重扫磁盘索引，不 pull GitHub、不抓 Web、不 pull Vault；**同样跳过 paired local**。见 [ARCHITECTURE.md](./ARCHITECTURE.md)。

**Q：能否 API 编辑 index.md？**  
A：不能；`index.md`、`log.md`、`SCHEMA.md` 为系统页。
