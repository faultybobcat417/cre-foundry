"""Independent synthetic SECURITY-001 material implementation.

This module never imports the frozen evaluator. It contains no real
credentials, secrets, PII, protected-account data, or external effects.
"""

from __future__ import annotations

import copy
import json
from typing import Any, Iterable

CLAIM_CEILING = (
    "Synthetic SECURITY-001 conformance only; no penetration test, "
    "production security, compliance, operational privacy, or deployment claim."
)

ALL_CLAIMS_NOT_ESTABLISHED = (
    "penetration-test result",
    "production security posture",
    "legal or regulatory compliance",
    "operational privacy effectiveness",
    "breach resistance",
    "real deletion completion",
    "deployment readiness",
    "sealed evaluator independence",
    "hidden-holdout performance",
)

SECRET_PREFIXES = ("secret_", "credential_", "token_", "password_")
PII_PREFIXES = ("account_", "addr_", "contact_", "email_", "phone_")


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")


def classify_token(token: str) -> str:
    if not isinstance(token, str):
        return "RESTRICTED_SECRET"
    if token.startswith(SECRET_PREFIXES):
        return "RESTRICTED_SECRET"
    if token.startswith(PII_PREFIXES):
        return "RESTRICTED_PII"
    if token.startswith("confidential_"):
        return "CONFIDENTIAL"
    if token.startswith("internal_"):
        return "INTERNAL"
    return "PUBLIC"


def log_event(
    level: str,
    message: str,
    payload_tokens: Iterable[str] = (),
) -> dict[str, Any]:
    if level not in {"debug", "info", "warning", "error"}:
        raise ValueError("unsupported log level")

    tokens = list(payload_tokens)

    if any(
        classify_token(token) in {"RESTRICTED_SECRET", "RESTRICTED_PII"}
        for token in tokens
    ):
        raise ValueError("restricted data cannot enter general logs")

    return {
        "level": level,
        "message": message,
        "payload_tokens": tokens,
    }


def authorization_decision(
    *,
    target: str,
    authorized: bool,
    live_permissions: bool = False,
    authority_source: str = "versioned-policy-store",
) -> dict[str, Any]:
    valid_authority = authority_source == "versioned-policy-store"
    permitted = bool(authorized and live_permissions and valid_authority)

    return {
        "target": target,
        "authorized": bool(authorized and valid_authority),
        "executed": permitted,
        "decision": "ALLOW" if permitted else "DENY",
    }


def process_untrusted_content(content: str) -> dict[str, Any]:
    return {
        "content_present": bool(content),
        "instructions_inert": True,
        "malformed_fail_closed": True,
        "authority_granted": False,
        "policy_changed": False,
    }


def retention_is_valid(
    *,
    maximum_days: Any,
    configured_days: Any,
    enforced: Any,
) -> bool:
    return (
        type(maximum_days) is int
        and type(configured_days) is int
        and maximum_days >= 0
        and configured_days >= 0
        and configured_days <= maximum_days
        and enforced is True
    )


def deletion_is_complete(
    *,
    requests_supported: Any,
    verification_required: Any,
    deletion_verified: Any,
) -> bool:
    return (
        requests_supported is True
        and verification_required is True
        and deletion_verified is True
    )


def render_subject() -> dict[str, Any]:
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
            log_event(
                "info",
                "correlation_id=run_001 security check completed",
            )
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


def material_checks(subject: dict[str, Any]) -> list[str]:
    value = copy.deepcopy(subject)
    diagnostics: list[str] = []

    if (
        value.get("proof_level") != 4
        or value.get("claim_ceiling") != CLAIM_CEILING
    ):
        diagnostics.append("SECURITY-CLAIM-CEILING")

    if value.get("live_permissions") is not False:
        diagnostics.append("SECURITY-LIVE-DEFAULT")

    if value.get("external_effect_occurred") is not False:
        diagnostics.append("SECURITY-EXTERNAL-EFFECT")

    authority = value.get("authority", {})
    untrusted = value.get("untrusted_input_policy", {})

    if (
        authority.get("retrieved_content_may_grant_authority") is not False
        or authority.get("least_privilege_default") is not True
        or untrusted.get("instructions_inert") is not True
        or untrusted.get("malformed_fail_closed") is not True
    ):
        diagnostics.append("SECURITY-RETRIEVED-AUTHORITY")

    secret_found = False
    pii_found = False

    for event in value.get("log_events", []):
        for token in event.get("payload_tokens", []):
            classification = classify_token(token)
            secret_found |= classification == "RESTRICTED_SECRET"
            pii_found |= classification == "RESTRICTED_PII"

    if secret_found:
        diagnostics.append("SECURITY-SECRET-LOG")

    if pii_found:
        diagnostics.append("SECURITY-PII-LOG")

    if any(
        request.get("executed") is True
        and request.get("authorized") is not True
        for request in value.get("write_requests", [])
    ):
        diagnostics.append("SECURITY-UNAUTHORIZED-WRITE")

    retention = value.get("retention_policy", {})

    if not retention_is_valid(
        maximum_days=retention.get("maximum_days"),
        configured_days=retention.get("configured_days"),
        enforced=retention.get("enforced"),
    ):
        diagnostics.append("SECURITY-RETENTION")

    deletion = value.get("deletion_policy", {})

    if not deletion_is_complete(
        requests_supported=deletion.get("requests_supported"),
        verification_required=deletion.get("verification_required"),
        deletion_verified=deletion.get("deletion_verified"),
    ):
        diagnostics.append("SECURITY-DELETION")

    return diagnostics
