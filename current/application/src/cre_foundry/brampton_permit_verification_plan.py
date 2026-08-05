from __future__ import annotations

from pathlib import Path
from typing import Any

import duckdb

from cre_foundry.bulk_storage import write_json_atomic
from cre_foundry.odbus_entities import warehouse_path

STANDARD_GATE_COUNT = 10


def _scalar(
    connection: duckdb.DuckDBPyConnection,
    query: str,
) -> int:
    row = connection.execute(query).fetchone()

    if row is None:
        raise RuntimeError("DuckDB scalar query returned no row.")

    return int(row[0])


def build_brampton_permit_verification_plan(
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
                silver.brampton_permit_opportunity_evidence
            """,
        )

        duplicate_opportunities = _scalar(
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

        manual_resolution_count = _scalar(
            connection,
            """
            SELECT count(*)
            FROM
                silver.brampton_permit_opportunity_evidence
            WHERE
                manual_resolution_required
            """,
        )

        unsafe_source_rows = _scalar(
            connection,
            """
            SELECT count(*)
            FROM
                silver.brampton_permit_opportunity_evidence
            WHERE
                operating_mode <> 'shadow'
                OR ranked
                OR outreach_eligible
            """,
        )

        if duplicate_opportunities != 0:
            raise RuntimeError("Opportunity evidence contains duplicate records.")

        if unsafe_source_rows != 0:
            raise RuntimeError("Verification planning received unsafe source records.")

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
                silver.brampton_permit_verification_tasks
            AS
            WITH opportunities AS (
                SELECT
                    opportunity_evidence_id,
                    permit_source_record_id,
                    permit_number,
                    application_at_utc,
                    event_type,
                    signal_strength,
                    address_raw,
                    evidence_status,
                    provisional_business_name,
                    provisional_business_source,
                    high_information_review_required,
                    unresolved_research_required,
                    manual_resolution_required
                FROM
                    silver.brampton_permit_opportunity_evidence
            ),
            standard_gates AS (
                SELECT *
                FROM (
                    VALUES
                        (
                            'identity_verification',
                            1,
                            'identity',
                            (
                                'Verify the legal and operating identity '
                                ||
                                'attached to the permit address.'
                            ),
                            NULL
                        ),
                        (
                            'permit_occupancy_verification',
                            2,
                            'occupancy',
                            (
                                'Verify whether the candidate business is '
                                ||
                                'the applicant, tenant or intended occupant.'
                            ),
                            'identity_verification'
                        ),
                        (
                            'commercial_requirement_verification',
                            3,
                            'requirement',
                            (
                                'Verify a current or credible future '
                                ||
                                'commercial real-estate requirement.'
                            ),
                            'permit_occupancy_verification'
                        ),
                        (
                            'decision_maker_verification',
                            4,
                            'contact',
                            'Verify the relevant decision-maker and their role in the requirement.',
                            'commercial_requirement_verification'
                        ),
                        (
                            'existing_client_exclusion',
                            5,
                            'restriction',
                            'Check whether the account is an existing client.',
                            'identity_verification'
                        ),
                        (
                            'protected_relationship_check',
                            6,
                            'restriction',
                            (
                                'Check whether the account is a protected '
                                ||
                                'or broker-owned relationship.'
                            ),
                            'identity_verification'
                        ),
                        (
                            'active_assignment_conflict_check',
                            7,
                            'restriction',
                            'Check active mandates, listings, assignments and conflicts.',
                            'identity_verification'
                        ),
                        (
                            'territory_restriction_check',
                            8,
                            'restriction',
                            'Check territory, specialization and representative restrictions.',
                            'identity_verification'
                        ),
                        (
                            'relationship_owner_check',
                            9,
                            'restriction',
                            'Identify the internal relationship owner and required approval.',
                            'identity_verification'
                        ),
                        (
                            'do_not_contact_check',
                            10,
                            'restriction',
                            'Check do-not-contact records and other contact prohibitions.',
                            'identity_verification'
                        )
                ) AS gates(
                    gate_id,
                    task_order,
                    gate_category,
                    task_instruction,
                    prerequisite_gate_id
                )
            ),
            manual_tasks AS (
                SELECT
                    (
                        opportunity.opportunity_evidence_id
                        || ':evidence_resolution'
                    ) AS verification_task_id,

                    opportunity.opportunity_evidence_id,
                    opportunity.permit_source_record_id,
                    opportunity.permit_number,
                    opportunity.application_at_utc,
                    opportunity.event_type,
                    opportunity.signal_strength,
                    opportunity.address_raw,
                    opportunity.evidence_status,
                    opportunity.provisional_business_name,
                    opportunity.provisional_business_source,

                    'evidence_resolution'
                        AS gate_id,
                    0 AS task_order,
                    'resolution'
                        AS gate_category,
                    (
                        'Resolve conflicting, ambiguous '
                        'or missing business identity evidence.'
                    ) AS task_instruction,
                    NULL::VARCHAR
                        AS prerequisite_gate_id,

                    true AS required,
                    true AS blocking,
                    false AS automatic_clear_allowed,
                    true AS task_ready,

                    'not_started' AS task_status,
                    'unknown' AS verification_result,

                    NULL::VARCHAR AS evidence_source_type,
                    NULL::VARCHAR AS evidence_reference,
                    NULL::VARCHAR AS reviewer,
                    NULL::TIMESTAMPTZ AS reviewed_at,
                    NULL::VARCHAR AS review_notes,

                    (
                        CASE opportunity.signal_strength
                            WHEN 'high' THEN 0
                            WHEN 'medium' THEN 100
                            ELSE 200
                        END
                        +
                        CASE
                            WHEN
                                opportunity.high_information_review_required
                            THEN 0
                            WHEN
                                opportunity.unresolved_research_required
                            THEN 10
                            ELSE 20
                        END
                    )::INTEGER AS queue_priority,

                    true
                        AS workflow_priority_only,
                    false
                        AS opportunity_ranked,
                    false
                        AS gate_cleared,
                    false
                        AS outreach_eligible,
                    'shadow'
                        AS operating_mode
                FROM opportunities AS opportunity
                WHERE
                    opportunity.manual_resolution_required
            ),
            standard_tasks AS (
                SELECT
                    (
                        opportunity.opportunity_evidence_id
                        || ':'
                        || gate.gate_id
                    ) AS verification_task_id,

                    opportunity.opportunity_evidence_id,
                    opportunity.permit_source_record_id,
                    opportunity.permit_number,
                    opportunity.application_at_utc,
                    opportunity.event_type,
                    opportunity.signal_strength,
                    opportunity.address_raw,
                    opportunity.evidence_status,
                    opportunity.provisional_business_name,
                    opportunity.provisional_business_source,

                    gate.gate_id,
                    gate.task_order,
                    gate.gate_category,
                    gate.task_instruction,

                    CASE
                        WHEN
                            gate.gate_id
                            = 'identity_verification'
                            AND
                            opportunity.manual_resolution_required
                        THEN 'evidence_resolution'

                        ELSE gate.prerequisite_gate_id
                    END AS prerequisite_gate_id,

                    true AS required,
                    true AS blocking,
                    false AS automatic_clear_allowed,

                    (
                        gate.gate_id
                        = 'identity_verification'
                        AND
                        NOT opportunity.manual_resolution_required
                    ) AS task_ready,

                    'not_started' AS task_status,
                    'unknown' AS verification_result,

                    NULL::VARCHAR AS evidence_source_type,
                    NULL::VARCHAR AS evidence_reference,
                    NULL::VARCHAR AS reviewer,
                    NULL::TIMESTAMPTZ AS reviewed_at,
                    NULL::VARCHAR AS review_notes,

                    (
                        CASE opportunity.signal_strength
                            WHEN 'high' THEN 0
                            WHEN 'medium' THEN 100
                            ELSE 200
                        END
                        +
                        CASE
                            WHEN
                                opportunity.high_information_review_required
                            THEN 0
                            WHEN
                                opportunity.unresolved_research_required
                            THEN 10
                            ELSE 20
                        END
                        +
                        gate.task_order
                    )::INTEGER AS queue_priority,

                    true
                        AS workflow_priority_only,
                    false
                        AS opportunity_ranked,
                    false
                        AS gate_cleared,
                    false
                        AS outreach_eligible,
                    'shadow'
                        AS operating_mode
                FROM
                    opportunities AS opportunity
                CROSS JOIN
                    standard_gates AS gate
            )
            SELECT *
            FROM manual_tasks

            UNION ALL

            SELECT *
            FROM standard_tasks
            """
        )

        connection.execute(
            """
            CREATE OR REPLACE TABLE
                silver.brampton_permit_verification_workflow
            AS
            SELECT
                opportunity.opportunity_evidence_id,
                opportunity.permit_source_record_id,
                opportunity.permit_number,
                opportunity.application_at_utc,
                opportunity.event_type,
                opportunity.signal_strength,
                opportunity.address_raw,
                opportunity.evidence_status,
                opportunity.provisional_business_name,
                opportunity.provisional_business_source,
                opportunity.manual_resolution_required,

                count(task.verification_task_id)::INTEGER
                    AS required_task_count,

                count(task.verification_task_id) FILTER (
                    WHERE task.task_ready
                )::INTEGER AS ready_task_count,

                count(task.verification_task_id) FILTER (
                    WHERE task.task_status = 'completed'
                )::INTEGER AS completed_task_count,

                count(task.verification_task_id) FILTER (
                    WHERE task.verification_result = 'pass'
                )::INTEGER AS passed_task_count,

                count(task.verification_task_id) FILTER (
                    WHERE task.verification_result = 'fail'
                )::INTEGER AS failed_task_count,

                'not_started' AS workflow_status,
                false AS all_required_tasks_passed,
                false AS opportunity_ranked,
                false AS outreach_eligible,
                'shadow' AS operating_mode
            FROM
                silver.brampton_permit_opportunity_evidence
                    AS opportunity
            INNER JOIN
                silver.brampton_permit_verification_tasks
                    AS task
            ON
                opportunity.opportunity_evidence_id
                =
                task.opportunity_evidence_id
            GROUP BY
                opportunity.opportunity_evidence_id,
                opportunity.permit_source_record_id,
                opportunity.permit_number,
                opportunity.application_at_utc,
                opportunity.event_type,
                opportunity.signal_strength,
                opportunity.address_raw,
                opportunity.evidence_status,
                opportunity.provisional_business_name,
                opportunity.provisional_business_source,
                opportunity.manual_resolution_required
            """
        )

        connection.execute(
            """
            CREATE OR REPLACE VIEW
                silver.brampton_permit_verification_queue
            AS
            SELECT *
            FROM
                silver.brampton_permit_verification_tasks
            WHERE
                task_ready
                AND task_status = 'not_started'
            ORDER BY
                queue_priority,
                application_at_utc DESC,
                permit_number,
                task_order
            """
        )

        connection.execute(
            """
            CREATE OR REPLACE VIEW
                silver.brampton_permit_verification_summary
            AS
            SELECT
                gate_id,
                gate_category,
                signal_strength,
                task_status,
                verification_result,
                count(*) AS tasks,
                count(*) FILTER (
                    WHERE task_ready
                ) AS ready_tasks
            FROM
                silver.brampton_permit_verification_tasks
            GROUP BY
                gate_id,
                gate_category,
                signal_strength,
                task_status,
                verification_result
            """
        )

        workflow_count = _scalar(
            connection,
            """
            SELECT count(*)
            FROM
                silver.brampton_permit_verification_workflow
            """,
        )

        task_count = _scalar(
            connection,
            """
            SELECT count(*)
            FROM
                silver.brampton_permit_verification_tasks
            """,
        )

        evidence_resolution_task_count = _scalar(
            connection,
            """
            SELECT count(*)
            FROM
                silver.brampton_permit_verification_tasks
            WHERE
                gate_id = 'evidence_resolution'
            """,
        )

        ready_task_count = _scalar(
            connection,
            """
            SELECT count(*)
            FROM
                silver.brampton_permit_verification_queue
            """,
        )

        duplicate_task_ids = _scalar(
            connection,
            """
            SELECT
                count(*)
                - count(
                    DISTINCT verification_task_id
                )
            FROM
                silver.brampton_permit_verification_tasks
            """,
        )

        completed_task_count = _scalar(
            connection,
            """
            SELECT count(*)
            FROM
                silver.brampton_permit_verification_tasks
            WHERE
                task_status = 'completed'
                OR verification_result <> 'unknown'
                OR gate_cleared
            """,
        )

        safety_violation_count = _scalar(
            connection,
            """
            SELECT
                (
                    SELECT count(*)
                    FROM
                        silver.brampton_permit_verification_tasks
                    WHERE
                        automatic_clear_allowed
                        OR opportunity_ranked
                        OR outreach_eligible
                        OR operating_mode <> 'shadow'
                )
                +
                (
                    SELECT count(*)
                    FROM
                        silver.brampton_permit_verification_workflow
                    WHERE
                        all_required_tasks_passed
                        OR opportunity_ranked
                        OR outreach_eligible
                        OR operating_mode <> 'shadow'
                )
            """,
        )

        connection.execute("COMMIT")
        transaction_active = False

    except Exception:
        if transaction_active:
            connection.execute("ROLLBACK")

        raise

    finally:
        connection.close()

    expected_task_count = source_count * STANDARD_GATE_COUNT + manual_resolution_count

    if workflow_count != source_count:
        raise RuntimeError("Verification workflow count does not match opportunity evidence.")

    if task_count != expected_task_count:
        raise RuntimeError("Verification task count does not match the required gate plan.")

    if evidence_resolution_task_count != manual_resolution_count:
        raise RuntimeError(
            "Evidence-resolution task count does not match manual-resolution records."
        )

    if ready_task_count != source_count:
        raise RuntimeError("Each opportunity must begin with exactly one ready verification task.")

    if duplicate_task_ids != 0:
        raise RuntimeError("Verification plan contains duplicate task IDs.")

    if completed_task_count != 0:
        raise RuntimeError("Initial verification tasks were improperly completed or cleared.")

    if safety_violation_count != 0:
        raise RuntimeError("Verification plan violated safety policy.")

    report: dict[str, Any] = {
        "model_version": ("brampton-permit-verification-plan-v1"),
        "opportunity_count": source_count,
        "manual_resolution_opportunity_count": (manual_resolution_count),
        "standard_gate_count_per_opportunity": (STANDARD_GATE_COUNT),
        "verification_task_count": task_count,
        "evidence_resolution_task_count": (evidence_resolution_task_count),
        "initial_ready_task_count": ready_task_count,
        "workflow_count": workflow_count,
        "duplicate_task_id_count": (duplicate_task_ids),
        "initial_completed_task_count": (completed_task_count),
        "safety_violation_count": (safety_violation_count),
        "task_table": ("silver.brampton_permit_verification_tasks"),
        "workflow_table": ("silver.brampton_permit_verification_workflow"),
        "queue_view": ("silver.brampton_permit_verification_queue"),
        "summary_view": ("silver.brampton_permit_verification_summary"),
        "policy": {
            "queue_priority_is_opportunity_ranking": (False),
            "automatic_gate_clearance": False,
            "one_initial_ready_task_per_opportunity": (True),
            "all_tasks_blocking": True,
            "operating_mode": "shadow",
            "opportunity_ranked": False,
            "outreach_eligible": False,
        },
    }

    contract_path = (
        project_root / "docs" / "data_contracts" / "brampton_permit_verification_plan.json"
    )

    report["contract_path"] = str(contract_path.relative_to(project_root))

    write_json_atomic(
        contract_path,
        report,
    )

    return report
