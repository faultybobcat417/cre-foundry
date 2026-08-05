#!/usr/bin/env bash
set -euo pipefail

REPO="/Users/alimehdi/Documents/cre"
EXPECTED_BRANCH="handoff/kimi-architecture-001"
EXPECTED_HEAD="f47e87defbfff9384d49e6d23c5494c0bdafcf68"
EXPECTED_READINESS_SHA="e0fa1f1d03904d74fb948a8b7d22d028dd193a1090a6f41bcba235f11d46cbc0"

STAMP="$(date +%Y%m%d-%H%M%S)"
OUT="$HOME/Desktop/CRE-Current-Checkpoint-$STAMP"
LOGS="$OUT/logs"
PARTIAL="$OUT/partial-security-work"

fail() {
  printf '\nSTOP: %s\n' "$*" >&2
  exit 1
}

sha256() {
  shasum -a 256 "$1" | awk '{print $1}'
}

[[ -d "$REPO/.git" ]] || fail "Repository not found."
[[ "$(git -C "$REPO" branch --show-current)" == "$EXPECTED_BRANCH" ]] ||
  fail "Unexpected branch."
[[ "$(git -C "$REPO" rev-parse HEAD)" == "$EXPECTED_HEAD" ]] ||
  fail "Unexpected HEAD."
[[ "$(sha256 "$REPO/control/ONE_SHOT_READINESS.json")" == "$EXPECTED_READINESS_SHA" ]] ||
  fail "Protected readiness file changed."

cd "$REPO"

git diff --quiet || fail "Tracked unstaged changes exist."
git diff --cached --quiet || fail "Staged changes exist."

EXPECTED_UNTRACKED="$(
  printf '%s\n' \
    control/ONE_SHOT_READINESS.json \
    evals/known_bad/frontier/security_secret_log.json |
  sort
)"

ACTUAL_UNTRACKED="$(
  git ls-files --others --exclude-standard | sort
)"

[[ "$ACTUAL_UNTRACKED" == "$EXPECTED_UNTRACKED" ]] ||
  fail "Unexpected untracked-file set."

mkdir -p "$OUT" "$LOGS" "$PARTIAL"

# Preserve the unfinished Security mutation before removing it from the live repo.
cp -p \
  "$REPO/evals/known_bad/frontier/security_secret_log.json" \
  "$PARTIAL/security_secret_log.json"

LATEST_DIAGNOSTIC="$(
  ls -t "$HOME"/Desktop/CRE-Security-Diagnostic-*.txt 2>/dev/null |
  head -1 || true
)"

if [[ -n "$LATEST_DIAGNOSTIC" && -f "$LATEST_DIAGNOSTIC" ]]; then
  cp -p "$LATEST_DIAGNOSTIC" "$PARTIAL/security-diagnostic.txt"
fi

cat > "$PARTIAL/README.md" <<'EOF'
# Paused Security Evaluator Work

This folder preserves the uncommitted `security_secret_log.json` fixture that
Antigravity created immediately before quota exhaustion.

It was not valid to leave active by itself because the existing
`validate_security_privacy.py` evaluator currently:

- discovers every `security_*.json` fixture,
- supports only `retrieved_authority` and `pii_log` mutation recipes, and
- has public evidence registering only those two cases.

Therefore the new `secret_log` fixture made the existing validator fail until
the evaluator, diagnostic logic, evidence registry, and frozen Security
contract are extended together.

This fixture is preserved as a design input for `SECURITY-001`; it is not a
completed or accepted artifact.
EOF

shasum -a 256 "$PARTIAL/security_secret_log.json" \
  > "$PARTIAL/security_secret_log.sha256"

# Remove only the orphaned untracked fixture from the live repository.
rm -- "$REPO/evals/known_bad/frontier/security_secret_log.json"

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

  [[ "$code" -eq 0 ]] || fail "$name failed; see $log"
}

printf 'check\texit_code\tlog\n' > "$OUT/results.tsv"

run_check \
  security_privacy_validator \
  uv run --python 3.12 python scripts/validate_security_privacy.py

run_check \
  all_public_tests \
  uv run --python 3.12 python -m unittest discover evals/public

run_check \
  control_plane \
  uv run --python 3.12 python scripts/validate_control_plane.py

run_check \
  git_diff_check \
  git diff --check

# Final repository must contain no tracked changes and only readiness untracked.
git diff --quiet || fail "Validation introduced tracked changes."
git diff --cached --quiet || fail "Validation introduced staged changes."

FINAL_UNTRACKED="$(
  git ls-files --others --exclude-standard | sort
)"

[[ "$FINAL_UNTRACKED" == "control/ONE_SHOT_READINESS.json" ]] ||
  fail "Unexpected final untracked-file set."

