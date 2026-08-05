# Brampton Verification Event Ledger

This subsystem stores analyst verification activity separately from the
source-derived permit, directory, reconciliation and task-plan tables.

## Durable ledger

Events are appended to the control-plane SQLite database:

`data/control/operations.sqlite3`

The `verification_events` table is append-only. SQLite triggers reject update
and delete operations.

Each task maintains a chained SHA-256 event history using:

- the previous event identifier;
- the previous chain hash;
- a canonical JSON representation of the new event.

## Allowed transitions

Supported events:

- `task_started`
- `evidence_added`
- `task_passed`
- `task_failed`
- `task_reset`

A task may pass or fail only after it is in progress and has at least one
evidence event since its latest reset.

A completed task can only return to `not_started` through an explicit reset
event with reviewer notes.

## Projection

The append-only ledger is projected into DuckDB control tables:

- `control.brampton_verification_events`
- `control.brampton_verification_task_state`
- `control.brampton_verification_workflow_state`
- `control.brampton_verification_active_queue`
- `control.brampton_verification_state_summary`

The projection is fully rebuildable from the task plan and ledger.

## Safety

Passing all verification tasks does not authorize outreach.

Every workflow retains:

- `outreach_authorization_required = true`
- `opportunity_ranked = false`
- `outreach_eligible = false`
- `operating_mode = 'shadow'`
