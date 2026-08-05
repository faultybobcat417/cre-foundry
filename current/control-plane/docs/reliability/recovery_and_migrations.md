# CRE Foundry representative route-day replay and recovery plan

Document kind: `REPLAY_RECOVERY_PLAN`
Schema version: `1.0.0`
Execution scope: `SYNTHETIC_NON_INFLUENCING`
Judged by: `scripts/validate_replay_recovery.py`

## 1. Replay and idempotency

- Every issuance and outreach effect carries an idempotency key. Retrying after
  an ambiguous failure must not duplicate a route issuance or an outreach
  effect.
- Replay receipts bind the immutable Stage-1 decision, the emitted route
  manifest, and the set of effects. A mismatched or missing receipt fails
  closed.

## 2. Crash, restore, and compatibility

- Snapshots and ledger records are retained and readable across schema
  changes. A schema change never makes a retained historical snapshot
  unreadable.
- Forward and backward migrations are explicit and reversible; rollback paths
  are defined for each material migration.
- Partial or corrupted state restores to the last consistent checkpoint rather
  than manufacturing a partial route.

## 3. Claim ceiling

This plan establishes replay, idempotency, crash, restore, compatibility,
forward/backward migration, and rollback mechanics only. It establishes no real
availability, durability, or production recovery claim.

## 4. Required mutations

The evaluator runs the registered mutations against this plan:

- `duplicate-effect`: retry after an ambiguous failure duplicates route
  issuance or outreach.
- `old-snapshot-unreadable`: a schema change makes a retained historical
  snapshot unreadable.

Both must be detected and rejected.
