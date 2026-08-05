"""Known-bad policy: greedy top-ten ignores joint incompatibility constraints."""
import json

from _support import issue, load


def main():
    problem = load()
    rows = sorted(problem["candidates"], key=lambda row: (-row["business_value_units"], row["candidate_id"]))[:10]
    print(json.dumps(issue(problem, rows)))


if __name__ == "__main__":
    main()
