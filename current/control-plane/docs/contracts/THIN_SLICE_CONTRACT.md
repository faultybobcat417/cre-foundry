# CONTRACT-001 thin-slice spine

This contract demonstrates a deterministic synthetic interface from source-native evidence to an exact-ten-or-abstain decision. It does not demonstrate source access, real entity truth, protected-account completeness, calibrated value, travel feasibility, or live issuance authority.

## Boundary and sequence

1. A `THIN_SLICE_OBSERVATION` retains source-native bytes, native key, provenance, distinct clocks, and normalized aliases. Its only identity claim is `SOURCE_RECORD_ONLY`.
2. A `THIN_SLICE_CANDIDATE` adds an explicit `SYNTHETIC_IDENTITY_ASSERTION`. The physical-location ID is recomputed from the versioned normalized address-and-unit basis; no brand, organization, licence, property, or other grain may substitute for it.
3. Protection tokens are the complete sorted alias projection. Incomplete bundles or extraction produce `UNKNOWN`; an intersection produces `PROTECTED`; only complete non-intersection produces `CLEAR`.
4. Candidate availability is the latest load-bearing observation, identity, gate, protection, or score clock. Observation, candidate, and MATH snapshot must bind the same Stage-1 cutoff, and availability must not exceed it. A known publication time must precede retrieval and the cutoff. Event and publisher-effective clocks remain semantically distinct metadata and are not treated as evidence-availability clocks.
5. Candidate documents project exactly into the MATH-001 problem. The candidate snapshot digest becomes the MATH snapshot digest, and the decision must echo the snapshot and policy hashes.
6. The replay receipt binds the source snapshot, candidate snapshot, problem, decision, policy, selected candidates, and result.

The focal observation proves the one-observation traversal requirement. A bounded batch of ten focal-equivalent synthetic observations proves the exact-ten `ISSUE` path. A one-candidate batch correctly abstains.

## Canonicalization and versions

`SORTED_KEYS_INTEGER_JSON_V1` means UTF-8 JSON with sorted object keys, compact comma/colon separators, no NaN or infinity, and integers for numeric contract values. Arrays with set semantics are sorted before hashing. Digests are lowercase SHA-256 hex.

Only the exact `1.0.0` observation-to-candidate-to-MATH transition is supported. An unregistered version fails before ordinary schema dispatch. Migration requires a separately reviewed contract version.

## Public verification

Run:

```bash
python scripts/validate_contract_spine.py
python -m unittest evals.public.test_contract_spine -v
```

The validator rebuilds the synthetic spine, checks it with an independently implemented semantic evaluator, compares its replay receipt with the committed artifact, and executes the public tests. Five declarative mutation fixtures must each produce their registered diagnostic.

## External gates

Real operation remains blocked by `approved_source_envelope`, `GATE-PUBLICATION-HISTORY-001`, `GATE-ENTITY-TRUTH-001`, `protected_account_bundle`, `representative_origins_capacity_specialties`, `approved_route_matrix`, `firm_economics_services_territories`, `GATE-OUTCOME-LABELS-MATURITY-001`, and `GATE-FULL-EXTERNAL-EVIDENCE-001`.
