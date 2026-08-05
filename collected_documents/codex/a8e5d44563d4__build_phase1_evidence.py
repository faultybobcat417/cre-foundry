"""Generate the Phase-1 domain evidence artifacts deterministically.

Each artifact records the domain's registered mutation results (from the
validators' own pure diagnostic predicates) plus the subject_hashes the
validator re-verifies.  Run once from a committed tree and commit the generated
artifacts.
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts._frontier_domain_common import file_sha256, strict_load  # noqa: PLC0415


def build_data_history() -> dict:
    from scripts.validate_data_history import (
        SUBJECT_HASHES as SUB, build_subject, run_one, SCHEMA,
    )
    fixtures = sorted((ROOT / "evals/known_bad/frontier").glob("data_*.json"))
    return _evidence(
        "DATA-HISTORY-001-PUBLIC-EVIDENCE", "data-history-public-v1", 5,
        SUB, fixtures, run_one,
        "Synthetic immutable source snapshot, bitemporal reconstruction, truncation, hash-drift, correction, tombstone, and future-leakage mutation report only.",
        "Synthetic snapshot/reconstruction mechanics; no real source bytes, availability, or production claim.",
        "DATA-HISTORY-001",
    )


def build_economics() -> dict:
    from scripts.validate_economics_ecv import (
        SUBJECT_HASHES as SUB, build_subject, run_one,
    )
    fixtures = sorted((ROOT / "evals/known_bad/frontier").glob("economics_*.json"))
    return _evidence(
        "ECONOMICS-ECV-001-PUBLIC-EVIDENCE", "economics-ecv-public-v1", 5,
        SUB, fixtures, run_one,
        "Synthetic symbolic ECV, uncertainty, cost, downside, and fallback-policy sensitivity report only.",
        "Synthetic economics mechanics; no firm-authoritative inputs, realized value, or commercial claim.",
        "ECONOMICS-ECV-001",
    )


def build_routing() -> dict:
    from scripts.validate_routing_feasibility import (
        SUBJECT_HASHES as SUB, build_subject, run_one,
    )
    fixtures = sorted((ROOT / "evals/known_bad/frontier").glob("routing_*.json"))
    return _evidence(
        "ROUTING-FEASIBILITY-001-PUBLIC-EVIDENCE", "routing-public-v1", 5,
        SUB, fixtures, run_one,
        "Synthetic reference matrix, service time, reserve, stale/asymmetric, feasibility, and substitution mutation report only.",
        "Synthetic route-time feasibility mechanics; no real provider matrix, measured service time, or operational claim.",
        "ROUTING-FEASIBILITY-001",
    )


def build_security() -> dict:
    from scripts.validate_security_privacy import (
        SUBJECT_HASHES as SUB, build_subject, run_one,
    )
    fixtures = sorted((ROOT / "evals/known_bad/frontier").glob("security_*.json"))
    return _evidence(
        "SECURITY-PRIVACY-001-PUBLIC-EVIDENCE", "security-privacy-public-v1", 4,
        SUB, fixtures, run_one,
        "Synthetic secret, PII-log, authorization, external-write, prompt-injection, retention, and deletion mutation report only.",
        "Synthetic security-threat-model conformance; no penetration test, production posture, compliance, or operational claim.",
        "SECURITY-PRIVACY-001",
    )


def build_observability() -> dict:
    from scripts.validate_observability_lineage import (
        SUBJECT_HASHES as SUB, build_subject, run_one,
    )
    fixtures = sorted((ROOT / "evals/known_bad/frontier").glob("lineage_*.json"))
    return _evidence(
        "OBSERVABILITY-LINEAGE-001-PUBLIC-EVIDENCE", "observability-lineage-public-v1", 4,
        SUB, fixtures, run_one,
        "Synthetic complete-path lineage, correlation, replay identity, and sensitive-log mutation report only.",
        "Synthetic lineage, correlation, replay-identity, and sensitive-log control; no real trace, telemetry, or operational claim.",
        "OBSERVABILITY-LINEAGE-001",
    )


def build_replay() -> dict:
    from scripts.validate_replay_recovery import (
        SUBJECT_HASHES as SUB, build_subject, run_one,
    )
    fixtures = sorted((ROOT / "evals/known_bad/frontier").glob("replay_*.json"))
    return _evidence(
        "REPLAY-RECOVERY-001-PUBLIC-EVIDENCE", "replay-recovery-public-v1", 4,
        SUB, fixtures, run_one,
        "Synthetic replay, idempotency, crash, restore, compatibility, migration, and rollback mutation report only.",
        "Synthetic replay, idempotency, crash, restore, compatibility, migration, and rollback mechanics; no real availability, durability, or production recovery claim.",
        "REPLAY-RECOVERY-001",
    )


def build_adversarial() -> dict:
    from scripts.run_adversarial_campaign import (
        SUBJECT_HASHES as SUB, build_campaign_subject, run_one,
    )
    from scripts.run_adversarial_campaign import CASES
    paths = [ROOT / case["fixture"] for case in CASES]
    return _evidence(
        "ADVERSARIAL-CAMPAIGN-001-PUBLIC-EVIDENCE", "adversarial-campaign-v1", 5,
        SUB, paths, run_one,
        "Connected-system mutation score, survivors, properties, leakage, malformed-input, source/route fault, and recovery report only.",
        "Connected synthetic mutation/fault campaign; no real deployment, field, adversarial, or production claim.",
        "ADVERSARIAL-RESISTANCE-001",
        subject=build_campaign_subject(),
    )


def build_external_readiness() -> dict:
    from scripts.validate_external_readiness import (
        SUBJECT_HASHES as SUB, build_subject, run_one,
    )
    fixtures = sorted((ROOT / "evals/known_bad/frontier").glob("external_*.json"))
    return _evidence(
        "EXTERNAL-READINESS-001-PUBLIC-EVIDENCE", "external-readiness-public-v1", 4,
        SUB, fixtures, run_one,
        "Synthetic authority, expiry, revocation, aggregate-only, contamination, preregistration, and rollback mutation report only.",
        "External evidence preparation readiness; no real external evidence, attestation, trial, or commercial claim.",
        "EXTERNAL-READINESS-001",
    )


def build_convergence() -> dict:
    from scripts.validate_convergence import build_subject
    ledger = build_subject()
    checks = {
        "rounds_complete": len(ledger.get("rounds", [])) >= 2,
        "no_critical_or_high": ledger.get("conclusion", {}).get("no_critical_or_high_issue") is True,
        "no_positive_value_repair": ledger.get("conclusion", {}).get("no_positive_value_repair") is True,
        "independent_coordinator": ledger.get("independence", {}).get("sweep_coordinator") == "independent sweep coordinator",
    }
    return {
        "artifact_id": "CONVERGENCE-SWEEPS-001-PUBLIC-EVIDENCE",
        "evaluator_id": "convergence-public-v1",
        "schema_version": "1.0.0",
        "execution_scope": "SYNTHETIC_NON_INFLUENCING",
        "result": "PASS" if all(checks.values()) else "FAIL",
        "proof_level": 4,
        "checks": checks,
        "rounds": ledger.get("rounds", []),
        "claim": "Six independent synthetic sweep artifacts, severity ledger, repair hashes, independence evidence, and no-positive-value conclusions after the final repair.",
        "claim_ceiling": "Convergence sweep mechanics; no real field, production, causal, or commercial convergence claim.",
        "task_id": "CONVERGENCE-SWEEPS-001",
    }


def _evidence(
    artifact_id: str,
    evaluator_id: str,
    proof_level: int,
    subject_hashes: dict[str, str | None],
    fixture_paths: list[Path],
    run_one,
    claim: str,
    claim_ceiling: str,
    task_id: str,
    subject: dict | None = None,
) -> dict:
    mutation_results = []
    for path in sorted(fixture_paths):
        code, payload = run_one(path)
        mutation_results.append({
            "fixture": path.relative_to(ROOT).as_posix(),
            "fixture_sha256": payload.get("fixture_sha256", ""),
            "case_id": payload.get("case_id", ""),
            "result": payload.get("result", "SURVIVED"),
            "diagnostic": payload.get("diagnostic", ""),
        })
    resolved_hashes = {
        relative: file_sha256(ROOT / relative) for relative in subject_hashes
    }
    all_detected = all(item["result"] == "DETECTED" for item in mutation_results)
    return {
        "artifact_id": artifact_id,
        "evaluator_id": evaluator_id,
        "schema_version": "1.0.0",
        "execution_scope": "SYNTHETIC_NON_INFLUENCING",
        "result": "PASS" if all_detected else "FAIL",
        "proof_level": proof_level,
        "checks": {
            "registered_fixtures_detected": all_detected,
            "registered_mutation_count": len(mutation_results),
        },
        "subject_hashes": resolved_hashes,
        "mutation_results": mutation_results,
        "claim": claim,
        "claim_ceiling": claim_ceiling,
        "task_id": task_id,
    }


def main() -> int:
    targets: dict[Path, dict] = {
        ROOT / "artifacts/evaluations/data_history_synthetic.json": build_data_history(),
        ROOT / "artifacts/evaluations/economics_synthetic.json": build_economics(),
        ROOT / "artifacts/evaluations/routing_synthetic.json": build_routing(),
        ROOT / "artifacts/evaluations/security_privacy.json": build_security(),
        ROOT / "artifacts/evaluations/observability_lineage.json": build_observability(),
        ROOT / "artifacts/evaluations/replay_recovery.json": build_replay(),
        ROOT / "artifacts/evaluations/full_adversarial_campaign.json": build_adversarial(),
        ROOT / "artifacts/evaluations/external_readiness.json": build_external_readiness(),
    }
    for path, payload in targets.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
        print(f"wrote {path.relative_to(ROOT)} result={payload['result']}")
    return 0 if all(payload["result"] == "PASS" for payload in targets.values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
