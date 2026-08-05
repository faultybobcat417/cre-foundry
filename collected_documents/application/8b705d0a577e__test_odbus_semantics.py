from __future__ import annotations

import hashlib
import json
import zipfile
from pathlib import Path

import pytest

from cre_foundry.odbus_semantics import (
    profile_latest_odbus_values,
)

HEADER = (
    "business_name,derived_NAICS,"
    "source_NAICS_primary,latitude,"
    "longitude,city,prov_terr,"
    "total_no_employees,status,"
    "provider,geo_source,CSDNAME,PRUID\n"
)


def build_fixture(
    tmp_path: Path,
    *,
    missing_columns: bool = False,
) -> None:
    run_directory = (
        tmp_path / "data" / "bronze" / "statscan_odbus_2023" / "2026" / "07" / "26" / "RUN-TEST"
    )

    run_directory.mkdir(
        parents=True,
    )

    archive_path = run_directory / "fixture.zip"

    if missing_columns:
        data = "business_name,city\nExample,Brampton\n"
    else:
        data = HEADER + (
            "A,54,541611,43.70,-79.80,"
            "Brampton,ON,10,Active,"
            "Provider A,Address,Brampton,35\n"
            "B,44,445110,bad,-79.60,"
            "Mississauga,ON,1-4,Inactive,"
            "Provider A,Address,Mississauga,35\n"
            "C,54,541611,43.65,-79.38,"
            "Toronto,ON,,Active,"
            "Provider B,Parcel,Toronto,35\n"
            "D,23,236110,51.05,-114.07,"
            "Calgary,AB,20,Active,"
            "Provider C,Address,Calgary,48\n"
            "E,54,541611,43.70,-79.80,"
            "Brampton,ON,8,Active,"
            "Provider A,Address,Brampton,48\n"
        )

    with zipfile.ZipFile(
        archive_path,
        mode="w",
        compression=zipfile.ZIP_DEFLATED,
    ) as archive:
        archive.writestr(
            "ODBus_v1/ODBus-record-layout.csv",
            (
                "Field name,Data type,"
                "Description,Field type\n"
                "business_name,text,"
                "Business name,source\n"
            ),
        )

        archive.writestr(
            "ODBus_v1/ODBus_v1.csv",
            data,
        )

    digest = hashlib.sha256(archive_path.read_bytes()).hexdigest()

    manifest = {
        "archive_path": str(archive_path.relative_to(tmp_path)),
        "archive_sha256": digest,
    }

    (run_directory / "manifest.json").write_text(json.dumps(manifest))


def test_profiles_ontario_and_target_alignment(
    tmp_path: Path,
) -> None:
    build_fixture(tmp_path)

    report = profile_latest_odbus_values(tmp_path)

    alignment = report["province_alignment"]

    assert alignment["ontario_by_prov_terr"] == 4
    assert alignment["ontario_by_pruid"] == 3
    assert alignment["ontario_intersection"] == 3
    assert alignment["prov_terr_pruid_disagreements"] == 1

    target = report["target_market"]

    assert target["union_ontario_intersection"] == 2

    assert target["city_csd_target_conflicts"] == 0


def test_profiles_invalid_numeric_values(
    tmp_path: Path,
) -> None:
    build_fixture(tmp_path)

    report = profile_latest_odbus_values(tmp_path)

    assert report["coordinate_quality"]["latitude"]["invalid_count"] == 1

    assert report["employee_field"]["non_integer_count"] == 1


def test_rejects_missing_required_columns(
    tmp_path: Path,
) -> None:
    build_fixture(
        tmp_path,
        missing_columns=True,
    )

    with pytest.raises(
        RuntimeError,
        match="missing required columns",
    ):
        profile_latest_odbus_values(tmp_path)
