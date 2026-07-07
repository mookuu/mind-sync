# 安全策略

文档索引：[README.md](README.md) · 架构：[ARCHITECTURE.md](ARCHITECTURE.md)

> ⚠️ 2026-07 Phase 0 已将角色统一为 admin/member。本文档中 `viewer` 一词保留仅在历史示例中，实际代码使用 `member`。

## 版本支持

| 版本 | 支持状态 |
|------|----------|
| `main` | 是 |

## 报告漏洞

请私下报告安全问题（不要在公开 Issue 中附漏洞细节）。

1. 通过邮件或私信联系仓库所有者，附上问题描述和复现步骤。
2. 在公开披露前给予合理的修复时间。

## 认证

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
AUTH_USERS=admin:$2b$12$...:admin,reader:$2b$12$...:member
```

| 角色 | 能力 |
|------|------|
| **admin** | 同步、全量重建、wiki 编辑、Vault、settings、purpose、lint、问答保存 |
| **member** | 搜索、浏览、图谱、问答；管理私有源（不可写入共享 Wiki） |

Web UI 会隐藏/禁用写控件；**以 API 403 为准**。

## 限速

| 桶 | 默认 | 环境变量 |
|----|------|----------|
| 登录失败 | 5 次 / 5 分钟 / IP+用户 | `LOGIN_RATE_LIMIT_*` |
| sync / rebuild | 10 次 / 小时 | `API_RATE_LIMIT_SYNC_MAX` |
| query | 30 次 / 小时 | `API_RATE_LIMIT_QUERY_MAX` |
| lint | 20 次 / 小时 | `API_RATE_LIMIT_LINT_MAX` |

## 审计

- 事件：登录/登出、sync、rebuild、settings、wiki 更新、vault 等
- 查询：`GET /api/audit-events`（需鉴权）
- 保留天数：`AUDIT_RETENTION_DAYS`（默认 30 天）

## Web 源抓取

`type: web` 源同步时会 HTTP 抓取第三方页面。工程提供 robots 协议遵守、UA 声明、域名限速、allowlist 白名单等机制（**不替代法律合规审查**）。

- 生产环境建议配置：`WEB_FETCH_ALLOWLIST`、`WEB_FETCH_CONTACT`、`WEB_FETCH_REQUIRE_OPT_IN=true`
- 当前策略查询：`GET /api/health` 响应的 `web_fetch` 字段

## 部署清单

- [ ] 修改 `.env` 中的默认值：`AUTH_PASSWORD`、`SECRET_KEY`、`API_KEY`
- [ ] 如有多人使用，配置 `AUTH_USERS`
- [ ] HTTPS 环境下启用 `COOKIE_SECURE=true` 和 `SECURITY_HSTS_ENABLED=true`
- [ ] 限制网络访问（防火墙 / 反向代理）
- [ ] `GITHUB_TOKEN` 和 `LLM_API_KEY` 仅存储在环境变量中
- [ ] 启用 Web 源前检查 `WEB_FETCH_*` 各项配置
- [ ] 定期运行 `pip-audit -r apps/api/requirements.txt`（CI 中配置 push 触发）

## 数据处理

- 文档内容存储在 `DATA_DIR`（默认 `./data`）
- 搜索索引为本地 SQLite FTS；默认不入 Git
- 可选 `VAULT_GIT_URL`：配置后同步 `wiki/` 和 `purpose.md`；**pull 操作会覆盖本地 Wiki**（详见日志）
- `POST /api/ingest` 与 sync 一致，会跳过 github/local 同源配对的本地副本
- 系统级 Wiki 页面（`index.md`、`log.md`、`SCHEMA.md`）不可通过 API 写入
- LLM 问答在设置了 `LLM_API_KEY` 时会将文档摘要发送至 `LLM_BASE_URL`

## 响应头

默认启用：`X-Content-Type-Options`、`X-Frame-Options`、`Referrer-Policy`、`Permissions-Policy`；HSTS 可选开启。
