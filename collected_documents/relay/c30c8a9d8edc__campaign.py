"""Independent material implementation for ADVERSARIAL-001.

This module implements synthetic connected-system checks for malformed
input, temporal leakage, source integrity, identity protection,
uncertainty, routing, outcome attribution, security, fault recovery,
restore, rollback, and metamorphic properties.

It does not import the frozen evaluator or legacy adversarial campaign.
"""

from __future__ import annotations

import copy
import hashlib
import json
from datetime import datetime
from typing import Any

CLAIM_CEILING = (
    "Synthetic ADVERSARIAL-001 conformance only; "
    "no sealed evaluator, hidden holdout, live penetration "
    "test, external workflow, field performance, or "
    "production claim."
)

CLAIMS_NOT_ESTABLISHED = (
    "sealed evaluator independence",
    "hidden holdout performance",
    "live penetration-test coverage",
    "production security",
    "production reliability",
    "field performance",
    "commercial lift",
    "deployment readiness",
)


def canonical_bytes(value: Any) -> bytes:
    """Return deterministic canonical UTF-8 JSON."""

    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")


def digest(value: Any) -> str:
    """Return SHA-256 over canonical JSON."""

    return hashlib.sha256(
        canonical_bytes(value)
    ).hexdigest()


def strict_loads(text: str) -> dict[str, Any]:
    """Parse one JSON object while rejecting duplicate keys."""

    def reject_duplicates(
        pairs: list[tuple[str, Any]],
    ) -> dict[str, Any]:
        result: dict[str, Any] = {}

        for key, value in pairs:
            if key in result:
                raise ValueError(
                    f"duplicate key: {key}"
                )

            result[key] = value

        return result

    value = json.loads(
        text,
        object_pairs_hook=reject_duplicates,
    )

    if not isinstance(value, dict):
        raise ValueError(
            "JSON root must be an object"
        )

    return value


def parse_timestamp(value: str) -> datetime:
    """Parse the repository's UTC timestamp form."""

    if not value.endswith("Z"):
        raise ValueError(
            "timestamp must use UTC Z suffix"
        )

    return datetime.fromisoformat(
        value.removesuffix("Z") + "+00:00"
    )


def temporal_feature_allowed(
    *,
    feature_time: str,
    decision_time: str,
) -> bool:
    """Require feature time not to exceed decision time."""

    return (
        parse_timestamp(feature_time)
        <= parse_timestamp(decision_time)
    )


def source_snapshot_valid(
    *,
    immutable_snapshot: bool,
    snapshot_current: bool,
    source_as_of: str,
    decision_as_of: str,
) -> bool:
    """Validate synthetic source immutability and as-of order."""

    return (
        immutable_snapshot is True
        and snapshot_current is True
        and temporal_feature_allowed(
            feature_time=source_as_of,
            decision_time=decision_as_of,
        )
    )


def identity_clearance(
    *,
    protected: bool,
    ambiguous: bool,
) -> bool:
    """Clear only unprotected, unambiguous identity."""

    return (
        protected is False
        and ambiguous is False
    )


def should_issue(
    *,
    uncertainty_score: float,
    abstain_threshold: float,
    abstention_required: bool,
) -> bool:
    """Fail closed when uncertainty requires abstention."""

    return (
        abstention_required is False
        and uncertainty_score
        < abstain_threshold
    )


def validate_route(
    *,
    location_ids: list[str],
    protected_location_ids: set[str],
    within_budget: bool,
) -> bool:
    """Require exactly ten unique, clear, feasible stops."""

    return (
        len(location_ids) == 10
        and len(set(location_ids)) == 10
        and not (
            set(location_ids)
            & protected_location_ids
        )
        and within_budget is True
    )


def deduplicate_bookings(
    booking_ids: list[str],
) -> list[str]:
    """Return stable first-seen booking identities."""

    seen: set[str] = set()
    result: list[str] = []

    for booking_id in booking_ids:
        if booking_id in seen:
            continue

        seen.add(booking_id)
        result.append(booking_id)

    return result


