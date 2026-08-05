#!/usr/bin/env bash
set -euo pipefail

SOURCE="/Users/alimehdi/Documents/cre"
EXPECTED_BRANCH="handoff/kimi-architecture-001"
EXPECTED_HEAD="f47e87defbfff9384d49e6d23c5494c0bdafcf68"
BASELINE_HEAD="dd44e5ee7f9195d140dfbd747b5a4812b199a81e"
EXPECTED_READINESS_SHA="e0fa1f1d03904d74fb948a8b7d22d028dd193a1090a6f41bcba235f11d46cbc0"
EXPECTED_IDENTITY_CONTRACT_SHA="583e7715e2af53e82309e934d6136d1b161bcda45771cebc948e9a9137525282"
EXPECTED_IDENTITY_SCHEMA_SHA="0c3b42f906063169b46cc760f9e7cf516b3c73c7c84f6293eb4cfcf826cc55ba"

STAMP="$(date +%Y%m%d-%H%M%S)"
OUT="$HOME/Desktop/CRE-Checkpoint-Verification-$STAMP"
CLONE="$OUT/repo"
LOGS="$OUT/logs"

fail() {
  printf '\nSTOP: %s\n' "$*" >&2
  exit 1
}

sha256() {
  shasum -a 256 "$1" | awk '{print $1}'
}

[[ -d "$SOURCE/.git" ]] || fail "Repository not found."
[[ "$(git -C "$SOURCE" branch --show-current)" == "$EXPECTED_BRANCH" ]] ||
  fail "Unexpected branch."
[[ "$(git -C "$SOURCE" rev-parse HEAD)" == "$EXPECTED_HEAD" ]] ||
  fail "Unexpected HEAD."
[[ "$(sha256 "$SOURCE/control/ONE_SHOT_READINESS.json")" == "$EXPECTED_READINESS_SHA" ]] ||
  fail "ONE_SHOT_READINESS.json changed."
[[ "$(sha256 "$SOURCE/artifacts/identity/public_evaluator_contract.json")" == "$EXPECTED_IDENTITY_CONTRACT_SHA" ]] ||
  fail "Frozen Identity evaluator contract changed."
[[ "$(sha256 "$SOURCE/contracts/temporal_identity.schema.json")" == "$EXPECTED_IDENTITY_SCHEMA_SHA" ]] ||
  fail "Frozen Identity schema changed."

mkdir -p "$OUT" "$LOGS"

git -C "$SOURCE" status --porcelain=v1 > "$OUT/source-status.before.txt"
git -C "$SOURCE" rev-parse HEAD > "$OUT/source-head.before.txt"

echo "Creating disposable verification clone:"
echo "$CLONE"
git clone --quiet --no-hardlinks "$SOURCE" "$CLONE"

# Overlay only the two known untracked files.
mkdir -p "$CLONE/control" "$CLONE/evals/known_bad/frontier"
cp -p "$SOURCE/control/ONE_SHOT_READINESS.json" \
  "$CLONE/control/ONE_SHOT_READINESS.json"
cp -p "$SOURCE/evals/known_bad/frontier/security_secret_log.json" \
  "$CLONE/evals/known_bad/frontier/security_secret_log.json"

cd "$CLONE"

git show --stat --summary 5b477d8 > "$OUT/commit-5b477d8-stat.txt"
git show --stat --summary f47e87d > "$OUT/commit-f47e87d-stat.txt"
git diff --name-status "$BASELINE_HEAD"..HEAD > "$OUT/committed-paths.txt"
git diff --stat "$BASELINE_HEAD"..HEAD > "$OUT/committed-stat.txt"

python3 -m json.tool \
  evals/known_bad/frontier/security_secret_log.json \
  > "$OUT/security-secret-log.pretty.json"

python3 <<'PY' > "$OUT/task-state.txt"
from __future__ import annotations

import json
from pathlib import Path

paths = [
    Path("control/CURRENT_STATE.json"),
    Path("control/CURRENT_TASK.json"),
    Path("control/TASK_GRAPH.json"),
    Path("tasks/IDENTITY-001.json"),
    Path("tasks/ECONOMICS-001.json"),
    Path("tasks/SECURITY-001.json"),
    Path("artifacts/task-results/IDENTITY-001.json"),
    Path("artifacts/task-results/ECONOMICS-001.json"),
    Path("artifacts/task-results/SECURITY-001.json"),
]

keys = [
    "task_id",
    "title",
    "status",
    "state",
    "phase",
    "current_task_id",
    "last_checkpoint",
    "proof_level",
    "achieved_proof_level",
    "completed_tasks",
    "executable_tasks",
    "blocked_tasks",
    "dependencies",
    "gates",
    "next_action",
]

