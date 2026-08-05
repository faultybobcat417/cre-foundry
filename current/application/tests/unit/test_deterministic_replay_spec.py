from __future__ import annotations

import json
from pathlib import Path

from cre_foundry.deterministic_replay_spec import (
    build_deterministic_replay_spec,
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
    artifact_sha256: str = "artifact-sha",
) -> Path:
    _write_json(
        tmp_path / "config" / "deterministic_replay_spec.json",
        {
            "policy": {
                "operating_mode": "shadow",
                "metadata_only": True,
                "canonical_json_required": True,
                "checksum_pin_required": True,
                "relative_paths_required": True,
                "parser_contract_approval_required": True,
                "temporal_approval_required": True,
                "registration_approval_required": True,
                "artifact_copy_enabled": False,
                "parser_execution_enabled": False,
                "row_materialization_enabled": False,
                "snapshot_registration_enabled": False,
                "automatic_acquisition": False,
                "browser_execution": False,
                "computer_vision_execution": False,
                "opportunity_ranked": False,
                "outreach_eligible": False,
            }
        },
    )

    _write_json(
        tmp_path / "docs" / "data_contracts" / "source_snapshot_admission.json",
        {
            "packets": [
                {
                    "source_id": "source-1",
                    "manifest_probe": {"actual_sha256": ("manifest-sha")},
                }
            ]
        },
    )

    _write_json(
        tmp_path / "docs" / "data_contracts" / "snapshot_registration_review.json",
        {
            "candidates": [
                {
                    "source_id": "source-1",
                    "registration_request_id": ("request-1"),
                    "bundle_sha256": ("bundle-sha"),
                    "manifest_path": ("data/source-1/manifest.json"),
                    "temporal_evidence_status": ("manifest_declared"),
                    "timestamp_candidates": [{"normalized_utc": ("2026-07-26T12:00:00+00:00")}],
                    "artifacts": [
                        {
                            "artifact_path": ("data/source-1/data.csv"),
                            "artifact_sha256": (artifact_sha256),
                            "container_type": ("plain_file"),
                        }
                    ],
                    "ready_for_human_review": True,
                    "execution_blockers": ["manual_parser_approval_missing"],
                }
            ]
        },
    )

    _write_json(
        tmp_path / "docs" / "data_contracts" / "bounded_parser_probe.json",
        {
            "entries": [
                {
                    "source_id": "source-1",
                    "artifact_path": ("data/source-1/data.csv"),
                    "recognized_formats": ["delimited_text"],
                    "probe_result": {
                        "header": [
                            "id",
                            "name",
                        ]
                    },
                    "probe_completed": True,
                }
            ]
        },
    )

    return tmp_path


def test_replay_identifier_is_deterministic(
    tmp_path: Path,
) -> None:
    project = _project(tmp_path)

    first = build_deterministic_replay_spec(
        project,
        write_contracts=False,
    )

    second = build_deterministic_replay_spec(
        project,
        write_contracts=False,
    )

    assert first["specifications"][0]["replay_id"] == second["specifications"][0]["replay_id"]


def test_checksum_change_changes_replay_identifier(
    tmp_path: Path,
) -> None:
    first_project = _project(
        tmp_path / "first",
        artifact_sha256="sha-one",
    )

    second_project = _project(
        tmp_path / "second",
        artifact_sha256="sha-two",
    )

    first = build_deterministic_replay_spec(
        first_project,
        write_contracts=False,
    )

    second = build_deterministic_replay_spec(
        second_project,
        write_contracts=False,
    )

    assert first["specifications"][0]["replay_id"] != second["specifications"][0]["replay_id"]


def test_replay_spec_never_executes(
    tmp_path: Path,
) -> None:
    report = build_deterministic_replay_spec(
        _project(tmp_path),
        write_contracts=False,
    )

    assert report["artifact_copy_execution_count"] == 0

    assert report["parser_execution_count"] == 0

    assert report["row_materialization_execution_count"] == 0

    assert report["snapshot_registration_execution_count"] == 0
