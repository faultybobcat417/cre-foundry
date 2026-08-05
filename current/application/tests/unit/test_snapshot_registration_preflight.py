from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from cre_foundry.snapshot_registration_preflight import (
    build_snapshot_registration_preflight,
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


def _write_config(
    project: Path,
) -> None:
    _write_json(
        project / "config" / "snapshot_registration_preflight.json",
        {
            "policy": {
                "operating_mode": "shadow",
                "authoritative_database_read_only": True,
                "ephemeral_database_clone_required": True,
                "schema_introspection_required": True,
                "required_column_mapping_required": True,
                "transaction_rollback_required": True,
                "count_reconciliation_required": True,
                "manual_parser_approval_required": True,
                "manual_temporal_approval_required": True,
                "manual_registration_approval_required": True,
                "authoritative_registration_enabled": False,
                "snapshot_event_insertion_enabled": False,
                "automatic_acquisition": False,
                "browser_execution": False,
                "computer_vision_execution": False,
                "opportunity_ranked": False,
                "outreach_eligible": False,
            }
        },
    )


def _project(
    tmp_path: Path,
    *,
    extra_required_column: bool = False,
) -> Path:
    _write_config(tmp_path)

    manifest = tmp_path / "data" / "source-1" / "manifest.json"

    manifest.parent.mkdir(parents=True)

    manifest.write_text(
        '{"source_id":"source-1"}',
        encoding="utf-8",
    )

    _write_json(
        tmp_path / "docs" / "data_contracts" / "snapshot_registration_review.json",
        {
            "candidates": [
                {
                    "source_id": "source-1",
                    "ready_for_human_review": True,
                    "temporal_evidence_missing": False,
                    "existing_snapshot_count": 0,
                    "manifest_path": str(manifest.relative_to(tmp_path)),
                    "registration_request_id": ("request-1"),
                    "bundle_sha256": ("bundle-sha"),
                    "timestamp_candidates": [{"normalized_utc": ("2026-07-26T12:00:00+00:00")}],
                    "artifacts": [
                        {
                            "artifact_path": ("data/source-1/data.csv"),
                            "artifact_sha256": ("artifact-sha"),
                            "size_bytes": 10,
                        }
                    ],
                }
            ]
        },
    )

    _write_json(
        tmp_path / "docs" / "data_contracts" / "deterministic_replay_spec.json",
        {"model_version": ("replay-v1")},
    )

    database = tmp_path / "data" / "control" / "operations.sqlite3"

    database.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    connection = sqlite3.connect(database)

    try:
        extra_column_sql = ", unknown_required TEXT NOT NULL" if extra_required_column else ""

        connection.execute(
            f"""
            CREATE TABLE source_snapshots (
                snapshot_id TEXT PRIMARY KEY,
                source_id TEXT NOT NULL,
                manifest_path TEXT NOT NULL,
                manifest_sha256 TEXT NOT NULL
                {extra_column_sql}
            )
            """
        )

        connection.execute(
            """
            CREATE TABLE source_snapshot_events (
                event_id TEXT PRIMARY KEY,
                source_id TEXT NOT NULL,
                event_type TEXT NOT NULL,
                payload_json TEXT NOT NULL
            )
            """
        )

        connection.commit()

    finally:
        connection.close()

    return tmp_path


def test_verifies_transaction_and_rollback_on_clone(
    tmp_path: Path,
) -> None:
    report = build_snapshot_registration_preflight(
        _project(tmp_path),
        write_contracts=False,
    )

    assert report["preflight_status"] == ("transactionally_verified_on_ephemeral_clone")

    assert report["ephemeral_transaction_verified"] is True

    assert report["authoritative_database_unchanged"] is True

    assert report["authoritative_registration_execution_count"] == 0

    assert report["authoritative_event_insertion_count"] == 0


def test_unknown_required_column_blocks_ephemeral_insert(
    tmp_path: Path,
) -> None:
    report = build_snapshot_registration_preflight(
        _project(
            tmp_path,
            extra_required_column=True,
        ),
        write_contracts=False,
    )

    assert report["preflight_status"] == "schema_mapping_incomplete"

    assert report["unmapped_snapshot_columns"] == ["unknown_required"]

    assert report["ephemeral_transaction_attempt_count"] == 0

    assert report["authoritative_database_unchanged"] is True


def test_authoritative_database_is_never_modified(
    tmp_path: Path,
) -> None:
    project = _project(tmp_path)

    database = project / "data" / "control" / "operations.sqlite3"

    before = database.read_bytes()

    report = build_snapshot_registration_preflight(
        project,
        write_contracts=False,
    )

    after = database.read_bytes()

    assert before == after

    assert report["authoritative_registration_execution_count"] == 0
