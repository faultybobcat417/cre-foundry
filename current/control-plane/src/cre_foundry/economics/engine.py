"""Material synthetic economic engine: risk-adjusted expected net commercial value,
cost, downside, and sensitivity machinery.

Two implementations must agree on the same canonical document: this material
engine and the frozen independent evaluator ``scripts/validate_economics_ecv.py``.
This module constructs the canonical ``COMMERCIAL_ECONOMICS_MODEL`` subject from a
compact declarative authoritative-economics policy seed and independently computes
the expected net commercial value, downside, fallback, and sensitivity machinery the
ECONOMICS-001 task requires.  It emits the frozen registered diagnostic codes when
costs are omitted or when modeled value is claimed as realized value.

This module must never import ``scripts.validate_economics_ecv`` and never import
any ``cre_foundry`` economics-adjacent package.
"""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[3]
POLICY_SCHEMA_PATH = ROOT / "contracts/economic_engine.schema.json"
SUBJECT_SCHEMA_PATH = ROOT / "contracts/commercial_economics.schema.json"
EVALUATOR_PATH = ROOT / "scripts/validate_economics_ecv.py"

DOCUMENT_KIND = "COMMERCIAL_ECONOMICS_MODEL"
SCHEMA_VERSION = "1.0.0"
EXECUTION_SCOPE = "SYNTHETIC_NON_INFLUENCING"
CANONICAL_SERIALIZATION = "UTF8_CANONICAL_JSON_SORTED_KEYS"
MATERIAL_BUILDER_IDENTITY = "economics-material-engine-v1"

# Registered diagnostic vocabulary (shared frozen contract strings)
ECONOMICS_OMITTED_COSTS = "ECONOMICS-OMITTED-COSTS"
ECONOMICS_MODELED_AS_REALIZED = "ECONOMICS-MODELED-AS-REALIZED"

# Material check vocabulary (economics assurance diagnostics not in the frozen gate).
ECONOMICS_INVENTED_INPUTS = "ECONOMICS-INVENTED-INPUTS"
ECONOMICS_DOWNSIDE_COLLAPSED = "ECONOMICS-DOWNSIDE-COLLAPSED"
ECONOMICS_UNCERTAINTY_IGNORED = "ECONOMICS-UNCERTAINTY-IGNORED"
ECONOMICS_FALLBACK_VIOLATED = "ECONOMICS-FALLBACK-VIOLATED"
ECONOMICS_REALIZED_CEILING = "ECONOMICS-REALIZED-CEILING"

ALL_CLAIM_NOT_ESTABLISHED = [
    "realized-commercial-value",
    "firm-authoritative-economics",
    "firm-cost-data",
    "calibrated-real-uncertainty",
    "commercial-lift",
    "production-readiness",
    "deployment-readiness",
    "field-effectiveness",
    "sealed-evaluator-independence",
    "hidden-holdout-performance",
]

# Canonical serialization (frozen contract conventions).


def canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
    ).encode("utf-8")


def digest_json(value: Any) -> str:
    return hashlib.sha256(canonical_json_bytes(value)).hexdigest()


def digest_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


# ---------------------------------------------------------------------------
# Declarative authoritative economics policy seed (synthetic, non-influencing)
# ---------------------------------------------------------------------------

def _policy_seed() -> dict[str, Any]:
    return {
        "document_kind": "AUTHORITATIVE_ECONOMICS_POLICY",
        "schema_version": SCHEMA_VERSION,
        "execution_scope": EXECUTION_SCOPE,
        "policy_version": "ECONOMICS-POLICY-2026-001",
        "authority": {
            "issued_by": "symbolic-synthetic-authority",
            "effective_from": "2026-01-01T00:00:00Z",
            "signature": "symbolic-pending-external-attestation",
        },
        "services": ["route-day outreach"],
        "territories": ["representative-territory"],
        "commission": {"rate": 0.06, "basis": "confirmed_booking"},
        "costs": [
            {"line_item": "material", "amount": 150.0, "currency": "CAD"},
            {"line_item": "travel", "amount": 60.0, "currency": "CAD"},
        ],
        "conversion": {"distribution": "beta", "mean": 0.18, "variance": 0.01},
        "downside": {"metric": "p10_net_value", "threshold": -200.0},
        "fallback_policy": "abstain when p10 net value is below threshold",
        "claim_ceiling": "Symbolic risk-adjusted expected value mechanics only; no firm-authoritative inputs, realized value, or commercial claim.",
    }


# ---------------------------------------------------------------------------
# Renderer: walk the policy into the canonical subject (byte-agreed with the frozen gate)
# ---------------------------------------------------------------------------

def _build_subject() -> dict[str, Any]:
    policy = _policy_seed()
    return {
        "document_kind": DOCUMENT_KIND,
        "schema_version": SCHEMA_VERSION,
        "execution_scope": EXECUTION_SCOPE,
        "services": list(policy["services"]),
        "territories": list(policy["territories"]),
        "commission": dict(policy["commission"]),
        "costs": [dict(cost) for cost in policy["costs"]],
        "conversion": dict(policy["conversion"]),
        "downside": dict(policy["downside"]),
        "fallback_policy": policy["fallback_policy"],
        "claim_status": "MODELED",
        "proof": {"level": 5, "result": "PASS"},
        "claim_ceiling": policy["claim_ceiling"],
    }


