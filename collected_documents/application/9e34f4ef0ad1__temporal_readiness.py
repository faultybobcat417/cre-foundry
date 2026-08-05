from __future__ import annotations

import json
import os
import tempfile
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

EXPECTED_POLICY: dict[str, Any] = {
    "operating_mode": "shadow",
    "read_only": True,
    "automatic_temporal_semantics_approval": False,
    "automatic_feature_approval": False,
    "automatic_snapshot_registration": False,
    "dataset_materialization_enabled": False,
    "model_training_enabled": False,
    "opportunity_ranked": False,
    "outreach_eligible": False,
}

TEMPORAL_TYPE_TOKENS = (
    "DATE",
    "TIME",
    "TIMESTAMP",
)

TEMPORAL_NAME_SUFFIXES = (
    "_at",
    "_date",
    "_time",
    "_timestamp",
    "_utc",
)

LINEAGE_NAMES = {
    "bronze_run_id",
    "manifest_path",
    "run_id",
    "snapshot_id",
    "source_id",
    "source_run_id",
}

LINEAGE_SUFFIXES = (
    "_hash",
    "_sha256",
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
    config = _load_object(project_root / "config" / "temporal_readiness.json")

    raw_policy = config.get("policy")

    if not isinstance(
        raw_policy,
        dict,
    ):
        raise RuntimeError("Temporal-readiness policy must be an object.")

    policy: dict[str, Any] = {str(key): value for key, value in raw_policy.items()}

    if policy != EXPECTED_POLICY:
        raise RuntimeError("Temporal-readiness policy mismatch.")

    return config


def _contract(
    project_root: Path,
    filename: str,
) -> dict[str, Any]:
    return _load_object(project_root / "docs" / "data_contracts" / filename)


def _relation_key(
    primitive: dict[str, Any],
) -> str:
    return (
        str(primitive["engine"]) + ":" + str(primitive["schema"]) + "." + str(primitive["relation"])
    )


def _is_temporal(
    primitive: dict[str, Any],
) -> bool:
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
    ).upper()

    raw_classification = primitive.get("classification")

    classification = (
        {str(key): value for key, value in raw_classification.items()}
        if isinstance(
            raw_classification,
            dict,
        )
        else {}
    )

    return (
        bool(classification.get("temporal_candidate"))
        or any(token in data_type for token in TEMPORAL_TYPE_TOKENS)
        or column_name.endswith(TEMPORAL_NAME_SUFFIXES)
    )


def _is_lineage(
    primitive: dict[str, Any],
) -> bool:
    column_name = str(
        primitive.get(
            "column",
            "",
        )
    ).lower()

    raw_classification = primitive.get("classification")

    classification = (
        {str(key): value for key, value in raw_classification.items()}
        if isinstance(
            raw_classification,
            dict,
        )
        else {}
    )

    return (
        bool(classification.get("lineage_candidate"))
        or column_name in LINEAGE_NAMES
        or column_name.endswith(LINEAGE_SUFFIXES)
        or column_name.startswith("source_")
    )


def _safe_metric(
    value: object,
) -> object:
    if value is None:
        return None

    if isinstance(
        value,
        bool | int | float | str,
    ):
        return value

    return str(value)


