import argparse
import json


def load():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    args = parser.parse_args()
    return json.load(open(args.input, encoding="utf-8"))


def issue(problem, rows):
    ordered = sorted(rows, key=lambda row: (row["physical_location_id"], row["candidate_id"]))
    gross = sum((row["business_value_units"] or 0) for row in rows)
    return {"schema_version": "1.0.0", "decision_scope": problem["decision_scope"], "oracle_version": "bounded-exhaustive-v1", "decision_id": problem["decision_id"], "snapshot_sha256": problem["snapshot"]["snapshot_sha256"], "policy_version": problem["policy"]["policy_version"], "policy_sha256": problem["policy"]["policy_sha256"], "decision": "ISSUE", "selected": [{"candidate_id": row["candidate_id"], "physical_location_id": row["physical_location_id"]} for row in ordered], "certificate": {"gross_business_value_units": gross, "redundancy_penalty_units": 0, "interference_penalty_units": 0, "business_value_units": gross, "proximity_cost_units": sum(row["proximity_cost_units"] for row in rows), "total_service_minutes": sum(row["service_minutes"] for row in rows), "feasible_sets_evaluated": 1, "canonical_order_not_route_order": True}}
