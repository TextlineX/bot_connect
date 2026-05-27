#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

echo "[docs] 生成本项目动态文档片段..."
python scripts/gen_motion_presets_doc.py

if [[ "${1:-}" == "--official" ]]; then
  echo "[docs] 同步官方文档（需要 requests/html2text/bs4 等依赖）..."
  python scripts/sync_official_docs.py
fi

echo "[docs] 完成"

