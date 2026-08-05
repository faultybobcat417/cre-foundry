"""Run frontier adversarial tests and state reconciliation with exact output."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def run(argv: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(argv, cwd=ROOT, check=False, capture_output=True, text=True)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--known-bad")
    args = parser.parse_args()
    if args.known_bad:
        result = run(
            [sys.executable, "evals/public/test_autonomous_frontier.py", "--known-bad", args.known_bad]
        )
        if result.returncode == 0 and result.stderr == "":
            sys.stdout.write(result.stdout)
            return 0
        print('{"result":"SURVIVED","case_id":"unknown","fixture_sha256":"","diagnostic":"frontier negative control was not detected"}')
        return 1
    tests = run([sys.executable, "evals/public/test_autonomous_frontier.py"])
    control = run([sys.executable, "scripts/validate_control_plane.py", "--reconcile-only"])
    passed = tests.returncode == 0 and control.returncode == 0
    print("PASS" if passed else "FAIL")
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
