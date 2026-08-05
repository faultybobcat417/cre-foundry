from __future__ import annotations

import json
from pathlib import Path

import duckdb

from cre_foundry.pilot_readiness import (
    build_pilot_readiness_dossier,
)


def _write_json(
    path: Path,
    payload: dict[str, object],
) -> None:
    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    path.write_text(
        json.dumps(payload),
        encoding="utf-8",
    )


def _project(
    tmp_path: Path,
) -> Path:
    config_root = tmp_path / "config"

    contract_root = tmp_path / "docs" / "data_contracts"

    warehouse_path = tmp_path / "data" / "warehouse" / "cre.duckdb"

    warehouse_path.parent.mkdir(parents=True)

    _write_json(
        config_root / "pilot_readiness.json",
        {
            "policy": {
                "operating_mode": "shadow",
                "read_only": True,
                "automatic_acquisition": False,
                "browser_execution": False,
                "computer_vision_execution": False,
                "automatic_conclusions": False,
                "opportunity_ranked": False,
                "outreach_eligible": False,
            },
            "required_client_inputs": [
                {
                    "input_id": "success",
                    "description": "Success definition.",
                    "provided": False,
                }
            ],
        },
    )

    contracts: dict[
        str,
        dict[str, object],
    ] = {
        "data_plane_readiness.json": {"ready": True},
        "source_runtime.json": {
            "ready": True,
            "configured_source_count": 1,
            "enabled_schedule_sources": [],
        },
        "source_acquisition_plan.json": {
            "automatic_execution_count": 0,
            "browser_execution_count": 0,
            "computer_vision_execution_count": 0,
            "plans": [
                {
                    "freshness_target_hours": None,
                    "maximum_staleness_hours": None,
                }
            ],
        },
        "browser_recipes.json": {
            "recipe_count": 1,
            "executable_count": 0,
            "design_pending_count": 1,
        },
        "primitive_inventory.json": {
            "inventory_ready": True,
            "primitive_count": 10,
            "relation_count": 2,
        },
        "primitive_quality_summary.json": {
            "profile_ready": True,
            "safety_ready": True,
            "profiled_primitive_count": 10,
            "profiled_relation_count": 2,
            "issue_count": 1,
            "safety_violation_count": 0,
        },
        "source_snapshot_bootstrap_review.json": {
            "candidate_count": 1,
            "review_ready_count": 1,
            "blocked_review_count": 0,
            "registration_execution_count": 0,
            "human_approval_required": True,
        },
    }

    for filename, payload in contracts.items():
        _write_json(
            contract_root / filename,
            payload,
        )

    connection = duckdb.connect(str(warehouse_path))

    try:
        connection.execute("CREATE SCHEMA control")

        connection.execute(
            """
            CREATE TABLE
                control.brampton_verification_task_state (
                    opportunity_ranked BOOLEAN,
                    outreach_eligible BOOLEAN
                )
            """
        )

        connection.execute(
            """
            INSERT INTO
                control.brampton_verification_task_state
            VALUES (
                FALSE,
                FALSE
            )
            """
        )

        connection.execute(
            """
            CREATE TABLE
                control.brampton_verification_workflow_state (
                    opportunity_ranked BOOLEAN,
                    outreach_eligible BOOLEAN
                )
            """
        )

        connection.execute(
            """
            INSERT INTO
                control.brampton_verification_workflow_state
            VALUES (
                FALSE,
                FALSE
            )
            """
        )

    finally:
        connection.close()

    return tmp_path


def test_foundation_ready_but_pilot_blocked(
    tmp_path: Path,
) -> None:
    project = _project(tmp_path)

    report = build_pilot_readiness_dossier(
        project,
        write_contracts=False,
    )

    assert report["research_foundation_ready"] is True

    assert report["manual_verification_workflow_ready"] is True

    assert report["missing_client_input_count"] == 1

    assert report["pilot_execution_ready"] is False

    assert report["production_ranking_ready"] is False

    assert report["outreach_ready"] is False


def test_safety_counts_remain_zero(
    tmp_path: Path,
) -> None:
    project = _project(tmp_path)

    report = build_pilot_readiness_dossier(
        project,
        write_contracts=False,
    )

    assert report["safety_counts_zero"] is True

    tasks = report["verification_state"]["task_metrics"]

    assert tasks["opportunity_ranked_true"] == 0

    assert tasks["outreach_eligible_true"] == 0


def test_execution_layers_remain_disabled(
    tmp_path: Path,
) -> None:
    project = _project(tmp_path)

    report = build_pilot_readiness_dossier(
        project,
        write_contracts=False,
    )

    assert report["capabilities"]["scheduled_acquisition"] == "disabled_pending_cadence"

    assert report["capabilities"]["browser_acquisition"] == "design_pending"

    assert report["capabilities"]["production_ranking"] == "disabled"

    assert report["capabilities"]["outreach"] == "disabled"
