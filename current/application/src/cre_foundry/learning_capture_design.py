from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import tempfile
from pathlib import Path
from typing import Any

EXPECTED_POLICY: dict[str, Any] = {
    "operating_mode": "shadow",
    "design_only": True,
    "append_only_outcomes_required": True,
    "point_in_time_required": True,
    "future_information_forbidden": True,
    "primary_outcome_requires_client_confirmation": True,
    "economic_parameters_require_client_confirmation": True,
    "source_schedule_activation_enabled": False,
    "automatic_acquisition_enabled": False,
    "historical_backfill_enabled": False,
    "persistent_outcome_database_enabled": False,
    "outcome_event_insertion_enabled": False,
    "label_materialization_enabled": False,
    "model_training_enabled": False,
    "backtest_execution_enabled": False,
    "production_ranking_enabled": False,
    "outreach_enabled": False,
}


OUTCOME_TABLES = (
    "pilot_recommendations",
    "pilot_actions",
    "pilot_outcome_events",
    "pilot_economic_events",
    "pilot_exclusions",
)


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


def _atomic_text(
    path: Path,
    content: str,
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
            stream.write(content)
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

    if not isinstance(raw, dict):
        raise RuntimeError(f"Expected JSON object: {path}")

    return {str(key): value for key, value in raw.items()}


def _count(
    connection: sqlite3.Connection,
    sql: str,
) -> int:
    row = connection.execute(sql).fetchone()

    if row is None:
        raise RuntimeError("Count query returned no row.")

    return int(row[0])


def _outcome_schema_sql() -> str:
    table_statements = [
        """
CREATE TABLE pilot_recommendations (
    recommendation_id TEXT PRIMARY KEY,
    decision_run_id TEXT NOT NULL,
    account_id TEXT NOT NULL,
    property_id TEXT,
    representative_id TEXT,
    generated_at TEXT NOT NULL,
    as_of_at TEXT NOT NULL,
    evidence_bundle_id TEXT NOT NULL,
    policy_version TEXT NOT NULL,
    assignment_group TEXT NOT NULL,
    assignment_probability REAL,
    excluded INTEGER NOT NULL CHECK (excluded IN (0, 1)),
    exclusion_reason TEXT,
    payload_json TEXT NOT NULL
)
""",
        """
CREATE TABLE pilot_actions (
    action_id TEXT PRIMARY KEY,
    recommendation_id TEXT NOT NULL,
    representative_id TEXT NOT NULL,
    action_type TEXT NOT NULL,
    assigned_at TEXT NOT NULL,
    started_at TEXT,
    completed_at TEXT,
    action_status TEXT NOT NULL,
    override_reason TEXT,
    evidence_reference TEXT,
    payload_json TEXT NOT NULL,
    FOREIGN KEY (
        recommendation_id
    ) REFERENCES pilot_recommendations (
        recommendation_id
    )
)
""",
        """
CREATE TABLE pilot_outcome_events (
    outcome_event_id TEXT PRIMARY KEY,
    recommendation_id TEXT NOT NULL,
    action_id TEXT,
    event_type TEXT NOT NULL,
    event_at TEXT NOT NULL,
    recorded_at TEXT NOT NULL,
    contact_established TEXT,
    decision_maker_reached TEXT,
    meaningful_cre_conversation TEXT,
    requirement_confirmed TEXT,
    previously_known TEXT,
    requirement_type TEXT,
    need_horizon TEXT,
    representation_status TEXT,
    evidence_reference TEXT,
    censored INTEGER NOT NULL CHECK (censored IN (0, 1)),
    censoring_reason TEXT,
    payload_json TEXT NOT NULL,
    FOREIGN KEY (
        recommendation_id
    ) REFERENCES pilot_recommendations (
        recommendation_id
    ),
    FOREIGN KEY (
        action_id
    ) REFERENCES pilot_actions (
        action_id
    )
)
""",
        """
CREATE TABLE pilot_economic_events (
    economic_event_id TEXT PRIMARY KEY,
    recommendation_id TEXT NOT NULL,
    event_type TEXT NOT NULL,
    event_at TEXT NOT NULL,
    amount_minor_units INTEGER,
    currency_code TEXT,
    representative_minutes INTEGER,
    travel_minutes INTEGER,
    contact_cost_minor_units INTEGER,
    data_cost_minor_units INTEGER,
    evidence_reference TEXT,
    payload_json TEXT NOT NULL,
    FOREIGN KEY (
        recommendation_id
    ) REFERENCES pilot_recommendations (
        recommendation_id
    )
)
""",
        """
CREATE TABLE pilot_exclusions (
    exclusion_event_id TEXT PRIMARY KEY,
    account_id TEXT NOT NULL,
    property_id TEXT,
    exclusion_type TEXT NOT NULL,
    effective_at TEXT NOT NULL,
    expires_at TEXT,
    evidence_reference TEXT NOT NULL,
    payload_json TEXT NOT NULL
)
""",
    ]

    trigger_statements = []

    for table_name in OUTCOME_TABLES:
        trigger_statements.extend(
            [
                f"""
CREATE TRIGGER {table_name}_no_update
BEFORE UPDATE ON {table_name}
BEGIN
    SELECT RAISE(
        ABORT,
        'append_only_update_forbidden'
    );
END
""",
                f"""
CREATE TRIGGER {table_name}_no_delete
BEFORE DELETE ON {table_name}
BEGIN
    SELECT RAISE(
        ABORT,
        'append_only_delete_forbidden'
    );
END
""",
            ]
        )

    statements = [
        *table_statements,
        *trigger_statements,
    ]

    return (
        "PRAGMA foreign_keys = ON;\n\n"
        + ";\n\n".join(statement.strip() for statement in statements)
        + ";\n"
    )


def _validate_ephemeral_outcomes(
    project_root: Path,
    schema_sql: str,
) -> dict[str, Any]:
    temporary_database_path: Path | None = None

    with tempfile.TemporaryDirectory(prefix="cre-foundry-learning-ledger-") as temporary_directory:
        database_path = Path(temporary_directory) / "pilot_outcomes.sqlite3"

        temporary_database_path = database_path

        try:
            database_path.resolve().relative_to(project_root.resolve())

        except ValueError:
            pass

        else:
            raise RuntimeError("Ephemeral database is inside project root.")

        connection = sqlite3.connect(database_path)

        try:
            connection.executescript(schema_sql)

            connection.execute(
                """
                INSERT INTO pilot_recommendations (
                    recommendation_id,
                    decision_run_id,
                    account_id,
                    generated_at,
                    as_of_at,
                    evidence_bundle_id,
                    policy_version,
                    assignment_group,
                    assignment_probability,
                    excluded,
                    payload_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "recommendation-test",
                    "run-test",
                    "account-test",
                    "2026-01-01T00:00:00+00:00",
                    "2026-01-01T00:00:00+00:00",
                    "evidence-test",
                    "policy-test",
                    "shadow-control",
                    0.5,
                    0,
                    "{}",
                ),
            )

            connection.execute(
                """
                INSERT INTO pilot_actions (
                    action_id,
                    recommendation_id,
                    representative_id,
                    action_type,
                    assigned_at,
                    action_status,
                    payload_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "action-test",
                    "recommendation-test",
                    "rep-test",
                    "review",
                    "2026-01-01T00:00:00+00:00",
                    "assigned",
                    "{}",
                ),
            )

            connection.execute(
                """
                INSERT INTO pilot_outcome_events (
                    outcome_event_id,
                    recommendation_id,
                    action_id,
                    event_type,
                    event_at,
                    recorded_at,
                    censored,
                    censoring_reason,
                    payload_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "outcome-test",
                    "recommendation-test",
                    "action-test",
                    "not_reached",
                    "2026-01-01T00:00:00+00:00",
                    "2026-01-01T00:00:00+00:00",
                    1,
                    "follow_up_incomplete",
                    "{}",
                ),
            )

            connection.commit()

            update_blocked = False
            delete_blocked = False

            try:
                connection.execute(
                    """
                    UPDATE pilot_recommendations
                    SET assignment_group = 'changed'
                    WHERE recommendation_id = 'recommendation-test'
                    """
                )

            except sqlite3.DatabaseError:
                update_blocked = True
                connection.rollback()

            try:
                connection.execute(
                    """
                    DELETE FROM pilot_recommendations
                    WHERE recommendation_id = 'recommendation-test'
                    """
                )

            except sqlite3.DatabaseError:
                delete_blocked = True
                connection.rollback()

            table_count = _count(
                connection,
                """
                SELECT count(*)
                FROM sqlite_master
                WHERE type = 'table'
                  AND name NOT LIKE 'sqlite_%'
                """,
            )

            trigger_count = _count(
                connection,
                """
                SELECT count(*)
                FROM sqlite_master
                WHERE type = 'trigger'
                """,
            )

            recommendation_count = _count(
                connection,
                """
                SELECT count(*)
                FROM pilot_recommendations
                """,
            )

            action_count = _count(
                connection,
                """
                SELECT count(*)
                FROM pilot_actions
                """,
            )

            outcome_count = _count(
                connection,
                """
                SELECT count(*)
                FROM pilot_outcome_events
                """,
            )

            schema_rows = connection.execute(
                """
                SELECT
                    type,
                    name,
                    tbl_name,
                    sql
                FROM sqlite_master
                WHERE type IN ('table', 'trigger')
                  AND name NOT LIKE 'sqlite_%'
                ORDER BY
                    type,
                    name
                """
            ).fetchall()

            schema_fingerprint = hashlib.sha256(
                json.dumps(
                    [
                        [None if value is None else str(value) for value in row]
                        for row in schema_rows
                    ],
                    sort_keys=True,
                    separators=(",", ":"),
                ).encode("utf-8")
            ).hexdigest()

        finally:
            connection.close()

    if temporary_database_path is None:
        raise RuntimeError("Ephemeral database was not created.")

    return {
        "table_count": table_count,
        "trigger_count": trigger_count,
        "sample_recommendation_count": (recommendation_count),
        "sample_action_count": action_count,
        "sample_outcome_count": outcome_count,
        "append_only_update_blocked": (update_blocked),
        "append_only_delete_blocked": (delete_blocked),
        "schema_fingerprint": (schema_fingerprint),
        "database_outside_project": True,
        "ephemeral_database_deleted": (not temporary_database_path.exists()),
    }


def build_learning_capture_design(
    project_root: Path,
    *,
    write_contracts: bool = True,
) -> dict[str, Any]:
    config = _load_object(project_root / "config" / "learning_capture_design.json")

    raw_policy = config.get("policy")
    raw_source_plans = config.get("source_plans")
    raw_event_types = config.get("candidate_event_types")
    raw_client_inputs = config.get("required_client_inputs")

    if not isinstance(raw_policy, dict):
        raise RuntimeError("Learning-capture policy must be an object.")

    policy = {str(key): value for key, value in raw_policy.items()}

    if policy != EXPECTED_POLICY:
        raise RuntimeError("Learning-capture policy mismatch.")

    if not isinstance(raw_source_plans, list):
        raise RuntimeError("Source plans must be a list.")

    if not isinstance(raw_event_types, list):
        raise RuntimeError("Candidate event types must be a list.")

    if not isinstance(raw_client_inputs, list):
        raise RuntimeError("Required client inputs must be a list.")

    parser_template = _load_object(
        project_root / "docs" / "data_contracts" / "source_parser_contract_approval_template.json"
    )

    raw_parser_approvals = parser_template.get("approvals")

    if not isinstance(
        raw_parser_approvals,
        list,
    ):
        raise RuntimeError("Parser approval template is malformed.")

    parser_sources = {
        str(approval["source_id"])
        for approval in raw_parser_approvals
        if (
            isinstance(approval, dict)
            and isinstance(
                approval.get("source_id"),
                str,
            )
        )
    }

    source_rows: list[dict[str, Any]] = []
    change_rows: list[dict[str, Any]] = []
    coverage_rows: list[dict[str, Any]] = []

    for raw_plan in raw_source_plans:
        if not isinstance(raw_plan, dict):
            raise RuntimeError("Source plan must be an object.")

        plan = {str(key): value for key, value in raw_plan.items()}

        source_id = str(plan["source_id"])

        parser_evidence_available = source_id in parser_sources

        source_rows.append(
            {
                **plan,
                "parser_evidence_available": (parser_evidence_available),
                "parser_contract_approved": False,
                "schema_contract_approved": False,
                "record_key_approved": False,
                "temporal_fields_approved": False,
                "capture_policy_approved": False,
                "schedule_activation_approved": False,
                "automatic_acquisition_approved": False,
                "historical_backfill_approved": False,
                "collection_ready": False,
                "collection_execution_count": 0,
                "snapshot_registration_count": 0,
            }
        )

        change_rows.append(
            {
                "source_id": source_id,
                "candidate_record_keys": plan["candidate_record_keys"],
                "change_types": plan["change_types"],
                "row_hash_required": True,
                "snapshot_hash_required": True,
                "added_record_detection": True,
                "removed_record_detection": True,
                "changed_record_detection": True,
                "unchanged_record_detection": True,
                "field_level_diff_required": True,
                "source_observed_at_required": True,
                "publication_lag_required": True,
                "future_information_forbidden": True,
                "change_contract_approved": False,
                "change_detection_execution_count": 0,
            }
        )

        coverage_rows.append(
            {
                "source_id": source_id,
                "candidate_history_months": plan["candidate_history_months"],
                "candidate_minimum_snapshots": plan["candidate_minimum_snapshots"],
                "registered_snapshot_count": 0,
                "approved_history_months": None,
                "approved_minimum_snapshots": None,
                "coverage_satisfied": False,
                "point_in_time_dataset_eligible": False,
                "backtest_eligible": False,
                "model_training_eligible": False,
            }
        )

    source_rows.sort(key=lambda row: str(row["source_id"]))
    change_rows.sort(key=lambda row: str(row["source_id"]))
    coverage_rows.sort(key=lambda row: str(row["source_id"]))

    event_types = [str(value) for value in raw_event_types]

    if len(event_types) != len(set(event_types)):
        raise RuntimeError("Duplicate event types exist.")

    client_inputs = [str(value) for value in raw_client_inputs]

    schema_sql = _outcome_schema_sql()

    outcome_validation = _validate_ephemeral_outcomes(
        project_root,
        schema_sql,
    )

    longitudinal_report: dict[str, Any] = {
        "model_version": ("cre-foundry-longitudinal-collection-plan-v1"),
        "source_count": len(source_rows),
        "parser_evidence_source_count": sum(
            bool(row["parser_evidence_available"]) for row in source_rows
        ),
        "collection_ready_source_count": 0,
        "source_plans": source_rows,
        "schedule_activation_count": 0,
        "automatic_acquisition_execution_count": 0,
        "historical_backfill_execution_count": 0,
        "snapshot_registration_execution_count": 0,
        "point_in_time_dataset_execution_count": 0,
        "model_training_execution_count": 0,
        "production_ranking_execution_count": 0,
        "outreach_execution_count": 0,
    }

    change_report: dict[str, Any] = {
        "model_version": ("cre-foundry-source-change-contracts-v1"),
        "contract_count": len(change_rows),
        "approved_contract_count": 0,
        "contracts": change_rows,
        "change_detection_execution_count": 0,
        "database_write_count": 0,
    }

    coverage_report: dict[str, Any] = {
        "model_version": ("cre-foundry-historical-coverage-v1"),
        "requirement_count": len(coverage_rows),
        "satisfied_requirement_count": 0,
        "requirements": coverage_rows,
        "point_in_time_eligible_source_count": 0,
        "backtest_eligible_source_count": 0,
        "model_training_eligible_source_count": 0,
    }

    outcome_report: dict[str, Any] = {
        "model_version": ("cre-foundry-outcome-collection-contract-v1"),
        "primary_pilot_outcome": None,
        "primary_pilot_outcome_confirmed": False,
        "candidate_event_type_count": len(event_types),
        "candidate_event_types": event_types,
        **outcome_validation,
        "negative_label_rule": (
            "A true negative requires the correct "
            "decision-maker to be reached and the "
            "label observation window to be complete."
        ),
        "censoring_rule": (
            "Not reached, incomplete follow-up, "
            "future requirement, protected account, "
            "already represented and insufficient "
            "observation time are not ordinary negatives."
        ),
        "persistent_database_created": False,
        "persistent_recommendation_count": 0,
        "persistent_action_count": 0,
        "persistent_outcome_event_count": 0,
        "persistent_economic_event_count": 0,
        "persistent_exclusion_event_count": 0,
        "label_materialization_execution_count": 0,
        "model_training_execution_count": 0,
        "production_ranking_execution_count": 0,
        "outreach_execution_count": 0,
    }

    experiment_report: dict[str, Any] = {
        "model_version": ("cre-foundry-pilot-experiment-design-v1"),
        "primary_outcome": None,
        "primary_outcome_confirmed": False,
        "phases": [
            {
                "phase": "shadow_review",
                "assignment_method": ("parallel_observation"),
                "outreach_permitted": False,
                "execution_approved": False,
            },
            {
                "phase": "controlled_pilot",
                "assignment_method": ("randomized_or_matched_holdout"),
                "outreach_permitted": False,
                "execution_approved": False,
            },
        ],
        "required_metrics": [
            "precision_at_daily_review_limit",
            "lift_over_random",
            "lift_over_business_as_usual",
            "decision_maker_reach_rate",
            "confirmed_requirement_rate",
            "meeting_rate",
            "active_opportunity_rate",
            "mandate_rate",
            "transaction_rate",
            "incremental_commission",
            "representative_minutes_per_confirmed_requirement",
            "travel_minutes_per_confirmed_requirement",
            "false_positive_review_burden",
            "incremental_net_value",
            "return_on_investment",
        ],
        "required_policy_logging": [
            "decision_run_id",
            "policy_version",
            "assignment_group",
            "assignment_probability",
            "as_of_at",
            "evidence_bundle_id",
            "eligible_action_set",
            "exclusion_state",
        ],
        "future_off_policy_requirements": [
            "behavior_policy_version",
            "target_policy_version",
            "propensity_overlap",
            "effective_sample_size",
            "inverse_propensity_estimate",
            "doubly_robust_estimate",
            "confidence_interval",
            "nonstationarity_review",
        ],
        "shadow_pilot_execution_count": 0,
        "controlled_pilot_execution_count": 0,
        "incremental_roi_proven": False,
        "production_ranking_enabled": False,
        "outreach_enabled": False,
    }

    client_report: dict[str, Any] = {
        "model_version": ("cre-foundry-client-input-capture-v1"),
        "section_count": len(client_inputs),
        "confirmed_section_count": 0,
        "sections": [
            {
                "input_id": input_id,
                "authoritative_value": None,
                "confirmed": False,
                "confirmed_by": None,
                "confirmed_at": None,
                "evidence_reference": None,
            }
            for input_id in client_inputs
        ],
        "invention_permitted": False,
        "schedule_activation_permitted": False,
        "pilot_execution_permitted": False,
        "model_training_permitted": False,
        "production_ranking_permitted": False,
        "outreach_permitted": False,
    }

    summary: dict[str, Any] = {
        "model_version": ("cre-foundry-learning-capture-design-v1"),
        "source_plan_count": len(source_rows),
        "change_contract_count": len(change_rows),
        "coverage_requirement_count": len(coverage_rows),
        "outcome_table_count": outcome_report["table_count"],
        "append_only_trigger_count": (outcome_report["trigger_count"]),
        "candidate_event_type_count": len(event_types),
        "client_input_section_count": len(client_inputs),
        "collection_ready_source_count": 0,
        "persistent_outcome_database_created": False,
        "point_in_time_dataset_ready": False,
        "model_training_ready": False,
        "historical_backtest_ready": False,
        "shadow_pilot_ready": False,
        "controlled_pilot_ready": False,
        "incremental_roi_proven": False,
        "codex_final_handoff_ready": False,
        "database_write_count": 0,
        "snapshot_registration_count": 0,
        "outcome_event_insertion_count": 0,
        "label_materialization_count": 0,
        "model_training_execution_count": 0,
        "backtest_execution_count": 0,
        "pilot_execution_count": 0,
        "production_ranking_execution_count": 0,
        "outreach_execution_count": 0,
        "policy": EXPECTED_POLICY,
    }

    if write_contracts:
        root = project_root / "docs" / "data_contracts"

        _atomic_json(
            root / "longitudinal_collection_plan.json",
            longitudinal_report,
        )
        _atomic_json(
            root / "source_change_detection_contracts.json",
            change_report,
        )
        _atomic_json(
            root / "historical_coverage_requirements.json",
            coverage_report,
        )
        _atomic_text(
            root / "outcome_collection_schema.sql",
            schema_sql,
        )
        _atomic_json(
            root / "outcome_collection_contract.json",
            outcome_report,
        )
        _atomic_json(
            root / "pilot_experiment_design.json",
            experiment_report,
        )
        _atomic_json(
            root / "client_input_capture_template.json",
            client_report,
        )
        _atomic_json(
            root / "learning_capture_design_summary.json",
            summary,
        )
        _atomic_text(
            root / "learning_capture_design.md",
            "\n".join(
                [
                    "# Learning Capture Design",
                    "",
                    (
                        "This package defines longitudinal "
                        "collection, change detection, append-only "
                        "outcomes and pilot measurement."
                    ),
                    "",
                    (f"- Source plans: `{summary['source_plan_count']}`"),
                    (f"- Change contracts: `{summary['change_contract_count']}`"),
                    (f"- Outcome tables: `{summary['outcome_table_count']}`"),
                    (f"- Append-only triggers: `{summary['append_only_trigger_count']}`"),
                    (f"- Candidate event types: `{summary['candidate_event_type_count']}`"),
                    "",
                    "- Collection-ready sources: `0`",
                    "- Persistent outcome database: `false`",
                    "- Model training ready: `false`",
                    "- ROI proven: `false`",
                    "- Final Codex handoff ready: `false`",
                    "",
                ]
            ),
        )

    return {
        "summary": summary,
        "longitudinal": (longitudinal_report),
        "changes": change_report,
        "coverage": coverage_report,
        "outcomes": outcome_report,
        "experiment": experiment_report,
        "client_inputs": client_report,
    }
