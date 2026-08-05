from __future__ import annotations

import json
import os
import sqlite3
import tempfile
from collections import Counter, defaultdict
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

import duckdb

EXPECTED_POLICY: dict[str, Any] = {
    "operating_mode": "shadow",
    "read_only": True,
    "schema_driven": True,
    "sample_values_enabled": False,
    "safety_control_values_enabled": True,
    "automatic_acquisition": False,
    "automatic_snapshot_registration": False,
    "browser_execution": False,
    "computer_vision_execution": False,
    "automatic_conclusions": False,
    "opportunity_ranked": False,
    "outreach_eligible": False,
}

TRUE_BLOCKED_CONTROLS = {
    "automatic_acquisition",
    "automatic_browser_execution",
    "automatic_computer_vision_execution",
    "automatic_conclusions",
    "automatic_execution",
    "automatic_outreach",
    "automatic_outreach_allowed",
    "browser_execution",
    "computer_vision_execution",
    "opportunity_ranked",
    "outreach_eligible",
}

TEMPORAL_TYPE_TOKENS = (
    "DATE",
    "TIME",
    "TIMESTAMP",
)

NUMERIC_TYPE_TOKENS = (
    "BIGINT",
    "DECIMAL",
    "DOUBLE",
    "FLOAT",
    "HUGEINT",
    "INTEGER",
    "NUMERIC",
    "REAL",
    "SMALLINT",
    "TINYINT",
    "UBIGINT",
    "UINTEGER",
    "USMALLINT",
    "UTINYINT",
)

TEXT_TYPE_TOKENS = (
    "CHAR",
    "JSON",
    "STRING",
    "TEXT",
    "UUID",
    "VARCHAR",
)

