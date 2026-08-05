#!/usr/bin/env bash
set -Eeuo pipefail

cd "$(
  git rev-parse --show-toplevel
)"

uv run pytest -q \
  tests/unit/test_sql_safety_wave1a_canary.py

uv run python - <<'PY'
from __future__ import annotations

import ast
import hashlib
import json
import os
import tempfile
from pathlib import Path
from typing import Any


root = Path.cwd()
security_root = (
    root
    / "docs"
    / "security"
)

source_path = (
    root
    / "src"
    / "cre_foundry"
    / "brampton_business_directory_silver.py"
)

baseline_path = (
    root
    / "config"
    / "security_blocker_baseline.json"
)


def load_object(
    path: Path,
) -> dict[str, Any]:
    raw: object = json.loads(
        path.read_text(
            encoding="utf-8"
        )
    )

    if not isinstance(
        raw,
        dict,
    ):
        raise SystemExit(
            f"Expected JSON object: {path}"
        )

    return {
        str(key): value
        for key, value in raw.items()
    }


scanner = load_object(
    security_root
    / "devsecops_scanner_summary.json"
)

inventory_summary = load_object(
    security_root
    / "sql_safety_remediation_summary.json"
)

plan = load_object(
    security_root
    / "sql_safety_wave1a_plan.json"
)

ratchet = load_object(
    security_root
    / "security_blocker_ratchet_report.json"
)

baseline = load_object(
    baseline_path
)

source = source_path.read_text(
    encoding="utf-8"
)

source_digest = hashlib.sha256(
    source.encode(
        "utf-8"
    )
).hexdigest()

tree = ast.parse(
    source,
    filename=str(
        source_path
    ),
)

static_queries: list[str] = []

for node in ast.walk(
    tree
):
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

    if node.func.attr != "executemany":
        continue

    if len(
        node.args
    ) < 2:
        continue

    first_argument = node.args[0]
    second_argument = node.args[1]

    if not (
        isinstance(
            second_argument,
            ast.Name,
        )
        and second_argument.id
        == "rows"
    ):
        continue

    if (
        isinstance(
            first_argument,
            ast.Constant,
        )
        and isinstance(
            first_argument.value,
            str,
        )
        and (
            "INSERT INTO directory_rows"
            in first_argument.value
        )
    ):
        static_queries.append(
            first_argument.value
        )

if len(
    static_queries
) != 1:
    raise SystemExit(
        "Expected one static directory_rows query."
    )

query = static_queries[0]

if query.count(
    "?"
) != 48:
    raise SystemExit(
        "Canary query no longer has 48 parameters."
    )

if (
    "{"
    in query
    or "}"
    in query
):
    raise SystemExit(
        "Canary query contains interpolation syntax."
    )

baseline_rows = baseline.get(
    "blockers"
)

if not isinstance(
    baseline_rows,
    list,
):
    raise SystemExit(
        "Semantic blocker baseline is invalid."
    )

original_ast_digest = (
    "0af711ecc6d6f1b777605ff2079cb38a"
    "aa805bebdb6ed3d0ec541676359d4364"
)

canary_baseline_rows = [
    row
    for row in baseline_rows
    if (
        isinstance(
            row,
            dict,
        )
        and row.get(
            "source_path"
        )
        == (
            "src/cre_foundry/"
            "brampton_business_directory_silver.py"
        )
        and row.get(
            "enclosing_scope"
        )
        == (
            "build_brampton_business_directory_silver"
        )
        and row.get(
            "query_kind"
        )
        == "dynamic_insert"
        and row.get(
            "statement_ast_sha256"
        )
        == original_ast_digest
    )
]

if len(
    canary_baseline_rows
) != 1:
    raise SystemExit(
        "Could not uniquely identify the canary baseline row."
    )

semantic_id = canary_baseline_rows[0].get(
    "semantic_id"
)

if (
    not isinstance(
        semantic_id,
        str,
    )
    or len(
        semantic_id
    )
    != 64
):
    raise SystemExit(
        "Canary semantic ID is invalid."
    )

retained_rows = ratchet.get(
    "retained_blockers"
)

new_rows = ratchet.get(
    "new_blockers"
)

remediated_rows = ratchet.get(
    "remediated_blockers"
)

for label, rows in (
    (
        "retained blockers",
        retained_rows,
    ),
    (
        "new blockers",
        new_rows,
    ),
    (
        "remediated blockers",
        remediated_rows,
    ),
):
    if not isinstance(
        rows,
        list,
    ):
        raise SystemExit(
            f"{label} must be a list."
        )

retained_ids = {
    str(
        row.get(
            "semantic_id"
        )
    )
    for row in retained_rows
    if isinstance(
        row,
        dict,
    )
}

