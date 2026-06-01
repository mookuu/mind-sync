#!/usr/bin/env bash
set -euo pipefail
ARCHIVE="${1:?usage: restore_data.sh <backup.tgz>}"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
mkdir -p "$ROOT/data"
tar -xzf "$ARCHIVE" -C "$ROOT"
echo "Restored data/ under $ROOT — restart API container if running."
