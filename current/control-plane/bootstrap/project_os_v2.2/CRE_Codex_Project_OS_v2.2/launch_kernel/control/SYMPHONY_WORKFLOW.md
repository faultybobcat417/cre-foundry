---
tracker:
  kind: generic_issue_tracker
  active_states: [Ready, In Progress, Rework]
  terminal_states: [Done, Cancelled, Rejected]
orchestration:
  poll_seconds: 30
  max_concurrency: 4
  retry_backoff_seconds: [60, 300, 900, 3600]
  one_workspace_per_issue: true
  preserve_workspaces_across_retries: true
codex:
  command: detected_by_capability_probe
  approval_policy: environment_managed
  sandbox: workspace_scoped
---

# CRE Foundry Orchestration Workflow

For each eligible unblocked issue:

1. create or reuse its isolated workspace;
2. read root and nested `AGENTS.md`;
3. validate repository state and issue contract;
4. compile the issue-specific context packet;
5. execute the bounded task;
6. stream structured progress and preserve the session/thread ID;
7. run the task evaluator and independent review;
8. update the issue with artifacts, findings, gates, and next actions;
9. transition to Rework, Review, Blocked, or Done according to evidence;
10. create follow-up issues for out-of-scope findings.

Do not dispatch blocked tasks. Stop active work when the issue becomes
ineligible. Recover transient crashes with bounded backoff. Preserve structured
logs sufficient to diagnose every run.
