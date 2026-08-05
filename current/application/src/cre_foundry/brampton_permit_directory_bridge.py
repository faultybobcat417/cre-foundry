from __future__ import annotations

from pathlib import Path
from typing import Any

import duckdb

from cre_foundry.brampton_permit_entity_bridge import (
    normalize_address,
)
from cre_foundry.bulk_storage import (
    write_json_atomic,
)
from cre_foundry.odbus_entities import (
    warehouse_path,
)


def _scalar(
    connection: duckdb.DuckDBPyConnection,
    query: str,
) -> int:
    row = connection.execute(query).fetchone()

    if row is None:
        raise RuntimeError("DuckDB scalar query returned no row.")

    return int(row[0])


def build_brampton_permit_directory_bridge(
    project_root: Path,
) -> dict[str, Any]:
    warehouse = warehouse_path(project_root)

    connection = duckdb.connect(str(warehouse))

    try:
        permit_rows = connection.execute(
            """
            SELECT
                source_record_id,
                object_id,
                permit_number,
                application_at_utc,
                event_type,
                signal_strength,
                address_raw
            FROM
                silver.brampton_active_permit_signals
            ORDER BY
                application_at_utc DESC,
                object_id DESC
            """
        ).fetchall()

        directory_count = _scalar(
            connection,
            """
            SELECT count(*)
            FROM
                silver.brampton_business_directory
            """,
        )

        duplicate_global_ids = _scalar(
            connection,
            """
            SELECT
                count(*)
                - count(DISTINCT global_id)
            FROM
                silver.brampton_business_directory
            """,
        )

        non_operational_directory_rows = _scalar(
            connection,
            """
            SELECT count(*)
            FROM
                silver.brampton_business_directory
            WHERE
                NOT directory_operational_at_snapshot
            """,
        )

        directory_safety_violations = _scalar(
            connection,
            """
            SELECT count(*)
            FROM
                silver.brampton_business_directory
            WHERE
                commercial_requirement_verified
                OR decision_maker_verified
                OR outreach_eligible
            """,
        )

        if duplicate_global_ids != 0:
            raise RuntimeError("Directory GLOBALIDs are not unique.")

        if non_operational_directory_rows != 0:
            raise RuntimeError("Directory silver contains non-operational records.")

        if directory_safety_violations != 0:
            raise RuntimeError("Directory silver contains invalid safety assertions.")

        normalized_permits = [
            (
                source_record_id,
                object_id,
                permit_number,
                application_at_utc,
                event_type,
                signal_strength,
                address_raw,
                normalize_address(
                    address_raw,
                    remove_unit=False,
                ),
                normalize_address(
                    address_raw,
                    remove_unit=True,
                ),
            )
            for (
                source_record_id,
                object_id,
                permit_number,
                application_at_utc,
                event_type,
                signal_strength,
                address_raw,
            ) in permit_rows
        ]

        connection.execute("BEGIN")

        connection.execute(
            """
            CREATE SCHEMA IF NOT EXISTS silver
            """
        )

        connection.execute(
            """
            CREATE OR REPLACE TEMP TABLE
                normalized_active_permits (
                    permit_source_record_id VARCHAR,
                    object_id BIGINT,
                    permit_number VARCHAR,
                    application_at_utc TIMESTAMPTZ,
                    event_type VARCHAR,
                    signal_strength VARCHAR,
                    address_raw VARCHAR,
                    normalized_full_address VARCHAR,
                    normalized_base_address VARCHAR
                )
            """
        )

        if normalized_permits:
            connection.executemany(
                """
                INSERT INTO
                    normalized_active_permits
                VALUES (
                    ?, ?, ?, ?, ?, ?, ?, ?, ?
                )
                """,
                normalized_permits,
            )

        connection.execute(
            """
            CREATE OR REPLACE TABLE
                silver.brampton_permit_directory_match_candidates
            AS
            WITH full_matches AS (
                SELECT
                    permit.permit_source_record_id,
                    permit.permit_number,
                    directory.source_record_id
                        AS directory_source_record_id,
                    directory.global_id
                        AS directory_global_id,
                    directory.company_name,
                    directory.business_full_address,
                    directory.unit,
                    directory.postal_code,
                    directory.phone,
                    directory.website,
                    directory.naics_2,
                    directory.naics_6,
                    directory.product_description,
                    directory.employee_group,
                    directory.employee_count_min,
                    directory.employee_count_max,
                    directory.gfa_square_feet,
                    directory.directory_operational_at_snapshot,
                    directory.as_of_timestamp
                        AS directory_as_of_timestamp,
                    'exact_full' AS match_method
                FROM
                    normalized_active_permits
                        AS permit
                INNER JOIN
                    silver.brampton_business_directory
                        AS directory
                ON
                    permit.normalized_full_address
                    =
                    directory.normalized_full_address
            ),
            permits_with_full_match AS (
                SELECT DISTINCT
                    permit_source_record_id
                FROM full_matches
            ),
            base_matches AS (
                SELECT
                    permit.permit_source_record_id,
                    permit.permit_number,
                    directory.source_record_id
                        AS directory_source_record_id,
                    directory.global_id
                        AS directory_global_id,
                    directory.company_name,
                    directory.business_full_address,
                    directory.unit,
                    directory.postal_code,
                    directory.phone,
                    directory.website,
                    directory.naics_2,
                    directory.naics_6,
                    directory.product_description,
                    directory.employee_group,
                    directory.employee_count_min,
                    directory.employee_count_max,
                    directory.gfa_square_feet,
                    directory.directory_operational_at_snapshot,
                    directory.as_of_timestamp
                        AS directory_as_of_timestamp,
                    'exact_base' AS match_method
                FROM
                    normalized_active_permits
                        AS permit
                INNER JOIN
                    silver.brampton_business_directory
                        AS directory
                ON
                    permit.normalized_base_address
                    =
                    directory.normalized_base_address
                LEFT JOIN
                    permits_with_full_match
                        AS full_match
                ON
                    permit.permit_source_record_id
                    =
                    full_match.permit_source_record_id
                WHERE
                    full_match.permit_source_record_id
                    IS NULL
            ),
            all_matches AS (
                SELECT *
                FROM full_matches

                UNION ALL

                SELECT *
                FROM base_matches
            )
            SELECT
                *,
                row_number() OVER (
                    PARTITION BY
                        permit_source_record_id
                    ORDER BY
                        directory_global_id
                )::INTEGER
                    AS candidate_rank,
                count(*) OVER (
                    PARTITION BY
                        permit_source_record_id
                )::INTEGER
                    AS candidate_count,
                true
                    AS address_evidence_only,
                false
                    AS permit_occupant_verified,
                false
                    AS commercial_requirement_verified,
                false
                    AS decision_maker_verified,
                false
                    AS outreach_eligible
            FROM all_matches
            """
        )

        connection.execute(
            """
            CREATE OR REPLACE TABLE
                silver.brampton_permit_directory_resolution
            AS
            WITH candidate_summary AS (
                SELECT
                    permit_source_record_id,
                    min(match_method)
                        AS match_method,
                    count(*)::INTEGER
                        AS candidate_count
                FROM
                    silver.brampton_permit_directory_match_candidates
                GROUP BY
                    permit_source_record_id
            )
            SELECT
                permit.permit_source_record_id,
                permit.object_id,
                permit.permit_number,
                permit.application_at_utc,
                permit.event_type,
                permit.signal_strength,
                permit.address_raw,
                permit.normalized_full_address,
                permit.normalized_base_address,
                coalesce(
                    summary.match_method,
                    'none'
                ) AS match_method,
                CASE
                    WHEN
                        coalesce(
                            summary.candidate_count,
                            0
                        ) = 0
                    THEN 'unmatched'
                    WHEN
                        summary.candidate_count = 1
                    THEN 'unique'
                    ELSE 'ambiguous'
                END AS match_status,
                coalesce(
                    summary.candidate_count,
                    0
                )::INTEGER AS candidate_count,
                (
                    coalesce(
                        summary.candidate_count,
                        0
                    ) > 0
                ) AS current_directory_address_match,
                false AS permit_occupant_verified,
                false AS commercial_requirement_verified,
                false AS decision_maker_verified,
                false AS outreach_eligible
            FROM
                normalized_active_permits
                    AS permit
            LEFT JOIN
                candidate_summary
                    AS summary
            ON
                permit.permit_source_record_id
                =
                summary.permit_source_record_id
            """
        )

        connection.execute(
            """
            CREATE OR REPLACE VIEW
                silver.brampton_permit_directory_unique_address_links
            AS
            SELECT
                resolution.permit_source_record_id,
                resolution.object_id,
                resolution.permit_number,
                resolution.application_at_utc,
                resolution.event_type,
                resolution.signal_strength,
                resolution.address_raw,
                resolution.match_method,
                candidate.directory_source_record_id,
                candidate.directory_global_id,
                candidate.company_name,
                candidate.business_full_address,
                candidate.unit,
                candidate.postal_code,
                candidate.phone,
                candidate.website,
                candidate.naics_2,
                candidate.naics_6,
                candidate.product_description,
                candidate.employee_group,
                candidate.employee_count_min,
                candidate.employee_count_max,
                candidate.gfa_square_feet,
                candidate.directory_operational_at_snapshot,
                candidate.directory_as_of_timestamp,
                true AS address_evidence_only,
                false AS permit_occupant_verified,
                false AS commercial_requirement_verified,
                false AS decision_maker_verified,
                false AS outreach_eligible
            FROM
                silver.brampton_permit_directory_resolution
                    AS resolution
            INNER JOIN
                silver.brampton_permit_directory_match_candidates
                    AS candidate
            ON
                resolution.permit_source_record_id
                =
                candidate.permit_source_record_id
            WHERE
                resolution.match_status = 'unique'
                AND resolution.candidate_count = 1
            """
        )

        signal_count = _scalar(
            connection,
            """
            SELECT count(*)
            FROM
                silver.brampton_permit_directory_resolution
            """,
        )

        unique_signal_count = _scalar(
            connection,
            """
            SELECT count(*)
            FROM
                silver.brampton_permit_directory_resolution
            WHERE match_status = 'unique'
            """,
        )

        ambiguous_signal_count = _scalar(
            connection,
            """
            SELECT count(*)
            FROM
                silver.brampton_permit_directory_resolution
            WHERE match_status = 'ambiguous'
            """,
        )

        unmatched_signal_count = _scalar(
            connection,
            """
            SELECT count(*)
            FROM
                silver.brampton_permit_directory_resolution
            WHERE match_status = 'unmatched'
            """,
        )

        candidate_count = _scalar(
            connection,
            """
            SELECT count(*)
            FROM
                silver.brampton_permit_directory_match_candidates
            """,
        )

        unique_link_count = _scalar(
            connection,
            """
            SELECT count(*)
            FROM
                silver.brampton_permit_directory_unique_address_links
            """,
        )

        unique_directory_record_count = _scalar(
            connection,
            """
            SELECT count(
                DISTINCT directory_global_id
            )
            FROM
                silver.brampton_permit_directory_unique_address_links
            """,
        )

        operational_candidate_count = _scalar(
            connection,
            """
            SELECT count(*)
            FROM
                silver.brampton_permit_directory_match_candidates
            WHERE
                directory_operational_at_snapshot
            """,
        )

        occupant_verified_count = _scalar(
            connection,
            """
            SELECT count(*)
            FROM
                silver.brampton_permit_directory_match_candidates
            WHERE
                permit_occupant_verified
            """,
        )

        commercial_requirement_count = _scalar(
            connection,
            """
            SELECT count(*)
            FROM
                silver.brampton_permit_directory_match_candidates
            WHERE
                commercial_requirement_verified
            """,
        )

        decision_maker_count = _scalar(
            connection,
            """
            SELECT count(*)
            FROM
                silver.brampton_permit_directory_match_candidates
            WHERE
                decision_maker_verified
            """,
        )

        outreach_count = _scalar(
            connection,
            """
            SELECT
                (
                    SELECT count(*)
                    FROM
                        silver.brampton_permit_directory_resolution
                    WHERE outreach_eligible
                )
                +
                (
                    SELECT count(*)
                    FROM
                        silver.brampton_permit_directory_match_candidates
                    WHERE outreach_eligible
                )
            """,
        )

        distribution_rows = connection.execute(
            """
            SELECT
                match_method
                || '_'
                || match_status
                    AS resolution_type,
                count(*) AS records
            FROM
                silver.brampton_permit_directory_resolution
            GROUP BY
                resolution_type
            ORDER BY
                resolution_type
            """
        ).fetchall()

        connection.execute("COMMIT")

    except Exception:
        connection.execute("ROLLBACK")
        raise

    finally:
        connection.close()

    if signal_count != len(permit_rows):
        raise RuntimeError("Permit-directory resolution count mismatch.")

    if unique_signal_count + ambiguous_signal_count + unmatched_signal_count != signal_count:
        raise RuntimeError("Permit-directory statuses do not reconcile.")

    if unique_link_count != unique_signal_count:
        raise RuntimeError("Unique directory-link count does not match unique signals.")

    if operational_candidate_count != candidate_count:
        raise RuntimeError(
            "Permit-directory candidates include a non-operational directory record."
        )

    if (
        occupant_verified_count
        or commercial_requirement_count
        or decision_maker_count
        or outreach_count
    ):
        raise RuntimeError("Permit-directory bridge violated safety flags.")

    match_distribution = {
        str(resolution_type): int(count) for resolution_type, count in (distribution_rows)
    }

    report: dict[str, Any] = {
        "model_version": ("brampton-permit-directory-bridge-v1"),
        "directory_record_count": (directory_count),
        "signal_count": signal_count,
        "unique_exact_signal_count": (unique_signal_count),
        "ambiguous_exact_signal_count": (ambiguous_signal_count),
        "unmatched_signal_count": (unmatched_signal_count),
        "candidate_row_count": (candidate_count),
        "unique_link_row_count": (unique_link_count),
        "unique_link_directory_record_count": (unique_directory_record_count),
        "directory_operational_candidate_count": (operational_candidate_count),
        "permit_occupant_verified_count": (occupant_verified_count),
        "commercial_requirement_verified_count": (commercial_requirement_count),
        "decision_maker_verified_count": (decision_maker_count),
        "outreach_eligible_count": (outreach_count),
        "match_distribution": (match_distribution),
        "resolution_table": ("silver.brampton_permit_directory_resolution"),
        "candidate_table": ("silver.brampton_permit_directory_match_candidates"),
        "unique_link_view": ("silver.brampton_permit_directory_unique_address_links"),
        "policy": {
            "allowed_match_methods": [
                "exact_full",
                "exact_base",
            ],
            "full_address_precedes_base_address": (True),
            "fuzzy_matching_enabled": False,
            "unique_address_link_means_occupant": (False),
            "ambiguous_links_promoted": False,
            "unmatched_links_promoted": False,
            "permit_occupant_verified": False,
            "commercial_requirement_verified": (False),
            "decision_maker_verified": False,
            "outreach_eligible": False,
        },
    }

    contract_path = (
        project_root / "docs" / "data_contracts" / "brampton_permit_directory_bridge.json"
    )

    report["contract_path"] = str(contract_path.relative_to(project_root))

    write_json_atomic(
        contract_path,
        report,
    )

    return report
