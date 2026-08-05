# CRE Foundry representative product workflow — system document

- **Scope:** deterministic synthetic architecture and representative product
  workflow surface only. No usability, accessibility conformance, production,
  security, route, deployment, live-authority, adoption, F9-lift, or commercial
  value claim is established.
- **Decision invariant:** issue exactly ten primary physical locations per
  representative route-day or `ABSTAIN_NO_VALID_TEN`. The product surface
  projects `ISSUE` with exactly ten unique physical location IDs, or `ABSTAIN`
  with a non-empty reason and zero selections.
- **Route-day unit:** every generation is keyed by
  `(execution_scope, representative_id, route_date, generation)`; the product
  projection preserves that aggregate key and route-day identity.
- **Stage isolation:** Stage-1 observation/candidate/decision material is
  frozen before issuance; Stage-2 (field events) and Stage-3 (outcomes) are
  append-only consumers that never rewrite Stage 1.
- **Protection:** protected-account and protected-stop tolerance is zero.
  A protected or unknown/drifted stop may never be issued; false clears are
  rejected (`zero_false_clear` is always true).
- **Lineage:** the projection binds the frozen canonical run digest,
  command-stream, event-stream, and final-receipt digests and requires
  completeness.
- **Issuance:** issuance is single-slot and idempotent; retrying never creates
  a duplicate external effect (`external_effect_occurred` is always false and
  `unique_slot_single_issuance` is always true).
- **Live defaults:** live workflow and live issuance are disabled by default
  and by request; the projection always reports them false.
- **Accessibility:** only synthetic programmatic semantics
  (`SYNTHETIC_PROGRAMMATIC_SEMANTICS_ONLY`) are claimed; structured status,
  reason codes, safe next actions, and error visibility are exposed.
- **External gates:** the five named external gates remain `OPEN_BLOCKING`
  (manual-review authority, live-workflow authority, accessibility empirical
  validation, representative usability, production deployment).
- **Authority:** the frozen architecture evaluator contract and canonical run
  remain the authority for the product projection; the product validator
  re-runs the architecture validator unweakened.
