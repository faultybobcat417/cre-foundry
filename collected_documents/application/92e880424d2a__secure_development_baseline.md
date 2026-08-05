# Secure Development Baseline

## Current normative baseline

- NIST SSDF 1.1 is the current final secure-development baseline.
- NIST SSDF 1.2 is tracked as draft guidance only.

## Future verification baselines

- OWASP ASVS 5.0.0 for the application layer.
- SLSA 1.2 for build and release provenance.
- CycloneDX 1.7 for software inventory.
- OpenSSF Scorecard for repository posture.

## Mandatory engineering properties

- Fail closed on unknown or stale inputs.
- Require attributable human authorization.
- Preserve immutable raw evidence and lineage.
- Use deterministic and reproducible transformations.
- Reject ambiguous serialization.
- Use atomic writes and rehearse recovery.
- Lock and inventory dependencies.
- Separate readiness from execution authorization.
- Preserve protected-account and exclusion integrity.
- Prohibit future-information leakage.
- Collect real outcomes with censoring.
- Require independent verification before production.

## Claims boundary

This repository records engineering evidence. It does not currently claim formal compliance, certification, production readiness or proven ROI.
