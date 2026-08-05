from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import duckdb

EXPECTED_POLICY: dict[str, Any] = {
    "operating_mode": "shadow",
    "read_only": True,
    "automatic_schema_mutation": False,
    "automatic_backfill": False,
    "automatic_acquisition": False,
    "automatic_conclusions": False,
    "opportunity_ranked": False,
    "outreach_eligible": False,
}

SEVERITY_ORDER = {
    "critical": 0,
    "high": 1,
    "medium": 2,
    "low": 3,
}

DEFAULT_PRIORITY = {
    "critical": "P0",
    "high": "P1",
    "medium": "P2",
    "low": "P3",
}

REMEDIATION_ACTIONS = {
    "all_null_important_primitive": (
        "Confirm source availability and mapping. "
        "Backfill only from an authorized point-in-time source, "
        "or remove the unsupported semantic role."
    ),
    "high_null_important_primitive": (
        "Audit source coverage, parser behavior and join loss. "
        "Add explicit coverage monitoring before downstream use."
    ),
    "material_null_important_primitive": (
        "Document the missingness mechanism and segment coverage. "
        "Do not impute until a validated analytical use exists."
    ),
    "nonempty_relation_without_lineage_primitive": (
        "Add source, run, snapshot or checksum lineage, "
        "or explicitly classify the relation as static reference data."
    ),
    "nonempty_relation_without_temporal_primitive": (
        "Add observed-at or effective-at semantics, "
        "or explicitly classify the relation as timeless reference data."
    ),
    "relation_profile_query_failed": (
        "Repair the relation-specific profiling query before "
        "accepting the relation into any evaluation dataset."
    ),
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

    if not isinstance(raw, dict):
        raise RuntimeError(f"Expected JSON object: {path}")

    return {str(key): value for key, value in raw.items()}


def _load_config(
    project_root: Path,
) -> dict[str, Any]:
    config = _load_object(project_root / "config" / "data_health.json")

    raw_policy = config.get("policy")

    if not isinstance(raw_policy, dict):
        raise RuntimeError("Data-health policy must be an object.")

    policy: dict[str, Any] = {str(key): value for key, value in raw_policy.items()}

    if policy != EXPECTED_POLICY:
        raise RuntimeError("Data-health policy mismatch.")

    return config


def _contract(
    project_root: Path,
    filename: str,
) -> dict[str, Any]:
    return _load_object(project_root / "docs" / "data_contracts" / filename)


def _stable_hash(
    payload: Any,
) -> str:
    encoded = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    ).encode("utf-8")

    return hashlib.sha256(encoded).hexdigest()


def _relation_key(
    engine: str,
    schema_name: str,
    relation_name: str,
) -> str:
    return engine + ":" + schema_name + "." + relation_name


def _parse_relation_key(
    relation_key: str,
) -> tuple[str, str, str]:
    engine, remainder = relation_key.split(
        ":",
        1,
    )

    schema_name, relation_name = remainder.split(
        ".",
        1,
    )

    return (
        engine,
        schema_name,
        relation_name,
    )


