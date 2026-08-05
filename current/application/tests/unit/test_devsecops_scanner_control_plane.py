from __future__ import annotations

import json
from pathlib import Path

from cre_foundry.devsecops_scanner_control_plane import (
    EXPECTED_POLICY,
    build_devsecops_scanner_control_plane,
)

TOOLCHAIN = {
    "pip-audit": "2.10.1",
    "bandit": "1.9.4",
    "detect-secrets": "1.5.0",
    "pip-licenses": "5.5.5",
}


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
            sort_keys=True,
        ),
        encoding="utf-8",
    )


def _project(
    tmp_path: Path,
) -> Path:
    _write_json(
        tmp_path / "config" / "devsecops_scanner_control_plane.json",
        {
            "config_version": ("cre-foundry-devsecops-scanner-control-plane-v1"),
            "policy": EXPECTED_POLICY,
            "toolchain": TOOLCHAIN,
            "raw_report_directory": ("logs/security_scans"),
            "suppression_path": ("config/security_suppressions.json"),
            "blocking_policy": {
                "bandit_severities": [
                    "medium",
                    "high",
                ],
                "bandit_confidences": [
                    "medium",
                    "high",
                ],
                "critical_secret_detectors": [
                    "Private Key",
                    "GitHub Token",
                ],
                "prohibited_license_markers": [
                    "AGPL",
                    "SSPL",
                ],
                "review_license_markers": [
                    "GPL",
                    "UNKNOWN",
                ],
            },
            "history_scan": {
                "maximum_blob_bytes": 1048576,
                "maximum_findings": 100,
                "excluded_path_prefixes": [
                    ".git/",
                    ".venv/",
                    "data/",
                    "logs/",
                ],
            },
            "ci_policy": {
                "required_workflow_path": (".github/workflows/security-audit.yml"),
                "maximum_timeout_minutes": 30,
                "required_top_level_permissions": {"contents": "read"},
                "required_job_permissions": {"contents": "read"},
                "forbidden_triggers": ["pull_request_target"],
                "required_commands": [
                    ("uv sync --locked --all-groups"),
                    ("./scripts/security_scan.sh --enforce"),
                ],
            },
        },
    )

    _write_json(
        tmp_path / "config" / "security_suppressions.json",
        {
            "config_version": ("cre-foundry-security-suppressions-v1"),
            "suppressions": [],
        },
    )

    (tmp_path / "pyproject.toml").write_text(
        "\n".join(
            [
                "[project]",
                'name = "test-project"',
                'version = "0.1.0"',
                "",
            ]
        ),
        encoding="utf-8",
    )

    (tmp_path / "uv.lock").write_text(
        "\n".join(
            [
                "version = 1",
                "revision = 1",
                "",
                "[[package]]",
                'name = "alpha"',
                'version = "1.0.0"',
                "",
            ]
        ),
        encoding="utf-8",
    )

    _write_json(
        tmp_path / "docs" / "security" / "software_bill_of_materials.cdx.json",
        {
            "bomFormat": "CycloneDX",
            "specVersion": "1.7",
            "components": [
                {
                    "type": "library",
                    "name": "alpha",
                    "version": "1.0.0",
                    "purl": ("pkg:pypi/alpha@1.0.0"),
                }
            ],
        },
    )

    workflow = tmp_path / ".github" / "workflows" / "security-audit.yml"

    workflow.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    workflow.write_text(
        "\n".join(
            [
                "name: Security Audit",
                "on:",
                "  pull_request:",
                "permissions:",
                "  contents: read",
                "jobs:",
                "  audit:",
                "    runs-on: ubuntu-24.04",
                "    timeout-minutes: 30",
                "    permissions:",
                "      contents: read",
                "    steps:",
                "      - uses: actions/checkout@" + "a" * 40,
                "        with:",
                "          persist-credentials: false",
                "      - uses: astral-sh/setup-uv@" + "b" * 40,
                "      - run: uv sync --locked --all-groups",
                "      - run: ./scripts/security_scan.sh --enforce",
                "",
            ]
        ),
        encoding="utf-8",
    )

    raw = tmp_path / "logs" / "security_scans"

    _write_json(
        raw / "tool_versions.json",
        TOOLCHAIN,
    )

    _write_json(
        raw / "pip_audit.json",
        [],
    )

    _write_json(
        raw / "bandit.json",
        {
            "results": [],
            "errors": [],
        },
    )

    _write_json(
        raw / "detect_secrets.json",
        {"results": {}},
    )

    _write_json(
        raw / "pip_licenses.json",
        [
            {
                "Name": "alpha",
                "Version": "1.0.0",
                "License": "MIT",
                "URL": ("https://example.invalid/alpha"),
            }
        ],
    )

    for scanner_name in (
        "pip_audit",
        "bandit",
        "detect_secrets",
        "pip_licenses",
    ):
        (raw / f"{scanner_name}.exit_code").write_text(
            "0\n",
            encoding="utf-8",
        )

    return tmp_path


def test_clean_scanner_state_passes_security_gate(
    tmp_path: Path,
    monkeypatch,
) -> None:
    project = _project(tmp_path)

    monkeypatch.setattr(
        "cre_foundry.devsecops_scanner_control_plane.version",
        lambda package: TOOLCHAIN[package],
    )

    result = build_devsecops_scanner_control_plane(
        project,
        raw_directory=(project / "logs" / "security_scans"),
        history_findings_override=[],
        write_contracts=False,
    )

    summary = result["summary"]

    assert summary["scanner_execution_error_count"] == 0

    assert summary["blocking_finding_count"] == 0

    assert summary["scanner_control_plane_operational"] is True

    assert summary["security_gate_passed"] is True

    assert summary["overall_release_eligible"] is False


