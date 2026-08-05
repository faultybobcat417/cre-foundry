from __future__ import annotations

import json
import os
import tempfile
from collections import Counter
from pathlib import Path
from typing import Any, Final

BASE_POLICY: Final = {
    "operating_mode": "shadow",
    "expected_parameter_aware_count": 7,
    "source_modification_enabled": False,
    "automatic_rewrite_enabled": False,
    "automatic_suppression_enabled": False,
    "automatic_risk_acceptance_enabled": False,
    "database_access_enabled": False,
    "database_write_enabled": False,
    "snapshot_registration_enabled": False,
    "model_training_enabled": False,
    "pilot_execution_enabled": False,
    "production_ranking_enabled": False,
    "outreach_enabled": False,
    "exact_source_excerpt_required": True,
    "semantic_ast_identity_required": True,
    "test_reference_capture_required": True,
    "path_value_classification_required": True,
    "identifier_classification_required": True,
}


def _load_object(
    path: Path,
) -> dict[str, Any]:
    raw: object = json.loads(path.read_text(encoding="utf-8"))

    if not isinstance(raw, dict):
        raise RuntimeError(f"Expected JSON object: {path}")

    return {str(key): value for key, value in raw.items()}


def _object_list(
    value: object,
    *,
    label: str,
) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        raise RuntimeError(f"{label} must be a list.")

    rows: list[dict[str, Any]] = []

    for index, raw_row in enumerate(value):
        if not isinstance(raw_row, dict):
            raise RuntimeError(f"{label}[{index}] must be an object.")

        rows.append({str(key): row_value for key, row_value in raw_row.items()})

    return rows


def _required_string(
    row: dict[str, Any],
    field: str,
    *,
    label: str,
) -> str:
    value = row.get(field)

    if not isinstance(value, str) or not value:
        raise RuntimeError(f"{label}.{field} must be a non-empty string.")

    return value


