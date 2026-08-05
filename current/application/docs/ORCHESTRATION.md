# Parameterized Orchestration

Run profiles live in:

`config/run_profiles/`

The initial profile is:

`metadata_watch.yaml`

## Supported execution modes

Plan only:

`cre-foundry run profile --profile metadata_watch --dry-run`

Force plan only:

`cre-foundry run profile --profile metadata_watch --force --dry-run`

Execute only due sources:

`cre-foundry run profile --profile metadata_watch`

Force execution:

`cre-foundry run profile --profile metadata_watch --force`

## Separation of responsibilities

- Run profiles define intent and parameters.
- The orchestration engine selects due sources.
- Prefect provides task retries and flow observability.
- The control plane remains the source of truth for locks,
  run history, source health and next-due timestamps.
- launchd scheduling is not enabled until local execution passes.
