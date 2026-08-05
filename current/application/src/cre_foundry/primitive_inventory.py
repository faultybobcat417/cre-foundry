from __future__ import annotations

import json
import os
import sqlite3
import tempfile
from collections import Counter
from pathlib import Path
from typing import Any

import duckdb

EXPECTED_POLICY: dict[str, Any] = {
    "operating_mode": "shadow",
    "read_only": True,
    "schema_driven": True,
    "sample_values_enabled": False,
    "automatic_conclusions": False,
    "opportunity_ranked": False,
    "outreach_eligible": False,
    "automatic_acquisition": False,
    "browser_execution": False,
    "computer_vision_execution": False,
}

LINEAGE_NAMES = {
    "source_id",
    "source_name",
    "source_run_id",
    "run_id",
    "snapshot_id",
    "content_sha256",
    "checksum",
    "file_sha256",
    "parser_version",
    "schema_version",
    "observed_at",
    "acquired_at",
    "ingested_at",
    "created_at",
    "updated_at",
}

SAFETY_NAMES = {
    "operating_mode",
    "automatic_conclusions",
    "opportunity_ranked",
    "outreach_eligible",
    "outreach_authorization_required",
    "verification_complete",
    "gate_cleared",
}

GEOGRAPHY_TOKENS = {
    "address",
    "city",
    "municipality",
    "province",
    "postal",
    "latitude",
    "longitude",
    "geometry",
    "geocode",
    "location",
}

VERIFICATION_TOKENS = {
    "verify",
    "verification",
    "review",
    "gate",
    "resolution",
    "confidence",
    "evidence",
}


def _atomic_json(
    path: Path,
    payload: dict[str, Any],
) -> None:
    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    descriptor, temporary_name = tempfile.mkstemp(
        dir=path.parent,
        prefix=f".{path.name}.",
        suffix=".tmp",
        text=True,
    )

    temporary_path = Path(temporary_name)

    try:
        with os.fdopen(
            descriptor,
            "w",
            encoding="utf-8",
        ) as stream:
            json.dump(
                payload,
                stream,
                indent=2,
                sort_keys=True,
            )
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())

        temporary_path.replace(path)

    except Exception:
        temporary_path.unlink(missing_ok=True)
        raise


def _load_config(
    project_root: Path,
) -> dict[str, Any]:
    path = project_root / "config" / "primitive_inventory.json"

    raw: object = json.loads(path.read_text(encoding="utf-8"))

    if not isinstance(
        raw,
        dict,
    ):
        raise RuntimeError("Primitive-inventory config must be a JSON object.")

    payload: dict[str, Any] = {str(key): value for key, value in raw.items()}

    raw_policy = payload.get("policy")

    if not isinstance(
        raw_policy,
        dict,
    ):
        raise RuntimeError("Primitive-inventory policy must be a JSON object.")

    policy: dict[str, Any] = {str(key): value for key, value in raw_policy.items()}

    if policy != EXPECTED_POLICY:
        raise RuntimeError("Primitive-inventory safety policy mismatch.")

    raw_excluded = payload.get("excluded_duckdb_schemas")

    if not isinstance(
        raw_excluded,
        list,
    ) or not all(
        isinstance(
            item,
            str,
        )
        for item in raw_excluded
    ):
        raise RuntimeError("Excluded DuckDB schemas must be a string list.")

    return payload


def _quote_identifier(
    value: str,
) -> str:
    return (
        '"'
        + value.replace(
            '"',
            '""',
        )
        + '"'
    )


def _column_flags(
    column_name: str,
) -> dict[str, bool]:
    normalized = column_name.strip().lower()

    tokens = {
        token
        for token in normalized.replace(
            "-",
            "_",
        ).split("_")
        if token
    }

    identity = normalized == "id" or normalized.endswith("_id") or "identifier" in tokens

    temporal = (
        normalized.endswith("_at")
        or normalized.endswith("_date")
        or normalized.endswith("_time")
        or "date" in tokens
        or "time" in tokens
        or "timestamp" in tokens
    )

    lineage = (
        normalized in LINEAGE_NAMES
        or "source" in tokens
        or "snapshot" in tokens
        or "checksum" in tokens
        or "sha256" in tokens
        or "parser" in tokens
        or "schema" in tokens
    )

    geography = bool(tokens & GEOGRAPHY_TOKENS)

    verification = bool(tokens & VERIFICATION_TOKENS)

    safety = normalized in SAFETY_NAMES

    return {
        "identity_candidate": identity,
        "temporal_candidate": temporal,
        "lineage_candidate": lineage,
        "geography_candidate": geography,
        "verification_candidate": verification,
        "safety_control": safety,
    }


