# PRD: mind-sync v2 — 权限体系统一与架构规范化

> 基于 v0.1.0 代码审计 + 全量文档交叉分析，2026-07 产出

---

## 1. 背景与动机

### 为什么做

mind-sync 经过 2025-06 ~ 2026-07 快速迭代，从单用户知识库演进为多用户 RBAC 系统。但快速迭代造成了**三套体系并行**的问题：

1. **权限体系分裂**：代码中是 `admin + viewer`（`permissions.py:11-13`），DB 和管理 API 接受 `member`（`main.py:742`），ROADMAP 声称合并为 `member`（`docs/ROADMAP.md` 决策记录），登录映射将 `member → viewer`（`auth.py:79`）——四条路径四种行为。
2. **安全漏洞**：Wiki 读取无用户隔离、文档浏览/读取无 owner 过滤、API Key 永远 admin 且无法审计追溯。
3. **文档腐烂**：两份完全相同的工作流文档、ROADMAP 号称 100% 完成但缺失 8+ 个已实现功能、死链接、todo.md 与 Phase 脱节。

### 解决什么问题

| 问题 | 用户影响 |
|------|----------|
| 权限混乱 | viewer 用户可以读取任何人的私有 Wiki 和私有源文档 |
| 角色名称冲突 | 环境变量配置 `member` 角色的用户被静默丢弃，无法登录 |
| 审计盲区 | API Key 调用无法追踪到具体人员 |
| 文档不可信 | 开发者不知道该看哪份文档，新成员无法上手 |

### 相关数据

- 代码库：55 个 API 端点，`main.py` 1788 行单文件
- 服务层：39 个模块，职责清晰但 API 层越界操作
- 测试覆盖：32 个测试文件，权限测试仅覆盖基本路径
- 文档：10+ 份 Markdown 文档，2 份完全重复

---

## 2. 目标与成功指标

### 业务目标

1. **权限体系统一**：确定唯一的角色模型，消除所有混乱路径
2. **安全漏洞清零**：消除所有已知的越权读取漏洞
3. **文档体系可信**：每份文档有明确权威来源，无重复、无死链接
4. **代码可维护**：`main.py` 拆分、响应模型规范化

### 可量化的成功标准

| 指标 | 当前 | 目标 | 验证方式 |
|------|------|------|----------|
| 角色定义源 | 4 处不一致 | 1 处（`permissions.py` 的 `Role` 枚举） | `search_content "viewer"` 无残余（仅保留迁移脚本注释） |
| Wiki 读取越权 | viewer 可读任何用户 wiki | member 只能读自己的和共享的 | 测试 `test_permissions.py` |
| 文档浏览越权 | 所有用户看到所有文档 | 按 source_owner 过滤 | 测试 `test_permissions.py` |
| 重复文档 | 2 份工作流文档 | 1 份 `docs/workflow.md` | 文件存在性检查 |
| ROADMAP 准确度 | 缺失 8+ 功能 | 100% 覆盖已实现功能 | 手动审查 |
| `main.py` 行数 | ~1788 行 | 路由层 < 200 行 | `wc -l` |

---

## 3. 功能范围

### In Scope（本次 PRD 覆盖）

| 模块 | 内容 |
|------|------|
| **P0 权限体系统一** | 确定 `admin/member` 命名 → 统一 `Role` 枚举 → 消除 `viewer` → 修复所有越权漏洞 |
| **P1 API 路由拆分** | `main.py` 拆分为 `routers/` 子模块；补充 Pydantic 响应模型 |
| **P2 文档清理** | 删除重复文档、更新 ROADMAP、修复死链接、统一术语 |
| **P3 安全加固** | API Key 绑定用户、审计完善、`safe_wiki_path` 修复 |
| **P4 测试补充** | 权限边界测试、越权测试、角色映射测试 |

### Out of Scope（本次不做）

- 向量库/Embedding 检索（`todo.md` 中的「本地存储向量库」）
- 关键字权重调整（`todo.md` 中的权重提升）
- 前端 UI 大改（仅修复权限相关的前端展示）
- 新功能开发（通知系统、登录锁等已实现，不在重构范围）
- Docker/部署架构变更

---

## 4. 用户故事

### P0 — 权限体系统一（最高优先级）

**US-01**：作为管理员，我使用 API 创建用户时指定 `member` 角色，该用户登录后应拥有 member 对应的权限，而不是被映射为另一个名称。`[P0]`

