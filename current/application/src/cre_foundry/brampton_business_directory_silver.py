from __future__ import annotations

import gzip
import hashlib
import json
import os
import re
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import duckdb
import orjson

from cre_foundry.brampton_permit_entity_bridge import (
    normalize_address,
)
from cre_foundry.bulk_storage import (
    write_json_atomic,
)
from cre_foundry.odbus_entities import (
    warehouse_path,
)

EMPLOYEE_RANGE_PATTERN = re.compile(r"^\s*(\d+)\s*-\s*(\d+)\s*$")

EMPLOYEE_LOWER_PATTERN = re.compile(r"^\s*(\d+)\s*\+\s*$")


def latest_business_directory_manifest(
    project_root: Path,
) -> Path:
    manifests = sorted(
        project_root.glob("data/bronze/brampton_business_directory/*/*/*/*/manifest.json"),
        key=lambda path: path.stat().st_mtime_ns,
    )

    if not manifests:
        raise RuntimeError("No Brampton business-directory manifest found.")

    latest = manifests[-1]

    payload = json.loads(latest.read_text(encoding="utf-8"))

    if payload.get("status") != "succeeded":
        raise RuntimeError("Latest business-directory run did not succeed.")

    return latest


def _optional_text(
    value: object,
) -> str | None:
    if value is None:
        return None

    normalized = str(value).strip()

    return normalized or None


def _optional_integer(
    value: object,
) -> int | None:
    if value is None:
        return None

    normalized = str(value).strip().replace(",", "")

    if not normalized:
        return None

    try:
        return int(float(normalized))
    except ValueError as exc:
        raise RuntimeError(f"Invalid integer value: {value!r}") from exc


def _optional_float(
    value: object,
) -> float | None:
    if value is None:
        return None

    normalized = str(value).strip().replace(",", "")

    if not normalized:
        return None

    try:
        return float(normalized)
    except ValueError as exc:
        raise RuntimeError(f"Invalid numeric value: {value!r}") from exc


def employee_bounds(
    value: object,
) -> tuple[
    int | None,
    int | None,
]:
    normalized = _optional_text(value)

    if normalized is None:
        return None, None

    range_match = EMPLOYEE_RANGE_PATTERN.match(normalized)

    if range_match:
        return (
            int(range_match.group(1)),
            int(range_match.group(2)),
        )

    lower_match = EMPLOYEE_LOWER_PATTERN.match(normalized)

    if lower_match:
        return (
            int(lower_match.group(1)),
            None,
        )

    return None, None


def _sha256_file(
    path: Path,
) -> str:
    digest = hashlib.sha256()

    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)

    return digest.hexdigest()


def _sql_path(
    path: Path,
) -> str:
    return str(path).replace(
        "'",
        "''",
    )


def _scalar(
    connection: duckdb.DuckDBPyConnection,
    query: str,
) -> int:
    row = connection.execute(query).fetchone()

    if row is None:
        raise RuntimeError("DuckDB scalar query returned no row.")

    return int(row[0])