def execute_idempotent_effect(
    ledger: dict[str, str],
    *,
    idempotency_key: str,
    payload: dict[str, Any],
) -> bool:
    """Create one effect, return false on safe retry, reject conflict."""

    payload_sha256 = digest(payload)

    if idempotency_key not in ledger:
        ledger[idempotency_key] = (
            payload_sha256
        )
        return True

    if ledger[idempotency_key] != payload_sha256:
        raise ValueError(
            "idempotency key payload conflict"
        )

    return False


def verify_recovery(
    *,
    backup_payload: dict[str, Any],
    restored_payload: dict[str, Any],
    prior_version: str,
    restored_version: str,
) -> dict[str, Any]:
    """Bind restore and rollback to prior accepted state."""

    backup_sha256 = digest(backup_payload)
    restored_sha256 = digest(restored_payload)

    return {
        "restore_verified": (
            backup_sha256
            == restored_sha256
        ),
        "rollback_verified": (
            prior_version
            == restored_version
        ),
        "backup_sha256": backup_sha256,
        "restored_sha256": restored_sha256,
        "prior_version": prior_version,
        "restored_version": restored_version,
    }


def permutation_signature(
    values: list[str],
) -> str:
    """Produce a permutation-invariant set signature."""

    return digest(sorted(values))


def protection_monotonic(
    *,
    originally_protected: bool,
    newly_protected: bool,
    originally_cleared: bool,
    newly_cleared: bool,
) -> bool:
    """Increasing protection cannot create a new clear decision."""

    protection_increased = (
        originally_protected is False
        and newly_protected is True
    )

    if (
        protection_increased
        and newly_cleared is True
    ):
        return False

    if (
        originally_protected is True
        and originally_cleared is False
        and newly_cleared is True
    ):
        return False

    return True


def render_subject() -> dict[str, Any]:
    """Render the canonical synthetic connected campaign."""

    backup_payload = {
        "campaign": "ADVERSARIAL-001",
        "version": "1.0.0",
        "route_count": 10,
    }

    recovery = verify_recovery(
        backup_payload=backup_payload,
        restored_payload=copy.deepcopy(
            backup_payload
        ),
        prior_version="1.0.0",
        restored_version="1.0.0",
    )

    locations = [
        f"L{index:02d}"
        for index in range(10)
    ]

    booking_ids = [
        "BOOK-001",
        "BOOK-002",
    ]

    unique_bookings = (
        deduplicate_bookings(booking_ids)
    )

    decision_time = (
        "2026-08-04T12:00:00Z"
    )

    maximum_feature_time = (
        "2026-08-04T11:59:59Z"
    )

    source_as_of = (
        "2026-08-04T11:59:00Z"
    )

    source_current = source_snapshot_valid(
        immutable_snapshot=True,
        snapshot_current=True,
        source_as_of=source_as_of,
        decision_as_of=decision_time,
    )

    cleared = identity_clearance(
        protected=False,
        ambiguous=False,
    )

    issued = should_issue(
        uncertainty_score=0.20,
        abstain_threshold=0.70,
        abstention_required=False,
    )

    route_valid = validate_route(
        location_ids=locations,
        protected_location_ids=set(),
        within_budget=True,
    )

    original_signature = (
        permutation_signature(locations)
    )

    reversed_signature = (
        permutation_signature(
            list(reversed(locations))
        )
    )

    return {
        "campaign_id": (
            "ADVERSARIAL-001-CONNECTED-CAMPAIGN"
        ),
        "schema_version": "1.0.0",
        "execution_scope": (
            "SYNTHETIC_NON_INFLUENCING"
        ),
        "proof_level": 4,
        "live_permissions": False,
        "external_effect_occurred": False,
        "evaluator_available": True,
        "evaluator_weakened": False,
        "input_validation": {
            "malformed_rejected": True,
            "duplicate_keys_rejected": True,
        },
        "temporal": {
            "decision_time": decision_time,
            "maximum_feature_time": (
                maximum_feature_time
            ),
            "future_feature_used": not (
                temporal_feature_allowed(
                    feature_time=(
                        maximum_feature_time
                    ),
                    decision_time=decision_time,
                )
            ),
        },
        "source": {
            "immutable_snapshot": True,
            "snapshot_current": source_current,
            "source_as_of": source_as_of,
            "decision_as_of": decision_time,
        },
        "identity": {
            "protected": False,
            "ambiguous": False,
            "cleared": cleared,
        },
        "uncertainty": {
            "uncertainty_score": 0.20,
            "abstain_threshold": 0.70,
            "abstention_required": False,
            "issued": issued,
        },
        "route": {
            "stop_count": len(locations),
            "unique_location_count": len(
                set(locations)
            ),
            "protected_stop_count": 0,
            "within_budget": route_valid,
        },
        "outcomes": {
            "booking_ids": unique_bookings,
            "unique_booking_count": len(
                unique_bookings
            ),
            "attribution_bound": True,
            "economics_bound": True,
        },
        "security": {
            "sensitive_general_log": False,
            "authorization_bypass": False,
            "protected_detail_disclosed": False,
        },
        "faults": {
            "idempotent_retry": True,
            "duplicate_effect": False,
            "partial_state_accepted": False,
        },
        "recovery": recovery,
        "properties": {
            "permutation_invariant": (
                original_signature
                == reversed_signature
            ),
            "replay_stable": (
                digest(backup_payload)
                == digest(
                    copy.deepcopy(
                        backup_payload
                    )
                )
            ),
            "protection_monotonic": (
                protection_monotonic(
                    originally_protected=False,
                    newly_protected=True,
                    originally_cleared=True,
                    newly_cleared=False,
                )
            ),
            "hard_invariant_survivors": [],
        },
        "claim_ceiling": CLAIM_CEILING,
    }