for path in paths:
    print("=" * 78)
    print(path)
    print("=" * 78)

    if not path.exists():
        print("MISSING")
        continue

    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        print(f"PARSE ERROR: {type(exc).__name__}: {exc}")
        continue

    if not isinstance(value, dict):
        print(f"ROOT TYPE: {type(value).__name__}")
        continue

    for key in keys:
        if key in value:
            print(f"{key}:")
            print(json.dumps(value[key], indent=2, sort_keys=True))
PY

run_check() {
  local name="$1"
  shift
  local log="$LOGS/$name.log"

  set +e
  "$@" > "$log" 2>&1
  local code=$?
  set -e

  printf '%s\t%s\t%s\n' "$name" "$code" "$log" >> "$OUT/results.tsv"
  echo "$name -> exit $code"
}

printf 'check\texit_code\tlog\n' > "$OUT/results.tsv"

# Prove repeated validator execution is byte-stable.
git status --porcelain=v1 > "$OUT/clone-status.before-validation.txt"

run_check identity_validator_first \
  uv run --python 3.12 python scripts/validate_identity_contracts.py

run_check economics_validator_first \
  uv run --python 3.12 python scripts/validate_economics_contracts.py

git status --porcelain=v1 > "$OUT/clone-status.after-first-validation.txt"

run_check identity_validator_second \
  uv run --python 3.12 python scripts/validate_identity_contracts.py

run_check economics_validator_second \
  uv run --python 3.12 python scripts/validate_economics_contracts.py

git status --porcelain=v1 > "$OUT/clone-status.after-second-validation.txt"

if cmp -s \
  "$OUT/clone-status.before-validation.txt" \
  "$OUT/clone-status.after-first-validation.txt" &&
   cmp -s \
  "$OUT/clone-status.after-first-validation.txt" \
  "$OUT/clone-status.after-second-validation.txt"
then
  echo "YES" > "$OUT/validator-byte-stable.txt"
else
  echo "NO" > "$OUT/validator-byte-stable.txt"
fi

run_check all_public_tests \
  uv run --python 3.12 python -m unittest discover evals/public

run_check control_plane \
  uv run --python 3.12 python scripts/validate_control_plane.py

if [[ -f scripts/validate_security_privacy.py ]]; then
  run_check existing_security_privacy \
    uv run --python 3.12 python scripts/validate_security_privacy.py
fi

run_check git_diff_check git diff --check

git status --short --branch > "$OUT/clone-final-status.txt"

# Verify the real repository stayed untouched.
git -C "$SOURCE" status --porcelain=v1 > "$OUT/source-status.after.txt"
git -C "$SOURCE" rev-parse HEAD > "$OUT/source-head.after.txt"

cmp "$OUT/source-status.before.txt" "$OUT/source-status.after.txt" ||
  fail "Source worktree changed during verification."
cmp "$OUT/source-head.before.txt" "$OUT/source-head.after.txt" ||
  fail "Source HEAD changed during verification."

{
  echo "CRE COMPLETION CHECKPOINT VERIFICATION"
  echo "Verification folder: $OUT"
  echo "Source repository unchanged: YES"
  echo
  echo "BRANCH / HEAD"
  echo "$EXPECTED_BRANCH"
  echo "$EXPECTED_HEAD"
  echo
  echo "COMMITS SINCE LAST VERIFIED CHECKPOINT"
  git log --oneline --decorate --reverse "$BASELINE_HEAD"..HEAD
  echo
  echo "COMMITTED DIFF STAT"
  cat "$OUT/committed-stat.txt"
  echo
  echo "CURRENT TASK STATE"
  cat "$OUT/task-state.txt"
  echo
  echo "VALIDATION RESULTS"
  column -t -s $'\t' "$OUT/results.tsv" 2>/dev/null || cat "$OUT/results.tsv"
  echo
  echo "VALIDATOR BYTE-STABLE"
  cat "$OUT/validator-byte-stable.txt"
  echo
  echo "DISPOSABLE CLONE FINAL STATUS"
  cat "$OUT/clone-final-status.txt"
  echo
  echo "SECURITY FIXTURE"
  cat "$OUT/security-secret-log.pretty.json"
} > "$OUT/CHECKPOINT_SUMMARY.txt"

echo
echo "CHECKPOINT VERIFICATION COMPLETE"
echo "Source repository unchanged: YES"
echo
cat "$OUT/CHECKPOINT_SUMMARY.txt"
