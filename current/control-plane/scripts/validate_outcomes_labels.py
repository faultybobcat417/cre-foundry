"""Read-only OUTCOMES-001 validator and declarative mutation runner."""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

from cre_foundry.outcomes.ledger import build_input_ledger, build_itt_inclusion_cases, build_outcome_run
from evals.public.outcomes_labels_evaluator import digest_json, strict_load, validate_itt_inclusion_cases, validate_outcome_run

INPUT_LEDGER = ROOT / "artifacts/outcomes/synthetic_input_ledger.json"
CANONICAL_RUN = ROOT / "artifacts/outcomes/canonical_run.json"
REPORT = ROOT / "artifacts/evaluations/outcomes_synthetic.json"
CONTRACT = ROOT / "artifacts/outcomes/public_evaluator_contract.json"
ITT_CASES = ROOT / "artifacts/outcomes/itt_inclusion_cases.json"
RECIPES = sorted((ROOT / "evals/known_bad/frontier").glob("outcome_*.json"))
REPORT_SUBJECTS = {
    "contracts/f9_outcome.schema.json",
    "contracts/f9_outcome_input_ledger.schema.json",
    "contracts/f9_window_policy.schema.json",
    "contracts/synthetic_field_event.schema.json",
    "contracts/synthetic_f9_outcome.schema.json",
    "artifacts/outcomes/public_evaluator_contract.json",
    "artifacts/outcomes/synthetic_window_policy.json",
    "artifacts/outcomes/scenario_matrix.json",
    "artifacts/outcomes/synthetic_input_ledger.json",
    "artifacts/outcomes/canonical_run.json",
    "artifacts/outcomes/itt_inclusion_cases.json",
    "artifacts/outcomes/capability_classification_reconciliation.json",
    "src/cre_foundry/outcomes/ledger.py",
    "evals/public/outcomes_labels_evaluator.py",
    "evals/public/test_outcomes_labels.py",
    "scripts/validate_outcomes_labels.py",
}
REPORT_CLAIM = "The bounded synthetic outcome ledger, common-as-of maturity projection, correction lineage, active-evidence booking deduplication, route-day aggregation, ITT inclusion registry, and replay receipt conform to the frozen public contract."
REPORT_CEILING = "No real F9 outcome, authorized maturity policy, label accuracy, baseline rate, predictive validity, incremental lift, downstream funnel, commercial value, live-use, or production claim is established."


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _assessment(subject: dict, sequence: int) -> dict:
    unit_id = f"OUTCOME_UNIT:ROUTE_DAY_001:{sequence:02d}"
    return next(row for row in subject["current_heads"] if row["outcome_unit_id"] == unit_id)


def _sync_assessment(subject: dict, head: dict) -> None:
    for index, row in enumerate(subject["assessments"]):
        if row["assessment_id"] == head["assessment_id"]:
            subject["assessments"][index] = head


def refresh_receipt(subject: dict) -> None:
    receipt = subject["replay_receipt"]
    receipt["input_ledger_sha256"] = digest_json(subject["input_ledger"])
    receipt["assessment_digests"] = [{"assessment_id": row["assessment_id"], "sha256": digest_json(row)} for row in subject["assessments"]]
    receipt["dedupe_groups_sha256"] = digest_json(subject["dedupe_groups"])
    edges = [{"assessment_id": row["assessment_id"], "predecessor": row["predecessor"]} for row in subject["assessments"] if row["predecessor"] is not None]
    receipt["correction_lineage_root_sha256"] = digest_json(edges)
    receipt["current_label_vector_sha256"] = digest_json([{"outcome_unit_id": row["outcome_unit_id"], "counted_f9": row["counted_f9"]} for row in subject["current_heads"]])
    receipt["route_day_aggregate_sha256"] = digest_json(subject["route_day_aggregate"])
    receipt["state_counts"] = subject["route_day_aggregate"]["state_counts"]


def _ledger_assertion(subject: dict, sequence: int, assertion_type: str) -> dict:
    unit_id = f"OUTCOME_UNIT:ROUTE_DAY_001:{sequence:02d}"
    unit = next(row for row in subject["input_ledger"]["units"] if row["outcome_unit_id"] == unit_id)
    return next(row for row in unit["assertions"] if row["assertion_type"] == assertion_type)


def _refresh_f9_evidence(payload: dict) -> None:
    core = {key: value for key, value in payload.items() if key != "supporting_evidence_sha256"}
    payload["supporting_evidence_sha256"] = digest_json(core)


