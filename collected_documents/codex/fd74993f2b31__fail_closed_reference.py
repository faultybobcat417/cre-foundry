"""Non-production reference used only to self-test the public evaluator."""

import argparse
import json


parser = argparse.ArgumentParser()
parser.add_argument("--input", required=True)
args = parser.parse_args()
fixture = json.load(open(args.input, encoding="utf-8"))
valid = [
    item["location_id"]
    for item in fixture["candidates"]
    if item["eligible"] and not item.get("protected_match", False)
]
if len(valid) < 10:
    print(json.dumps({"decision": "ABSTAIN_NO_VALID_TEN", "locations": [], "reason": "fewer_than_ten_valid"}))
else:
    print(json.dumps({"decision": "ISSUE", "locations": valid[:10]}))
