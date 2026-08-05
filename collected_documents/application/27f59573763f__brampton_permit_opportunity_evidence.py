from __future__ import annotations

from pathlib import Path
from typing import Any

import duckdb

from cre_foundry.bulk_storage import write_json_atomic
from cre_foundry.odbus_entities import warehouse_path


def derive_evidence_status(
    reconciliation_state: str,
) -> str:
    mapping = {
        "corroborated_name_agreement": ("cross_source_corroborated"),
        "current_resolves_historical_ambiguity": ("current_resolves_historical_ambiguity"),
        "cross_source_name_conflict": ("cross_source_conflict"),
        "current_address_ambiguity": ("current_address_ambiguity"),
        "historical_address_ambiguity": ("historical_address_ambiguity"),
        "cross_source_address_ambiguity": ("cross_source_address_ambiguity"),
        "current_only_address_evidence": ("current_only"),
        "historical_only_address_evidence": ("historical_only"),
        "current_vs_historical_ambiguity": ("cross_source_ambiguity"),
        "historical_vs_current_ambiguity": ("cross_source_ambiguity"),
        "unresolved": "unresolved",
        "unclassified": "unclassified",
    }

    return mapping.get(
        reconciliation_state,
        "review_required",
    )


def _scalar(
    connection: duckdb.DuckDBPyConnection,
    query: str,
) -> int:
    row = connection.execute(query).fetchone()

    if row is None:
        raise RuntimeError("DuckDB scalar query returned no row.")

    return int(row[0])


