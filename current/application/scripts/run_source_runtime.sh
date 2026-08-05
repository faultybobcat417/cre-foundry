#!/bin/bash
set -Eeuo pipefail

cd "$(
  git rev-parse --show-toplevel
)"

source .venv/bin/activate

mkdir -p logs

uv run cre-foundry source \
  initialize-source-runtime \
  > logs/source_runtime_initialization.json

uv run cre-foundry source \
  audit-source-runtime \
  > logs/source_runtime_audit.json

uv run cre-foundry source \
  plan-source-acquisitions \
  > logs/source_acquisition_plan.json

uv run cre-foundry source \
  plan-source-snapshot-bootstrap \
  > logs/source_snapshot_bootstrap.json

uv run cre-foundry source \
  audit-browser-recipes \
  > logs/browser_recipe_audit.json
