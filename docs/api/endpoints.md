# mind-sync API 端点参考

> Base URL: `http://localhost:8000`
> 认证方式：`Authorization: Bearer <API_KEY>` 或 Cookie Session

---

## 健康与认证

| 方法 | 路径             | 说明                                       |
| ---- | ---------------- | ------------------------------------------ |
| GET  | `/api/health`    | 系统健康检查，返回各源状态和安全警告       |
| GET  | `/api/auth-mode` | 查看当前认证模式                           |
| POST | `/api/login`     | 密码登录，返回 session cookie + CSRF token |
| POST | `/api/logout`    | 登出                                       |

## 知识源管理

| 方法 | 路径                        | 说明                                          |
| ---- | --------------------------- | --------------------------------------------- |
| GET  | `/api/sources`              | 列出所有配置的知识源                          |
| POST | `/api/sync`                 | 启动增量同步（GitHub pull + 本地扫描 + 索引） |
| GET  | `/api/sync-status`          | 查看同步进度和状态                            |
| POST | `/api/rebuild-index`        | 全量重建索引（不清除源数据）                  |
| POST | `/api/admin/sources/reload` | 重载 sources.yaml 配置                        |

## 检索与问答

| 方法 | 路径                                                 | 说明                              |
| ---- | ---------------------------------------------------- | --------------------------------- |
| GET  | `/api/search?q=<query>&limit=N&category=&source_id=` | FTS5 全文检索（**无需 LLM**）     |
| POST | `/api/query`                                         | LLM 问答，可选保存到 wiki/queries |
| GET  | `/api/classify-suggest?q=<query>`                    | 分类建议（给新内容推荐 topic）    |
| GET  | `/api/categories`                                    | 按 category/topic 统计文档数量    |

## 文档浏览

| 方法 | 路径                                   | 说明                                        |
| ---- | -------------------------------------- | ------------------------------------------- |
| GET  | `/api/browse?category=&topic=&limit=N` | 按分类/主题浏览                             |
| GET  | `/api/library?category=`               | 层级目录浏览（sources → languages → files） |
| GET  | `/api/document/{doc_id}`               | 获取单篇文档内容                            |
| GET  | `/api/document/{doc_id}/asset`         | 获取文档附件                                |
| GET  | `/api/wiki-asset`                      | Wiki 附件                                   |

## Wiki 管理

| 方法 | 路径                      | 说明                                |
| ---- | ------------------------- | ----------------------------------- |
| GET  | `/api/wiki-content?path=` | 读取 Wiki 页面                      |
| PUT  | `/api/wiki-content`       | 写入/更新 Wiki 页面                 |
| GET  | `/api/wiki-page`          | Wiki 页面信息                       |
| GET  | `/api/wiki-graph`         | Wiki 链接图谱分析（hubs / orphans） |
| POST | `/api/lint`               | Wiki 健康检查（断链/孤岛/过期）     |
| POST | `/api/ingest`             | 增量索引（不拉取远程）              |

## 规则约束 (Purpose)

| 方法 | 路径           | 说明             |
| ---- | -------------- | ---------------- |
| GET  | `/api/purpose` | 读取当前规则约束 |
| POST | `/api/purpose` | 更新规则约束     |

## 系统管理

| 方法 | 路径                        | 说明                             |
| ---- | --------------------------- | -------------------------------- |
| GET  | `/api/settings`             | 读取系统设置                     |
| POST | `/api/settings`             | 更新系统设置                     |
| GET  | `/api/audit-events?limit=N` | 审计日志（登录/同步/设置变更）   |
| GET  | `/api/vault-status`         | Git Vault 状态                   |
| POST | `/api/vault-sync`           | Git Vault 同步（push/pull wiki） |

---

## 常用组合

```bash
# 1. 健康检查
curl -s http://localhost:8000/api/health | jq .status

# 2. 同步
curl -X POST http://localhost:8000/api/sync \
  -H "Authorization: Bearer <API_KEY>"

# 3. 搜索（无 LLM）
curl -s "http://localhost:8000/api/search?q=关键词&limit=5" \
  -H "Authorization: Bearer <API_KEY>"

# 4. 问答（需 LLM）
curl -X POST http://localhost:8000/api/query \
  -H "Authorization: Bearer <API_KEY>" \
  -H "Content-Type: application/json" \
  -d '{"question":"你的问题","save_to_wiki":true}'

# 5. 质检
curl -s -X POST http://localhost:8000/api/lint \
  -H "Authorization: Bearer <API_KEY>" \
  -H "Content-Type: application/json" \
  -d '{"stale_days":180}'
```