**US-02**：作为 member 用户，我使用 Web 搜索时只能看到共享源和我自己的私有源文档，无法看到其他用户的私有文档。`[P0]`

**US-03**：作为 member 用户，我通过 Wiki 读取其他用户私有 Wiki 页面时应被拒绝（403）。`[P0]`

**US-04**：作为管理员，我通过 API Key 调用时，审计日志应能追溯到具体用户而非仅 `api-key:msk-xxxx…`。`[P0]`

**US-05**：作为开发者，我在环境变量中配置 `AUTH_USERS` 时使用 `member` 角色，该用户应被正确识别和加载。`[P0]`

### P1 — API 层重构

**US-06**：作为开发者，我查找某个 API 端点时能在 `routers/` 目录下按功能分组快速定位，而非在一个 1788 行的文件中搜索。`[P1]`

**US-07**：作为 API 使用者，Swagger 文档中每个端点的响应结构应完整展示（通过 Pydantic `response_model`）。`[P1]`

### P2 — 文档清理

**US-08**：作为新成员，阅读文档时只有一个权威的工作流指南，不会在两份完全相同的文档间困惑。`[P2]`

**US-09**：作为开发者，ROADMAP 能真实反映代码现状，已实现的功能都被记录。`[P2]`

### P3 — 安全加固

**US-10**：作为管理员，API Key 创建时可绑定到具体用户，该 Key 的调用以该用户身份执行（而非永远 admin）。`[P3]`

### P4 — 测试补充

**US-11**：作为开发者，修改权限逻辑后有充分的测试覆盖边界路径，包括越权读写、角色映射、环境变量解析。`[P4]`

---

## 5. 验收标准

### US-01：角色命名统一

```
Given  管理员通过 POST /api/admin/users 创建用户，role="member"
When   该用户登录
Then   返回的角色信息应为 "member"（不是 "viewer"）
And    Role 枚举中应存在 MEMBER = "member"

Given  环境变量 AUTH_USERS="alice:pass123:member"
When   系统启动
Then   alice 应被加载，角色为 Role.MEMBER

Given  旧数据中 role="viewer"
When   执行 DB 迁移
Then   "viewer" 应被自动迁移为 "member"
```

### US-02：搜索权限过滤

```
Given  admin 用户有私有源 A，member 用户有私有源 B
When   member 用户搜索关键词 X
Then   结果中不应包含私有源 A 的文档
And    结果中应包含私有源 B 和共享源的文档
```

### US-03：Wiki 读取隔离

```
Given  member 用户 alice 的 Wiki 页面 wiki/users/alice/notes.md
When   member 用户 bob 请求 GET /api/wiki-content?path=wiki/users/alice/notes.md
Then   返回 403 Forbidden
```

### US-04：API Key 用户绑定

```
Given  管理员创建 API Key 绑定到用户 moku
When   使用该 API Key 调用 POST /api/query
Then   审计日志 actor 显示 "moku" 而非 "api-key:msk-xxxx…"
And    该请求以 moku 的身份（role=admin）执行
```

### US-05：环境变量 member 角色识别

```
Given  .env 中 AUTH_USERS="bob:secret:member"
When   系统启动
Then   bob 被加载为 AuthUser(username="bob", role=Role.MEMBER)
And    bob 可以正常登录
```

### US-06：路由拆分

```
Given  API 路由全部在 main.py 中
When   重构完成
Then   main.py 仅保留 app 创建 + 中间件 + 路由注册
And    每个功能域在 routers/{domain}.py 中有独立路由文件
And    Swagger 文档 /docs 正常展示所有端点
```

### US-08：文档去重

```
Given  docs/workflow.md 和 docs/MIND_SYNC_WORKFLOW.md 内容重复
When   重构完成
Then   docs/MIND_SYNC_WORKFLOW.md 被删除
And    docs/workflow.md 中所有链接指向正确的实际路径
And    docs/README.md 索引更新
```

---

## 6. 边界条件

| 场景 | 预期行为 |
|------|----------|
| **空数据库**（新部署） | Role 枚举只有 `ADMIN`/`MEMBER`；DB 中的旧 `viewer` 不存在 |
| **旧数据迁移**（`viewer` → `member`） | 迁移脚本将所有 `role='viewer'` 更新为 `role='member'`；迁移失败时回滚 |
| **网络异常**（API 请求失败） | 权限检查不依赖网络，本地校验 |
| **权限不足**（member 访问 admin 端点） | 返回 403，审计日志记录 |
| **并发源共享切换** | `toggle_source_shared` 加文件锁或 DB 事务 |
| **大量私有源**（100+ 用户各有 10+ 源） | 搜索过滤性能不劣化（索引 `source_owner` 列已有） |

