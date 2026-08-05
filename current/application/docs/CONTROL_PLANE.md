# CRE Foundry Control Plane

The control plane is stored separately from analytical data.

## Operational database

`data/control/operations.sqlite3`

This database is intentionally excluded from Git.

## Responsibilities

- Source registration
- Source access state
- Persistent run history
- One-source-at-a-time locks
- Expired-lock recovery
- Schema-version history
- Schema-drift detection
- Source success and failure streaks
- Adaptive run cadence
- Next-due timestamps
- Error history

## Adaptive cadence policy

- A material change resets the source to base cadence.
- Every third consecutive no-change run slows the source by 1.5x.
- Failures double cadence, bounded by the configured maximum.
- One or two consecutive failures produce `degraded`.
- Three or more consecutive failures produce `unhealthy`.

This policy is transparent and replaceable. It is not machine learning.

## Governance

`access_state` and scheduling are separate.

A source may be healthy and due for metadata inspection while still
remaining prohibited from bulk acquisition.