def test_dependency_vulnerability_blocks_gate(
    tmp_path: Path,
    monkeypatch,
) -> None:
    project = _project(tmp_path)

    raw = project / "logs" / "security_scans"

    _write_json(
        raw / "pip_audit.json",
        [
            {
                "name": "alpha",
                "version": "1.0.0",
                "vulns": [
                    {
                        "id": "TEST-2026-1",
                        "fix_versions": ["1.0.1"],
                        "aliases": [],
                    }
                ],
            }
        ],
    )

    (raw / "pip_audit.exit_code").write_text(
        "1\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(
        "cre_foundry.devsecops_scanner_control_plane.version",
        lambda package: TOOLCHAIN[package],
    )

    result = build_devsecops_scanner_control_plane(
        project,
        raw_directory=raw,
        history_findings_override=[],
        write_contracts=False,
    )

    summary = result["summary"]

    assert summary["scanner_execution_error_count"] == 0

    assert summary["dependency_vulnerability_count"] == 1

    assert summary["blocking_finding_count"] == 1

    assert summary["security_gate_passed"] is False


def test_mutable_ci_action_is_rejected(
    tmp_path: Path,
    monkeypatch,
) -> None:
    project = _project(tmp_path)

    workflow = project / ".github" / "workflows" / "security-audit.yml"

    text = workflow.read_text(encoding="utf-8").replace(
        "actions/checkout@" + "a" * 40,
        "actions/checkout@v7",
    )

    workflow.write_text(
        text,
        encoding="utf-8",
    )

    monkeypatch.setattr(
        "cre_foundry.devsecops_scanner_control_plane.version",
        lambda package: TOOLCHAIN[package],
    )

    result = build_devsecops_scanner_control_plane(
        project,
        raw_directory=(project / "logs" / "security_scans"),
        history_findings_override=[],
        write_contracts=False,
    )

    assert result["ci"]["policy_passed"] is False

    assert any(
        violation.startswith("mutable-action-reference:")
        for violation in result["ci"]["violations"]
    )

    assert result["summary"]["scanner_control_plane_operational"] is False


def test_sbom_drift_is_detected(
    tmp_path: Path,
    monkeypatch,
) -> None:
    project = _project(tmp_path)

    _write_json(
        project / "docs" / "security" / "software_bill_of_materials.cdx.json",
        {
            "bomFormat": "CycloneDX",
            "specVersion": "1.7",
            "components": [],
        },
    )

    monkeypatch.setattr(
        "cre_foundry.devsecops_scanner_control_plane.version",
        lambda package: TOOLCHAIN[package],
    )

    result = build_devsecops_scanner_control_plane(
        project,
        raw_directory=(project / "logs" / "security_scans"),
        history_findings_override=[],
        write_contracts=False,
    )

    assert result["sbom"]["missing_from_sbom_count"] == 1

    assert result["sbom"]["reconciliation_passed"] is False

    assert result["summary"]["scanner_control_plane_operational"] is False


def test_history_override_metadata_is_commit_independent(
    tmp_path: Path,
    monkeypatch,
) -> None:
    project = _project(tmp_path)

    monkeypatch.setattr(
        "cre_foundry.devsecops_scanner_control_plane.version",
        lambda package: TOOLCHAIN[package],
    )

    result = build_devsecops_scanner_control_plane(
        project,
        raw_directory=(project / "logs" / "security_scans"),
        history_findings_override=[],
        write_contracts=False,
    )

    history_scan = result["secrets"]["history_scan"]

    assert history_scan["revision_scope"] == "synthetic_override"

    assert history_scan["scan_completed"] is True

    assert "commit_count" not in history_scan
    assert "git_command_count" not in history_scan


def test_history_scan_uses_explicit_pattern_flag(
    tmp_path: Path,
    monkeypatch,
) -> None:
    import subprocess

    import cre_foundry.devsecops_scanner_control_plane as scanner_module

    calls: list[list[str]] = []

    def fake_run(
        arguments: list[str],
        **kwargs: object,
    ) -> subprocess.CompletedProcess[str]:
        del kwargs

        calls.append(list(arguments))

        if arguments[:3] == [
            "git",
            "rev-list",
            "--all",
        ]:
            return subprocess.CompletedProcess(
                arguments,
                0,
                stdout="abc123\n",
                stderr="",
            )

        return subprocess.CompletedProcess(
            arguments,
            1,
            stdout="",
            stderr="",
        )

    monkeypatch.setattr(
        scanner_module,
        "HISTORY_PATTERNS",
        [
            {
                "pattern_id": ("leading_hyphen_pattern"),
                "expression": ("---BEGIN TEST PATTERN---"),
                "severity": "critical",
                "blocking": True,
            }
        ],
    )

    monkeypatch.setattr(
        scanner_module.subprocess,
        "run",
        fake_run,
    )

    report = scanner_module._scan_git_history(
        tmp_path,
        maximum_findings=10,
        excluded_prefixes=[],
    )

    assert report["scan_completed"] is True

    assert report["finding_count"] == 0

    assert len(calls) == 2

    grep_command = calls[1]

    expression_index = grep_command.index("---BEGIN TEST PATTERN---")

    assert grep_command[expression_index - 1] == "-e"
