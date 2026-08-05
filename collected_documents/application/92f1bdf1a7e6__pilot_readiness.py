from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any

import duckdb

EXPECTED_POLICY: dict[str, Any] = {
    "operating_mode": "shadow",
    "read_only": True,
    "automatic_acquisition": False,
    "browser_execution": False,
    "computer_vision_execution": False,
    "automatic_conclusions": False,
    "opportunity_ranked": False,
    "outreach_eligible": False,
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


def _contract(
    project_root: Path,
    filename: str,
) -> dict[str, Any]:
    path = project_root / "docs" / "data_contracts" / filename

    if not path.is_file():
        raise RuntimeError(f"Missing contract: {filename}")

    return _load_object(path)


def _quote(
    identifier: str,
) -> str:
    return (
        '"'
        + identifier.replace(
            '"',
            '""',
        )
        + '"'
    )


def _relation_metrics(
    connection: duckdb.DuckDBPyConnection,
    schema_name: str,
    relation_name: str,
) -> dict[str, Any]:
    exists_row = connection.execute(
        """
        SELECT count(*)
        FROM information_schema.tables
        WHERE
            table_schema = ?
            AND table_name = ?
        """,
        [schema_name, relation_name],
    ).fetchone()

    exists = bool(exists_row and int(exists_row[0]) > 0)

    if not exists:
        return {
            "exists": False,
            "schema": schema_name,
            "relation": relation_name,
            "row_count": 0,
        }

    column_rows = connection.execute(
        """
        SELECT column_name
        FROM information_schema.columns
        WHERE
            table_schema = ?
            AND table_name = ?
        """,
        [schema_name, relation_name],
    ).fetchall()

    columns = {str(row[0]) for row in column_rows}

    expressions = ["COUNT(*) AS row_count"]

    included = []

    for column_name in (
        "opportunity_ranked",
        "outreach_eligible",
    ):
        if column_name not in columns:
            continue

        quoted_column = _quote(column_name)

        alias = column_name + "_true"

        expressions.append(
            f"SUM(CASE WHEN {quoted_column} IS TRUE THEN 1 ELSE 0 END) AS {_quote(alias)}"
        )

        included.append(column_name)

    relation_identifier = _quote(schema_name) + "." + _quote(relation_name)

    cursor = connection.execute("SELECT " + ", ".join(expressions) + " FROM " + relation_identifier)

    row = cursor.fetchone()

    if row is None:
        raise RuntimeError("Relation metrics returned no row.")

    names = [str(field[0]) for field in cursor.description]

    values = dict(
        zip(
            names,
            row,
            strict=True,
        )
    )

    report: dict[str, Any] = {
        "exists": True,
        "schema": schema_name,
        "relation": relation_name,
        "row_count": int(values["row_count"]),
    }

    for column_name in included:
        alias = column_name + "_true"

        report[alias] = int(values.get(alias) or 0)

    return report


def _markdown(
    report: dict[str, Any],
) -> str:
    capabilities_raw = report.get("capabilities")

    inputs_raw = report.get("client_inputs")

    if not isinstance(
        capabilities_raw,
        dict,
    ):
        raise RuntimeError("Capabilities must be an object.")

    if not isinstance(
        inputs_raw,
        list,
    ):
        raise RuntimeError("Client inputs must be a list.")

    lines = [
        "# CRE Foundry Pilot Readiness",
        "",
        ("**Overall status:** `" + str(report["overall_status"]) + "`"),
        "",
        "## Capability state",
        "",
    ]

    for name, status in capabilities_raw.items():
        lines.append(
            "- "
            + str(name).replace(
                "_",
                " ",
            )
            + ": `"
            + str(status)
            + "`"
        )

    lines.extend(
        [
            "",
            "## Missing client inputs",
            "",
        ]
    )

    for raw_item in inputs_raw:
        if not isinstance(
            raw_item,
            dict,
        ):
            continue

        if bool(raw_item.get("provided")):
            continue

        lines.append(
            "- `" + str(raw_item.get("input_id")) + "` — " + str(raw_item.get("description"))
        )

    lines.extend(
        [
            "",
            "## Safety boundary",
            "",
            "- Operating mode remains `shadow`.",
            "- Automatic acquisition remains disabled.",
            "- Browser and computer-vision execution remain disabled.",
            "- Automatic conclusions remain disabled.",
            "- Opportunity ranking remains disabled.",
            "- Outreach eligibility remains false.",
            "",
        ]
    )

    return "\n".join(lines)


def build_pilot_readiness_dossier(
    project_root: Path,
    *,
    write_contracts: bool = True,
) -> dict[str, Any]:
    config = _load_object(project_root / "config" / "pilot_readiness.json")

    raw_policy = config.get("policy")

    if not isinstance(
        raw_policy,
        dict,
    ):
        raise RuntimeError("Pilot-readiness policy must be an object.")

    policy: dict[str, Any] = {str(key): value for key, value in raw_policy.items()}

    if policy != EXPECTED_POLICY:
        raise RuntimeError("Pilot-readiness policy mismatch.")

    raw_inputs = config.get("required_client_inputs")

    if not isinstance(
        raw_inputs,
        list,
    ):
        raise RuntimeError("Required client inputs must be a list.")

    client_inputs: list[dict[str, Any]] = []

    seen_ids: set[str] = set()

    for raw_input in raw_inputs:
        if not isinstance(
            raw_input,
            dict,
        ):
            raise RuntimeError("Every client input must be an object.")

        item: dict[str, Any] = {str(key): value for key, value in raw_input.items()}

        input_id = item.get("input_id")

        if (
            not isinstance(
                input_id,
                str,
            )
            or not input_id
        ):
            raise RuntimeError("Every client input requires an ID.")

        if input_id in seen_ids:
            raise RuntimeError(f"Duplicate client input: {input_id}")

        seen_ids.add(input_id)

        if not isinstance(
            item.get("provided"),
            bool,
        ):
            raise RuntimeError(f"Client input {input_id} requires a boolean provided state.")

        client_inputs.append(item)

    missing_inputs = [item for item in client_inputs if not bool(item["provided"])]

    data_plane = _contract(
        project_root,
        "data_plane_readiness.json",
    )

    runtime = _contract(
        project_root,
        "source_runtime.json",
    )

    acquisition = _contract(
        project_root,
        "source_acquisition_plan.json",
    )

    browser = _contract(
        project_root,
        "browser_recipes.json",
    )

    inventory = _contract(
        project_root,
        "primitive_inventory.json",
    )

    quality = _contract(
        project_root,
        "primitive_quality_summary.json",
    )

    bootstrap = _contract(
        project_root,
        "source_snapshot_bootstrap_review.json",
    )

    plans_raw = acquisition.get(
        "plans",
        [],
    )

    if not isinstance(
        plans_raw,
        list,
    ):
        raise RuntimeError("Source acquisition plans must be a list.")

    freshness_configured_count = 0

    for raw_plan in plans_raw:
        if not isinstance(
            raw_plan,
            dict,
        ):
            continue

        if (
            raw_plan.get("freshness_target_hours") is not None
            and raw_plan.get("maximum_staleness_hours") is not None
        ):
            freshness_configured_count += 1

    enabled_raw = runtime.get(
        "enabled_schedule_sources",
        [],
    )

    enabled_schedule_count = (
        len(enabled_raw)
        if isinstance(
            enabled_raw,
            list,
        )
        else 0
    )

    warehouse_path = project_root / "data" / "warehouse" / "cre.duckdb"

    connection = duckdb.connect(
        str(warehouse_path),
        read_only=True,
    )

    try:
        task_metrics = _relation_metrics(
            connection,
            "control",
            "brampton_verification_task_state",
        )

        workflow_metrics = _relation_metrics(
            connection,
            "control",
            "brampton_verification_workflow_state",
        )

    finally:
        connection.close()

    safety_counts_zero = all(
        int(
            metrics.get(
                field,
                0,
            )
        )
        == 0
        for metrics in (
            task_metrics,
            workflow_metrics,
        )
        for field in (
            "opportunity_ranked_true",
            "outreach_eligible_true",
        )
    )

    if not safety_counts_zero:
        raise RuntimeError("Live ranking or outreach values are nonzero.")

    data_plane_ready = bool(
        data_plane.get(
            "ready",
            data_plane.get(
                "data_plane_ready",
                False,
            ),
        )
    )

    research_foundation_ready = all(
        (
            data_plane_ready,
            bool(runtime.get("ready")),
            bool(inventory.get("inventory_ready")),
            bool(quality.get("profile_ready")),
            bool(quality.get("safety_ready")),
            safety_counts_zero,
        )
    )

    manual_workflow_ready = all(
        (
            bool(task_metrics["exists"]),
            bool(workflow_metrics["exists"]),
            int(task_metrics["row_count"]) > 0,
            int(workflow_metrics["row_count"]) > 0,
        )
    )

    client_inputs_ready = not missing_inputs

    configured_source_count = int(
        runtime.get(
            "configured_source_count",
            0,
        )
    )

    schedule_ready = all(
        (
            configured_source_count > 0,
            enabled_schedule_count == configured_source_count,
            freshness_configured_count == configured_source_count,
        )
    )

    executable_browser_count = int(
        browser.get(
            "executable_count",
            0,
        )
    )

    browser_ready = executable_browser_count > 0

    pilot_ready = all(
        (
            research_foundation_ready,
            manual_workflow_ready,
            client_inputs_ready,
        )
    )

    capabilities = {
        "research_foundation": ("complete" if research_foundation_ready else "blocked"),
        "manual_verification_workflow": ("complete" if manual_workflow_ready else "blocked"),
        "scheduled_acquisition": ("complete" if schedule_ready else "disabled_pending_cadence"),
        "browser_acquisition": ("complete" if browser_ready else "design_pending"),
        "snapshot_registration": ("human_review_required"),
        "pilot_execution": ("ready" if pilot_ready else "blocked_by_client_inputs"),
        "predictive_validation": ("not_started"),
        "production_ranking": ("disabled"),
        "outreach": "disabled",
    }

    report: dict[str, Any] = {
        "model_version": ("cre-foundry-pilot-readiness-v1"),
        "overall_status": (
            "foundation_ready_for_controlled_next_steps"
            if research_foundation_ready
            else "foundation_attention_required"
        ),
        "capabilities": capabilities,
        "client_inputs": client_inputs,
        "missing_client_input_count": len(missing_inputs),
        "missing_client_input_ids": [str(item["input_id"]) for item in missing_inputs],
        "source_state": {
            "configured_source_count": (configured_source_count),
            "enabled_schedule_count": (enabled_schedule_count),
            "freshness_configured_count": (freshness_configured_count),
            "automatic_execution_count": int(
                acquisition.get(
                    "automatic_execution_count",
                    0,
                )
            ),
            "browser_execution_count": int(
                acquisition.get(
                    "browser_execution_count",
                    0,
                )
            ),
            "computer_vision_execution_count": int(
                acquisition.get(
                    "computer_vision_execution_count",
                    0,
                )
            ),
        },
        "data_state": {
            "primitive_count": int(
                inventory.get(
                    "primitive_count",
                    0,
                )
            ),
            "relation_count": int(
                inventory.get(
                    "relation_count",
                    0,
                )
            ),
            "profiled_primitive_count": int(
                quality.get(
                    "profiled_primitive_count",
                    0,
                )
            ),
            "profiled_relation_count": int(
                quality.get(
                    "profiled_relation_count",
                    0,
                )
            ),
            "quality_issue_count": int(
                quality.get(
                    "issue_count",
                    0,
                )
            ),
            "quality_safety_violation_count": int(
                quality.get(
                    "safety_violation_count",
                    0,
                )
            ),
        },
        "verification_state": {
            "task_metrics": task_metrics,
            "workflow_metrics": (workflow_metrics),
        },
        "bootstrap_state": {
            "candidate_count": int(
                bootstrap.get(
                    "candidate_count",
                    0,
                )
            ),
            "review_ready_count": int(
                bootstrap.get(
                    "review_ready_count",
                    0,
                )
            ),
            "blocked_review_count": int(
                bootstrap.get(
                    "blocked_review_count",
                    0,
                )
            ),
            "registration_execution_count": int(
                bootstrap.get(
                    "registration_execution_count",
                    0,
                )
            ),
            "human_approval_required": bool(bootstrap.get("human_approval_required")),
        },
        "browser_state": {
            "recipe_count": int(
                browser.get(
                    "recipe_count",
                    0,
                )
            ),
            "executable_count": (executable_browser_count),
            "design_pending_count": int(
                browser.get(
                    "design_pending_count",
                    0,
                )
            ),
        },
        "next_actions": [
            "Resolve the five authoritative client inputs.",
            "Review the exact bootstrap packets.",
            "Approve source-specific freshness and cadence.",
            "Complete one deterministic PlanTrak browser recipe.",
            "Begin shadow-mode outcome collection.",
            "Validate predictive usefulness before ranking.",
        ],
        "policy": EXPECTED_POLICY,
        "research_foundation_ready": (research_foundation_ready),
        "manual_verification_workflow_ready": (manual_workflow_ready),
        "pilot_execution_ready": (pilot_ready),
        "production_ranking_ready": False,
        "outreach_ready": False,
        "safety_counts_zero": (safety_counts_zero),
    }

    if write_contracts:
        contract_root = project_root / "docs" / "data_contracts"

        json_path = contract_root / "pilot_readiness_dossier.json"

        markdown_path = contract_root / "pilot_readiness_dossier.md"

        report["contract_paths"] = {
            "json": str(json_path.relative_to(project_root)),
            "markdown": str(markdown_path.relative_to(project_root)),
        }

        _atomic_json(
            json_path,
            report,
        )

        _atomic_text(
            markdown_path,
            _markdown(report),
        )

    return report
