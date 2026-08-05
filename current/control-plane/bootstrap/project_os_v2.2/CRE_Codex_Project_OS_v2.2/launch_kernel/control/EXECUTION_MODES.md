# Execution Modes

## Mode A — Interactive Codex / Goal

Best for the initial ambiguous bootstrap and high-judgment decisions.

- upload kernel and vault;
- connect the real repository;
- paste the launch prompt;
- allow Codex to execute multiple bounded steps in the durable thread;
- checkpoint whenever the product requires approval, pauses, or ends the turn;
- resume from `CURRENT_STATE.json` and artifacts.

This mode can run long tasks, but an interactive thread is not itself an
always-on multi-issue scheduler.

## Mode B — Headless resumable CLI

Best after repository commands and task contracts are known.

- probe the installed CLI first;
- use `codex exec` JSONL and output capture only when supported;
- preserve thread/session identifiers;
- use `codex exec resume` when supported;
- validate final task output against the task-result schema;
- retry only transient failures;
- never use dangerous approval/sandbox bypass flags.

The included launcher generates commands from the capability manifest rather
than assuming a specific Codex release.

## Mode C — Tracker-backed orchestration

Best for continuous multi-task execution after the task DAG is stable.

- issue tracker is the control plane;
- one issue maps to one isolated workspace;
- only unblocked tasks are dispatched;
- repository-owned `WORKFLOW.md` supplies execution policy;
- retries, reconciliation, observability, and stop/restart behavior are explicit;
- agents may create follow-up issues;
- successful runs may end at review/handoff rather than falsely marking Done.

Use a Symphony-compatible orchestrator or implement the local specification in
`control/SYMPHONY_WORKFLOW.md`.

## Recommended progression

Start in Mode A for BOOTSTRAP-001. Move repetitive bounded work to Mode B.
Move parallel, continuous task execution to Mode C after evaluator and task
quality are proven.
