"""Read-only EXTERNAL-READINESS-001 validator and declarative mutation runner.

The canonical synthetic subject is the external evidence readiness manifest:
every external gate has a versioned input/attestation schema, owner role,
authority scope, expiry/revocation, adapter, synthetic fixture, evaluator, and
unlock protocol; empirical protocols are preregistered and cannot silently
change after observation.  Diagnostics fire when an owner is a placeholder or
when a trial may change post-hoc.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts._frontier_domain_common import (  # noqa: PLC0415
    file_sha256, known_bad_main, run_known_bad, strict_load,
)

MANIFEST = ROOT / "artifacts/external-readiness/readiness_manifest.json"
EVIDENCE = ROOT / "artifacts/evaluations/external_readiness.json"
FIXTURES = sorted((ROOT / "evals/known_bad/frontier").glob("external_*.json"))
SUBJECT_HASHES = {
    "artifacts/external-readiness/readiness_manifest.json": None,
    "scripts/validate_external_readiness.py": None,
}
for fixture in FIXTURES:
    SUBJECT_HASHES[fixture.relative_to(ROOT).as_posix()] = None

PLACEHOLDER_OWNERS = {"TBD", "UNKNOWN", "", "to be determined"}


def build_subject() -> dict:
    return strict_load(MANIFEST)


def apply_mutation(subject: dict, mutation_id: str) -> None:
    if mutation_id == "placeholder_owner":
        subject["external_gates"][0]["owner_role"] = "TBD"
    elif mutation_id == "posthoc_trial":
        subject["contamination_controls"]["trial_endpoint_lock"] = False
    else:
        raise ValueError("unsupported mutation recipe")


def diagnostics(subject: dict) -> list[str]:
    errors: list[str] = []
    for gate in subject.get("external_gates", []):
        if gate.get("owner_role") in PLACEHOLDER_OWNERS:
            errors.append("EXTERNAL-READINESS-PLACEHOLDER-OWNER")
    controls = subject.get("contamination_controls", {})
    if controls.get("trial_endpoint_lock") is not True:
        errors.append("EXTERNAL-READINESS-POSTHOC-TRIAL")
    return errors


def run_one(path: Path) -> tuple[int, dict]:
    return run_known_bad(ROOT, FIXTURES, build_subject, apply_mutation, diagnostics, path)


def validate_all() -> list[str]:
    errors: list[str] = []
    if not MANIFEST.is_file():
        errors.append("EXTERNAL-READINESS-MANIFEST-MISSING")
        return sorted(set(errors))
    if diagnostics(build_subject()):
        errors.append("EXTERNAL-READINESS-CLEAN-MANIFEST")
    if not EVIDENCE.is_file():
        errors.append("EXTERNAL-READINESS-EVIDENCE-MISSING")
        return sorted(set(errors))
    evidence = strict_load(EVIDENCE)
    if evidence.get("artifact_id") != "EXTERNAL-READINESS-001-PUBLIC-EVIDENCE" or evidence.get("result") != "PASS":
        errors.append("EXTERNAL-READINESS-EVIDENCE-CLAIM")
    registered = {row.get("case_id"): row.get("diagnostic") for row in evidence.get("mutation_results", [])}
    for path in FIXTURES:
        recipe = strict_load(path)
        code, payload = run_one(path)
        if code != 0 or payload.get("result") != "DETECTED":
            errors.append(f"EXTERNAL-READINESS-MUTATION-SURVIVED:{recipe.get('case_id')}")
        if registered.get(recipe.get("case_id")) != recipe.get("expected_diagnostic"):
            errors.append(f"EXTERNAL-READINESS-MUTATION-REGISTRY:{recipe.get('case_id')}")
    subject_hashes = evidence.get("subject_hashes", {})
    for relative, _ in SUBJECT_HASHES.items():
        if file_sha256(ROOT / relative) != subject_hashes.get(relative):
            errors.append(f"EXTERNAL-READINESS-SUBJECT-DIGEST:{relative}")
    return sorted(set(errors))


if __name__ == "__main__":
    raise SystemExit(known_bad_main(sys.argv[1:], ROOT, build_subject, apply_mutation, diagnostics, validate_all))
