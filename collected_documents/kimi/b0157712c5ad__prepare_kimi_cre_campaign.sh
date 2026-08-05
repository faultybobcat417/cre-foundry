#!/usr/bin/env bash
set -euo pipefail

SOURCE="/Users/alimehdi/Documents/cre"
EXPECTED_BRANCH="handoff/kimi-architecture-001"
EXPECTED_HEAD="f47e87defbfff9384d49e6d23c5494c0bdafcf68"
EXPECTED_READINESS_SHA="e0fa1f1d03904d74fb948a8b7d22d028dd193a1090a6f41bcba235f11d46cbc0"

STAMP="$(date +%Y%m%d-%H%M%S)"
BRANCH="kimi/security-001-golden-$STAMP"
WORKTREE="$HOME/Desktop/CRE-Kimi-Security-$STAMP"
PACKET="$HOME/Desktop/CRE-Kimi-Campaign-$STAMP"

fail() {
  printf '\nSTOP: %s\n' "$*" >&2
  exit 1
}

sha256() {
  shasum -a 256 "$1" | awk '{print $1}'
}

[[ -d "$SOURCE/.git" ]] || fail "Repository not found: $SOURCE"
[[ "$(git -C "$SOURCE" branch --show-current)" == "$EXPECTED_BRANCH" ]] ||
  fail "Unexpected source branch."
[[ "$(git -C "$SOURCE" rev-parse HEAD)" == "$EXPECTED_HEAD" ]] ||
  fail "Unexpected source HEAD."
[[ -f "$SOURCE/control/ONE_SHOT_READINESS.json" ]] ||
  fail "Protected readiness file missing."
[[ "$(sha256 "$SOURCE/control/ONE_SHOT_READINESS.json")" == "$EXPECTED_READINESS_SHA" ]] ||
  fail "Protected readiness hash mismatch."

SOURCE_STATUS="$(
  git -C "$SOURCE" status --porcelain=v1
)"
[[ "$SOURCE_STATUS" == "?? control/ONE_SHOT_READINESS.json" ]] ||
  fail "Source repository is not at the expected clean checkpoint."

mkdir -p "$PACKET"

git -C "$SOURCE" worktree add -b "$BRANCH" "$WORKTREE" "$EXPECTED_HEAD"

mkdir -p "$WORKTREE/control"
cp -p \
  "$SOURCE/control/ONE_SHOT_READINESS.json" \
  "$WORKTREE/control/ONE_SHOT_READINESS.json"
chmod 444 "$WORKTREE/control/ONE_SHOT_READINESS.json"

# Copy useful external references when present.
for candidate in \
  "$HOME/Downloads/CRE_STRONG_PRODUCTION_RESEARCH_AND_BUILD_PROGRAM_v1.md" \
  "/mnt/data/CRE_STRONG_PRODUCTION_RESEARCH_AND_BUILD_PROGRAM_v1.md" \
  "$HOME/Desktop/CRE-Current-Checkpoint-20260803-184027/CURRENT_CHECKPOINT.md"
do
  if [[ -f "$candidate" ]]; then
    cp -p "$candidate" "$PACKET/$(basename "$candidate")"
  fi
done

cat > "$PACKET/00_READ_ME_FIRST.md" <<EOF
# Kimi CRE Campaign Control Packet

## Isolated worktree

