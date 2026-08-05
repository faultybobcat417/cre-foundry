# Codex Milestone Acceptance Plan v0.12

Machine authority:
`../../contracts/codex_milestone_acceptance_plan.json`.

## Rule

Codex receives one bounded milestone at a time. A task tracker is the control
plane; each task runs in an isolated worktree and must return its own evidence.

## Milestones

| ID | Milestone | Cannot exit until |
|---|---|---|
| M00 | Repository bootstrap and truth inventory | actual commands, dependencies, capabilities and blockers are recorded |
| M01 | Contract and generated-type foundation | schemas and OpenAPI/AsyncAPI-generated types validate |
| M02 | Immutable acquisition and source health | raw replay, count reconciliation and failure semantics pass |
| M03 | Normalization and lineage | primitives reproduce from raw bytes and lineage closes |
| M04 | Entity graph and universe | identity/protection audits pass |
| M05 | Historical label and feature factory | point-in-time joins, maturity and leakage tests pass |
| M06 | Baselines, models and calibration | baseline, replay and model registry evidence pass |
| M07 | Economic ranking and composition | value, uncertainty, diversity and abstention pass |
| M08 | Spatial routing | exact-ten, reserve and route-provider replay pass |
| M09 | Field and outcomes | information boundaries and F9 evidence pass |
| M10 | Governance, telemetry and security | authorization, emergency stop, lineage and incident tests pass |
| M11 | Integrated shadow pilot | end-to-end shadow SLOs pass |
| M12 | Randomized field pilot | preregistered empirical experiment operates |
| M13 | Production promotion | signed authority, empirical proof and rollback pass |

## Worktree and reviewer rules

- one writer per worktree;
- builder cannot modify evaluator or protected authority;
- independent sweeper reviews the diff and evidence;
- failures produce a diagnosis and retained artifact;
- unresolved external information becomes a named gate;
- milestone closure is atomic and hash-referenced.

## Parallelism

Parallel work is allowed only when tasks have:

- non-overlapping writable roots;
- stable shared contracts;
- no unresolved ordering dependency;
- deterministic integration tests.

Integration owns the merge order and reruns the full system proof.