def _strict_dependency_graph(
    project_root: Path,
    relation_keys: set[str],
) -> dict[str, Any]:
    duckdb_relations: dict[str, tuple[str, str]] = {}

    for relation_key in relation_keys:
        (
            engine,
            schema_name,
            relation_name,
        ) = _parse_relation_key(relation_key)

        if engine == "duckdb":
            duckdb_relations[relation_key] = (
                schema_name,
                relation_name,
            )

    warehouse_path = project_root / "data" / "warehouse" / "cre.duckdb"

    connection = duckdb.connect(
        str(warehouse_path),
        read_only=True,
    )

    try:
        rows = connection.execute(
            """
            SELECT
                table_schema,
                table_name,
                view_definition
            FROM information_schema.views
            ORDER BY
                table_schema,
                table_name
            """
        ).fetchall()

    finally:
        connection.close()

    edges: list[dict[str, str]] = []
    edge_ids: set[tuple[str, str]] = set()

    for raw_schema, raw_view, raw_definition in rows:
        schema_name = str(raw_schema)
        view_name = str(raw_view)

        view_key = _relation_key(
            "duckdb",
            schema_name,
            view_name,
        )

        if view_key not in duckdb_relations:
            continue

        definition = str(raw_definition or "")

        for (
            dependency_key,
            (
                dependency_schema,
                dependency_relation,
            ),
        ) in duckdb_relations.items():
            if dependency_key == view_key:
                continue

            plain_pattern = re.compile(
                r"(?<![A-Za-z0-9_])"
                + re.escape(dependency_schema)
                + r"\s*\.\s*"
                + re.escape(dependency_relation)
                + r"(?![A-Za-z0-9_])",
                re.IGNORECASE,
            )

            quoted_pattern = re.compile(
                re.escape('"' + dependency_schema + '"')
                + r"\s*\.\s*"
                + re.escape('"' + dependency_relation + '"'),
                re.IGNORECASE,
            )

            if not (plain_pattern.search(definition) or quoted_pattern.search(definition)):
                continue

            edge_id = (
                dependency_key,
                view_key,
            )

            if edge_id in edge_ids:
                continue

            edge_ids.add(edge_id)

            edges.append(
                {
                    "from_relation": (dependency_key),
                    "to_relation": view_key,
                    "relationship": ("strict_view_sql_reference"),
                }
            )

    downstream_counts: Counter[str] = Counter()

    upstream_counts: Counter[str] = Counter()

    for edge in edges:
        downstream_counts[edge["from_relation"]] += 1

        upstream_counts[edge["to_relation"]] += 1

    nodes = []

    for relation_key in sorted(relation_keys):
        nodes.append(
            {
                "relation": relation_key,
                "upstream_dependency_count": int(
                    upstream_counts.get(
                        relation_key,
                        0,
                    )
                ),
                "downstream_relation_count": int(
                    downstream_counts.get(
                        relation_key,
                        0,
                    )
                ),
            }
        )

    return {
        "model_version": ("cre-foundry-relation-dependency-graph-v1"),
        "method": ("strict_information_schema_view_definition_reference"),
        "node_count": len(nodes),
        "edge_count": len(edges),
        "nodes": nodes,
        "edges": sorted(
            edges,
            key=lambda edge: (
                edge["from_relation"],
                edge["to_relation"],
            ),
        ),
        "policy": EXPECTED_POLICY,
        "graph_ready": True,
        "opportunity_ranking": False,
        "outreach_eligible": False,
    }


def _maximum_severity(
    issues: list[dict[str, Any]],
) -> str:
    if not issues:
        return "low"

    return min(
        (
            str(
                issue.get(
                    "severity",
                    "low",
                )
            )
            for issue in issues
        ),
        key=lambda severity: SEVERITY_ORDER.get(
            severity,
            99,
        ),
    )


