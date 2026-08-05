"""Known-bad mutant: abstains even when a conformance fixture has ten valid locations."""

import argparse
import json


parser = argparse.ArgumentParser()
parser.add_argument("--input", required=True)
parser.parse_args()
print(json.dumps({"decision": "ABSTAIN_NO_VALID_TEN", "locations": [], "reason": "always_abstain"}))
