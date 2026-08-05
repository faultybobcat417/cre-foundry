from __future__ import annotations

from pathlib import Path
from typing import Any

import duckdb

from cre_foundry.bulk_storage import write_json_atomic


def warehouse_path(
    project_root: Path,
) -> Path:
    candidates = sorted((project_root / "data" / "warehouse").glob("*.duckdb"))

    if len(candidates) != 1:
        raise RuntimeError(f"Expected exactly one DuckDB warehouse, found {len(candidates)}.")

    return candidates[0]


def _fetch_scalar_int(
    connection: duckdb.DuckDBPyConnection,
    query: str,
) -> int:
    row = connection.execute(query).fetchone()

    if row is None:
        raise RuntimeError("DuckDB scalar query returned no row.")

    return int(row[0])


def build_odbus_entity_model(
    project_root: Path,
) -> dict[str, Any]:
    warehouse = warehouse_path(project_root)

    sql_path = project_root / "sql" / "odbus_entity_model.sql"

    connection = duckdb.connect(str(warehouse))

    try:
        connection.execute(sql_path.read_text(encoding="utf-8"))

        source_count = _fetch_scalar_int(
            connection,
            """
                SELECT count(*)
                FROM silver.odbus_target_businesses
                """,
        )

        observation_count = _fetch_scalar_int(
            connection,
            """
                SELECT count(*)
                FROM silver.odbus_entity_observations
                """,
        )

        entity_count = _fetch_scalar_int(
            connection,
            """
                SELECT count(*)
                FROM silver.odbus_entities
                """,
        )

        ambiguous_clusters = _fetch_scalar_int(
            connection,
            """
                SELECT count(
                    DISTINCT unresolved_cluster_id
                )
                FROM silver.odbus_entity_observations
                WHERE unresolved_cluster_id IS NOT NULL
                """,
        )

        rows = connection.execute(
            """
            SELECT
                resolution_status,
                cluster_classification,
                entity_count,
                observation_count
            FROM silver.odbus_entity_resolution_summary
            ORDER BY
                resolution_status,
                cluster_classification
            """
        ).fetchall()

        classifications = [
            {
                "resolution_status": row[0],
                "cluster_classification": row[1],
                "entity_count": int(row[2]),
                "observation_count": int(row[3]),
            }
            for row in rows
        ]

    finally:
        connection.close()

    if observation_count != source_count:
        raise RuntimeError("Observation mapping lost source rows.")

    report = {
        "model_version": "odbus-entity-v1",
        "warehouse_path": str(warehouse.relative_to(project_root)),
        "source_record_count": source_count,
        "observation_count": observation_count,
        "entity_count": entity_count,
        "collapsed_observation_count": (observation_count - entity_count),
        "ambiguous_cluster_count": (ambiguous_clusters),
        "classifications": classifications,
        "entity_table": ("silver.odbus_entities"),
        "observation_table": ("silver.odbus_entity_observations"),
        "summary_view": ("silver.odbus_entity_resolution_summary"),
        "policy": {
            "safe_identity_clusters": (
                "Collapse rows sharing identity fields; retain every source observation."
            ),
            "attribute_variations": (
                "NAICS, employee and sector differences remain attached to observations."
            ),
            "ambiguous_identity": (
                "Do not collapse clusters differing by "
                "address, business ID, provider or municipality."
            ),
            "current_status_verified": False,
        },
    }

    contract_path = project_root / "docs" / "data_contracts" / "statscan_odbus_entity_model.json"

    write_json_atomic(
        contract_path,
        report,
    )

    report["contract_path"] = str(contract_path.relative_to(project_root))

    return report
