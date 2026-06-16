# 变更日志

## 2026-06-16

- **feat**: Source 模型加 `owner` 字段，支持共享/私有源隔离
- **feat**: `load_sources_for_user()` 按用户角色过滤源列表
- **feat**: DB 迁移 V3 — `documents` + `documents_fts` 加 `source_owner` 列
- **feat**: 搜索加用户权限过滤，私有源仅本人 + admin 可见
- **feat**: jieba 中文分词（预分词写入 FTS，搜索时同样分词查询）
- **feat**: 用户管理 API（`/api/admin/users` CRUD + `/api/user/me`）
- **feat**: 私有源管理 API（`/api/user/sources` CRUD）
- **feat**: Wiki 路径隔离 — `shared/` 共享 / `users/{name}/` 私有
- **feat**: 用户自动创建专属目录 `/data/users/{name}/` 和默认私有源
- **feat**: Admin Dashboard 系统概览页
- **feat**: 用户管理页面（`/admin/users`）
- **feat**: 一键重索引 API（`POST /api/admin/reindex`）
- **feat**: 数据备份脚本（`scripts/backup.py`）
- **feat**: 搜索结果标注源归属（🔒 私有标签）
- **feat**: 账户页扩展用户信息卡片
- **fix**: 删除按钮悬浮布局修复
- **fix**: 删除 API 复合 key 匹配（`PythonBasic:local`）
- **docs**: 更新 ROADMAP.md、API 端点文档、sources.yaml 配置参考

## 2026-06-15

- **chore**: 忽略 `.reasonix/`，清理临时构建脚本
- **docs**: 重构 docs/ 目录结构（统一小写命名、分组配置参考、新增 API 端点文档）

## 2026-06-05

- **config**: Reasonix 配置迁移，项目 `reasonix.toml` 精简，公共配置移至系统级

## 2026-06-02

- **feat**: RBAC 多用户权限、Web 抓取策略、源配对、模块化 Web UI
- **refactor**: 安全与代码质量改进
- **chore**: 项目配置更新、`.gitignore` 条目补充

## 2026-06-01

- **feat(api)**: 增强文库与 purpose 服务逻辑
- **fix(ci)**: 升级依赖修复 pip-audit 漏洞

## 更早

- 项目初始化、基础架构搭建
