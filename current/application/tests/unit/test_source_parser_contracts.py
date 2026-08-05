from __future__ import annotations

import gzip
import hashlib
import json
import zipfile
from pathlib import Path

from cre_foundry.source_parser_contracts import (
    build_source_parser_contracts,
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


def _policy() -> dict[str, object]:
    return {
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
    }


def test_validates_json_and_csv_twice(
    tmp_path: Path,
) -> None:
    json_artifact = tmp_path / "data" / "records.geojson.gz"

    json_artifact.parent.mkdir(parents=True)

    json_artifact.write_bytes(
        gzip.compress(
            json.dumps(
                {
                    "features": [
                        {
                            "attributes": {
                                "id": 1,
                                "name": "A",
                            },
                            "geometry": {"x": 1},
                        },
                        {
                            "attributes": {
                                "id": 2,
                                "name": "B",
                            },
                            "geometry": None,
                        },
                    ]
                }
            ).encode("utf-8-sig")
        )
    )

    csv_artifact = tmp_path / "data" / "records.zip"

    with zipfile.ZipFile(
        csv_artifact,
        mode="w",
    ) as archive:
        archive.writestr(
            "records.csv",
            "id,name\n1,A\n2,B\n",
        )

    json_fields = [
        "__geometry_present",
        "id",
        "name",
    ]

    csv_fields = [
        "id",
        "name",
    ]

    _write_json(
        tmp_path / "config" / "source_parser_contracts.json",
        {
            "policy": _policy(),
            "contracts": [
                {
                    "source_id": "json-source",
                    "artifact_path": str(json_artifact.relative_to(tmp_path)),
                    "artifact_sha256": hashlib.sha256(json_artifact.read_bytes()).hexdigest(),
                    "parser_type": ("gzip_json_feature_collection"),
                    "encoding": "utf-8-sig",
                    "record_path": "$.features",
                    "expected_record_count": 2,
                    "expected_schema_fingerprint": (_stable_hash(json_fields)),
                    "expected_fields": (json_fields),
                },
                {
                    "source_id": "csv-source",
                    "artifact_path": str(csv_artifact.relative_to(tmp_path)),
                    "artifact_sha256": hashlib.sha256(csv_artifact.read_bytes()).hexdigest(),
                    "parser_type": ("zip_csv_member"),
                    "encoding": "utf-8-sig",
                    "archive_member": ("records.csv"),
                    "delimiter": ",",
                    "expected_record_count": 2,
                    "expected_schema_fingerprint": (_stable_hash(csv_fields)),
                    "expected_fields": (csv_fields),
                },
            ],
        },
    )

    result = build_source_parser_contracts(
        tmp_path,
        write_contracts=False,
    )

    report = result["validation"]

    assert report["contract_count"] == 2

    assert report["validation_complete_count"] == 2

    assert report["reproducibility_match_count"] == 2

    assert report["parser_execution_count"] == 4

    assert report["parser_contract_approval_count"] == 0


def test_schema_mismatch_fails_closed(
    tmp_path: Path,
) -> None:
    artifact = tmp_path / "data" / "records.geojson.gz"

    artifact.parent.mkdir(parents=True)

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

    _write_json(
        tmp_path / "config" / "source_parser_contracts.json",
        {
            "policy": _policy(),
            "contracts": [
                {
                    "source_id": "json-source",
                    "artifact_path": str(artifact.relative_to(tmp_path)),
                    "artifact_sha256": hashlib.sha256(artifact.read_bytes()).hexdigest(),
                    "parser_type": ("gzip_json_feature_collection"),
                    "encoding": "utf-8",
                    "record_path": "$.features",
                    "expected_record_count": 1,
                    "expected_schema_fingerprint": ("incorrect"),
                    "expected_fields": [
                        "__geometry_present",
                        "id",
                    ],
                }
            ],
        },
    )

    result = build_source_parser_contracts(
        tmp_path,
        write_contracts=False,
    )

    validation = result["validation"]["validations"][0]

    assert validation["validation_complete"] is False

    assert "schema_fingerprint_mismatch" in validation["first_run"]["validation_errors"]


def test_checksum_change_raises(
    tmp_path: Path,
) -> None:
    artifact = tmp_path / "data" / "records.geojson.gz"

    artifact.parent.mkdir(parents=True)

    artifact.write_bytes(gzip.compress(b'{"features":[]}'))

    wrong_hash = "0" * 64

    _write_json(
        tmp_path / "config" / "source_parser_contracts.json",
        {
            "policy": _policy(),
            "contracts": [
                {
                    "source_id": "json-source",
                    "artifact_path": str(artifact.relative_to(tmp_path)),
                    "artifact_sha256": wrong_hash,
                    "parser_type": ("gzip_json_feature_collection"),
                    "encoding": "utf-8",
                    "record_path": "$.features",
                    "expected_record_count": 0,
                    "expected_schema_fingerprint": (_stable_hash([])),
                    "expected_fields": [],
                }
            ],
        },
    )

    try:
        build_source_parser_contracts(
            tmp_path,
            write_contracts=False,
        )

    except RuntimeError as error:
        assert "Checksum mismatch" in str(error)

    else:
        raise AssertionError("Checksum mismatch did not fail closed.")
