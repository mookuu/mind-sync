# 变更日志

## 2026-06-17 (续)

- **feat**: 表示名（display_name）字段 — DB 迁移 V4 + 用户可编辑 + 右上角显示 + F5 持久化
- **feat**: 个人源共享 — `PUT /api/user/sources/{id}/share` 切换共享 + 共享知识库区域
- **feat**: 登录锁定 — DB 迁移 V5，失败超限自动锁定 5 分钟 + 状态列显示
- **feat**: 创建用户支持表示名输入
- **feat**: 非管理员「全局知识库」只显示管理员选中的源
- **feat**: 共享源名旁显示「共享中」标签
- **fix**: `user_sources.yaml` 写入路径与读取路径不一致（`/data/config/` vs `/data/`）
- **fix**: `_USER_ROOT` 遗漏 `users` 段导致路径错误
- **fix**: 非管理员「全部同步」状态未持久化 localStorage，F5 丢失
- **fix**: 前端 enrichment 覆盖后端 `path_exists` 导致路径有效性检测失效
- **fix**: 管理员源数量统计口径（改用 `list_sync_presets` 排除 all/custom）
- **fix**: 被共享源重复出现在「我的知识库」和「共享知识库」
- **fix**: 非管理员 `loadUserDisplayNames` 调 admin API 返回 403
- **fix**: 文件缺失警告逻辑修复（仅显示 `path_exists=false` 的源）
- **fix**: 侧边栏子菜单点击后父级收起
- **fix**: `.env` 删除重复的 `DATA_DIR=/data` 行
- **refactor**: 所有 alert/confirm → 居中模态弹窗（ESC/点击遮罩关闭）
- **refactor**: 侧边栏重写（同一时间只有一个父级展开 + 路由自动展开）
- **rename**: 「共享知识库」→「全局知识库」
- **docs**: lessons.md 归档今日踩坑记录

## 2026-06-17

- **feat**: 管理员重置用户密码（`POST /api/admin/users/{username}/reset-password`）
- **feat**: 用户管理页面"重置密码"弹窗 + 创建用户按钮位置调整
- **feat**: F5 刷新/重新登录保持上次打开的页面
- **feat**: 登录自动清理过期 session，每用户上限 5 条
- **fix**: `config.py` 增加 MSYS2 路径翻译防护（Windows Docker 兼容）
- **fix**: `main.py` 中 `authenticate` 被 `permissions` 同名函数覆盖导致 DB 用户无法登录
- **fix**: `update_settings` 权限从 `require_admin` 改为 `require_any_auth`（非管理员保存同步范围不生效）
- **fix**: `sync_source_ids` 过滤时忽略预设 ID（`web_snapshots` 勾选 F5 后丢失）
- **fix**: 列表页 `sync_presets` 加 `owner` 字段，前端 `!p.owner` 正确过滤个人/共享库
- **fix**: 添加 `dataLoaded` 标记，防止 F5 时模板空数据闪烁
- **refactor**: Sidebar 重写为固定顺序 + hover 展开/收起
- **docs**: 更新踩坑记录、API 端点文档

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
- **infra**: 数据目录迁移到独立位置 `${DATA_ROOT}`，与代码仓库分离
- **infra**: docker-compose.yml 通配映射 `/home/moku:/home/moku:ro`，简化卷管理
- **infra**: sources.yaml 精简为仅保留默认库，用户源移入 `user_sources.yaml`
- **infra**: 目录浏览器默认路径改为 `/home/moku/`
- **infra**: jieba 词典移至持久卷
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
