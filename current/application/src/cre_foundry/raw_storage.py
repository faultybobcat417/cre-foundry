from __future__ import annotations

import gzip
import hashlib
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import orjson

from cre_foundry.source_contracts import SnapshotRecord, SourceRunManifest


def utc_now() -> datetime:
    return datetime.now(UTC)


def canonical_json_bytes(payload: Any) -> bytes:
    return orjson.dumps(payload, option=orjson.OPT_SORT_KEYS)


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def schema_fingerprint(layer_metadata: dict[str, Any]) -> str:
    fields = layer_metadata.get("fields", [])

    canonical_fields = [
        {
            "name": field.get("name"),
            "alias": field.get("alias"),
            "type": field.get("type"),
            "length": field.get("length"),
            "nullable": field.get("nullable"),
        }
        for field in fields
    ]

    schema_payload = {
        "id": layer_metadata.get("id"),
        "name": layer_metadata.get("name"),
        "objectIdField": (
            layer_metadata.get("objectIdField") or layer_metadata.get("objectIdFieldName")
        ),
        "geometryType": layer_metadata.get("geometryType"),
        "fields": canonical_fields,
    }

    return sha256_bytes(canonical_json_bytes(schema_payload))


def write_layer_snapshot(
    *,
    project_root: Path,
    source_id: str,
    run_id: str,
    layer_id: int,
    collected_at: datetime,
    as_of_timestamp: datetime,
    layer_metadata: dict[str, Any],
    feature_collection: dict[str, Any],
) -> SnapshotRecord:
    raw_bytes = canonical_json_bytes(feature_collection)
    digest = sha256_bytes(raw_bytes)

    date_path = as_of_timestamp.astimezone(UTC)
    relative_path = (
        Path("data")
        / "bronze"
        / source_id
        / f"{date_path.year:04d}"
        / f"{date_path.month:02d}"
        / f"{date_path.day:02d}"
        / run_id
        / f"layer_{layer_id}_{digest[:16]}.geojson.gz"
    )

    absolute_path = project_root / relative_path
    absolute_path.parent.mkdir(parents=True, exist_ok=True)

    with gzip.open(absolute_path, "wb", compresslevel=6) as handle:
        handle.write(raw_bytes)

    features = feature_collection.get("features", [])

    return SnapshotRecord(
        source_id=source_id,
        run_id=run_id,
        layer_id=layer_id,
        collected_at=collected_at,
        as_of_timestamp=as_of_timestamp,
        raw_path=str(relative_path),
        sha256=digest,
        record_count=len(features),
        schema_fingerprint=schema_fingerprint(layer_metadata),
        content_type="application/geo+json",
    )


def write_manifest(
    *,
    project_root: Path,
    manifest: SourceRunManifest,
) -> Path:
    as_of = manifest.as_of_timestamp.astimezone(UTC)

    relative_path = (
        Path("data")
        / "bronze"
        / manifest.source_id
        / f"{as_of.year:04d}"
        / f"{as_of.month:02d}"
        / f"{as_of.day:02d}"
        / manifest.run_id
        / "manifest.json"
    )

    absolute_path = project_root / relative_path
    absolute_path.parent.mkdir(parents=True, exist_ok=True)

    absolute_path.write_bytes(
        orjson.dumps(
            manifest.model_dump(mode="json"),
            option=orjson.OPT_INDENT_2 | orjson.OPT_SORT_KEYS,
        )
    )

    return absolute_path
