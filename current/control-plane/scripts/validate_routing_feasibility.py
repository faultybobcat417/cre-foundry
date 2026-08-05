"""Read-only ROUTING-FEASIBILITY-001 validator and declarative mutation runner.

The canonical synthetic subject is a versioned travel-time matrix with
service times, capacity, reserve, and the selected ten locations.  Diagnostics
fire when straight-line distance is substituted for route time or when a stale
or asymmetric matrix is accepted.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts._frontier_domain_common import (  # noqa: PLC0415
    file_sha256, known_bad_main, run_known_bad, strict_load,
)

SCHEMA = ROOT / "contracts/route_feasibility.schema.json"
EVIDENCE = ROOT / "artifacts/evaluations/routing_synthetic.json"
FIXTURES = sorted((ROOT / "evals/known_bad/frontier").glob("routing_*.json"))
SUBJECT_HASHES = {
    "contracts/route_feasibility.schema.json": None,
    "scripts/validate_routing_feasibility.py": None,
}
for fixture in FIXTURES:
    SUBJECT_HASHES[fixture.relative_to(ROOT).as_posix()] = None

CURRENT_MATRIX_VERSION = "matrix-v7"
STRAIGHT_LINE_METRIC = "STRAIGHT_LINE_DISTANCE"


def build_subject() -> dict:
    return {
        "document_kind": "ROUTE_FEASIBILITY_MATRIX",
        "schema_version": "1.0.0",
        "execution_scope": "SYNTHETIC_NON_INFLUENCING",
        "matrix_version": CURRENT_MATRIX_VERSION,
        "generated_at": "2026-08-02T00:00:00Z",
        "metric": "DRIVING_TIME",
        "travel_time": [
            [0, 12, 24],
            [12, 0, 18],
            [24, 18, 0],
        ],
        "service_times": [10, 12, 11],
        "capacity": 10,
        "reserve": 2,
        "ten_locations": ["loc_01", "loc_02", "loc_03"],
        "proof": {"level": 5, "result": "PASS"},
        "claim_ceiling": "Synthetic route-time feasibility mechanics only; no real provider matrix, measured service time, or operational claim.",
    }


def apply_mutation(subject: dict, mutation_id: str) -> None:
    if mutation_id == "straight_line_substitution":
        subject["metric"] = STRAIGHT_LINE_METRIC
        subject["travel_time"] = [
            [0, 8, 15],
            [8, 0, 12],
            [15, 12, 0],
        ]
    elif mutation_id == "stale_asymmetric_matrix":
        subject["matrix_version"] = "matrix-v3"
        subject["travel_time"] = [
            [0, 12, 24],
            [9, 0, 18],
            [25, 17, 0],
        ]
    else:
        raise ValueError("unsupported mutation recipe")


def diagnostics(subject: dict) -> list[str]:
    errors: list[str] = []
    matrix = subject.get("travel_time", [])
    size = len(matrix)
    symmetric = size > 0 and all(
        matrix[i][j] == matrix[j][i] for i in range(size) for j in range(size)
    )
    if subject.get("metric") == STRAIGHT_LINE_METRIC:
        errors.append("ROUTING-STRAIGHT-LINE")
    if subject.get("matrix_version") != CURRENT_MATRIX_VERSION or not symmetric:
        errors.append("ROUTING-STALE-ASYMMETRIC")
    return errors


def run_one(path: Path) -> tuple[int, dict]:
    return run_known_bad(ROOT, FIXTURES, build_subject, apply_mutation, diagnostics, path)


def validate_all() -> list[str]:
    errors: list[str] = []
    if diagnostics(build_subject()):
        errors.append("ROUTING-CLEAN-SUBJECT")
    if not SCHEMA.is_file():
        errors.append("ROUTING-SCHEMA-MISSING")
    if not EVIDENCE.is_file():
        errors.append("ROUTING-EVIDENCE-MISSING")
        return sorted(set(errors))
    evidence = strict_load(EVIDENCE)
    if evidence.get("artifact_id") != "ROUTING-FEASIBILITY-001-PUBLIC-EVIDENCE" or evidence.get("result") != "PASS":
        errors.append("ROUTING-EVIDENCE-CLAIM")
    registered = {row.get("case_id"): row.get("diagnostic") for row in evidence.get("mutation_results", [])}
    for path in FIXTURES:
        recipe = strict_load(path)
        code, payload = run_one(path)
        if code != 0 or payload.get("result") != "DETECTED":
            errors.append(f"ROUTING-MUTATION-SURVIVED:{recipe.get('case_id')}")
        if registered.get(recipe.get("case_id")) != recipe.get("expected_diagnostic"):
            errors.append(f"ROUTING-MUTATION-REGISTRY:{recipe.get('case_id')}")
    subject_hashes = evidence.get("subject_hashes", {})
    for relative, _ in SUBJECT_HASHES.items():
        if file_sha256(ROOT / relative) != subject_hashes.get(relative):
            errors.append(f"ROUTING-SUBJECT-DIGEST:{relative}")
    return sorted(set(errors))


if __name__ == "__main__":
    raise SystemExit(known_bad_main(sys.argv[1:], ROOT, build_subject, apply_mutation, diagnostics, validate_all))
