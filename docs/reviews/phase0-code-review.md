# Phase 0 代码审查报告

> 审查日期：2026-07 | 审查范围：角色统一重构（`viewer` → `member`）
>
> 关联 PRD：`docs/PRD.md`

---

## 审查结论

**通过** ✅ — 4 项 Critical 已修复，5 项 Suggestion 已修复。残留 `viewer` 全部消除。

---

## 问题汇总

### 🔴 Critical（已修复）

| ID | 问题 | 文件:行 | 修复 |
|----|------|---------|------|
| CR-01 | 测试断言 `role == "viewer"` 与实际返回 `"member"` 不匹配 | `tests/test_permissions.py:42` | 改为 `"member"` |
| CR-02 | 测试环境变量仍用 `viewer` 角色名 | `tests/test_permissions.py:15`、`tests/test_sources_reload.py:42` | 统一为 `member` |
| CR-03 | `docs/bak/` 过期文档镜像残留 | `docs/bak/`（12 个文件） | 移至 `docs/.archive/` |

### 🟡 Suggestion（已修复）

| ID | 问题 | 文件:行 | 修复 |
|----|------|---------|------|
| SG-01 | `.env` 注释 `viewer=只读` | `.env:11`、`.env.example:11` | 改为 `member=成员` |
| SG-02 | `generate_secrets.py` 示例 `viewer` | `scripts/generate_secrets.py:46` | 改为 `member` |
| SG-03 | 前端标签 `只读用户`（旧 viewer 语义） | `SyncSources.vue:390` | 改为 `成员` |
| SG-04 | 测试 docstring `admin vs viewer` | `tests/test_permissions.py:1` | 改为 `admin vs member` |
| SG-05 | 测试函数名 `test_viewer_*` | `tests/test_permissions.py:34,64`、`tests/test_sources_reload.py:41` | 改为 `test_member_*` |

### 🟢 Nice to have（延后）

| ID | 问题 | 说明 |
|----|------|------|
| NT-01 | `role` 返回值一致性 | `resolve_current_user()` 返回裸字符串，建议统一用 `Role` 枚举值 |
| NT-02 | `config.py:13` 注释 | 已由其他改动修复（`Roles: admin \| member`） |

---

## 确认良好的改动

| 文件 | 改动 | 评价 |
|------|------|------|
| `permissions.py:13` | `Role.MEMBER = "member"` | ✅ 单一权威来源 |
| `permissions.py:29-30` | `"viewer"` 向后兼容归一化 | ✅ 旧配置不断裂 |
| `auth.py:79` | `Role.MEMBER` 替代 `Role.VIEWER` | ✅ 正确 |
| `auth.py:186,192` | 默认 role → `"member"` | ✅ 正确 |
| `db.py:165-167` | V8 迁移 viewer → member（users + sessions） | ✅ 完整 |
| `config.py:13` | `Roles: admin \| member` | ✅ 已同步 |

---

---

## 第二轮审查（Wiki 隔离 + API Key 审计）

> 审查日期：2026-07 | 审查范围：`da3d260` — US-03 Wiki 隔离 + US-04 API Key 审计绑定

### 🔴 Critical（已修复）

| ID | 问题 | 文件:行 | 修复 |
|----|------|---------|------|
| CR-04 | `safe_wiki_path` 用 `username == "admin"` 判断管理员，应用 `role` 判断 | `wiki_util.py:48` | 增加 `role` 参数，`role == "admin"` 显式放行 |
| CR-05 | env API Key 时 `username=None` 导致隔离检查静默跳过 | `main.py:1582` → `wiki_util.py:48` | 同上修复覆盖；`role="admin"` 时显式授权 |

### 🟡 Suggestion（延后）

| ID | 问题 | 文件:行 |
|----|------|---------|
| SG-06 | `resolve_api_key_user()` 吞异常 | `auth.py:149-153` |
| SG-07 | `wiki_util.py` 两套隔离逻辑（`resolve_wiki_prefix` 未使用） | `wiki_util.py:6` |
| SG-08 | V9 迁移脆弱 try/except | `db.py:175` |

### 🟢 Nice to have（延后）

| ID | 问题 |
|----|------|
| NT-03 | `/api/wiki-page` 废弃端点可删除 |
| NT-04 | 缺少 Wiki 越权读取测试 |

### 第二轮修改文件

```
apps/api/app/services/wiki_util.py — safe_wiki_path 加 role 参数 + 修复判断逻辑
apps/api/app/main.py               — _read_wiki_page/wiki_content/wiki_page/update_wiki_content 传 role
```

---

## 残余检查

全项目 `search_content "viewer"` 结果：

| 位置 | 内容 | 判定 |
|------|------|------|
| `permissions.py:29` | `"viewer"` 在兼容集合中 | ✅ 有意保留 |
| `db.py:165-167` | V8 迁移 SQL 中的 `'viewer'` | ✅ 迁移逻辑，必须保留 |
| `docs/PRD.md` | PRD 描述旧状态的引用 | ✅ 历史记录 |
| `docs/.archive/*` | 归档的旧文档 | ✅ 已归档 |

**结论**：业务逻辑中无 `viewer` 残余。✅

---

## 修改文件清单

```
tests/test_permissions.py       — viewer → member（5 处）
tests/test_sources_reload.py    — viewer → member（2 处）
.env                            — 注释更新（2 处）
.env.example                    — 注释更新（2 处）
scripts/generate_secrets.py     — 示例更新（1 处）
apps/web-new/src/views/SyncSources.vue — 标签更新（1 处）
docs/bak/ → docs/.archive/      — 目录移动
```
