"""Persist derived RESEARCH-001 hashes and completion status."""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from validate_research_completion import FILES, ROOT, validate_bundle

BUNDLE = ROOT / "artifacts/research"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    bound = [BUNDLE / name for name in FILES]
    bound += sorted(path for path in (BUNDLE / "raw").rglob("*") if path.is_file())
    bound += sorted((ROOT / "contracts/research").glob("*.json"))
    manifest = {
        "artifact_id": "RESEARCH-001-BUNDLE-MANIFEST",
        "schema_version": "1.0.0",
        "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "files": [{"path": path.relative_to(ROOT).as_posix(), "sha256": sha(path)} for path in bound],
    }
    (BUNDLE / "bundle_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    errors = validate_bundle(BUNDLE, validate_report=False)
    source_registry = json.loads((BUNDLE / "source_feasibility_registry.json").read_text())
    report = {
        "artifact_id": "RESEARCH-001-COMPLETION-REPORT",
        "schema_version": "2.0.0",
        "result": "PASS" if not errors else "FAIL",
        "proof_level": 2,
        "claim_ceiling": "Strict public research-contract and mutation evidence only; no coverage, join accuracy, association, causal, operational, or commercial proof.",
        "computed_diagnostics": errors,
        "bundle_manifest": "artifacts/research/bundle_manifest.json",
        "artifacts": [f"artifacts/research/{name}" for name in FILES],
        "schemas": [f"contracts/research/{name.replace('.json', '.schema.json')}" for name in FILES],
        "open_gates": source_registry["external_gates"],
        "unresolved_evidence": ["Independent exact-byte evidence is limited to current metadata/schema, narrow aggregates, and two narrow Toronto counterexample rows; it is not an authorized operational or representative source sample.", "No bulk or operational source-row acquisition, historical replay, coverage audit, live-use authority, predictive evidence, or causal evidence has been granted."],
    }
    (BUNDLE / "research_completion_report.json").write_text(json.dumps(report, indent=2) + "\n")
    final_errors = validate_bundle(BUNDLE)
    if final_errors:
        report["result"] = "FAIL"
        report["computed_diagnostics"] = final_errors
        (BUNDLE / "research_completion_report.json").write_text(json.dumps(report, indent=2) + "\n")
    print(report["result"])
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