def build_temporal_readiness_bundle(
    project_root: Path,
    *,
    write_contracts: bool = True,
) -> dict[str, Any]:
    _load_config(project_root)

    inventory = _contract(
        project_root,
        "primitive_inventory.json",
    )

    quality = _contract(
        project_root,
        "primitive_quality_profile.json",
    )

    dependencies = _contract(
        project_root,
        "relation_dependency_graph.json",
    )

    feature_review = _contract(
        project_root,
        "shadow_feature_review.json",
    )

    shadow_audit = _contract(
        project_root,
        "shadow_learning_audit.json",
    )

    evaluation_plan = _contract(
        project_root,
        "shadow_evaluation_plan.json",
    )

    readiness = _contract(
        project_root,
        "pilot_readiness_dossier.json",
    )

    snapshot_review = _contract(
        project_root,
        "source_snapshot_bootstrap_review.json",
    )

    primitive_count = _require_nonnegative_int(
        inventory.get("primitive_count"),
        "primitive inventory primitive_count",
    )

    relation_count = _require_nonnegative_int(
        inventory.get("relation_count"),
        "primitive inventory relation_count",
    )

    raw_primitives = inventory.get("primitives")

    raw_relation_profiles = quality.get("relation_profiles")

    raw_feature_entries = feature_review.get("entries")

    raw_dependency_nodes = dependencies.get("nodes")

    if not isinstance(
        raw_primitives,
        list,
    ):
        raise RuntimeError("Primitive inventory must contain a list.")

    if not isinstance(
        raw_relation_profiles,
        list,
    ):
        raise RuntimeError("Quality relation profiles must be a list.")

    if not isinstance(
        raw_feature_entries,
        list,
    ):
        raise RuntimeError("Feature review entries must be a list.")

    if not isinstance(
        raw_dependency_nodes,
        list,
    ):
        raise RuntimeError("Dependency nodes must be a list.")

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

        raw_columns = raw_relation_profile.get("column_profiles")

        if not isinstance(
            raw_columns,
            list,
        ):
            raise RuntimeError("Column profiles must be a list.")

        for raw_column in raw_columns:
            if not isinstance(
                raw_column,
                dict,
            ):
                raise RuntimeError("Column profile must be an object.")

            column_profile: dict[str, Any] = {str(key): value for key, value in raw_column.items()}

            primitive_id = column_profile.get("primitive_id")

            if (
                not isinstance(
                    primitive_id,
                    str,
                )
                or not primitive_id
            ):
                raise RuntimeError("Column profile lacks a primitive ID.")

            quality_by_primitive[primitive_id] = column_profile

    feature_role_by_primitive: dict[
        str,
        str,
    ] = {}

    for raw_entry in raw_feature_entries:
        if not isinstance(
            raw_entry,
            dict,
        ):
            raise RuntimeError("Feature entry must be an object.")

        primitive_id = raw_entry.get("primitive_id")

        feature_role = raw_entry.get("feature_role")

        if (
            not isinstance(
                primitive_id,
                str,
            )
            or not primitive_id
        ):
            raise RuntimeError("Feature entry lacks a primitive ID.")

        if not isinstance(
            feature_role,
            str,
        ):
            raise RuntimeError("Feature role must be a string.")

        feature_role_by_primitive[primitive_id] = feature_role

    downstream_by_relation: dict[
        str,
        int,
    ] = {}

    for raw_node in raw_dependency_nodes:
        if not isinstance(
            raw_node,
            dict,
        ):
            raise RuntimeError("Dependency node must be an object.")

        relation_value = raw_node.get("relation")

        downstream_value = raw_node.get("downstream_relation_count")

        if (
            not isinstance(
                relation_value,
                str,
            )
            or not relation_value
        ):
            raise RuntimeError("Dependency relation must be a string.")

        downstream_by_relation[relation_value] = _require_nonnegative_int(
            downstream_value,
            "dependency downstream_relation_count",
        )

    primitives_by_relation: dict[
        str,
        list[dict[str, Any]],
    ] = defaultdict(list)

    for raw_primitive in raw_primitives:
        if not isinstance(
            raw_primitive,
            dict,
        ):
            raise RuntimeError("Primitive must be an object.")

        primitive: dict[str, Any] = {str(key): value for key, value in raw_primitive.items()}

        primitive_id = primitive.get("primitive_id")

        if (
            not isinstance(
                primitive_id,
                str,
            )
            or not primitive_id
        ):
            raise RuntimeError("Primitive lacks an ID.")

        primitives_by_relation[_relation_key(primitive)].append(primitive)

    relation_reviews: list[dict[str, Any]] = []

    status_counts: Counter[str] = Counter()

    feature_definitions: list[dict[str, Any]] = []

    for relation in sorted(primitives_by_relation):
        primitives = sorted(
            primitives_by_relation[relation],
            key=lambda primitive: str(primitive["primitive_id"]),
        )

        temporal_candidates = []
        lineage_candidates = []
        feature_role_counts: Counter[str] = Counter()

        for primitive in primitives:
            primitive_id = str(primitive["primitive_id"])

            column_name = str(
                primitive.get(
                    "column",
                    "",
                )
            )

            profile = quality_by_primitive.get(
                primitive_id,
                {},
            )

            role = feature_role_by_primitive.get(
                primitive_id,
                "blocked_missing_feature_review",
            )

            feature_role_counts[role] += 1

            metric = {
                "primitive_id": primitive_id,
                "column": column_name,
                "data_type": primitive.get("data_type"),
                "minimum": _safe_metric(profile.get("minimum")),
                "maximum": _safe_metric(profile.get("maximum")),
                "null_ratio": _safe_metric(profile.get("null_ratio")),
            }

            if _is_temporal(primitive):
                temporal_candidates.append(metric)

            if _is_lineage(primitive):
                lineage_candidates.append(metric)

            if role == "review_required":
                feature_definitions.append(
                    {
                        "primitive_id": (primitive_id),
                        "relation": relation,
                        "column": column_name,
                        "data_type": primitive.get("data_type"),
                        "business_definition": None,
                        "unit": None,
                        "transformation": None,
                        "as_of_rule": None,
                        "missingness_policy": None,
                        "validity_range": None,
                        "leakage_review_status": ("unapproved"),
                        "point_in_time_review_status": ("unapproved"),
                        "owner": None,
                        "approval_status": ("unapproved"),
                        "model_feature_enabled": False,
                    }
                )

        if not temporal_candidates:
            status = "blocked_no_temporal_semantics"

        elif not lineage_candidates:
            status = "blocked_no_lineage_semantics"

        elif len(temporal_candidates) > 1:
            status = "review_multiple_temporal_candidates"

        else:
            status = "review_temporal_semantics"

        status_counts[status] += 1

        relation_reviews.append(
            {
                "relation": relation,
                "primitive_count": len(primitives),
                "temporal_candidate_count": len(temporal_candidates),
                "temporal_candidates": (temporal_candidates),
                "lineage_candidate_count": len(lineage_candidates),
                "lineage_candidates": (lineage_candidates),
                "feature_role_counts": dict(sorted(feature_role_counts.items())),
                "downstream_relation_count": (
                    downstream_by_relation.get(
                        relation,
                        0,
                    )
                ),
                "status": status,
                "approved_as_of_column": None,
                "approved_effective_time_rule": None,
                "approved_availability_time_rule": None,
                "temporal_semantics_approved": False,
                "feature_source_approved": False,
            }
        )

    feature_definitions.sort(key=lambda item: str(item["primitive_id"]))

    temporal_review: dict[str, Any] = {
        "model_version": ("cre-foundry-temporal-relation-review-v1"),
        "relation_count": len(relation_reviews),
        "inventory_relation_count": (relation_count),
        "primitive_count": primitive_count,
        "status_counts": dict(sorted(status_counts.items())),
        "approved_temporal_relation_count": 0,
        "approved_feature_source_count": 0,
        "relations": relation_reviews,
        "review_ready": (len(relation_reviews) == relation_count),
        "policy": EXPECTED_POLICY,
        "dataset_materialization_enabled": False,
        "model_training_enabled": False,
        "opportunity_ranked": False,
        "outreach_eligible": False,
    }

    feature_queue: dict[str, Any] = {
        "model_version": ("cre-foundry-feature-definition-queue-v1"),
        "purpose": ("feature_definition_engineering_only"),
        "definition_count": len(feature_definitions),
        "approved_definition_count": 0,
        "enabled_feature_count": 0,
        "definitions": feature_definitions,
        "automatic_feature_approval": False,
        "dataset_materialization_enabled": False,
        "model_training_enabled": False,
        "opportunity_ranking": False,
        "account_ranking": False,
        "outreach_eligible": False,
        "policy": EXPECTED_POLICY,
    }

    blockers = [
        "no_approved_temporal_relations",
        "no_approved_feature_definitions",
    ]

    evaluation_blockers = evaluation_plan.get("blockers")

    if isinstance(
        evaluation_blockers,
        list,
    ):
        blockers.extend(str(blocker) for blocker in evaluation_blockers)

    feature_snapshot_count = _require_nonnegative_int(
        shadow_audit.get("feature_snapshot_count"),
        "shadow feature snapshot count",
    )

    outcome_event_count = _require_nonnegative_int(
        shadow_audit.get("outcome_event_count"),
        "shadow outcome event count",
    )

    missing_client_inputs = _require_nonnegative_int(
        readiness.get("missing_client_input_count"),
        "missing client input count",
    )

    registration_count = _require_nonnegative_int(
        snapshot_review.get("registration_execution_count"),
        "bootstrap registration execution count",
    )

    if feature_snapshot_count == 0:
        blockers.append("no_registered_feature_snapshots")

    if outcome_event_count == 0:
        blockers.append("no_verified_outcome_events")

    if missing_client_inputs > 0:
        blockers.append("authoritative_client_inputs_incomplete")

    if registration_count == 0:
        blockers.append("no_registered_source_snapshots")

    unique_blockers = sorted(set(blockers))

    dataset_plan: dict[str, Any] = {
        "model_version": ("cre-foundry-point-in-time-dataset-plan-v1"),
        "required_join_semantics": [
            "feature_observed_at_must_not_exceed_decision_time",
            "feature_available_at_must_not_exceed_decision_time",
            "source_snapshot_must_exist_before_decision_time",
            "outcome_window_must_begin_after_decision_time",
            "training_rows_must_precede_validation_rows",
            "approved_embargo_must_separate_train_and_validation",
        ],
        "relation_count": relation_count,
        "approved_temporal_relation_count": 0,
        "feature_definition_count": len(feature_definitions),
        "approved_feature_definition_count": 0,
        "feature_snapshot_count": (feature_snapshot_count),
        "outcome_event_count": (outcome_event_count),
        "missing_client_input_count": (missing_client_inputs),
        "registered_source_snapshot_count": 0,
        "blocker_count": len(unique_blockers),
        "blockers": unique_blockers,
        "plan_ready": True,
        "dataset_build_ready": False,
        "dataset_build_execution_permitted": False,
        "snapshot_registration_permitted": False,
        "feature_approval_permitted": False,
        "model_training_permitted": False,
        "production_ranking_permitted": False,
        "outreach_permitted": False,
        "policy": EXPECTED_POLICY,
    }

    if write_contracts:
        contract_root = project_root / "docs" / "data_contracts"

        temporal_path = contract_root / "temporal_relation_review.json"

        feature_path = contract_root / "feature_definition_queue.json"

        dataset_path = contract_root / "point_in_time_dataset_plan.json"

        paths = {
            "temporal_review": str(temporal_path.relative_to(project_root)),
            "feature_queue": str(feature_path.relative_to(project_root)),
            "dataset_plan": str(dataset_path.relative_to(project_root)),
        }

        temporal_review["contract_paths"] = paths

        feature_queue["contract_paths"] = paths

        dataset_plan["contract_paths"] = paths

        _atomic_json(
            temporal_path,
            temporal_review,
        )

        _atomic_json(
            feature_path,
            feature_queue,
        )

        _atomic_json(
            dataset_path,
            dataset_plan,
        )

    return {
        "temporal_review": (temporal_review),
        "feature_queue": feature_queue,
        "dataset_plan": dataset_plan,
    }
