from __future__ import annotations

import hashlib
import json
import os
import tempfile
from pathlib import Path
from typing import Any, Final

BASELINE_VERSION: Final = "cre-foundry-security-blocker-baseline-v2"

SEMANTIC_IDENTITY_VERSION: Final = "python-ast-no-attributes-v1"

EXPECTED_POLICY: Final = {
    "baseline_is_temporary": True,
    "baseline_is_not_suppression": True,
    "baseline_is_not_risk_acceptance": True,
    "new_blockers_forbidden": True,
    "remediated_blockers_may_disappear": True,
    "line_number_drift_permitted": True,
    "formatting_only_drift_permitted": True,
    "semantic_statement_drift_treated_as_new": True,
    "source_path_drift_treated_as_new": True,
    "scope_drift_treated_as_new": True,
    "query_kind_drift_treated_as_new": True,
    "scanner_inventory_count_reconciliation_required": True,
    "duplicate_semantic_identity_forbidden": True,
    "full_enforcement_required_at_zero": True,
    "expected_initial_blocker_count": 20,
}

IDENTITY_FIELDS: Final = (
    "scanner",
    "advisory_id",
    "title",
    "source_path",
    "enclosing_scope",
    "query_kind",
    "statement_ast_sha256",
)


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


def _identity_payload(
    row: dict[str, Any],
    *,
    label: str,
) -> dict[str, str]:
    payload = {
        field: _required_string(
            row,
            field,
            label=label,
        )
        for field in IDENTITY_FIELDS
    }

    if payload["scanner"] != "bandit":
        raise RuntimeError(f"{label}.scanner must be bandit.")

    if payload["advisory_id"] != "B608":
        raise RuntimeError(f"{label}.advisory_id must be B608.")

    if not payload["source_path"].startswith("src/cre_foundry/"):
        raise RuntimeError(f"{label}.source_path must be under src/cre_foundry.")

    digest = payload["statement_ast_sha256"]

    if len(digest) != 64 or any(character not in "0123456789abcdef" for character in digest):
        raise RuntimeError(f"{label}.statement_ast_sha256 must be lowercase SHA-256.")

    return payload


def _semantic_id(
    payload: dict[str, str],
) -> str:
    return hashlib.sha256(
        json.dumps(
            payload,
            sort_keys=True,
            separators=(
                ",",
                ":",
            ),
        ).encode("utf-8")
    ).hexdigest()


def _current_location(
    row: dict[str, Any],
    *,
    label: str,
) -> str:
    source_path = _required_string(
        row,
        "source_path",
        label=label,
    )

    line_number = row.get("line_number")

    if type(line_number) is not int or line_number <= 0:
        raise RuntimeError(f"{label}.line_number must be a positive integer.")

    return f"{source_path}:{line_number}"


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