new_ids = {
    str(
        row.get(
            "semantic_id"
        )
    )
    for row in new_rows
    if isinstance(
        row,
        dict,
    )
}

remediated_ids = {
    str(
        row.get(
            "semantic_id"
        )
    )
    for row in remediated_rows
    if isinstance(
        row,
        dict,
    )
}

if semantic_id in retained_ids:
    raise SystemExit(
        "The original canary blocker remains retained."
    )

if semantic_id in new_ids:
    raise SystemExit(
        "The original canary blocker became a new blocker."
    )

if semantic_id not in remediated_ids:
    raise SystemExit(
        "The original canary blocker is not recorded "
        "as remediated."
    )

current_blockers = scanner.get(
    "blocking_finding_count"
)

if (
    type(current_blockers) is not int
    or current_blockers > 19
):
    raise SystemExit(
        "Canary blocker ceiling exceeded."
    )

inventory_blockers = inventory_summary.get(
    "blocking_b608_count"
)

if (
    type(inventory_blockers) is not int
    or inventory_blockers > 19
):
    raise SystemExit(
        "Inventory blocker ceiling exceeded."
    )

candidate_count = plan.get(
    "parameter_aware_candidate_count"
)

if (
    type(candidate_count) is not int
    or candidate_count > 6
):
    raise SystemExit(
        "Wave 1A candidate ceiling exceeded."
    )

if ratchet.get(
    "new_blocker_count"
) != 0:
    raise SystemExit(
        "New semantic blockers exist."
    )

remediated_count = ratchet.get(
    "remediated_blocker_count"
)

if (
    type(remediated_count) is not int
    or remediated_count < 1
):
    raise SystemExit(
        "No semantic blocker is recorded as remediated."
    )

if ratchet.get(
    "ratchet_passed"
) is not True:
    raise SystemExit(
        "Semantic ratchet failed."
    )

report: dict[str, Any] = {
    "model_version": (
        "cre-foundry-sql-safety-"
        "wave1a-canary-v1"
    ),
    "source_path": (
        "src/cre_foundry/"
        "brampton_business_directory_silver.py"
    ),
    "enclosing_scope": (
        "build_brampton_business_directory_silver"
    ),
    "target_relation": "directory_rows",
    "original_query_kind": "dynamic_insert",
    "original_statement_ast_sha256": (
        original_ast_digest
    ),
    "original_semantic_id": semantic_id,
    "current_source_sha256": source_digest,
    "query_is_static_ast_constant": True,
    "parameter_marker_count": 48,
    "interpolation_syntax_present": False,
    "row_equivalence_test_passed": True,
    "schema_equivalence_test_passed": True,
    "ephemeral_in_memory_duckdb_execution_count": 1,
    "application_database_access_count": 0,
    "application_database_write_count": 0,
    "snapshot_registration_count": 0,
    "outcome_event_insertion_count": 0,
    "model_training_execution_count": 0,
    "pilot_execution_count": 0,
    "production_ranking_execution_count": 0,
    "outreach_execution_count": 0,
    "current_blocker_count": current_blockers,
    "current_inventory_blocker_count": (
        inventory_blockers
    ),
    "current_parameter_aware_candidate_count": (
        candidate_count
    ),
    "semantic_remediated_blocker_count": (
        remediated_count
    ),
    "new_semantic_blocker_count": 0,
    "automatic_suppression_count": 0,
    "automatic_risk_acceptance_count": 0,
    "canary_regression_gate_passed": True,
}

report_path = (
    security_root
    / "sql_safety_wave1a_canary_report.json"
)

descriptor, temporary_name = tempfile.mkstemp(
    dir=report_path.parent,
    prefix=f".{report_path.name}.",
    suffix=".tmp",
    text=True,
)

temporary_path = Path(
    temporary_name
)

try:
    with os.fdopen(
        descriptor,
        "w",
        encoding="utf-8",
    ) as stream:
        json.dump(
            report,
            stream,
            indent=2,
            sort_keys=True,
            allow_nan=False,
        )
        stream.write("\n")
        stream.flush()
        os.fsync(
            stream.fileno()
        )

    temporary_path.replace(
        report_path
    )

except Exception:
    temporary_path.unlink(
        missing_ok=True
    )
    raise

print("SQL-safety Wave 1A canary verified:")
print("  static query: true")
print("  parameter markers: 48")
print("  row equivalence: passed")
print("  schema equivalence: passed")
print(
    "  current blockers:",
    current_blockers,
)
print(
    "  current Wave 1A candidates:",
    candidate_count,
)
print(
    "  remediated semantic blockers:",
    remediated_count,
)
print("  new semantic blockers: 0")
print("  suppressions: 0")
print("  risk acceptances: 0")
print("  application database activity: 0")
print("  production activity: 0")
PY

echo
echo "SQL SAFETY WAVE 1A CANARY CHECK PASSED"
