#!/usr/bin/env bash
set -Eeuo pipefail

cd "$(
  git rev-parse --show-toplevel
)"

uv run pytest -q \
  tests/unit/test_sql_safety.py

uv run cre-foundry \
  build-sql-safety-primitives-report

uv run python - <<'PY'
import json
from pathlib import Path


report = json.loads(
    Path(
        "docs/security/"
        "sql_safety_primitives_report.json"
    ).read_text(
        encoding="utf-8"
    )
)

if report[
    "all_properties_passed"
] is not True:
    raise SystemExit(
        "SQL-safety primitive properties failed."
    )

for field in (
    "valid_example_failure_count",
    "hostile_example_acceptance_count",
    "deterministic_case_violation_count",
    "qualified_rendering_violation_count",
    "invalid_qualified_acceptance_count",
    "automatic_source_rewrite_count",
    "automatic_suppression_count",
    "automatic_risk_acceptance_count",
    "application_database_access_count",
    "application_database_write_count",
    "production_action_count",
):
    if report[field] != 0:
        raise SystemExit(
            f"SQL-safety violation: {field}"
        )

print("SQL-safety primitives validated:")
print(
    "  deterministic cases:",
    report[
        "deterministic_case_count"
    ],
)
print(
    "  accepted cases:",
    report[
        "accepted_deterministic_case_count"
    ],
)
print(
    "  rejected cases:",
    report[
        "rejected_deterministic_case_count"
    ],
)
print("  property violations: 0")
print("  hostile acceptances: 0")
print("  automatic rewrites: 0")
print("  suppressions: 0")
print("  application database activity: 0")
PY

echo
echo "SQL SAFETY PRIMITIVES CHECK PASSED"
