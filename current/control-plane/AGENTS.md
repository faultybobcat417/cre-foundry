# CRE Foundry repository map

The durable mission, invariants, authority, workflow, proof policy, and task
schema live in:

`bootstrap/project_os_v2.2/CRE_Codex_Project_OS_v2.2/launch_kernel/`

Start each run there with the commands in its `AGENTS.md`. The application
repository root is this directory.

## Repository control plane

- `control/`: current state, task graph, gates, and decisions.
- `control/AUTONOMOUS_FRONTIER_CONTRACT.json`: machine-verifiable completion and external-frontier gates. Narrative completion claims have no authority over its evaluator.
- `tasks/`: issue-quality task packets.
- `artifacts/`: evidence and schema-conformant task results.
- `contracts/`: public machine contracts.
- `evals/public/`: builder-visible evaluators and synthetic fixtures.
- `evals/known_bad/`: mutation cases that public evaluators must reject.
- `evals/reference/`: non-production reference implementations used only to
  self-test evaluator behavior.
- `src/`: application code after its evaluator is defined.

## Hard boundaries

- Issue exactly ten primary physical locations or
  `ABSTAIN_NO_VALID_TEN`.
- Stage-2/3 information never rewrites Stage 1.
- Protected-account false-clear tolerance is zero.
- A builder may not change the evaluator judging its task.
- `evals/public/` is not a sealed or hidden evaluator.
- Sealed cases must be held in a separate custodian-owned repository outside
  this worktree. True hidden holdouts require an additional external owner.
- Live permissions remain disabled unless explicit authority closes the
  relevant named gates.

Use one writer per worktree. Run independent review before integration and
persist every task result against the Project OS task-result schema.

Run `uv run --python 3.12 python scripts/evaluate_autonomous_frontier.py` when
orienting or checkpointing. `FAIL` means autonomous work remains;
`BLOCKED_EXTERNAL` is terminal only when the evaluator proves every autonomous
prerequisite and the task graph has no executable work.
