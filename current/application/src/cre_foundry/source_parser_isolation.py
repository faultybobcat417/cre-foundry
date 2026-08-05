from __future__ import annotations

import ast
import json
import os
import sqlite3
import tempfile
from pathlib import Path
from typing import Any, NoReturn
from unittest import mock

import duckdb

from cre_foundry.source_parser_contracts import (
    build_source_parser_contracts,
)

FORBIDDEN_IMPORT_ROOTS = {
    "sqlite3",
    "duckdb",
    "sqlalchemy",
}

FORBIDDEN_LITERAL_FRAGMENTS = {
    "operations.sqlite3",
    "shadow_learning.sqlite3",
    "cre.duckdb",
    "data/control/",
    "data/warehouse/",
}

AUTHORITATIVE_DATABASE_PATHS = (
    "data/warehouse/cre.duckdb",
    "data/control/operations.sqlite3",
    "data/control/shadow_learning.sqlite3",
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


def _scan_parser_source(
    source_path: Path,
) -> dict[str, Any]:
    text = source_path.read_text(encoding="utf-8")

    tree = ast.parse(text)

    imported_roots: set[str] = set()
    forbidden_literals: set[str] = set()

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imported_roots.add(
                    alias.name.split(
                        ".",
                        maxsplit=1,
                    )[0]
                )

        elif isinstance(node, ast.ImportFrom):
            if node.module:
                imported_roots.add(
                    node.module.split(
                        ".",
                        maxsplit=1,
                    )[0]
                )

        elif isinstance(node, ast.Constant) and isinstance(node.value, str):
            for fragment in FORBIDDEN_LITERAL_FRAGMENTS:
                if fragment in node.value:
                    forbidden_literals.add(fragment)

    forbidden_imports = sorted(imported_roots & FORBIDDEN_IMPORT_ROOTS)

    return {
        "source_path": str(source_path),
        "imported_roots": sorted(imported_roots),
        "forbidden_imports": (forbidden_imports),
        "forbidden_database_literals": sorted(forbidden_literals),
        "static_isolation_passed": (not forbidden_imports and not forbidden_literals),
    }


def _validate_artifact_boundaries(
    project_root: Path,
) -> dict[str, Any]:
    config = _load_object(project_root / "config" / "source_parser_contracts.json")

    raw_contracts = config.get("contracts")

    if not isinstance(raw_contracts, list):
        raise RuntimeError("Parser contracts must be a list.")

    database_paths = {
        (project_root / relative_path).resolve(strict=False)
        for relative_path in AUTHORITATIVE_DATABASE_PATHS
    }

    contract_rows: list[dict[str, Any]] = []
    violations: list[str] = []

    for raw_contract in raw_contracts:
        if not isinstance(raw_contract, dict):
            raise RuntimeError("Parser contract must be an object.")

        source_id = raw_contract.get("source_id")

        artifact_path = raw_contract.get("artifact_path")

        if not isinstance(source_id, str) or not isinstance(
            artifact_path,
            str,
        ):
            raise RuntimeError("Parser contract identity is malformed.")

        resolved = (project_root / artifact_path).resolve(strict=False)

        bronze_relative = False

        try:
            relative = resolved.relative_to(
                (project_root / "data" / "bronze").resolve(strict=False)
            )

            bronze_relative = bool(relative.parts)

        except ValueError:
            bronze_relative = False

        is_database_path = resolved in database_paths

        suffix_blocked = resolved.suffix.lower() in {
            ".sqlite",
            ".sqlite3",
            ".db",
            ".duckdb",
        }

        row_violations: list[str] = []

        if not bronze_relative:
            row_violations.append("artifact_outside_bronze")

        if is_database_path:
            row_violations.append("artifact_is_authoritative_database")

        if suffix_blocked:
            row_violations.append("database_suffix_forbidden")

        if row_violations:
            violations.extend(f"{source_id}:{value}" for value in row_violations)

        contract_rows.append(
            {
                "source_id": source_id,
                "artifact_path": artifact_path,
                "inside_bronze": bronze_relative,
                "authoritative_database_path": (is_database_path),
                "database_suffix_forbidden": (suffix_blocked),
                "violations": row_violations,
            }
        )

    return {
        "contract_count": len(contract_rows),
        "contracts": contract_rows,
        "boundary_violations": sorted(violations),
        "artifact_boundary_passed": (not violations),
    }


def _blocked_database_connect(
    *_args: object,
    **_kwargs: object,
) -> NoReturn:
    raise RuntimeError("Parser attempted an authoritative database connection.")


def build_source_parser_isolation(
    project_root: Path,
    *,
    write_contracts: bool = True,
) -> dict[str, Any]:
    source_path = project_root / "src" / "cre_foundry" / "source_parser_contracts.py"

    static_scan = _scan_parser_source(source_path)

    boundary_scan = _validate_artifact_boundaries(project_root)

    if not static_scan["static_isolation_passed"]:
        raise RuntimeError("Parser source contains forbidden database dependencies.")

    if not boundary_scan["artifact_boundary_passed"]:
        raise RuntimeError("Parser artifact boundaries failed.")

    with (
        mock.patch.object(
            sqlite3,
            "connect",
            side_effect=(_blocked_database_connect),
        ),
        mock.patch.object(
            duckdb,
            "connect",
            side_effect=(_blocked_database_connect),
        ),
    ):
        parser_result = build_source_parser_contracts(
            project_root,
            write_contracts=False,
        )

    validation = parser_result["validation"]

    runtime_guard_passed = (
        validation["contract_count"] == 3
        and validation["validation_complete_count"] == 3
        and validation["reproducibility_match_count"] == 3
        and validation["parser_execution_count"] == 6
    )

    if not runtime_guard_passed:
        raise RuntimeError("Parser validation failed while database APIs were blocked.")

    report: dict[str, Any] = {
        "model_version": ("cre-foundry-source-parser-isolation-v1"),
        "static_scan": static_scan,
        "artifact_boundary_scan": (boundary_scan),
        "sqlite_connection_api_blocked": True,
        "duckdb_connection_api_blocked": True,
        "runtime_guard_passed": (runtime_guard_passed),
        "validated_contract_count": (validation["validation_complete_count"]),
        "reproducibility_match_count": (validation["reproducibility_match_count"]),
        "guarded_parser_execution_count": (validation["parser_execution_count"]),
        "authoritative_database_connection_count": 0,
        "authoritative_database_write_count": 0,
        "snapshot_registration_count": 0,
        "parser_contract_approval_count": 0,
        "schema_contract_approval_count": 0,
        "model_training_execution_count": 0,
        "production_ranking_execution_count": 0,
        "outreach_execution_count": 0,
    }

    if write_contracts:
        contract_root = project_root / "docs" / "data_contracts"

        _atomic_json(
            contract_root / "source_parser_isolation.json",
            report,
        )

        _atomic_text(
            contract_root / "source_parser_isolation.md",
            "\n".join(
                [
                    "# Source Parser Isolation",
                    "",
                    (
                        "The source parser is statically and "
                        "dynamically isolated from authoritative "
                        "SQLite and DuckDB connections."
                    ),
                    "",
                    (
                        f"- Static isolation: "
                        f"`{str(static_scan['static_isolation_passed']).lower()}`"
                    ),
                    (
                        f"- Artifact boundary isolation: "
                        f"`{str(boundary_scan['artifact_boundary_passed']).lower()}`"
                    ),
                    (f"- Guarded parser runs: `{report['guarded_parser_execution_count']}`"),
                    (f"- Validated contracts: `{report['validated_contract_count']}`"),
                    "",
                    "- Database connections: `0`",
                    "- Database writes: `0`",
                    "- Snapshot registrations: `0`",
                    "- Automatic approvals: `0`",
                    "",
                ]
            ),
        )

    return report
