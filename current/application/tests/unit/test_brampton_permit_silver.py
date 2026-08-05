from __future__ import annotations

import gzip
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

import duckdb
import orjson

from cre_foundry.brampton_permit_silver import (
    build_brampton_permit_silver,
)


def epoch_ms(
    value: datetime,
) -> int:
    return int(value.timestamp() * 1000)


def test_builds_permit_silver_and_active_view(
    tmp_path: Path,
) -> None:
    run_id = "RUN-20260726T000000Z-test"
    as_of = datetime(
        2026,
        7,
        26,
        tzinfo=UTC,
    )

    raw_relative = (
        Path("data")
        / "bronze"
        / "brampton_building_permits"
        / "2026"
        / "07"
        / "26"
        / run_id
        / "layer_0_fixture.geojson.gz"
    )

    raw_path = tmp_path / raw_relative
    raw_path.parent.mkdir(parents=True)

    recent = datetime(
        2026,
        7,
        20,
        tzinfo=UTC,
    )

    old = datetime(
        2025,
        1,
        1,
        tzinfo=UTC,
    )

    features = [
        {
            "type": "Feature",
            "properties": {
                "OBJECTID": 1,
                "GIS_ID": 101,
                "FOLDERRSN": 1001,
                "PERMITNUMBER": "26-000001-000-00",
                "ADDRESS": "1 Test St",
                "SUBDESC": "F2: Industrial",
                "WORKDESC": "Interior/Unit Finish",
                "STATUSDESC": "Applied",
                "INDATE": epoch_ms(recent),
                "ISSUEDATE": None,
                "PROCESSDATE": None,
                "EXPIRYDATE": None,
                "BUILDER": None,
                "CONTRACTOR": None,
                "GFA": "10,987.5",
            },
            "geometry": {
                "type": "Point",
                "coordinates": [-79.8, 43.7],
            },
        },
        {
            "type": "Feature",
            "properties": {
                "OBJECTID": 2,
                "GIS_ID": 102,
                "FOLDERRSN": 1002,
                "PERMITNUMBER": "26-000002-P01-01",
                "ADDRESS": "2 Test St",
                "SUBDESC": "F2: Industrial",
                "WORKDESC": "Revision",
                "STATUSDESC": "Applied",
                "INDATE": epoch_ms(recent),
                "ISSUEDATE": None,
                "PROCESSDATE": None,
                "EXPIRYDATE": None,
                "BUILDER": None,
                "CONTRACTOR": None,
                "GFA": 200,
            },
            "geometry": None,
        },
        {
            "type": "Feature",
            "properties": {
                "OBJECTID": 3,
                "GIS_ID": 103,
                "FOLDERRSN": 1003,
                "PERMITNUMBER": "26-000003-000-00",
                "ADDRESS": "3 Test St",
                "SUBDESC": "F1: Industrial",
                "WORKDESC": "Addition - Complete",
                "STATUSDESC": "Closed",
                "INDATE": epoch_ms(recent),
                "ISSUEDATE": epoch_ms(recent),
                "PROCESSDATE": None,
                "EXPIRYDATE": None,
                "BUILDER": None,
                "CONTRACTOR": None,
                "GFA": 300,
            },
            "geometry": None,
        },
        {
            "type": "Feature",
            "properties": {
                "OBJECTID": 4,
                "GIS_ID": 104,
                "FOLDERRSN": 1004,
                "PERMITNUMBER": "26-000004-000-00",
                "ADDRESS": "4 Test St",
                "SUBDESC": "F3: Industrial",
                "WORKDESC": "Change of Use",
                "STATUSDESC": "Issued",
                "INDATE": epoch_ms(old),
                "ISSUEDATE": epoch_ms(old),
                "PROCESSDATE": None,
                "EXPIRYDATE": None,
                "BUILDER": None,
                "CONTRACTOR": None,
                "GFA": None,
            },
            "geometry": None,
        },
        {
            "type": "Feature",
            "properties": {
                "OBJECTID": 5,
                "GIS_ID": 105,
                "FOLDERRSN": 1005,
                "PERMITNUMBER": "26-000005-000-00",
                "ADDRESS": "5 Test St",
                "SUBDESC": "F2: Industrial",
                "WORKDESC": "Alteration (Renovation)",
                "STATUSDESC": "Revoked",
                "INDATE": epoch_ms(recent),
                "ISSUEDATE": None,
                "PROCESSDATE": None,
                "EXPIRYDATE": None,
                "BUILDER": None,
                "CONTRACTOR": None,
                "GFA": None,
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
        "source_id": ("brampton_building_permits"),
        "run_id": run_id,
        "started_at": as_of.isoformat(),
        "completed_at": as_of.isoformat(),
        "as_of_timestamp": as_of.isoformat(),
        "status": "succeeded",
        "service_url": "https://example.test",
        "layer_snapshots": [
            {
                "source_id": ("brampton_building_permits"),
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

    manifest_path = raw_path.parent / "manifest.json"

    manifest_path.write_text(json.dumps(manifest))

    warehouse_directory = tmp_path / "data" / "warehouse"

    warehouse_directory.mkdir(parents=True)

    duckdb.connect(str(warehouse_directory / "fixture.duckdb")).close()

    report = build_brampton_permit_silver(tmp_path)

    assert report["silver_record_count"] == 5
    assert report["active_90_day_signal_count"] == 1
    assert report["unknown_lifecycle_count"] == 0
    assert report["outreach_eligible_count"] == 0

    connection = duckdb.connect(
        str(warehouse_directory / "fixture.duckdb"),
        read_only=True,
    )

    try:
        active = connection.execute(
            """
            SELECT
                permit_number,
                event_type,
                lifecycle_stage,
                gfa
            FROM
                silver.brampton_active_permit_signals
            """
        ).fetchall()
    finally:
        connection.close()

    assert active == [
        (
            "26-000001-000-00",
            "tenant_fitout",
            "application",
            10987.5,
        )
    ]
