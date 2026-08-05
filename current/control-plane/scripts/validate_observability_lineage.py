"""Read-only OBSERVABILITY-LINEAGE-001 validator and declarative mutation runner.

The canonical synthetic subject is an observability lineage manifest with
complete-path lineage, correlation, replay identity, and sensitive-log
control.  Diagnostics fire when a route decision omits source
public-availability/as-of identity or when protected-account match details are
emitted to general logs.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts._frontier_domain_common import (  # noqa: PLC0415
    file_sha256, known_bad_main, run_known_bad, strict_load,
)

SCHEMA = ROOT / "contracts/lineage_manifest.schema.json"
EVIDENCE = ROOT / "artifacts/evaluations/observability_lineage.json"
FIXTURES = sorted((ROOT / "evals/known_bad/frontier").glob("lineage_*.json"))
SUBJECT_HASHES = {
    "contracts/lineage_manifest.schema.json": None,
    "scripts/validate_observability_lineage.py": None,
}
for fixture in FIXTURES:
    SUBJECT_HASHES[fixture.relative_to(ROOT).as_posix()] = None


def build_subject() -> dict:
    return {
        "document_kind": "OBSERVABILITY_LINEAGE_MANIFEST",
        "schema_version": "1.0.0",
        "execution_scope": "SYNTHETIC_NON_INFLUENCING",
        "decisions": [
            {
                "decision_id": "DEC-001",
                "as_of": "2026-08-02T00:00:00Z",
                "source_public_availability": "2026-08-01T00:00:00Z",
                "lineage_nodes": ["snapshot_sha=abc", "math_problem=hash1", "decision=hash2"],
                "correlation_id": "run_001",
            }
        ],
        "logs": [
            {"level": "info", "message": "decision issued", "payload": ["run_001"]},
        ],
        "proof": {"level": 4, "result": "PASS"},
        "claim_ceiling": "Synthetic lineage, correlation, replay-identity, and sensitive-log control only; no real trace, telemetry, or operational claim.",
    }


def apply_mutation(subject: dict, mutation_id: str) -> None:
    if mutation_id == "missing_asof":
        subject["decisions"][0].pop("as_of")
        subject["decisions"][0].pop("source_public_availability")
    elif mutation_id == "protected_detail_log":
        subject["logs"].append(
            {"level": "info", "message": "protected match detail", "payload": ["account_0123", "addr_9"]}
        )
    else:
        raise ValueError("unsupported mutation recipe")


def diagnostics(subject: dict) -> list[str]:
    errors: list[str] = []
    for decision in subject.get("decisions", []):
        if not decision.get("as_of") or not decision.get("source_public_availability"):
            errors.append("LINEAGE-MISSING-ASOF")
    for entry in subject.get("logs", []):
        if entry.get("payload") and any(
            isinstance(item, str) and (item.startswith("account_") or item.startswith("addr_") or item.startswith("contact_"))
            for item in entry["payload"]
        ):
            errors.append("LINEAGE-PROTECTED-DETAIL-LOG")
    return errors


def run_one(path: Path) -> tuple[int, dict]:
    return run_known_bad(ROOT, FIXTURES, build_subject, apply_mutation, diagnostics, path)


def validate_all() -> list[str]:
    errors: list[str] = []
    if diagnostics(build_subject()):
        errors.append("LINEAGE-CLEAN-SUBJECT")
    if not SCHEMA.is_file():
        errors.append("LINEAGE-SCHEMA-MISSING")
    if not EVIDENCE.is_file():
        errors.append("LINEAGE-EVIDENCE-MISSING")
        return sorted(set(errors))
    evidence = strict_load(EVIDENCE)
    if evidence.get("artifact_id") != "OBSERVABILITY-LINEAGE-001-PUBLIC-EVIDENCE" or evidence.get("result") != "PASS":
        errors.append("LINEAGE-EVIDENCE-CLAIM")
    registered = {row.get("case_id"): row.get("diagnostic") for row in evidence.get("mutation_results", [])}
    for path in FIXTURES:
        recipe = strict_load(path)
        code, payload = run_one(path)
        if code != 0 or payload.get("result") != "DETECTED":
            errors.append(f"LINEAGE-MUTATION-SURVIVED:{recipe.get('case_id')}")
        if registered.get(recipe.get("case_id")) != recipe.get("expected_diagnostic"):
            errors.append(f"LINEAGE-MUTATION-REGISTRY:{recipe.get('case_id')}")
    subject_hashes = evidence.get("subject_hashes", {})
    for relative, _ in SUBJECT_HASHES.items():
        if file_sha256(ROOT / relative) != subject_hashes.get(relative):
            errors.append(f"LINEAGE-SUBJECT-DIGEST:{relative}")
    return sorted(set(errors))


if __name__ == "__main__":
    raise SystemExit(known_bad_main(sys.argv[1:], ROOT, build_subject, apply_mutation, diagnostics, validate_all))
