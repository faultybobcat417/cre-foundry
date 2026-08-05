"""Independent frozen evaluator for ADVERSARIAL-001."""

from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[2]

SCHEMA_PATH = (
    ROOT
    / "contracts/adversarial_campaign.schema.json"
)

EVALUATOR_ID = "adversarial-connected-public-v1"

CLAIM_CEILING = (
    "Synthetic ADVERSARIAL-001 conformance only; "
    "no sealed evaluator, hidden holdout, live penetration "
    "test, external workflow, field performance, or "
    "production claim."
)


def strict_load_json(path: Path) -> dict[str, Any]:
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
        path.read_text(encoding="utf-8"),
        object_pairs_hook=reject_duplicates,
    )

    if not isinstance(value, dict):
        raise ValueError(
            "JSON root must be an object"
        )

    return value


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")


def digest(value: Any) -> str:
    return hashlib.sha256(
        canonical_bytes(value)
    ).hexdigest()


def build_clean_subject() -> dict[str, Any]:
    backup_payload = {
        "campaign": "ADVERSARIAL-001",
        "version": "1.0.0",
        "route_count": 10,
    }

    backup_sha256 = digest(backup_payload)

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
            "decision_time": (
                "2026-08-04T12:00:00Z"
            ),
            "maximum_feature_time": (
                "2026-08-04T11:59:59Z"
            ),
            "future_feature_used": False,
        },
        "source": {
            "immutable_snapshot": True,
            "snapshot_current": True,
            "source_as_of": (
                "2026-08-04T11:59:00Z"
            ),
            "decision_as_of": (
                "2026-08-04T12:00:00Z"
            ),
        },
        "identity": {
            "protected": False,
            "ambiguous": False,
            "cleared": True,
        },
        "uncertainty": {
            "uncertainty_score": 0.20,
            "abstain_threshold": 0.70,
            "abstention_required": False,
            "issued": True,
        },
        "route": {
            "stop_count": 10,
            "unique_location_count": 10,
            "protected_stop_count": 0,
            "within_budget": True,
        },
        "outcomes": {
            "booking_ids": [
                "BOOK-001",
                "BOOK-002",
            ],
            "unique_booking_count": 2,
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
        "recovery": {
            "restore_verified": True,
            "rollback_verified": True,
            "backup_sha256": backup_sha256,
            "restored_sha256": backup_sha256,
            "prior_version": "1.0.0",
            "restored_version": "1.0.0",
        },
        "properties": {
            "permutation_invariant": True,
            "replay_stable": True,
            "protection_monotonic": True,
            "hard_invariant_survivors": [],
        },
        "claim_ceiling": CLAIM_CEILING,
    }


def apply_mutation(
    subject: dict[str, Any],
    mutation_id: str,
) -> None:
    if mutation_id == (
        "malformed_duplicate_key_accepted"
    ):
        subject["input_validation"].update(
            {
                "malformed_rejected": False,
                "duplicate_keys_rejected": False,
            }
        )
    elif mutation_id == "temporal_leakage":
        subject["temporal"].update(
            {
                "maximum_feature_time": (
                    "2026-08-04T12:01:00Z"
                ),
                "future_feature_used": True,
            }
        )
    elif mutation_id == "source_integrity_bypass":
        subject["source"][
            "snapshot_current"
        ] = False
    elif mutation_id == (
        "identity_protection_bypass"
    ):
        subject["identity"].update(
            {
                "protected": True,
                "cleared": True,
            }
        )
    elif mutation_id == "uncertainty_bypass":
        subject["uncertainty"].update(
            {
                "uncertainty_score": 0.95,
                "abstention_required": True,
                "issued": True,
            }
        )
    elif mutation_id == "route_violation":
        subject["route"][
            "unique_location_count"
        ] = 9
    elif mutation_id == (
        "outcome_economic_misattribution"
    ):
        subject["outcomes"].update(
            {
                "unique_booking_count": 1,
                "attribution_bound": False,
            }
        )
    elif mutation_id == "security_bypass":
        subject["security"][
            "sensitive_general_log"
        ] = True
    elif mutation_id == "fault_retry_partial":
        subject["faults"].update(
            {
                "duplicate_effect": True,
                "partial_state_accepted": True,
            }
        )
    elif mutation_id == (
        "restore_rollback_mismatch"
    ):
        subject["recovery"].update(
            {
                "restored_sha256": "f" * 64,
                "restored_version": "2.0.0",
            }
        )
    elif mutation_id == (
        "evaluator_unavailable_pass"
    ):
        subject["evaluator_available"] = False
    elif mutation_id == "evaluator_weakened":
        subject["evaluator_weakened"] = True
    elif mutation_id == (
        "metamorphic_property_failure"
    ):
        subject["properties"][
            "permutation_invariant"
        ] = False
    else:
        raise ValueError(
            f"unsupported mutation: {mutation_id}"
        )


