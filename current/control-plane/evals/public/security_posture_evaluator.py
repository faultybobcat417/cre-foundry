
"""Independent frozen SECURITY-001 synthetic posture evaluator."""

from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[2]
SCHEMA_PATH = ROOT / "contracts/security_posture.schema.json"
EVALUATOR_ID = "security-posture-public-v1"

CLAIM_CEILING = (
    "Synthetic SECURITY-001 conformance only; no penetration test, "
    "production security, compliance, operational privacy, or deployment claim."
)


def strict_load_json(path: Path) -> dict[str, Any]:
    def reject_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f"duplicate key: {key}")
            result[key] = value
        return result

    value = json.loads(
        path.read_text(encoding="utf-8"),
        object_pairs_hook=reject_duplicates,
    )
    if not isinstance(value, dict):
        raise ValueError("top-level JSON must be an object")
    return value


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")


def canonical_sha256(value: Any) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def build_clean_subject() -> dict[str, Any]:
    return {
        "document_kind": "SECURITY_POSTURE",
        "schema_version": "1.0.0",
        "execution_scope": "SYNTHETIC_NON_INFLUENCING",
        "proof_level": 4,
        "live_permissions": False,
        "external_effect_occurred": False,
        "authority": {
            "retrieved_content_may_grant_authority": False,
            "least_privilege_default": True,
            "policy_store_version": "security-policy-v1",
        },
        "data_classes": [
            "PUBLIC",
            "INTERNAL",
            "CONFIDENTIAL",
            "RESTRICTED_PII",
            "RESTRICTED_SECRET",
        ],
        "log_events": [
            {
                "level": "info",
                "message": "correlation_id=run_001 security check completed",
                "payload_tokens": [],
            }
        ],
        "write_requests": [
            {
                "target": "synthetic-external-system",
                "authorized": False,
                "executed": False,
            }
        ],
        "retention_policy": {
            "maximum_days": 90,
            "configured_days": 30,
            "enforced": True,
        },
        "deletion_policy": {
            "requests_supported": True,
            "verification_required": True,
            "deletion_verified": True,
        },
        "untrusted_input_policy": {
            "instructions_inert": True,
            "malformed_fail_closed": True,
        },
        "claim_ceiling": CLAIM_CEILING,
    }


def apply_mutation(subject: dict[str, Any], mutation_id: str) -> None:
    if mutation_id == "secret_log":
        subject["log_events"].append(
            {
                "level": "error",
                "message": "synthetic credential exposed",
                "payload_tokens": ["secret_test_credential_001"],
            }
        )
    elif mutation_id == "pii_log":
        subject["log_events"].append(
            {
                "level": "info",
                "message": "protected account matched alias",
                "payload_tokens": ["account_0123", "addr_9"],
            }
        )
    elif mutation_id == "retrieved_authority":
        subject["authority"]["retrieved_content_may_grant_authority"] = True
        subject["untrusted_input_policy"]["instructions_inert"] = False
    elif mutation_id == "unauthorized_write":
        subject["write_requests"][0]["executed"] = True
    elif mutation_id == "live_default":
        subject["live_permissions"] = True
    elif mutation_id == "retention_violation":
        subject["retention_policy"]["configured_days"] = 365
        subject["retention_policy"]["enforced"] = False
    elif mutation_id == "deletion_refused":
        subject["deletion_policy"]["requests_supported"] = False
        subject["deletion_policy"]["deletion_verified"] = False
    else:
        raise ValueError(f"unsupported mutation: {mutation_id}")


def semantic_diagnostics(subject: dict[str, Any]) -> list[str]:
    errors: list[str] = []

    if subject.get("proof_level") != 4 or subject.get("claim_ceiling") != CLAIM_CEILING:
        errors.append("SECURITY-CLAIM-CEILING")

    if subject.get("live_permissions") is not False:
        errors.append("SECURITY-LIVE-DEFAULT")

    if subject.get("external_effect_occurred") is not False:
        errors.append("SECURITY-EXTERNAL-EFFECT")

    authority = subject.get("authority", {})
    untrusted = subject.get("untrusted_input_policy", {})
    if (
        authority.get("retrieved_content_may_grant_authority") is not False
        or authority.get("least_privilege_default") is not True
        or untrusted.get("instructions_inert") is not True
        or untrusted.get("malformed_fail_closed") is not True
    ):
        errors.append("SECURITY-RETRIEVED-AUTHORITY")

    secret_prefixes = ("secret_", "credential_", "token_", "password_")
    pii_prefixes = ("account_", "addr_", "contact_", "email_", "phone_")

    secret_found = False
    pii_found = False
    for event in subject.get("log_events", []):
        for token in event.get("payload_tokens", []):
            if isinstance(token, str) and token.startswith(secret_prefixes):
                secret_found = True
            if isinstance(token, str) and token.startswith(pii_prefixes):
                pii_found = True

    if secret_found:
        errors.append("SECURITY-SECRET-LOG")
    if pii_found:
        errors.append("SECURITY-PII-LOG")

    for request in subject.get("write_requests", []):
        if request.get("executed") is True and request.get("authorized") is not True:
            errors.append("SECURITY-UNAUTHORIZED-WRITE")
            break

    retention = subject.get("retention_policy", {})
    if (
        retention.get("enforced") is not True
        or not isinstance(retention.get("configured_days"), int)
        or not isinstance(retention.get("maximum_days"), int)
        or retention.get("configured_days") > retention.get("maximum_days")
    ):
        errors.append("SECURITY-RETENTION")

    deletion = subject.get("deletion_policy", {})
    if (
        deletion.get("requests_supported") is not True
        or deletion.get("verification_required") is not True
        or deletion.get("deletion_verified") is not True
    ):
        errors.append("SECURITY-DELETION")

    return errors


def evaluate_subject(subject: dict[str, Any]) -> dict[str, Any]:
    schema = strict_load_json(SCHEMA_PATH)
    schema_errors = sorted(
        {
            error.json_path
            for error in Draft202012Validator(schema).iter_errors(subject)
        }
    )
    diagnostics = (
        ["SECURITY-SCHEMA-FAILURE"]
        if schema_errors
        else semantic_diagnostics(subject)
    )
    return {
        "evaluator_id": EVALUATOR_ID,
        "passed": not diagnostics,
        "diagnostics": diagnostics,
        "schema_errors": schema_errors,
        "subject_sha256": canonical_sha256(subject),
    }


def evaluate_known_bad(path: Path) -> dict[str, Any]:
    fixture = strict_load_json(path)
    subject = build_clean_subject()
    apply_mutation(subject, fixture["mutation_id"])
    result = evaluate_subject(copy.deepcopy(subject))
    expected = fixture["expected_diagnostic"]
    detected = result["diagnostics"] == [expected]
    return {
        "result": "DETECTED" if detected else "SURVIVED",
        "case_id": fixture["case_id"],
        "fixture_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "diagnostic": (
            result["diagnostics"][0]
            if len(result["diagnostics"]) == 1
            else "unexpected diagnostics"
        ),
    }
