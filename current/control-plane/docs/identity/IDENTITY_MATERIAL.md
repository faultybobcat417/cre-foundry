# IDENTITY-001 material identity graph implementation

This document describes the material implementation of the IDENTITY-001
synthetic temporal identity and fail-closed protection primitives in
`src/cre_foundry/identity/`. It implements the semantics the frozen
`contracts/temporal_identity.schema.json` and the frozen independent evaluator
(`evals/public/temporal_identity_evaluator.py`) demand, but it is an independent
code path: it never imports the evaluator or any identity-adjacent package. Two
independent implementations agreeing byte-for-byte on the canonical subject, and
diagnostic-for-diagnostic on every registered mutation, is the proof that both
are correct.

This material layer establishes no real entity truth, no real protected-account
completeness, and no live eligibility. Proof level is 4 (synthetic, replayable,
non-influencing).

## Package layout

- `src/cre_foundry/identity/__init__.py` — package intent and boundaries.
- `src/cre_foundry/identity/graph.py` — declarative seed, canonical renderer,
  digest/lineage/protection binding, and the material semantic checks.

## Canonicalization

`UTF8_CANONICAL_JSON_SORTED_KEYS`: UTF-8 JSON, sorted object keys, compact
comma/colon separators, integer numbers, no NaN/infinity. Set-semantics arrays
are sorted before hashing; ordered arrays (rank, lineage journal, protection
expansion path order) keep semantic order. Every `*_digest` is the canonical
digest of its own record with that digest field removed. The subject digest
removes the top-level `subject_sha256` and the replay-receipt `subject_sha256`
before hashing. Digests are lowercase SHA-256 hex. These conventions are the
frozen contract and are intentionally shared by both independent
implementations.

## Material renderer

`graph.render_subject()` walks a compact declarative seed:

- `GRAIN_CATALOG` — 21 typed grains (legal, parent, subsidiary, operating
  business, brand, franchise system, franchisee, establishment, physical
  location, address, building, unit, parcel, property, owner, occupier, two
  protected accounts, representative relationship). Entity grains remain
  distinct; an address or name alone is never identity.
- `ASSERTION_CATALOG` — observation assertions.
- `LINK_CATALOG` — 20 typed links (owns/operates/brand/sub/parent/franchise/
  located-at/part-of/occupies/alias/protected-link).
- `EXPANSION_CATALOG` — three protected expansion paths (depth 1).
- the protection bundle seed (complete, authoritative, COMPLETE extraction, no
  former addresses).

The renderer binds:

1. record digests (`_rebuild_record_digests`),
2. protection snapshots and decision digest (`_rebuild_protection_digests`),
3. lineage nodes/edges and the journal chain (`_rebuild_lineage`),
4. the subject and replay receipt binding (`_subject_digest`).

`graph.rebind_digests(subject, preserve_predecessors=False)` re-binds a mutated
subject so only an intended semantic diagnostic fires; it never weakens the
frozen evaluator, which recomputes the same conventions independently. A
mutation that rewrites prior history with `preserve_predecessors=True` keeps
stale correction predecessors detectable.

## Material semantic checks

`graph.material_checks(subject)` independently re-derives the identity semantics
and emits the frozen registered diagnostic codes:

- `check_suite_collapse` — two establishments/operating businesses colliding
  into one unit in an overlapping interval (registered `suite-collapse`).
- `check_protected_alias_clear` — a `CLEAR` decision that silently omits a
  required protected alias, linked location, or former-address coverage
  (registered `protected-alias-clear`).
- `check_grain_collapse` — grain id/type mismatch, duplicate id with differing
  type, or link endpoints not present as grains.
- `check_address_as_identity` — an address/location grain used as an identity
  link source.
- `check_relocation_rewrite` — relocation must be append-only: link count must
  equal relocations + 1 and prior links must close before the next opens.
- `check_closure_temporal` — permanent closure is open-ended; temporary closure
  must carry an `effective_to`.
- `check_alias_supersede` — a rename/legal-name change must be covered by an
  alias link.
- `check_alternatives_blocked` — unresolved ambiguous/unknown alternatives block
  eligibility; conflicting alternatives block outright.
- `check_unit_separation` — distinct units sharing identical evidence in an
  overlapping interval.
- `check_multi_unit_establishment` — one establishment located at units that
  resolve to more than one physical location.
- `check_duplicate_active_truth` — two active same-type grains with identical
  overlapping evidence.

These checks are the material implementation of the identity primitives the task
requires (temporal, relocation, closure, unit, franchise-grain preservation,
alternative/ambiguity/conflict, fail-closed protection). They are independent of
the evaluator and used only to cross-check it.

## Verification

```bash
uv run --python 3.12 python scripts/validate_identity_contracts.py
uv run --python 3.12 python -m unittest evals.public.test_identity_contracts -v
uv run --python 3.12 python scripts/validate_temporal_identity.py
uv run --python 3.12 python -m unittest evals.public.test_temporal_identity -v
```

The house validator `scripts/validate_identity_contracts.py`:

1. verifies the material graph schema
   (`contracts/synthetic_identity_graph.schema.json`) is a valid Draft 2020-12
   schema;
2. renders the material subject deterministically;
3. constrains the material subject to the frozen subject schema (zero errors);
4. requires the frozen independent evaluator to PASS the material subject with
   zero diagnostics;
5. requires the material checks to agree with the evaluator's reconstruction
   (`CLEAR`);
6. replays every registered known-bad fixture onto the material subject and
   requires both the frozen evaluator and the material checks to detect the
   exact registered diagnostic;
7. binds the subject/canonical digest to the evaluator's reconstruction digest.

The result is persisted to `artifacts/evaluations/identity_contracts.json`.

## Input contract

`contracts/synthetic_identity_graph.schema.json` is the material layer's own
strict Draft 2020-12 schema for the graph/seed it consumes. Records carry no
digest fields; binding is the renderer's job. This schema is disabled into the
same strict shape as the frozen subject schema but stays declarative.

## Boundaries

Material output never rewrites Stage-1 spine documents. `exact_ten_or_abstain`
remains authoritative to the MATH decision; this layer only enriches identity
semantics and protection fail-closed behavior. External gates for authorized
entity truth (`GATE-ENTITY-TRUTH-001`), authorized protected bundles
(`protected_account_bundle`), adjudication, empirical validation, sealed
evaluator custody, and hidden holdouts remain OPEN_BLOCKING and are not claimed.