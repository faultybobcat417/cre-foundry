#!/usr/bin/env bash
set -Eeuo pipefail

cd "$(
  git rev-parse --show-toplevel
)"

uv run cre-foundry \
  build-sql-safety-remediation-inventory

echo
echo "SQL SAFETY INVENTORY COMPLETED"
