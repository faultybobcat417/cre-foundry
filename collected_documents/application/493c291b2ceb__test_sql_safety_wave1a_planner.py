from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from cre_foundry.sql_safety_wave1a_planner import (
    BASE_POLICY,
    build_sql_safety_wave1a_plan,
)


def _write_json(
    path: Path,
    payload: object,
) -> None:
    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    path.write_text(
        json.dumps(
            payload,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )


def _project(
    tmp_path: Path,
    *,
    include_candidate: bool = True,
) -> Path:
    policy = {
        **BASE_POLICY,
        "expected_parameter_aware_count": 1,
    }

    _write_json(
        tmp_path / "config" / "sql_safety_wave1a_planner.json",
        {
            "config_version": ("cre-foundry-sql-safety-wave1a-planner-v1"),
            "policy": policy,
            "input": ("docs/security/sql_safety_remediation_inventory.json"),
            "outputs": {
                "plan": ("docs/security/sql_safety_wave1a_plan.json"),
                "report": ("docs/security/sql_safety_wave1a_plan.md"),
            },
        },
    )

    rows: list[dict[str, object]] = []

    if include_candidate:
        rows.append(
            {
                "source_path": ("src/cre_foundry/example.py"),
                "line_number": 25,
                "enclosing_scope": "load_file",
                "query_kind": ("parquet_path_ingestion"),
                "statement_ast_sha256": (hashlib.sha256(b"statement").hexdigest()),
                "statement_source": (
                    "connection.execute(f\"SELECT * FROM read_parquet('{path}')\", [limit])"
                ),
                "source_excerpt": ("> 00025: connection.execute(...)"),
                "dynamic_expressions": ["path"],
                "test_references": ["tests/unit/test_example.py"],
                "execute_parameter_binding_present": True,
            }
        )

    rows.append(
        {
            "source_path": ("src/cre_foundry/other.py"),
            "line_number": 40,
            "enclosing_scope": "other",
            "query_kind": ("dynamic_relation_count"),
            "statement_ast_sha256": (hashlib.sha256(b"other").hexdigest()),
            "statement_source": ("connection.execute(query)"),
            "source_excerpt": ("> 00040: connection.execute(query)"),
            "dynamic_expressions": [],
            "test_references": [],
            "execute_parameter_binding_present": False,
        }
    )

    _write_json(
        tmp_path / "docs" / "security" / "sql_safety_remediation_inventory.json",
        {"items": rows},
    )

    return tmp_path


def test_planner_selects_only_parameter_aware_candidates(
    tmp_path: Path,
) -> None:
    project = _project(tmp_path)

    result = build_sql_safety_wave1a_plan(
        project,
        write_contracts=True,
    )

    assert result["parameter_aware_candidate_count"] == 1

    assert result["candidates"][0]["classification"] == "path_value_candidate"

    assert result["source_modification_count"] == 0

    assert result["automatic_suppression_count"] == 0


def test_planner_is_deterministic(
    tmp_path: Path,
) -> None:
    project = _project(tmp_path)

    first = build_sql_safety_wave1a_plan(
        project,
        write_contracts=True,
    )

    plan_path = project / "docs" / "security" / "sql_safety_wave1a_plan.json"

    first_bytes = plan_path.read_bytes()

    second = build_sql_safety_wave1a_plan(
        project,
        write_contracts=True,
    )

    second_bytes = plan_path.read_bytes()

    assert first == second
    assert first_bytes == second_bytes


def test_policy_drift_is_rejected(
    tmp_path: Path,
) -> None:
    project = _project(tmp_path)

    config_path = project / "config" / "sql_safety_wave1a_planner.json"

    document = json.loads(config_path.read_text(encoding="utf-8"))

    document["policy"]["automatic_rewrite_enabled"] = True

    _write_json(
        config_path,
        document,
    )

    with pytest.raises(
        RuntimeError,
        match="policy mismatch",
    ):
        build_sql_safety_wave1a_plan(
            project,
            write_contracts=False,
        )


@pytest.mark.parametrize(
    "invalid_count",
    [
        True,
        False,
        0,
        -1,
        101,
        "1",
        1.0,
        None,
    ],
)
def test_invalid_candidate_count_is_rejected(
    tmp_path: Path,
    invalid_count: object,
) -> None:
    project = _project(tmp_path)

    config_path = project / "config" / "sql_safety_wave1a_planner.json"

    document = json.loads(config_path.read_text(encoding="utf-8"))

    document["policy"]["expected_parameter_aware_count"] = invalid_count

    _write_json(
        config_path,
        document,
    )

    with pytest.raises(
        RuntimeError,
        match=("expected_parameter_aware_count must be an integer"),
    ):
        build_sql_safety_wave1a_plan(
            project,
            write_contracts=False,
        )


def test_candidate_count_mismatch_is_rejected(
    tmp_path: Path,
) -> None:
    project = _project(
        tmp_path,
        include_candidate=False,
    )

    with pytest.raises(
        RuntimeError,
        match="candidate count mismatch",
    ):
        build_sql_safety_wave1a_plan(
            project,
            write_contracts=False,
        )
