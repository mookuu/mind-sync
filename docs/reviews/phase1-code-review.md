# Phase 1 代码审查报告

> 审查日期：2026-07 | 审查范围：PRD Phase 1 安全漏洞修复 + UX_SPEC 一致性
>
> 关联文档：`docs/PRD.md`、`docs/UX_SPEC.md`

---

## 审查结论

**通过** ✅ — 2 项缺陷已修复，4 项检查全部通过。Phase 0+1 安全漏洞清零。

---

## 缺陷汇总

### 🔴 Critical（已修复）

| ID | 问题 | 文件:行 | 修复 |
|----|------|---------|------|
| CR-06 | `browse_documents()` 无 `source_owner` 过滤，member 可浏览全部文档 | `categories.py:75` | 加 username/role 参数 + SQL WHERE 过滤 |
| CR-07 | `list_category_stats()` 无 `source_owner` 过滤，统计信息泄露 | `categories.py:53` | 同上，按角色过滤统计范围 |
| CR-08 | `GET /api/browse` 不传用户上下文 | `main.py:1490` | 加 `request: Request`，传入 `resolve_current_user()` |
| CR-09 | `GET /api/categories` 不传用户上下文 | `main.py:1481` | 同上 |

### 无缺陷确认

| 检查项 | 结果 |
|--------|------|
| `GET /api/search` 权限过滤 | ✅ `fts.py _user_owner_filter` 三层防线 |
| `GET /api/document/{doc_id}` owner 检查 | ✅ 之前已修复 |
| `safe_wiki_path` Wiki 隔离 | ✅ role 判断已修复 |
| API Key 审计绑定 | ✅ `resolve_actor` 优先返回绑定用户名 |
| 前端权限判断 | ✅ 全部 `role === "admin"`，无 `"viewer"` |
| UX_SPEC 实装状态 | ✅ 抽样 5/5 准确 |

---

## Phase 0+1 完成度

```
P0-1 Role 枚举 MEMBER           ✅
P0-2 DB 迁移 viewer→member      ✅
P0-3 _normalize_role 兼容       ✅
P0-4 auth.py role 映射          ✅
P0-5 全局 viewer 消除           ✅
P1-1 safe_wiki_path 隔离        ✅
P1-2 browse_documents 过滤      ✅
P1-3 get_document 过滤          ✅
P1-4 API Key 用户绑定           ✅
P1-5 审计 actor 解析            ✅
```

**Phase 0+1 完成度：10/10 ✅**

---

## 修改文件清单

```
apps/api/app/services/categories.py — browse_documents + list_category_stats 加 source_owner 过滤
apps/api/app/main.py                — browse + categories 端点加 request 参数
```
