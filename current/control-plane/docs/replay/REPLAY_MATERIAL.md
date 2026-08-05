# REPLAY-001 material recovery layer

This synthetic, non-influencing layer implements deterministic replay,
idempotent effect handling, bounded crash recovery, snapshot compatibility,
migration safety, backup and restore verification, and rollback
verification.

The same canonical input always creates the same byte-stable output.
Repeated execution under the same idempotency key returns the prior effect
rather than creating a duplicate. Reusing an idempotency key with a
different payload fails closed.

Prepared journal state is recovered without accepting partial state.
Retained snapshots must remain readable under an explicitly supported
schema version. Migration requires compatibility and a defined rollback.
Restore identities must match the bound backup, and rollback must restore
the prior accepted version.

The material implementation is independent from both the frozen
REPLAY-001 evaluator and the legacy replay-recovery evaluator. Live
permissions and external effects remain disabled.

Public proof level 4 establishes synthetic contract conformance only. It
does not establish production durability, availability, disaster recovery,
recovery time, persistence correctness, migration safety, or deployment
readiness.
