"""Known-bad mutant: ignores the fixture's pre-adjudicated protection flag."""

import argparse
import json


parser = argparse.ArgumentParser()
parser.add_argument("--input", required=True)
args = parser.parse_args()
fixture = json.load(open(args.input, encoding="utf-8"))
selected = [item["location_id"] for item in fixture["candidates"] if item["eligible"]][:10]
print(json.dumps({"decision": "ISSUE", "locations": selected}))