def _duckdb_inventory(
    project_root: Path,
    excluded_schemas: set[str],
) -> tuple[
    list[dict[str, Any]],
    list[dict[str, Any]],
]:
    warehouse_path = project_root / "data" / "warehouse" / "cre.duckdb"

    connection = duckdb.connect(
        str(warehouse_path),
        read_only=True,
    )

    try:
        relation_rows = connection.execute(
            """
            SELECT
                table_schema,
                table_name,
                table_type
            FROM information_schema.tables
            ORDER BY
                table_schema,
                table_name
            """
        ).fetchall()

        column_rows = connection.execute(
            """
            SELECT
                table_schema,
                table_name,
                column_name,
                ordinal_position,
                data_type,
                is_nullable
            FROM information_schema.columns
            ORDER BY
                table_schema,
                table_name,
                ordinal_position
            """
        ).fetchall()

        relations: list[dict[str, Any]] = []

        valid_relations: set[tuple[str, str]] = set()

        for row in relation_rows:
            schema_name = str(row[0])

            table_name = str(row[1])

            if schema_name in excluded_schemas:
                continue

            relation_type = str(row[2])

            identifier = _quote_identifier(schema_name) + "." + _quote_identifier(table_name)

            try:
                count_row = connection.execute(
                    f"""
                    SELECT count(*)
                    FROM {identifier}
                    """
                ).fetchone()

                row_count = int(count_row[0]) if count_row is not None else None

                count_error = None

            except Exception as exception:
                row_count = None
                count_error = type(exception).__name__

            relations.append(
                {
                    "engine": "duckdb",
                    "schema": schema_name,
                    "relation": table_name,
                    "relation_type": relation_type,
                    "row_count": row_count,
                    "count_error": count_error,
                }
            )

            valid_relations.add(
                (
                    schema_name,
                    table_name,
                )
            )

        primitives: list[dict[str, Any]] = []

        for row in column_rows:
            schema_name = str(row[0])

            table_name = str(row[1])

            if (
                schema_name,
                table_name,
            ) not in valid_relations:
                continue

            column_name = str(row[2])

            primitive_id = "duckdb:" + schema_name + "." + table_name + "." + column_name

            primitives.append(
                {
                    "primitive_id": (primitive_id),
                    "engine": "duckdb",
                    "schema": schema_name,
                    "relation": table_name,
                    "column": column_name,
                    "ordinal_position": int(row[3]),
                    "data_type": str(row[4]),
                    "nullable": (str(row[5]).upper() == "YES"),
                    "classification": (_column_flags(column_name)),
                }
            )

    finally:
        connection.close()

    return (
        relations,
        primitives,
    )


def _sqlite_inventory(
    project_root: Path,
) -> tuple[
    list[dict[str, Any]],
    list[dict[str, Any]],
    list[str],
]:
    database_path = project_root / "data" / "control" / "operations.sqlite3"

    connection = sqlite3.connect(
        ("file:" + str(database_path) + "?mode=ro"),
        uri=True,
    )

    try:
        relation_rows = connection.execute(
            """
            SELECT
                name,
                type
            FROM sqlite_master
            WHERE
                type IN (
                    'table',
                    'view'
                )
                AND name NOT LIKE
                    'sqlite_%'
            ORDER BY
                type,
                name
            """
        ).fetchall()

        trigger_rows = connection.execute(
            """
            SELECT name
            FROM sqlite_master
            WHERE type = 'trigger'
            ORDER BY name
            """
        ).fetchall()

        relations: list[dict[str, Any]] = []

        primitives: list[dict[str, Any]] = []

        for relation_row in relation_rows:
            relation_name = str(relation_row[0])

            relation_type = str(relation_row[1])

            quoted_relation = _quote_identifier(relation_name)

            try:
                count_row = connection.execute(
                    f"""
                    SELECT count(*)
                    FROM {quoted_relation}
                    """
                ).fetchone()

                row_count = int(count_row[0]) if count_row is not None else None

                count_error = None

            except Exception as exception:
                row_count = None
                count_error = type(exception).__name__

            relations.append(
                {
                    "engine": "sqlite",
                    "schema": "main",
                    "relation": relation_name,
                    "relation_type": relation_type,
                    "row_count": row_count,
                    "count_error": count_error,
                }
            )

            column_rows = connection.execute(
                f"""
                PRAGMA table_info(
                    {quoted_relation}
                )
                """
            ).fetchall()

            for column_row in column_rows:
                column_name = str(column_row[1])

                primitive_id = "sqlite:main." + relation_name + "." + column_name

                primitives.append(
                    {
                        "primitive_id": (primitive_id),
                        "engine": "sqlite",
                        "schema": "main",
                        "relation": (relation_name),
                        "column": column_name,
                        "ordinal_position": (int(column_row[0]) + 1),
                        "data_type": str(column_row[2]),
                        "nullable": not bool(column_row[3]),
                        "primary_key": bool(column_row[5]),
                        "classification": (_column_flags(column_name)),
                    }
                )

        triggers = [str(row[0]) for row in trigger_rows]

    finally:
        connection.close()

    return (
        relations,
        primitives,
        triggers,
    )