- Path: \`$WORKTREE\`
- Branch: \`$BRANCH\`
- Starting HEAD: \`$EXPECTED_HEAD\`
- Source repository remains untouched at \`$SOURCE\`

## Hard budget policy

This campaign does not attempt the remaining production system in one session.
It uses scarce Kimi capacity to create one golden evaluator-first checkpoint:
\`SECURITY-001\`.

The repeatable campaign pattern is:

1. bounded read-only audit;
2. evaluator freeze;
3. material implementation;
4. full verification and red team;
5. coherent commit and continuation packet;
6. stop before the next task.

## Safety

- Never edit, stage, commit, regenerate or delete
  \`control/ONE_SHOT_READINESS.json\`.
- Never push.
- Never use real credentials or PII.
- Keep live permissions and external effects disabled.
- Work only inside the isolated worktree.
- Do not begin a second control-plane task.
EOF

cat > "$PACKET/01_LOOP_1_AUDIT_AND_PLAN.txt" <<'EOF'
You are the principal integration engineer for one bounded CRE Foundry
checkpoint. Work inside the current isolated Git worktree only.

FIRST VERIFY, READ-ONLY

1. Print branch, HEAD, status, recent commits and protected readiness SHA.
2. Confirm the expected starting checkpoint is f47e87d and the only untracked
   file is control/ONE_SHOT_READINESS.json.
3. Read CURRENT_STATE, CURRENT_TASK, TASK_GRAPH and tasks/SECURITY-001.json.
4. Read all existing security/privacy validators, fixtures, evidence, threat
   model and directly relevant tests.
5. Read the completed Identity and Economics evaluator/material patterns.
6. Read the production-program reference in the added campaign directory when
   present.
7. Use an explore swarm only for independent read-only repository mapping and
   red-team gap discovery. Maximum useful concurrency is two. Do not dispatch
   coding agents and do not edit during this loop.

PLAN REQUIREMENTS

Produce a concrete evaluator-first plan for completing SECURITY-001, including:

- exact files to add or change;
- evaluator/material independence boundary;
- frozen contract and schema;
- clean synthetic subject;
- registered mutations and stable diagnostics for secret logging, PII logging,
  retrieved authority, prompt-instruction bypass, unauthorized external write,
  live-default enablement, retention violation, deletion refusal, excessive
  privilege and malformed/unknown security state;
- deterministic evidence generation;
- public tests;
- material security implementation;
- full acceptance commands;
- control-state and task-result transition;
- rollback;
- coherent commit boundaries;
- stop-budget strategy if quota becomes low.

Do not modify repository files during this loop. Do not claim tests were run.
End with the exact implementation goal that should be approved next.
EOF

cat > "$PACKET/02_LOOP_2_EXECUTE_GOAL.txt" <<'EOF'
/goal Complete SECURITY-001 evaluator-first in this isolated worktree and stop
after one coherent passing Security checkpoint. First freeze an implementation-
independent public evaluator contract, schema, mutation registry, known-bad
fixtures, deterministic evidence and public tests. Prove the evaluator rejects
every registered mutation and accepts the clean synthetic subject. Then build
the minimum material src/cre_foundry/security layer required by the task,
including explicit threat/data classifications, least privilege, negative
authorization, untrusted-input isolation, live-disabled defaults, redaction,
retention and verifiable deletion behavior. Keep all data synthetic, use no
credentials or PII, perform no network or external writes, never modify/stage/
commit control/ONE_SHOT_READINESS.json, never push, and do not alter completed
Identity or Economics contracts. Run the Security validator twice for byte
stability, all direct tests, the full public suite, control-plane validation,
compile checks and git diff --check. Independently red-team the final diff,
repair every supported failure, update the truthful SECURITY-001 task result
and control transition only after all gates pass, make small coherent commits,
write a continuation packet, and stop without starting the next task. If the
full material layer cannot be completed within the remaining budget, preserve
the largest coherent passing evaluator-first checkpoint, commit only green
work, document the exact stop point and stop rather than leaving partial edits.
EOF

cat > "$PACKET/03_LOOP_3_VERIFY_AND_REPAIR.txt" <<'EOF'
Perform an independent final verification of the SECURITY-001 checkpoint in
this isolated worktree.

Use read-only explore/reviewer sub-agents for separate checks of:

1. evaluator independence and frozen-contract integrity;
2. mutation completeness and diagnostic registration;
3. material security behavior and fail-closed defaults;
4. temporal/provenance/claim-ceiling correctness;
5. regression, control-state truth and protected-file safety.

Do not use a broad swarm for implementation. Aggregate the reviews, reproduce
every supported finding locally, repair only confirmed defects, and rerun:

- Security validator twice with byte-stability comparison;
- direct Security public tests;
- full public test suite;
- control-plane validator;
- Python compile checks;
- git diff --check;
- protected readiness hash and untracked-state check.

Require a clean tracked worktree, no staged protected readiness file, truthful
task result, coherent commits and a continuation packet. Never push. Stop after
SECURITY-001; do not begin another task.
EOF

cat > "$PACKET/04_REPEATING_CAMPAIGN_TEMPLATE.md" <<'EOF'
# Repeating Campaign Template

For every later task, create a new worktree from the last verified integration
checkpoint and repeat:

## Loop 1 — Map and freeze

- Verify checkpoint and protected files.
- Use at most two read-only specialists for independent mapping.
- Freeze the decision, evaluator, mutations, acceptance commands and claim
  ceiling.
- No material implementation yet.

## Loop 2 — Build to a goal

- Use one main agent in Auto mode.
- Use coder sub-agents only for truly isolated modules.
- Keep shared control files owned by the main integrator.
- Run tests after every coherent layer.
- Commit green checkpoints before context or quota exhaustion.
- Never advance to another task automatically.

## Loop 3 — Sweep, red-team and integrate

- Use independent read-only reviewers.
- Reproduce findings before repair.
- Rerun the complete regression suite.
- Update task result, evidence, decision/risk logs and continuation packet.
- Merge only after human inspection of the diff and tests.

## Stop rule

A smaller passing, documented checkpoint is always preferred to a larger
unfinished or unverified diff.
EOF

cat > "$PACKET/start_loop_1.sh" <<EOF
#!/usr/bin/env bash
set -euo pipefail
cd "$WORKTREE"
export KIMI_CODE_AGENT_SWARM_MAX_CONCURRENCY=2
export KIMI_SUBAGENT_TIMEOUT_MS=900000
echo "Worktree: \$PWD"
echo "Prompt: $PACKET/01_LOOP_1_AUDIT_AND_PLAN.txt"
echo
echo "Inside Kimi, run /usage first, then paste the Loop 1 prompt."
exec kimi --plan --add-dir "$PACKET"
EOF
chmod +x "$PACKET/start_loop_1.sh"

cat > "$PACKET/start_resume_auto.sh" <<EOF
#!/usr/bin/env bash
set -euo pipefail
cd "$WORKTREE"
export KIMI_CODE_AGENT_SWARM_MAX_CONCURRENCY=2
export KIMI_SUBAGENT_TIMEOUT_MS=900000
echo "Resume the audited session in Auto mode."
echo "Paste: $PACKET/02_LOOP_2_EXECUTE_GOAL.txt"
exec kimi --continue --auto --add-dir "$PACKET"
EOF
chmod +x "$PACKET/start_resume_auto.sh"

cat > "$PACKET/check_state.sh" <<EOF
#!/usr/bin/env bash
set -euo pipefail
cd "$WORKTREE"
echo "=== STATUS ==="
git status --short --branch
echo
echo "=== HEAD ==="
git rev-parse HEAD
echo
echo "=== RECENT COMMITS ==="
git log --oneline --decorate -12
echo
echo "=== READINESS HASH ==="
shasum -a 256 control/ONE_SHOT_READINESS.json
echo
echo "=== STAGED READINESS? ==="
git diff --cached --name-only -- control/ONE_SHOT_READINESS.json
EOF
chmod +x "$PACKET/check_state.sh"

cat > "$PACKET/MANIFEST.json" <<EOF
{
  "source_repository": "$SOURCE",
  "source_branch": "$EXPECTED_BRANCH",
  "starting_head": "$EXPECTED_HEAD",
  "protected_readiness_sha256": "$EXPECTED_READINESS_SHA",
  "worktree": "$WORKTREE",
  "worktree_branch": "$BRANCH",
  "swarm_max_concurrency": 2,
  "subagent_timeout_ms": 900000
}
EOF

echo
echo "KIMI CRE CAMPAIGN PREPARED"
echo
echo "Source repository unchanged:"
git -C "$SOURCE" status --short --branch
echo
echo "Isolated worktree:"
echo "$WORKTREE"
echo
echo "Campaign packet:"
echo "$PACKET"
echo
echo "Start Loop 1 with:"
echo "bash \"$PACKET/start_loop_1.sh\""
echo
echo "Inside Kimi, run /usage before pasting the Loop 1 prompt."
