#!/usr/bin/env bash
set -Eeuo pipefail

cd "$(
  git rev-parse --show-toplevel
)"

uv run cre-foundry \
  build-security-blocker-ratchet

uv run python - <<'PY'
import json
from pathlib import Path


report = json.loads(
    Path(
        "docs/security/"
        "security_blocker_ratchet_report.json"
    ).read_text(
        encoding="utf-8"
    )
)

if not report[
    "ratchet_passed"
]:
    raise SystemExit(
        "Security blocker ratchet failed. "
        f"New blockers={report['new_blocker_count']}."
    )

if report[
    "automatic_suppression_count"
] != 0:
    raise SystemExit(
        "Automatic suppression occurred."
    )

if report[
    "automatic_risk_acceptance_count"
] != 0:
    raise SystemExit(
        "Automatic risk acceptance occurred."
    )

print(
    "Security blocker ratchet passed:"
)
print(
    "  baseline blockers:",
    report[
        "baseline_blocker_count"
    ],
)
print(
    "  current blockers:",
    report[
        "current_blocker_count"
    ],
)
print(
    "  remediated blockers:",
    report[
        "remediated_blocker_count"
    ],
)
print(
    "  new blockers:",
    report[
        "new_blocker_count"
    ],
)
print(
    "  full enforcement ready:",
    report[
        "full_enforcement_ready"
    ],
)
PY