def build_primitive_inventory(
    project_root: Path,
    *,
    write_contract: bool = True,
) -> dict[str, Any]:
    config = _load_config(project_root)

    excluded_raw = config["excluded_duckdb_schemas"]

    if not isinstance(
        excluded_raw,
        list,
    ):
        raise RuntimeError("Excluded schemas are malformed.")

    excluded_schemas = {str(item) for item in excluded_raw}

    (
        duckdb_relations,
        duckdb_primitives,
    ) = _duckdb_inventory(
        project_root,
        excluded_schemas,
    )

    (
        sqlite_relations,
        sqlite_primitives,
        sqlite_triggers,
    ) = _sqlite_inventory(project_root)

    relations = duckdb_relations + sqlite_relations

    primitives = duckdb_primitives + sqlite_primitives

    primitive_ids = [str(primitive["primitive_id"]) for primitive in primitives]

    duplicate_ids = sorted(
        primitive_id for primitive_id, count in Counter(primitive_ids).items() if count > 1
    )

    flag_counts: Counter[str] = Counter()

    safety_controls: list[dict[str, Any]] = []

    relation_temporal_flags: dict[
        tuple[str, str, str],
        bool,
    ] = {}

    relation_lineage_flags: dict[
        tuple[str, str, str],
        bool,
    ] = {}

    for primitive in primitives:
        classification = primitive["classification"]

        if not isinstance(
            classification,
            dict,
        ):
            raise RuntimeError("Primitive classification is malformed.")

        relation_key = (
            str(primitive["engine"]),
            str(primitive["schema"]),
            str(primitive["relation"]),
        )

        relation_temporal_flags.setdefault(
            relation_key,
            False,
        )

        relation_lineage_flags.setdefault(
            relation_key,
            False,
        )

        for flag_name, enabled in classification.items():
            if bool(enabled):
                flag_counts[str(flag_name)] += 1

        if bool(classification.get("temporal_candidate")):
            relation_temporal_flags[relation_key] = True

        if bool(classification.get("lineage_candidate")):
            relation_lineage_flags[relation_key] = True

        if bool(classification.get("safety_control")):
            safety_controls.append(
                {
                    "primitive_id": primitive["primitive_id"],
                    "engine": primitive["engine"],
                    "schema": primitive["schema"],
                    "relation": primitive["relation"],
                    "column": primitive["column"],
                }
            )

    relations_without_temporal = [
        {
            "engine": key[0],
            "schema": key[1],
            "relation": key[2],
        }
        for key, detected in sorted(relation_temporal_flags.items())
        if not detected
    ]

    relations_without_lineage = [
        {
            "engine": key[0],
            "schema": key[1],
            "relation": key[2],
        }
        for key, detected in sorted(relation_lineage_flags.items())
        if not detected
    ]

    schema_counts: Counter[str] = Counter()

    for relation in relations:
        key = str(relation["engine"]) + ":" + str(relation["schema"])

        schema_counts[key] += 1

    report = {
        "model_version": ("cre-foundry-schema-primitive-inventory-v1"),
        "relation_count": len(relations),
        "primitive_count": len(primitives),
        "duckdb_relation_count": len(duckdb_relations),
        "duckdb_primitive_count": len(duckdb_primitives),
        "sqlite_relation_count": len(sqlite_relations),
        "sqlite_primitive_count": len(sqlite_primitives),
        "sqlite_trigger_count": len(sqlite_triggers),
        "schema_relation_counts": dict(sorted(schema_counts.items())),
        "classification_counts": dict(sorted(flag_counts.items())),
        "duplicate_primitive_ids": (duplicate_ids),
        "relations_without_detected_temporal_columns": (relations_without_temporal),
        "relations_without_detected_lineage_columns": (relations_without_lineage),
        "safety_controls": safety_controls,
        "relations": relations,
        "primitives": primitives,
        "sqlite_triggers": (sqlite_triggers),
        "policy": EXPECTED_POLICY,
        "inventory_ready": (not duplicate_ids and bool(relations) and bool(primitives)),
        "production_ranking_ready": False,
        "automatic_acquisition_ready": False,
        "browser_execution_ready": False,
        "computer_vision_execution_ready": False,
        "outreach_ready": False,
    }

    if write_contract:
        contract_path = project_root / "docs" / "data_contracts" / "primitive_inventory.json"

        report["contract_path"] = str(contract_path.relative_to(project_root))

        _atomic_json(
            contract_path,
            report,
        )

    return report
