"""Emit exact PASS only when mission invariants, control state, and route negative controls hold.

Default mode is fast and deterministic: it validates the machine-readable
invariant trace (every hard invariant from the launch-kernel INVARIANTS.json
must be covered by current sha256-bound evaluator evidence), reconciles control
state without the full public suite (``validate_control_plane.py
--reconcile-only``), and confirms the registered route negative controls are
rejected.  ``--known-bad`` mode runs one registered fixture through
``prove_known_bad_fails.py``.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
INVARIANTS_PATH = ROOT / "bootstrap/project_os_v2.2/CRE_Codex_Project_OS_v2.2/launch_kernel/kernel/INVARIANTS.json"
INVARIANT_TRACE_PATH = ROOT / "artifacts/evaluations/invariant_trace.json"


def run(argv: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(argv, cwd=ROOT, check=False, capture_output=True, text=True)


def _file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate_invariant_trace() -> list[str]:
    errors: list[str] = []
    if not INVARIANTS_PATH.is_file():
        return ["missing canonical INVARIANTS.json"]
    if not INVARIANT_TRACE_PATH.is_file():
        return ["missing invariant trace artifact"]
    try:
        invariants = json.loads(INVARIANTS_PATH.read_text())
        trace = json.loads(INVARIANT_TRACE_PATH.read_text())
    except json.JSONDecodeError as exc:
        return [f"invariant trace not strictly parseable: {exc}"]
    canonical = {item["id"] for item in invariants.get("hard_invariants", [])}
    if len(canonical) != len(invariants.get("hard_invariants", [])):
        errors.append("canonical INVARIANTS.json has duplicate hard invariant ids")
    by_id = {item.get("invariant_id"): item for item in trace.get("invariants", [])}
    if set(by_id) != canonical:
        missing = sorted(canonical - set(by_id))
        extra = sorted(set(by_id) - canonical)
        if missing:
            errors.append(f"invariant trace misses invariants: {missing}")
        if extra:
            errors.append(f"invariant trace has unknown invariants: {extra}")
    for item in trace.get("invariants", []):
        invariant_id = item.get("invariant_id")
        if invariant_id not in canonical:
            continue
        evidence = item.get("evidence")
        if not isinstance(evidence, list) or not evidence:
            errors.append(f"{invariant_id}: no evidence coverage")
            continue
        for entry in evidence:
            path = ROOT / entry.get("path", "")
            if not path.is_file() or path.is_symlink():
                errors.append(f"{invariant_id}: missing evidence artifact {entry.get('path')}")
            elif _file_sha256(path) != entry.get("sha256"):
                errors.append(f"{invariant_id}: evidence hash mismatch {entry.get('path')}")
    return sorted(set(errors))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--known-bad")
    args = parser.parse_args()
    if args.known_bad:
        result = run([sys.executable, "scripts/prove_known_bad_fails.py", "--known-bad", args.known_bad])
        if result.returncode == 0 and result.stderr == "":
            sys.stdout.write(result.stdout)
            return 0
        print('{"result":"SURVIVED","case_id":"unknown","fixture_sha256":"","diagnostic":"route negative control was not detected"}')
        return 1
    errors = validate_invariant_trace()
    control = run([sys.executable, "scripts/validate_control_plane.py", "--reconcile-only"])
    if control.returncode != 0:
        errors.append("control-state reconciliation failed")
    mutants = run([sys.executable, "scripts/prove_known_bad_fails.py", "--check-only"])
    passed = not errors and mutants.returncode == 0 and mutants.stdout == "PASS\n"
    print("PASS" if passed else "FAIL")
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
