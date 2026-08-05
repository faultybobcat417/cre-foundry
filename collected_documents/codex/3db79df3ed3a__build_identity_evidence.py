"""Generate the IDENTITY-001 S-2 public evidence artifact (identity_synthetic.json).

Uses only the frozen independent evaluator's public functions
(``build_clean_subject``, ``evaluate_subject``, ``evaluate_known_bad``,
``scan_source_independence``) and never imports the identity material
implementation.  The honest public proof ceiling for the frozen layer is 4
(``proof_target: 4``); the evidence therefore records ``proof_level: 4``.
Read-only against every frozen input; run once from a committed tree and commit
the generated artifact.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from evals.public.temporal_identity_evaluator import (  # noqa: PLC0415
    build_clean_subject, evaluate_subject, evaluate_known_bad,
    scan_source_independence, strict_load_json,
    CONTRACT_PATH, SCHEMA_PATH, EVALUATOR_ID,
)

OUT = ROOT / "artifacts/evaluations/identity_synthetic.json"
IMPLEMENTATION_DIR = ROOT / "src/cre_foundry/identity"


def _file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    contract = strict_load_json(CONTRACT_PATH)
    subject = build_clean_subject()
    clean = evaluate_subject(subject)
    fixtures = contract["required_fixtures"]
    fixture_results = []
    for relative in fixtures:
        payload = evaluate_known_bad(ROOT / relative)
        fixture_results.append({
            "fixture": relative,
            "fixture_sha256": _file_sha256(ROOT / relative),
            "case_id": payload.get("case_id"),
            "result": payload.get("result"),
            "diagnostic": payload.get("diagnostic"),
        })
    independence_scan: list[str] = []
    if IMPLEMENTATION_DIR.is_dir():
        independence_scan = scan_source_independence([IMPLEMENTATION_DIR])
    subject_hashes = {
        "contracts/temporal_identity.schema.json": _file_sha256(SCHEMA_PATH),
        "artifacts/identity/public_evaluator_contract.json": _file_sha256(CONTRACT_PATH),
        "evals/public/temporal_identity_evaluator.py": _file_sha256(ROOT / "evals/public/temporal_identity_evaluator.py"),
    }
    for relative in fixtures:
        subject_hashes[relative] = _file_sha256(ROOT / relative)
    all_detected = all(item["result"] == "DETECTED" for item in fixture_results)
    result = "PASS" if clean["passed"] and all_detected and not independence_scan else "FAIL"
    evidence = {
        "artifact_id": "IDENTITY-001-PUBLIC-EVIDENCE",
        "evaluator_id": EVALUATOR_ID,
        "schema_version": "1.0.0",
        "execution_scope": "SYNTHETIC_NON_INFLUENCING",
        "result": result,
        "proof_level": 4,
        "checks": {
            "frozen_contract_present": CONTRACT_PATH.is_file(),
            "frozen_schema_present": SCHEMA_PATH.is_file(),
            "clean_subject_pass": bool(clean["passed"]),
            "registered_fixtures_detected": all_detected,
            "registered_mutation_count": len(contract.get("registered_mutations", [])),
            "stable_diagnostic_count": len(contract.get("stable_diagnostics", [])),
            "source_independence_clean": not independence_scan,
            "source_independence_scan": independence_scan,
            "live_permissions_false": bool(contract.get("live_permissions") is False),
            "external_effect_occurred_false": bool(contract.get("external_effect_occurred") is False),
        },
        "subject_hashes": subject_hashes,
        "mutation_results": fixture_results,
        "claim": "Public proof level 4 establishes deterministic, replayable conformance of "
                 "synthetic temporal identity mechanics, grain distinctness, alternative/ambiguity/"
                 "conflict handling, relocation and closure temporality, fail-closed protection, "
                 "correction and lineage binding, and the registered mutations only.",
        "claim_ceiling": contract.get("claim_ceiling", ""),
        "upstream": {
            "mission_ref": "bootstrap/project_os_v2.2/CRE_Codex_Project_OS_v2.2/launch_kernel/kernel/MISSION.md",
            "task_id": "IDENTITY-001",
            "stage": "S2 public evidence for the frozen independent evaluator",
        },
    }
    OUT.write_text(json.dumps(evidence, indent=2, sort_keys=True) + "\n")
    print(f"wrote {OUT} result={result}")
    return 0 if result == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
