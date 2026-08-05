# CRE Codex Project OS v2.2

This is the final pre-build launch system.

It is designed to maximize the probability that Codex produces the intended
CRE Tip Sheet system without drowning the agent in historical planning,
forcing weak implementation choices, or losing project state across sessions.

## Recommended launch sequence

1. Provide the actual `cre-foundry` repository or its current archive.
2. Upload `CRE_Codex_Launch_Kernel_v2.2.zip`.
3. Upload `CRE_Codex_Reference_Vault_v2.2.zip`.
4. Paste `FINAL_CODEX_LAUNCH_PROMPT_v2.2.md`.
5. Let Codex execute `BOOTSTRAP-001`.

## What is authoritative at startup

1. `AGENTS.md`
2. `kernel/MISSION.md`
3. `kernel/INVARIANTS.json`
4. `control/WORKFLOW.md`
5. `control/CURRENT_STATE.json`
6. `control/CURRENT_TASK.json`
7. generated current-task context packet
8. task-selected reference-vault files
9. historical planning only when resolving provenance or contradiction

## What “one launch” means

One initiation establishes a resumable project control plane. Codex may
execute multiple bounded tasks in one session where the product supports it.
When a session, approval, or platform boundary stops execution, the project
resumes from repository artifacts and state—not from chat memory.

For truly continuous multi-task operation, use the tracker-backed orchestration
mode described in `control/EXECUTION_MODES.md`.

## Core principle

Give Codex the destination, invariants, current task, evaluator, tools, and
state. Let it discover and prove the strongest route.

## New v2.2 boundary

Before building, Codex separates derivable/public research from access-dependent, human-authoritative, empirical-only, and externally hidden information. The mathematical constitution and claim-proof register prevent simulated or observational work from being promoted into causal/commercial claims.

## Level-10 gate

Run `python scripts/run_level10_campaign.py`. The release is pre-Codex ready only when all 24 design/evaluator domains score 10 and the package still reports empirical claims as unproven.