def apply_mutation(subject: dict, mutation_id: str) -> None:
    if mutation_id == "immature_as_negative":
        head = _assessment(subject, 3); head["counted_f9"] = False; _sync_assessment(subject, head)
    elif mutation_id == "censored_as_negative":
        head = _assessment(subject, 4); head["counted_f9"] = False; _sync_assessment(subject, head)
    elif mutation_id == "competing_event_as_negative":
        head = _assessment(subject, 5); head["counted_f9"] = False; _sync_assessment(subject, head)
    elif mutation_id == "outside_window_positive":
        head = _assessment(subject, 1); head["booking_episode"]["booking_confirmed_at"] = "2026-08-31T00:00:01Z"; _sync_assessment(subject, head)
    elif mutation_id == "missing_f9_conjunct_positive":
        head = _assessment(subject, 1); head["components"]["actor_role"] = "UNKNOWN"; _sync_assessment(subject, head)
    elif mutation_id == "duplicate_booking_double_counted":
        canonical = _assessment(subject, 8)
        head = _assessment(subject, 9)
        head.update({"assessment_state": "F9_CONFIRMED_SYNTHETIC", "counted_f9": True, "event_ascertainment_state": "EVENT_CONFIRMED", "booking_episode": copy.deepcopy(canonical["booking_episode"]), "components": copy.deepcopy(canonical["components"])})
        _sync_assessment(subject, head)
    elif mutation_id == "post_window_rewrites_prior":
        successor = next(row for row in subject["assessments"] if row["outcome_unit_id"].endswith(":10") and row["revision"] == 2)
        successor["predecessor"]["sha256"] = "0" * 64
    elif mutation_id == "correction_cycle_or_fork":
        successor = next(row for row in subject["assessments"] if row["outcome_unit_id"].endswith(":10") and row["revision"] == 2)
        successor["predecessor"]["assessment_id"] = successor["assessment_id"]
    elif mutation_id == "future_available_evidence_used":
        head = _assessment(subject, 3); head["eligible_assertions"][0]["available_at"] = "2026-09-01T00:00:00Z"; _sync_assessment(subject, head)
    elif mutation_id == "nonmonotonic_clock_chain":
        assertion = subject["input_ledger"]["units"][0]["assertions"][0]
        assertion["recorded_at"] = "2026-08-01T00:00:00Z"
    elif mutation_id == "stage3_changes_stage1":
        subject["input_ledger"]["stage1_unchanged_sha256"] = "0" * 64
    elif mutation_id == "booking_implies_commission":
        head = _assessment(subject, 1); head["downstream_states"]["commission"] = "REALIZED_SYNTHETIC"; _sync_assessment(subject, head)
    elif mutation_id == "unauthorized_window_promoted":
        subject["policy"]["real_policy_authorized"] = True
    elif mutation_id == "partial_route_day_finalized":
        subject["route_day_aggregate"]["final_f9_count"] = subject["route_day_aggregate"]["confirmed_f9_lower_bound"]
        subject["route_day_aggregate"]["route_day_ascertainment_state"] = "FINAL"
    elif mutation_id == "rehashed_label_contamination":
        head = _assessment(subject, 7)
        head["assessment_state"] = "IMMATURE_UNKNOWN"; head["event_ascertainment_state"] = "WINDOW_OPEN"
        _sync_assessment(subject, head); refresh_receipt(subject)
    elif mutation_id == "rehashed_dedupe_reassignment":
        group = next(row for row in subject["dedupe_groups"] if len(row["outcome_unit_ids"]) == 2)
        group["canonical_outcome_unit_id"] = group["outcome_unit_ids"][1]
        refresh_receipt(subject)
    elif mutation_id == "rehashed_correction_history":
        subject["replay_receipt"]["correction_lineage_root_sha256"] = "0" * 64
    elif mutation_id == "replay_receipt_mismatch":
        subject["replay_receipt"]["schema_sha256"] = "0" * 64
    elif mutation_id == "rehashed_input_new_f9":
        unit = next(row for row in subject["input_ledger"]["units"] if row["sequence_position"] == 3)
        assertion = copy.deepcopy(_ledger_assertion(subject, 1, "F9_EVIDENCE"))
        assertion["assertion_id"] = "ASSERTION:ROUTE_DAY_001:03:02"
        assertion["outcome_unit_id"] = unit["outcome_unit_id"]
        assertion["payload"]["booking_episode_id"] = "BOOKING:SYN_ATTACK_NEW_003"
        _refresh_f9_evidence(assertion["payload"])
        unit["assertions"].append(assertion)
        refresh_receipt(subject)
    elif mutation_id == "rehashed_dedupe_split_input":
        payload = _ledger_assertion(subject, 9, "F9_EVIDENCE")["payload"]
        payload["booking_episode_id"] = "BOOKING:SYN_ATTACK_SPLIT_009"
        _refresh_f9_evidence(payload); refresh_receipt(subject)
    elif mutation_id == "rehashed_policy_binding":
        subject["input_ledger"]["policy_sha256"] = "0" * 64; refresh_receipt(subject)
    elif mutation_id == "shifted_assignment_anchor":
        subject["input_ledger"]["route_assignment"]["assigned_at"] = "2026-08-02T00:00:00Z"; refresh_receipt(subject)
    elif mutation_id == "future_booking_before_assessment":
        payload = _ledger_assertion(subject, 1, "F9_EVIDENCE")["payload"]
        payload["booking_confirmed_at"] = "2026-08-20T11:00:00Z"
        _refresh_f9_evidence(payload); refresh_receipt(subject)
    elif mutation_id == "incomplete_watermark_negative":
        _ledger_assertion(subject, 2, "OBSERVATION_WATERMARK")["payload"]["source_complete"] = False; refresh_receipt(subject)
    elif mutation_id == "missing_realtor_identity":
        payload = _ledger_assertion(subject, 1, "F9_EVIDENCE")["payload"]
        payload["senior_commercial_realtor_id"] = ""; _refresh_f9_evidence(payload); refresh_receipt(subject)
    elif mutation_id == "forged_supporting_evidence":
        _ledger_assertion(subject, 1, "F9_EVIDENCE")["payload"]["supporting_evidence_sha256"] = "0" * 64; refresh_receipt(subject)
    elif mutation_id == "appointment_before_booking":
        payload = _ledger_assertion(subject, 1, "F9_EVIDENCE")["payload"]
        payload["appointment_scheduled_at"] = "2026-08-01T00:00:00Z"; _refresh_f9_evidence(payload); refresh_receipt(subject)
    elif mutation_id == "unknown_assertion_type":
        assertion = _ledger_assertion(subject, 3, "OBSERVATION_WATERMARK")
        assertion["assertion_type"] = "UNREGISTERED_ASSERTION"; refresh_receipt(subject)
    elif mutation_id == "assertion_unit_mismatch":
        _ledger_assertion(subject, 1, "F9_EVIDENCE")["outcome_unit_id"] = "OUTCOME_UNIT:ROUTE_DAY_001:02"; refresh_receipt(subject)
    elif mutation_id == "correction_target_missing":
        _ledger_assertion(subject, 10, "CORRECTION")["payload"]["corrects_assertion_id"] = "ASSERTION:ROUTE_DAY_001:10:99"; refresh_receipt(subject)
    elif mutation_id == "post_window_stopper":
        assertion = _ledger_assertion(subject, 4, "CENSORING")
        for offset, field in enumerate(["occurred_at", "recorded_at", "ingested_at", "validation_completed_at", "available_at"]):
            assertion[field] = f"2026-09-01T00:0{offset}:00Z"
        refresh_receipt(subject)
    elif mutation_id == "unregistered_stopper_cause":
        _ledger_assertion(subject, 4, "CENSORING")["payload"]["cause"] = "UNREGISTERED_CAUSE"; refresh_receipt(subject)
    elif mutation_id == "failed_competing_adjudication":
        _ledger_assertion(subject, 5, "COMPETING_EVENT")["payload"]["adjudication"] = "FAIL_SYNTHETIC"; refresh_receipt(subject)
    elif mutation_id == "extra_ledger_field":
        subject["input_ledger"]["unexpected_float"] = 1.25; refresh_receipt(subject)
    elif mutation_id == "common_asof_divergence":
        unit = next(row for row in subject["input_ledger"]["units"] if row["sequence_position"] == 3)
        unit["assessment_cutoffs"][-1] = "2026-08-30T00:01:00Z"; refresh_receipt(subject)
    elif mutation_id == "forged_stopper_evidence":
        _ledger_assertion(subject, 4, "CENSORING")["payload"]["evidence_sha256"] = "0" * 64; refresh_receipt(subject)
    else:
        raise ValueError("unsupported mutation")


