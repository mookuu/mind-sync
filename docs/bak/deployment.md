# 部署与迁移指南

文档索引：[docs/README.md](./README.md)

## 目录约定

| 路径 | 说明 |
|------|------|
| `${DATA_ROOT:-./data}` | SQLite、`wiki/`、`user_sources.yaml`、`purpose.md`（持久化） |
| `./sources.yaml` | 共享索引来源配置（默认库） |
| `./sources/<id>` | local / github clone 目录 |
| `./sources/obsidian` | Obsidian Web Clipper 导出 |
| `./sources/web_snapshots/<id>` | Web 源抓取快照（API 写入，需可写） |

详见 [SOURCES.md](./reference/sources.md)。

## Docker（推荐）

```bash
cp .env.example .env
# 修改 AUTH_PASSWORD、SECRET_KEY、API_KEY
cp sources.example.yaml sources.yaml

mkdir -p sources/obsidian sources/web_snapshots/example_web sources/example_github

docker compose up -d --build
```

- Web: http://localhost:8080
- API: http://localhost:8000/docs
- 健康检查: `GET /api/health`（含 `source_warnings`、`web_fetch` 策略）

## 环境变量要点

### 认证

| 变量 | 说明 |
|------|------|
| `AUTH_PASSWORD` | 单用户 admin 密码（用户名为 `default`） |
| `AUTH_USERS` | 多用户 RBAC，如 `admin:pass:admin,reader:pass:viewer` |
| `API_KEY` | CLI/MCP，视为 admin |
| `SECRET_KEY` | 会话签名 |

### 数据与源

| 变量 | 说明 |
|------|------|
| `DATA_DIR` | 默认 `/data` |
| `SOURCES_FILE` | 默认 `/workspace/sources.yaml` |
| `SOURCE_*` | Docker 卷：本地目录 → 容器内 `/sources/...` |
| `GITHUB_TOKEN` | 私有 GitHub 源 |
| `VAULT_GIT_URL` | 跨设备 wiki + purpose Git 同步 |

### Web 源合规

| 变量 | 默认 |
|------|------|
| `WEB_FETCH_RESPECT_ROBOTS` | `true` |
| `WEB_FETCH_USER_AGENT` | `mind-sync/0.1` |
| `WEB_FETCH_CONTACT` | 建议填联系邮箱 |
| `WEB_FETCH_ALLOWLIST` | 生产建议限定域名 |
| `WEB_FETCH_REQUIRE_OPT_IN` | 建议 `true`，并在 yaml 设 `fetch_confirmed: true` |
| `WEB_FETCH_MAX_BYTES` | 单次抓取响应上限（默认 5MB） |

完整列表见 [.env.example](../.env.example)。

## 从 Windows 绝对路径迁移

旧版 `sources.yaml` 可能硬编码 `C:/Workspace/...`。新版：

1. 在 `.env` 设置 `SOURCE_*` 指向原目录，或  
2. `mklink /J` 链接到 `./sources/<id>`

## 备份与恢复

```bash
tar -czf mind-sync-data-backup.tgz data/
# 可选：sources.yaml、.env（勿提交 git）
```

恢复：解压到 `data/` 并重启 API。

## HTTPS / 公网

```env
COOKIE_SECURE=true
SECURITY_HSTS_ENABLED=true
CORS_ALLOW_ORIGINS=https://your-domain.example
```

- 使用反向代理终止 TLS（Caddy / Nginx），示例见 [workflow.md](./workflow.md)
- 多用户场景配置 `AUTH_USERS`，只读用户用 `viewer` 角色
- 限制 API 端口暴露；`API_KEY` 仅给可信自动化

## 部署后自检

```bash
python scripts/smoke_auth.py --base-url http://localhost:8000 --password "<AUTH_PASSWORD>"
curl -s http://localhost:8000/api/health | python -m json.tool
```

API 启动时若仍用默认 `AUTH_PASSWORD` / `API_KEY`，日志会输出 `SECURITY:` 警告。

## 升级注意

- 修改 `sources.yaml` 后：Web 设置 **重新加载**，或重启 API（见 [SOURCES.md](./reference/sources.md)）
- 远程源连续同步失败会进入指数退避（`SYNC_BACKOFF_*`），可在 `/api/sync-status` 查看
- 新增 Python 依赖后 `docker compose up --build`
- RBAC / Web 合规相关 env 变更后需重启
