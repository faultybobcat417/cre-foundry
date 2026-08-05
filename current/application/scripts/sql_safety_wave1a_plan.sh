#!/usr/bin/env bash
set -Eeuo pipefail

cd "$(
  git rev-parse --show-toplevel
)"

uv run cre-foundry \
  build-sql-safety-wave1a-plan

uv run python - <<'PY'
from __future__ import annotations

import json
from pathlib import Path


config = json.loads(
    Path(
        "config/"
        "sql_safety_wave1a_planner.json"
    ).read_text(
        encoding="utf-8"
    )
)

plan = json.loads(
    Path(
        "docs/security/"
        "sql_safety_wave1a_plan.json"
    ).read_text(
        encoding="utf-8"
    )
)

expected = config[
    "policy"
][
    "expected_parameter_aware_count"
]

actual = plan[
    "parameter_aware_candidate_count"
]

if (
    type(expected) is not int
    or expected < 0
):
    raise SystemExit(
        "Configured candidate count is invalid."
    )

if actual != expected:
    raise SystemExit(
        "Wave 1A candidate count mismatch. "
        f"Expected={expected}, actual={actual}"
    )

if plan[
    "ready_for_surgical_migration"
] is not True:
    raise SystemExit(
        "Wave 1A plan is not migration-ready."
    )

for field in (
    "source_modification_count",
    "automatic_rewrite_count",
    "automatic_suppression_count",
    "automatic_risk_acceptance_count",
    "database_access_count",
    "database_write_count",
    "snapshot_registration_count",
    "model_training_execution_count",
    "pilot_execution_count",
    "production_ranking_execution_count",
    "outreach_execution_count",
):
    if plan[field] != 0:
        raise SystemExit(
            f"Unsafe planner activity: {field}"
        )

print()
print("Exact Wave 1A migration queue:")

for candidate in plan[
    "candidates"
]:
    print(
        "  -",
        candidate[
            "location"
        ],
        "|",
        candidate[
            "enclosing_scope"
        ],
        "|",
        candidate[
            "classification"
        ],
        "| tests",
        candidate[
            "test_reference_count"
        ],
    )

print()
print("Wave 1A planner contract:")
print(
    "  configured candidates:",
    expected,
)
print(
    "  generated candidates:",
    actual,
)
print(
    "  affected files:",
    plan[
        "affected_file_count"
    ],
)
print(
    "  classifications:",
    plan[
        "classification_counts"
    ],
)
print("  source modifications: 0")
print("  automatic rewrites: 0")
print("  suppressions: 0")
print("  risk acceptances: 0")
print("  database activity: 0")
print("  production activity: 0")
PY

echo
echo "SQL SAFETY WAVE 1A PLAN COMPLETED"
