"""Read-only SECURITY-PRIVACY-001 validator and declarative mutation runner.

The canonical synthetic subject is the security posture of the representative
route-day system: retrieved-source authority, protected-data logging, external
writes, injection, retention, and deletion.  Diagnostics fire when retrieved
content grants credentials or changes policy, or when protected data appears
in general logs.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts._frontier_domain_common import (  # noqa: PLC0415
    file_sha256, known_bad_main, run_known_bad, strict_load,
)

THREAT_MODEL = ROOT / "docs/security/threat_model.md"
EVIDENCE = ROOT / "artifacts/evaluations/security_privacy.json"
FIXTURES = sorted((ROOT / "evals/known_bad/frontier").glob("security_*.json"))
SUBJECT_HASHES = {
    "docs/security/threat_model.md": None,
    "scripts/validate_security_privacy.py": None,
}
for fixture in FIXTURES:
    SUBJECT_HASHES[fixture.relative_to(ROOT).as_posix()] = None


def build_subject() -> dict:
    return {
        "document_kind": "SECURITY_POSTURE_SUBJECT",
        "schema_version": "1.0.0",
        "execution_scope": "SYNTHETIC_NON_INFLUENCING",
        "retrieved_authority": False,
        "policy_changes_from_content": False,
        "log_entries": [
            {"level": "info", "message": "correlation_id=run_001 route issued", "payload": []},
        ],
        "external_writes": [],
        "retention_days": 90,
        "deletion_verifiable": True,
        "proof": {"level": 4, "result": "PASS"},
        "claim_ceiling": "Synthetic security-threat-model conformance only; no penetration test, production posture, compliance, or operational claim.",
    }


def apply_mutation(subject: dict, mutation_id: str) -> None:
    if mutation_id == "retrieved_authority":
        subject["retrieved_authority"] = True
        subject["policy_changes_from_content"] = True
    elif mutation_id == "pii_log":
        subject["log_entries"].append(
            {"level": "info", "message": "protected account matched alias", "payload": ["account_0123", "addr_9"]}
        )
    else:
        raise ValueError("unsupported mutation recipe")


def diagnostics(subject: dict) -> list[str]:
    errors: list[str] = []
    if subject.get("retrieved_authority") or subject.get("policy_changes_from_content"):
        errors.append("SECURITY-RETRIEVED-AUTHORITY")
    for entry in subject.get("log_entries", []):
        if entry.get("payload") and any(
            isinstance(item, str) and (item.startswith("account_") or item.startswith("addr_") or item.startswith("contact_"))
            for item in entry["payload"]
        ):
            errors.append("SECURITY-PII-LOG")
    return errors


def run_one(path: Path) -> tuple[int, dict]:
    return run_known_bad(ROOT, FIXTURES, build_subject, apply_mutation, diagnostics, path)


def validate_all() -> list[str]:
    errors: list[str] = []
    if diagnostics(build_subject()):
        errors.append("SECURITY-CLEAN-SUBJECT")
    if not THREAT_MODEL.is_file():
        errors.append("SECURITY-THREAT-MODEL-MISSING")
    if not EVIDENCE.is_file():
        errors.append("SECURITY-EVIDENCE-MISSING")
        return sorted(set(errors))
    evidence = strict_load(EVIDENCE)
    if evidence.get("artifact_id") != "SECURITY-PRIVACY-001-PUBLIC-EVIDENCE" or evidence.get("result") != "PASS":
        errors.append("SECURITY-EVIDENCE-CLAIM")
    registered = {row.get("case_id"): row.get("diagnostic") for row in evidence.get("mutation_results", [])}
    for path in FIXTURES:
        recipe = strict_load(path)
        code, payload = run_one(path)
        if code != 0 or payload.get("result") != "DETECTED":
            errors.append(f"SECURITY-MUTATION-SURVIVED:{recipe.get('case_id')}")
        if registered.get(recipe.get("case_id")) != recipe.get("expected_diagnostic"):
            errors.append(f"SECURITY-MUTATION-REGISTRY:{recipe.get('case_id')}")
    subject_hashes = evidence.get("subject_hashes", {})
    for relative, _ in SUBJECT_HASHES.items():
        if file_sha256(ROOT / relative) != subject_hashes.get(relative):
            errors.append(f"SECURITY-SUBJECT-DIGEST:{relative}")
    return sorted(set(errors))


if __name__ == "__main__":
    raise SystemExit(known_bad_main(sys.argv[1:], ROOT, build_subject, apply_mutation, diagnostics, validate_all))
