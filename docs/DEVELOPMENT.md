# 开发指南

## 工作区路径

项目源码位于：

`C:\Workspace\10.program\90.ai\mind-sync`

在 Cursor 中请 **Open Folder** 指向该目录（不要使用不存在的 `C:\Users\moku\Projects\mind-sync`）。

## 环境

- **Python 3.12**（与 CI / Docker 一致；见仓库根目录 `.python-version`）
- Node.js 22+（构建 `apps/web` vendor 包）

### 依赖安装（暂不跑 pytest 时）

```bash
# API（必选，本地 uvicorn / 自检）
pip install -r requirements.txt

# CLI + MCP（可选）
pip install -r requirements-tools.txt

# 开发/CI（pytest、pip-audit，可稍后再装）
# pip install -r requirements-dev.txt

python scripts/check_test_env.py
```

Windows：`.\scripts\install-deps.ps1 -Tools`  
Git Bash：`./scripts/install-deps.sh --tools`

3.14 上若 `pip` 卡住，先另开终端执行：

```bash
pip install --only-binary=:all: pydantic-core
pip install -r requirements.txt
```

Web 前端 vendor：

```bash
cd apps/web && npm install && npm run build:vendor
```

## 测试

### 本地卡住 / 很慢？

1. **先看环境（几秒内结束）**
   ```bash
   python scripts/check_test_env.py
   ```
2. **本机若是 Python 3.14**（`python --version`）  
   - `pytest` 本身不慢；**慢的是** `pip install` 在缺预编译 wheel 时编译 `pydantic-core`（Rust，可 10～30+ 分钟）。  
   - 项目 **CI / Docker 固定 3.12**；建议在 Windows 安装 [Python 3.12](https://www.python.org/downloads/) 后：
     ```bash
     py -3.12 -m venv .venv
     .venv\Scripts\activate
     pip install -r apps/api/requirements.txt -r requirements-dev.txt
     ```
3. **依赖未装全**时，`pytest` 应在收集阶段就报错（`No module named 'fastapi'`），不应 silent 挂住。若从未装过 API 依赖，先：
   ```bash
   pip install -r apps/api/requirements.txt -r requirements-dev.txt
   ```
4. **不要用** `pytest ... | tail -30`（Git Bash 下 pytest 缓冲输出时，`tail` 会一直等，看起来像卡死）。直接：
   ```bash
   set DATA_DIR=./.pytest-data
   python -m pytest -q --tb=short -x
   ```

### 常规命令

```bash
export DATA_DIR=./.pytest-data
pytest -q
```

## 本地 API（非 Docker）

```bash
export DATA_DIR=./data
export SOURCES_FILE=./sources.yaml
uvicorn app.main:app --app-dir apps/api --reload
```

## 架构要点

| 能力 | 模块 |
|------|------|
| GitHub 源拉取 | `services/source_sync.py`, `services/git_ops.py` |
| Vault 跨设备 | `services/vault_git.py`, `VAULT_GIT_URL` |
| 索引 | `services/indexer.py`, `services/sync_engine.py` |
| 搜索 | `services/fts.py`（`sort=mtime_desc`） |
| 问答降级 | `services/query_engine.py`（无 LLM / Ollama） |
