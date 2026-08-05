# ECONOMICS-001 material economics engine implementation

This document describes the material implementation of the ECONOMICS-001
synthetic risk-adjusted expected net commercial value (ECV), cost, downside,
and sensitivity machinery in `src/cre_foundry/economics/`. It implements the
semantics the frozen `contracts/commercial_economics.schema.json` and the frozen
independent evaluator (`scripts/validate_economics_ecv.py`) demand, but it is an
independent code path: it never imports the evaluator or any economics-adjacent
package. Two independent implementations agreeing byte-for-byte on the canonical
subject, and diagnostic-for-diagnostic on every registered mutation, is the proof
that both are correct.

This material layer establishes no firm-authoritative economics, no realized
commercial value, and no live decision authority. Proof level is 5 (synthetic,
replayable, non-influencing) for the ECV engine surface.

## Package layout

- `src/cre_foundry/economics/__init__.py` — package intent and boundaries.
- `src/cre_foundry/economics/engine.py` — declarative authoritative-economics
  policy seed, canonical renderer, risk-adjusted expected-net-value, downside,
  sensitivity and fallback machinery, and the material semantic checks.
- `contracts/economic_engine.schema.json` — Draft 2020-12 input contract for the
  versioned authoritative economics policy the engine accepts.

## Canonicalization

`UTF8_CANONICAL_JSON_SORTED_KEYS`: UTF-8 JSON, sorted object keys, compact
comma/colon separators, integer numbers, no NaN/infinity. The canonical subject
is `COMMERCIAL_ECONOMICS_MODEL` (schema version 1.0.0, execution scope
`SYNTHETIC_NON_INFLUENCING`, proof level 5, live permissions false). These
conventions are shared by both independent implementations.

## Material renderer

`engine.render_subject()` walks a compact declarative authoritative-economics
policy seed (`_policy_seed`) into the canonical subject with explicit:

- services and territories (one representative territory),
- commission rate and basis,
- cost line items (material, travel),
- conversion mean and variance (a synthetic beta distribution),
- downside metric (p10 net value) and threshold,
- a fallback policy ("abstain when p10 net value is below threshold"),
- claim status `MODELED` and the level-9 realized-value claim ceiling.

The material render is byte-identical to the frozen evaluator's clean subject.

## Economic machinery

- `expected_net_value(subject)` — expected gross commission, expected net value,
  downside net value, total cost, and downside conversion, evaluated across
  conversion uncertainty under a synthetic reference volume.
- `sensitivity(subject)` — local sensitivity of expected net value to conversion
  mean, commission rate, and total cost (the cost partial is exactly -1).
- `downside_fallback(subject)` — whether the downside net value breaches the
  downside threshold and the resulting `MODELED`/`ABSTAIN` decision.

These are deterministic, symbolic, and never invent firm inputs; a synthetic
reference volume and a display-NZ distribution offset are documented constants.

## Material checks

`engine.material_checks(subject)` emits the frozen registered diagnostics and
material assurance codes:

- `ECONOMICS-OMITTED-COSTS` — costs removed.
- `ECONOMICS-MODELED-AS-REALIZED` — claim status changed from `MODELED`.
- `ECONOMICS-INVENTED-INPUTS` — placeholder/invented service or territory.
- `ECONOMICS-DOWNSIDE-COLLAPSED` — downside metric or threshold missing.
- `ECONOMICS-UNCERTAINTY-IGNORED` — zero conversion variance.
- `ECONOMICS-REALIZED-CEILING` — claim status set to realized.
- `ECONOMICS-FALLBACK-VIOLATED` — a claimed usable value while the fallback says
  abstain.

The canonical clean subject produces no diagnostics from either implementation.

## Verification

- `scripts/validate_economics_contracts.py` — S-2 house cross-check
  (determinism, frozen byte-agreement, schema conformance, frozen acceptance,
  known-bad replay on both implementations, machinery determinism, source
  independence; exit 0/1).
- `evals/public/test_economics_contracts.py` — 6 builder-side tests.
- `scripts/validate_economics_ecv.py` — the frozen gate evaluator
  (`PASS`, exit 0).

## Boundaries / claims not established

Realized commercial value, firm-authoritative economics, firm cost data,
calibrated real uncertainty, commercial lift, production/deployment readiness,
field effectiveness, scaled-evaluator independence, and hidden-holdout
performance are all legally/engine-not-established and remain externally gated.