def _classify_candidate(
    statement_source: str,
    dynamic_expressions: list[str],
) -> tuple[str, str]:
    upper = statement_source.upper()

    path_markers = (
        "READ_PARQUET",
        "READ_CSV",
        "READ_JSON",
        ".PARQUET",
        ".CSV",
        ".JSON",
    )

    if any(marker in upper for marker in path_markers):
        return (
            "path_value_candidate",
            (
                "Move each file path outside constructed SQL "
                "and bind it as a DuckDB value parameter or "
                "supply it through the typed relation API."
            ),
        )

    identifier_markers = (
        " FROM ",
        " INTO ",
        " TABLE ",
        "SELECT ",
        " JOIN ",
    )

    if dynamic_expressions and any(marker in upper for marker in identifier_markers):
        return (
            "identifier_candidate",
            (
                "Separate schema, table and column tokens from "
                "data values and route each token through the "
                "strict SQL identifier primitives."
            ),
        )

    return (
        "manual_query_shape_review",
        (
            "Inspect the complete statement and separate every "
            "identifier from every data value before selecting "
            "the canary migration."
        ),
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
                allow_nan=False,
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


def build_sql_safety_wave1a_plan(
    project_root: Path,
    *,
    write_contracts: bool = True,
) -> dict[str, Any]:
    config = _load_object(project_root / "config" / "sql_safety_wave1a_planner.json")

    if config.get("config_version") != ("cre-foundry-sql-safety-wave1a-planner-v1"):
        raise RuntimeError("Unsupported Wave 1A planner version.")

    policy_raw = config.get("policy")

    if not isinstance(policy_raw, dict):
        raise RuntimeError("Wave 1A planner policy must be an object.")

    policy = {str(key): value for key, value in policy_raw.items()}

    expected_count_raw = policy.get("expected_parameter_aware_count")

    if type(expected_count_raw) is not int or expected_count_raw <= 0 or expected_count_raw > 100:
        raise RuntimeError("expected_parameter_aware_count must be an integer between 1 and 100.")

    expected_policy = {
        **BASE_POLICY,
        "expected_parameter_aware_count": (expected_count_raw),
    }

    if policy != expected_policy:
        raise RuntimeError("Wave 1A planner policy mismatch.")

    input_path = project_root / str(config["input"])

    inventory = _load_object(input_path)

    inventory_rows = _object_list(
        inventory.get("items"),
        label="inventory items",
    )

    candidates = [
        row for row in inventory_rows if row.get("execute_parameter_binding_present") is True
    ]

    if len(candidates) != expected_count_raw:
        raise RuntimeError(
            "Parameter-aware candidate count mismatch. "
            f"Expected={expected_count_raw}, "
            f"actual={len(candidates)}"
        )

    plan_rows: list[dict[str, Any]] = []

    for index, row in enumerate(
        sorted(
            candidates,
            key=lambda item: (
                str(
                    item.get(
                        "source_path",
                        "",
                    )
                ),
                int(
                    item.get(
                        "line_number",
                        0,
                    )
                ),
            ),
        )
    ):
        label = f"candidate[{index}]"

        source_path = _required_string(
            row,
            "source_path",
            label=label,
        )

        enclosing_scope = _required_string(
            row,
            "enclosing_scope",
            label=label,
        )

        query_kind = _required_string(
            row,
            "query_kind",
            label=label,
        )

        ast_digest = _required_string(
            row,
            "statement_ast_sha256",
            label=label,
        )

        statement_source = _required_string(
            row,
            "statement_source",
            label=label,
        )

        source_excerpt = _required_string(
            row,
            "source_excerpt",
            label=label,
        )

        line_number = row.get("line_number")

        if type(line_number) is not int or line_number <= 0:
            raise RuntimeError(f"{label}.line_number is invalid.")

        raw_dynamic = row.get("dynamic_expressions")

        if not isinstance(raw_dynamic, list):
            raise RuntimeError(f"{label}.dynamic_expressions must be a list.")

        dynamic_expressions = [str(value) for value in raw_dynamic]

        raw_tests = row.get("test_references")

        if not isinstance(raw_tests, list):
            raise RuntimeError(f"{label}.test_references must be a list.")

        test_references = [str(value) for value in raw_tests]

        classification, strategy = _classify_candidate(
            statement_source,
            dynamic_expressions,
        )

        plan_rows.append(
            {
                "sequence": index + 1,
                "source_path": source_path,
                "line_number": line_number,
                "location": (f"{source_path}:{line_number}"),
                "enclosing_scope": enclosing_scope,
                "query_kind": query_kind,
                "classification": classification,
                "recommended_strategy": strategy,
                "statement_ast_sha256": ast_digest,
                "dynamic_expressions": (dynamic_expressions),
                "test_references": (test_references),
                "test_reference_count": len(test_references),
                "statement_source": (statement_source),
                "source_excerpt": (source_excerpt),
                "source_modification_performed": False,
                "automatic_rewrite_performed": False,
                "automatic_suppression_performed": False,
                "automatic_risk_acceptance_performed": False,
                "database_access_performed": False,
                "database_write_performed": False,
            }
        )

    classification_counts = Counter(str(row["classification"]) for row in plan_rows)

    affected_files = sorted({str(row["source_path"]) for row in plan_rows})

    plan = {
        "model_version": ("cre-foundry-sql-safety-wave1a-plan-v1"),
        "operating_mode": "shadow",
        "parameter_aware_candidate_count": len(plan_rows),
        "affected_file_count": len(affected_files),
        "affected_files": affected_files,
        "classification_counts": dict(sorted(classification_counts.items())),
        "candidates": plan_rows,
        "source_modification_count": 0,
        "automatic_rewrite_count": 0,
        "automatic_suppression_count": 0,
        "automatic_risk_acceptance_count": 0,
        "database_access_count": 0,
        "database_write_count": 0,
        "snapshot_registration_count": 0,
        "model_training_execution_count": 0,
        "pilot_execution_count": 0,
        "production_ranking_execution_count": 0,
        "outreach_execution_count": 0,
        "ready_for_surgical_migration": True,
        "next_checkpoint": ("sql-safety-wave1a-canary-migration"),
    }

    if write_contracts:
        outputs = config.get("outputs")

        if not isinstance(outputs, dict):
            raise RuntimeError("Wave 1A outputs must be an object.")

        plan_path = project_root / str(outputs["plan"])

        report_path = project_root / str(outputs["report"])

        _atomic_json(
            plan_path,
            plan,
        )

        markdown = [
            "# SQL Safety Wave 1A Migration Plan",
            "",
            (
                "This plan isolates the seven B608 call sites "
                "that already use database parameters elsewhere "
                "in the same statement."
            ),
            "",
            (f"- Candidates: `{plan['parameter_aware_candidate_count']}`"),
            (f"- Affected files: `{plan['affected_file_count']}`"),
            "- Source modifications: `0`",
            "- Automatic rewrites: `0`",
            "- Suppressions: `0`",
            "- Risk acceptances: `0`",
            "",
            "## Exact queue",
            "",
        ]

        for row in plan_rows:
            markdown.extend(
                [
                    (f"### {row['sequence']}. {row['location']}"),
                    "",
                    (f"- Scope: `{row['enclosing_scope']}`"),
                    (f"- Classification: `{row['classification']}`"),
                    (f"- Query kind: `{row['query_kind']}`"),
                    (f"- AST digest: `{row['statement_ast_sha256']}`"),
                    (f"- Test references: `{row['test_reference_count']}`"),
                    "",
                    str(row["recommended_strategy"]),
                    "",
                    "```python",
                    str(row["statement_source"]),
                    "```",
                    "",
                ]
            )

        _atomic_text(
            report_path,
            "\n".join(markdown).rstrip() + "\n",
        )

    return plan
