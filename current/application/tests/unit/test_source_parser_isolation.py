from __future__ import annotations

import gzip
import hashlib
import json
from pathlib import Path

from cre_foundry.source_parser_isolation import (
    build_source_parser_isolation,
)


def _stable_hash(
    value: object,
) -> str:
    return hashlib.sha256(
        json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()


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


def test_parser_isolation_blocks_database_apis(
    tmp_path: Path,
) -> None:
    parser_source = tmp_path / "src" / "cre_foundry" / "source_parser_contracts.py"

    parser_source.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    installed_source = (
        Path(__file__).resolve().parents[2] / "src" / "cre_foundry" / "source_parser_contracts.py"
    )

    parser_source.write_text(
        installed_source.read_text(encoding="utf-8"),
        encoding="utf-8",
    )

    artifact = tmp_path / "data" / "bronze" / "test-source" / "records.geojson.gz"

    artifact.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    artifact.write_bytes(
        gzip.compress(
            json.dumps(
                {
                    "features": [
                        {
                            "attributes": {"id": 1},
                            "geometry": None,
                        }
                    ]
                }
            ).encode("utf-8")
        )
    )

    fields = [
        "__geometry_present",
        "id",
    ]

    contracts = []

    for index in range(3):
        contracts.append(
            {
                "source_id": (f"source-{index}"),
                "artifact_path": str(artifact.relative_to(tmp_path)),
                "artifact_sha256": hashlib.sha256(artifact.read_bytes()).hexdigest(),
                "parser_type": ("gzip_json_feature_collection"),
                "encoding": "utf-8",
                "record_path": "$.features",
                "expected_record_count": 1,
                "expected_schema_fingerprint": (_stable_hash(fields)),
                "expected_fields": fields,
            }
        )

    _write_json(
        tmp_path / "config" / "source_parser_contracts.json",
        {
            "policy": {
                "operating_mode": "shadow",
                "authoritative_artifacts_read_only": True,
                "checksum_revalidation_required": True,
                "exact_schema_required": True,
                "exact_record_count_required": True,
                "double_run_reproducibility_required": True,
                "raw_value_export_enabled": False,
                "warehouse_write_enabled": False,
                "operations_database_write_enabled": False,
                "snapshot_registration_enabled": False,
                "automatic_parser_approval": False,
                "automatic_schema_approval": False,
                "model_training_enabled": False,
                "production_ranking_enabled": False,
                "outreach_enabled": False,
            },
            "contracts": contracts,
        },
    )

    report = build_source_parser_isolation(
        tmp_path,
        write_contracts=False,
    )

    assert report["static_scan"]["static_isolation_passed"] is True

    assert report["artifact_boundary_scan"]["artifact_boundary_passed"] is True

    assert report["runtime_guard_passed"] is True

    assert report["guarded_parser_execution_count"] == 6

    assert report["authoritative_database_connection_count"] == 0

    assert report["authoritative_database_write_count"] == 0


def test_parser_contracts_cannot_target_database_file(
    tmp_path: Path,
) -> None:
    parser_source = tmp_path / "src" / "cre_foundry" / "source_parser_contracts.py"

    parser_source.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    installed_source = (
        Path(__file__).resolve().parents[2] / "src" / "cre_foundry" / "source_parser_contracts.py"
    )

    parser_source.write_text(
        installed_source.read_text(encoding="utf-8"),
        encoding="utf-8",
    )

    database = tmp_path / "data" / "control" / "operations.sqlite3"

    database.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    database.write_bytes(b"not-a-parser-artifact")

    _write_json(
        tmp_path / "config" / "source_parser_contracts.json",
        {
            "policy": {
                "operating_mode": "shadow",
                "authoritative_artifacts_read_only": True,
                "checksum_revalidation_required": True,
                "exact_schema_required": True,
                "exact_record_count_required": True,
                "double_run_reproducibility_required": True,
                "raw_value_export_enabled": False,
                "warehouse_write_enabled": False,
                "operations_database_write_enabled": False,
                "snapshot_registration_enabled": False,
                "automatic_parser_approval": False,
                "automatic_schema_approval": False,
                "model_training_enabled": False,
                "production_ranking_enabled": False,
                "outreach_enabled": False,
            },
            "contracts": [
                {
                    "source_id": "bad-source",
                    "artifact_path": str(database.relative_to(tmp_path)),
                }
            ],
        },
    )

    try:
        build_source_parser_isolation(
            tmp_path,
            write_contracts=False,
        )

    except RuntimeError as error:
        assert "artifact boundaries" in str(error).lower()

    else:
        raise AssertionError("Database artifact path did not fail closed.")
