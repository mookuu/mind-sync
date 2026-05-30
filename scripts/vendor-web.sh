#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT/apps/web"
npm install --no-audit --no-fund
mkdir -p vendor
cp node_modules/marked/marked.min.js vendor/
cp node_modules/highlight.js/styles/github-dark.min.css vendor/github-dark.min.css
# Browser UMD bundle (npm common.js is Node-only)
curl -fsSL "https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.9.0/highlight.min.js" -o vendor/highlight.min.js
echo "Vendor files ready in apps/web/vendor/"
ls -la vendor/
