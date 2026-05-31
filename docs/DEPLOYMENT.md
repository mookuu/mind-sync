# 部署与迁移指南

## 目录约定

| 路径 | 说明 |
|------|------|
| `./data` | SQLite、wiki、purpose.md（持久化） |
| `./sources.yaml` | 索引来源配置 |
| `./sources/<id>` | 可选：本地笔记挂载点（Docker 默认，已在 `.gitignore` 中忽略） |

## Docker（推荐）

```bash
cp .env.example .env
# 修改 AUTH_PASSWORD、SECRET_KEY、API_KEY
cp sources.example.yaml sources.yaml

# 可选：在 .env 指定本机笔记路径
# SOURCE_KNOWLEDGE_ENGINEERING=...

docker compose up -d --build
```

- Web: http://localhost:8080（容器 healthcheck 探测 `/`）
- API: http://localhost:8000/docs（healthcheck 探测 `/api/health`，含来源目录状态）

## 从 Windows 绝对路径迁移

旧版 `sources.yaml` 使用 `C:/Workspace/...` 硬编码路径。新版改为：

1. 在 `.env` 设置 `SOURCE_*` 环境变量指向原目录，或
2. 用 `mklink /J` 将原目录链接到 `./sources/<id>`

## 备份

```bash
# 数据卷（含 wiki、索引库）
tar -czf mind-sync-data-backup.tgz data/
```

恢复时解压到项目 `data/` 并重启 API。

## HTTPS / 公网

`.env` 建议：

```env
COOKIE_SECURE=true
SECURITY_HSTS_ENABLED=true
CORS_ALLOW_ORIGINS=https://your-domain.example
```

## 安全自检

```bash
pip install -r apps/api/requirements.txt
python scripts/smoke_auth.py --base-url http://localhost:8000 --password "<AUTH_PASSWORD>"
pytest -q
```

API 启动时若仍使用默认 `AUTH_PASSWORD` / `API_KEY`，日志会输出 `SECURITY:` 警告。