SEVERITY_ORDER = {
    "critical": 0,
    "high": 1,
    "medium": 2,
    "low": 3,
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


def _load_object(
    path: Path,
) -> dict[str, Any]:
    raw: object = json.loads(path.read_text(encoding="utf-8"))

    if not isinstance(
        raw,
        dict,
    ):
        raise RuntimeError(f"Expected JSON object: {path}")

    return {str(key): value for key, value in raw.items()}


def _load_config(
    project_root: Path,
) -> dict[str, Any]:
    payload = _load_object(project_root / "config" / "primitive_quality.json")

    raw_policy = payload.get("policy")

    if not isinstance(
        raw_policy,
        dict,
    ):
        raise RuntimeError("Primitive-quality policy must be a JSON object.")

    policy: dict[str, Any] = {str(key): value for key, value in raw_policy.items()}

    if policy != EXPECTED_POLICY:
        raise RuntimeError("Primitive-quality safety policy mismatch.")

    raw_thresholds = payload.get("thresholds")

    if not isinstance(
        raw_thresholds,
        dict,
    ):
        raise RuntimeError("Primitive-quality thresholds must be a JSON object.")

    high_null_ratio = raw_thresholds.get("high_null_ratio")

    material_null_ratio = raw_thresholds.get("material_null_ratio")

    maximum_safety_values = raw_thresholds.get("maximum_safety_distinct_values")

    if (
        not isinstance(
            high_null_ratio,
            int | float,
        )
        or not 0.0 <= float(high_null_ratio) <= 1.0
    ):
        raise RuntimeError("high_null_ratio must be between zero and one.")

    if (
        not isinstance(
            material_null_ratio,
            int | float,
        )
        or not 0.0 <= float(material_null_ratio) <= 1.0
    ):
        raise RuntimeError("material_null_ratio must be between zero and one.")

    if (
        not isinstance(
            maximum_safety_values,
            int,
        )
        or maximum_safety_values <= 0
    ):
        raise RuntimeError("maximum_safety_distinct_values must be a positive integer.")

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


def _json_value(
    value: Any,
) -> Any:
    if value is None:
        return None

    if isinstance(
        value,
        bool | int | float | str,
    ):
        return value

    if isinstance(
        value,
        Decimal | date | datetime,
    ):
        return str(value)

    if isinstance(
        value,
        bytes,
    ):
        return value.hex()

    return str(value)


def _normalized_type(
    data_type: str,
) -> str:
    return data_type.strip().upper()


def _is_boolean(
    data_type: str,
) -> bool:
    normalized = _normalized_type(data_type)

    return normalized == "BOOLEAN" or normalized == "BOOL"


def _is_temporal(
    data_type: str,
) -> bool:
    normalized = _normalized_type(data_type)

    return any(token in normalized for token in TEMPORAL_TYPE_TOKENS)


def _is_numeric(
    data_type: str,
) -> bool:
    normalized = _normalized_type(data_type)

    return any(token in normalized for token in NUMERIC_TYPE_TOKENS)


def _is_text(
    data_type: str,
) -> bool:
    normalized = _normalized_type(data_type)

    return any(token in normalized for token in TEXT_TYPE_TOKENS)


def _supports_distinct(
    data_type: str,
) -> bool:
    return (
        _is_boolean(data_type)
        or _is_temporal(data_type)
        or _is_numeric(data_type)
        or _is_text(data_type)
    )


def _effective_roles(
    primitive: dict[str, Any],
) -> dict[str, bool]:
    raw_classification = primitive.get("classification")

    classification: dict[str, Any]

    if isinstance(
        raw_classification,
        dict,
    ):
        classification = {str(key): value for key, value in raw_classification.items()}

    else:
        classification = {}

    column_name = str(
        primitive.get(
            "column",
            "",
        )
    ).lower()

    data_type = str(
        primitive.get(
            "data_type",
            "",
        )
    )

    temporal = (
        bool(classification.get("temporal_candidate"))
        or _is_temporal(data_type)
        or column_name.endswith("_utc")
        or column_name.endswith("_timestamp")
    )

    lineage = (
        bool(classification.get("lineage_candidate"))
        or column_name.startswith("source_")
        or column_name.endswith("_sha256")
        or column_name.endswith("_hash")
        or column_name
        in {
            "run_id",
            "snapshot_id",
            "manifest_path",
            "bronze_run_id",
        }
    )

    verification = (
        bool(classification.get("verification_candidate"))
        or "verified" in column_name
        or "review" in column_name
        or "evidence" in column_name
        or "gate" in column_name
    )

    return {
        "identity": bool(classification.get("identity_candidate")),
        "temporal": temporal,
        "lineage": lineage,
        "geography": bool(classification.get("geography_candidate")),
        "verification": verification,
        "safety": bool(classification.get("safety_control")),
    }


def _metric_expressions(
    column_name: str,
    data_type: str,
    metric_index: int,
    *,
    engine: str,
) -> tuple[
    list[str],
    list[
        tuple[
            str,
            str,
        ]
    ],
]:
    quoted = _quote_identifier(column_name)

    expressions = [(f"COUNT({quoted}) AS m{metric_index}_non_null")]

    mappings = [
        (
            f"m{metric_index}_non_null",
            "non_null_count",
        )
    ]

    if _supports_distinct(data_type):
        if engine == "duckdb":
            distinct_expression = f"approx_count_distinct({quoted})"

        else:
            distinct_expression = f"COUNT(DISTINCT {quoted})"

        expressions.append(f"{distinct_expression} AS m{metric_index}_distinct")

        mappings.append(
            (
                f"m{metric_index}_distinct",
                "distinct_count",
            )
        )

    if _is_numeric(data_type) or _is_temporal(data_type):
        expressions.extend(
            [
                (f"MIN({quoted}) AS m{metric_index}_min"),
                (f"MAX({quoted}) AS m{metric_index}_max"),
            ]
        )

        mappings.extend(
            [
                (
                    f"m{metric_index}_min",
                    "minimum",
                ),
                (
                    f"m{metric_index}_max",
                    "maximum",
                ),
            ]
        )

    if _is_text(data_type):
        expressions.append(f"MAX(LENGTH(CAST({quoted} AS VARCHAR))) AS m{metric_index}_max_length")

        mappings.append(
            (
                f"m{metric_index}_max_length",
                "maximum_length",
            )
        )

    if _is_boolean(data_type):
        expressions.extend(
            [
                (f"SUM(CASE WHEN {quoted} IS TRUE THEN 1 ELSE 0 END) AS m{metric_index}_true"),
                (f"SUM(CASE WHEN {quoted} IS FALSE THEN 1 ELSE 0 END) AS m{metric_index}_false"),
            ]
        )

        mappings.extend(
            [
                (
                    f"m{metric_index}_true",
                    "true_count",
                ),
                (
                    f"m{metric_index}_false",
                    "false_count",
                ),
            ]
        )

    return (
        expressions,
        mappings,
    )


def _duckdb_profile_relation(
    connection: duckdb.DuckDBPyConnection,
    schema_name: str,
    relation_name: str,
    primitives: list[dict[str, Any]],
    maximum_safety_values: int,
) -> dict[str, Any]:
    relation_identifier = _quote_identifier(schema_name) + "." + _quote_identifier(relation_name)

    expressions = ["COUNT(*) AS row_count"]

    mappings_by_column: dict[
        str,
        list[
            tuple[
                str,
                str,
            ]
        ],
    ] = {}

    for index, primitive in enumerate(primitives):
        column_name = str(primitive["column"])

        data_type = str(primitive["data_type"])

        (
            metric_expressions,
            metric_mappings,
        ) = _metric_expressions(
            column_name,
            data_type,
            index,
            engine="duckdb",
        )

        expressions.extend(metric_expressions)

        mappings_by_column[column_name] = metric_mappings

    query = "SELECT\n    " + ",\n    ".join(expressions) + "\nFROM " + relation_identifier

    cursor = connection.execute(query)

    row = cursor.fetchone()

    if row is None:
        raise RuntimeError(f"DuckDB profile query returned no row: {schema_name}.{relation_name}")

    description = cursor.description

    field_names = [str(field[0]) for field in description]

    values = dict(
        zip(
            field_names,
            row,
            strict=True,
        )
    )

    row_count = int(values["row_count"])

    column_profiles = []

    for primitive in primitives:
        column_name = str(primitive["column"])

        metrics: dict[str, Any] = {}

        for alias, metric_name in mappings_by_column[column_name]:
            metrics[metric_name] = _json_value(values.get(alias))

        non_null_count = int(metrics.get("non_null_count") or 0)

        null_count = row_count - non_null_count

        null_ratio = (null_count / row_count) if row_count else None

        profile: dict[str, Any] = {
            "primitive_id": primitive["primitive_id"],
            "column": column_name,
            "data_type": primitive["data_type"],
            "nullable": primitive["nullable"],
            "roles": _effective_roles(primitive),
            "row_count": row_count,
            "null_count": null_count,
            "null_ratio": null_ratio,
            **metrics,
        }

        if profile["roles"]["safety"]:
            quoted_column = _quote_identifier(column_name)

            safety_rows = connection.execute(
                f"""
                SELECT DISTINCT
                    CAST(
                        {quoted_column}
                        AS VARCHAR
                    )
                FROM {relation_identifier}
                WHERE
                    {quoted_column}
                    IS NOT NULL
                ORDER BY 1
                LIMIT ?
                """,
                [maximum_safety_values],
            ).fetchall()

            profile["safety_distinct_values"] = [str(safety_row[0]) for safety_row in safety_rows]

        column_profiles.append(profile)

    return {
        "engine": "duckdb",
        "schema": schema_name,
        "relation": relation_name,
        "row_count": row_count,
        "column_profiles": column_profiles,
    }


def _sqlite_profile_relation(
    connection: sqlite3.Connection,
    relation_name: str,
    primitives: list[dict[str, Any]],
    maximum_safety_values: int,
) -> dict[str, Any]:
    relation_identifier = _quote_identifier(relation_name)

    expressions = ["COUNT(*) AS row_count"]

    mappings_by_column: dict[
        str,
        list[
            tuple[
                str,
                str,
            ]
        ],
    ] = {}

    for index, primitive in enumerate(primitives):
        column_name = str(primitive["column"])

        data_type = str(primitive["data_type"])

        (
            metric_expressions,
            metric_mappings,
        ) = _metric_expressions(
            column_name,
            data_type,
            index,
            engine="sqlite",
        )

        expressions.extend(metric_expressions)

        mappings_by_column[column_name] = metric_mappings

    query = "SELECT\n    " + ",\n    ".join(expressions) + "\nFROM " + relation_identifier

    cursor = connection.execute(query)

    row = cursor.fetchone()

    if row is None:
        raise RuntimeError(f"SQLite profile query returned no row: {relation_name}")

    field_names = [str(field[0]) for field in cursor.description]

    values = dict(
        zip(
            field_names,
            row,
            strict=True,
        )
    )

    row_count = int(values["row_count"])

    column_profiles = []

    for primitive in primitives:
        column_name = str(primitive["column"])

        metrics: dict[str, Any] = {}

        for alias, metric_name in mappings_by_column[column_name]:
            metrics[metric_name] = _json_value(values.get(alias))

        non_null_count = int(metrics.get("non_null_count") or 0)

        null_count = row_count - non_null_count

        null_ratio = (null_count / row_count) if row_count else None

        profile: dict[str, Any] = {
            "primitive_id": primitive["primitive_id"],
            "column": column_name,
            "data_type": primitive["data_type"],
            "nullable": primitive["nullable"],
            "roles": _effective_roles(primitive),
            "row_count": row_count,
            "null_count": null_count,
            "null_ratio": null_ratio,
            **metrics,
        }

        if profile["roles"]["safety"]:
            quoted_column = _quote_identifier(column_name)

            safety_rows = connection.execute(
                f"""
                SELECT DISTINCT
                    CAST(
                        {quoted_column}
                        AS TEXT
                    )
                FROM {relation_identifier}
                WHERE
                    {quoted_column}
                    IS NOT NULL
                ORDER BY 1
                LIMIT ?
                """,
                (maximum_safety_values,),
            ).fetchall()

            profile["safety_distinct_values"] = [str(safety_row[0]) for safety_row in safety_rows]

        column_profiles.append(profile)

    return {
        "engine": "sqlite",
        "schema": "main",
        "relation": relation_name,
        "row_count": row_count,
        "column_profiles": column_profiles,
    }


def _evaluate_profile(
    relation_profile: dict[str, Any],
    *,
    high_null_ratio: float,
    material_null_ratio: float,
) -> tuple[
    list[dict[str, Any]],
    list[dict[str, Any]],
]:
    issues: list[dict[str, Any]] = []

    safety_violations: list[dict[str, Any]] = []

    relation_key = (
        str(relation_profile["engine"])
        + ":"
        + str(relation_profile["schema"])
        + "."
        + str(relation_profile["relation"])
    )

    row_count = int(relation_profile["row_count"])

    raw_column_profiles = relation_profile["column_profiles"]

    if not isinstance(
        raw_column_profiles,
        list,
    ):
        raise RuntimeError("Column profiles must be a list.")

    has_temporal = False
    has_lineage = False

    for raw_profile in raw_column_profiles:
        if not isinstance(
            raw_profile,
            dict,
        ):
            raise RuntimeError("Column profile must be an object.")

        profile: dict[str, Any] = {str(key): value for key, value in raw_profile.items()}

        column_name = str(profile["column"])

        raw_roles = profile["roles"]

        if not isinstance(
            raw_roles,
            dict,
        ):
            raise RuntimeError("Column roles must be an object.")

        roles = {str(key): bool(value) for key, value in raw_roles.items()}

        has_temporal = has_temporal or roles.get(
            "temporal",
            False,
        )

        has_lineage = has_lineage or roles.get(
            "lineage",
            False,
        )

        null_ratio_raw = profile.get("null_ratio")

        null_ratio = (
            float(null_ratio_raw)
            if isinstance(
                null_ratio_raw,
                int | float,
            )
            else None
        )

        important_role = any(
            roles.get(
                role_name,
                False,
            )
            for role_name in (
                "identity",
                "temporal",
                "lineage",
                "geography",
                "verification",
            )
        )

        if (
            row_count > 0
            and important_role
            and null_ratio is not None
            and null_ratio >= high_null_ratio
        ):
            issues.append(
                {
                    "issue_type": ("high_null_important_primitive"),
                    "severity": "medium",
                    "relation": relation_key,
                    "column": column_name,
                    "primitive_id": profile["primitive_id"],
                    "null_ratio": null_ratio,
                    "engineering_only": True,
                }
            )

        elif (
            row_count > 0
            and important_role
            and null_ratio is not None
            and null_ratio >= material_null_ratio
        ):
            issues.append(
                {
                    "issue_type": ("material_null_important_primitive"),
                    "severity": "low",
                    "relation": relation_key,
                    "column": column_name,
                    "primitive_id": profile["primitive_id"],
                    "null_ratio": null_ratio,
                    "engineering_only": True,
                }
            )

        if row_count > 0 and int(profile.get("non_null_count") or 0) == 0 and important_role:
            issues.append(
                {
                    "issue_type": ("all_null_important_primitive"),
                    "severity": "high",
                    "relation": relation_key,
                    "column": column_name,
                    "primitive_id": profile["primitive_id"],
                    "engineering_only": True,
                }
            )

        if roles.get(
            "safety",
            False,
        ):
            normalized_name = column_name.lower()

            true_count = int(profile.get("true_count") or 0)

            safety_values_raw = profile.get(
                "safety_distinct_values",
                [],
            )

            safety_values = (
                [str(value) for value in safety_values_raw]
                if isinstance(
                    safety_values_raw,
                    list,
                )
                else []
            )

            if normalized_name in TRUE_BLOCKED_CONTROLS and true_count > 0:
                safety_violations.append(
                    {
                        "violation_type": ("blocked_control_true"),
                        "relation": relation_key,
                        "column": column_name,
                        "true_count": true_count,
                        "values": safety_values,
                    }
                )

            if normalized_name == "operating_mode" and any(
                value.lower() != "shadow" for value in safety_values
            ):
                safety_violations.append(
                    {
                        "violation_type": ("unsafe_operating_mode"),
                        "relation": relation_key,
                        "column": column_name,
                        "values": safety_values,
                    }
                )

    if row_count > 0 and not has_temporal:
        issues.append(
            {
                "issue_type": ("nonempty_relation_without_temporal_primitive"),
                "severity": "medium",
                "relation": relation_key,
                "engineering_only": True,
            }
        )

    if row_count > 0 and not has_lineage:
        issues.append(
            {
                "issue_type": ("nonempty_relation_without_lineage_primitive"),
                "severity": "medium",
                "relation": relation_key,
                "engineering_only": True,
            }
        )

    return (
        issues,
        safety_violations,
    )


def build_primitive_quality_profile(
    project_root: Path,
    *,
    write_contracts: bool = True,
) -> dict[str, Any]:
    config = _load_config(project_root)

    inventory = _load_object(project_root / "docs" / "data_contracts" / "primitive_inventory.json")

    if not inventory.get("inventory_ready"):
        raise RuntimeError("Primitive inventory is not ready.")

    raw_primitives = inventory.get("primitives")

    if not isinstance(
        raw_primitives,
        list,
    ):
        raise RuntimeError("Primitive inventory contains no primitive list.")

    grouped: dict[
        tuple[str, str, str],
        list[dict[str, Any]],
    ] = defaultdict(list)

    for raw_primitive in raw_primitives:
        if not isinstance(
            raw_primitive,
            dict,
        ):
            raise RuntimeError("Primitive must be an object.")

        primitive: dict[str, Any] = {str(key): value for key, value in raw_primitive.items()}

        key = (
            str(primitive["engine"]),
            str(primitive["schema"]),
            str(primitive["relation"]),
        )

        grouped[key].append(primitive)

    raw_thresholds = config["thresholds"]

    if not isinstance(
        raw_thresholds,
        dict,
    ):
        raise RuntimeError("Threshold object is malformed.")

    high_null_ratio = float(raw_thresholds["high_null_ratio"])

    material_null_ratio = float(raw_thresholds["material_null_ratio"])

    maximum_safety_values = int(raw_thresholds["maximum_safety_distinct_values"])

    warehouse_path = project_root / "data" / "warehouse" / "cre.duckdb"

    control_path = project_root / "data" / "control" / "operations.sqlite3"

    duckdb_connection = duckdb.connect(
        str(warehouse_path),
        read_only=True,
    )

    duckdb_connection.execute("SET threads = 2")

    sqlite_connection = sqlite3.connect(
        ("file:" + str(control_path) + "?mode=ro"),
        uri=True,
    )

    relation_profiles = []
    query_errors = []

    try:
        for (
            engine,
            schema_name,
            relation_name,
        ), primitives in sorted(grouped.items()):
            try:
                if engine == "duckdb":
                    relation_profile = _duckdb_profile_relation(
                        duckdb_connection,
                        schema_name,
                        relation_name,
                        primitives,
                        maximum_safety_values,
                    )

                elif engine == "sqlite":
                    relation_profile = _sqlite_profile_relation(
                        sqlite_connection,
                        relation_name,
                        primitives,
                        maximum_safety_values,
                    )

                else:
                    raise RuntimeError(f"Unknown engine: {engine}")

                relation_profiles.append(relation_profile)

            except Exception as exception:
                query_errors.append(
                    {
                        "engine": engine,
                        "schema": schema_name,
                        "relation": relation_name,
                        "error_type": type(exception).__name__,
                        "error_message": str(exception),
                    }
                )

    finally:
        duckdb_connection.close()
        sqlite_connection.close()

    issues = []
    safety_violations = []

    for relation_profile in relation_profiles:
        (
            relation_issues,
            relation_safety_violations,
        ) = _evaluate_profile(
            relation_profile,
            high_null_ratio=(high_null_ratio),
            material_null_ratio=(material_null_ratio),
        )

        issues.extend(relation_issues)

        safety_violations.extend(relation_safety_violations)

    for query_error in query_errors:
        issues.append(
            {
                "issue_type": ("relation_profile_query_failed"),
                "severity": "high",
                "relation": (
                    str(query_error["engine"])
                    + ":"
                    + str(query_error["schema"])
                    + "."
                    + str(query_error["relation"])
                ),
                "error_type": query_error["error_type"],
                "error_message": query_error["error_message"],
                "engineering_only": True,
            }
        )

    for safety_violation in safety_violations:
        issues.append(
            {
                "issue_type": (safety_violation["violation_type"]),
                "severity": "critical",
                "relation": (safety_violation["relation"]),
                "column": (safety_violation["column"]),
                "engineering_only": False,
            }
        )

    sorted_issues = sorted(
        issues,
        key=lambda issue: (
            SEVERITY_ORDER.get(
                str(
                    issue.get(
                        "severity",
                        "low",
                    )
                ),
                99,
            ),
            str(
                issue.get(
                    "relation",
                    "",
                )
            ),
            str(
                issue.get(
                    "column",
                    "",
                )
            ),
            str(
                issue.get(
                    "issue_type",
                    "",
                )
            ),
        ),
    )

    issue_counts = Counter(str(issue["issue_type"]) for issue in sorted_issues)

    severity_counts = Counter(str(issue["severity"]) for issue in sorted_issues)

    profiled_primitive_count = sum(
        len(relation_profile["column_profiles"]) for relation_profile in relation_profiles
    )

    nonempty_relation_count = sum(
        int(relation_profile["row_count"]) > 0 for relation_profile in relation_profiles
    )

    full_report: dict[str, Any] = {
        "model_version": ("cre-foundry-primitive-quality-v1"),
        "inventory_primitive_count": inventory["primitive_count"],
        "inventory_relation_count": inventory["relation_count"],
        "profiled_primitive_count": (profiled_primitive_count),
        "profiled_relation_count": len(relation_profiles),
        "nonempty_relation_count": (nonempty_relation_count),
        "query_error_count": len(query_errors),
        "query_errors": query_errors,
        "issue_count": len(sorted_issues),
        "issue_counts": dict(sorted(issue_counts.items())),
        "severity_counts": dict(sorted(severity_counts.items())),
        "safety_violation_count": len(safety_violations),
        "safety_violations": (safety_violations),
        "relation_profiles": (relation_profiles),
        "policy": EXPECTED_POLICY,
        "profile_ready": (
            not query_errors and profiled_primitive_count == int(inventory["primitive_count"])
        ),
        "safety_ready": (not safety_violations),
        "automatic_acquisition_ready": False,
        "automatic_snapshot_registration_ready": False,
        "browser_execution_ready": False,
        "computer_vision_execution_ready": False,
        "production_ranking_ready": False,
        "outreach_ready": False,
    }

    summary: dict[str, Any] = {
        "model_version": ("cre-foundry-primitive-quality-summary-v1"),
        "inventory_primitive_count": (full_report["inventory_primitive_count"]),
        "profiled_primitive_count": (profiled_primitive_count),
        "inventory_relation_count": (full_report["inventory_relation_count"]),
        "profiled_relation_count": len(relation_profiles),
        "nonempty_relation_count": (nonempty_relation_count),
        "query_error_count": len(query_errors),
        "issue_count": len(sorted_issues),
        "issue_counts": full_report["issue_counts"],
        "severity_counts": full_report["severity_counts"],
        "safety_violation_count": len(safety_violations),
        "profile_ready": full_report["profile_ready"],
        "safety_ready": full_report["safety_ready"],
        "policy": EXPECTED_POLICY,
        "automatic_acquisition_ready": False,
        "automatic_snapshot_registration_ready": False,
        "browser_execution_ready": False,
        "computer_vision_execution_ready": False,
        "production_ranking_ready": False,
        "outreach_ready": False,
    }

    remediation: dict[str, Any] = {
        "model_version": ("cre-foundry-primitive-remediation-v1"),
        "purpose": ("data_engineering_remediation_order_only"),
        "opportunity_ranking": False,
        "account_ranking": False,
        "issue_count": len(sorted_issues),
        "issues": sorted_issues,
        "policy": EXPECTED_POLICY,
    }

    if write_contracts:
        contract_root = project_root / "docs" / "data_contracts"

        profile_path = contract_root / "primitive_quality_profile.json"

        summary_path = contract_root / "primitive_quality_summary.json"

        remediation_path = contract_root / "primitive_remediation_queue.json"

        full_report["contract_paths"] = {
            "profile": str(profile_path.relative_to(project_root)),
            "summary": str(summary_path.relative_to(project_root)),
            "remediation": str(remediation_path.relative_to(project_root)),
        }

        summary["contract_paths"] = full_report["contract_paths"]

        remediation["contract_paths"] = full_report["contract_paths"]

        _atomic_json(
            profile_path,
            full_report,
        )

        _atomic_json(
            summary_path,
            summary,
        )

        _atomic_json(
            remediation_path,
            remediation,
        )

    return {
        "summary": summary,
        "remediation": remediation,
        "profile": full_report,
    }
