#!/bin/zsh
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

export DO_NOT_TRACK=1
export PREFECT_SERVER_ANALYTICS_ENABLED=false
export PREFECT_HOME="$ROOT/data/control/prefect"

echo "===== RUFF ====="
uv run ruff check src tests

echo
echo "===== MYPY ====="
uv run mypy src

echo
echo "===== PYTEST ====="
uv run pytest -q

echo
echo "===== DOCTOR ====="
uv run cre-foundry doctor

echo
echo "ALL PROJECT CHECKS PASSED"
