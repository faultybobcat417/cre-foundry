#!/usr/bin/env bash
set -Eeuo pipefail

cd "$(
  git rev-parse --show-toplevel
)"

mode="${1:-}"
raw_dir="logs/security_scans"

rm -rf "$raw_dir"
mkdir -p "$raw_dir"

echo "===== LOCKED ENVIRONMENT ====="

uv sync \
  --locked \
  --all-groups

echo
echo "===== TOOL VERSIONS ====="

uv run python - <<'PY' \
  > logs/security_scans/tool_versions.json
import json
from importlib.metadata import version


packages = (
    "pip-audit",
    "bandit",
    "detect-secrets",
    "pip-licenses",
)

print(
    json.dumps(
        {
            package: version(package)
            for package in packages
        },
        indent=2,
        sort_keys=True,
    )
)
PY

run_scanner() {
  local exit_file="$1"
  shift

  set +e
  "$@"
  local scanner_exit="$?"
  set -e

  printf '%s\n' \
    "$scanner_exit" \
    > "$exit_file"
}

echo
echo "===== DEPENDENCY VULNERABILITIES ====="

run_scanner \
  "$raw_dir/pip_audit.exit_code" \
  uv run pip-audit \
    --local \
    --format=json \
    --progress-spinner=off \
    --output "$raw_dir/pip_audit.json"

if [ ! -f "$raw_dir/pip_audit.json" ]; then
  printf '[]\n' \
    > "$raw_dir/pip_audit.json"
fi

echo
echo "===== PYTHON SECURITY STATIC ANALYSIS ====="

run_scanner \
  "$raw_dir/bandit.exit_code" \
  uv run bandit \
    -r src \
    -f json \
    -o "$raw_dir/bandit.json"

if [ ! -f "$raw_dir/bandit.json" ]; then
  printf '{"results":[],"errors":[]}\n' \
    > "$raw_dir/bandit.json"
fi

echo
echo "===== WORKTREE SECRET SCAN ====="

set +e

uv run detect-secrets scan \
  --all-files \
  --exclude-files \
  '(^|/)(\.git|\.venv|data|logs)(/|$)|^docs/security/.*\.json$' \
  > "$raw_dir/detect_secrets.json"

detect_exit="$?"

set -e

printf '%s\n' \
  "$detect_exit" \
  > "$raw_dir/detect_secrets.exit_code"

if [ ! -f "$raw_dir/detect_secrets.json" ]; then
  printf '{"results":{}}\n' \
    > "$raw_dir/detect_secrets.json"
fi

echo
echo "===== LICENSE INVENTORY ====="

set +e

uv run pip-licenses \
  --format=json \
  --with-urls \
  > "$raw_dir/pip_licenses.json"

license_exit="$?"

set -e

printf '%s\n' \
  "$license_exit" \
  > "$raw_dir/pip_licenses.exit_code"

if [ ! -f "$raw_dir/pip_licenses.json" ]; then
  printf '[]\n' \
    > "$raw_dir/pip_licenses.json"
fi

echo
echo "===== NORMALIZE AND GOVERN FINDINGS ====="

uv run cre-foundry \
  build-devsecops-scanner-control-plane

if [ "$mode" = "--enforce" ]; then
  echo
  echo "===== ENFORCE SECURITY GATE ====="

  uv run python - <<'PY'
import json
from pathlib import Path


summary = json.loads(
    Path(
        "docs/security/"
        "devsecops_scanner_summary.json"
    ).read_text(
        encoding="utf-8"
    )
)

if not summary[
    "scanner_control_plane_operational"
]:
    raise SystemExit(
        "Scanner control plane is not operational."
    )

if not summary[
    "security_gate_passed"
]:
    raise SystemExit(
        "Unresolved blocking security findings exist."
    )

print(
    "Enforced security gate passed."
)
PY
fi

echo
echo "SECURITY SCANNER LOOP COMPLETED"
