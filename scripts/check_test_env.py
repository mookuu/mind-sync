#!/usr/bin/env python3
"""Quick local check before pytest — prints blockers in seconds."""

from __future__ import annotations

import os
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(ROOT)
sys.path.insert(0, os.path.join(ROOT, "apps", "api"))
os.environ.setdefault("DATA_DIR", os.path.join(ROOT, ".pytest-data"))

print(f"Python: {sys.version.split()[0]} ({sys.executable})")
if sys.version_info[:2] != (3, 12):
    print("  ⚠ 项目 CI/Docker 使用 Python 3.12；3.14 一般可用，但缺 wheel 时 pip 会长时间编译 Rust。")
    print("  建议安装 3.12 并用: py -3.12 -m venv .venv")

deps = [
    "pytest",
    "fastapi",
    "pydantic",
    "pydantic_settings",
    "httpx",
    "yaml",
    "itsdangerous",
]
missing = []
for name in deps:
    mod = "pyyaml" if name == "yaml" else name.replace("-", "_")
    if name == "pydantic_settings":
        mod = "pydantic_settings"
    t0 = time.perf_counter()
    try:
        __import__(mod)
        dt = time.perf_counter() - t0
        print(f"  OK {name} ({dt:.2f}s)")
    except ImportError:
        missing.append(name)
        print(f"  MISSING {name}")

if missing:
    print("\n请先安装 API 依赖（若卡住很久，多半是在编译 pydantic-core，见 docs/DEVELOPMENT.md）：")
    print("  pip install --only-binary=:all: pydantic-core")
    print("  pip install -r requirements.txt")
    print("CLI/MCP 可选: pip install -r requirements-tools.txt")
    sys.exit(1)

print("\n导入 app.main …")
t0 = time.perf_counter()
from app.main import app  # noqa: E402

print(f"  OK ({time.perf_counter() - t0:.2f}s) — 可以运行 pytest")
print("  推荐: DATA_DIR=./.pytest-data python -m pytest -q --tb=short -x")
print("  不要用 tail 管道（Git Bash 下 pytest 缓冲时看起来像卡住）")
