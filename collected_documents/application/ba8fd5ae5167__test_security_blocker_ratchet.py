from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from cre_foundry.security_blocker_ratchet import (
    EXPECTED_POLICY,
    build_security_blocker_ratchet,
)

TITLE = "B608: Possible SQL injection vector through string-based query construction."


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


def _identity_payload(
    index: int,
    *,
    ast_digest: str | None = None,
) -> dict[str, str]:
    return {
        "scanner": "bandit",
        "advisory_id": "B608",
        "title": TITLE,
        "source_path": (f"src/cre_foundry/example_{index}.py"),
        "enclosing_scope": (f"query_scope_{index}"),
        "query_kind": ("dynamic_projection_or_relation"),
        "statement_ast_sha256": (
            ast_digest
            if ast_digest is not None
            else hashlib.sha256(f"statement-{index}".encode()).hexdigest()
        ),
    }


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


def _project(
    tmp_path: Path,
    *,
    current_count: int = 20,
    line_offset: int = 0,
    mutate_first: bool = False,
    duplicate_first: bool = False,
    scanner_count_override: int | None = None,
) -> Path:
    baseline_rows: list[dict[str, object]] = []

    current_rows: list[dict[str, object]] = []

    for index in range(20):
        payload = _identity_payload(index)

        baseline_rows.append(
            {
                **payload,
                "semantic_id": _semantic_id(payload),
                "initial_location": (f"{payload['source_path']}:{index + 1}"),
            }
        )

    for index in range(current_count):
        payload = _identity_payload(
            index,
            ast_digest=(
                hashlib.sha256(b"mutated-statement").hexdigest()
                if (mutate_first and index == 0)
                else None
            ),
        )

        current_rows.append(
            {
                **payload,
                "line_number": (index + 1 + line_offset),
            }
        )

    if duplicate_first and current_rows:
        current_rows.append(dict(current_rows[0]))

    _write_json(
        tmp_path / "config" / "security_blocker_baseline.json",
        {
            "config_version": ("cre-foundry-security-blocker-baseline-v2"),
            "semantic_identity_version": ("python-ast-no-attributes-v1"),
            "baseline_policy": (EXPECTED_POLICY),
            "blockers": baseline_rows,
        },
    )

    _write_json(
        tmp_path / "docs" / "security" / "sql_safety_remediation_inventory.json",
        {"items": current_rows},
    )

    scanner_count = (
        scanner_count_override if scanner_count_override is not None else len(current_rows)
    )

    _write_json(
        tmp_path / "docs" / "security" / "devsecops_scanner_summary.json",
        {
            "scanner_control_plane_operational": True,
            "blocking_finding_count": scanner_count,
            "security_gate_passed": (current_count == 0 and not duplicate_first),
        },
    )

    return tmp_path


def test_exact_semantic_baseline_passes(
    tmp_path: Path,
) -> None:
    project = _project(tmp_path)

    report = build_security_blocker_ratchet(
        project,
        write_contracts=True,
    )

    assert report["ratchet_passed"] is True

    assert report["current_blocker_count"] == 20

    assert report["new_blocker_count"] == 0

    assert report["semantic_ast_identity_used"] is True

    assert report["line_number_identity_used"] is False


def test_line_number_drift_is_evidence_not_identity(
    tmp_path: Path,
) -> None:
    project = _project(
        tmp_path,
        line_offset=500,
    )

    report = build_security_blocker_ratchet(
        project,
        write_contracts=False,
    )

    assert report["ratchet_passed"] is True

    assert report["new_blocker_count"] == 0

    assert report["location_drift_count"] == 20


def test_semantic_statement_change_is_new_blocker(
    tmp_path: Path,
) -> None:
    project = _project(
        tmp_path,
        mutate_first=True,
    )

    report = build_security_blocker_ratchet(
        project,
        write_contracts=False,
    )

    assert report["ratchet_passed"] is False

    assert report["new_blocker_count"] == 1

    assert report["remediated_blocker_count"] == 1


def test_remediated_blockers_may_disappear(
    tmp_path: Path,
) -> None:
    project = _project(
        tmp_path,
        current_count=12,
    )

    report = build_security_blocker_ratchet(
        project,
        write_contracts=False,
    )

    assert report["ratchet_passed"] is True

    assert report["current_blocker_count"] == 12

    assert report["remediated_blocker_count"] == 8

    assert report["new_blocker_count"] == 0


def test_zero_blockers_enables_full_enforcement(
    tmp_path: Path,
) -> None:
    project = _project(
        tmp_path,
        current_count=0,
    )

    report = build_security_blocker_ratchet(
        project,
        write_contracts=False,
    )

    assert report["ratchet_passed"] is True

    assert report["zero_blocker_state"] is True

    assert report["full_enforcement_ready"] is True


def test_duplicate_current_semantic_identity_is_rejected(
    tmp_path: Path,
) -> None:
    project = _project(
        tmp_path,
        duplicate_first=True,
    )

    with pytest.raises(
        RuntimeError,
        match=("Duplicate current semantic identity"),
    ):
        build_security_blocker_ratchet(
            project,
            write_contracts=False,
        )


def test_scanner_inventory_count_disagreement_is_rejected(
    tmp_path: Path,
) -> None:
    project = _project(
        tmp_path,
        scanner_count_override=19,
    )

    with pytest.raises(
        RuntimeError,
        match=("Scanner and semantic inventory blocker counts disagree"),
    ):
        build_security_blocker_ratchet(
            project,
            write_contracts=False,
        )


def test_policy_drift_is_rejected(
    tmp_path: Path,
) -> None:
    project = _project(tmp_path)

    baseline_path = project / "config" / "security_blocker_baseline.json"

    document = json.loads(baseline_path.read_text(encoding="utf-8"))

    document["baseline_policy"]["line_number_drift_permitted"] = False

    _write_json(
        baseline_path,
        document,
    )

    with pytest.raises(
        RuntimeError,
        match="policy mismatch",
    ):
        build_security_blocker_ratchet(
            project,
            write_contracts=False,
        )