def build_data_health_bundle(
    project_root: Path,
    *,
    write_contracts: bool = True,
) -> dict[str, Any]:
    config = _load_config(project_root)

    inventory = _contract(
        project_root,
        "primitive_inventory.json",
    )

    quality = _contract(
        project_root,
        "primitive_quality_profile.json",
    )

    remediation_source = _contract(
        project_root,
        "primitive_remediation_queue.json",
    )

    if not inventory.get("inventory_ready"):
        raise RuntimeError("Primitive inventory is not ready.")

    if not quality.get("profile_ready"):
        raise RuntimeError("Primitive quality profile is not ready.")

    raw_primitives = inventory.get("primitives")

    raw_profiles = quality.get("relation_profiles")

    raw_issues = remediation_source.get("issues")

    if not isinstance(
        raw_primitives,
        list,
    ):
        raise RuntimeError("Primitive inventory has no primitive list.")

    if not isinstance(
        raw_profiles,
        list,
    ):
        raise RuntimeError("Quality profile has no relation list.")

    if not isinstance(
        raw_issues,
        list,
    ):
        raise RuntimeError("Remediation contract has no issue list.")

    primitives_by_relation: dict[
        str,
        list[dict[str, Any]],
    ] = defaultdict(list)

    for raw_primitive in raw_primitives:
        if not isinstance(
            raw_primitive,
            dict,
        ):
            raise RuntimeError("Primitive entry must be an object.")

        primitive: dict[str, Any] = {str(key): value for key, value in raw_primitive.items()}

        relation_key = _relation_key(
            str(primitive["engine"]),
            str(primitive["schema"]),
            str(primitive["relation"]),
        )

        primitives_by_relation[relation_key].append(primitive)

    profiles_by_relation: dict[
        str,
        dict[str, Any],
    ] = {}

    for raw_profile in raw_profiles:
        if not isinstance(
            raw_profile,
            dict,
        ):
            raise RuntimeError("Relation profile must be an object.")

        profile: dict[str, Any] = {str(key): value for key, value in raw_profile.items()}

        relation_key = _relation_key(
            str(profile["engine"]),
            str(profile["schema"]),
            str(profile["relation"]),
        )

        profiles_by_relation[relation_key] = profile

    issues_by_relation: dict[
        str,
        list[dict[str, Any]],
    ] = defaultdict(list)

    normalized_issues: list[dict[str, Any]] = []

    for raw_issue in raw_issues:
        if not isinstance(
            raw_issue,
            dict,
        ):
            raise RuntimeError("Remediation issue must be an object.")

        issue: dict[str, Any] = {str(key): value for key, value in raw_issue.items()}

        relation = issue.get("relation")

        if not isinstance(
            relation,
            str,
        ):
            raise RuntimeError("Remediation issue lacks a relation.")

        normalized_issues.append(issue)

        issues_by_relation[relation].append(issue)

    inventory_relations = set(primitives_by_relation)

    profile_relations = set(profiles_by_relation)

    missing_profile_relations = sorted(inventory_relations - profile_relations)

    unexpected_profile_relations = sorted(profile_relations - inventory_relations)

    dependencies = _strict_dependency_graph(
        project_root,
        inventory_relations,
    )

    raw_dependency_nodes: object = dependencies.get("nodes")

    if not isinstance(
        raw_dependency_nodes,
        list,
    ):
        raise RuntimeError("Dependency graph nodes must be a list.")

    downstream_counts: dict[str, int] = {}

    for raw_dependency_node in raw_dependency_nodes:
        if not isinstance(
            raw_dependency_node,
            dict,
        ):
            raise RuntimeError("Every dependency node must be an object.")

        dependency_node: dict[str, object] = {
            str(key): value for key, value in raw_dependency_node.items()
        }

        relation_value = dependency_node.get("relation")

        downstream_value = dependency_node.get("downstream_relation_count")

        if (
            not isinstance(
                relation_value,
                str,
            )
            or not relation_value
        ):
            raise RuntimeError("Dependency relation must be a nonempty string.")

        if isinstance(
            downstream_value,
            bool,
        ) or not isinstance(
            downstream_value,
            int,
        ):
            raise RuntimeError("Dependency downstream count must be an integer.")

        if downstream_value < 0:
            raise RuntimeError("Dependency downstream count cannot be negative.")

        downstream_counts[relation_value] = downstream_value

    relation_baselines = []
    relation_fingerprints: dict[
        str,
        dict[str, str],
    ] = {}

    for relation_key in sorted(inventory_relations):
        relation_primitives = sorted(
            primitives_by_relation[relation_key],
            key=lambda primitive: str(primitive["primitive_id"]),
        )

        relation_profile = profiles_by_relation.get(relation_key)

        if relation_profile is None:
            continue

        raw_column_profiles = relation_profile.get("column_profiles")

        if not isinstance(
            raw_column_profiles,
            list,
        ):
            raise RuntimeError("Column profiles must be a list.")

        compact_profiles = []

        for raw_column_profile in raw_column_profiles:
            if not isinstance(
                raw_column_profile,
                dict,
            ):
                raise RuntimeError("Column profile must be an object.")

            column_profile: dict[
                str,
                Any,
            ] = {str(key): value for key, value in raw_column_profile.items()}

            compact_profiles.append(
                {
                    "primitive_id": (column_profile.get("primitive_id")),
                    "column": (column_profile.get("column")),
                    "row_count": (column_profile.get("row_count")),
                    "null_count": (column_profile.get("null_count")),
                    "null_ratio": (column_profile.get("null_ratio")),
                    "distinct_count": (column_profile.get("distinct_count")),
                    "minimum": (column_profile.get("minimum")),
                    "maximum": (column_profile.get("maximum")),
                    "true_count": (column_profile.get("true_count")),
                    "false_count": (column_profile.get("false_count")),
                }
            )

        schema_payload = [
            {
                "primitive_id": primitive.get("primitive_id"),
                "column": primitive.get("column"),
                "data_type": primitive.get("data_type"),
                "nullable": primitive.get("nullable"),
                "classification": primitive.get("classification"),
            }
            for primitive in relation_primitives
        ]

        quality_payload = {
            "row_count": relation_profile.get("row_count"),
            "columns": sorted(
                compact_profiles,
                key=lambda profile: str(profile["primitive_id"]),
            ),
        }

        schema_fingerprint = _stable_hash(schema_payload)

        quality_fingerprint = _stable_hash(quality_payload)

        relation_issues = issues_by_relation.get(
            relation_key,
            [],
        )

        severity_counts = Counter(
            str(
                issue.get(
                    "severity",
                    "low",
                )
            )
            for issue in relation_issues
        )

        issue_type_counts = Counter(
            str(
                issue.get(
                    "issue_type",
                    "unknown",
                )
            )
            for issue in relation_issues
        )

        relation_baselines.append(
            {
                "relation": relation_key,
                "row_count": int(
                    relation_profile.get(
                        "row_count",
                        0,
                    )
                ),
                "primitive_count": len(relation_primitives),
                "issue_count": len(relation_issues),
                "severity_counts": dict(sorted(severity_counts.items())),
                "issue_type_counts": dict(sorted(issue_type_counts.items())),
                "downstream_relation_count": int(
                    downstream_counts.get(
                        relation_key,
                        0,
                    )
                ),
                "schema_fingerprint": (schema_fingerprint),
                "quality_fingerprint": (quality_fingerprint),
            }
        )

        relation_fingerprints[relation_key] = {
            "schema_fingerprint": (schema_fingerprint),
            "quality_fingerprint": (quality_fingerprint),
        }

    raw_priority_mapping = config.get("priority_mapping")

    priority_mapping = (
        {str(key): str(value) for key, value in raw_priority_mapping.items()}
        if isinstance(
            raw_priority_mapping,
            dict,
        )
        else DEFAULT_PRIORITY
    )

    work_items: list[dict[str, Any]] = []

    for relation_key in sorted(issues_by_relation):
        relation_issues = issues_by_relation[relation_key]

        maximum_severity = _maximum_severity(relation_issues)

        issue_types = sorted(
            {
                str(
                    issue.get(
                        "issue_type",
                        "unknown",
                    )
                )
                for issue in relation_issues
            }
        )

        actions = [
            REMEDIATION_ACTIONS.get(
                issue_type,
                (
                    "Investigate the structural data-quality "
                    "condition and document an approved repair."
                ),
            )
            for issue_type in issue_types
        ]

        work_item_payload = {
            "relation": relation_key,
            "maximum_severity": (maximum_severity),
            "issue_types": issue_types,
        }

        work_items.append(
            {
                "work_item_id": ("dh_" + _stable_hash(work_item_payload)[:16]),
                "relation": relation_key,
                "engineering_priority": (
                    priority_mapping.get(
                        maximum_severity,
                        "P3",
                    )
                ),
                "maximum_severity": (maximum_severity),
                "issue_count": len(relation_issues),
                "issue_types": issue_types,
                "recommended_actions": actions,
                "downstream_relation_count": int(
                    downstream_counts.get(
                        relation_key,
                        0,
                    )
                ),
                "manual_approval_required": True,
                "automatic_schema_mutation": False,
                "automatic_backfill": False,
                "opportunity_ranking": False,
            }
        )

    def _work_item_sort_key(
        item: dict[str, Any],
    ) -> tuple[str, int, str]:
        priority_value: object = item.get("engineering_priority")

        downstream_value: object = item.get("downstream_relation_count")

        relation_value: object = item.get("relation")

        if (
            not isinstance(
                priority_value,
                str,
            )
            or not priority_value
        ):
            raise RuntimeError("Work-item priority must be a nonempty string.")

        if isinstance(
            downstream_value,
            bool,
        ) or not isinstance(
            downstream_value,
            int,
        ):
            raise RuntimeError("Work-item downstream count must be an integer.")

        if downstream_value < 0:
            raise RuntimeError("Work-item downstream count cannot be negative.")

        if (
            not isinstance(
                relation_value,
                str,
            )
            or not relation_value
        ):
            raise RuntimeError("Work-item relation must be a nonempty string.")

        return (
            priority_value,
            -downstream_value,
            relation_value,
        )

    work_items.sort(key=_work_item_sort_key)

    baseline: dict[str, Any] = {
        "model_version": ("cre-foundry-data-health-baseline-v1"),
        "relation_count": len(relation_baselines),
        "primitive_count": int(inventory["primitive_count"]),
        "issue_count": len(normalized_issues),
        "missing_profile_relations": (missing_profile_relations),
        "unexpected_profile_relations": (unexpected_profile_relations),
        "relation_fingerprints": (relation_fingerprints),
        "relation_baselines": (relation_baselines),
        "policy": EXPECTED_POLICY,
        "baseline_ready": (
            not missing_profile_relations
            and not unexpected_profile_relations
            and len(relation_baselines) == int(inventory["relation_count"])
        ),
        "automatic_schema_mutation": False,
        "automatic_backfill": False,
        "opportunity_ranked": False,
        "outreach_eligible": False,
    }

    remediation: dict[str, Any] = {
        "model_version": ("cre-foundry-data-health-remediation-v1"),
        "purpose": ("data_engineering_remediation_only"),
        "work_item_count": len(work_items),
        "source_issue_count": len(normalized_issues),
        "work_items": work_items,
        "policy": EXPECTED_POLICY,
        "automatic_schema_mutation": False,
        "automatic_backfill": False,
        "opportunity_ranking": False,
        "account_ranking": False,
        "outreach_eligible": False,
    }

    if write_contracts:
        contract_root = project_root / "docs" / "data_contracts"

        baseline_path = contract_root / "data_health_baseline.json"

        dependency_path = contract_root / "relation_dependency_graph.json"

        remediation_path = contract_root / "data_health_remediation_plan.json"

        baseline["contract_paths"] = {
            "baseline": str(baseline_path.relative_to(project_root)),
            "dependencies": str(dependency_path.relative_to(project_root)),
            "remediation": str(remediation_path.relative_to(project_root)),
        }

        dependencies["contract_paths"] = baseline["contract_paths"]

        remediation["contract_paths"] = baseline["contract_paths"]

        _atomic_json(
            baseline_path,
            baseline,
        )

        _atomic_json(
            dependency_path,
            dependencies,
        )

        _atomic_json(
            remediation_path,
            remediation,
        )

    return {
        "baseline": baseline,
        "dependencies": dependencies,
        "remediation": remediation,
    }