def diagnostics(
    subject: dict[str, Any],
) -> list[str]:
    if not isinstance(subject, dict):
        return ["ADVERSARIAL-SHAPE-INVALID"]

    errors: list[str] = []

    input_validation = subject.get(
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

    temporal = subject.get("temporal", {})

    if (
        not isinstance(temporal, dict)
        or temporal.get("future_feature_used")
        is not False
        or temporal.get(
            "maximum_feature_time",
            "",
        )
        > temporal.get("decision_time", "")
    ):
        errors.append(
            "ADVERSARIAL-TEMPORAL-LEAKAGE"
        )

    source = subject.get("source", {})

    if (
        not isinstance(source, dict)
        or source.get("immutable_snapshot")
        is not True
        or source.get("snapshot_current")
        is not True
        or source.get("source_as_of", "")
        > source.get("decision_as_of", "")
    ):
        errors.append(
            "ADVERSARIAL-SOURCE-INTEGRITY"
        )

    identity = subject.get("identity", {})

    if (
        not isinstance(identity, dict)
        or (
            identity.get("cleared") is True
            and (
                identity.get("protected") is True
                or identity.get("ambiguous")
                is True
            )
        )
    ):
        errors.append(
            "ADVERSARIAL-IDENTITY-PROTECTION"
        )

    uncertainty = subject.get(
        "uncertainty",
        {},
    )

    if (
        not isinstance(uncertainty, dict)
        or (
            uncertainty.get(
                "uncertainty_score",
                1,
            )
            >= uncertainty.get(
                "abstain_threshold",
                0,
            )
            and uncertainty.get("issued")
            is True
        )
        or (
            uncertainty.get(
                "abstention_required"
            )
            is True
            and uncertainty.get("issued")
            is True
        )
    ):
        errors.append(
            "ADVERSARIAL-UNCERTAINTY-BYPASS"
        )

    route = subject.get("route", {})

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

    outcomes = subject.get("outcomes", {})
    booking_ids = (
        outcomes.get("booking_ids", [])
        if isinstance(outcomes, dict)
        else []
    )

    if (
        not isinstance(outcomes, dict)
        or not isinstance(booking_ids, list)
        or len(set(booking_ids))
        != len(booking_ids)
        or outcomes.get(
            "unique_booking_count"
        )
        != len(booking_ids)
        or outcomes.get(
            "attribution_bound"
        )
        is not True
        or outcomes.get("economics_bound")
        is not True
    ):
        errors.append(
            "ADVERSARIAL-OUTCOME-ECONOMICS"
        )

    security = subject.get("security", {})

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
        or subject.get("live_permissions")
        is not False
    ):
        errors.append(
            "ADVERSARIAL-SECURITY-BYPASS"
        )

    faults = subject.get("faults", {})

    if (
        not isinstance(faults, dict)
        or faults.get("idempotent_retry")
        is not True
        or faults.get("duplicate_effect")
        is not False
        or faults.get(
            "partial_state_accepted"
        )
        is not False
    ):
        errors.append(
            "ADVERSARIAL-FAULT-RETRY"
        )

    recovery = subject.get("recovery", {})

    if (
        not isinstance(recovery, dict)
        or recovery.get("restore_verified")
        is not True
        or recovery.get("rollback_verified")
        is not True
        or recovery.get("backup_sha256")
        != recovery.get("restored_sha256")
        or recovery.get("prior_version")
        != recovery.get("restored_version")
    ):
        errors.append(
            "ADVERSARIAL-RECOVERY-MISMATCH"
        )

    if subject.get(
        "evaluator_available"
    ) is not True:
        errors.append(
            "ADVERSARIAL-EVALUATOR-UNAVAILABLE"
        )

    if subject.get(
        "evaluator_weakened"
    ) is not False:
        errors.append(
            "ADVERSARIAL-EVALUATOR-WEAKENED"
        )

    properties = subject.get(
        "properties",
        {},
    )

    if (
        not isinstance(properties, dict)
        or properties.get(
            "permutation_invariant"
        )
        is not True
        or properties.get("replay_stable")
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

    if (
        subject.get(
            "external_effect_occurred"
        )
        is not False
    ):
        errors.append(
            "ADVERSARIAL-EXTERNAL-EFFECT"
        )

    if (
        subject.get("proof_level") != 4
        or subject.get("claim_ceiling")
        != CLAIM_CEILING
    ):
        errors.append(
            "ADVERSARIAL-CLAIM-CEILING"
        )

    return sorted(set(errors))


def evaluate_subject(
    subject: dict[str, Any],
) -> dict[str, Any]:
    semantic = diagnostics(
        copy.deepcopy(subject)
    )

    schema = strict_load_json(SCHEMA_PATH)
    Draft202012Validator.check_schema(schema)

    schema_errors = list(
        Draft202012Validator(
            schema
        ).iter_errors(subject)
    )

    if semantic:
        result_diagnostics = semantic
    elif schema_errors:
        result_diagnostics = [
            "ADVERSARIAL-SCHEMA"
        ]
    else:
        result_diagnostics = []

    return {
        "passed": not result_diagnostics,
        "diagnostics": result_diagnostics,
        "schema_error_count": len(
            schema_errors
        ),
    }
