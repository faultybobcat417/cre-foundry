from __future__ import annotations

import gzip
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

import duckdb
import orjson

from cre_foundry.brampton_business_directory_silver import (
    build_brampton_business_directory_silver,
    employee_bounds,
)


def test_parses_employee_groups() -> None:
    assert employee_bounds("1-4") == (
        1,
        4,
    )

    assert employee_bounds("500+") == (
        500,
        None,
    )

    assert employee_bounds(None) == (
        None,
        None,
    )


def test_builds_business_directory_silver(
    tmp_path: Path,
) -> None:
    run_id = "RUN-directory-fixture"

    as_of = datetime(
        2026,
        7,
        26,
        tzinfo=UTC,
    )

    raw_relative = (
        Path("data")
        / "bronze"
        / "brampton_business_directory"
        / "2026"
        / "07"
        / "26"
        / run_id
        / "layer_0_fixture.geojson.gz"
    )

    raw_path = tmp_path / raw_relative

    raw_path.parent.mkdir(parents=True)

    features = [
        {
            "type": "Feature",
            "properties": {
                "OBJECTID": 1,
                "GLOBALID": "{GLOBAL-1}",
                "COMPANY_NAME": "Business One",
                "BUSINESS_FULL_ADDRESS": ("1 Test Road, Brampton, ON"),
                "UNIT": None,
                "STREET_NUM": "1",
                "STREET_NAME": "Test",
                "STREET_TYPE": "Road",
                "STREET_DIRECTION": None,
                "CITY": "Brampton",
                "PROVINCE": "ON",
                "POSTAL_CODE": "L6T 1A1",
                "PHONE": "905-555-0001",
                "WEBURL": "https://example.test",
                "FAX": None,
                "DATE_EST_IN_CITY": "2020",
                "STARTED_IN_CITY": "YES",
                "HEAD_OFFICE_LOCATION": "Brampton",
                "TOTAL_EMPLOYEE_GROUPED": "1-4",
                "GFA_SQUARE_FEET": "10,000",
                "GFA_SQUARE_METER": 929,
                "NAICS_DETAIL": "Manufacturing",
                "NAIC_2": "31",
                "NAIC_3": "311",
                "NAIC_4": "3111",
                "NAIC_6": "311111",
                "OPERATIONAL": "YES",
                "PRODUCT_DESC": "Test products",
                "FACEBOOK": None,
                "TWITTER": None,
                "YOUTUBE": None,
                "INSTAGRAM": None,
                "OTHER_SOCIALS": None,
            },
            "geometry": {
                "type": "Point",
                "coordinates": [
                    -79.8,
                    43.7,
                ],
            },
        },
        {
            "type": "Feature",
            "properties": {
                "OBJECTID": 2,
                "GLOBALID": "{GLOBAL-2}",
                "COMPANY_NAME": "Business Two",
                "BUSINESS_FULL_ADDRESS": ("2 Test Road, Unit 7, Brampton, ON"),
                "UNIT": "7",
                "STREET_NUM": "2",
                "STREET_NAME": "Test",
                "STREET_TYPE": "Road",
                "STREET_DIRECTION": None,
                "CITY": "Brampton",
                "PROVINCE": "ON",
                "POSTAL_CODE": None,
                "PHONE": None,
                "WEBURL": None,
                "FAX": None,
                "DATE_EST_IN_CITY": None,
                "STARTED_IN_CITY": None,
                "HEAD_OFFICE_LOCATION": None,
                "TOTAL_EMPLOYEE_GROUPED": "500+",
                "GFA_SQUARE_FEET": None,
                "GFA_SQUARE_METER": None,
                "NAICS_DETAIL": None,
                "NAIC_2": "48",
                "NAIC_3": None,
                "NAIC_4": None,
                "NAIC_6": None,
                "OPERATIONAL": "YES",
                "PRODUCT_DESC": None,
                "FACEBOOK": None,
                "TWITTER": None,
                "YOUTUBE": None,
                "INSTAGRAM": None,
                "OTHER_SOCIALS": None,
            },
            "geometry": None,
        },
    ]

    collection = {
        "type": "FeatureCollection",
        "features": features,
    }

    raw_bytes = orjson.dumps(
        collection,
        option=orjson.OPT_SORT_KEYS,
    )

    with gzip.open(
        raw_path,
        "wb",
    ) as handle:
        handle.write(raw_bytes)

    snapshot_hash = hashlib.sha256(raw_bytes).hexdigest()

    manifest = {
        "source_id": ("brampton_business_directory"),
        "run_id": run_id,
        "started_at": as_of.isoformat(),
        "completed_at": as_of.isoformat(),
        "as_of_timestamp": as_of.isoformat(),
        "status": "succeeded",
        "service_url": "https://example.test",
        "layer_snapshots": [
            {
                "source_id": ("brampton_business_directory"),
                "run_id": run_id,
                "layer_id": 0,
                "collected_at": as_of.isoformat(),
                "as_of_timestamp": (as_of.isoformat()),
                "raw_path": str(raw_relative),
                "sha256": snapshot_hash,
                "record_count": len(features),
                "schema_fingerprint": "schema",
                "content_type": ("application/geo+json"),
            }
        ],
        "error_type": None,
        "error_message": None,
    }

    (raw_path.parent / "manifest.json").write_text(json.dumps(manifest))

    warehouse_directory = tmp_path / "data" / "warehouse"

    warehouse_directory.mkdir(parents=True)

    duckdb.connect(str(warehouse_directory / "fixture.duckdb")).close()

    report = build_brampton_business_directory_silver(tmp_path)

    assert report["silver_record_count"] == 2

    assert report["duplicate_global_id_count"] == 0

    assert report["directory_operational_count"] == 2

    assert report["outreach_eligible_count"] == 0

    connection = duckdb.connect(
        str(warehouse_directory / "fixture.duckdb"),
        read_only=True,
    )

    try:
        rows = connection.execute(
            """
            SELECT
                global_id,
                normalized_full_address,
                normalized_base_address,
                employee_count_min,
                employee_count_max,
                gfa_square_feet,
                directory_operational_at_snapshot,
                commercial_requirement_verified,
                decision_maker_verified,
                outreach_eligible
            FROM
                silver.brampton_business_directory
            ORDER BY object_id
            """
        ).fetchall()

    finally:
        connection.close()

    assert rows == [
        (
            "{GLOBAL-1}",
            "1 test rd",
            "1 test rd",
            1,
            4,
            10000,
            True,
            False,
            False,
            False,
        ),
        (
            "{GLOBAL-2}",
            "2 test rd unit 7",
            "2 test rd",
            500,
            None,
            None,
            True,
            False,
            False,
            False,
        ),
    ]
