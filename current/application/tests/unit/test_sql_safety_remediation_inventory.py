from __future__ import annotations

import json
from pathlib import Path

import pytest

from cre_foundry.sql_safety_remediation_inventory import (
    EXPECTED_POLICY,
    build_sql_safety_remediation_inventory,
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
) -> Path:
    config = {
        "config_version": ("cre-foundry-sql-safety-remediation-inventory-v1"),
        "policy": {
            **EXPECTED_POLICY,
            "expected_blocking_b608_count": 1,
        },
        "inputs": {
            "normalized_findings": ("docs/security/devsecops_scanner_findings.json"),
            "scanner_summary": ("docs/security/devsecops_scanner_summary.json"),
        },
        "outputs": {
            "inventory": ("docs/security/sql_safety_remediation_inventory.json"),
            "summary": ("docs/security/sql_safety_remediation_summary.json"),
            "secret_noise_profile": ("docs/security/secret_noise_profile.json"),
            "license_review_profile": ("docs/security/license_review_profile.json"),
            "report": ("docs/security/sql_safety_remediation_inventory.md"),
        },
    }

    _write_json(
        tmp_path / "config" / "sql_safety_remediation_inventory.json",
        config,
    )

    source_path = tmp_path / "src" / "cre_foundry" / "example.py"

    source_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    source_path.write_text(
        "\n".join(
            [
                "from __future__ import annotations",
                "",
                "",
                "def count_rows(connection, relation_name: str):",
                '    query = "SELECT count(*) FROM " + relation_name',
                "    return connection.execute(query).fetchone()",
                "",
            ]
        ),
        encoding="utf-8",
    )

    test_path = tmp_path / "tests" / "unit" / "test_example.py"

    test_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    test_path.write_text(
        "\n".join(
            [
                "def test_count_rows():",
                "    assert True",
                "",
            ]
        ),
        encoding="utf-8",
    )

    _write_json(
        tmp_path / "docs" / "security" / "devsecops_scanner_summary.json",
        {
            "scanner_control_plane_operational": True,
            "security_gate_passed": False,
        },
    )

    _write_json(
        tmp_path / "docs" / "security" / "devsecops_scanner_findings.json",
        {
            "model_version": ("cre-foundry-devsecops-scanner-findings-v1"),
            "findings": [
                {
                    "finding_fingerprint": ("a" * 64),
                    "scanner": "bandit",
                    "category": "static_analysis",
                    "severity": "medium",
                    "confidence": "medium",
                    "title": (
                        "B608: Possible SQL injection vector "
                        "through string-based query construction."
                    ),
                    "location": ("src/cre_foundry/example.py:5"),
                    "advisory_id": "B608",
                    "blocking_by_policy": True,
                    "suppressed": False,
                    "suppression_id": None,
                    "metadata": {},
                },
                {
                    "finding_fingerprint": ("b" * 64),
                    "scanner": "detect-secrets",
                    "category": "secret_worktree",
                    "severity": "review",
                    "confidence": "review",
                    "title": "Digest-shaped value",
                    "location": ("docs/data_contracts/example.json:4"),
                    "advisory_id": ("Hex High Entropy String"),
                    "blocking_by_policy": False,
                    "suppressed": False,
                    "suppression_id": None,
                    "metadata": {"secret_value_persisted": False},
                },
                {
                    "finding_fingerprint": ("c" * 64),
                    "scanner": "pip-licenses",
                    "category": "license_risk",
                    "severity": "review",
                    "confidence": "medium",
                    "title": ("example uses MPL-2.0"),
                    "component": ("example==1.0"),
                    "location": ("installed environment"),
                    "advisory_id": None,
                    "blocking_by_policy": False,
                    "suppressed": False,
                    "suppression_id": None,
                    "metadata": {"risk": "review"},
                },
            ],
            "raw_secret_value_count": 0,
        },
    )

    return tmp_path


def test_inventory_extracts_blocker_without_mutation(
    tmp_path: Path,
) -> None:
    project = _project(tmp_path)

    source = project / "src" / "cre_foundry" / "example.py"

    before = source.read_bytes()

    result = build_sql_safety_remediation_inventory(
        project,
        write_contracts=True,
    )

    after = source.read_bytes()

    assert before == after

    summary = result["summary"]

    inventory = result["inventory"]

    assert summary["blocking_b608_count"] == 1

    assert summary["affected_file_count"] == 1

    assert summary["automatic_source_rewrite_count"] == 0

    assert summary["automatic_suppression_count"] == 0

    assert summary["database_access_count"] == 0

    assert inventory["items"][0]["enclosing_scope"] == "count_rows"

    assert inventory["items"][0]["query_kind"] == "dynamic_relation_count"

    assert inventory["items"][0]["test_reference_count"] == 1


