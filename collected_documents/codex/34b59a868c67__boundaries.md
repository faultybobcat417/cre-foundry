# ARCHITECTURE-001 Boundary Contract

## Scope

This document records the replaceable boundaries, workflow invariants, and
explicit non-claims of the ARCHITECTURE-001 product layer. It is the
human-readable companion to the machine-verifiable contract at
`artifacts/architecture/public_evaluator_contract.json` and the report at
`artifacts/evaluations/architecture.json`. The contract, the frozen schemas and
registries, the frozen public evaluator, and the 34 registered mutation
fixtures are the only authorities for what this layer proves.

Everything in this layer is synthetic, non-influencing, and local. It runs no
real route, touches no production system, enables no live issuance or outreach,
and claims no representative usability or field effectiveness.

## Replaceable module boundaries

The layer is a transactional modular monolith with replaceable ports. Exactly
one module is registered per role (`artifacts/architecture/module_registry.json`):

| role | replaceable interface | live default |
| --- | --- | --- |
| observation_port | Stage-1 observation input | disabled |
| candidate_port | candidate roster input | disabled |
| decision_port | MATH decision binding | disabled |
| issuance_port | prepared-route commitment | disabled |
| field_event_port | Stage-2 field-event input | disabled |
| outcome_port | Stage-3 outcome input | disabled |
| workflow_query_port | read-only workflow projection | disabled |

Each module must bind an input and output schema digest, an interface version,
an effect class, and an idempotency mode registered in the module registry, and
must set `live_enabled: false`. A module whose role, version, or schema binding
is unregistered, duplicated, or missing fails with `ARCH-MODULE-REGISTRY` or
`ARCH-MODULE-BINDING`. The evaluator never imports the implementation package;
`ARCH-EVALUATOR-COUPLING` fires on any actual import of
`cre_foundry.architecture`.

## Workflow state machine

Reachable states (`artifacts/architecture/state_machine_registry.json`):
`COLLECTING_STAGE1`, `STAGE1_FROZEN`, `ISSUE_READY`, `ISSUANCE_PREPARED`,
`ISSUED_INTERNAL`. Reserved live-only states (`DELIVERY_PENDING`, `DELIVERED`,
`RECALL_REQUIRED`) are unreachable in this layer and never terminal.

Allowed transitions:

- `APPEND_STAGE1` (COLLECTING_STAGE1 -> COLLECTING_STAGE1)
- `FREEZE_STAGE1` (COLLECTING_STAGE1 -> STAGE1_FROZEN)
- `DECIDE_ISSUE` (STAGE1_FROZEN -> ISSUE_READY)
- `DECIDE_ABSTAIN` (STAGE1_FROZEN -> ABSTAINED, terminal)
- `QUARANTINE_INVALID` (STAGE1_FROZEN -> QUARANTINED, terminal)
- `PREPARE_SYNTHETIC_ISSUANCE` (ISSUE_READY -> ISSUANCE_PREPARED)
- `COMMIT_SYNTHETIC_ISSUANCE` (ISSUANCE_PREPARED -> ISSUED_INTERNAL)
- `APPEND_STAGE2`, `APPEND_STAGE3` (ISSUED_INTERNAL -> ISSUED_INTERNAL)
- `VOID_UNDELIVERED` (ISSUED_INTERNAL -> VOIDED, terminal)
- `SUPERSEDE_WITH_NEW_GENERATION` (to SUPERSEDED, terminal, from the open states)

Sidecar commands `RECORD_REVIEW_ANNOTATION` and
`REQUEST_AUTHORITATIVE_EVIDENCE` apply without aggregate-state change. An
unknown command type is `REJECTED_WITHOUT_STATE_CHANGE`. A command that does not
match a legal transition, or that expects a stale or impossible aggregate
version, fails closed with `ARCH-ILLEGAL-TRANSITION`. A terminal state can
never be reopened and the aggregate version can never move backward; a
coordinated rehash that hides a semantic defect is caught by
`ARCH-RECONSTRUCTION-MISMATCH`.

## Command envelope and authority

Every command carries an idempotency key bound to contract version,
representative, route date, generation, operation, frozen Stage-1 snapshot, and
MATH decision digest. Every write-like command must present a current
authorization granting exactly its requested capability, scoped to
`SYNTHETIC_NON_INFLUENCING`, issued by a principal other than the requester
(`ARCH-AUTHORITY-ESCALATION`), and not revoked or expired. A command that asks
for a capability it is not authorized to hold — for example a `DECIDE` command
requesting `issuance:commit` (`ARCH-POLICY-BYPASS`) — is held
`HELD_UNAUTHORIZED` and produces a held-unauthorized outbox entry rather than
any effect.

## Idempotency, atomicity, and issuance uniqueness

