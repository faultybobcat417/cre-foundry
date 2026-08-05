from __future__ import annotations

import gzip
import hashlib
import json
import zipfile
from pathlib import Path

from cre_foundry.bounded_parser_probe import (
    build_bounded_parser_probe,
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
        project / "config" / "bounded_parser_probe.json",
        {
            "policy": {
                "operating_mode": "shadow",
                "read_only": True,
                "checksum_revalidation_required": True,
                "project_boundary_required": True,
                "symlink_allowed": False,
                "bounded_stream_reads_enabled": True,
                "bounded_in_memory_decompression_enabled": True,
                "archive_extraction_enabled": False,
                "full_decompression_enabled": False,
                "full_parser_execution_enabled": False,
                "schema_mutation_enabled": False,
                "row_materialization_enabled": False,
                "automatic_parser_approval": False,
                "snapshot_registration_enabled": False,
                "automatic_acquisition": False,
                "browser_execution": False,
                "computer_vision_execution": False,
                "opportunity_ranked": False,
                "outreach_eligible": False,
            },
            "limits": {
                "maximum_gzip_prefix_bytes": 524288,
                "maximum_zip_member_prefix_bytes": 131072,
                "maximum_zip_members_probed": 100,
                "maximum_member_compression_ratio": 1000.0,
                "maximum_detected_columns": 500,
                "maximum_detected_json_keys": 500,
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
                "probe": {"actual_sha256": checksum},
            }
        ],
    }


def _container(
    project: Path,
    artifact: Path,
    container_type: str,
) -> dict[str, object]:
    return {
        "source_id": "source-1",
        "artifact_path": str(artifact.relative_to(project)),
        "container_type": (container_type),
        "container_recon_ready": True,
    }


def test_probes_gzip_geojson_prefix(
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

    _write_json(
        tmp_path / "docs" / "data_contracts" / "source_container_inventory.json",
        {
            "entries": [
                _container(
                    tmp_path,
                    artifact,
                    "gzip",
                )
            ]
        },
    )

    report = build_bounded_parser_probe(
        tmp_path,
        write_contracts=False,
    )

    probe = report["probe"]
    entry = probe["entries"][0]

    assert probe["probe_completed_count"] == 1

    assert entry["recognized_formats"] == ["geojson_feature_collection"]

    assert entry["probe_result"]["bounded_decompression_performed"] is True

    assert entry["full_decompression_performed"] is False

    assert entry["full_parser_execution_performed"] is False


def test_probes_zip_csv_without_extraction(
    tmp_path: Path,
) -> None:
    _write_config(tmp_path)

    artifact = tmp_path / "data" / "records.zip"

    artifact.parent.mkdir(parents=True)

    with zipfile.ZipFile(
        artifact,
        mode="w",
    ) as archive:
        archive.writestr(
            "records.csv",
            "id,name\n1,Example\n",
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

    _write_json(
        tmp_path / "docs" / "data_contracts" / "source_container_inventory.json",
        {
            "entries": [
                _container(
                    tmp_path,
                    artifact,
                    "zip",
                )
            ]
        },
    )

    report = build_bounded_parser_probe(
        tmp_path,
        write_contracts=False,
    )

    entry = report["probe"]["entries"][0]

    member = entry["probe_result"]["members"][0]

    assert entry["recognized_formats"] == ["delimited_text"]

    assert member["classification"]["delimited_evidence"]["header_columns"] == [
        "id",
        "name",
    ]

    assert entry["archive_extraction_performed"] is False


def test_checksum_change_blocks_probe(
    tmp_path: Path,
) -> None:
    _write_config(tmp_path)

    artifact = tmp_path / "data" / "records.geojson.gz"

    artifact.parent.mkdir(parents=True)

    artifact.write_bytes(gzip.compress(b'{"type":"FeatureCollection","features":[]}'))

    packet = _packet(
        tmp_path,
        artifact,
    )

    artifact.write_bytes(gzip.compress(b'{"changed":true}'))

    _write_json(
        tmp_path / "docs" / "data_contracts" / "source_snapshot_admission.json",
        {"packets": [packet]},
    )

    _write_json(
        tmp_path / "docs" / "data_contracts" / "source_container_inventory.json",
        {
            "entries": [
                _container(
                    tmp_path,
                    artifact,
                    "gzip",
                )
            ]
        },
    )

    report = build_bounded_parser_probe(
        tmp_path,
        write_contracts=False,
    )

    entry = report["probe"]["entries"][0]

    assert "artifact_checksum_changed" in entry["integrity_violations"]

    assert entry["probe_completed"] is False
