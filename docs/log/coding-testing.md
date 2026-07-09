# 实际踩坑记录 — 开发与测试

> 本文档记录 mind-sync 开发中的测试相关踩坑，归档至 `docs/log/coding-testing.md`。
> 用于后续发布前检查、代码审查参考。

---

## 1. Pydantic response_model 类型不匹配导致 Health Check 失败

**症状**：API 启动后健康检查返回 `ResponseValidationError`，容器因 unhealthy 被 Docker 重启。

**根因**：`HealthResponse` 模型声明 `security: dict[str, Any]`，但实际端点返回的是 `list[str]`（`collect_security_warnings()` 返回字符串列表）。FastAPI 在运行时验证响应 → 不符合 Pydantic 模型 → 抛异常。

**教训**：
- `response_model` 不仅文档化，它还在运行时做类型校验
- 先确认端点实际返回类型，再定义模型
- 开发时注意 `FastAPI` 响应的 `ResponseValidationError` 会返回 500，可能导致容器健康检查失败

**修复**：`list[str]` 替代 `dict[str, Any]`。

---

## 2. main.py 拆分 routers 时的导入链断裂

**症状**：端点在 main.py 中删除后未迁入 router 文件 → 404。

**根因**：`sed -i '124,397d'` 删除了一块包含 login/logout/auth-mode 等端点的区域，但未检查这些端点是否已迁移到 router 文件。

**教训**：删除大块代码前先 grep 确认目标端点在其他地方有备份：

```bash
grep -n "@app.post.*login\|@app.get.*auth\|@app.post.*logout" main.py
# 确认所有被删端点在 router 中已补全
```

---

## 3. 意外创建的 router 文件

**症状**：Docker 构建时 `ImportError: cannot import name 'load_ordered_sources' from 'app.services.indexer'`。

**根因**：`sed` 命令截断 main.py 时，截断部分的内容被 shell 重定向写入了 `routers/admin.py`、`routers/user.py` 等文件。这些文件有错误的 import 语句，被 `main.py` 引用导致启动失败。

**教训**：
- 避免用 `sed` 做大幅代码移动，优先用 `git mv` + 手动拆分
- 重构前先 `ls routers/` 确认只有预期文件
- Deleted 的文件可能还在 Docker build context 中，重建前确认旧文件已清理

---

## 4. Pydantic 运行时校验的双刃剑

**收益**：Swagger 文档自动完整，端点返回结构可预期。
**风险**：类型不匹配直接报 500（而非静默丢字段），对健康检查等关键路径影响大。

**最佳实践**：
- 核心端点（health、auth-mode）加 `response_model`
- 复杂动态结构（sections、tree）用 `dict[str, Any]` 宽松校验
- 先确认不报错再加 `response_model`，不要在重构时同时做
