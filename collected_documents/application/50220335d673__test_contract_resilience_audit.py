from __future__ import annotations

import json
from pathlib import Path

from cre_foundry.contract_resilience_audit import (
    EXPECTED_POLICY,
    build_contract_resilience_audit,
)


def _write_json(
    path: Path,
    payload: dict[str, object],
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
        tmp_path / "config" / "governance_decisions.json",
        {
            "decision_bundle_version": ("cre-foundry-governance-decisions-v1"),
            "source_decisions": [
                {
                    "source_id": "source-1",
                    "evidence_bundle_digest": ("a" * 64),
                    "parser_contract_approved": False,
                    "schema_contract_approved": False,
                    "approved_record_key": None,
                    "approved_temporal_fields": [],
                    "capture_policy_approved": False,
                    "change_contract_approved": False,
                    "registration_approved": False,
                    "reviewer_id": None,
                    "reviewed_at": None,
                    "evidence_reference": None,
                }
            ],
            "client_inputs": [
                {
                    "input_id": "input-1",
                    "authoritative_value": None,
                    "confirmed": False,
                    "confirmed_by": None,
                    "confirmed_at": None,
                    "evidence_reference": None,
                }
            ],
        },
    )

    evidence_path = tmp_path / "evidence.json"

    _write_json(
        evidence_path,
        {"model_version": "evidence-v1"},
    )

    _write_json(
        tmp_path / "config" / "contract_resilience_audit.json",
        {
            "config_version": ("cre-foundry-contract-resilience-audit-v1"),
            "policy": EXPECTED_POLICY,
            "seed": 1234,
            "decision_fuzz_case_count": 64,
            "serialization_case_count": 128,
            "max_generated_depth": 4,
            "standards_baseline": [
                {
                    "standard_id": "nist-ssdf-1.1",
                    "version": "1.1",
                },
                {
                    "standard_id": "owasp-asvs-5.0.0",
                    "version": "5.0.0",
                },
                {
                    "standard_id": "slsa-1.2",
                    "version": "1.2",
                },
                {
                    "standard_id": "cyclonedx-1.7",
                    "version": "1.7",
                },
            ],
            "evidence_paths": ["evidence.json"],
        },
    )

    (tmp_path / "pyproject.toml").write_text(
        "\n".join(
            [
                "[project]",
                'name = "cre-foundry"',
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
                "[[package]]",
                'name = "beta"',
                'version = "2.0.0"',
                "",
            ]
        ),
        encoding="utf-8",
    )

    return tmp_path


def test_fuzzing_and_serialization_pass(
    tmp_path: Path,
) -> None:
    result = build_contract_resilience_audit(
        _project(tmp_path),
        write_contracts=False,
    )

    fuzz = result["fuzz"]

    serialization = result["serialization"]

    assert fuzz["malformed_case_count"] == 64

    assert fuzz["rejected_malformed_case_count"] == 64

    assert fuzz["escaped_malformed_case_count"] == 0

    assert fuzz["all_properties_passed"] is True

    assert serialization["case_count"] == 128

    assert serialization["successful_round_trip_count"] == 128

    assert serialization["stable_digest_count"] == 128

    assert serialization["rejected_negative_case_count"] == 5

    assert serialization["all_properties_passed"] is True


def test_atomic_recovery_is_fail_safe(
    tmp_path: Path,
) -> None:
    result = build_contract_resilience_audit(
        _project(tmp_path),
        write_contracts=False,
    )

    recovery = result["atomic_recovery"]

    assert recovery["scenario_count"] == 6

    assert recovery["passed_scenario_count"] == 6

    assert recovery["failed_scenario_count"] == 0

    assert recovery["temporary_rehearsal_deleted"] is True

    assert recovery["project_file_mutation_count"] == 0


def test_versions_migration_and_sbom(
    tmp_path: Path,
) -> None:
    result = build_contract_resilience_audit(
        _project(tmp_path),
        write_contracts=False,
    )

    compatibility = result["compatibility"]

    sbom = result["sbom"]

    assert compatibility["unversioned_document_count"] == 0

    assert compatibility["ambiguous_version_field_count"] == 0

    assert compatibility["future_version_rejected"] is True

    assert compatibility["missing_version_rejected"] is True

    assert compatibility["migration_reproducible"] is True

    assert sbom["bomFormat"] == "CycloneDX"

    assert sbom["specVersion"] == "1.7"

    assert len(sbom["components"]) == 2


def test_audit_spine_does_not_claim_compliance(
    tmp_path: Path,
) -> None:
    result = build_contract_resilience_audit(
        _project(tmp_path),
        write_contracts=False,
    )

    summary = result["summary"]

    controls = result["controls"]

    steelman = result["steelman"]

    assert summary["all_resilience_properties_passed"] is True

    assert summary["compliance_claimed"] is False

    assert summary["certification_claimed"] is False

    assert summary["independent_audit_complete"] is False

    assert controls["control_count"] == 28

    assert controls["compliance_claimed"] is False

    assert steelman["phase_count"] == 10

    assert steelman["default_release_decision"] == "rejected"

    assert steelman["audit_complete"] is False
