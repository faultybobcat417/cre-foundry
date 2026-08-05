#!/usr/bin/env bash
set -Eeuo pipefail

cd "$(
  git rev-parse --show-toplevel
)"

echo "===== PROJECT VERIFICATION ====="
./scripts/verify.sh

echo
echo "===== ASSURANCE MESH ====="
uv run cre-foundry \
  build-assurance-mesh

echo
echo "===== ACTIVATION MODEL CHECK ====="
uv run cre-foundry \
  build-activation-state-model

echo
echo "===== CONTRACT RESILIENCE ====="
uv run cre-foundry \
  build-contract-resilience-audit

echo
echo "===== SQL SAFETY PRIMITIVES ====="
./scripts/sql_safety_primitives_check.sh

echo
echo "===== DEVSECOPS SCANNER CONTROL PLANE ====="
./scripts/security_scan.sh

echo
echo "===== SQL SAFETY REMEDIATION INVENTORY ====="
./scripts/sql_safety_inventory.sh

echo
echo "===== SQL SAFETY WAVE 1A PLAN ====="
./scripts/sql_safety_wave1a_plan.sh

echo
echo "===== SECURITY BLOCKER RATCHET ====="
./scripts/security_ratchet.sh

echo
echo "===== SQL SAFETY WAVE 1A CANARY ====="
./scripts/sql_safety_wave1a_canary_check.sh

echo
echo "===== DIFF SAFETY ====="
git diff --check

echo
echo "AUDIT READINESS LOOP PASSED"
