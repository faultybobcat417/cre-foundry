from __future__ import annotations

from pathlib import Path
from typing import Any

import duckdb

from cre_foundry.bulk_storage import write_json_atomic
from cre_foundry.odbus_entities import warehouse_path


def _scalar(
    connection: duckdb.DuckDBPyConnection,
    query: str,
) -> int:
    row = connection.execute(query).fetchone()

    if row is None:
        raise RuntimeError("DuckDB scalar query returned no row.")

    return int(row[0])


def build_odbus_industrial_segments(
    project_root: Path,
) -> dict[str, Any]:
    warehouse = warehouse_path(project_root)

    sql_path = project_root / "sql" / "odbus_industrial_segments.sql"

    connection = duckdb.connect(str(warehouse))

    try:
        connection.execute(sql_path.read_text(encoding="utf-8"))

        candidate_entities = _scalar(
            connection,
            """
            SELECT count(*)
            FROM silver.odbus_industrial_entities
            """,
        )

        core_pool = _scalar(
            connection,
            """
            SELECT count(*)
            FROM silver.odbus_industrial_entities
            WHERE core_pool_eligible
            """,
        )

        baseline_eligible = _scalar(
            connection,
            """
            SELECT count(*)
            FROM silver.odbus_industrial_entities
            WHERE baseline_eligible
            """,
        )

        review_entities = _scalar(
            connection,
            """
            SELECT count(*)
            FROM silver.odbus_industrial_entities
            WHERE segment_tier = 'review'
            """,
        )

        unresolved_entities = _scalar(
            connection,
            """
            SELECT count(*)
            FROM silver.odbus_industrial_entities
            WHERE resolution_status = 'unresolved_split'
            """,
        )

        outreach_eligible = _scalar(
            connection,
            """
            SELECT count(*)
            FROM silver.odbus_industrial_entities
            WHERE outreach_eligible
            """,
        )

        missing_primary_naics = _scalar(
            connection,
            """
            SELECT count(*)
            FROM silver.odbus_entities
            WHERE naics_primary IS NULL
            """,
        )

        result = connection.execute(
            """
            SELECT
                segment_tier,
                segment_name,
                entities,
                baseline_eligible_entities,
                core_pool_entities,
                unresolved_entities
            FROM silver.odbus_industrial_segment_summary
            ORDER BY
                segment_tier,
                entities DESC,
                segment_name
            """
        )

        distribution = [
            {
                "segment_tier": row[0],
                "segment_name": row[1],
                "entities": int(row[2]),
                "baseline_eligible_entities": int(row[3]),
                "core_pool_entities": int(row[4]),
                "unresolved_entities": int(row[5]),
            }
            for row in result.fetchall()
        ]

    finally:
        connection.close()

    if outreach_eligible != 0:
        raise RuntimeError("Historical ODBus entities became outreach-eligible.")

    report = {
        "model_version": "odbus-industrial-v1",
        "warehouse_path": str(warehouse.relative_to(project_root)),
        "candidate_entities": candidate_entities,
        "baseline_eligible_entities": (baseline_eligible),
        "core_pool_entities": core_pool,
        "review_entities": review_entities,
        "unresolved_entities": unresolved_entities,
        "entities_missing_primary_naics": (missing_primary_naics),
        "outreach_eligible_entities": (outreach_eligible),
        "distribution": distribution,
        "policy": {
            "core": [
                "manufacturing",
                "wholesale",
                "transport_warehousing",
            ],
            "adjacent": [
                "construction_trades",
                "industrial_facility_services",
            ],
            "review": [
                "broad_construction_review",
                "broad_support_review",
                "mixed_industrial_evidence",
            ],
            "missing_primary_naics": ("Not classified automatically."),
            "historical_constraint": ("No entity is outreach-eligible."),
        },
    }

    contract_path = (
        project_root / "docs" / "data_contracts" / "statscan_odbus_industrial_segments.json"
    )

    write_json_atomic(
        contract_path,
        report,
    )

    report["contract_path"] = str(contract_path.relative_to(project_root))

    return report
