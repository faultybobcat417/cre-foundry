"""Known-bad policy: choose the first ten admissible candidates in input order."""
import json

from _support import issue, load


def main():
    problem = load()
    rows = [
        row for row in problem["candidates"]
        if row["protected_status"] == "CLEAR"
        and all(value == "PASS" for value in row["gates"].values())
        and row["value_state"] == "REGISTERED_SYNTHETIC_PROXY"
    ][:10]
    print(json.dumps(issue(problem, rows)))


if __name__ == "__main__":
    main()
