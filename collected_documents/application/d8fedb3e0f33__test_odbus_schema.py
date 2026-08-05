from __future__ import annotations

import hashlib
import json
import zipfile
from pathlib import Path

import pytest

from cre_foundry.odbus_schema import (
    inspect_latest_odbus_schema,
)


def build_fixture(
    tmp_path: Path,
    *,
    valid_hash: bool = True,
) -> Path:
    run_directory = (
        tmp_path / "data" / "bronze" / "statscan_odbus_2023" / "2026" / "07" / "26" / "RUN-TEST"
    )

    run_directory.mkdir(
        parents=True,
    )

    archive_path = run_directory / "fixture.zip"

    with zipfile.ZipFile(
        archive_path,
        mode="w",
        compression=zipfile.ZIP_DEFLATED,
    ) as archive:
        archive.writestr(
            "ODBus_v1/ODBus-record-layout.csv",
            (
                "Variable,Description\n"
                "business_name,Business name\n"
                "city,City name\n"
                "latitude,Latitude\n"
            ),
        )

        archive.writestr(
            "ODBus_v1/ODBus_v1.csv",
            (
                "business_name,city,latitude\n"
                "Example One,Brampton,43.70\n"
                "Example Two,Mississauga,43.59\n"
            ),
        )

    digest = hashlib.sha256(archive_path.read_bytes()).hexdigest()

    manifest = {
        "archive_path": str(archive_path.relative_to(tmp_path)),
        "archive_sha256": (digest if valid_hash else "0" * 64),
    }

    (run_directory / "manifest.json").write_text(json.dumps(manifest))

    return archive_path


def test_profiles_actual_csv_schema(
    tmp_path: Path,
) -> None:
    build_fixture(tmp_path)

    report = inspect_latest_odbus_schema(tmp_path)

    assert report["row_count"] == 2
    assert report["column_count"] == 3
    assert report["columns"] == [
        "business_name",
        "city",
        "latitude",
    ]

    profiles = {item["name"]: item for item in report["column_profiles"]}

    assert profiles["latitude"]["candidate_type"] == "numeric-like"

    assert report["record_layout"]["row_count"] == 3


def test_rejects_manifest_hash_mismatch(
    tmp_path: Path,
) -> None:
    build_fixture(
        tmp_path,
        valid_hash=False,
    )

    with pytest.raises(
        RuntimeError,
        match="hash does not match",
    ):
        inspect_latest_odbus_schema(tmp_path)
