#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
OUT="${1:-mind-sync-data-backup.tgz}"
tar -czf "$OUT" -C "$ROOT" data/
echo "Wrote $OUT"
