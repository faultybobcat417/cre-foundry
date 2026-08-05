from __future__ import annotations

import csv
import hashlib
import json
import zipfile
from pathlib import Path

import duckdb
import polars as pl
import pytest

from cre_foundry.odbus_silver import (
    build_latest_odbus_silver,
    parse_employee_count,
    resolve_target_municipality,
)

SOURCE_COLUMNS = [
    "idx",
    "business_name",
    "alt_business_name",
    "business_sector",
    "business_subsector",
    "business_description",
    "business_id_no",
    "licence_number",
    "licence_type",
    "derived_NAICS",
    "source_NAICS_primary",
    "source_NAICS_secondary",
    "NAICS_descr",
    "NAICS_descr2",
    "latitude",
    "longitude",
    "full_address",
    "postal_code",
    "unit",
    "street_no",
    "street_name",
    "street_direction",
    "street_type",
    "city",
    "prov_terr",
    "total_no_employees",
    "status",
    "provider",
    "geo_source",
    "CSDUID",
    "CSDNAME",
    "PRUID",
]


@pytest.mark.parametrize(
    (
        "raw",
        "minimum",
        "maximum",
        "method",
    ),
    [
        ("12", 12, 12, "exact"),
        ("1--4", 1, 4, "range"),
        ("5 to 9", 5, 9, "range"),
        ("500+", 500, None, "lower_bound"),
        ("..", None, None, "unknown"),
    ],
)
def test_employee_parser(
    raw: str,
    minimum: int | None,
    maximum: int | None,
    method: str,
) -> None:
    result = parse_employee_count(raw)

    assert result["minimum"] == minimum
    assert result["maximum"] == maximum
    assert result["method"] == method


def test_municipality_resolution() -> None:
    assert resolve_target_municipality(
        city="Brampton",
        csd_name="Brampton",
    ) == ("brampton", "csd")

    assert resolve_target_municipality(
        city="Mississauga",
        csd_name="..",
    ) == (
        "mississauga",
        "city_fallback",
    )

    assert resolve_target_municipality(
        city="Brampton",
        csd_name="Mississauga",
    ) == (None, "conflict")


def _row(
    **values: str,
) -> dict[str, str]:
    row = {column: ".." for column in SOURCE_COLUMNS}

    row.update(
        {
            "business_name": "Example",
            "derived_NAICS": "54",
            "source_NAICS_primary": "541611",
            "latitude": "43.70",
            "longitude": "-79.80",
            "full_address": "1 Main St",
            "postal_code": "L6T1A1",
            "street_no": "1",
            "street_name": "Main",
            "street_type": "St",
            "prov_terr": "ON",
            "total_no_employees": "5 to 9",
            "status": "Active",
            "provider": "Fixture",
            "geo_source": "Source",
            "CSDUID": "3521010",
            "PRUID": "35",
        }
    )

    row.update(values)

    return row


def _build_fixture(
    tmp_path: Path,
) -> None:
    run_directory = (
        tmp_path / "data" / "bronze" / "statscan_odbus_2023" / "2026" / "07" / "26" / "RUN-TEST"
    )

    run_directory.mkdir(parents=True)

    archive_path = run_directory / "fixture.zip"

    csv_path = tmp_path / "fixture.csv"

    with csv_path.open(
        "w",
        encoding="utf-8",
        newline="",
    ) as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=SOURCE_COLUMNS,
        )

        writer.writeheader()

        writer.writerow(
            _row(
                idx="1",
                business_name="Brampton A",
                city="Brampton",
                CSDNAME="Brampton",
            )
        )

        writer.writerow(
            _row(
                idx="2",
                business_name="Mississauga B",
                city="Mississauga",
                CSDNAME="..",
                PRUID="..",
            )
        )

        writer.writerow(
            _row(
                idx="3",
                business_name="Conflict C",
                city="Brampton",
                CSDNAME="Mississauga",
            )
        )

        writer.writerow(
            _row(
                idx="4",
                business_name="Calgary D",
                city="Calgary",
                CSDNAME="Calgary",
                prov_terr="AB",
                PRUID="48",
            )
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

        archive.write(
            csv_path,
            "ODBus_v1/ODBus_v1.csv",
        )

    csv_path.unlink()

    digest = hashlib.sha256(archive_path.read_bytes()).hexdigest()

    manifest = {
        "archive_path": str(archive_path.relative_to(tmp_path)),
        "archive_sha256": digest,
        "vintage_start": "2022-05-01",
        "vintage_end": "2022-12-31",
        "release_date": "2023-11-28",
    }

    (run_directory / "manifest.json").write_text(json.dumps(manifest))


def test_builds_silver_and_duckdb(
    tmp_path: Path,
) -> None:
    _build_fixture(tmp_path)

    report = build_latest_odbus_silver(tmp_path)

    assert report["source_row_count"] == 4
    assert report["ontario_row_count"] == 3
    assert report["target_candidate_count"] == 3
    assert report["silver_row_count"] == 2
    assert report["quarantined_conflict_count"] == 1

    target_path = tmp_path / report["target_parquet_path"]

    frame = pl.read_parquet(target_path)

    assert set(frame["municipality"].to_list()) == {
        "brampton",
        "mississauga",
    }

    warehouse_path = tmp_path / report["warehouse_path"]

    connection = duckdb.connect(
        str(warehouse_path),
        read_only=True,
    )

    try:
        count = connection.execute(
            """
            SELECT count(*)
            FROM silver.odbus_target_businesses
            """
        ).fetchone()
    finally:
        connection.close()

    assert count is not None
    assert count[0] == 2
