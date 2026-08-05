from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from cre_foundry.source_operations import (
    audit_source_operations,
    initialize_source_operations,
    plan_snapshot_replay,
    register_source_snapshot,
)


def _project(
    tmp_path: Path,
) -> Path:
    config_path = tmp_path / "config" / "source_operations.json"

    config_path.parent.mkdir(parents=True)

    config_path.write_text(
        json.dumps(
            {
                "config_version": "test-v1",
                "policies": {
                    "content_addressed_storage": True,
                    "snapshot_updates_allowed": False,
                    "snapshot_deletes_allowed": False,
                    "deduplicate_by_source_and_sha256": True,
                    "quarantine_on_checksum_mismatch": True,
                    "reacquire_during_replay": False,
                    "automatic_conclusions": False,
                    "opportunity_ranked": False,
                    "outreach_eligible": False,
                    "operating_mode": "shadow",
                },
                "sources": {
                    "test_source": {
                        "authorization_status": ("approved"),
                        "schedule_enabled": False,
                        "freshness_target_hours": None,
                        "maximum_staleness_hours": None,
                        "allowed_acquisition_methods": ["manual_file"],
                        "domain_allowlist": [],
                        "owner": None,
                        "credential_reference": None,
                        "parser_version": "test",
                        "schema_version": "test",
                        "browser_automation_status": ("not_configured"),
                    }
                },
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    return tmp_path


def test_initializes_append_only_source_controls(
    tmp_path: Path,
) -> None:
    project = _project(tmp_path)

    report = initialize_source_operations(project)

    assert report["configured_source_count"] == 1

    assert report["append_only_trigger_count"] == 8

    database = sqlite3.connect(project / "data" / "control" / "operations.sqlite3")

    try:
        policy_row = database.execute(
            """
            SELECT
                authorization_status,
                schedule_enabled
            FROM source_operation_policies
            WHERE source_id = 'test_source'
            """
        ).fetchone()

    finally:
        database.close()

    assert policy_row == (
        "approved",
        0,
    )


def test_registers_and_deduplicates_snapshot(
    tmp_path: Path,
) -> None:
    project = _project(tmp_path)

    initialize_source_operations(project)

    source_file = tmp_path / "input.json"

    source_file.write_text(
        '{"record": 1}\n',
        encoding="utf-8",
    )

    dry_run = register_source_snapshot(
        project,
        source_id="test_source",
        file_path=source_file,
        observed_at=("2026-07-26T12:00:00Z"),
        acquisition_method="manual_file",
        content_type="application/json",
        dry_run=True,
    )

    assert dry_run["status"] == ("validated")

    registered = register_source_snapshot(
        project,
        source_id="test_source",
        file_path=source_file,
        observed_at=("2026-07-26T12:00:00Z"),
        acquisition_method="manual_file",
        content_type="application/json",
        dry_run=False,
    )

    assert registered["status"] == ("registered")

    duplicate = register_source_snapshot(
        project,
        source_id="test_source",
        file_path=source_file,
        observed_at=("2026-07-26T12:00:00Z"),
        acquisition_method="manual_file",
        content_type="application/json",
        dry_run=False,
    )

    assert duplicate["status"] == ("duplicate")

    assert duplicate["snapshot_id"] == registered["snapshot_id"]

    replay = plan_snapshot_replay(
        project,
        snapshot_id=registered["snapshot_id"],
    )

    assert replay["status"] == ("replay_ready")

    assert replay["reacquire"] is False
    assert replay["writes_performed"] is False

    audit = audit_source_operations(
        project,
        write_contract=False,
    )

    assert audit["snapshot_count"] == 1
    assert audit["checksum_mismatch_count"] == 0
    assert audit["ready"] is True


def test_detects_snapshot_tampering(
    tmp_path: Path,
) -> None:
    project = _project(tmp_path)

    initialize_source_operations(project)

    source_file = tmp_path / "input.csv"

    source_file.write_text(
        "id\n1\n",
        encoding="utf-8",
    )

    registered = register_source_snapshot(
        project,
        source_id="test_source",
        file_path=source_file,
        observed_at=None,
        acquisition_method="manual_file",
        content_type="text/csv",
        dry_run=False,
    )

    artifact = project / registered["artifact_relative_path"]

    artifact.write_text(
        "tampered\n",
        encoding="utf-8",
    )

    audit = audit_source_operations(
        project,
        write_contract=False,
    )

    assert audit["checksum_mismatch_count"] == 1

    assert audit["ready"] is False

    with pytest.raises(
        RuntimeError,
        match="checksum",
    ):
        plan_snapshot_replay(
            project,
            snapshot_id=registered["snapshot_id"],
        )


def test_snapshot_ledger_blocks_update_and_delete(
    tmp_path: Path,
) -> None:
    project = _project(tmp_path)

    initialize_source_operations(project)

    source_file = tmp_path / "immutable.json"

    source_file.write_text(
        '{"immutable": true}\n',
        encoding="utf-8",
    )

    registered = register_source_snapshot(
        project,
        source_id="test_source",
        file_path=source_file,
        observed_at=("2026-07-26T12:00:00Z"),
        acquisition_method="manual_file",
        content_type="application/json",
        dry_run=False,
    )

    database_path = project / "data" / "control" / "operations.sqlite3"

    connection = sqlite3.connect(database_path)

    try:
        with pytest.raises(
            sqlite3.IntegrityError,
            match="append-only",
        ):
            connection.execute(
                """
                UPDATE source_snapshots
                SET byte_size = byte_size + 1
                WHERE snapshot_id = ?
                """,
                (registered["snapshot_id"],),
            )

        connection.rollback()

        with pytest.raises(
            sqlite3.IntegrityError,
            match="append-only",
        ):
            connection.execute(
                """
                DELETE FROM source_snapshots
                WHERE snapshot_id = ?
                """,
                (registered["snapshot_id"],),
            )

        connection.rollback()

        row = connection.execute(
            """
            SELECT
                byte_size
            FROM source_snapshots
            WHERE snapshot_id = ?
            """,
            (registered["snapshot_id"],),
        ).fetchone()

    finally:
        connection.close()

    assert row is not None

    assert int(row[0]) == source_file.stat().st_size


def test_rejects_non_object_configuration(
    tmp_path: Path,
) -> None:
    config_path = tmp_path / "config" / "source_operations.json"

    config_path.parent.mkdir(parents=True)

    config_path.write_text(
        "[]\n",
        encoding="utf-8",
    )

    with pytest.raises(
        RuntimeError,
        match="JSON object",
    ):
        initialize_source_operations(tmp_path)