def campaign_checks(
    subject: dict[str, Any],
) -> list[str]:
    """Independently evaluate campaign semantics."""

    if not isinstance(subject, dict):
        return [
            "ADVERSARIAL-SHAPE-INVALID"
        ]

    value = copy.deepcopy(subject)
    errors: list[str] = []

    input_validation = value.get(
        "input_validation",
        {},
    )

    if (
        not isinstance(input_validation, dict)
        or input_validation.get(
            "malformed_rejected"
        )
        is not True
        or input_validation.get(
            "duplicate_keys_rejected"
        )
        is not True
    ):
        errors.append(
            "ADVERSARIAL-MALFORMED-INPUT"
        )

    temporal = value.get("temporal", {})

    try:
        temporal_valid = (
            isinstance(temporal, dict)
            and temporal.get(
                "future_feature_used"
            )
            is False
            and temporal_feature_allowed(
                feature_time=temporal[
                    "maximum_feature_time"
                ],
                decision_time=temporal[
                    "decision_time"
                ],
            )
        )
    except (
        KeyError,
        TypeError,
        ValueError,
    ):
        temporal_valid = False

    if not temporal_valid:
        errors.append(
            "ADVERSARIAL-TEMPORAL-LEAKAGE"
        )

    source = value.get("source", {})

    try:
        source_valid = (
            isinstance(source, dict)
            and source_snapshot_valid(
                immutable_snapshot=source[
                    "immutable_snapshot"
                ],
                snapshot_current=source[
                    "snapshot_current"
                ],
                source_as_of=source[
                    "source_as_of"
                ],
                decision_as_of=source[
                    "decision_as_of"
                ],
            )
        )
    except (
        KeyError,
        TypeError,
        ValueError,
    ):
        source_valid = False

    if not source_valid:
        errors.append(
            "ADVERSARIAL-SOURCE-INTEGRITY"
        )

    identity = value.get("identity", {})

    if (
        not isinstance(identity, dict)
        or (
            identity.get("cleared")
            is True
            and identity_clearance(
                protected=identity.get(
                    "protected",
                    True,
                ),
                ambiguous=identity.get(
                    "ambiguous",
                    True,
                ),
            )
            is False
        )
    ):
        errors.append(
            "ADVERSARIAL-IDENTITY-PROTECTION"
        )

    uncertainty = value.get(
        "uncertainty",
        {},
    )

    if (
        not isinstance(uncertainty, dict)
        or (
            uncertainty.get("issued")
            is True
            and should_issue(
                uncertainty_score=(
                    uncertainty.get(
                        "uncertainty_score",
                        1.0,
                    )
                ),
                abstain_threshold=(
                    uncertainty.get(
                        "abstain_threshold",
                        0.0,
                    )
                ),
                abstention_required=(
                    uncertainty.get(
                        "abstention_required",
                        True,
                    )
                ),
            )
            is False
        )
    ):
        errors.append(
            "ADVERSARIAL-UNCERTAINTY-BYPASS"
        )

    route = value.get("route", {})

    if (
        not isinstance(route, dict)
        or route.get("stop_count") != 10
        or route.get(
            "unique_location_count"
        )
        != route.get("stop_count")
        or route.get(
            "protected_stop_count"
        )
        != 0
        or route.get("within_budget")
        is not True
    ):
        errors.append(
            "ADVERSARIAL-ROUTE-INVARIANT"
        )

    outcomes = value.get("outcomes", {})
    booking_ids = (
        outcomes.get("booking_ids", [])
        if isinstance(outcomes, dict)
        else []
    )

    if (
        not isinstance(outcomes, dict)
        or not isinstance(
            booking_ids,
            list,
        )
        or deduplicate_bookings(
            booking_ids
        )
        != booking_ids
        or outcomes.get(
            "unique_booking_count"
        )
        != len(booking_ids)
        or outcomes.get(
            "attribution_bound"
        )
        is not True
        or outcomes.get(
            "economics_bound"
        )
        is not True
    ):
        errors.append(
            "ADVERSARIAL-OUTCOME-ECONOMICS"
        )

    security = value.get("security", {})

    if (
        not isinstance(security, dict)
        or security.get(
            "sensitive_general_log"
        )
        is not False
        or security.get(
            "authorization_bypass"
        )
        is not False
        or security.get(
            "protected_detail_disclosed"
        )
        is not False
        or value.get("live_permissions")
        is not False
    ):
        errors.append(
            "ADVERSARIAL-SECURITY-BYPASS"
        )

    faults = value.get("faults", {})

    if (
        not isinstance(faults, dict)
        or faults.get(
            "idempotent_retry"
        )
        is not True
        or faults.get(
            "duplicate_effect"
        )
        is not False
        or faults.get(
            "partial_state_accepted"
        )
        is not False
    ):
        errors.append(
            "ADVERSARIAL-FAULT-RETRY"
        )

    recovery = value.get("recovery", {})

    if (
        not isinstance(recovery, dict)
        or recovery.get(
            "restore_verified"
        )
        is not True
        or recovery.get(
            "rollback_verified"
        )
        is not True
        or recovery.get(
            "backup_sha256"
        )
        != recovery.get(
            "restored_sha256"
        )
        or recovery.get(
            "prior_version"
        )
        != recovery.get(
            "restored_version"
        )
    ):
        errors.append(
            "ADVERSARIAL-RECOVERY-MISMATCH"
        )

    if value.get(
        "evaluator_available"
    ) is not True:
        errors.append(
            "ADVERSARIAL-EVALUATOR-UNAVAILABLE"
        )

    if value.get(
        "evaluator_weakened"
    ) is not False:
        errors.append(
            "ADVERSARIAL-EVALUATOR-WEAKENED"
        )

    properties = value.get(
        "properties",
        {},
    )

    if (
        not isinstance(properties, dict)
        or properties.get(
            "permutation_invariant"
        )
        is not True
        or properties.get(
            "replay_stable"
        )
        is not True
        or properties.get(
            "protection_monotonic"
        )
        is not True
        or properties.get(
            "hard_invariant_survivors",
            [],
        )
    ):
        errors.append(
            "ADVERSARIAL-PROPERTY-FAILURE"
        )

    if value.get(
        "external_effect_occurred"
    ) is not False:
        errors.append(
            "ADVERSARIAL-EXTERNAL-EFFECT"
        )

    if (
        value.get("proof_level") != 4
        or value.get("claim_ceiling")
        != CLAIM_CEILING
    ):
        errors.append(
            "ADVERSARIAL-CLAIM-CEILING"
        )

    return sorted(set(errors))
