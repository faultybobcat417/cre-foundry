"""Read-only CONVERGENCE-SWEEPS-001 validator and declarative mutation runner.

The canonical synthetic subject is the convergence ledger: three independent
domain sweeps per round, two successive complete rounds with no critical/high
issue and no defensible positive-value change after the last material repair.
Diagnostics fire when only one clean round exists, sweeps predate a material
repair, synthetic success is promoted to field proof, or booked appointments
are promoted to realized net commercial value.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts._frontier_domain_common import (  # noqa: PLC0415
    file_sha256, known_bad_main, run_known_bad, strict_load,
)

LEDGER = ROOT / "artifacts/convergence/convergence_ledger.json"
FIXTURES = sorted(
    path for path in (ROOT / "evals/known_bad/frontier").glob("convergence_*.json")
    if path.stem in {"convergence_single_round", "convergence_stale_sweeps", "convergence_synthetic_as_field", "convergence_booking_as_value"}
)
SUBJECT_HASHES = {
    "artifacts/convergence/convergence_ledger.json": None,
    "scripts/validate_convergence.py": None,
}
for fixture in FIXTURES:
    SUBJECT_HASHES[fixture.as_posix()] = None


def build_subject() -> dict:
    return strict_load(LEDGER)


def apply_mutation(subject: dict, mutation_id: str) -> None:
    if mutation_id == "single_clean_round":
        subject["rounds"] = subject["rounds"][:1]
    elif mutation_id == "stale_sweeps":
        subject["rounds"][-1]["after_last_material_repair"] = False
        subject["rounds"][-1]["issue_severity"]["high"] = 1
    elif mutation_id == "synthetic_as_field":
        subject["conclusion"]["synthetic_promoted_as_field"] = True
    elif mutation_id == "booking_as_net_value":
        subject["conclusion"]["booking_promoted_as_value"] = True
    else:
        raise ValueError("unsupported mutation recipe")


def diagnostics(subject: dict) -> list[str]:
    errors: list[str] = []
    rounds = subject.get("rounds", [])
    if len(rounds) < 2:
        errors.append("CONVERGENCE-SINGLE-CLEAN-ROUND")
    for round_ in rounds:
        if round_.get("after_last_material_repair") is not True:
            errors.append("CONVERGENCE-STALE-SWEEPS")
        if round_.get("issue_severity", {}).get("high", 0) > 0 or round_.get("issue_severity", {}).get("critical", 0) > 0:
            errors.append("CONVERGENCE-STALE-SWEEPS")
    if subject.get("conclusion", {}).get("synthetic_promoted_as_field"):
        errors.append("registered mutation detected: synthetic-as-field-proof")
    if subject.get("conclusion", {}).get("booking_promoted_as_value"):
        errors.append("registered mutation detected: booking-as-net-value")
    return sorted(set(errors))


def run_one(path: Path) -> tuple[int, dict]:
    return run_known_bad(ROOT, FIXTURES, build_subject, apply_mutation, diagnostics, path)


def validate_all() -> list[str]:
    errors: list[str] = []
    if not LEDGER.is_file():
        errors.append("CONVERGENCE-LEDGER-MISSING")
        return sorted(set(errors))
    if diagnostics(build_subject()):
        errors.append("CONVERGENCE-CLEAN-LEDGER")
    for path in FIXTURES:
        recipe = strict_load(path)
        code, payload = run_one(path)
        if code != 0 or payload.get("result") != "DETECTED":
            errors.append(f"CONVERGENCE-MUTATION-SURVIVED:{recipe.get('case_id')}")
    return sorted(set(errors))


if __name__ == "__main__":
    raise SystemExit(known_bad_main(sys.argv[1:], ROOT, build_subject, apply_mutation, diagnostics, validate_all))