def run_known_bad(path: Path) -> tuple[int, dict]:
    recipe = strict_load(path)
    subject = build_outcome_run()
    apply_mutation(subject, recipe["mutation_id"])
    diagnostics = validate_outcome_run(subject)
    detected = diagnostics == [recipe["expected_diagnostic"]]
    payload = {
        "result": "DETECTED" if detected else "SURVIVED",
        "case_id": recipe["case_id"],
        "fixture_sha256": file_sha256(path),
        "diagnostic": diagnostics[0] if len(diagnostics) == 1 else "unexpected diagnostics",
    }
    return (0 if detected else 1), payload


def validate() -> list[str]:
    errors = []
    ledger = build_input_ledger()
    run = build_outcome_run(ledger)
    if strict_load(INPUT_LEDGER) != ledger:
        errors.append("OUTCOMES-INPUT-LEDGER-MISMATCH")
    if strict_load(CANONICAL_RUN) != run:
        errors.append("OUTCOMES-CANONICAL-RUN-MISMATCH")
    errors.extend(validate_outcome_run(run))
    if strict_load(ITT_CASES) != build_itt_inclusion_cases() or validate_itt_inclusion_cases(strict_load(ITT_CASES)):
        errors.append("OUTCOMES-ITT-INCLUSION")
    contract = strict_load(CONTRACT)
    registered = {row["mutation_id"]: row["expected_diagnostic"] for row in contract["registered_mutations"]}
    recipes = [strict_load(path) for path in RECIPES]
    if len(recipes) != len(registered) or set(registered) != {row.get("mutation_id") for row in recipes}:
        errors.append("OUTCOMES-MUTATION-COVERAGE")
    for path, recipe in zip(RECIPES, recipes):
        if registered.get(recipe.get("mutation_id")) != recipe.get("expected_diagnostic"):
            errors.append(f"OUTCOMES-MUTATION-REGISTRY:{recipe.get('case_id')}")
        code, payload = run_known_bad(path)
        if code or payload["result"] != "DETECTED":
            errors.append(f"OUTCOMES-MUTATION-SURVIVED:{recipe.get('case_id')}")
    process = subprocess.run([sys.executable, "-m", "unittest", "evals.public.test_outcomes_labels"], cwd=ROOT, capture_output=True, text=True, timeout=60)
    if process.returncode:
        errors.append("OUTCOMES-PUBLIC-TESTS")
    report = strict_load(REPORT)
    expected_mutation_results = []
    for path in RECIPES:
        _, payload = run_known_bad(path)
        expected_mutation_results.append(payload)
    expected_tests = {
        "public_test_cases": 14,
        "full_public_suite_tests": 70,
        "assessment_revisions": 20,
        "current_outcome_units": 10,
        "registered_mutations_total": len(registered),
        "registered_mutations_detected": len(registered),
    }
    if (
        report.get("result") != "PASS"
        or report.get("proof_level") != 5
        or report.get("registered_mutations_total") != len(registered)
        or report.get("registered_mutations_detected") != len(registered)
        or report.get("mutation_results") != expected_mutation_results
        or report.get("tests") != expected_tests
        or report.get("route_day_aggregate") != run["route_day_aggregate"]
        or report.get("claim") != REPORT_CLAIM
        or report.get("claim_ceiling") != REPORT_CEILING
        or set(report.get("subject_hashes", {})) != REPORT_SUBJECTS
    ):
        errors.append("OUTCOMES-REPORT")
    for relative, expected in report.get("subject_hashes", {}).items():
        if file_sha256(ROOT / relative) != expected:
            errors.append(f"OUTCOMES-REPORT-DIGEST:{relative}")
    return sorted(set(errors))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--known-bad", type=Path)
    args = parser.parse_args()
    if args.known_bad:
        path = args.known_bad if args.known_bad.is_absolute() else ROOT / args.known_bad
        try:
            code, payload = run_known_bad(path)
        except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
            code, payload = 1, {"result": "SURVIVED", "case_id": "invalid", "fixture_sha256": file_sha256(path) if path.is_file() else "", "diagnostic": type(exc).__name__}
        print(json.dumps(payload, sort_keys=True))
        return code
    try:
        errors = validate()
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError):
        errors = ["OUTCOMES-VALIDATION-EXCEPTION"]
    print("PASS" if not errors else "FAIL")
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