---

## 7. 非功能性需求

### 性能

- 搜索权限过滤不引入额外 DB 查询（当前已通过 SQL WHERE `source_owner` 实现，保持不变）
- Wiki 隔离检查为 O(1) 路径前缀比对

### 安全

- 所有越权漏洞修复后需通过安全审查（对照 `SECURITY.md`）
- API Key 绑定用户后需支持吊销
- CSRF 机制保持不变

### 可访问性

- 前端错误提示（403/401）需区分"未登录"和"无权限"，给出明确中文提示

### 国际化

- 当前仅中文，无变更

### 向后兼容

- 旧 `viewer` 角色在 DB 迁移中自动转为 `member`
- API 端点路由路径不变
- 环境变量 `AUTH_USERS` 格式不变（`member` 角色被正确识别）

---

## 8. 重构路线图

```
Phase 0: 角色统一（当前 PRD 核心）  ← 必须先做
  ├─ P0-1 Role 枚举：MEMBER = "member" 替代 VIEWER
  ├─ P0-2 DB 迁移：viewer → member
  ├─ P0-3 _normalize_role() 识别 "member"
  ├─ P0-4 auth.py authenticate() 直接使用 DB role
  ├─ P0-5 全局搜索替换 "viewer" → "member"
  └─ P0-6 测试 → 部署

Phase 1: 安全漏洞修复  ← 最高优先级
  ├─ P1-1 safe_wiki_path() 真正校验 username
  ├─ P1-2 browse_documents() 加 source_owner 过滤
  ├─ P1-3 GET /api/document/{doc_id} 加 owner 过滤
  ├─ P1-4 API Key 绑定用户（api_keys 表加 username 列）
  └─ P1-5 审计 actor 解析改进

Phase 2: API 规范化
  ├─ P2-1 main.py 拆分为 routers/
  ├─ P2-2 补充 Pydantic 响应模型
  └─ P2-3 迁移系统加固（ALTER TABLE IF NOT EXISTS）

Phase 3: 文档清理
  ├─ P3-1 删除 MIND_SYNC_WORKFLOW.md
  ├─ P3-2 更新 ROADMAP.md
  ├─ P3-3 删除/整合 todo.md
  └─ P3-4 docs/README.md 索引修正

Phase 4: 测试补充
  ├─ P4-1 test_permissions.py 扩展
  ├─ P4-2 test_wiki_isolation.py 新增
  └─ P4-3 test_role_migration.py 新增
```

---

## 9. 风险与回滚

| 风险 | 影响 | 缓解 |
|------|------|------|
| 旧数据 `viewer` 角色迁移失败 | 用户无法登录 | 迁移前备份 DB；迁移脚本有 dry-run 模式 |
| 前端硬编码 `viewer` 字符串 | 前端角色判断失效 | `search_content "viewer"` 遍历前端代码 |
| API Key 绑定用户后行为变更 | 现有自动化脚本失效 | 未绑定用户的旧 API Key 保持 admin 行为 |
| Wiki 隔离上线后用户无法读取自己的 Wiki | 用户体验下降 | 充分测试，灰度发布 |

---

## 10. 关键决策记录

| 决策 | 选项 | 选择 | 理由 |
|------|------|------|------|
| 角色命名 | `admin/member` vs `admin/viewer` | **`admin/member`** | ROADMAP 决策记录一致；`viewer` 语义模糊 |
| 角色枚举位置 | 仅 `permissions.py` | **仅 `permissions.py`** | 单一权威来源，其他模块通过 `Role.MEMBER` 引用 |
| API Key 默认角色 | 永远 admin vs 绑定用户 | **绑定用户 + 未绑定时兼容 admin** | 安全与向后兼容兼顾 |
| `main.py` 拆分粒度 | 按功能域（sync/auth/wiki/admin/query） | **按功能域** | 当前 55 个端点自然分为 6-7 组 |
| 响应模型 | 全量 Pydantic vs 渐进 | **渐进：先核心端点** | 降低风险，search/query/sync 等高频端点优先 |
| 迁移脚本位置 | `db.py` 内 vs 独立文件 | **独立 `scripts/migrate_role.py`** | 可单独执行、可回滚 |

---

## 附：改善需求用户故事 (v1.x 迭代)

