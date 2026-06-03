#!/bin/bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

if [[ -n "${PYTHON_BIN:-}" ]]; then
    PYTHON="$PYTHON_BIN"
elif [[ -x "$ROOT_DIR/.venv/bin/python" ]]; then
    PYTHON="$ROOT_DIR/.venv/bin/python"
else
    PYTHON="python3"
fi

echo "Running backend lint..."
PYTHONPATH="$ROOT_DIR/backend" "$PYTHON" -m ruff check \
    "$ROOT_DIR/backend/app" \
    "$ROOT_DIR/backend/tests" \
    "$ROOT_DIR/scripts/migrate_v1_to_v2.py"

echo "Running backend tests..."
PYTHONPATH="$ROOT_DIR/backend" "$PYTHON" -m pytest "$ROOT_DIR/backend/tests" -q

echo "Running frontend tests..."
cd "$ROOT_DIR/frontend"
npm test

echo "Building frontend..."
npm run build

echo "All checks passed."
