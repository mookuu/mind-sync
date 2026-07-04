# Security Policy

文档索引：[docs/README.md](docs/README.md) · 架构：[docs/architecture.md](docs/architecture.md)

## Supported versions

| Version | Supported |
|---------|-----------|
| `main`  | Yes       |

## Reporting a vulnerability

Please report security issues privately (do not open a public issue with exploit details).

1. Email or message the repository owner with a description and reproduction steps.
2. Allow reasonable time for a fix before public disclosure.

## Authentication

| 方式 | 用途 | 写操作 |
|------|------|--------|
| Cookie 会话 | Web 浏览器 | 依 RBAC 角色 |
| `x-api-key` / Bearer | CLI、MCP | 始终 **admin** |

- 写请求（POST/PUT/DELETE）Cookie 鉴权需 **CSRF** 头（`x-csrf-token` 与 `ms_csrf` cookie 一致）
- 会话：`HttpOnly` cookie、可配 `Secure` / `SameSite` / TTL；`POST /api/logout` 吊销 token

## RBAC（角色）

配置见 `.env`：

```env
# 单用户（默认 admin）
AUTH_PASSWORD=strong-secret

# 多用户（密码推荐 bcrypt 哈希，明文仍兼容迁移期）
# 生成: python scripts/generate_secrets.py hash-password 'your-pass'
AUTH_USERS=admin:$2b$12$...:admin,reader:$2b$12$...:viewer
```

| 角色 | 能力 |
|------|------|
| **admin** | 同步、全量重建、wiki 编辑、Vault、settings、purpose、lint、问答保存 |
| **viewer** | 搜索、浏览、图谱、问答（不可写入磁盘） |

Web UI 会隐藏/禁用写控件；**以 API 403 为准**。

## Rate limiting

| 桶 | 默认 | 环境变量 |
|----|------|----------|
| 登录失败 | 5 次 / 5 分钟 / IP+用户 | `LOGIN_RATE_LIMIT_*` |
| sync / rebuild | 10 次 / 小时 | `API_RATE_LIMIT_SYNC_MAX` |
| query | 30 次 / 小时 | `API_RATE_LIMIT_QUERY_MAX` |
| lint | 20 次 / 小时 | `API_RATE_LIMIT_LINT_MAX` |

## Audit

- 事件：登录/登出、sync、rebuild、settings、wiki 更新、vault 等
- 查询：`GET /api/audit-events`（需鉴权）
- 保留：`AUDIT_RETENTION_DAYS`（默认 30）

## Web source fetch

`type: web` 同步会 HTTP 抓取第三方页面。工程提供 robots、UA、域名限速、allowlist（**不替代法律合规**）。

- 生产建议：`WEB_FETCH_ALLOWLIST`、`WEB_FETCH_CONTACT`、`WEB_FETCH_REQUIRE_OPT_IN=true`
- 策略：`GET /api/health` → `web_fetch`

## Deployment checklist

- [ ] Change `AUTH_PASSWORD`, `SECRET_KEY`, and `API_KEY` from defaults in `.env`
- [ ] Configure `AUTH_USERS` if multiple humans use the instance
- [ ] Use `COOKIE_SECURE=true` and `SECURITY_HSTS_ENABLED=true` over HTTPS
- [ ] Restrict network access (firewall / reverse proxy)
- [ ] Store `GITHUB_TOKEN` and `LLM_API_KEY` only in environment variables
- [ ] Review `WEB_FETCH_*` before enabling web sources
- [ ] Run `pip-audit -r apps/api/requirements.txt` periodically (CI on push)

## Data handling

- Document content: `DATA_DIR` (default `./data`)
- Search index: local SQLite FTS; not pushed to Git by default
- Optional `VAULT_GIT_URL`: syncs `wiki/` and `purpose.md` when configured; **pull replaces local wiki** (see logs)
- `POST /api/ingest` skips github/local paired locals (same as sync)
- System wiki pages (`index.md`, `log.md`, `SCHEMA.md`) are not writable via API
- LLM queries may send excerpts to `LLM_BASE_URL` when `LLM_API_KEY` is set

## Response headers

Default: `X-Content-Type-Options`, `X-Frame-Options`, `Referrer-Policy`, `Permissions-Policy`; optional HSTS.
