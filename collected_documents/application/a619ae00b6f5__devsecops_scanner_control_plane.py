from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import tempfile
import tomllib
from datetime import UTC, datetime
from importlib.metadata import version
from pathlib import Path
from typing import Any

import yaml

EXPECTED_POLICY: dict[str, Any] = {
    "operating_mode": "shadow",
    "scanner_execution_required": True,
    "machine_readable_results_required": True,
    "finding_normalization_required": True,
    "deterministic_fingerprints_required": True,
    "git_history_secret_scan_required": True,
    "sbom_lockfile_reconciliation_required": True,
    "ci_least_privilege_required": True,
    "immutable_action_pinning_required": True,
    "suppression_governance_required": True,
    "silent_suppressions_forbidden": True,
    "expired_suppressions_forbidden": True,
    "wildcard_suppressions_forbidden": True,
    "raw_secret_persistence_forbidden": True,
    "critical_secret_suppression_forbidden": True,
    "network_access_scope": ("pip-audit-vulnerability-service-only"),
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


SUPPRESSION_FIELDS = {
    "suppression_id",
    "scanner",
    "finding_fingerprint",
    "rationale",
    "owner",
    "approved_by",
    "created_at",
    "expires_at",
    "evidence_reference",
}


HISTORY_PATTERNS = [
    {
        "pattern_id": "private_key",
        "expression": ("-----BEGIN (RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----"),
        "severity": "critical",
        "blocking": True,
    },
    {
        "pattern_id": "aws_access_key",
        "expression": "AKIA[0-9A-Z]{16}",
        "severity": "critical",
        "blocking": True,
    },
    {
        "pattern_id": "github_token",
        "expression": ("gh[pousr]_[A-Za-z0-9_]{20,}"),
        "severity": "critical",
        "blocking": True,
    },
    {
        "pattern_id": "openai_key",
        "expression": ("sk-[A-Za-z0-9]{20,}"),
        "severity": "critical",
        "blocking": True,
    },
    {
        "pattern_id": "slack_token",
        "expression": ("xox[baprs]-[A-Za-z0-9-]{10,}"),
        "severity": "critical",
        "blocking": True,
    },
    {
        "pattern_id": "stripe_secret",
        "expression": ("sk_(live|test)_[A-Za-z0-9]{16,}"),
        "severity": "critical",
        "blocking": True,
    },
    {
        "pattern_id": "generic_secret_assignment",
        "expression": (
            "(password|passwd|secret|api[_-]?key|token)"
            "[[:space:]]*[:=][[:space:]]*"
            "[\"'][^\"']{8,}[\"']"
        ),
        "severity": "review",
        "blocking": False,
    },
]


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

    if not isinstance(
        raw,
        dict,
    ):
        raise RuntimeError(f"Expected JSON object: {path}")

    return {str(key): value for key, value in raw.items()}


def _load_json(
    path: Path,
) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _object_list(
    value: object,
    *,
    label: str,
) -> list[dict[str, Any]]:
    if not isinstance(
        value,
        list,
    ):
        raise RuntimeError(f"{label} must be a list.")

    rows: list[dict[str, Any]] = []

    for index, raw_row in enumerate(value):
        if not isinstance(
            raw_row,
            dict,
        ):
            raise RuntimeError(f"{label}[{index}] must be an object.")

        rows.append({str(key): row_value for key, row_value in raw_row.items()})

    return rows


def _string_list(
    value: object,
    *,
    label: str,
) -> list[str]:
    if not isinstance(
        value,
        list,
    ):
        raise RuntimeError(f"{label} must be a list.")

    values: list[str] = []

    for index, raw_value in enumerate(value):
        if not isinstance(
            raw_value,
            str,
        ):
            raise RuntimeError(f"{label}[{index}] must be a string.")

        values.append(raw_value)

    return values


def _canonical_name(
    value: str,
) -> str:
    return re.sub(
        r"[-_.]+",
        "-",
        value.strip().lower(),
    )


def _fingerprint(
    scanner: str,
    *parts: object,
) -> str:
    canonical = json.dumps(
        [
            scanner,
            *parts,
        ],
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        default=str,
    ).encode("utf-8")

    return hashlib.sha256(canonical).hexdigest()


def _read_exit_code(
    path: Path,
) -> int:
    raw = path.read_text(encoding="utf-8").strip()

    try:
        return int(raw)

    except ValueError as error:
        raise RuntimeError(f"Invalid scanner exit code: {path}") from error


def _toolchain_report(
    expected_versions: dict[str, Any],
    raw_versions: dict[str, Any],
) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []

    for package in sorted(expected_versions):
        expected = str(expected_versions[package])

        installed = version(package)

        reported = raw_versions.get(package)

        rows.append(
            {
                "package": package,
                "expected_version": expected,
                "installed_version": installed,
                "reported_version": reported,
                "installed_match": bool(installed == expected),
                "reported_match": bool(reported == expected),
            }
        )

    return {
        "model_version": ("cre-foundry-scanner-toolchain-manifest-v1"),
        "tool_count": len(rows),
        "version_mismatch_count": sum(
            not bool(row["installed_match"] and row["reported_match"]) for row in rows
        ),
        "tools": rows,
    }


def _base_finding(
    *,
    scanner: str,
    category: str,
    severity: str,
    confidence: str,
    title: str,
    component: str | None,
    location: str | None,
    advisory_id: str | None,
    blocking: bool,
    fingerprint_parts: list[object],
    metadata: dict[str, Any],
) -> dict[str, Any]:
    fingerprint = _fingerprint(
        scanner,
        *fingerprint_parts,
    )

    return {
        "finding_fingerprint": fingerprint,
        "scanner": scanner,
        "category": category,
        "severity": severity,
        "confidence": confidence,
        "title": title,
        "component": component,
        "location": location,
        "advisory_id": advisory_id,
        "blocking_by_policy": blocking,
        "suppressed": False,
        "suppression_id": None,
        "metadata": metadata,
    }


def _parse_pip_audit(
    raw: object,
) -> list[dict[str, Any]]:
    dependencies_raw = raw.get("dependencies", []) if isinstance(raw, dict) else raw

    dependencies = _object_list(
        dependencies_raw,
        label="pip-audit dependencies",
    )

    findings: list[dict[str, Any]] = []

    for dependency in dependencies:
        name = str(
            dependency.get(
                "name",
                "unknown",
            )
        )

        installed_version = str(
            dependency.get(
                "version",
                "unknown",
            )
        )

        vulnerabilities = _object_list(
            dependency.get(
                "vulns",
                [],
            ),
            label=f"{name}.vulns",
        )

        for vulnerability in vulnerabilities:
            advisory_id = str(
                vulnerability.get(
                    "id",
                    "unknown-advisory",
                )
            )

            fix_versions = _string_list(
                vulnerability.get(
                    "fix_versions",
                    [],
                ),
                label=(f"{name}.{advisory_id}.fix_versions"),
            )

            aliases = _string_list(
                vulnerability.get(
                    "aliases",
                    [],
                ),
                label=(f"{name}.{advisory_id}.aliases"),
            )

            findings.append(
                _base_finding(
                    scanner="pip-audit",
                    category=("dependency_vulnerability"),
                    severity="unknown",
                    confidence="high",
                    title=(f"{name} {installed_version} is affected by {advisory_id}"),
                    component=(f"{name}=={installed_version}"),
                    location="uv.lock/.venv",
                    advisory_id=advisory_id,
                    blocking=True,
                    fingerprint_parts=[
                        name,
                        installed_version,
                        advisory_id,
                    ],
                    metadata={
                        "fix_versions": (fix_versions),
                        "aliases": aliases,
                        "fix_available": bool(fix_versions),
                    },
                )
            )

    return findings


def _parse_bandit(
    raw: object,
    *,
    blocking_severities: set[str],
    blocking_confidences: set[str],
) -> list[dict[str, Any]]:
    if not isinstance(
        raw,
        dict,
    ):
        raise RuntimeError("Bandit report must be an object.")

    results = _object_list(
        raw.get(
            "results",
            [],
        ),
        label="bandit results",
    )

    findings: list[dict[str, Any]] = []

    for result in results:
        severity = str(
            result.get(
                "issue_severity",
                "unknown",
            )
        ).lower()

        confidence = str(
            result.get(
                "issue_confidence",
                "unknown",
            )
        ).lower()

        test_id = str(
            result.get(
                "test_id",
                "unknown-test",
            )
        )

        filename = str(
            result.get(
                "filename",
                "unknown-file",
            )
        )

        line_number = int(
            result.get(
                "line_number",
                0,
            )
        )

        issue_text = str(
            result.get(
                "issue_text",
                "Bandit finding",
            )
        )

        blocking = bool(severity in blocking_severities and confidence in blocking_confidences)

        findings.append(
            _base_finding(
                scanner="bandit",
                category="static_analysis",
                severity=severity,
                confidence=confidence,
                title=(f"{test_id}: {issue_text}"),
                component=None,
                location=(f"{filename}:{line_number}"),
                advisory_id=test_id,
                blocking=blocking,
                fingerprint_parts=[
                    test_id,
                    filename,
                    line_number,
                    issue_text,
                ],
                metadata={
                    "more_info": result.get("more_info"),
                },
            )
        )

    return findings


def _parse_detect_secrets(
    raw: object,
    *,
    critical_detectors: set[str],
) -> list[dict[str, Any]]:
    if not isinstance(
        raw,
        dict,
    ):
        raise RuntimeError("detect-secrets report must be an object.")

    raw_results = raw.get(
        "results",
        {},
    )

    if not isinstance(
        raw_results,
        dict,
    ):
        raise RuntimeError("detect-secrets results must be an object.")

    findings: list[dict[str, Any]] = []

    for raw_path, raw_rows in sorted(
        raw_results.items(),
        key=lambda item: str(item[0]),
    ):
        path = str(raw_path)

        rows = _object_list(
            raw_rows,
            label=f"detect-secrets.{path}",
        )

        for row in rows:
            detector_type = str(
                row.get(
                    "type",
                    "unknown-detector",
                )
            )

            line_number = int(
                row.get(
                    "line_number",
                    0,
                )
            )

            hashed_secret = str(
                row.get(
                    "hashed_secret",
                    "",
                )
            )

            blocking = detector_type in (critical_detectors)

            findings.append(
                _base_finding(
                    scanner="detect-secrets",
                    category="secret_worktree",
                    severity=("critical" if blocking else "review"),
                    confidence=("high" if blocking else "review"),
                    title=(f"Potential secret detected by {detector_type}"),
                    component=None,
                    location=(f"{path}:{line_number}"),
                    advisory_id=detector_type,
                    blocking=blocking,
                    fingerprint_parts=[
                        detector_type,
                        path,
                        line_number,
                        hashed_secret,
                    ],
                    metadata={
                        "detector_type": (detector_type),
                        "secret_value_persisted": False,
                    },
                )
            )

    return findings


def _scan_git_history(
    project_root: Path,
    *,
    maximum_findings: int,
    excluded_prefixes: list[str],
) -> dict[str, Any]:
    revision_result = subprocess.run(
        [
            "git",
            "rev-list",
            "--all",
        ],
        cwd=project_root,
        check=True,
        capture_output=True,
        text=True,
    )

    commits = [line.strip() for line in revision_result.stdout.splitlines() if line.strip()]

    findings_by_fingerprint: dict[str, dict[str, Any]] = {}

    truncated = False

    for pattern in HISTORY_PATTERNS:
        expression = str(pattern["expression"])

        for commit in commits:
            result = subprocess.run(
                [
                    "git",
                    "grep",
                    "-n",
                    "-I",
                    "-E",
                    "-e",
                    expression,
                    commit,
                    "--",
                    ".",
                ],
                cwd=project_root,
                check=False,
                capture_output=True,
                text=True,
                errors="replace",
            )

            if result.returncode not in {
                0,
                1,
            }:
                raise RuntimeError(
                    "Git-history scan failed for "
                    f"{pattern['pattern_id']} "
                    f"at {commit}: "
                    f"{result.stderr.strip()}"
                )

            if result.returncode == 1:
                continue

            for raw_line in result.stdout.splitlines():
                parts = raw_line.split(
                    ":",
                    maxsplit=3,
                )

                if len(parts) != 4:
                    continue

                raw_commit, path, raw_line_number, content = parts

                if any(path.startswith(prefix) for prefix in excluded_prefixes):
                    continue

                try:
                    line_number = int(raw_line_number)

                except ValueError:
                    continue

                content_digest = hashlib.sha256(
                    content.encode(
                        "utf-8",
                        errors="replace",
                    )
                ).hexdigest()

                finding = _base_finding(
                    scanner=("git-history-secret-scan"),
                    category="secret_history",
                    severity=str(pattern["severity"]),
                    confidence=("high" if bool(pattern["blocking"]) else "review"),
                    title=(f"Potential historical secret: {pattern['pattern_id']}"),
                    component=None,
                    location=(f"{path}:{line_number}"),
                    advisory_id=str(pattern["pattern_id"]),
                    blocking=bool(pattern["blocking"]),
                    fingerprint_parts=[
                        pattern["pattern_id"],
                        path,
                        line_number,
                        content_digest,
                    ],
                    metadata={
                        "first_observed_commit": (raw_commit),
                        "content_sha256": (content_digest),
                        "secret_value_persisted": False,
                    },
                )

                fingerprint = str(finding["finding_fingerprint"])

                findings_by_fingerprint[fingerprint] = finding

                if len(findings_by_fingerprint) >= maximum_findings:
                    truncated = True
                    break

            if truncated:
                break

        if truncated:
            break

    findings = [findings_by_fingerprint[key] for key in sorted(findings_by_fingerprint)]

    return {
        "model_version": ("cre-foundry-git-history-secret-scan-v1"),
        "revision_scope": "all_reachable_commits",
        "scan_completed": True,
        "pattern_count": len(HISTORY_PATTERNS),
        "finding_count": len(findings),
        "blocking_finding_count": sum(bool(finding["blocking_by_policy"]) for finding in findings),
        "truncated": truncated,
        "raw_secret_persistence_count": 0,
        "findings": findings,
    }


def _parse_licenses(
    raw: object,
    *,
    prohibited_markers: list[str],
    review_markers: list[str],
) -> tuple[
    dict[str, Any],
    list[dict[str, Any]],
]:
    rows = _object_list(
        raw,
        label="pip-licenses output",
    )

    packages: list[dict[str, Any]] = []
    findings: list[dict[str, Any]] = []

    for row in rows:
        name = str(
            row.get(
                "Name",
                row.get(
                    "name",
                    "unknown",
                ),
            )
        )

        package_version = str(
            row.get(
                "Version",
                row.get(
                    "version",
                    "unknown",
                ),
            )
        )

        license_name = str(
            row.get(
                "License",
                row.get(
                    "license",
                    "UNKNOWN",
                ),
            )
        )

        url = row.get(
            "URL",
            row.get(
                "url",
            ),
        )

        upper_license = license_name.upper()

        prohibited_matches = [
            marker for marker in prohibited_markers if marker.upper() in upper_license
        ]

        review_matches = [marker for marker in review_markers if marker.upper() in upper_license]

        risk = "allowed"

        if prohibited_matches:
            risk = "prohibited"

        elif review_matches:
            risk = "review"

        package_row = {
            "name": name,
            "version": package_version,
            "license": license_name,
            "url": url,
            "risk": risk,
            "prohibited_matches": (prohibited_matches),
            "review_matches": review_matches,
        }

        packages.append(package_row)

        if risk in {
            "prohibited",
            "review",
        }:
            findings.append(
                _base_finding(
                    scanner="pip-licenses",
                    category="license_risk",
                    severity=("high" if risk == "prohibited" else "review"),
                    confidence="medium",
                    title=(f"{name} {package_version} uses {license_name}"),
                    component=(f"{name}=={package_version}"),
                    location="installed environment",
                    advisory_id=None,
                    blocking=bool(risk == "prohibited"),
                    fingerprint_parts=[
                        name,
                        package_version,
                        license_name,
                    ],
                    metadata={
                        "risk": risk,
                        "url": url,
                    },
                )
            )

    packages.sort(
        key=lambda row: (
            str(row["name"]).lower(),
            str(row["version"]),
        )
    )

    report = {
        "model_version": ("cre-foundry-license-risk-report-v1"),
        "package_count": len(packages),
        "prohibited_package_count": sum(row["risk"] == "prohibited" for row in packages),
        "review_package_count": sum(row["risk"] == "review" for row in packages),
        "allowed_package_count": sum(row["risk"] == "allowed" for row in packages),
        "packages": packages,
    }

    return report, findings


def _lock_components(
    project_root: Path,
) -> set[tuple[str, str]]:
    raw = tomllib.loads((project_root / "uv.lock").read_text(encoding="utf-8"))

    raw_packages = raw.get(
        "package",
        [],
    )

    if not isinstance(
        raw_packages,
        list,
    ):
        raise RuntimeError("uv.lock package list is invalid.")

    components: set[tuple[str, str]] = set()

    for raw_package in raw_packages:
        if not isinstance(
            raw_package,
            dict,
        ):
            continue

        name = raw_package.get("name")

        package_version = raw_package.get("version")

        if isinstance(
            name,
            str,
        ) and isinstance(
            package_version,
            str,
        ):
            components.add(
                (
                    _canonical_name(name),
                    package_version,
                )
            )

    return components


def _sbom_components(
    sbom: dict[str, Any],
) -> tuple[
    set[tuple[str, str]],
    int,
]:
    raw_components = _object_list(
        sbom.get(
            "components",
            [],
        ),
        label="SBOM components",
    )

    components: set[tuple[str, str]] = set()

    duplicate_count = 0

    for row in raw_components:
        name = row.get("name")

        package_version = row.get("version")

        if not isinstance(
            name,
            str,
        ) or not isinstance(
            package_version,
            str,
        ):
            continue

        identity = (
            _canonical_name(name),
            package_version,
        )

        if identity in components:
            duplicate_count += 1

        components.add(identity)

    return components, duplicate_count


def _sbom_reconciliation(
    project_root: Path,
) -> dict[str, Any]:
    sbom = _load_object(project_root / "docs" / "security" / "software_bill_of_materials.cdx.json")

    lock_components = _lock_components(project_root)

    (
        sbom_components,
        duplicate_count,
    ) = _sbom_components(sbom)

    missing_from_sbom = sorted(lock_components - sbom_components)

    extra_in_sbom = sorted(sbom_components - lock_components)

    return {
        "model_version": ("cre-foundry-sbom-reconciliation-v1"),
        "lock_component_count": len(lock_components),
        "sbom_component_count": len(sbom_components),
        "missing_from_sbom_count": len(missing_from_sbom),
        "extra_in_sbom_count": len(extra_in_sbom),
        "duplicate_sbom_component_count": (duplicate_count),
        "missing_from_sbom": [
            {
                "name": name,
                "version": package_version,
            }
            for name, package_version in missing_from_sbom
        ],
        "extra_in_sbom": [
            {
                "name": name,
                "version": package_version,
            }
            for name, package_version in extra_in_sbom
        ],
        "reconciliation_passed": bool(
            not missing_from_sbom and not extra_in_sbom and duplicate_count == 0
        ),
    }


def _permission_violations(
    value: object,
    *,
    label: str,
) -> list[str]:
    if not isinstance(
        value,
        dict,
    ):
        return [f"{label}:permissions-missing-or-invalid"]

    violations: list[str] = []

    for raw_scope, raw_permission in value.items():
        scope = str(raw_scope)
        permission = str(raw_permission).lower()

        if scope != "contents" or permission != "read":
            violations.append(f"{label}:{scope}={permission}")

    if value.get("contents") != "read":
        violations.append(f"{label}:contents-read-required")

    return sorted(set(violations))


def _ci_policy_report(
    project_root: Path,
    ci_policy: dict[str, Any],
) -> dict[str, Any]:
    relative_path = str(ci_policy["required_workflow_path"])

    workflow_path = project_root / relative_path

    violations: list[str] = []

    if not workflow_path.is_file():
        return {
            "model_version": ("cre-foundry-ci-workflow-policy-v1"),
            "workflow_path": relative_path,
            "workflow_present": False,
            "violation_count": 1,
            "violations": ["required-workflow-missing"],
            "action_reference_count": 0,
            "pinned_action_reference_count": 0,
            "policy_passed": False,
        }

    raw = yaml.safe_load(workflow_path.read_text(encoding="utf-8"))

    if not isinstance(
        raw,
        dict,
    ):
        raise RuntimeError("CI workflow must be a mapping.")

    violations.extend(
        _permission_violations(
            raw.get("permissions"),
            label="workflow",
        )
    )

    workflow_text = workflow_path.read_text(encoding="utf-8")

    for forbidden_trigger in _string_list(
        ci_policy.get(
            "forbidden_triggers",
            [],
        ),
        label="forbidden_triggers",
    ):
        if re.search(
            rf"(?m)^[ \t]*"
            rf"{re.escape(forbidden_trigger)}"
            rf"[ \t]*:",
            workflow_text,
        ):
            violations.append(f"forbidden-trigger:{forbidden_trigger}")

    jobs = raw.get("jobs")

    if (
        not isinstance(
            jobs,
            dict,
        )
        or not jobs
    ):
        violations.append("workflow-jobs-missing")
        jobs = {}

    action_references: list[str] = []
    run_commands: list[str] = []
    checkout_persist_credentials_values: list[object] = []

    maximum_timeout = int(ci_policy["maximum_timeout_minutes"])

    for raw_job_name, raw_job in jobs.items():
        job_name = str(raw_job_name)

        if not isinstance(
            raw_job,
            dict,
        ):
            violations.append(f"job-invalid:{job_name}")
            continue

        violations.extend(
            _permission_violations(
                raw_job.get("permissions"),
                label=f"job:{job_name}",
            )
        )

        timeout = raw_job.get("timeout-minutes")

        if (
            not isinstance(
                timeout,
                int,
            )
            or timeout <= 0
            or timeout > maximum_timeout
        ):
            violations.append(f"job-timeout-invalid:{job_name}")

        raw_steps = raw_job.get(
            "steps",
            [],
        )

        if not isinstance(
            raw_steps,
            list,
        ):
            violations.append(f"job-steps-invalid:{job_name}")
            continue

        for raw_step in raw_steps:
            if not isinstance(
                raw_step,
                dict,
            ):
                continue

            uses = raw_step.get("uses")

            if isinstance(
                uses,
                str,
            ):
                action_references.append(uses)

                if not re.fullmatch(
                    r"[^@\s]+@[0-9a-f]{40}",
                    uses,
                ):
                    violations.append(f"mutable-action-reference:{uses}")

                if uses.startswith("actions/checkout@"):
                    raw_with = raw_step.get(
                        "with",
                        {},
                    )

                    if isinstance(
                        raw_with,
                        dict,
                    ):
                        checkout_persist_credentials_values.append(
                            raw_with.get("persist-credentials")
                        )

                    else:
                        checkout_persist_credentials_values.append(None)

            run = raw_step.get("run")

            if isinstance(
                run,
                str,
            ):
                run_commands.append(run.strip())

                if re.search(
                    r"\bcurl\b.*\|\s*(bash|sh)\b",
                    run,
                ):
                    violations.append("curl-pipe-shell-detected")

    if not action_references:
        violations.append("no-action-references")

    if not checkout_persist_credentials_values:
        violations.append("checkout-step-missing")

    elif any(value is not False for value in checkout_persist_credentials_values):
        violations.append("checkout-credentials-persisted")

    required_commands = _string_list(
        ci_policy.get(
            "required_commands",
            [],
        ),
        label="required_commands",
    )

    combined_runs = "\n".join(run_commands)

    for required_command in required_commands:
        if required_command not in combined_runs:
            violations.append(f"required-command-missing:{required_command}")

    pinned_count = sum(
        bool(
            re.fullmatch(
                r"[^@\s]+@[0-9a-f]{40}",
                reference,
            )
        )
        for reference in action_references
    )

    return {
        "model_version": ("cre-foundry-ci-workflow-policy-v1"),
        "workflow_path": relative_path,
        "workflow_present": True,
        "action_reference_count": len(action_references),
        "pinned_action_reference_count": (pinned_count),
        "violation_count": len(sorted(set(violations))),
        "violations": sorted(set(violations)),
        "policy_passed": bool(not violations),
    }


def _parse_timestamp(
    value: object,
    *,
    label: str,
) -> datetime:
    if not isinstance(
        value,
        str,
    ):
        raise RuntimeError(f"{label} must be a timestamp string.")

    try:
        parsed = datetime.fromisoformat(
            value.replace(
                "Z",
                "+00:00",
            )
        )

    except ValueError as error:
        raise RuntimeError(f"{label} is invalid.") from error

    if parsed.tzinfo is None:
        raise RuntimeError(f"{label} must contain a timezone.")

    return parsed.astimezone(UTC)


def _inline_suppressions(
    project_root: Path,
) -> list[dict[str, Any]]:
    roots = [
        project_root / "src",
        project_root / "scripts",
        project_root / "tests",
        project_root / ".github",
    ]

    patterns = [
        (
            "bandit-nosec",
            re.compile(
                r"#\s*nosec\b",
                re.IGNORECASE,
            ),
        ),
        (
            "secret-inline-allowlist",
            re.compile(
                r"pragma:\s*allowlist"
                r"(?:\s+nextline)?\s+secret",
                re.IGNORECASE,
            ),
        ),
    ]

    rows: list[dict[str, Any]] = []

    for root in roots:
        if not root.exists():
            continue

        for path in root.rglob("*"):
            if not path.is_file() or path.suffix.lower() not in {
                ".py",
                ".sh",
                ".yml",
                ".yaml",
            }:
                continue

            try:
                lines = path.read_text(encoding="utf-8").splitlines()

            except UnicodeDecodeError:
                continue

            relative_path = str(path.relative_to(project_root))

            for line_number, line in enumerate(
                lines,
                start=1,
            ):
                for suppression_type, pattern in patterns:
                    if pattern.search(line):
                        rows.append(
                            {
                                "suppression_type": (suppression_type),
                                "path": (relative_path),
                                "line_number": (line_number),
                                "finding_fingerprint": (
                                    _fingerprint(
                                        "inline-suppression",
                                        suppression_type,
                                        relative_path,
                                        line_number,
                                        line.strip(),
                                    )
                                ),
                            }
                        )

    return rows


def _suppression_governance(
    project_root: Path,
    suppressions_document: dict[str, Any],
    findings: list[dict[str, Any]],
) -> tuple[
    dict[str, Any],
    list[dict[str, Any]],
]:
    if suppressions_document.get("config_version") != "cre-foundry-security-suppressions-v1":
        raise RuntimeError("Unsupported suppression document version.")

    rows = _object_list(
        suppressions_document.get(
            "suppressions",
            [],
        ),
        label="security suppressions",
    )

    now = datetime.now(UTC)

    violations: list[str] = []
    valid_suppressions: dict[tuple[str, str], dict[str, Any]] = {}

    suppression_ids: set[str] = set()

    for index, row in enumerate(rows):
        fields = set(row)

        if fields != SUPPRESSION_FIELDS:
            violations.append(f"suppression-fields-invalid:{index}")
            continue

        suppression_id = str(row["suppression_id"])

        if suppression_id in suppression_ids:
            violations.append(f"duplicate-suppression-id:{suppression_id}")
            continue

        suppression_ids.add(suppression_id)

        scanner = str(row["scanner"])

        fingerprint = str(row["finding_fingerprint"])

        if (
            "*" in scanner
            or "*" in fingerprint
            or re.fullmatch(
                r"[0-9a-f]{64}",
                fingerprint,
            )
            is None
        ):
            violations.append(f"wildcard-or-invalid-suppression:{suppression_id}")
            continue

        required_text_fields = (
            "rationale",
            "owner",
            "approved_by",
            "evidence_reference",
        )

        if any(
            not isinstance(
                row[field],
                str,
            )
            or not str(row[field]).strip()
            for field in required_text_fields
        ):
            violations.append(f"suppression-attribution-invalid:{suppression_id}")
            continue

        if str(row["owner"]).strip() == str(row["approved_by"]).strip():
            violations.append(f"suppression-independent-approval-missing:{suppression_id}")
            continue

        created_at = _parse_timestamp(
            row["created_at"],
            label=(f"{suppression_id}.created_at"),
        )

        expires_at = _parse_timestamp(
            row["expires_at"],
            label=(f"{suppression_id}.expires_at"),
        )

        if expires_at <= created_at:
            violations.append(f"suppression-expiration-invalid:{suppression_id}")
            continue

        if expires_at <= now:
            violations.append(f"suppression-expired:{suppression_id}")
            continue

        key = (
            scanner,
            fingerprint,
        )

        if key in valid_suppressions:
            violations.append(f"duplicate-suppression-target:{suppression_id}")
            continue

        valid_suppressions[key] = row

    findings_by_key = {
        (
            str(finding["scanner"]),
            str(finding["finding_fingerprint"]),
        ): finding
        for finding in findings
    }

    applied_count = 0

    for key, suppression in valid_suppressions.items():
        finding = findings_by_key.get(key)

        suppression_id = str(suppression["suppression_id"])

        if finding is None:
            violations.append(f"orphan-suppression:{suppression_id}")
            continue

        if (
            finding["category"]
            in {
                "secret_worktree",
                "secret_history",
            }
            and finding["blocking_by_policy"]
        ):
            violations.append(f"critical-secret-suppression-forbidden:{suppression_id}")
            continue

        finding["suppressed"] = True

        finding["suppression_id"] = suppression_id

        applied_count += 1

    inline_rows = _inline_suppressions(project_root)

    governed_inline_fingerprints = {
        str(row["finding_fingerprint"])
        for row in rows
        if row.get("scanner") == "inline-suppression"
    }

    ungoverned_inline_rows = [
        row for row in inline_rows if row["finding_fingerprint"] not in governed_inline_fingerprints
    ]

    for row in ungoverned_inline_rows:
        violations.append(f"ungoverned-inline-suppression:{row['path']}:{row['line_number']}")

    report = {
        "model_version": ("cre-foundry-suppression-governance-v1"),
        "declared_suppression_count": len(rows),
        "valid_suppression_count": len(valid_suppressions),
        "applied_suppression_count": (applied_count),
        "inline_suppression_count": len(inline_rows),
        "ungoverned_inline_suppression_count": len(ungoverned_inline_rows),
        "violation_count": len(sorted(set(violations))),
        "violations": sorted(set(violations)),
        "inline_suppressions": (inline_rows),
        "governance_passed": bool(not violations),
    }

    return report, findings


def build_devsecops_scanner_control_plane(
    project_root: Path,
    *,
    raw_directory: Path | None = None,
    history_findings_override: (list[dict[str, Any]] | None) = None,
    write_contracts: bool = True,
) -> dict[str, Any]:
    config = _load_object(project_root / "config" / "devsecops_scanner_control_plane.json")

    raw_policy = config.get("policy")

    if not isinstance(
        raw_policy,
        dict,
    ):
        raise RuntimeError("Scanner policy must be an object.")

    policy = {str(key): value for key, value in raw_policy.items()}

    if policy != EXPECTED_POLICY:
        raise RuntimeError("Scanner-control policy mismatch.")

    raw_toolchain = config.get("toolchain")

    if not isinstance(
        raw_toolchain,
        dict,
    ):
        raise RuntimeError("Toolchain configuration is invalid.")

    toolchain = {str(key): str(value) for key, value in raw_toolchain.items()}

    if raw_directory is None:
        raw_directory = project_root / str(config["raw_report_directory"])

    required_raw_files = {
        "tool_versions": (raw_directory / "tool_versions.json"),
        "pip_audit": (raw_directory / "pip_audit.json"),
        "bandit": (raw_directory / "bandit.json"),
        "detect_secrets": (raw_directory / "detect_secrets.json"),
        "pip_licenses": (raw_directory / "pip_licenses.json"),
    }

    missing_raw_files = [str(path) for path in required_raw_files.values() if not path.is_file()]

    if missing_raw_files:
        raise RuntimeError(f"Scanner raw reports are missing: {missing_raw_files}")

    raw_versions = _load_object(required_raw_files["tool_versions"])

    toolchain_report = _toolchain_report(
        toolchain,
        raw_versions,
    )

    scanner_status_rows: list[dict[str, Any]] = [
        {
            "scanner": "pip-audit",
            "exit_code": _read_exit_code(raw_directory / "pip_audit.exit_code"),
            "accepted_exit_codes": [
                0,
                1,
            ],
        },
        {
            "scanner": "bandit",
            "exit_code": _read_exit_code(raw_directory / "bandit.exit_code"),
            "accepted_exit_codes": [
                0,
                1,
            ],
        },
        {
            "scanner": "detect-secrets",
            "exit_code": _read_exit_code(raw_directory / "detect_secrets.exit_code"),
            "accepted_exit_codes": [
                0,
            ],
        },
        {
            "scanner": "pip-licenses",
            "exit_code": _read_exit_code(raw_directory / "pip_licenses.exit_code"),
            "accepted_exit_codes": [
                0,
            ],
        },
    ]

    for row in scanner_status_rows:
        row["execution_complete"] = bool(row["exit_code"] in row["accepted_exit_codes"])

    scanner_execution_error_count = sum(
        not bool(row["execution_complete"]) for row in scanner_status_rows
    )

    raw_blocking_policy = config.get("blocking_policy")

    if not isinstance(
        raw_blocking_policy,
        dict,
    ):
        raise RuntimeError("Blocking policy is invalid.")

    blocking_severities = {
        value.lower()
        for value in _string_list(
            raw_blocking_policy.get(
                "bandit_severities",
                [],
            ),
            label="bandit_severities",
        )
    }

    blocking_confidences = {
        value.lower()
        for value in _string_list(
            raw_blocking_policy.get(
                "bandit_confidences",
                [],
            ),
            label="bandit_confidences",
        )
    }

    critical_detectors = set(
        _string_list(
            raw_blocking_policy.get(
                "critical_secret_detectors",
                [],
            ),
            label="critical_secret_detectors",
        )
    )

    findings: list[dict[str, Any]] = []

    findings.extend(_parse_pip_audit(_load_json(required_raw_files["pip_audit"])))

    findings.extend(
        _parse_bandit(
            _load_json(required_raw_files["bandit"]),
            blocking_severities=(blocking_severities),
            blocking_confidences=(blocking_confidences),
        )
    )

    findings.extend(
        _parse_detect_secrets(
            _load_json(required_raw_files["detect_secrets"]),
            critical_detectors=(critical_detectors),
        )
    )

    history_config = config.get("history_scan")

    if not isinstance(
        history_config,
        dict,
    ):
        raise RuntimeError("History scan configuration is invalid.")

    excluded_prefixes = _string_list(
        history_config.get(
            "excluded_path_prefixes",
            [],
        ),
        label="excluded_path_prefixes",
    )

    if history_findings_override is None:
        history_report = _scan_git_history(
            project_root,
            maximum_findings=int(history_config["maximum_findings"]),
            excluded_prefixes=(excluded_prefixes),
        )

    else:
        history_report = {
            "model_version": ("cre-foundry-git-history-secret-scan-v1"),
            "revision_scope": "synthetic_override",
            "scan_completed": True,
            "pattern_count": len(HISTORY_PATTERNS),
            "finding_count": len(history_findings_override),
            "blocking_finding_count": sum(
                bool(finding["blocking_by_policy"]) for finding in history_findings_override
            ),
            "truncated": False,
            "raw_secret_persistence_count": 0,
            "findings": (history_findings_override),
        }

    findings.extend(
        _object_list(
            history_report["findings"],
            label="history findings",
        )
    )

    license_report, license_findings = _parse_licenses(
        _load_json(required_raw_files["pip_licenses"]),
        prohibited_markers=(
            _string_list(
                raw_blocking_policy.get(
                    "prohibited_license_markers",
                    [],
                ),
                label=("prohibited_license_markers"),
            )
        ),
        review_markers=(
            _string_list(
                raw_blocking_policy.get(
                    "review_license_markers",
                    [],
                ),
                label=("review_license_markers"),
            )
        ),
    )

    findings.extend(license_findings)

    suppressions_document = _load_object(project_root / str(config["suppression_path"]))

    (
        suppression_report,
        findings,
    ) = _suppression_governance(
        project_root,
        suppressions_document,
        findings,
    )

    findings.sort(
        key=lambda row: (
            str(row["scanner"]),
            str(row["finding_fingerprint"]),
        )
    )

    duplicate_finding_count = len(findings) - len(
        {
            (
                str(finding["scanner"]),
                str(finding["finding_fingerprint"]),
            )
            for finding in findings
        }
    )

    sbom_report = _sbom_reconciliation(project_root)

    raw_ci_policy = config.get("ci_policy")

    if not isinstance(
        raw_ci_policy,
        dict,
    ):
        raise RuntimeError("CI policy configuration is invalid.")

    ci_report = _ci_policy_report(
        project_root,
        {str(key): value for key, value in raw_ci_policy.items()},
    )

    blocking_findings = [
        finding
        for finding in findings
        if (finding["blocking_by_policy"] and not finding["suppressed"])
    ]

    suppressed_findings = [finding for finding in findings if finding["suppressed"]]

    review_findings = [
        finding
        for finding in findings
        if (not finding["blocking_by_policy"] and not finding["suppressed"])
    ]

    normalized_report = {
        "model_version": ("cre-foundry-devsecops-scanner-findings-v1"),
        "finding_count": len(findings),
        "blocking_finding_count": len(blocking_findings),
        "review_finding_count": len(review_findings),
        "suppressed_finding_count": len(suppressed_findings),
        "duplicate_finding_count": (duplicate_finding_count),
        "findings": findings,
        "raw_secret_value_count": 0,
    }

    dependency_report = {
        "model_version": ("cre-foundry-dependency-vulnerability-report-v1"),
        "finding_count": sum(finding["scanner"] == "pip-audit" for finding in findings),
        "blocking_finding_count": sum(
            finding["scanner"] == "pip-audit"
            and finding["blocking_by_policy"]
            and not finding["suppressed"]
            for finding in findings
        ),
        "findings": [finding for finding in findings if finding["scanner"] == "pip-audit"],
    }

    static_report = {
        "model_version": ("cre-foundry-static-analysis-report-v1"),
        "finding_count": sum(finding["scanner"] == "bandit" for finding in findings),
        "blocking_finding_count": sum(
            finding["scanner"] == "bandit"
            and finding["blocking_by_policy"]
            and not finding["suppressed"]
            for finding in findings
        ),
        "findings": [finding for finding in findings if finding["scanner"] == "bandit"],
    }

    secret_report = {
        "model_version": ("cre-foundry-secret-scan-report-v1"),
        "worktree_finding_count": sum(
            finding["scanner"] == "detect-secrets" for finding in findings
        ),
        "history_finding_count": (history_report["finding_count"]),
        "blocking_finding_count": sum(
            finding["category"]
            in {
                "secret_worktree",
                "secret_history",
            }
            and finding["blocking_by_policy"]
            and not finding["suppressed"]
            for finding in findings
        ),
        "history_scan": {key: value for key, value in history_report.items() if key != "findings"},
        "findings": [
            finding
            for finding in findings
            if finding["category"]
            in {
                "secret_worktree",
                "secret_history",
            }
        ],
        "raw_secret_value_count": 0,
    }

    scanner_control_plane_operational = bool(
        scanner_execution_error_count == 0
        and toolchain_report["version_mismatch_count"] == 0
        and duplicate_finding_count == 0
        and not history_report["truncated"]
        and sbom_report["reconciliation_passed"]
        and ci_report["policy_passed"]
        and suppression_report["governance_passed"]
    )

    security_gate_passed = bool(scanner_control_plane_operational and not blocking_findings)

    summary = {
        "model_version": ("cre-foundry-devsecops-scanner-control-plane-v1"),
        "scanner_count": len(scanner_status_rows) + 1,
        "scanner_execution_error_count": (scanner_execution_error_count),
        "tool_version_mismatch_count": (toolchain_report["version_mismatch_count"]),
        "finding_count": len(findings),
        "blocking_finding_count": len(blocking_findings),
        "review_finding_count": len(review_findings),
        "suppressed_finding_count": len(suppressed_findings),
        "duplicate_finding_count": (duplicate_finding_count),
        "dependency_vulnerability_count": (dependency_report["finding_count"]),
        "bandit_finding_count": (static_report["finding_count"]),
        "worktree_secret_finding_count": (secret_report["worktree_finding_count"]),
        "history_secret_finding_count": (secret_report["history_finding_count"]),
        "prohibited_license_count": (license_report["prohibited_package_count"]),
        "review_license_count": (license_report["review_package_count"]),
        "sbom_missing_component_count": (sbom_report["missing_from_sbom_count"]),
        "sbom_extra_component_count": (sbom_report["extra_in_sbom_count"]),
        "sbom_duplicate_component_count": (sbom_report["duplicate_sbom_component_count"]),
        "ci_policy_violation_count": (ci_report["violation_count"]),
        "suppression_violation_count": (suppression_report["violation_count"]),
        "scanner_control_plane_operational": (scanner_control_plane_operational),
        "security_gate_passed": (security_gate_passed),
        "overall_release_eligible": False,
        "overall_release_blockers": [
            "five_authoritative_client_inputs",
            "named_brampton_permit_review",
            "real_historical_snapshots",
            "real_outcome_labels",
            "point_in_time_dataset",
            "model_backtesting_and_calibration",
            "controlled_pilot",
            "incremental_roi_proof",
            "production_governance",
        ],
        "compliance_claimed": False,
        "certification_claimed": False,
        "independent_audit_complete": False,
        "raw_secret_value_count": 0,
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
        "scanner_statuses": (scanner_status_rows),
        "policy": EXPECTED_POLICY,
    }

    result = {
        "summary": summary,
        "toolchain": toolchain_report,
        "dependency": dependency_report,
        "licenses": license_report,
        "secrets": secret_report,
        "static_analysis": static_report,
        "sbom": sbom_report,
        "ci": ci_report,
        "suppressions": (suppression_report),
        "findings": normalized_report,
    }

    if write_contracts:
        security_root = project_root / "docs" / "security"

        _atomic_json(
            security_root / "scanner_toolchain_manifest.json",
            toolchain_report,
        )

        _atomic_json(
            security_root / "dependency_vulnerability_report.json",
            dependency_report,
        )

        _atomic_json(
            security_root / "license_risk_report.json",
            license_report,
        )

        _atomic_json(
            security_root / "secret_scan_report.json",
            secret_report,
        )

        _atomic_json(
            security_root / "static_analysis_report.json",
            static_report,
        )

        _atomic_json(
            security_root / "sbom_reconciliation_report.json",
            sbom_report,
        )

        _atomic_json(
            security_root / "ci_workflow_policy_report.json",
            ci_report,
        )

        _atomic_json(
            security_root / "suppression_governance_report.json",
            suppression_report,
        )

        _atomic_json(
            security_root / "devsecops_scanner_findings.json",
            normalized_report,
        )

        _atomic_json(
            security_root / "devsecops_scanner_summary.json",
            summary,
        )

        _atomic_text(
            security_root / "devsecops_scanner_control_plane.md",
            "\n".join(
                [
                    "# DevSecOps Scanner Control Plane",
                    "",
                    (
                        "Scanner findings are normalized, "
                        "fingerprinted, retained and subjected "
                        "to governed suppression and release rules."
                    ),
                    "",
                    (f"- Scanners: `{summary['scanner_count']}`"),
                    (f"- Scanner execution errors: `{summary['scanner_execution_error_count']}`"),
                    (f"- Findings: `{summary['finding_count']}`"),
                    (f"- Blocking findings: `{summary['blocking_finding_count']}`"),
                    (f"- Review findings: `{summary['review_finding_count']}`"),
                    (f"- Suppressed findings: `{summary['suppressed_finding_count']}`"),
                    (
                        f"- Dependency vulnerabilities: "
                        f"`{summary['dependency_vulnerability_count']}`"
                    ),
                    (f"- Bandit findings: `{summary['bandit_finding_count']}`"),
                    (f"- Worktree secret findings: `{summary['worktree_secret_finding_count']}`"),
                    (f"- History secret findings: `{summary['history_secret_finding_count']}`"),
                    (f"- Prohibited licenses: `{summary['prohibited_license_count']}`"),
                    (f"- CI policy violations: `{summary['ci_policy_violation_count']}`"),
                    (f"- Suppression violations: `{summary['suppression_violation_count']}`"),
                    (
                        "- Scanner control plane operational: "
                        f"`{str(summary['scanner_control_plane_operational']).lower()}`"
                    ),
                    (f"- Security gate passed: `{str(summary['security_gate_passed']).lower()}`"),
                    "- Overall release eligible: `false`",
                    "",
                    "- Raw secret values persisted: `0`",
                    "- Database accesses: `0`",
                    "- Database writes: `0`",
                    "- Snapshot registrations: `0`",
                    "- Model training executions: `0`",
                    "- Pilot executions: `0`",
                    "- Production rankings: `0`",
                    "- Outreach executions: `0`",
                    "",
                ]
            ),
        )

    return result
