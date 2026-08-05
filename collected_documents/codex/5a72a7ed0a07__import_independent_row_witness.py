"""Import a reviewer-owned narrow row-witness capture with exact byte validation."""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEST = ROOT / "artifacts/research/raw/row_witness"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    args = parser.parse_args()
    source = args.source.resolve()
    manifest = json.loads((source / "capture_manifest.json").read_text())
    if manifest.get("artifact_id") != "RESEARCH-001-INDEPENDENT-ROW-WITNESS-CAPTURE" or manifest.get("capture_role") != "independent_reviewer":
        raise SystemExit("invalid row-witness manifest")
    required = {"TOR-CLOSED-3209741", "TOR-2016-3209741", "ON-TOTAL-LIMIT0", "ON-DISTINCT-LICENCE-LIMIT0", "ON-LICENCE-4716137-COUNT", "ON-LICENCE-4716137-DISTINCT-ADDRESS"}
    captures = manifest.get("captures", [])
    if not required <= {item.get("evidence_id") for item in captures}:
        raise SystemExit("row-witness capture coverage mismatch")
    DEST.mkdir(parents=True, exist_ok=True)
    for item in captures:
        path = source / item["path"]
        if not path.is_file() or sha(path) != item["sha256"] or path.stat().st_size != item["byte_length"]:
            raise SystemExit(f"row-witness capture mismatch: {item['evidence_id']}")
        shutil.copyfile(path, DEST / item["path"])
        item["path"] = f"artifacts/research/raw/row_witness/{item['path']}"
    manifest.pop("capture_directory", None)
    (DEST / "capture_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print("PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
