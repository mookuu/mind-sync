# 开发指南

文档索引：[docs/README.md](./README.md)

## 环境

- **Python 3.12**（与 CI / Docker 一致；见仓库根目录 `.python-version`）
- Node.js 22+（构建 Vue 3 前端 `apps/web-new/`）

### 依赖安装

```bash
pip install -r requirements.txt
pip install -r requirements-tools.txt   # CLI + MCP，可选
# pip install -r requirements-dev.txt   # pytest、pip-audit

python scripts/check_test_env.py
```

Windows：`.\scripts\install-deps.ps1 -Tools`  
Git Bash：`./scripts/install-deps.sh --tools`

Python 3.14 上若 `pip` 编译 `pydantic-core` 过慢，可先：

```bash
pip install --only-binary=:all: pydantic-core
pip install -r requirements.txt
```

Web 前端（Vue 3 + Vite）：

```bash
cd apps/web-new && npm install && npm run build
```

## 本地 API（非 Docker）

```bash
export DATA_DIR=./data
export SOURCES_FILE=./sources.yaml
uvicorn app.main:app --app-dir apps/api --reload
```

Windows PowerShell：

```powershell
$env:DATA_DIR="./data"
$env:SOURCES_FILE="./sources.yaml"
uvicorn app.main:app --app-dir apps/api --reload
```

## 测试

```bash
export DATA_DIR=./.pytest-data
export PYTHONPATH=apps/api
pytest -q
```

Windows：

```powershell
$env:DATA_DIR="./.pytest-data"
$env:PYTHONPATH="apps/api"
python -m pytest -q
```

测试使用 `tests/conftest.py` 隔离临时 `DATA_DIR`，不写入生产 `data/`。

### 测试卡住？

1. `python scripts/check_test_env.py`
2. 优先用 Python 3.12 虚拟环境
3. 不要用 `pytest ... | tail`（缓冲会导致假死）

## 模块速查

完整架构见 [ARCHITECTURE.md](./architecture.md)。

| 能力 | 模块 |
|------|------|
| 来源配置 | `services/indexer.load_sources`, [SOURCES.md](./reference/sources.md) |
| GitHub / Web 拉取 | `services/source_sync.py`, `services/git_ops.py` |
| 同源配对 | `services/source_pairing.py` |
| Web 抓取合规 | `services/web_fetch_policy.py` |
| Wiki 源/保护页 | `services/wiki_source.py` |
| Source → Spec | `services/source_spec_util.py` |
| HTML → MD | `services/web_extract.py` |
| 同步任务 | `services/sync_engine.py` |
| 全量重建 | `services/rebuild_engine.py` |
| Vault Git | `services/vault_git.py` |
| FTS 搜索 | `services/fts.py` |
| 问答 / 证据 | `services/query_engine.py`, `services/evidence.py` |
| Wiki 导航 | `services/wiki_nav.py` |
| Lint | `services/lint_engine.py` |
| RBAC | `services/permissions.py`, `services/auth.py` |
| 审计 / 限速 | `services/audit.py`, `services/rate_limit.py` |

## 冒烟脚本

```bash
python scripts/smoke_all.py --base-url http://localhost:8000 --password "<AUTH_PASSWORD>"
python scripts/smoke_auth_meta.py --base-url http://localhost:8000 --password "<AUTH_PASSWORD>"
```

## 提交前建议

```bash
pytest -q
pip-audit -r apps/api/requirements.txt   # 与 CI 一致时
```