def test_inventory_is_deterministic(
    tmp_path: Path,
) -> None:
    project = _project(tmp_path)

    first = build_sql_safety_remediation_inventory(
        project,
        write_contracts=True,
    )

    first_bytes = (
        project / "docs" / "security" / "sql_safety_remediation_inventory.json"
    ).read_bytes()

    second = build_sql_safety_remediation_inventory(
        project,
        write_contracts=True,
    )

    second_bytes = (
        project / "docs" / "security" / "sql_safety_remediation_inventory.json"
    ).read_bytes()

    assert first == second
    assert first_bytes == second_bytes


def test_inventory_profiles_secret_noise_and_licenses(
    tmp_path: Path,
) -> None:
    project = _project(tmp_path)

    result = build_sql_safety_remediation_inventory(
        project,
        write_contracts=False,
    )

    secret_noise = result["secret_noise"]

    license_review = result["license_review"]

    assert secret_noise["secret_finding_count"] == 1

    assert secret_noise["likely_digest_artifact_count"] == 1

    assert secret_noise["raw_secret_value_count"] == 0

    assert license_review["review_license_count"] == 1

    assert license_review["prohibited_license_count"] == 0


def test_source_path_escape_is_rejected(
    tmp_path: Path,
) -> None:
    project = _project(tmp_path)

    findings_path = project / "docs" / "security" / "devsecops_scanner_findings.json"

    document = json.loads(findings_path.read_text(encoding="utf-8"))

    document["findings"][0]["location"] = "../outside.py:1"

    _write_json(
        findings_path,
        document,
    )

    with pytest.raises(
        RuntimeError,
        match="escapes project root",
    ):
        build_sql_safety_remediation_inventory(
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
        10001,
        "1",
        1.0,
        None,
    ],
)
def test_invalid_expected_count_is_rejected(
    tmp_path: Path,
    invalid_count: object,
) -> None:
    project = _project(tmp_path)

    config_path = project / "config" / "sql_safety_remediation_inventory.json"

    document = json.loads(config_path.read_text(encoding="utf-8"))

    document["policy"]["expected_blocking_b608_count"] = invalid_count

    _write_json(
        config_path,
        document,
    )

    with pytest.raises(
        RuntimeError,
        match=("expected_blocking_b608_count must be an integer"),
    ):
        build_sql_safety_remediation_inventory(
            project,
            write_contracts=False,
        )


def test_non_count_policy_drift_is_rejected(
    tmp_path: Path,
) -> None:
    project = _project(tmp_path)

    config_path = project / "config" / "sql_safety_remediation_inventory.json"

    document = json.loads(config_path.read_text(encoding="utf-8"))

    document["policy"]["automatic_suppression_enabled"] = True

    _write_json(
        config_path,
        document,
    )

    with pytest.raises(
        RuntimeError,
        match="SQL-safety policy mismatch",
    ):
        build_sql_safety_remediation_inventory(
            project,
            write_contracts=False,
        )


def test_unknown_policy_field_is_rejected(
    tmp_path: Path,
) -> None:
    project = _project(tmp_path)

    config_path = project / "config" / "sql_safety_remediation_inventory.json"

    document = json.loads(config_path.read_text(encoding="utf-8"))

    document["policy"]["unreviewed_override"] = True

    _write_json(
        config_path,
        document,
    )

    with pytest.raises(
        RuntimeError,
        match="SQL-safety policy mismatch",
    ):
        build_sql_safety_remediation_inventory(
            project,
            write_contracts=False,
        )


def test_inventory_emits_semantic_ast_identity(
    tmp_path: Path,
) -> None:
    project = _project(tmp_path)

    result = build_sql_safety_remediation_inventory(
        project,
        write_contracts=False,
    )

    item = result["inventory"]["items"][0]

    assert item["scanner"] == "bandit"

    assert item["advisory_id"] == "B608"

    assert isinstance(
        item["title"],
        str,
    )

    digest = item["statement_ast_sha256"]

    assert isinstance(
        digest,
        str,
    )

    assert len(digest) == 64

    assert all(character in "0123456789abcdef" for character in digest)


def test_ast_identity_ignores_line_number_drift(
    tmp_path: Path,
) -> None:
    project = _project(tmp_path)

    first = build_sql_safety_remediation_inventory(
        project,
        write_contracts=False,
    )

    first_item = first["inventory"]["items"][0]

    source_path = project / "src" / "cre_foundry" / "example.py"

    source_path.write_text(
        "\n\n" + source_path.read_text(encoding="utf-8"),
        encoding="utf-8",
    )

    findings_path = project / "docs" / "security" / "devsecops_scanner_findings.json"

    document = json.loads(findings_path.read_text(encoding="utf-8"))

    location = document["findings"][0]["location"]

    path_text, separator, line_text = location.rpartition(":")

    assert separator

    document["findings"][0]["location"] = f"{path_text}:{int(line_text) + 2}"

    _write_json(
        findings_path,
        document,
    )

    second = build_sql_safety_remediation_inventory(
        project,
        write_contracts=False,
    )

    second_item = second["inventory"]["items"][0]

    assert first_item["statement_ast_sha256"] == second_item["statement_ast_sha256"]

    assert first_item["statement_sha256"] == second_item["statement_sha256"]