> 以下为 v1.x→v2.0 过渡期间的增量改善需求，按模块整理为正式用户故事。

### S-1：文档库 — 目录树展示

**S1-US-01**：作为用户，文档库树中的目录结构应与源的实际目录结构完全一致，不应因文件类型（Python/Markdown/Java）不同而拆分出多棵独立的树。`[done]`

**验收**：`moku-default/JavaBasic/src/main/Hello.java` 和 `moku-default/JavaBasic/README.md` 出现在同一棵 `moku-default` 树下的 `JavaBasic/` 目录中。

---

**S1-US-02**：作为用户，源的根目录下的文件（如 `README.md`）应在树中可见，不因缺少父目录而不渲染。`[done]`

**验收**：源的树中第一级同时显示顶层目录和顶层文件。

---

**S1-US-03**：作为用户，文档库树只显示已同步（增量同步或全量重建后）的源。未同步的源不应出现在文档库中。`[done]`

**验收**：素材管理添加新库 → 文档库不显示 → 同步控制点击增量同步 → 文档库出现该库。

---

**S1-US-04**：作为用户，路径无效的源（磁盘上目录不存在）不应出现在文档库树中。`[done]`

**验收**：素材管理中标记「⚠ 路径无效」的库，不出现在文档库「原始素材」中。

---

### S-2：文档库 — 代码/图片渲染

**S2-US-01**：作为用户，阅读代码文件（`.py`/`.java`/`.json` 等）时应看到语法高亮色彩，而非纯灰色文本块。`[done]`

**验收**：打开 Python 文件 → `def`/`class`/字符串等有不同颜色。HTML 中存在 `<span class="hljs-*">` 标签。

---

**S2-US-02**：作为用户，Markdown 文档中引用的本地图片应正确显示。`[done]`

**验收**：Markdown 中 `![desc](image.png)` 的图片通过 `/api/document/{id}/asset` 端点正确加载。

---

### S-3：全文搜索

**S3-US-01**：作为用户，搜索结果跨页面导航时保持状态。从搜索页点击结果跳转到文档库阅读后，返回搜索页仍能看到上次的搜索结果和关键词。`[done]`

**验收**：搜索"IO.md" → 点击结果 → 在 Library 阅读 → 浏览器后退 → 搜索页恢复上次结果。

---

**S3-US-02**：作为用户，增量同步或全量重建后搜索缓存应自动清空，避免点击过期结果导致 404。F5 刷新或重新进入搜索页时，若缓存未过期（10 分钟内）则保留。`[done]`

**验收**：搜索 → 同步 → 返回搜索页 → 缓存已清空，需重新搜索。F5 刷新后缓存仍有效。

---

**S3-US-03**：作为用户，搜索结果点击后侧边栏文档库树应自动展开并定位到对应文档。`[done]`

**验收**：搜索 → 点结果 → 跳转 Library → 侧边栏「原始素材」自动展开 → 树中高亮对应文档。

---

### S-4：素材管理

**S4-US-01**：作为管理员，素材管理页面分为三个清晰区域：全局知识库、我的知识库、共享知识库。`[done]`

**验收**：管理员登录素材管理，分别看到三个折叠区域，标签明确。

---

**S4-US-02**：作为管理员，全局知识库中 Obsidian、Web 快照、Wiki 三个默认库始终排在最前且默认勾选。`[done]`

**验收**：全局知识库展开 → 前三个条目为 Obsidian/Web快照/Wiki → checkbox 为勾选状态。

---

**S4-US-03**：作为任意角色，新增库后该库的同步 checkbox 不应自动勾选。`[done]`

**验收**：添加全局库 → 该库的 checkbox 为未勾选。原为"全部同步"则自动转为"自定义"模式。

---

**S4-US-04**：作为管理员，删除其他用户的个人库时，该用户登录后应看到顶部通知条：「xx 删除了 xx 库，请通过同步控制页面更新库信息」。`[done]`

**验收**：admin 删除 kan 的库 → kan 登录 → 顶部黄色通知条 → 点击跳转同步控制页。

---

**S4-US-05**：作为管理员，添加全局库时库的文件类型 include 应覆盖常见编程文件类型（.md/.py/.java/.txt/.json/.yaml/.js/.ts/.html/.css/.sql/.sh 等 18 种），而非仅 .md 和 .py。`[done]`

**验收**：添加全局库后，库内 .java/.json 等文件能被索引和搜索到。

---

