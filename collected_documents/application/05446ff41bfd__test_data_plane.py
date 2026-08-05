from __future__ import annotations

import json
from pathlib import Path

import pytest

from cre_foundry.data_plane import (
    BRAMPTON_STAGE_SPECS,
    EXACT_STAGE_COMMANDS,
    StageSpec,
    _resolve_stage,
    build_data_plane_plan,
    discover_source_commands,
    run_data_plane,
)


def _create_project(
    tmp_path: Path,
) -> Path:
    cli_path = tmp_path / "src" / "cre_foundry" / "cli.py"

    cli_path.parent.mkdir(parents=True)

    command_names = [
        "build-brampton-permit-rules",
        "acquire-brampton-permits",
        "inspect-brampton-permits",
        "build-brampton-permit-silver",
        "build-brampton-permit-entity-bridge",
        "acquire-brampton-business-directory",
        "build-brampton-business-directory-silver",
        "build-brampton-permit-directory-bridge",
        "build-brampton-cross-source-reconciliation",
        "build-brampton-permit-opportunity-evidence",
        "build-brampton-permit-verification-plan",
        "initialize-brampton-verification-ledger",
        "project-brampton-verification-state",
    ]

    cli_text = "\n".join(
        (f'@source_app.command("{command}")\ndef command_{index}() -> None:\n    pass\n')
        for index, command in enumerate(command_names)
    )

    cli_path.write_text(
        cli_text,
        encoding="utf-8",
    )

    config_path = tmp_path / "config" / "data_plane.json"

    config_path.parent.mkdir(parents=True)

    config_path.write_text(
        json.dumps(
            {
                "config_version": ("test"),
                "minimum_free_disk_gib": 0,
                "default_stage_timeout_seconds": 60,
                "acquisition_retries": 2,
                "transform_retries": 1,
                "retry_base_seconds": 0,
                "default_pipeline": ("brampton_operational"),
                "policies": {
                    "operating_mode": "shadow",
                    "automatic_conclusions": False,
                    "opportunity_ranked": False,
                    "outreach_eligible": False,
                    "require_exclusive_lock": True,
                    "fail_fast": True,
                    "allow_partial_batch_success": False,
                },
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    return tmp_path


def test_discovers_source_commands(
    tmp_path: Path,
) -> None:
    project = _create_project(tmp_path)

    commands = discover_source_commands(project / "src" / "cre_foundry" / "cli.py")

    assert "acquire-brampton-permits" in commands

    assert "project-brampton-verification-state" in commands

    assert len(commands) == len(BRAMPTON_STAGE_SPECS)


def test_plan_skips_acquisition_by_default(
    tmp_path: Path,
) -> None:
    project = _create_project(tmp_path)

    plan = build_data_plane_plan(
        project,
        pipeline="brampton_operational",
        include_acquisition=False,
    )

    acquisition_stages = [stage for stage in plan["stages"] if stage["kind"] == "acquisition"]

    required_non_acquisition_stages = [
        stage for stage in plan["stages"] if (stage["kind"] != "acquisition" and stage["required"])
    ]

    optional_non_acquisition_stages = [
        stage
        for stage in plan["stages"]
        if (stage["kind"] != "acquisition" and not stage["required"])
    ]

    assert acquisition_stages

    assert all(not stage["enabled"] for stage in acquisition_stages)

    assert all(stage["enabled"] for stage in required_non_acquisition_stages)

    assert all(
        (stage["enabled"] or stage["command"] is None) for stage in optional_non_acquisition_stages
    )

    assert plan["policy"]["outreach_eligible"] is False

    assert plan["policy"]["opportunity_ranked"] is False


def test_dry_run_executes_no_commands(
    tmp_path: Path,
) -> None:
    project = _create_project(tmp_path)

    result = run_data_plane(
        project,
        pipeline="brampton_operational",
        include_acquisition=False,
        dry_run=True,
    )

    assert result["status"] == ("dry_run_complete")

    assert result["dry_run"] is True

    manifest_path = project / result["manifest_path"]

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    statuses = {item["status"] for item in manifest["stage_results"]}

    assert statuses == {
        "planned",
        "skipped",
    }

    assert manifest["policy"]["automatic_conclusions"] is False

    assert manifest["policy"]["outreach_eligible"] is False


def test_required_stage_rejects_fuzzy_command_match() -> None:
    spec = StageSpec(
        stage_id="synthetic_required_stage",
        kind="transform",
        required_tokens=(
            "synthetic",
            "required",
        ),
        preferred_tokens=(
            "build",
            "stage",
        ),
        aliases=("build-synthetic-required-stage",),
    )

    with pytest.raises(
        RuntimeError,
        match="No static command binding exists",
    ):
        _resolve_stage(
            spec,
            (
                "inspect-synthetic-required-stage",
                "build-synthetic-stage-like-command",
            ),
        )


def test_exact_stage_bindings_cover_required_pipeline() -> None:
    required_stage_ids = {spec.stage_id for spec in BRAMPTON_STAGE_SPECS if spec.required}

    assert required_stage_ids <= set(EXACT_STAGE_COMMANDS)

    assert EXACT_STAGE_COMMANDS["permit_lifecycle"] == "inspect-brampton-permits"

    lifecycle_spec = next(
        spec for spec in BRAMPTON_STAGE_SPECS if spec.stage_id == "permit_lifecycle"
    )

    assert lifecycle_spec.kind == "validation"
