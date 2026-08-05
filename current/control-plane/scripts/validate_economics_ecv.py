"""Read-only ECONOMICS-ECV-001 validator and declarative mutation runner.

The canonical synthetic subject is a risk-adjusted expected net commercial
value model with explicit services, territories, commission, costs, conversion
uncertainty, downside, and fallback policy.  Diagnostics fire when costs are
omitted or when modeled value is claimed as realized net commercial value.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts._frontier_domain_common import (  # noqa: PLC0415
    file_sha256, known_bad_main, run_known_bad, strict_load,
)

SCHEMA = ROOT / "contracts/commercial_economics.schema.json"
EVIDENCE = ROOT / "artifacts/evaluations/economics_synthetic.json"
FIXTURES = sorted((ROOT / "evals/known_bad/frontier").glob("economics_*.json"))
SUBJECT_HASHES = {
    "contracts/commercial_economics.schema.json": None,
    "scripts/validate_economics_ecv.py": None,
}
for fixture in FIXTURES:
    SUBJECT_HASHES[fixture.relative_to(ROOT).as_posix()] = None


def build_subject() -> dict:
    return {
        "document_kind": "COMMERCIAL_ECONOMICS_MODEL",
        "schema_version": "1.0.0",
        "execution_scope": "SYNTHETIC_NON_INFLUENCING",
        "services": ["route-day outreach"],
        "territories": ["representative-territory"],
        "commission": {"rate": 0.06, "basis": "confirmed_booking"},
        "costs": [
            {"line_item": "material", "amount": 150.0, "currency": "CAD"},
            {"line_item": "travel", "amount": 60.0, "currency": "CAD"},
        ],
        "conversion": {"distribution": "beta", "mean": 0.18, "variance": 0.01},
        "downside": {"metric": "p10_net_value", "threshold": -200.0},
        "fallback_policy": "abstain when p10 net value is below threshold",
        "claim_status": "MODELED",
        "proof": {"level": 5, "result": "PASS"},
        "claim_ceiling": "Symbolic risk-adjusted expected value mechanics only; no firm-authoritative inputs, realized value, or commercial claim.",
    }


def apply_mutation(subject: dict, mutation_id: str) -> None:
    if mutation_id == "omitted_costs":
        subject["costs"] = []
    elif mutation_id == "modeled_as_realized":
        subject["claim_status"] = "REALIZED"
    else:
        raise ValueError("unsupported mutation recipe")


def diagnostics(subject: dict) -> list[str]:
    errors: list[str] = []
    if not subject.get("costs"):
        errors.append("ECONOMICS-OMITTED-COSTS")
    if subject.get("claim_status") != "MODELED":
        errors.append("ECONOMICS-MODELED-AS-REALIZED")
    return errors


def run_one(path: Path) -> tuple[int, dict]:
    return run_known_bad(ROOT, FIXTURES, build_subject, apply_mutation, diagnostics, path)


def validate_all() -> list[str]:
    errors: list[str] = []
    if diagnostics(build_subject()):
        errors.append("ECONOMICS-CLEAN-SUBJECT")
    if not SCHEMA.is_file():
        errors.append("ECONOMICS-SCHEMA-MISSING")
    if not EVIDENCE.is_file():
        errors.append("ECONOMICS-EVIDENCE-MISSING")
        return sorted(set(errors))
    evidence = strict_load(EVIDENCE)
    if evidence.get("artifact_id") != "ECONOMICS-ECV-001-PUBLIC-EVIDENCE" or evidence.get("result") != "PASS":
        errors.append("ECONOMICS-EVIDENCE-CLAIM")
    registered = {row.get("case_id"): row.get("diagnostic") for row in evidence.get("mutation_results", [])}
    for path in FIXTURES:
        recipe = strict_load(path)
        code, payload = run_one(path)
        if code != 0 or payload.get("result") != "DETECTED":
            errors.append(f"ECONOMICS-MUTATION-SURVIVED:{recipe.get('case_id')}")
        if registered.get(recipe.get("case_id")) != recipe.get("expected_diagnostic"):
            errors.append(f"ECONOMICS-MUTATION-REGISTRY:{recipe.get('case_id')}")
    subject_hashes = evidence.get("subject_hashes", {})
    for relative, _ in SUBJECT_HASHES.items():
        if file_sha256(ROOT / relative) != subject_hashes.get(relative):
            errors.append(f"ECONOMICS-SUBJECT-DIGEST:{relative}")
    return sorted(set(errors))


if __name__ == "__main__":
    raise SystemExit(known_bad_main(sys.argv[1:], ROOT, build_subject, apply_mutation, diagnostics, validate_all))