[[ "$(sha256 "$REPO/control/ONE_SHOT_READINESS.json")" == "$EXPECTED_READINESS_SHA" ]] ||
  fail "Protected readiness file changed during checkpointing."

# Build an organized current checkpoint package.
git bundle create "$OUT/cre-current.bundle" --all

git status --short --branch > "$OUT/git-status.txt"
git log --oneline --decorate -30 > "$OUT/recent-commits.txt"
git branch -vv > "$OUT/branches.txt"

mkdir -p \
  "$OUT/control" \
  "$OUT/tasks" \
  "$OUT/task-results"

cp -p control/CURRENT_STATE.json "$OUT/control/"
cp -p control/CURRENT_TASK.json "$OUT/control/"
cp -p control/TASK_GRAPH.json "$OUT/control/"
cp -p control/ONE_SHOT_READINESS.json "$OUT/control/"

for file in \
  tasks/IDENTITY-001.json \
  tasks/ECONOMICS-001.json \
  tasks/SECURITY-001.json
do
  cp -p "$file" "$OUT/tasks/"
done

for file in \
  artifacts/task-results/IDENTITY-001.json \
  artifacts/task-results/ECONOMICS-001.json
do
  cp -p "$file" "$OUT/task-results/"
done

{
  shasum -a 256 \
    control/ONE_SHOT_READINESS.json \
    artifacts/identity/public_evaluator_contract.json \
    contracts/temporal_identity.schema.json
} > "$OUT/protected-hashes.txt"

PUBLIC_COUNT="$(
  grep -Eo 'Ran [0-9]+ tests' "$LOGS/all_public_tests.log" |
  tail -1 || true
)"

cat > "$OUT/CURRENT_CHECKPOINT.md" <<EOF
# CRE Foundry Current Checkpoint

## Repository

- Branch: $EXPECTED_BRANCH
- HEAD: $EXPECTED_HEAD
- Protected readiness SHA-256: $EXPECTED_READINESS_SHA
- Tracked worktree: clean
- Staged files: none
- Expected untracked file: control/ONE_SHOT_READINESS.json only

## Verified commits since the prior checkpoint

- 5b477d8 — complete Economics control transition and select Security
- f47e87d — repair Identity and Economics validator byte stability

## Completion state

- 12 of 24 control-plane tasks completed
- Current task: SECURITY-001
- Current task status: in_progress
- Identity material result: completed, public proof level 4
- Economics material result: completed, public proof level 5
- Security material result: not yet created
- Security is the only currently executable task

## Validation

- Existing Security/privacy frontier validator: PASS
- Full public suite: PASS (${PUBLIC_COUNT:-test count not parsed})
- Control-plane validator: PASS
- git diff --check: PASS
- Identity/Economics deterministic replay was verified previously

## Paused Security work

The orphaned secret-log mutation fixture was removed from the live repository
after being preserved under:

partial-security-work/security_secret_log.json

It must be reintroduced only as part of a coherent evaluator-first Security
checkpoint that also adds its mutation implementation, diagnostic, evidence
registration, frozen evaluator contract, tests, and material implementation.

## Known follow-up audit

The task definition files for IDENTITY-001 and ECONOMICS-001 still contain
status `in_progress`, while their task-result artifacts and CURRENT_STATE mark
them completed. The control-plane validator passes, so this is not current
repository corruption. Determine later whether task definitions are intended
to be immutable execution briefs or should be reconciled.

## Next exact action

Freeze the SECURITY-001 evaluator contract and registered mutation set before
implementing the Security material layer. Do not modify or stage
control/ONE_SHOT_READINESS.json.
EOF

OUT="$OUT" python3 <<'PY'
from __future__ import annotations

import hashlib
import os
from pathlib import Path

out = Path(os.environ["OUT"])
lines = []

for path in sorted(out.rglob("*")):
    if not path.is_file() or path.name == "CHECKSUMS.sha256":
        continue
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    lines.append(f"{digest}  {path.relative_to(out)}")

(out / "CHECKSUMS.sha256").write_text(
    "\n".join(lines) + "\n",
    encoding="utf-8",
)
PY

echo
echo "CURRENT CHECKPOINT ORGANIZED"
echo "Repository clean except protected readiness file: YES"
echo
echo "Checkpoint folder:"
echo "$OUT"
echo
echo "Validation results:"
column -t -s $'\t' "$OUT/results.tsv" 2>/dev/null || cat "$OUT/results.tsv"
echo
echo "Repository status:"
git status --short --branch
echo
echo "Checkpoint summary:"
cat "$OUT/CURRENT_CHECKPOINT.md"
