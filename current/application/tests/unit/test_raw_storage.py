from __future__ import annotations

import gzip
from datetime import UTC, datetime
from pathlib import Path

import orjson

from cre_foundry.raw_storage import write_layer_snapshot


def test_layer_snapshot_is_immutable_and_hashed(
    tmp_path: Path,
) -> None:
    metadata = {
        "id": 1,
        "name": "Development Apps",
        "objectIdField": "OBJECTID",
        "geometryType": "esriGeometryPolygon",
        "fields": [
            {
                "name": "OBJECTID",
                "alias": "OBJECTID",
                "type": "esriFieldTypeOID",
            }
        ],
    }

    collection = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "properties": {"OBJECTID": 1},
                "geometry": None,
            }
        ],
    }

    timestamp = datetime(
        2026,
        7,
        25,
        12,
        0,
        tzinfo=UTC,
    )

    snapshot = write_layer_snapshot(
        project_root=tmp_path,
        source_id="test_source",
        run_id="test-run",
        layer_id=1,
        collected_at=timestamp,
        as_of_timestamp=timestamp,
        layer_metadata=metadata,
        feature_collection=collection,
    )

    saved_path = tmp_path / snapshot.raw_path

    assert saved_path.exists()
    assert snapshot.record_count == 1
    assert len(snapshot.sha256) == 64
    assert len(snapshot.schema_fingerprint) == 64

    with gzip.open(saved_path, "rb") as handle:
        saved_payload = orjson.loads(handle.read())

    assert saved_payload == collection