def build_brampton_business_directory_silver(
    project_root: Path,
) -> dict[str, Any]:
    manifest_path = latest_business_directory_manifest(project_root)

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    snapshots = manifest.get(
        "layer_snapshots",
        [],
    )

    if len(snapshots) != 1:
        raise RuntimeError("Expected exactly one business-directory snapshot.")

    snapshot = snapshots[0]

    if snapshot.get("layer_id") != 0:
        raise RuntimeError("Unexpected business-directory layer.")

    raw_path = project_root / str(snapshot["raw_path"])

    with gzip.open(
        raw_path,
        "rb",
    ) as handle:
        raw_bytes = handle.read()

    actual_raw_hash = hashlib.sha256(raw_bytes).hexdigest()

    if actual_raw_hash != snapshot["sha256"]:
        raise RuntimeError("Business-directory snapshot hash mismatch.")

    collection = orjson.loads(raw_bytes)

    features = collection.get("features")

    if not isinstance(features, list):
        raise RuntimeError("Business-directory snapshot has no feature list.")

    as_of = datetime.fromisoformat(
        str(manifest["as_of_timestamp"]).replace(
            "Z",
            "+00:00",
        )
    )

    if as_of.tzinfo is None:
        as_of = as_of.replace(tzinfo=UTC)

    as_of = as_of.astimezone(UTC)

    rows: list[tuple[Any, ...]] = []

    object_ids: list[int] = []
    global_ids: list[str] = []

    company_names: Counter[str] = Counter()
    full_addresses: Counter[str] = Counter()
    company_address_keys: Counter[tuple[str, str]] = Counter()

    employee_distribution: Counter[str] = Counter()
    naics_2_distribution: Counter[str] = Counter()

    null_counts: Counter[str] = Counter()

    for feature in features:
        if not isinstance(feature, dict):
            raise RuntimeError("Invalid business-directory feature.")

        properties = feature.get("properties")

        if not isinstance(
            properties,
            dict,
        ):
            raise RuntimeError("Business-directory feature has no properties.")

        operational = _optional_text(properties.get("OPERATIONAL"))

        if operational is None or operational.casefold() != "yes":
            raise RuntimeError(
                f"Silver received a non-operational directory record: {operational!r}"
            )

        object_id = _optional_integer(properties.get("OBJECTID"))

        global_id = _optional_text(properties.get("GLOBALID"))

        company_name = _optional_text(properties.get("COMPANY_NAME"))

        address = _optional_text(properties.get("BUSINESS_FULL_ADDRESS"))

        if object_id is None:
            raise RuntimeError("Directory record has no OBJECTID.")

        if global_id is None:
            raise RuntimeError("Directory record has no GLOBALID.")

        if company_name is None:
            raise RuntimeError("Directory record has no company name.")

        if address is None:
            raise RuntimeError("Directory record has no address.")

        normalized_full = normalize_address(
            address,
            remove_unit=False,
        )

        normalized_base = normalize_address(
            address,
            remove_unit=True,
        )

        employee_group = _optional_text(properties.get("TOTAL_EMPLOYEE_GROUPED"))

        (
            employee_min,
            employee_max,
        ) = employee_bounds(employee_group)

        longitude: float | None = None
        latitude: float | None = None

        geometry = feature.get("geometry")

        if isinstance(geometry, dict):
            coordinates = geometry.get("coordinates")

            if isinstance(coordinates, list) and len(coordinates) >= 2:
                longitude = _optional_float(coordinates[0])
                latitude = _optional_float(coordinates[1])

        unit = _optional_text(properties.get("UNIT"))
        postal_code = _optional_text(properties.get("POSTAL_CODE"))
        phone = _optional_text(properties.get("PHONE"))
        website = _optional_text(properties.get("WEBURL"))
        naics_detail = _optional_text(properties.get("NAICS_DETAIL"))
        naics_2 = _optional_text(properties.get("NAIC_2"))
        naics_3 = _optional_text(properties.get("NAIC_3"))
        naics_4 = _optional_text(properties.get("NAIC_4"))
        naics_6 = _optional_text(properties.get("NAIC_6"))
        product_description = _optional_text(properties.get("PRODUCT_DESC"))

        nullable_values = {
            "unit": unit,
            "postal_code": postal_code,
            "phone": phone,
            "website": website,
            "naics_detail": naics_detail,
            "naics_6": naics_6,
            "employee_group": employee_group,
            "gfa_square_feet": (properties.get("GFA_SQUARE_FEET")),
            "product_description": (product_description),
        }

        for field, value in nullable_values.items():
            if value is None:
                null_counts[field] += 1

        object_ids.append(object_id)
        global_ids.append(global_id)

        company_names[company_name.casefold()] += 1

        full_addresses[normalized_full] += 1

        company_address_keys[
            (
                company_name.casefold(),
                normalized_full,
            )
        ] += 1

        employee_distribution[employee_group or "<NULL>"] += 1

        naics_2_distribution[naics_2 or "<NULL>"] += 1

        rows.append(
            (
                "brampton_business_directory",
                str(manifest["run_id"]),
                str(snapshot["sha256"]),
                (f"brampton_business_directory:{global_id}"),
                object_id,
                global_id,
                company_name,
                address,
                normalized_full,
                normalized_base,
                unit,
                _optional_text(properties.get("STREET_NUM")),
                _optional_text(properties.get("STREET_NAME")),
                _optional_text(properties.get("STREET_TYPE")),
                _optional_text(properties.get("STREET_DIRECTION")),
                _optional_text(properties.get("CITY")),
                _optional_text(properties.get("PROVINCE")),
                postal_code,
                phone,
                website,
                _optional_text(properties.get("FAX")),
                _optional_text(properties.get("DATE_EST_IN_CITY")),
                _optional_text(properties.get("STARTED_IN_CITY")),
                _optional_text(properties.get("HEAD_OFFICE_LOCATION")),
                employee_group,
                employee_min,
                employee_max,
                _optional_integer(properties.get("GFA_SQUARE_FEET")),
                _optional_integer(properties.get("GFA_SQUARE_METER")),
                naics_detail,
                naics_2,
                naics_3,
                naics_4,
                naics_6,
                product_description,
                _optional_text(properties.get("FACEBOOK")),
                _optional_text(properties.get("TWITTER")),
                _optional_text(properties.get("YOUTUBE")),
                _optional_text(properties.get("INSTAGRAM")),
                _optional_text(properties.get("OTHER_SOCIALS")),
                operational,
                True,
                as_of,
                longitude,
                latitude,
                False,
                False,
                False,
            )
        )

    if len(set(object_ids)) != len(rows):
        raise RuntimeError("Directory OBJECTIDs are not unique.")

    if len(set(global_ids)) != len(rows):
        raise RuntimeError("Directory GLOBALIDs are not unique.")

    duplicate_company_address_rows = sum(
        count - 1 for count in (company_address_keys.values()) if count > 1
    )

    date_path = as_of.astimezone(UTC)

    relative_parquet = (
        Path("data")
        / "silver"
        / "brampton_business_directory"
        / f"{date_path.year:04d}"
        / f"{date_path.month:02d}"
        / f"{date_path.day:02d}"
        / str(manifest["run_id"])
        / "silver-v1"
        / "business_directory.parquet"
    )

    parquet_path = project_root / relative_parquet

    parquet_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    temporary_path = parquet_path.with_name(f".{parquet_path.name}.tmp")

    temporary_path.unlink(missing_ok=True)

    staging = duckdb.connect(":memory:")

    try:
        staging.execute(
            """
            CREATE TABLE directory_rows (
                source_id VARCHAR,
                run_id VARCHAR,
                source_snapshot_sha256 VARCHAR,
                source_record_id VARCHAR,
                object_id BIGINT,
                global_id VARCHAR,
                company_name VARCHAR,
                business_full_address VARCHAR,
                normalized_full_address VARCHAR,
                normalized_base_address VARCHAR,
                unit VARCHAR,
                street_number VARCHAR,
                street_name VARCHAR,
                street_type VARCHAR,
                street_direction VARCHAR,
                city VARCHAR,
                province VARCHAR,
                postal_code VARCHAR,
                phone VARCHAR,
                website VARCHAR,
                fax VARCHAR,
                date_established_in_city_raw VARCHAR,
                started_in_city_raw VARCHAR,
                head_office_location VARCHAR,
                employee_group VARCHAR,
                employee_count_min INTEGER,
                employee_count_max INTEGER,
                gfa_square_feet BIGINT,
                gfa_square_meters BIGINT,
                naics_detail VARCHAR,
                naics_2 VARCHAR,
                naics_3 VARCHAR,
                naics_4 VARCHAR,
                naics_6 VARCHAR,
                product_description VARCHAR,
                facebook VARCHAR,
                twitter VARCHAR,
                youtube VARCHAR,
                instagram VARCHAR,
                other_socials VARCHAR,
                operational_raw VARCHAR,
                directory_operational_at_snapshot BOOLEAN,
                as_of_timestamp TIMESTAMPTZ,
                longitude DOUBLE,
                latitude DOUBLE,
                commercial_requirement_verified BOOLEAN,
                decision_maker_verified BOOLEAN,
                outreach_eligible BOOLEAN
            )
            """
        )

        staging.executemany(
            (
                "INSERT INTO directory_rows VALUES (?, ?, ?, ?, ?, ?, ?, ?, "
                "?, ?, ?, ?, ?, ?, ?, ?, "
                "?, ?, ?, ?, ?, ?, ?, ?, "
                "?, ?, ?, ?, ?, ?, ?, ?, "
                "?, ?, ?, ?, ?, ?, ?, ?, "
                "?, ?, ?, ?, ?, ?, ?, ?)"
            ),
            rows,
        )

        staging.execute(
            f"""
            COPY directory_rows
            TO '{_sql_path(temporary_path)}'
            (
                FORMAT PARQUET,
                COMPRESSION ZSTD
            )
            """
        )

    finally:
        staging.close()

    os.replace(
        temporary_path,
        parquet_path,
    )

    warehouse = warehouse_path(project_root)

    connection = duckdb.connect(str(warehouse))

    try:
        connection.execute("BEGIN")

        connection.execute(
            """
            CREATE SCHEMA IF NOT EXISTS silver
            """
        )

        connection.execute(
            f"""
            CREATE OR REPLACE TABLE
                silver.brampton_business_directory
            AS
            SELECT *
            FROM read_parquet(
                '{_sql_path(parquet_path)}'
            )
            """
        )

        connection.execute(
            """
            CREATE OR REPLACE VIEW
                silver.brampton_business_directory_summary
            AS
            SELECT
                naics_2,
                employee_group,
                count(*) AS records,
                count(*) FILTER (
                    WHERE phone IS NOT NULL
                ) AS records_with_phone,
                count(*) FILTER (
                    WHERE website IS NOT NULL
                ) AS records_with_website
            FROM
                silver.brampton_business_directory
            GROUP BY
                naics_2,
                employee_group
            """
        )

        warehouse_count = _scalar(
            connection,
            """
            SELECT count(*)
            FROM silver.brampton_business_directory
            """,
        )

        non_operational_count = _scalar(
            connection,
            """
            SELECT count(*)
            FROM silver.brampton_business_directory
            WHERE NOT directory_operational_at_snapshot
            """,
        )

        duplicate_object_ids = _scalar(
            connection,
            """
            SELECT
                count(*)
                - count(DISTINCT object_id)
            FROM silver.brampton_business_directory
            """,
        )

        duplicate_global_ids = _scalar(
            connection,
            """
            SELECT
                count(*)
                - count(DISTINCT global_id)
            FROM silver.brampton_business_directory
            """,
        )

        outreach_count = _scalar(
            connection,
            """
            SELECT count(*)
            FROM silver.brampton_business_directory
            WHERE outreach_eligible
            """,
        )

        commercial_requirement_count = _scalar(
            connection,
            """
            SELECT count(*)
            FROM silver.brampton_business_directory
            WHERE commercial_requirement_verified
            """,
        )

        decision_maker_count = _scalar(
            connection,
            """
            SELECT count(*)
            FROM silver.brampton_business_directory
            WHERE decision_maker_verified
            """,
        )

        connection.execute("COMMIT")

    except Exception:
        connection.execute("ROLLBACK")
        raise

    finally:
        connection.close()

    if warehouse_count != len(rows):
        raise RuntimeError("Directory silver count mismatch.")

    if non_operational_count != 0:
        raise RuntimeError("Directory silver contains non-operational rows.")

    if duplicate_object_ids != 0:
        raise RuntimeError("Directory silver contains duplicate OBJECTIDs.")

    if duplicate_global_ids != 0:
        raise RuntimeError("Directory silver contains duplicate GLOBALIDs.")

    if outreach_count or commercial_requirement_count or decision_maker_count:
        raise RuntimeError("Directory silver violated safety flags.")

    report: dict[str, Any] = {
        "model_version": ("brampton-business-directory-silver-v1"),
        "source_id": ("brampton_business_directory"),
        "run_id": manifest["run_id"],
        "manifest_path": str(manifest_path.relative_to(project_root)),
        "source_snapshot_path": (snapshot["raw_path"]),
        "source_snapshot_sha256": (snapshot["sha256"]),
        "source_record_count": len(features),
        "silver_record_count": len(rows),
        "warehouse_record_count": (warehouse_count),
        "duplicate_object_id_count": (duplicate_object_ids),
        "duplicate_global_id_count": (duplicate_global_ids),
        "duplicate_company_address_extra_rows": (duplicate_company_address_rows),
        "null_counts": dict(sorted(null_counts.items())),
        "employee_group_distribution": dict(employee_distribution.most_common()),
        "naics_2_distribution": dict(naics_2_distribution.most_common()),
        "directory_operational_count": (warehouse_count),
        "commercial_requirement_verified_count": (commercial_requirement_count),
        "decision_maker_verified_count": (decision_maker_count),
        "outreach_eligible_count": (outreach_count),
        "parquet_path": str(relative_parquet),
        "parquet_sha256": _sha256_file(parquet_path),
        "warehouse_path": str(warehouse.relative_to(project_root)),
        "table": ("silver.brampton_business_directory"),
        "summary_view": ("silver.brampton_business_directory_summary"),
        "policy": {
            "stable_record_key": "GLOBALID",
            "operational_scope": ("OPERATIONAL=YES"),
            "fuzzy_deduplication_enabled": False,
            "commercial_requirement_verified": (False),
            "decision_maker_verified": False,
            "outreach_eligible": False,
        },
    }

    contract_path = (
        project_root / "docs" / "data_contracts" / "brampton_business_directory_silver.json"
    )

    report["contract_path"] = str(contract_path.relative_to(project_root))

    write_json_atomic(
        contract_path,
        report,
    )

    return report
