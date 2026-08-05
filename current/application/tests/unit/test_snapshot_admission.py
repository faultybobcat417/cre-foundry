from __future__ import annotations

import hashlib
import json
from pathlib import Path

from cre_foundry.snapshot_admission import (
    build_snapshot_admission,
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


def _config(
    project: Path,
) -> None:
    _write_json(
        project / "config" / "source_snapshot_admission.json",
        {
            "policy": {
                "operating_mode": "shadow",
                "read_only": True,
                "manual_review_required": True,
                "exact_path_required": True,
                "project_boundary_required": True,
                "regular_file_required": True,
                "symlink_allowed": False,
                "checksum_verification_required": True,
                "source_identity_match_required": True,
                "automatic_snapshot_registration": False,
                "automatic_acquisition": False,
                "automatic_conclusions": False,
                "opportunity_ranked": False,
                "outreach_eligible": False,
            },
            "artifact_probe": {
                "header_bytes": 65536,
                "json_parse_limit_bytes": 5242880,
                "text_header_limit_bytes": 65536,
            },
        },
    )


def _project(
    tmp_path: Path,
) -> tuple[
    Path,
    Path,
    Path,
]:
    _config(tmp_path)

    artifact = tmp_path / "data" / "bronze" / "source-1" / "artifact.json"

    artifact.parent.mkdir(parents=True)

    artifact.write_text(
        '{"records": [1, 2, 3]}\n',
        encoding="utf-8",
    )

    artifact_sha = hashlib.sha256(artifact.read_bytes()).hexdigest()

    manifest = artifact.parent / "manifest.json"

    manifest.write_text(
        json.dumps(
            {
                "source_id": "source-1",
                "artifact_path": str(artifact.relative_to(tmp_path)),
                "artifact_sha256": (artifact_sha),
                "acquired_at": ("2026-07-26T12:00:00Z"),
            }
        ),
        encoding="utf-8",
    )

    manifest_sha = hashlib.sha256(manifest.read_bytes()).hexdigest()

    _write_json(
        tmp_path / "docs" / "data_contracts" / "source_snapshot_bootstrap_review.json",
        {
            "packet_count": 1,
            "packets": [
                {
                    "source_id": "source-1",
                    "manifest_path": str(manifest.relative_to(tmp_path)),
                    "manifest_actual_sha256": (manifest_sha),
                    "review_ready": True,
                    "violations": [],
                    "referenced_artifacts": [
                        {
                            "declared_path": str(artifact.relative_to(tmp_path)),
                            "actual_sha256": (artifact_sha),
                            "size_bytes": (artifact.stat().st_size),
                        }
                    ],
                }
            ],
        },
    )

    return (
        tmp_path,
        artifact,
        manifest,
    )


def test_admits_checksum_verified_bundle(
    tmp_path: Path,
) -> None:
    project, _, _ = _project(tmp_path)

    report = build_snapshot_admission(
        project,
        write_contracts=False,
    )

    assert report["admission"]["source_packet_count"] == 1

    assert report["admission"]["admission_ready_count"] == 1

    assert report["admission"]["blocked_count"] == 0

    assert report["admission"]["snapshot_registration_permitted"] is False

    assert report["replay"]["replay_metadata_ready_count"] == 1


def test_blocks_changed_artifact(
    tmp_path: Path,
) -> None:
    (
        project,
        artifact,
        _,
    ) = _project(tmp_path)

    artifact.write_text(
        '{"records": [4]}\n',
        encoding="utf-8",
    )

    report = build_snapshot_admission(
        project,
        write_contracts=False,
    )

    packet = report["admission"]["packets"][0]

    assert packet["admission_ready"] is False

    assert "artifact_checksum_changed" in packet["violations"]


def test_blocks_path_outside_project(
    tmp_path: Path,
) -> None:
    project, _, manifest = _project(tmp_path)

    outside = tmp_path.parent / "outside-artifact.json"

    outside.write_text(
        '{"outside": true}\n',
        encoding="utf-8",
    )

    payload = json.loads(
        (project / "docs" / "data_contracts" / "source_snapshot_bootstrap_review.json").read_text(
            encoding="utf-8"
        )
    )

    payload["packets"][0]["referenced_artifacts"][0]["declared_path"] = str(outside)

    payload["packets"][0]["manifest_path"] = str(manifest.relative_to(project))

    (project / "docs" / "data_contracts" / "source_snapshot_bootstrap_review.json").write_text(
        json.dumps(payload),
        encoding="utf-8",
    )

    report = build_snapshot_admission(
        project,
        write_contracts=False,
    )

    packet = report["admission"]["packets"][0]

    assert packet["admission_ready"] is False

    assert "artifact_outside_project_boundary" in packet["violations"]