def build_brampton_permit_opportunity_evidence(
    project_root: Path,
) -> dict[str, Any]:
    warehouse = warehouse_path(project_root)

    connection = duckdb.connect(str(warehouse))

    transaction_active = False

    try:
        source_count = _scalar(
            connection,
            """
            SELECT count(*)
            FROM
                silver.brampton_permit_cross_source_reconciliation
            """,
        )

        duplicate_source_permits = _scalar(
            connection,
            """
            SELECT
                count(*)
                - count(
                    DISTINCT permit_source_record_id
                )
            FROM
                silver.brampton_permit_cross_source_reconciliation
            """,
        )

        duplicate_current_links = _scalar(
            connection,
            """
            SELECT
                count(*)
                - count(
                    DISTINCT permit_source_record_id
                )
            FROM
                silver.brampton_permit_directory_unique_address_links
            """,
        )

        if duplicate_source_permits != 0:
            raise RuntimeError("Cross-source reconciliation contains duplicate permits.")

        if duplicate_current_links != 0:
            raise RuntimeError("Current unique-link view contains duplicate permit records.")

        connection.execute("BEGIN")
        transaction_active = True

        connection.execute(
            """
            CREATE SCHEMA IF NOT EXISTS silver
            """
        )

        connection.execute(
            """
            CREATE OR REPLACE TABLE
                silver.brampton_permit_opportunity_evidence
            AS
            SELECT
                (
                    'brampton-permit-opportunity:'
                    ||
                    reconciliation.permit_source_record_id
                ) AS opportunity_evidence_id,

                reconciliation.permit_source_record_id,
                reconciliation.object_id,
                reconciliation.permit_number,
                reconciliation.application_at_utc,
                reconciliation.event_type,
                reconciliation.signal_strength,
                reconciliation.address_raw,

                reconciliation.reconciliation_class,
                reconciliation.reconciliation_state,

                CASE
                    WHEN
                        reconciliation.reconciliation_state
                        =
                        'corroborated_name_agreement'
                    THEN 'cross_source_corroborated'

                    WHEN
                        reconciliation.reconciliation_state
                        =
                        'current_resolves_historical_ambiguity'
                    THEN
                        'current_resolves_historical_ambiguity'

                    WHEN
                        reconciliation.reconciliation_state
                        =
                        'cross_source_name_conflict'
                    THEN 'cross_source_conflict'

                    WHEN
                        reconciliation.reconciliation_state
                        =
                        'current_address_ambiguity'
                    THEN 'current_address_ambiguity'

                    WHEN
                        reconciliation.reconciliation_state
                        =
                        'historical_address_ambiguity'
                    THEN 'historical_address_ambiguity'

                    WHEN
                        reconciliation.reconciliation_state
                        =
                        'cross_source_address_ambiguity'
                    THEN 'cross_source_address_ambiguity'

                    WHEN
                        reconciliation.reconciliation_state
                        =
                        'current_only_address_evidence'
                    THEN 'current_only'

                    WHEN
                        reconciliation.reconciliation_state
                        =
                        'historical_only_address_evidence'
                    THEN 'historical_only'

                    WHEN
                        reconciliation.reconciliation_state
                        =
                        'current_vs_historical_ambiguity'
                    THEN 'cross_source_ambiguity'

                    WHEN
                        reconciliation.reconciliation_state
                        =
                        'historical_vs_current_ambiguity'
                    THEN 'cross_source_ambiguity'

                    WHEN
                        reconciliation.reconciliation_state
                        =
                        'unresolved'
                    THEN 'unresolved'

                    WHEN
                        reconciliation.reconciliation_state
                        =
                        'unclassified'
                    THEN 'unclassified'

                    ELSE 'review_required'
                END AS evidence_status,

                reconciliation.historical_match_method,
                reconciliation.historical_match_status,
                reconciliation.historical_candidate_count,

                reconciliation.current_match_method,
                reconciliation.current_match_status,
                reconciliation.current_candidate_count,
                reconciliation.current_directory_address_match,

                reconciliation.historical_unique_entity_id,
                reconciliation.historical_unique_business_name,

                reconciliation.current_unique_global_id,
                reconciliation.current_unique_business_name,

                reconciliation.best_historical_entity_id,
                reconciliation.best_historical_business_name,
                reconciliation.best_current_global_id,
                reconciliation.best_current_business_name,

                reconciliation.name_similarity,
                reconciliation.normalized_name_exact,
                reconciliation.cross_source_name_alignment,

                reconciliation.historical_candidate_names_json,
                reconciliation.current_candidate_names_json,

                CASE
                    WHEN
                        current_link.company_name
                        IS NOT NULL
                    THEN current_link.company_name

                    WHEN
                        reconciliation.historical_match_status
                        = 'unique'
                    THEN
                        reconciliation.historical_unique_business_name

                    ELSE NULL
                END AS provisional_business_name,

                CASE
                    WHEN
                        current_link.company_name
                        IS NOT NULL
                    THEN 'current_brampton_directory'

                    WHEN
                        reconciliation.historical_match_status
                        = 'unique'
                    THEN 'historical_odbus'

                    ELSE NULL
                END AS provisional_business_source,

                current_link.directory_source_record_id,
                current_link.directory_global_id,
                current_link.business_full_address
                    AS current_directory_address,
                current_link.unit
                    AS current_directory_unit,
                current_link.postal_code
                    AS current_directory_postal_code,
                current_link.naics_2
                    AS current_directory_naics_2,
                current_link.naics_6
                    AS current_directory_naics_6,
                current_link.product_description
                    AS current_directory_product_description,
                current_link.employee_group
                    AS current_directory_employee_group,
                current_link.employee_count_min
                    AS current_directory_employee_count_min,
                current_link.employee_count_max
                    AS current_directory_employee_count_max,
                current_link.gfa_square_feet
                    AS current_directory_gfa_square_feet,
                (
                    current_link.phone IS NOT NULL
                ) AS current_directory_phone_present,
                (
                    current_link.website IS NOT NULL
                ) AS current_directory_website_present,
                current_link.directory_operational_at_snapshot
                    AS current_directory_operational_at_snapshot,
                current_link.directory_as_of_timestamp,

                (
                    reconciliation.reconciliation_state
                    = 'cross_source_name_conflict'
                ) AS cross_source_name_conflict_present,

                (
                    reconciliation.current_match_status
                    = 'ambiguous'
                ) AS current_address_ambiguity_present,

                (
                    reconciliation.historical_match_status
                    = 'ambiguous'
                ) AS historical_address_ambiguity_present,

                (
                    reconciliation.current_match_status
                    = 'unmatched'
                    AND
                    reconciliation.historical_match_status
                    = 'unmatched'
                ) AS no_address_candidate_present,

                reconciliation.review_required
                    AS high_information_review_required,

                (
                    reconciliation.reconciliation_state
                    = 'unresolved'
                ) AS unresolved_research_required,

                (
                    reconciliation.review_required
                    OR
                    reconciliation.reconciliation_state
                    = 'unresolved'
                ) AS manual_resolution_required,

                true AS identity_verification_required,
                true AS permit_occupancy_verification_required,
                true AS commercial_requirement_verification_required,
                true AS decision_maker_verification_required,
                true AS existing_client_exclusion_check_required,
                true AS protected_relationship_check_required,
                true AS active_assignment_conflict_check_required,
                true AS territory_restriction_check_required,
                true AS relationship_owner_check_required,
                true AS do_not_contact_check_required,

                false AS identity_verified,
                false AS permit_occupant_verified,
                false AS commercial_requirement_verified,
                false AS decision_maker_verified,
                false AS exclusions_cleared,
                false AS relationship_restrictions_cleared,
                false AS territory_cleared,
                false AS outreach_eligible,

                'shadow' AS operating_mode,
                false AS ranked,
                NULL::DOUBLE AS opportunity_score,
                NULL::INTEGER AS opportunity_rank
            FROM
                silver.brampton_permit_cross_source_reconciliation
                    AS reconciliation
            LEFT JOIN
                silver.brampton_permit_directory_unique_address_links
                    AS current_link
            ON
                reconciliation.permit_source_record_id
                =
                current_link.permit_source_record_id
            """
        )

        connection.execute(
            """
            CREATE OR REPLACE VIEW
                silver.brampton_permit_opportunity_review_queue
            AS
            SELECT *
            FROM
                silver.brampton_permit_opportunity_evidence
            WHERE
                high_information_review_required
            ORDER BY
                CASE signal_strength
                    WHEN 'high' THEN 1
                    WHEN 'medium' THEN 2
                    ELSE 3
                END,
                application_at_utc DESC,
                permit_number
            """
        )

        connection.execute(
            """
            CREATE OR REPLACE VIEW
                silver.brampton_permit_opportunity_unresolved
            AS
            SELECT *
            FROM
                silver.brampton_permit_opportunity_evidence
            WHERE
                unresolved_research_required
            ORDER BY
                CASE signal_strength
                    WHEN 'high' THEN 1
                    WHEN 'medium' THEN 2
                    ELSE 3
                END,
                application_at_utc DESC,
                permit_number
            """
        )

        connection.execute(
            """
            CREATE OR REPLACE VIEW
                silver.brampton_permit_opportunity_summary
            AS
            SELECT
                evidence_status,
                reconciliation_state,
                signal_strength,
                event_type,
                count(*) AS permit_signals,
                count(*) FILTER (
                    WHERE
                        high_information_review_required
                ) AS review_queue_signals,
                count(*) FILTER (
                    WHERE
                        unresolved_research_required
                ) AS unresolved_signals,
                count(*) FILTER (
                    WHERE
                        current_directory_operational_at_snapshot
                ) AS signals_with_current_directory_record
            FROM
                silver.brampton_permit_opportunity_evidence
            GROUP BY
                evidence_status,
                reconciliation_state,
                signal_strength,
                event_type
            """
        )

        record_count = _scalar(
            connection,
            """
            SELECT count(*)
            FROM
                silver.brampton_permit_opportunity_evidence
            """,
        )

        duplicate_opportunity_ids = _scalar(
            connection,
            """
            SELECT
                count(*)
                - count(
                    DISTINCT opportunity_evidence_id
                )
            FROM
                silver.brampton_permit_opportunity_evidence
            """,
        )

        duplicate_permit_ids = _scalar(
            connection,
            """
            SELECT
                count(*)
                - count(
                    DISTINCT permit_source_record_id
                )
            FROM
                silver.brampton_permit_opportunity_evidence
            """,
        )

        current_directory_record_count = _scalar(
            connection,
            """
            SELECT count(*)
            FROM
                silver.brampton_permit_opportunity_evidence
            WHERE
                directory_global_id IS NOT NULL
            """,
        )

        cross_source_corroborated_count = _scalar(
            connection,
            """
            SELECT count(*)
            FROM
                silver.brampton_permit_opportunity_evidence
            WHERE
                evidence_status
                = 'cross_source_corroborated'
            """,
        )

        review_queue_count = _scalar(
            connection,
            """
            SELECT count(*)
            FROM
                silver.brampton_permit_opportunity_review_queue
            """,
        )

        unresolved_count = _scalar(
            connection,
            """
            SELECT count(*)
            FROM
                silver.brampton_permit_opportunity_unresolved
            """,
        )

        ranked_count = _scalar(
            connection,
            """
            SELECT count(*)
            FROM
                silver.brampton_permit_opportunity_evidence
            WHERE
                ranked
                OR opportunity_score IS NOT NULL
                OR opportunity_rank IS NOT NULL
            """,
        )

        safety_violation_count = _scalar(
            connection,
            """
            SELECT count(*)
            FROM
                silver.brampton_permit_opportunity_evidence
            WHERE
                identity_verified
                OR permit_occupant_verified
                OR commercial_requirement_verified
                OR decision_maker_verified
                OR exclusions_cleared
                OR relationship_restrictions_cleared
                OR territory_cleared
                OR outreach_eligible
                OR operating_mode <> 'shadow'
            """,
        )

        missing_verification_gates = _scalar(
            connection,
            """
            SELECT count(*)
            FROM
                silver.brampton_permit_opportunity_evidence
            WHERE
                NOT identity_verification_required
                OR NOT permit_occupancy_verification_required
                OR NOT commercial_requirement_verification_required
                OR NOT decision_maker_verification_required
                OR NOT existing_client_exclusion_check_required
                OR NOT protected_relationship_check_required
                OR NOT active_assignment_conflict_check_required
                OR NOT territory_restriction_check_required
                OR NOT relationship_owner_check_required
                OR NOT do_not_contact_check_required
            """,
        )

        distribution_rows = connection.execute(
            """
            SELECT
                evidence_status,
                count(*) AS permit_signals
            FROM
                silver.brampton_permit_opportunity_evidence
            GROUP BY
                evidence_status
            ORDER BY
                evidence_status
            """
        ).fetchall()

        connection.execute("COMMIT")
        transaction_active = False

    except Exception:
        if transaction_active:
            connection.execute("ROLLBACK")

        raise

    finally:
        connection.close()

    if record_count != source_count:
        raise RuntimeError("Opportunity evidence count does not match cross-source reconciliation.")

    if duplicate_opportunity_ids != 0:
        raise RuntimeError("Opportunity evidence contains duplicate opportunity IDs.")

    if duplicate_permit_ids != 0:
        raise RuntimeError("Opportunity evidence contains duplicate permit records.")

    if ranked_count != 0:
        raise RuntimeError("Opportunity evidence was ranked before ranking governance was defined.")

    if safety_violation_count != 0:
        raise RuntimeError("Opportunity evidence violated safety gates.")

    if missing_verification_gates != 0:
        raise RuntimeError("Opportunity evidence is missing required verification gates.")

    evidence_distribution = {str(status): int(count) for status, count in distribution_rows}

    report: dict[str, Any] = {
        "model_version": ("brampton-permit-opportunity-evidence-v1"),
        "source_record_count": source_count,
        "record_count": record_count,
        "duplicate_opportunity_id_count": (duplicate_opportunity_ids),
        "duplicate_permit_id_count": (duplicate_permit_ids),
        "current_directory_record_count": (current_directory_record_count),
        "cross_source_corroborated_count": (cross_source_corroborated_count),
        "review_queue_count": review_queue_count,
        "unresolved_count": unresolved_count,
        "ranked_count": ranked_count,
        "safety_violation_count": (safety_violation_count),
        "missing_verification_gate_count": (missing_verification_gates),
        "evidence_status_distribution": (evidence_distribution),
        "table": ("silver.brampton_permit_opportunity_evidence"),
        "review_queue_view": ("silver.brampton_permit_opportunity_review_queue"),
        "unresolved_view": ("silver.brampton_permit_opportunity_unresolved"),
        "summary_view": ("silver.brampton_permit_opportunity_summary"),
        "policy": {
            "one_row_per_active_permit": True,
            "business_name_is_provisional": True,
            "current_directory_record_is_occupant_proof": (False),
            "cross_source_name_agreement_is_occupant_proof": (False),
            "ranking_enabled": False,
            "operating_mode": "shadow",
            "identity_verified": False,
            "permit_occupant_verified": False,
            "commercial_requirement_verified": False,
            "decision_maker_verified": False,
            "exclusions_cleared": False,
            "outreach_eligible": False,
        },
    }

    contract_path = (
        project_root / "docs" / "data_contracts" / "brampton_permit_opportunity_evidence.json"
    )

    report["contract_path"] = str(contract_path.relative_to(project_root))

    write_json_atomic(
        contract_path,
        report,
    )

    return report
