"""Validate the autonomous (proof-level 2) source-feasibility boundary."""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--known-bad", type=Path)
    args = parser.parse_args()
    if args.known_bad:
        return subprocess.call([sys.executable, "scripts/run_research_mutation.py", "--known-bad", str(args.known_bad)], cwd=ROOT)
    return subprocess.call([sys.executable, "scripts/validate_research_completion.py"], cwd=ROOT)


if __name__ == "__main__":
    raise SystemExit(main())
