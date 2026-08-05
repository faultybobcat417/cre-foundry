from __future__ import annotations

import ast
import hashlib
import json
import os
import re
import tempfile
from collections import Counter
from pathlib import Path
from typing import Any

EXPECTED_POLICY: dict[str, Any] = {
    "operating_mode": "shadow",
    "expected_blocking_b608_count": 20,
    "automatic_source_rewrite_enabled": False,
    "automatic_suppression_enabled": False,
    "automatic_risk_acceptance_enabled": False,
    "value_parameterization_required": True,
    "file_path_parameterization_required": True,
    "strict_identifier_validation_required": True,
    "strict_identifier_quoting_required": True,
    "source_digest_binding_required": True,
    "statement_digest_binding_required": True,
    "enclosing_scope_capture_required": True,
    "test_coverage_discovery_required": True,
    "secret_noise_profiling_required": True,
    "license_review_profiling_required": True,
    "raw_secret_persistence_forbidden": True,
    "database_access_enabled": False,
    "database_write_enabled": False,
    "snapshot_registration_enabled": False,
    "automatic_acquisition_enabled": False,
    "persistent_outcome_ledger_enabled": False,
    "outcome_event_insertion_enabled": False,
    "point_in_time_materialization_enabled": False,
    "model_training_enabled": False,
    "backtest_execution_enabled": False,
    "pilot_execution_enabled": False,
    "production_ranking_enabled": False,
    "outreach_enabled": False,
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


def _load_object(
    path: Path,
) -> dict[str, Any]:
    raw: object = json.loads(path.read_text(encoding="utf-8"))

    if not isinstance(raw, dict):
        raise RuntimeError(f"Expected JSON object: {path}")

    return {str(key): value for key, value in raw.items()}


def _sha256_text(
    value: str,
) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _safe_source_path(
    project_root: Path,
    relative_path: str,
) -> Path:
    root = project_root.resolve()
    candidate = (project_root / relative_path).resolve()

    try:
        candidate.relative_to(root)

    except ValueError as error:
        raise RuntimeError(f"Finding source path escapes project root: {relative_path}") from error

    if not candidate.is_file():
        raise RuntimeError(f"Finding source file is missing: {relative_path}")

    return candidate


def _parse_location(
    location: object,
) -> tuple[str, int]:
    if not isinstance(location, str):
        raise RuntimeError("B608 finding location must be a string.")

    path_text, separator, line_text = location.rpartition(":")

    if not separator or not path_text:
        raise RuntimeError(f"Invalid B608 location: {location}")

    try:
        line_number = int(line_text)

    except ValueError as error:
        raise RuntimeError(f"Invalid B608 line number: {location}") from error

    if line_number <= 0:
        raise RuntimeError(f"Invalid B608 line number: {location}")

    return path_text, line_number


def _node_contains_line(
    node: ast.AST,
    line_number: int,
) -> bool:
    start = getattr(
        node,
        "lineno",
        None,
    )

    end = getattr(
        node,
        "end_lineno",
        None,
    )

    return bool(isinstance(start, int) and isinstance(end, int) and start <= line_number <= end)


def _smallest_containing_node(
    tree: ast.AST,
    line_number: int,
    node_types: tuple[type[ast.AST], ...],
) -> ast.AST | None:
    candidates: list[ast.AST] = []

    for node in ast.walk(tree):
        if not isinstance(
            node,
            node_types,
        ):
            continue

        if _node_contains_line(
            node,
            line_number,
        ):
            candidates.append(node)

    if not candidates:
        return None

    return min(
        candidates,
        key=lambda node: (
            int(
                getattr(
                    node,
                    "end_lineno",
                    line_number,
                )
            )
            - int(
                getattr(
                    node,
                    "lineno",
                    line_number,
                )
            ),
            int(
                getattr(
                    node,
                    "lineno",
                    line_number,
                )
            ),
        ),
    )


def _scope_name(
    scope: ast.AST | None,
) -> str:
    if isinstance(
        scope,
        (
            ast.FunctionDef,
            ast.AsyncFunctionDef,
            ast.ClassDef,
        ),
    ):
        return scope.name

    return "<module>"


def _source_segment(
    source_text: str,
    node: ast.AST | None,
) -> str:
    if node is None:
        return ""

    segment = ast.get_source_segment(
        source_text,
        node,
    )

    return segment or ""


def _source_excerpt(
    source_lines: list[str],
    line_number: int,
    *,
    radius: int = 6,
) -> str:
    start = max(
        1,
        line_number - radius,
    )

    end = min(
        len(source_lines),
        line_number + radius,
    )

    rendered: list[str] = []

    for current in range(
        start,
        end + 1,
    ):
        marker = ">" if current == line_number else " "

        rendered.append(f"{marker} {current:05d}: {source_lines[current - 1]}")

    return "\n".join(rendered)


def _dynamic_expressions(
    statement: ast.AST | None,
) -> list[str]:
    if statement is None:
        return []

    expressions: set[str] = set()

    for node in ast.walk(statement):
        if isinstance(
            node,
            ast.FormattedValue,
        ):
            expressions.add(ast.unparse(node.value))

        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
            for operand in (
                node.left,
                node.right,
            ):
                if not isinstance(
                    operand,
                    ast.Constant,
                ):
                    expressions.add(ast.unparse(operand))

        if (
            isinstance(node, ast.Call)
            and isinstance(
                node.func,
                ast.Attribute,
            )
            and node.func.attr
            in {
                "format",
                "join",
            }
        ):
            for argument in node.args:
                expressions.add(ast.unparse(argument))

    return sorted(expression for expression in expressions if expression)


def _execute_parameter_binding_present(
    statement: ast.AST | None,
) -> bool:
    if statement is None:
        return False

    for node in ast.walk(statement):
        if not isinstance(
            node,
            ast.Call,
        ):
            continue

        if not isinstance(
            node.func,
            ast.Attribute,
        ):
            continue

        if node.func.attr not in {
            "execute",
            "executemany",
        }:
            continue

        if len(node.args) >= 2:
            return True

        if any(
            keyword.arg
            in {
                "parameters",
                "params",
            }
            for keyword in node.keywords
        ):
            return True

    return False


def _query_kind(
    statement_source: str,
) -> str:
    upper = statement_source.upper()

    if "READ_PARQUET" in upper:
        return "parquet_path_ingestion"

    if "INSERT INTO" in upper:
        return "dynamic_insert"

    if "SELECT DISTINCT" in upper:
        return "dynamic_distinct_projection"

    if "COUNT(*)" in upper:
        return "dynamic_relation_count"

    if "CREATE OR REPLACE TABLE" in upper:
        return "dynamic_table_materialization"

    if "SELECT" in upper:
        return "dynamic_projection_or_relation"

    return "other_dynamic_sql"


def _remediation_wave(
    query_kind: str,
) -> int:
    if query_kind == "parquet_path_ingestion":
        return 1

    if query_kind in {
        "dynamic_relation_count",
        "dynamic_table_materialization",
    }:
        return 2

    if query_kind in {
        "dynamic_insert",
        "dynamic_distinct_projection",
        "dynamic_projection_or_relation",
    }:
        return 3

    return 4


def _proposed_control(
    query_kind: str,
) -> str:
    controls = {
        "parquet_path_ingestion": (
            "Bind the file path as a DuckDB value parameter "
            "or use the Python read_parquet relation API; keep "
            "the destination identifier fixed or strictly validated."
        ),
        "dynamic_relation_count": (
            "Route the relation through a strict qualified-identifier "
            "validator and quoting function before SQL construction."
        ),
        "dynamic_table_materialization": (
            "Separate the fixed SQL structure from validated identifiers "
            "and parameter-bound file or data values."
        ),
        "dynamic_insert": (
            "Validate and quote table and column identifiers; bind every "
            "row value through execute parameters."
        ),
        "dynamic_distinct_projection": (
            "Validate and quote relation and column identifiers; keep "
            "LIMIT and filter values parameter-bound."
        ),
        "dynamic_projection_or_relation": (
            "Construct only validated identifier tokens; bind all data values separately."
        ),
        "other_dynamic_sql": (
            "Perform manual query-shape review before selecting a "
            "parameterization or identifier-control strategy."
        ),
    }

    return controls[query_kind]


def _identifier_safety_signals(
    scope_source: str,
) -> list[str]:
    patterns = {
        "quote_identifier_helper": (r"\bquote(?:d)?_identifier\b"),
        "qualified_identifier_helper": (r"\bqualified_identifier\b"),
        "identifier_allowlist": (r"\ballow(?:ed|list)\b"),
        "identifier_regular_expression": (r"(?:re\.fullmatch|fullmatch\()"),
        "manual_double_quote_escaping": (r'replace\(\s*[\'"]"[\'"]'),
    }

    signals: list[str] = []

    for signal, pattern in patterns.items():
        if re.search(
            pattern,
            scope_source,
            flags=re.IGNORECASE,
        ):
            signals.append(signal)

    return sorted(signals)


def _test_references(
    project_root: Path,
    *,
    source_path: str,
    scope_name: str,
) -> list[str]:
    tests_root = project_root / "tests"

    if not tests_root.is_dir():
        return []

    source_stem = Path(source_path).stem

    references: list[str] = []

    for path in sorted(tests_root.rglob("*.py")):
        try:
            text = path.read_text(encoding="utf-8")

        except UnicodeDecodeError:
            continue

        if source_stem in text or (scope_name != "<module>" and scope_name in text):
            references.append(str(path.relative_to(project_root)))

    return references[:25]


def _path_bucket(
    location: object,
) -> str:
    if not isinstance(location, str):
        return "unknown"

    path_text = location.rpartition(":")[0]

    if not path_text:
        path_text = location

    parts = Path(path_text).parts

    if not parts:
        return "unknown"

    if len(parts) >= 2:
        return "/".join(parts[:2])

    return parts[0]


def _build_secret_noise_profile(
    findings: list[dict[str, Any]],
) -> dict[str, Any]:
    secret_findings = [
        finding for finding in findings if finding.get("category") == "secret_worktree"
    ]

    detector_counts = Counter(
        str(
            finding.get(
                "advisory_id",
                "unknown",
            )
        )
        for finding in secret_findings
    )

    path_counts = Counter(_path_bucket(finding.get("location")) for finding in secret_findings)

    likely_digest_artifacts = [
        finding
        for finding in secret_findings
        if (
            finding.get("advisory_id") == "Hex High Entropy String"
            and _path_bucket(finding.get("location"))
            in {
                "docs/data_contracts",
                "docs/source_access",
                "outputs/brampton_verification_review_packets",
                "outputs/source_snapshot_bootstrap_review",
            }
        )
    ]

    blocking = [finding for finding in secret_findings if finding.get("blocking_by_policy") is True]

    return {
        "model_version": ("cre-foundry-secret-noise-profile-v1"),
        "secret_finding_count": len(secret_findings),
        "blocking_secret_finding_count": len(blocking),
        "likely_digest_artifact_count": len(likely_digest_artifacts),
        "detector_counts": dict(sorted(detector_counts.items())),
        "path_bucket_counts": dict(sorted(path_counts.items())),
        "raw_secret_value_count": 0,
        "automatic_exclusion_count": 0,
        "automatic_suppression_count": 0,
        "review_required": True,
    }


def _build_license_review_profile(
    findings: list[dict[str, Any]],
) -> dict[str, Any]:
    license_findings = [
        finding for finding in findings if finding.get("category") == "license_risk"
    ]

    prohibited = [
        finding for finding in license_findings if finding.get("blocking_by_policy") is True
    ]

    review_rows = [
        {
            "component": finding.get("component"),
            "title": finding.get("title"),
            "fingerprint": finding.get("finding_fingerprint"),
            "metadata": finding.get("metadata"),
        }
        for finding in license_findings
        if finding.get("blocking_by_policy") is not True
    ]

    return {
        "model_version": ("cre-foundry-license-review-profile-v1"),
        "license_finding_count": len(license_findings),
        "prohibited_license_count": len(prohibited),
        "review_license_count": len(review_rows),
        "review_items": review_rows,
        "automatic_approval_count": 0,
        "automatic_suppression_count": 0,
    }


def build_sql_safety_remediation_inventory(
    project_root: Path,
    *,
    write_contracts: bool = True,
) -> dict[str, Any]:
    config = _load_object(project_root / "config" / "sql_safety_remediation_inventory.json")

    policy_raw = config.get("policy")

    if not isinstance(
        policy_raw,
        dict,
    ):
        raise RuntimeError("SQL-safety policy must be an object.")

    policy = {str(key): value for key, value in policy_raw.items()}

    expected_count_raw = policy.get("expected_blocking_b608_count")

    if type(expected_count_raw) is not int or expected_count_raw <= 0 or expected_count_raw > 10000:
        raise RuntimeError("expected_blocking_b608_count must be an integer between 1 and 10000.")

    expected_policy = {
        **EXPECTED_POLICY,
        "expected_blocking_b608_count": (expected_count_raw),
    }

    if policy != expected_policy:
        raise RuntimeError("SQL-safety policy mismatch.")

    inputs = config.get("inputs")

    outputs = config.get("outputs")

    if not isinstance(inputs, dict):
        raise RuntimeError("SQL-safety inputs must be an object.")

    if not isinstance(outputs, dict):
        raise RuntimeError("SQL-safety outputs must be an object.")

    normalized = _load_object(project_root / str(inputs["normalized_findings"]))

    scanner_summary = _load_object(project_root / str(inputs["scanner_summary"]))

    raw_findings = normalized.get("findings")

    if not isinstance(
        raw_findings,
        list,
    ):
        raise RuntimeError("Normalized findings must be a list.")

    findings: list[dict[str, Any]] = []

    for index, raw_finding in enumerate(raw_findings):
        if not isinstance(
            raw_finding,
            dict,
        ):
            raise RuntimeError(f"Finding {index} must be an object.")

        findings.append({str(key): value for key, value in raw_finding.items()})

    blocking_b608 = [
        finding
        for finding in findings
        if (
            finding.get("scanner") == "bandit"
            and finding.get("advisory_id") == "B608"
            and finding.get("blocking_by_policy") is True
            and finding.get("suppressed") is not True
        )
    ]

    expected_count = int(policy["expected_blocking_b608_count"])

    if len(blocking_b608) != expected_count:
        raise RuntimeError(
            f"Blocking B608 count mismatch. Expected={expected_count}, actual={len(blocking_b608)}"
        )

    inventory_rows: list[dict[str, Any]] = []

    for finding in sorted(
        blocking_b608,
        key=lambda row: (
            str(
                row.get(
                    "location",
                    "",
                )
            ),
            str(
                row.get(
                    "finding_fingerprint",
                    "",
                )
            ),
        ),
    ):
        relative_path, line_number = _parse_location(finding.get("location"))

        source_path = _safe_source_path(
            project_root,
            relative_path,
        )

        source_text = source_path.read_text(encoding="utf-8")

        source_lines = source_text.splitlines()

        tree = ast.parse(
            source_text,
            filename=relative_path,
        )

        scope = _smallest_containing_node(
            tree,
            line_number,
            (
                ast.FunctionDef,
                ast.AsyncFunctionDef,
                ast.ClassDef,
            ),
        )

        statement = _smallest_containing_node(
            tree,
            line_number,
            (ast.stmt,),
        )

        scope_source = _source_segment(
            source_text,
            scope,
        )

        statement_source = _source_segment(
            source_text,
            statement,
        )

        if not statement_source:
            statement_source = _source_excerpt(
                source_lines,
                line_number,
                radius=2,
            )

        query_kind = _query_kind(statement_source)

        dynamic_expressions = _dynamic_expressions(statement)

        signals = _identifier_safety_signals(scope_source)

        scope_name = _scope_name(scope)

        test_references = _test_references(
            project_root,
            source_path=relative_path,
            scope_name=scope_name,
        )

        wave = _remediation_wave(query_kind)

        priority = "critical-review" if not signals and dynamic_expressions else "high-review"

        inventory_rows.append(
            {
                "finding_fingerprint": finding.get("finding_fingerprint"),
                "scanner": finding.get("scanner"),
                "advisory_id": finding.get("advisory_id"),
                "title": finding.get("title"),
                "source_path": relative_path,
                "line_number": line_number,
                "enclosing_scope": scope_name,
                "query_kind": query_kind,
                "remediation_wave": wave,
                "review_priority": priority,
                "proposed_control": _proposed_control(query_kind),
                "dynamic_expressions": dynamic_expressions,
                "dynamic_expression_count": len(dynamic_expressions),
                "execute_parameter_binding_present": _execute_parameter_binding_present(statement),
                "identifier_safety_signals": signals,
                "identifier_safety_signal_count": len(signals),
                "source_sha256": _sha256_text(source_text),
                "statement_sha256": _sha256_text(statement_source),
                "statement_ast_sha256": _sha256_text(
                    ast.dump(statement, annotate_fields=True, include_attributes=False)
                    if statement is not None
                    else statement_source
                ),
                "statement_source": statement_source,
                "source_excerpt": _source_excerpt(source_lines, line_number),
                "test_references": test_references,
                "test_reference_count": len(test_references),
                "automatic_rewrite_performed": False,
                "automatic_suppression_performed": False,
                "database_access_performed": False,
                "database_write_performed": False,
            }
        )

    file_counts = Counter(str(row["source_path"]) for row in inventory_rows)

    kind_counts = Counter(str(row["query_kind"]) for row in inventory_rows)

    wave_counts = Counter(str(row["remediation_wave"]) for row in inventory_rows)

    inventory = {
        "model_version": ("cre-foundry-sql-safety-remediation-inventory-v1"),
        "blocking_b608_count": len(inventory_rows),
        "affected_file_count": len(file_counts),
        "affected_scope_count": len(
            {
                (
                    str(row["source_path"]),
                    str(row["enclosing_scope"]),
                )
                for row in inventory_rows
            }
        ),
        "file_counts": dict(sorted(file_counts.items())),
        "query_kind_counts": dict(sorted(kind_counts.items())),
        "remediation_wave_counts": dict(sorted(wave_counts.items())),
        "items": inventory_rows,
    }

    secret_noise = _build_secret_noise_profile(findings)

    license_review = _build_license_review_profile(findings)

    summary = {
        "model_version": ("cre-foundry-sql-safety-remediation-summary-v1"),
        "scanner_control_plane_operational": (
            scanner_summary.get("scanner_control_plane_operational")
        ),
        "security_gate_passed": False,
        "blocking_b608_count": len(inventory_rows),
        "affected_file_count": len(file_counts),
        "affected_scope_count": (inventory["affected_scope_count"]),
        "parameter_binding_present_count": sum(
            bool(row["execute_parameter_binding_present"]) for row in inventory_rows
        ),
        "identifier_safety_signal_count": sum(
            int(row["identifier_safety_signal_count"]) for row in inventory_rows
        ),
        "test_reference_count": sum(int(row["test_reference_count"]) for row in inventory_rows),
        "secret_review_finding_count": (secret_noise["secret_finding_count"]),
        "likely_digest_artifact_count": (secret_noise["likely_digest_artifact_count"]),
        "license_review_count": (license_review["review_license_count"]),
        "prohibited_license_count": (license_review["prohibited_license_count"]),
        "automatic_source_rewrite_count": 0,
        "automatic_suppression_count": 0,
        "automatic_risk_acceptance_count": 0,
        "raw_secret_value_count": 0,
        "network_access_count": 0,
        "database_access_count": 0,
        "database_write_count": 0,
        "snapshot_registration_count": 0,
        "automatic_acquisition_count": 0,
        "persistent_outcome_database_creation_count": 0,
        "outcome_event_insertion_count": 0,
        "point_in_time_dataset_execution_count": 0,
        "model_training_execution_count": 0,
        "backtest_execution_count": 0,
        "pilot_execution_count": 0,
        "production_ranking_execution_count": 0,
        "outreach_execution_count": 0,
        "next_required_checkpoint": ("sql-safety-remediation-wave-1"),
        "policy": EXPECTED_POLICY,
    }

    result = {
        "summary": summary,
        "inventory": inventory,
        "secret_noise": secret_noise,
        "license_review": license_review,
    }

    if write_contracts:
        inventory_path = project_root / str(outputs["inventory"])

        summary_path = project_root / str(outputs["summary"])

        secret_noise_path = project_root / str(outputs["secret_noise_profile"])

        license_review_path = project_root / str(outputs["license_review_profile"])

        report_path = project_root / str(outputs["report"])

        _atomic_json(
            inventory_path,
            inventory,
        )

        _atomic_json(
            summary_path,
            summary,
        )

        _atomic_json(
            secret_noise_path,
            secret_noise,
        )

        _atomic_json(
            license_review_path,
            license_review,
        )

        markdown: list[str] = [
            "# SQL Safety Remediation Inventory",
            "",
            (
                "This inventory preserves every blocking B608 "
                "finding and binds it to its source and statement "
                "digests before any source rewrite occurs."
            ),
            "",
            (f"- Blocking B608 findings: `{summary['blocking_b608_count']}`"),
            (f"- Affected files: `{summary['affected_file_count']}`"),
            (f"- Affected scopes: `{summary['affected_scope_count']}`"),
            (
                f"- Existing parameter-binding signals: "
                f"`{summary['parameter_binding_present_count']}`"
            ),
            (f"- Discovered test references: `{summary['test_reference_count']}`"),
            (f"- Secret review findings: `{summary['secret_review_finding_count']}`"),
            (f"- Likely digest artifacts: `{summary['likely_digest_artifact_count']}`"),
            (f"- License review items: `{summary['license_review_count']}`"),
            "- Automatic rewrites: `0`",
            "- Automatic suppressions: `0`",
            "- Automatic risk acceptances: `0`",
            "- Database access: `0`",
            "- Database writes: `0`",
            "- Security gate passed: `false`",
            "",
            "## Remediation waves",
            "",
            (
                "1. Parameterize Parquet and other file paths; "
                "separate fixed table structure from path values."
            ),
            ("2. Introduce one strict qualified-identifier validation and quoting layer."),
            (
                "3. Refactor projection, column and INSERT query "
                "construction onto the shared safety layer."
            ),
            ("4. Manually investigate any query shape that cannot be proven safe mechanically."),
            "",
            "## Blocking locations",
            "",
        ]

        for row in inventory_rows:
            markdown.extend(
                [
                    (f"### {row['source_path']}:{row['line_number']}"),
                    "",
                    (f"- Scope: `{row['enclosing_scope']}`"),
                    (f"- Query kind: `{row['query_kind']}`"),
                    (f"- Remediation wave: `{row['remediation_wave']}`"),
                    (f"- Review priority: `{row['review_priority']}`"),
                    (
                        f"- Parameter binding present: "
                        f"`{str(row['execute_parameter_binding_present']).lower()}`"
                    ),
                    (f"- Dynamic expressions: `{row['dynamic_expression_count']}`"),
                    (f"- Test references: `{row['test_reference_count']}`"),
                    (f"- Source digest: `{row['source_sha256']}`"),
                    (f"- Statement digest: `{row['statement_sha256']}`"),
                    "",
                    str(row["proposed_control"]),
                    "",
                ]
            )

        _atomic_text(
            report_path,
            "\n".join(markdown).rstrip() + "\n",
        )

    return result