### S-5：同步控制

**S5-US-01**：作为任意角色，可以访问同步控制页面并执行增量同步/全量重建。结果只影响自己的搜索和文档库视图。`[done]`

**验收**：member 登录 → 同步控制 → 点击增量同步 → 成功执行 → 文档库出现同步后的源。

---

**S5-US-02**（全部同步作用域）：

| 角色 | 范围 |
|------|------|
| 管理员 | 所有全局库（不管勾选）+ 所有个人库（不管勾选）+ 已勾选的共享库 |
| 只读 | 所有个人库（不管勾选）+ 已勾选的全局库 + 已勾选的共享库 |

---

**S5-US-03**：作为用户，全量重建的确认弹窗应使用统一的组件式 modal，而非浏览器 `confirm()` 对话框。`[done]`

**验收**：点击全量重建 → 弹出居中 modal →「确认执行全量重建？」→ 取消/确认重建 两个按钮。

---

**S5-US-04**：作为用户，删除源后文档库树菜单应同步更新，删除的源不再出现在树中。`[done]`

**验收**：素材管理删除 PythonBasic → 切回文档库 → 原始素材中 PythonBasic 消失。

---

### S-6：权限与菜单

**S6-US-01**：作为只读用户，Wiki图谱、规则约束、系统管理三个菜单项完全不可见。`[done]`

**验收**：member 登录 → 侧边栏无「Wiki图谱」「规则约束」「系统管理」条目。

---

**S6-US-02**：作为只读用户，通过 URL 直接输入 `/graph` 等管理员页面地址时，跳转到文档库并显示黄底提示「页面『/graph』仅管理员可访问」，不显示其他干扰信息。`[done]`

**验收**：member 直接访问 `/graph` → 跳转 `/library?denied=/graph` → 仅显示提示文字。

---

**S6-US-03**：作为开发者，系统中的角色定义应统一为 `admin` / `member`，消除 `viewer` 残余。`[PRD P0]`

**验收**：全局搜索 `viewer` 无业务逻辑引用。

---

### S-7：操作记录（原审计）

**S7-US-01**：作为任意角色，操作记录页面可见。管理员看到所有记录，只读用户仅看到自己的操作记录。`[done]`

**验收**：member → 操作记录 → 只有自己的登录/同步记录。

---

**S7-US-02**：作为用户，被管理员删除了个人库后，操作记录中该条记录高亮显示，点击可跳转到同步控制页面。`[done]`

**验收**：admin 删除 member 的库 → member 操作记录中出现黄色高亮条目 → 点击跳转 `/sync/control`。

---

### S-8：性能 — 文档库子菜单切换

**S8-US-01**：作为用户，在"原始素材"和"学习摘要"之间切换时，应瞬间完成，不出现"加载中"闪烁。`[done]`

**验收**：展开原始素材 → 展开学习摘要 → 再点原始素材 → 无 API 调用，无"加载中"文字。

---

**S8-US-02**：文档库树缓存仅在执行增量同步或全量重建后失效。其他任何操作（页面切换、素材管理增删源）不触发重新加载。`[done]`

**验收**：同步后切回文档库 → 树自动刷新。素材管理增删源 → 切回文档库 → 树不刷新（源未同步无变化）。

---

### S-9：CSRF 与登录稳定性

**S9-US-01**：作为用户，当 CSRF cookie 被浏览器清除后，POST 请求应自动恢复而不是报 403。`[done]`

**验收**：清除 `ms_csrf` cookie → 素材管理添加库 → 自动调 auth-mode 获取新 token → 重试成功。

---

**S9-US-02**：作为用户，页面刷新时若因并发 DB 锁导致 session 检查失败，应自动重试一次而非直接退出登录。`[done]`

**验收**：高并发场景下刷新页面 → 不会被踢出登录。

---

### 改善需求完成度总览

| 模块 | 完成 | 暂定 |
|------|------|------|
| S-1 文档库树 | ✅ | — |
| S-2 代码/图片渲染 | ✅ | — |
| S-3 全文搜索 | ✅ | — |
| S-4 素材管理 | ✅ | — |
| S-5 同步控制 | ✅ | — |
| S-6 权限与菜单 | ✅ | 只读角色素材管理细节 |
| S-7 操作记录 | ✅ | — |
| S-8 子菜单性能 | ✅ | — |
| S-9 CSRF/登录 | ✅ | — |
| PRD P0-P4（v2 重构） | ⬜ 未开始 | — |
