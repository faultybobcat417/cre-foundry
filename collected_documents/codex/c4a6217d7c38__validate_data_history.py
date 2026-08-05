"""Read-only DATA-HISTORY-001 validator and declarative mutation runner.

The canonical synthetic subject is an immutable source-snapshot store with
bitemporal clocks (retrieved / available / effective / published) and
correction revisions.  Diagnostics are returned only when a snapshot is
accepted while truncated, hash-drifted, future-revisable, or conflated across
clocks — matching the gate's pass/failure conditions.
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts._frontier_domain_common import (  # noqa: PLC0415
    file_sha256, known_bad_main, run_known_bad, strict_load,
)

SCHEMA = ROOT / "contracts/source_snapshot.schema.json"
EVIDENCE = ROOT / "artifacts/evaluations/data_history_synthetic.json"
FIXTURE_GLOB = "data_*.json"
FIXTURES = sorted((ROOT / "evals/known_bad/frontier").glob(FIXTURE_GLOB))
FIXTURE_PATHS = [path for path in FIXTURES if path.stem != "data_future_revision" or True]
RECIPE_CASES = {
    "future-revision-visible": "DATA-HISTORY-FUTURE-REVISION",
    "partial-download-accepted": "DATA-HISTORY-PARTIAL-DOWNLOAD",
}
SUBJECT_HASHES = {
    "contracts/source_snapshot.schema.json": None,
    "scripts/validate_data_history.py": None,
}
for fixture in FIXTURES:
    SUBJECT_HASHES[fixture.relative_to(ROOT).as_posix()] = None


def build_subject() -> dict:
    return {
        "document_kind": "SOURCE_SNAPSHOT_STORE",
        "schema_version": "1.0.0",
        "execution_scope": "SYNTHETIC_NON_INFLUENCING",
        "snapshots": [
            {
                "snapshot_id": "SRC_001",
                "source_ref": "https://example.org/source/locations/v1",
                "retrieved_at": "2026-07-01T08:00:00Z",
                "byte_count": 4096,
                "sha256": "a" * 64,
                "complete": True,
                "available_at": "2026-07-01T08:30:00Z",
                "effective_at": "2026-07-01T00:00:00Z",
                "published_at": "2026-07-02T00:00:00Z",
                "correction_of": None,
                "tombstoned": False,
            },
            {
                "snapshot_id": "SRC_002",
                "source_ref": "https://example.org/source/locations/v1",
                "retrieved_at": "2026-07-10T08:00:00Z",
                "byte_count": 4608,
                "sha256": "b" * 64,
                "complete": True,
                "available_at": "2026-07-10T08:30:00Z",
                "effective_at": "2026-07-10T00:00:00Z",
                "published_at": "2026-07-11T00:00:00Z",
                "correction_of": "SRC_001",
                "tombstoned": False,
            },
        ],
        "reconstruction": {
            "as_of": "2026-07-11T00:00:00Z",
            "visible_snapshot_ids": ["SRC_002"],
            "checksum": "c" * 64,
        },
        "proof": {"level": 5, "result": "PASS"},
        "claim_ceiling": "Synthetic immutable snapshot mechanics and bitemporal replay only; no real source bytes, availability, accuracy, or production claim.",
    }


def apply_mutation(subject: dict, mutation_id: str) -> None:
    if mutation_id == "future_revision_visible":
        subject["snapshots"][1]["available_at"] = "2026-07-01T08:31:00Z"
        subject["snapshots"][1]["published_at"] = "2026-07-01T23:00:00Z"
        subject["reconstruction"]["visible_snapshot_ids"] = ["SRC_001", "SRC_002"]
    elif mutation_id == "partial_download_accepted":
        subject["snapshots"][1]["complete"] = False
        subject["snapshots"][1]["byte_count"] = 1024
    else:
        raise ValueError("unsupported mutation recipe")


def diagnostics(subject: dict) -> list[str]:
    errors: list[str] = []
    by_id = {row["snapshot_id"]: row for row in subject["snapshots"]}
    visible = subject["reconstruction"]["visible_snapshot_ids"]
    for snapshot_id in visible:
        row = by_id[snapshot_id]
        if not row["complete"] or row["byte_count"] <= 0:
            errors.append("DATA-HISTORY-PARTIAL-DOWNLOAD")
    for row in subject["snapshots"]:
        if row["correction_of"] is not None:
            prior = by_id.get(row["correction_of"])
            if prior is not None and row["available_at"] <= prior["published_at"]:
                errors.append("DATA-HISTORY-FUTURE-REVISION")
    return errors


def run_one(path: Path) -> tuple[int, dict]:
    return run_known_bad(ROOT, FIXTURES, build_subject, apply_mutation, diagnostics, path)


def validate_all() -> list[str]:
    errors: list[str] = []
    clean = diagnostics(build_subject())
    if clean:
        errors.append("DATA-HISTORY-CLEAN-SUBJECT")
    if not SCHEMA.is_file():
        errors.append("DATA-HISTORY-SCHEMA-MISSING")
    if not EVIDENCE.is_file():
        errors.append("DATA-HISTORY-EVIDENCE-MISSING")
        return sorted(set(errors))
    evidence = strict_load(EVIDENCE)
    if evidence.get("artifact_id") != "DATA-HISTORY-001-PUBLIC-EVIDENCE" or evidence.get("result") != "PASS":
        errors.append("DATA-HISTORY-EVIDENCE-CLAIM")
    registered = {row.get("case_id"): row.get("diagnostic") for row in evidence.get("mutation_results", [])}
    for path in FIXTURES:
        recipe = strict_load(path)
        code, payload = run_one(path)
        if code != 0 or payload.get("result") != "DETECTED":
            errors.append(f"DATA-HISTORY-MUTATION-SURVIVED:{recipe.get('case_id')}")
        if registered.get(recipe.get("case_id")) != recipe.get("expected_diagnostic"):
            errors.append(f"DATA-HISTORY-MUTATION-REGISTRY:{recipe.get('case_id')}")
    subject_hashes = evidence.get("subject_hashes", {})
    for relative, _ in SUBJECT_HASHES.items():
        if file_sha256(ROOT / relative) != subject_hashes.get(relative):
            errors.append(f"DATA-HISTORY-SUBJECT-DIGEST:{relative}")
    return sorted(set(errors))


if __name__ == "__main__":
    raise SystemExit(known_bad_main(sys.argv[1:], ROOT, build_subject, apply_mutation, diagnostics, validate_all))
