"""Read-only REPLAY-RECOVERY-001 validator and declarative mutation runner.

The canonical synthetic subject is the replay and recovery posture: idempotent
effects, replay receipts, snapshot readability across schema changes, and
migration/rollback plans.  Diagnostics fire when a retry duplicates an effect
or when a schema change makes a retained snapshot unreadable.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts._frontier_domain_common import (  # noqa: PLC0415
    file_sha256, known_bad_main, run_known_bad, strict_load,
)

RECOVERY_PLAN = ROOT / "docs/reliability/recovery_and_migrations.md"
EVIDENCE = ROOT / "artifacts/evaluations/replay_recovery.json"
FIXTURES = sorted((ROOT / "evals/known_bad/frontier").glob("replay_*.json"))
SUBJECT_HASHES = {
    "docs/reliability/recovery_and_migrations.md": None,
    "scripts/validate_replay_recovery.py": None,
}
for fixture in FIXTURES:
    SUBJECT_HASHES[fixture.relative_to(ROOT).as_posix()] = None


def build_subject() -> dict:
    return {
        "document_kind": "REPLAY_RECOVERY_SUBJECT",
        "schema_version": "1.0.0",
        "execution_scope": "SYNTHETIC_NON_INFLUENCING",
        "effects": [
            {"effect_id": "EFF-001", "idempotency_key": "key_001", "kind": "issuance"},
        ],
        "snapshots": [
            {"snapshot_id": "SNAP-001", "schema_version": 1, "readable": True},
        ],
        "receipts": [
            {"decision_sha": "hash1", "manifest_sha": "hash2", "effect_sha": "hash3"},
        ],
        "migrations": [{"from": 1, "to": 2, "rollback_defined": True}],
        "proof": {"level": 4, "result": "PASS"},
        "claim_ceiling": "Synthetic replay, idempotency, crash, restore, compatibility, migration, and rollback mechanics only; no real availability, durability, or production recovery claim.",
    }


def apply_mutation(subject: dict, mutation_id: str) -> None:
    if mutation_id == "duplicate_effect":
        subject["effects"].append(
            {"effect_id": "EFF-002", "idempotency_key": "key_001", "kind": "issuance"}
        )
    elif mutation_id == "old_snapshot_unreadable":
        subject["snapshots"][0]["readable"] = False
    else:
        raise ValueError("unsupported mutation recipe")


def diagnostics(subject: dict) -> list[str]:
    errors: list[str] = []
    seen: set[str] = set()
    for effect in subject.get("effects", []):
        key = effect.get("idempotency_key")
        if key in seen:
            errors.append("REPLAY-DUPLICATE-EFFECT")
        seen.add(key)
    for snapshot in subject.get("snapshots", []):
        if not snapshot.get("readable"):
            errors.append("REPLAY-OLD-SNAPSHOT-UNREADABLE")
    return errors


def run_one(path: Path) -> tuple[int, dict]:
    return run_known_bad(ROOT, FIXTURES, build_subject, apply_mutation, diagnostics, path)


def validate_all() -> list[str]:
    errors: list[str] = []
    if diagnostics(build_subject()):
        errors.append("REPLAY-CLEAN-SUBJECT")
    if not RECOVERY_PLAN.is_file():
        errors.append("REPLAY-RECOVERY-PLAN-MISSING")
    if not EVIDENCE.is_file():
        errors.append("REPLAY-EVIDENCE-MISSING")
        return sorted(set(errors))
    evidence = strict_load(EVIDENCE)
    if evidence.get("artifact_id") != "REPLAY-RECOVERY-001-PUBLIC-EVIDENCE" or evidence.get("result") != "PASS":
        errors.append("REPLAY-EVIDENCE-CLAIM")
    registered = {row.get("case_id"): row.get("diagnostic") for row in evidence.get("mutation_results", [])}
    for path in FIXTURES:
        recipe = strict_load(path)
        code, payload = run_one(path)
        if code != 0 or payload.get("result") != "DETECTED":
            errors.append(f"REPLAY-MUTATION-SURVIVED:{recipe.get('case_id')}")
        if registered.get(recipe.get("case_id")) != recipe.get("expected_diagnostic"):
            errors.append(f"REPLAY-MUTATION-REGISTRY:{recipe.get('case_id')}")
    subject_hashes = evidence.get("subject_hashes", {})
    for relative, _ in SUBJECT_HASHES.items():
        if file_sha256(ROOT / relative) != subject_hashes.get(relative):
            errors.append(f"REPLAY-SUBJECT-DIGEST:{relative}")
    return sorted(set(errors))


if __name__ == "__main__":
    raise SystemExit(known_bad_main(sys.argv[1:], ROOT, build_subject, apply_mutation, diagnostics, validate_all))
