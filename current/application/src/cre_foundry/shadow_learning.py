from __future__ import annotations

import hashlib
import json
import os
import re
import sqlite3
import tempfile
from collections import Counter
from pathlib import Path
from typing import Any

EXPECTED_POLICY: dict[str, Any] = {
    "operating_mode": "shadow",
    "outcome_event_recording_enabled": False,
    "feature_snapshot_registration_enabled": False,
    "evaluation_run_execution_enabled": False,
    "model_training_enabled": False,
    "automatic_conclusions": False,
    "opportunity_ranked": False,
    "outreach_eligible": False,
}

EXPECTED_TABLES = {
    "outcome_events",
    "feature_snapshots",
    "evaluation_runs",
}

EXPECTED_TRIGGERS = {
    "outcome_events_insert_disabled",
    "outcome_events_no_update",
    "outcome_events_no_delete",
    "feature_snapshots_insert_disabled",
    "feature_snapshots_no_update",
    "feature_snapshots_no_delete",
    "evaluation_runs_insert_disabled",
    "evaluation_runs_no_update",
    "evaluation_runs_no_delete",
}

OUTCOME_LEAKAGE_TOKENS = {
    "closed",
    "closing",
    "converted",
    "conversion",
    "deal",
    "label",
    "mandate",
    "outcome",
    "requirement_confirmed",
    "result",
    "success",
    "transaction_closed",
    "won",
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


def _require_nonnegative_int(
    value: object,
    field_name: str,
) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise RuntimeError(f"{field_name} must be a nonnegative integer.")

    return value


def _load_config(
    project_root: Path,
) -> dict[str, Any]:
    config = _load_object(project_root / "config" / "shadow_learning.json")

    raw_policy = config.get("policy")

    if not isinstance(
        raw_policy,
        dict,
    ):
        raise RuntimeError("Shadow-learning policy must be an object.")

    policy: dict[str, Any] = {str(key): value for key, value in raw_policy.items()}

    if policy != EXPECTED_POLICY:
        raise RuntimeError("Shadow-learning safety policy mismatch.")

    if not isinstance(
        config.get("label_protocol"),
        dict,
    ):
        raise RuntimeError("Label protocol must be an object.")

    if not isinstance(
        config.get("evaluation_protocol"),
        dict,
    ):
        raise RuntimeError("Evaluation protocol must be an object.")

    return config


def _database_path(
    project_root: Path,
) -> Path:
    return project_root / "data" / "control" / "shadow_learning.sqlite3"


def _schema_sql() -> str:
    return """
    CREATE TABLE IF NOT EXISTS outcome_events (
        event_id TEXT PRIMARY KEY,
        opportunity_id TEXT NOT NULL,
        event_type TEXT NOT NULL,
        occurred_at TEXT NOT NULL,
        observed_at TEXT NOT NULL,
        evidence_reference TEXT NOT NULL,
        actor_reference TEXT NOT NULL,
        previous_event_hash TEXT,
        event_hash TEXT NOT NULL UNIQUE,
        created_at TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS feature_snapshots (
        snapshot_id TEXT PRIMARY KEY,
        opportunity_id TEXT NOT NULL,
        as_of_time TEXT NOT NULL,
        artifact_path TEXT NOT NULL,
        artifact_sha256 TEXT NOT NULL,
        schema_fingerprint TEXT NOT NULL,
        source_manifest_sha256 TEXT NOT NULL,
        previous_snapshot_hash TEXT,
        snapshot_hash TEXT NOT NULL UNIQUE,
        created_at TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS evaluation_runs (
        evaluation_run_id TEXT PRIMARY KEY,
        protocol_version TEXT NOT NULL,
        train_start TEXT NOT NULL,
        train_end TEXT NOT NULL,
        validation_start TEXT NOT NULL,
        validation_end TEXT NOT NULL,
        prediction_horizon_days INTEGER NOT NULL,
        embargo_days INTEGER NOT NULL,
        feature_manifest_path TEXT NOT NULL,
        feature_manifest_sha256 TEXT NOT NULL,
        outcome_manifest_path TEXT NOT NULL,
        outcome_manifest_sha256 TEXT NOT NULL,
        result_artifact_path TEXT NOT NULL,
        result_artifact_sha256 TEXT NOT NULL,
        previous_run_hash TEXT,
        run_hash TEXT NOT NULL UNIQUE,
        created_at TEXT NOT NULL
    );

    CREATE TRIGGER IF NOT EXISTS outcome_events_insert_disabled
    BEFORE INSERT ON outcome_events
    BEGIN
        SELECT RAISE(
            ABORT,
            'outcome event recording is disabled'
        );
    END;

    CREATE TRIGGER IF NOT EXISTS outcome_events_no_update
    BEFORE UPDATE ON outcome_events
    BEGIN
        SELECT RAISE(
            ABORT,
            'outcome_events is append-only'
        );
    END;

    CREATE TRIGGER IF NOT EXISTS outcome_events_no_delete
    BEFORE DELETE ON outcome_events
    BEGIN
        SELECT RAISE(
            ABORT,
            'outcome_events is append-only'
        );
    END;

    CREATE TRIGGER IF NOT EXISTS feature_snapshots_insert_disabled
    BEFORE INSERT ON feature_snapshots
    BEGIN
        SELECT RAISE(
            ABORT,
            'feature snapshot registration is disabled'
        );
    END;

    CREATE TRIGGER IF NOT EXISTS feature_snapshots_no_update
    BEFORE UPDATE ON feature_snapshots
    BEGIN
        SELECT RAISE(
            ABORT,
            'feature_snapshots is append-only'
        );
    END;

    CREATE TRIGGER IF NOT EXISTS feature_snapshots_no_delete
    BEFORE DELETE ON feature_snapshots
    BEGIN
        SELECT RAISE(
            ABORT,
            'feature_snapshots is append-only'
        );
    END;

    CREATE TRIGGER IF NOT EXISTS evaluation_runs_insert_disabled
    BEFORE INSERT ON evaluation_runs
    BEGIN
        SELECT RAISE(
            ABORT,
            'evaluation run execution is disabled'
        );
    END;

    CREATE TRIGGER IF NOT EXISTS evaluation_runs_no_update
    BEFORE UPDATE ON evaluation_runs
    BEGIN
        SELECT RAISE(
            ABORT,
            'evaluation_runs is append-only'
        );
    END;

    CREATE TRIGGER IF NOT EXISTS evaluation_runs_no_delete
    BEFORE DELETE ON evaluation_runs
    BEGIN
        SELECT RAISE(
            ABORT,
            'evaluation_runs is append-only'
        );
    END;
    """


def _schema_fingerprint(
    connection: sqlite3.Connection,
) -> str:
    rows = connection.execute(
        """
        SELECT
            type,
            name,
            tbl_name,
            sql
        FROM sqlite_master
        WHERE
            type IN (
                'table',
                'trigger'
            )
            AND name NOT LIKE
                'sqlite_%'
        ORDER BY
            type,
            name
        """
    ).fetchall()

    payload = [[str(value) if value is not None else None for value in row] for row in rows]

    encoded = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")

    return hashlib.sha256(encoded).hexdigest()


def initialize_shadow_learning(
    project_root: Path,
    *,
    write_contract: bool = True,
) -> dict[str, Any]:
    config = _load_config(project_root)

    database_path = _database_path(project_root)

    database_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    connection = sqlite3.connect(database_path)

    try:
        connection.executescript(_schema_sql())
        connection.commit()

        schema_fingerprint = _schema_fingerprint(connection)

    finally:
        connection.close()

    audit = audit_shadow_learning(
        project_root,
        write_contract=False,
    )

    protocol: dict[str, Any] = {
        "model_version": ("cre-foundry-shadow-learning-protocol-v1"),
        "database_path": str(database_path.relative_to(project_root)),
        "schema_fingerprint": (schema_fingerprint),
        "label_protocol": config["label_protocol"],
        "evaluation_protocol": config["evaluation_protocol"],
        "table_count": audit["table_count"],
        "trigger_count": audit["trigger_count"],
        "infrastructure_ready": audit["infrastructure_ready"],
        "policy": EXPECTED_POLICY,
        "outcome_event_recording_enabled": False,
        "feature_snapshot_registration_enabled": False,
        "evaluation_run_execution_enabled": False,
        "model_training_enabled": False,
        "opportunity_ranked": False,
        "outreach_eligible": False,
    }

    if write_contract:
        contract_path = project_root / "docs" / "data_contracts" / "shadow_learning_protocol.json"

        protocol["contract_path"] = str(contract_path.relative_to(project_root))

        _atomic_json(
            contract_path,
            protocol,
        )

    return protocol


def audit_shadow_learning(
    project_root: Path,
    *,
    write_contract: bool = True,
) -> dict[str, Any]:
    _load_config(project_root)

    database_path = _database_path(project_root)

    if not database_path.is_file():
        raise RuntimeError("Shadow-learning database has not been initialized.")

    connection = sqlite3.connect(
        ("file:" + str(database_path) + "?mode=ro"),
        uri=True,
    )

    try:
        table_rows = connection.execute(
            """
            SELECT name
            FROM sqlite_master
            WHERE
                type = 'table'
                AND name NOT LIKE
                    'sqlite_%'
            ORDER BY name
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

        tables = {str(row[0]) for row in table_rows}

        triggers = {str(row[0]) for row in trigger_rows}

        counts: dict[str, int] = {}

        for table_name in sorted(EXPECTED_TABLES):
            if table_name not in tables:
                continue

            row = connection.execute(
                f"""
                SELECT count(*)
                FROM "{table_name}"
                """
            ).fetchone()

            if row is None:
                raise RuntimeError(f"No count returned for {table_name}.")

            counts[table_name] = int(row[0])

        schema_fingerprint = _schema_fingerprint(connection)

    finally:
        connection.close()

    missing_tables = sorted(EXPECTED_TABLES - tables)

    missing_triggers = sorted(EXPECTED_TRIGGERS - triggers)

    report: dict[str, Any] = {
        "model_version": ("cre-foundry-shadow-learning-audit-v1"),
        "database_path": str(database_path.relative_to(project_root)),
        "schema_fingerprint": (schema_fingerprint),
        "table_count": len(EXPECTED_TABLES & tables),
        "trigger_count": len(EXPECTED_TRIGGERS & triggers),
        "tables": sorted(EXPECTED_TABLES & tables),
        "triggers": sorted(EXPECTED_TRIGGERS & triggers),
        "missing_tables": (missing_tables),
        "missing_triggers": (missing_triggers),
        "record_counts": counts,
        "outcome_event_count": int(
            counts.get(
                "outcome_events",
                0,
            )
        ),
        "feature_snapshot_count": int(
            counts.get(
                "feature_snapshots",
                0,
            )
        ),
        "evaluation_run_count": int(
            counts.get(
                "evaluation_runs",
                0,
            )
        ),
        "infrastructure_ready": (not missing_tables and not missing_triggers),
        "policy": EXPECTED_POLICY,
        "outcome_event_recording_enabled": False,
        "feature_snapshot_registration_enabled": False,
        "evaluation_run_execution_enabled": False,
        "model_training_enabled": False,
        "opportunity_ranked": False,
        "outreach_eligible": False,
    }

    if write_contract:
        contract_path = project_root / "docs" / "data_contracts" / "shadow_learning_audit.json"

        report["contract_path"] = str(contract_path.relative_to(project_root))

        _atomic_json(
            contract_path,
            report,
        )

    return report


def _primitive_tokens(
    column_name: str,
) -> set[str]:
    normalized = re.sub(
        r"[^a-z0-9]+",
        "_",
        column_name.lower(),
    )

    return {token for token in normalized.split("_") if token}


def build_shadow_feature_review(
    project_root: Path,
    *,
    write_contract: bool = True,
) -> dict[str, Any]:
    _load_config(project_root)

    inventory = _load_object(project_root / "docs" / "data_contracts" / "primitive_inventory.json")

    quality = _load_object(
        project_root / "docs" / "data_contracts" / "primitive_quality_profile.json"
    )

    raw_primitives = inventory.get("primitives")

    raw_relation_profiles = quality.get("relation_profiles")

    if not isinstance(
        raw_primitives,
        list,
    ):
        raise RuntimeError("Primitive inventory has no primitive list.")

    inventory_primitive_count = _require_nonnegative_int(
        inventory.get("primitive_count"),
        "primitive inventory primitive_count",
    )

    if not isinstance(
        raw_relation_profiles,
        list,
    ):
        raise RuntimeError("Primitive quality has no relation profiles.")

    quality_by_primitive: dict[
        str,
        dict[str, Any],
    ] = {}

    for raw_relation_profile in raw_relation_profiles:
        if not isinstance(
            raw_relation_profile,
            dict,
        ):
            raise RuntimeError("Relation profile must be an object.")

        raw_column_profiles = raw_relation_profile.get("column_profiles")

        if not isinstance(
            raw_column_profiles,
            list,
        ):
            raise RuntimeError("Column profiles must be a list.")

        for raw_column_profile in raw_column_profiles:
            if not isinstance(
                raw_column_profile,
                dict,
            ):
                raise RuntimeError("Column profile must be an object.")

            profile: dict[str, Any] = {str(key): value for key, value in raw_column_profile.items()}

            primitive_id = profile.get("primitive_id")

            if (
                not isinstance(
                    primitive_id,
                    str,
                )
                or not primitive_id
            ):
                raise RuntimeError("Column profile lacks a primitive ID.")

            quality_by_primitive[primitive_id] = profile

    entries: list[dict[str, Any]] = []

    role_counts: Counter[str] = Counter()

    missing_quality_profile_count = 0

    for raw_primitive in raw_primitives:
        if not isinstance(
            raw_primitive,
            dict,
        ):
            raise RuntimeError("Primitive must be an object.")

        primitive: dict[str, Any] = {str(key): value for key, value in raw_primitive.items()}

        primitive_id = primitive.get("primitive_id")

        column_name = primitive.get("column")

        if (
            not isinstance(
                primitive_id,
                str,
            )
            or not primitive_id
        ):
            raise RuntimeError("Primitive lacks a valid ID.")

        if not isinstance(
            column_name,
            str,
        ):
            raise RuntimeError("Primitive column must be a string.")

        raw_classification = primitive.get("classification")

        if not isinstance(
            raw_classification,
            dict,
        ):
            raise RuntimeError("Primitive classification must be an object.")

        classification: dict[str, Any] = {
            str(key): value for key, value in raw_classification.items()
        }

        quality_profile = quality_by_primitive.get(primitive_id)

        reasons: list[str] = []

        if quality_profile is None:
            missing_quality_profile_count += 1
            role = "blocked_missing_quality_profile"
            reasons.append("quality_profile_missing")

        else:
            null_ratio_value = quality_profile.get("null_ratio")

            if null_ratio_value is not None and (
                isinstance(
                    null_ratio_value,
                    bool,
                )
                or not isinstance(
                    null_ratio_value,
                    int | float,
                )
            ):
                raise RuntimeError("Primitive null ratio must be numeric or null.")

            null_ratio = (
                float(null_ratio_value)
                if isinstance(
                    null_ratio_value,
                    int | float,
                )
                and not isinstance(
                    null_ratio_value,
                    bool,
                )
                else None
            )

            tokens = _primitive_tokens(column_name)

            normalized_name = column_name.lower()

            safety_control = bool(classification.get("safety_control"))

            identity_candidate = bool(classification.get("identity_candidate"))

            temporal_candidate = bool(classification.get("temporal_candidate"))

            lineage_candidate = bool(classification.get("lineage_candidate"))

            leakage_detected = bool(tokens & OUTCOME_LEAKAGE_TOKENS) or any(
                phrase in normalized_name
                for phrase in (
                    "requirement_confirmed",
                    "transaction_closed",
                    "mandate_signed",
                    "outreach_eligible",
                    "opportunity_ranked",
                )
            )

            if safety_control:
                role = "blocked_safety_control"
                reasons.append("governed_safety_control")

            elif leakage_detected:
                role = "blocked_potential_outcome_leakage"
                reasons.append("potential_target_or_post_outcome_leakage")

            elif identity_candidate:
                role = "join_key_only"
                reasons.append("direct_identity_not_predictor")

            elif temporal_candidate:
                role = "point_in_time_metadata"
                reasons.append("temporal_cutoff_metadata")

            elif lineage_candidate:
                role = "lineage_metadata"
                reasons.append("lineage_not_predictor")

            elif null_ratio is not None and null_ratio >= 1.0:
                role = "blocked_no_observed_values"
                reasons.append("all_values_missing")

            else:
                role = "review_required"
                reasons.append("requires_feature_definition_and_leakage_review")

        role_counts[role] += 1

        entries.append(
            {
                "primitive_id": primitive_id,
                "engine": primitive.get("engine"),
                "schema": primitive.get("schema"),
                "relation": primitive.get("relation"),
                "column": column_name,
                "data_type": primitive.get("data_type"),
                "feature_role": role,
                "reasons": reasons,
                "approval_status": "unapproved",
                "model_feature_enabled": False,
                "point_in_time_validation_complete": False,
                "leakage_review_complete": False,
                "business_definition_approved": False,
            }
        )

    entries.sort(key=lambda entry: str(entry["primitive_id"]))

    report: dict[str, Any] = {
        "model_version": ("cre-foundry-shadow-feature-review-v1"),
        "primitive_count": len(entries),
        "inventory_primitive_count": inventory_primitive_count,
        "missing_quality_profile_count": (missing_quality_profile_count),
        "feature_role_counts": dict(sorted(role_counts.items())),
        "approved_feature_count": 0,
        "enabled_feature_count": 0,
        "entries": entries,
        "review_ready": (
            len(entries) == inventory_primitive_count and missing_quality_profile_count == 0
        ),
        "model_training_enabled": False,
        "production_ranking_enabled": False,
        "outreach_enabled": False,
        "policy": EXPECTED_POLICY,
    }

    if write_contract:
        contract_path = project_root / "docs" / "data_contracts" / "shadow_feature_review.json"

        report["contract_path"] = str(contract_path.relative_to(project_root))

        _atomic_json(
            contract_path,
            report,
        )

    return report


def plan_shadow_evaluation(
    project_root: Path,
    *,
    write_contract: bool = True,
) -> dict[str, Any]:
    config = _load_config(project_root)

    audit = audit_shadow_learning(
        project_root,
        write_contract=False,
    )

    feature_review = build_shadow_feature_review(
        project_root,
        write_contract=False,
    )

    readiness = _load_object(
        project_root / "docs" / "data_contracts" / "pilot_readiness_dossier.json"
    )

    raw_label_protocol = config.get("label_protocol")

    raw_evaluation_protocol = config.get("evaluation_protocol")

    if not isinstance(
        raw_label_protocol,
        dict,
    ):
        raise RuntimeError("Label protocol is malformed.")

    if not isinstance(
        raw_evaluation_protocol,
        dict,
    ):
        raise RuntimeError("Evaluation protocol is malformed.")

    label_protocol: dict[str, object] = {
        str(key): value for key, value in raw_label_protocol.items()
    }

    evaluation_protocol: dict[
        str,
        object,
    ] = {str(key): value for key, value in raw_evaluation_protocol.items()}

    blockers: list[str] = []

    if label_protocol.get("approval_status") != "approved":
        blockers.append("label_protocol_not_approved")

    if label_protocol.get("approved_success_event") is None:
        blockers.append("approved_success_event_missing")

    if label_protocol.get("active_prediction_horizon_days") is None:
        blockers.append("prediction_horizon_missing")

    if evaluation_protocol.get("approved_embargo_days") is None:
        blockers.append("embargo_period_missing")

    if evaluation_protocol.get("minimum_positive_events") is None:
        blockers.append("minimum_positive_events_missing")

    if evaluation_protocol.get("minimum_negative_events") is None:
        blockers.append("minimum_negative_events_missing")

    missing_client_value = readiness.get("missing_client_input_count")

    if (
        isinstance(
            missing_client_value,
            bool,
        )
        or not isinstance(
            missing_client_value,
            int,
        )
        or missing_client_value < 0
    ):
        raise RuntimeError("Pilot readiness has an invalid missing-client-input count.")

    if missing_client_value > 0:
        blockers.append("authoritative_client_inputs_incomplete")

    if audit["outcome_event_count"] == 0:
        blockers.append("no_outcome_events")

    if audit["feature_snapshot_count"] == 0:
        blockers.append("no_point_in_time_feature_snapshots")

    if feature_review["approved_feature_count"] == 0:
        blockers.append("no_approved_model_features")

    report: dict[str, Any] = {
        "model_version": ("cre-foundry-shadow-evaluation-plan-v1"),
        "split_strategy": (evaluation_protocol.get("split_strategy")),
        "point_in_time_features_required": bool(
            evaluation_protocol.get("point_in_time_features_required")
        ),
        "embargo_required": bool(evaluation_protocol.get("embargo_required")),
        "blocker_count": len(blockers),
        "blockers": blockers,
        "missing_client_input_count": (missing_client_value),
        "outcome_event_count": audit["outcome_event_count"],
        "feature_snapshot_count": audit["feature_snapshot_count"],
        "evaluation_run_count": audit["evaluation_run_count"],
        "reviewed_primitive_count": (feature_review["primitive_count"]),
        "approved_feature_count": (feature_review["approved_feature_count"]),
        "evaluation_ready": not blockers,
        "execution_permitted": False,
        "model_training_permitted": False,
        "production_ranking_permitted": False,
        "outreach_permitted": False,
        "policy": EXPECTED_POLICY,
    }

    if write_contract:
        contract_path = project_root / "docs" / "data_contracts" / "shadow_evaluation_plan.json"

        report["contract_path"] = str(contract_path.relative_to(project_root))

        _atomic_json(
            contract_path,
            report,
        )

    return report


def export_client_input_bundle(
    project_root: Path,
    *,
    write_contracts: bool = True,
) -> dict[str, Any]:
    readiness_config = _load_object(project_root / "config" / "pilot_readiness.json")

    raw_inputs = readiness_config.get("required_client_inputs")

    if not isinstance(
        raw_inputs,
        list,
    ):
        raise RuntimeError("Pilot client inputs are malformed.")

    templates: dict[
        str,
        dict[str, Any],
    ] = {
        "pilot_success_event": {
            "event_name": None,
            "decision_maker_confirmation_required": None,
            "acceptable_evidence": [],
            "measurement_window_days": None,
            "notes": None,
        },
        "transaction_economics": {
            "service_segments": [],
            "commission_ranges": [],
            "transaction_size_ranges": [],
            "typical_cycle_time_days": [],
            "representative_time_cost_assumptions": [],
        },
        "pilot_representatives": {
            "representatives": [],
            "required_fields": [
                "representative_id",
                "starting_location",
                "territory",
                "specializations",
                "existing_relationships",
                "daily_capacity",
                "preferred_channels",
            ],
        },
        "protected_accounts_and_exclusions": {
            "existing_clients": [],
            "protected_relationships": [],
            "active_assignments": [],
            "do_not_contact": [],
            "broker_owned_accounts": [],
            "territory_restrictions": [],
            "conflicts": [],
        },
        "operating_environment": {
            "approved_interface": None,
            "crm_system": None,
            "spreadsheet_system": None,
            "mobile_requirement": None,
            "browser_requirement": None,
            "data_import_format": None,
            "data_export_format": None,
        },
    }

    sections: list[dict[str, Any]] = []

    for raw_input in raw_inputs:
        if not isinstance(
            raw_input,
            dict,
        ):
            raise RuntimeError("Every client input must be an object.")

        input_id_value = raw_input.get("input_id")

        description_value = raw_input.get("description")

        if (
            not isinstance(
                input_id_value,
                str,
            )
            or not input_id_value
        ):
            raise RuntimeError("Client input ID must be a nonempty string.")

        if not isinstance(
            description_value,
            str,
        ):
            raise RuntimeError("Client input description must be a string.")

        sections.append(
            {
                "input_id": input_id_value,
                "description": (description_value),
                "provided": False,
                "authoritative_source": None,
                "approved_by": None,
                "approved_at": None,
                "values": templates.get(
                    input_id_value,
                    {},
                ),
            }
        )

    bundle: dict[str, Any] = {
        "model_version": ("cre-foundry-client-input-bundle-v1"),
        "section_count": len(sections),
        "sections": sections,
        "all_inputs_complete": False,
        "automatic_approval": False,
        "model_training_enabled": False,
        "opportunity_ranked": False,
        "outreach_eligible": False,
    }

    markdown_lines = [
        "# Client Input Bundle",
        "",
        ("Complete each section using authoritative, client-approved information."),
        "",
    ]

    for section in sections:
        markdown_lines.extend(
            [
                "## " + str(section["input_id"]),
                "",
                str(section["description"]),
                "",
                "- Provided: `false`",
                "- Authoritative source: _blank_",
                "- Approved by: _blank_",
                "- Approved at: _blank_",
                "",
            ]
        )

    markdown_lines.extend(
        [
            "No input becomes active automatically.",
            "",
            ("Model training, production ranking and outreach remain disabled."),
            "",
        ]
    )

    if write_contracts:
        contract_root = project_root / "docs" / "data_contracts"

        json_path = contract_root / "client_input_bundle.json"

        markdown_path = contract_root / "client_input_bundle.md"

        bundle["contract_paths"] = {
            "json": str(json_path.relative_to(project_root)),
            "markdown": str(markdown_path.relative_to(project_root)),
        }

        _atomic_json(
            json_path,
            bundle,
        )

        _atomic_text(
            markdown_path,
            "\n".join(markdown_lines),
        )

    return bundle