def audit_data_health_baseline(
    project_root: Path,
    *,
    write_contract: bool = True,
) -> dict[str, Any]:
    baseline_path = project_root / "docs" / "data_contracts" / "data_health_baseline.json"

    if not baseline_path.is_file():
        raise RuntimeError("Data-health baseline has not been initialized.")

    saved = _load_object(baseline_path)

    current_bundle = build_data_health_bundle(
        project_root,
        write_contracts=False,
    )

    current = current_bundle["baseline"]

    saved_fingerprints_raw = saved.get("relation_fingerprints")

    current_fingerprints_raw = current.get("relation_fingerprints")

    if not isinstance(
        saved_fingerprints_raw,
        dict,
    ):
        raise RuntimeError("Saved relation fingerprints are invalid.")

    if not isinstance(
        current_fingerprints_raw,
        dict,
    ):
        raise RuntimeError("Current relation fingerprints are invalid.")

    saved_fingerprints = {str(key): value for key, value in saved_fingerprints_raw.items()}

    current_fingerprints = {str(key): value for key, value in current_fingerprints_raw.items()}

    saved_relations = set(saved_fingerprints)

    current_relations = set(current_fingerprints)

    added_relations = sorted(current_relations - saved_relations)

    removed_relations = sorted(saved_relations - current_relations)

    changed_relations = sorted(
        relation
        for relation in (saved_relations & current_relations)
        if saved_fingerprints[relation] != current_fingerprints[relation]
    )

    report: dict[str, Any] = {
        "model_version": ("cre-foundry-data-health-audit-v1"),
        "saved_relation_count": len(saved_relations),
        "current_relation_count": len(current_relations),
        "added_relation_count": len(added_relations),
        "removed_relation_count": len(removed_relations),
        "changed_relation_count": len(changed_relations),
        "added_relations": added_relations,
        "removed_relations": (removed_relations),
        "changed_relations": (changed_relations),
        "drift_detected": bool(added_relations or removed_relations or changed_relations),
        "baseline_matches_current": not (added_relations or removed_relations or changed_relations),
        "policy": EXPECTED_POLICY,
        "automatic_schema_mutation": False,
        "automatic_backfill": False,
        "opportunity_ranked": False,
        "outreach_eligible": False,
    }

    if write_contract:
        contract_path = project_root / "docs" / "data_contracts" / "data_health_audit.json"

        report["contract_path"] = str(contract_path.relative_to(project_root))

        _atomic_json(
            contract_path,
            report,
        )

    return report