Idempotency scope is aggregate key + command type + idempotency key; the retry
number never participates. Same key + same payload replays the canonical
original response byte-identically with no new event or effect. Same key +
different payload is rejected without state change (`ARCH-IDEMPOTENCY-CONFLICT`).
Two keys committing the same issuance slot conflict without a second route
(`ARCH-ISSUANCE-SLOT-CONFLICT`); a duplicated issuance ledger entry is
`ARCH-DUPLICATE-ISSUANCE`; `COMMIT_SYNTHETIC_ISSUANCE` with no prior
`PREPARE_SYNTHETIC_ISSUANCE` is `ARCH-COMMIT-WITHOUT-PREPARE`.

The atomic commit set is the transition event, the aggregate projection, the
immutable route artifact, the issuance ledger entry, the idempotency response,
and the held-unauthorized outbox entry. The registered pre-commit fault points
(`BEFORE_EVENT_APPEND` ... `AFTER_OUTBOX_BEFORE_COMMIT`) leave no state,
issuance, idempotency, outbox, or external effect; ambiguous partial state is
forbidden and any unregistered fault point is
`ARCH-PARTIAL-FAILURE-AMBIGUOUS`. A post-commit retry returns the already
committed canonical response with exactly one issuance.

## Exactly ten or abstain

An ISSUE decision selects exactly ten distinct physical locations from the MATH
decision. A selection of nine or eleven is `ARCH-EXACT-TEN`; a duplicated
physical location is `ARCH-DUPLICATE-LOCATION`; an unknown or drifted stop is
`ARCH-PROTECTION-BYPASS`; a claimed route or selection that differs from the
MATH decision is `ARCH-DECISION-MISMATCH`. When MATH cannot form ten, the only
legal outcome is `ABSTAIN_NO_VALID_TEN` with one of the registered reasons.
Abstention must not carry a route, event, outbox, or effect
(`ARCH-ABSTAIN-HAS-EFFECTS`) and must expose its reason
(`ARCH-ABSTAIN-REASON-HIDDEN`). An invalid problem must surface a structured
ERROR with a visible diagnostic (`ARCH-ERROR-HIDDEN`).

## Stage isolation and manual review

Stage 1 is frozen by digest and is immutable: Stage 2 and Stage 3 can never
rewrite it (`ARCH-STAGE1-REWRITE`), and a stage-3 binding to a field event that
Stage 2 never produced is `ARCH-DOWNSTREAM-BINDING`. Manual review may only
annotate or request evidence; it can never change Stage 1 selection, rank, or
protection gates (`ARCH-MANUAL-BYPASS`). Journal events form an append-only
hash chain (`ARCH-JOURNAL-CHAIN`); lineage must bind every event to its command
and every downstream artifact to its producer (`ARCH-LINEAGE-BINDING`). The
synthetic reviewer role grants no real authority.

## Accessibility metadata

The workflow exposes a programmatic accessibility projection: ordered actions,
focus and reading order, an ordered status disclosure with reason code,
evidence references, and safe next actions, plus `location_rows`. Accessible
action identifiers must be unique (`ARCH-ACCESSIBLE-ACTION`); focus/reading
association must be deterministic (`ARCH-ACCESSIBLE-STATUS`); the status must
not be visual-only (`ARCH-ACCESSIBLE-NONVISUAL`); abstention and error statuses
must disclose their reason or diagnostic (`ARCH-STATUS-DISCLOSURE`). The
projection explicitly lists what it does not establish (WCAG conformance,
screen-reader performance, representative usability, satisfaction, adoption).

## Live denial and claims ceiling

`live_enabled` is false by default and any request for live action is denied
(`ARCH-LIVE-DENIAL`). External effects are never recorded
(`ARCH-EXTERNAL-EFFECT`); delivery is `HELD_UNAUTHORIZED` by design. The claim
ceiling is the frozen contract ceiling and any receipt that weakens or overstates
it fails (`ARCH-CLAIM-CEILING`). The receipt binds command stream, event stream,
aggregate projection, idempotency, issuance ledger, outbox, effect ledger,
responses, and accessibility projection digests and is itself self-hashed.

## Non-claims

This layer does not claim representative usability, WCAG or assistive-technology
performance or certification, production durability or atomicity, operational
reliability or error rate, security certification, route feasibility,
deployment readiness, live authority, adoption, incremental F9 lift, or
commercial value. Live permissions remain disabled and all relevant gates stay
open pending explicit authority.

## Verification

`scripts/validate_architecture.py` regenerates the canonical subject
deterministically (twice, byte-identical), judges it with the frozen public
evaluator, then regenerates each of the 34 registered mutation subjects from
its embedded recipe and requires the registered diagnostic in every case, with
no missing or extra fixture references. `artifacts/evaluations/architecture.json`
records the result at public proof level 4.
