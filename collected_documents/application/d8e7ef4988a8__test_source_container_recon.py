from __future__ import annotations

import gzip
import hashlib
import json
import zipfile
from pathlib import Path

from cre_foundry.source_container_recon import (
    build_source_container_recon,
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
        project / "config" / "source_container_recon.json",
        {
            "policy": {
                "operating_mode": "shadow",
                "read_only": True,
                "checksum_revalidation_required": True,
                "project_boundary_required": True,
                "symlink_allowed": False,
                "zip_central_directory_inspection": True,
                "zip_extraction_enabled": False,
                "gzip_header_inspection": True,
                "gzip_decompression_enabled": False,
                "parser_execution_enabled": False,
                "schema_validation_enabled": False,
                "row_validation_enabled": False,
                "snapshot_registration_enabled": False,
                "automatic_acquisition": False,
                "browser_execution": False,
                "computer_vision_execution": False,
                "opportunity_ranked": False,
                "outreach_eligible": False,
            },
            "limits": {
                "maximum_zip_members": 100,
                "maximum_member_name_length": 1024,
            },
        },
    )


def _packet(
    project: Path,
    artifact: Path,
) -> dict[str, object]:
    checksum = hashlib.sha256(artifact.read_bytes()).hexdigest()

    return {
        "source_id": "source-1",
        "artifacts": [
            {
                "resolved_relative_path": str(artifact.relative_to(project)),
                "probe": {"actual_sha256": (checksum)},
            }
        ],
    }


def test_inventories_zip_without_extracting(
    tmp_path: Path,
) -> None:
    _write_config(tmp_path)

    artifact = tmp_path / "data" / "source.zip"

    artifact.parent.mkdir(parents=True)

    with zipfile.ZipFile(
        artifact,
        mode="w",
    ) as archive:
        archive.writestr(
            "folder/data.csv",
            "a,b\n1,2\n",
        )

    _write_json(
        tmp_path / "docs" / "data_contracts" / "source_snapshot_admission.json",
        {
            "packets": [
                _packet(
                    tmp_path,
                    artifact,
                )
            ]
        },
    )

    report = build_source_container_recon(
        tmp_path,
        write_contracts=False,
    )

    inventory = report["inventory"]

    assert inventory["zip_container_count"] == 1

    assert inventory["recon_ready_count"] == 1

    entry = inventory["entries"][0]

    assert entry["inventory"]["member_count"] == 1

    assert entry["format_candidates"] == ["zip_csv_members"]

    assert entry["archive_extraction_performed"] is False


def test_rejects_unsafe_zip_member_name(
    tmp_path: Path,
) -> None:
    _write_config(tmp_path)

    artifact = tmp_path / "data" / "unsafe.zip"

    artifact.parent.mkdir(parents=True)

    with zipfile.ZipFile(
        artifact,
        mode="w",
    ) as archive:
        archive.writestr(
            "../escape.csv",
            "x\n1\n",
        )

    _write_json(
        tmp_path / "docs" / "data_contracts" / "source_snapshot_admission.json",
        {
            "packets": [
                _packet(
                    tmp_path,
                    artifact,
                )
            ]
        },
    )

    report = build_source_container_recon(
        tmp_path,
        write_contracts=False,
    )

    entry = report["inventory"]["entries"][0]

    assert entry["container_recon_ready"] is False

    assert "unsafe_zip_member_paths" in entry["violations"]


def test_reads_gzip_metadata_without_decompressing(
    tmp_path: Path,
) -> None:
    _write_config(tmp_path)

    artifact = tmp_path / "data" / "records.geojson.gz"

    artifact.parent.mkdir(parents=True)

    artifact.write_bytes(gzip.compress(b'{"type":"FeatureCollection","features":[]}'))

    _write_json(
        tmp_path / "docs" / "data_contracts" / "source_snapshot_admission.json",
        {
            "packets": [
                _packet(
                    tmp_path,
                    artifact,
                )
            ]
        },
    )

    report = build_source_container_recon(
        tmp_path,
        write_contracts=False,
    )

    inventory = report["inventory"]

    assert inventory["gzip_container_count"] == 1

    assert inventory["gzip_decompression_execution_count"] == 0

    entry = inventory["entries"][0]

    assert entry["format_candidates"] == ["gzip_geojson"]

    assert entry["gzip_decompression_performed"] is False


def test_detects_checksum_change(
    tmp_path: Path,
) -> None:
    _write_config(tmp_path)

    artifact = tmp_path / "data" / "records.json.gz"

    artifact.parent.mkdir(parents=True)

    artifact.write_bytes(gzip.compress(b"{}"))

    packet = _packet(
        tmp_path,
        artifact,
    )

    artifact.write_bytes(gzip.compress(b'{"changed":true}'))

    _write_json(
        tmp_path / "docs" / "data_contracts" / "source_snapshot_admission.json",
        {"packets": [packet]},
    )

    report = build_source_container_recon(
        tmp_path,
        write_contracts=False,
    )

    entry = report["inventory"]["entries"][0]

    assert "artifact_checksum_changed" in entry["violations"]
