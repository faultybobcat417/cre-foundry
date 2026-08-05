from __future__ import annotations

import hashlib
import json
from pathlib import Path

from cre_foundry.snapshot_bootstrap_review import (
    build_snapshot_bootstrap_review,
)


def test_builds_checksum_verified_review_packet(
    tmp_path: Path,
) -> None:
    artifact = tmp_path / "data" / "bronze" / "source-1" / "artifact.json"

    artifact.parent.mkdir(parents=True)

    artifact.write_text(
        '{"records": 3}\n',
        encoding="utf-8",
    )

    artifact_sha256 = hashlib.sha256(artifact.read_bytes()).hexdigest()

    manifest = artifact.parent / "manifest.json"

    manifest.write_text(
        json.dumps(
            {
                "source_id": "source-1",
                "artifact_path": str(artifact.relative_to(tmp_path)),
                "artifact_sha256": (artifact_sha256),
            }
        ),
        encoding="utf-8",
    )

    contract_root = tmp_path / "docs" / "data_contracts"

    contract_root.mkdir(parents=True)

    (contract_root / "source_snapshot_bootstrap.json").write_text(
        json.dumps(
            {
                "exact_candidates": [
                    {
                        "source_id": "source-1",
                        "path": str(manifest),
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    report = build_snapshot_bootstrap_review(
        tmp_path,
        write_contract=False,
        write_packets=False,
    )

    assert report["candidate_count"] == 1

    assert report["review_ready_count"] == 1

    assert report["violation_count"] == 0

    assert report["registration_execution_count"] == 0

    assert report["registration_permitted"] is False

    packet = report["packets"][0]

    assert packet["declared_checksum_match_count"] == 1


def test_missing_artifact_blocks_review(
    tmp_path: Path,
) -> None:
    manifest = tmp_path / "manifest.json"

    manifest.write_text(
        json.dumps(
            {
                "source_id": "source-1",
                "artifact_path": ("data/missing.json"),
            }
        ),
        encoding="utf-8",
    )

    contract_root = tmp_path / "docs" / "data_contracts"

    contract_root.mkdir(parents=True)

    (contract_root / "source_snapshot_bootstrap.json").write_text(
        json.dumps(
            {
                "exact_candidates": [
                    {
                        "source_id": "source-1",
                        "path": str(manifest),
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    report = build_snapshot_bootstrap_review(
        tmp_path,
        write_contract=False,
        write_packets=False,
    )

    assert report["review_ready_count"] == 0

    assert report["blocked_review_count"] == 1

    assert report["violation_count"] >= 1


def test_source_mismatch_blocks_review(
    tmp_path: Path,
) -> None:
    manifest = tmp_path / "manifest.json"

    manifest.write_text(
        json.dumps({"source_id": "wrong-source"}),
        encoding="utf-8",
    )

    contract_root = tmp_path / "docs" / "data_contracts"

    contract_root.mkdir(parents=True)

    (contract_root / "source_snapshot_bootstrap.json").write_text(
        json.dumps(
            {
                "exact_candidates": [
                    {
                        "source_id": "source-1",
                        "path": str(manifest),
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    report = build_snapshot_bootstrap_review(
        tmp_path,
        write_contract=False,
        write_packets=False,
    )

    assert report["review_ready_count"] == 0

    assert any(
        violation["violation"] == "manifest_source_id_mismatch"
        for violation in report["violations"]
    )


def test_checksum_field_is_not_treated_as_path(
    tmp_path: Path,
) -> None:
    artifact = tmp_path / "data" / "artifact.json"

    artifact.parent.mkdir(parents=True)

    artifact.write_text(
        '{"ok": true}\n',
        encoding="utf-8",
    )

    artifact_sha256 = hashlib.sha256(artifact.read_bytes()).hexdigest()

    manifest = tmp_path / "manifest.json"

    manifest.write_text(
        json.dumps(
            {
                "source_id": "source-1",
                "artifact_path": str(artifact.relative_to(tmp_path)),
                "artifact_sha256": (artifact_sha256),
            }
        ),
        encoding="utf-8",
    )

    contract_root = tmp_path / "docs" / "data_contracts"

    contract_root.mkdir(parents=True)

    (contract_root / "source_snapshot_bootstrap.json").write_text(
        json.dumps(
            {
                "exact_candidates": [
                    {
                        "source_id": "source-1",
                        "path": str(manifest),
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    report = build_snapshot_bootstrap_review(
        tmp_path,
        write_contract=False,
        write_packets=False,
    )

    packet = report["packets"][0]

    assert packet["declared_path_count"] == 1

    assert packet["referenced_artifact_count"] == 1

    assert packet["declared_checksum_count"] == 1

    assert packet["declared_checksum_match_count"] == 1

    assert packet["violations"] == []

    assert packet["review_ready"] is True
