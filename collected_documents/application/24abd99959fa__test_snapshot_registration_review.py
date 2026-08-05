from __future__ import annotations

import hashlib
import json
import sqlite3
from pathlib import Path

from cre_foundry.snapshot_registration_review import (
    build_snapshot_registration_review,
)


def _write_json(
    path: Path,
    payload: dict[str, object],
) -> None:
    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    path.write_text(
        json.dumps(payload),
        encoding="utf-8",
    )


def _project(
    tmp_path: Path,
    *,
    manifest_source_id: str = "source-1",
) -> Path:
    _write_json(
        tmp_path / "config" / "snapshot_registration_review.json",
        {
            "policy": {
                "operating_mode": "shadow",
                "read_only": True,
                "governed_source_required": True,
                "admission_ready_required": True,
                "container_recon_ready_required": True,
                "manifest_source_identity_match_required": True,
                "manifest_timestamp_required": True,
                "manual_parser_approval_required": True,
                "manual_temporal_approval_required": True,
                "manual_registration_approval_required": True,
                "registration_sql_generation_enabled": False,
                "snapshot_registration_enabled": False,
                "automatic_acquisition": False,
                "browser_execution": False,
                "computer_vision_execution": False,
                "opportunity_ranked": False,
                "outreach_eligible": False,
            }
        },
    )

    artifact = tmp_path / "data" / "source-1" / "records.geojson.gz"

    artifact.parent.mkdir(parents=True)

    artifact.write_bytes(b"\x1f\x8btest")

    checksum = hashlib.sha256(artifact.read_bytes()).hexdigest()

    manifest = artifact.parent / "manifest.json"

    _write_json(
        manifest,
        {
            "source_id": (manifest_source_id),
            "acquired_at": ("2026-07-26T12:00:00Z"),
        },
    )

    artifact_path = str(artifact.relative_to(tmp_path))

    _write_json(
        tmp_path / "docs" / "data_contracts" / "source_snapshot_admission.json",
        {
            "packets": [
                {
                    "source_id": "source-1",
                    "manifest_path": str(manifest.relative_to(tmp_path)),
                    "bundle_sha256": ("bundle-sha"),
                    "admission_ready": True,
                    "artifacts": [
                        {
                            "resolved_relative_path": (artifact_path),
                            "probe": {
                                "actual_sha256": (checksum),
                                "size_bytes": (artifact.stat().st_size),
                            },
                        }
                    ],
                }
            ]
        },
    )

    _write_json(
        tmp_path / "docs" / "data_contracts" / "source_container_inventory.json",
        {
            "entries": [
                {
                    "source_id": "source-1",
                    "artifact_path": (artifact_path),
                    "container_type": "gzip",
                    "format_candidates": ["gzip_geojson"],
                    "container_recon_ready": True,
                }
            ]
        },
    )

    database_path = tmp_path / "data" / "control" / "operations.sqlite3"

    database_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    connection = sqlite3.connect(database_path)

    try:
        connection.execute(
            """
            CREATE TABLE source_operation_policies (
                source_id TEXT PRIMARY KEY
            )
            """
        )

        connection.executemany(
            """
            INSERT INTO source_operation_policies
            VALUES (?)
            """,
            [
                ("source-1",),
                ("source-2",),
            ],
        )

        connection.execute(
            """
            CREATE TABLE source_snapshots (
                snapshot_id TEXT PRIMARY KEY,
                source_id TEXT NOT NULL
            )
            """
        )

        connection.execute(
            """
            CREATE TABLE source_snapshot_events (
                event_id TEXT PRIMARY KEY,
                source_id TEXT NOT NULL
            )
            """
        )

        connection.commit()

    finally:
        connection.close()

    return tmp_path


def test_builds_review_ready_packet(
    tmp_path: Path,
) -> None:
    report = build_snapshot_registration_review(
        _project(tmp_path),
        write_contracts=False,
    )

    review = report["review"]

    assert review["governed_source_count"] == 2

    assert review["candidate_count"] == 1

    assert review["review_ready_count"] == 1

    assert review["unadmitted_source_ids"] == ["source-2"]

    candidate = review["candidates"][0]

    assert candidate["manifest_source_identity_match"] is True

    assert candidate["timestamp_candidate_count"] == 1

    assert candidate["registration_execution_permitted"] is False


def test_blocks_manifest_source_mismatch(
    tmp_path: Path,
) -> None:
    report = build_snapshot_registration_review(
        _project(
            tmp_path,
            manifest_source_id=("different-source"),
        ),
        write_contracts=False,
    )

    candidate = report["review"]["candidates"][0]

    assert candidate["ready_for_human_review"] is False

    assert "manifest_source_identity_mismatch" in candidate["structural_violations"]


def test_never_approves_or_registers(
    tmp_path: Path,
) -> None:
    report = build_snapshot_registration_review(
        _project(tmp_path),
        write_contracts=False,
    )

    review = report["review"]

    approvals = report["approval_template"]

    assert review["approved_registration_count"] == 0

    assert review["registration_sql_generation_count"] == 0

    assert review["snapshot_registration_execution_count"] == 0

    assert approvals["approved_parser_contract_count"] == 0

    assert approvals["approved_temporal_semantics_count"] == 0

    assert approvals["approved_registration_count"] == 0

    for approval in approvals["approvals"]:
        assert approval["parser_contract_approved"] is False

        assert approval["temporal_semantics_approved"] is False

        assert approval["registration_approved"] is False

        assert approval["registration_execution_permitted"] is False


def test_missing_manifest_timestamp_blocks_execution_not_review(
    tmp_path: Path,
) -> None:
    project = _project(tmp_path)

    admission_path = project / "docs" / "data_contracts" / "source_snapshot_admission.json"

    admission = json.loads(admission_path.read_text(encoding="utf-8"))

    manifest_path = project / admission["packets"][0]["manifest_path"]

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    for key in (
        "acquired_at",
        "completed_at",
        "created_at",
        "effective_at",
        "fetched_at",
        "generated_at",
        "observed_at",
        "retrieved_at",
        "run_started_at",
        "started_at",
    ):
        manifest.pop(
            key,
            None,
        )

    manifest_path.write_text(
        json.dumps(manifest),
        encoding="utf-8",
    )

    report = build_snapshot_registration_review(
        project,
        write_contracts=False,
    )

    candidate = report["review"]["candidates"][0]

    assert candidate["ready_for_human_review"] is True

    assert candidate["structural_violations"] == []

    assert candidate["timestamp_candidate_count"] == 0

    assert candidate["temporal_evidence_missing"] is True

    assert candidate["temporal_evidence_status"] == "missing_manifest_timestamp"

    assert "manifest_timestamp_evidence_missing" in candidate["execution_blockers"]

    assert candidate["registration_execution_permitted"] is False
