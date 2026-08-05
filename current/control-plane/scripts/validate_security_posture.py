
#!/usr/bin/env python3
"""Read-only frozen SECURITY-001 evaluator validator."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from evals.public.security_posture_evaluator import (
    build_clean_subject,
    evaluate_known_bad,
    evaluate_subject,
)

FROZEN_SHA256 = {
    "artifacts/security/SECURITY-001-start.json": "3e53e03e7b004d51ba52d8efc2805aaaf896402cf99d44bb103faf17218ddf05",
    "artifacts/security/public_evaluator_contract.json": "61bb1ef04fd8eeae5ac1b0eb9d3f5326cce4a2b23e2af4dc04f9d1dabc42b401",
    "contracts/security_posture.schema.json": "d3bc705541c49f1f846882579e1ea9b009bd57994f94a17f8cd823eb1b9100b4",
    "evals/known_bad/frontier/security001/security_deletion_refused.json": "450c995b5917b375bf47b72b6fe72122902394802cdc0fd667d9e149f61821cf",
    "evals/known_bad/frontier/security001/security_live_default.json": "987fc9d96e7599decc04406810450464d91c8af51a29f807a4ef4b30e4309d0a",
    "evals/known_bad/frontier/security001/security_retention_violation.json": "491dbc4e5799ba12efbbebb067fa6a20617e424bce0f9742ed8f42e5bafbfc2a",
    "evals/known_bad/frontier/security001/security_secret_log.json": "0fc585002b110878ebd2a0643cd29969219558d65cd38f9b0d41ed2ac662fc40",
    "evals/known_bad/frontier/security001/security_unauthorized_write.json": "0443ebefb173f18af09196aa053cc04e13cfbf2398df603198c90023b4edbcd8",
    "evals/known_bad/frontier/security_pii_log.json": "a14773e5d239d97e7a2c57f508a197749c13d8084340c07a78ff36b153f04f3b",
    "evals/known_bad/frontier/security_retrieved_authority.json": "eddee3f7d8e70f8512e74b49049fae43b1273cbe6188e0a937318d901e73cd88",
    "evals/public/security_posture_evaluator.py": "49296226b0a1b245d0071b9acf936c04365d892c7f6a61c69f2c0af4ec8b51bc"
}
REQUIRED_FIXTURES = [
    "evals/known_bad/frontier/security001/security_secret_log.json",
    "evals/known_bad/frontier/security_pii_log.json",
    "evals/known_bad/frontier/security_retrieved_authority.json",
    "evals/known_bad/frontier/security001/security_unauthorized_write.json",
    "evals/known_bad/frontier/security001/security_live_default.json",
    "evals/known_bad/frontier/security001/security_retention_violation.json",
    "evals/known_bad/frontier/security001/security_deletion_refused.json"
]


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def check_frozen(errors: list[str]) -> None:
    for relative, expected in FROZEN_SHA256.items():
        path = ROOT / relative
        if not path.is_file():
            errors.append(f"FROZEN-MISSING:{relative}")
        elif file_sha256(path) != expected:
            errors.append(f"FROZEN-CHANGED:{relative}")


def validate_all() -> list[str]:
    errors: list[str] = []
    check_frozen(errors)

    clean = evaluate_subject(build_clean_subject())
    if not clean["passed"] or clean["diagnostics"]:
        errors.append("SECURITY-CLEAN-SUBJECT")

    for relative in REQUIRED_FIXTURES:
        path = ROOT / relative
        payload = evaluate_known_bad(path)
        if payload.get("result") != "DETECTED":
            errors.append(f"SECURITY-MUTATION-SURVIVED:{payload.get('case_id')}")

    return sorted(set(errors))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--known-bad", type=Path)
    args = parser.parse_args()

    if args.known_bad is not None:
        path = args.known_bad
        if not path.is_absolute():
            path = ROOT / path
        try:
            payload = evaluate_known_bad(path)
        except Exception as exc:
            payload = {
                "result": "SURVIVED",
                "case_id": "invalid",
                "fixture_sha256": "",
                "diagnostic": str(exc),
            }
        print(json.dumps(payload, sort_keys=True))
        return 0 if payload.get("result") == "DETECTED" else 1

    errors = validate_all()
    print("PASS" if not errors else "FAIL")
    for error in errors:
        print(f"  {error}", file=sys.stderr)
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