def build_security_blocker_ratchet(
    project_root: Path,
    *,
    write_contracts: bool = True,
) -> dict[str, Any]:
    baseline = _load_object(project_root / "config" / "security_blocker_baseline.json")

    if baseline.get("config_version") != BASELINE_VERSION:
        raise RuntimeError("Unsupported security blocker baseline version.")

    if baseline.get("semantic_identity_version") != SEMANTIC_IDENTITY_VERSION:
        raise RuntimeError("Unsupported semantic identity version.")

    policy = baseline.get("baseline_policy")

    if policy != EXPECTED_POLICY:
        raise RuntimeError("Security blocker baseline policy mismatch.")

    baseline_rows = _object_list(
        baseline.get("blockers"),
        label="baseline blockers",
    )

    baseline_by_id: dict[
        str,
        dict[str, Any],
    ] = {}

    for index, row in enumerate(baseline_rows):
        label = f"baseline blockers[{index}]"

        payload = _identity_payload(
            row,
            label=label,
        )

        computed_id = _semantic_id(payload)

        declared_id = _required_string(
            row,
            "semantic_id",
            label=label,
        )

        if computed_id != declared_id:
            raise RuntimeError(f"{label}.semantic_id mismatch.")

        if computed_id in baseline_by_id:
            raise RuntimeError("Duplicate baseline semantic identity.")

        initial_location = _required_string(
            row,
            "initial_location",
            label=label,
        )

        baseline_by_id[computed_id] = {
            "semantic_id": computed_id,
            "identity": payload,
            "initial_location": initial_location,
        }

    if len(baseline_by_id) != 20:
        raise RuntimeError("Semantic baseline must contain exactly 20 blockers.")

    inventory = _load_object(
        project_root / "docs" / "security" / "sql_safety_remediation_inventory.json"
    )

    current_rows = _object_list(
        inventory.get("items"),
        label="current inventory items",
    )

    current_by_id: dict[
        str,
        dict[str, Any],
    ] = {}

    for index, row in enumerate(current_rows):
        label = f"current inventory items[{index}]"

        payload = _identity_payload(
            row,
            label=label,
        )

        computed_id = _semantic_id(payload)

        if computed_id in current_by_id:
            raise RuntimeError("Duplicate current semantic identity.")

        current_by_id[computed_id] = {
            "semantic_id": computed_id,
            "identity": payload,
            "current_location": _current_location(
                row,
                label=label,
            ),
        }

    scanner_summary = _load_object(
        project_root / "docs" / "security" / "devsecops_scanner_summary.json"
    )

    scanner_operational = scanner_summary.get("scanner_control_plane_operational") is True

    scanner_blocker_count = scanner_summary.get("blocking_finding_count")

    if type(scanner_blocker_count) is not int or scanner_blocker_count < 0:
        raise RuntimeError("Scanner blocker count is invalid.")

    if scanner_blocker_count != len(current_by_id):
        raise RuntimeError("Scanner and semantic inventory blocker counts disagree.")

    baseline_ids = set(baseline_by_id)

    current_ids = set(current_by_id)

    retained_ids = sorted(baseline_ids & current_ids)

    remediated_ids = sorted(baseline_ids - current_ids)

    new_ids = sorted(current_ids - baseline_ids)

    retained_blockers: list[dict[str, Any]] = []

    location_drifts: list[dict[str, str]] = []

    for semantic_id in retained_ids:
        baseline_row = baseline_by_id[semantic_id]

        current_row = current_by_id[semantic_id]

        initial_location = str(baseline_row["initial_location"])

        current_location = str(current_row["current_location"])

        if initial_location != current_location:
            location_drifts.append(
                {
                    "semantic_id": semantic_id,
                    "initial_location": initial_location,
                    "current_location": current_location,
                }
            )

        retained_blockers.append(
            {
                "semantic_id": semantic_id,
                "identity": current_row["identity"],
                "initial_location": initial_location,
                "current_location": current_location,
            }
        )

    ratchet_passed = bool(scanner_operational and not new_ids)

    zero_blocker_state = not current_ids

    full_enforcement_ready = bool(
        ratchet_passed
        and zero_blocker_state
        and scanner_summary.get("security_gate_passed") is True
    )

    report = {
        "model_version": ("cre-foundry-security-blocker-ratchet-v2"),
        "semantic_identity_version": (SEMANTIC_IDENTITY_VERSION),
        "scanner_control_plane_operational": (scanner_operational),
        "scanner_blocker_count": (scanner_blocker_count),
        "baseline_blocker_count": len(baseline_ids),
        "current_blocker_count": len(current_ids),
        "retained_blocker_count": len(retained_ids),
        "remediated_blocker_count": len(remediated_ids),
        "new_blocker_count": len(new_ids),
        "location_drift_count": len(location_drifts),
        "ratchet_passed": ratchet_passed,
        "zero_blocker_state": zero_blocker_state,
        "full_enforcement_ready": (full_enforcement_ready),
        "semantic_ast_identity_used": True,
        "line_number_identity_used": False,
        "formatting_sensitive_identity_used": False,
        "baseline_is_suppression": False,
        "baseline_is_risk_acceptance": False,
        "automatic_suppression_count": 0,
        "automatic_risk_acceptance_count": 0,
        "database_access_count": 0,
        "database_write_count": 0,
        "production_action_count": 0,
        "retained_blockers": (retained_blockers),
        "remediated_blockers": [baseline_by_id[semantic_id] for semantic_id in remediated_ids],
        "new_blockers": [current_by_id[semantic_id] for semantic_id in new_ids],
        "location_drifts": location_drifts,
    }

    if write_contracts:
        _atomic_json(
            project_root / "docs" / "security" / "security_blocker_ratchet_report.json",
            report,
        )

    return report
