#!/usr/bin/env bash
# 安装 mind-sync Python 依赖
# 用法: ./scripts/install-deps.sh [--tools] [--dev]
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

TOOLS=false
DEV=false
for arg in "$@"; do
  case "$arg" in
    --tools) TOOLS=true ;;
    --dev) DEV=true ;;
  esac
done

echo "Python: $(python --version)"
python -m pip install --upgrade pip
python -m pip install --only-binary=:all: pydantic-core 2>/dev/null || \
  echo "Note: pydantic-core wheel unavailable; pip may compile (slow)."
python -m pip install -r requirements.txt

if $TOOLS; then
  echo "Installing CLI + MCP..."
  python -m pip install -r requirements-tools.txt
fi

if $DEV; then
  echo "Installing dev..."
  python -m pip install -r requirements-dev.txt
fi

echo "Done. Verify: python scripts/check_test_env.py"