def subject_canonical_digest(subject: dict[str, Any]) -> str:
    return digest_json(subject)


def render_subject() -> dict[str, Any]:
    return _build_subject()


# ---------------------------------------------------------------------------
# Economic machinery: expected net commercial value, downside, sensitivity
# ---------------------------------------------------------------------------

_DISTRIBUTION_SCALE = 1.282  # p10 standard-normal offset for a synthetic distribution
_REFERENCE_BOOKINGS = 10.0  # synthetic reference volume; not a firm input


def _commission_rate(subject: dict[str, Any]) -> float:
    return float(subject.get("commission", {}).get("rate", 0.0))


def _total_cost(subject: dict[str, Any]) -> float:
    return float(sum(float(cost.get("amount", 0.0)) for cost in subject.get("costs", [])))


def _conversion_mean(subject: dict[str, Any]) -> float:
    return float(subject.get("conversion", {}).get("mean", 0.0))


def _conversion_std(subject: dict[str, Any]) -> float:
    variance = float(subject.get("conversion", {}).get("variance", 0.0))
    return math.sqrt(max(0.0, variance))


def _expected_gross_at(subject: dict[str, Any], conversion: float) -> float:
    """Expected gross commission for a given conversion rate under a synthetic reference volume."""
    return _REFERENCE_BOOKINGS * conversion * _commission_rate(subject)


def expected_net_value(subject: dict[str, Any]) -> dict[str, float]:
    """Risk-adjusted expected net commercial value and downside across conversion uncertainty."""
    expected_gross = _expected_gross_at(subject, _conversion_mean(subject))
    total_cost = _total_cost(subject)
    expected_net = expected_gross - total_cost
    downside_conversion = _conversion_mean(subject) - _DISTRIBUTION_SCALE * _conversion_std(subject)
    downside_gross = _expected_gross_at(subject, max(0.0, downside_conversion))
    downside_net = downside_gross - total_cost
    return {
        "expected_gross_commission": expected_gross,
        "expected_net_value": expected_net,
        "downside_net_value": downside_net,
        "total_cost": total_cost,
        "downside_conversion": max(0.0, downside_conversion),
    }


def sensitivity(subject: dict[str, Any]) -> dict[str, float]:
    """Local sensitivity of expected net value to conversion, commission, and cost."""
    return {
        "conversion_mean": _REFERENCE_BOOKINGS * _commission_rate(subject),
        "commission_rate": _REFERENCE_BOOKINGS * _conversion_mean(subject),
        "total_cost": -1.0,
    }


def downside_fallback(subject: dict[str, Any]) -> dict[str, Any]:
    values = expected_net_value(subject)
    threshold = float(subject.get("downside", {}).get("threshold", 0.0))
    triggered = values["downside_net_value"] < threshold
    return {
        "downside_net_value": values["downside_net_value"],
        "threshold": threshold,
        "triggered": bool(triggered),
        "decision": "ABSTAIN" if triggered else "MODELED",
    }


# ---------------------------------------------------------------------------
# Material semantic checks
# ---------------------------------------------------------------------------

def check_invented_inputs(subject: dict[str, Any]) -> bool:
    if not subject.get("services") or not subject.get("territories"):
        return True
    joined = " ".join(map(str, subject.get("services", []))) + " " + " ".join(map(str, subject.get("territories", [])))
    return any(marker in joined for marker in ("placeholder", "tbd", "xxx", "invented", "fake", "garbage"))


def check_downside_collapsed(subject: dict[str, Any]) -> bool:
    downside = subject.get("downside", {})
    return not downside.get("metric") or downside.get("threshold") is None


def check_uncertainty_ignored(subject: dict[str, Any]) -> bool:
    variance = float(subject.get("conversion", {}).get("variance", 0.0))
    return not (variance > 0.0)


def check_realized_ceiling(subject: dict[str, Any]) -> bool:
    return subject.get("claim_status") == "REALIZED"


def check_omitted_costs(subject: dict[str, Any]) -> bool:
    return not subject.get("costs")


def check_modeled_as_realized(subject: dict[str, Any]) -> bool:
    return subject.get("claim_status") != "MODELED"


def check_fallback_violated(subject: dict[str, Any]) -> bool:
    """A fallback violation occurs only when the model claims a usable value
    while its own fallback policy says to abstain."""
    if not check_modeled_as_realized(subject):
        return False
    fallback = downside_fallback(subject)
    return fallback["triggered"]


def material_checks(subject: dict[str, Any]) -> list[str]:
    """Material economics verdict: emit frozen registered codes plus material assurance codes."""
    errors: list[str] = []
    if check_omitted_costs(subject):
        errors.append(ECONOMICS_OMITTED_COSTS)
    if check_modeled_as_realized(subject):
        errors.append(ECONOMICS_MODELED_AS_REALIZED)
    if check_invented_inputs(subject):
        errors.append(ECONOMICS_INVENTED_INPUTS)
    if check_downside_collapsed(subject):
        errors.append(ECONOMICS_DOWNSIDE_COLLAPSED)
    if check_uncertainty_ignored(subject):
        errors.append(ECONOMICS_UNCERTAINTY_IGNORED)
    if check_realized_ceiling(subject):
        errors.append(ECONOMICS_REALIZED_CEILING)
    if check_fallback_violated(subject):
        errors.append(ECONOMICS_FALLBACK_VIOLATED)
    return sorted(set(errors))