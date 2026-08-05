"""Import a reviewer-owned exact-byte capture after verifying its manifest."""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEST = ROOT / "artifacts/research/raw/independent"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    args = parser.parse_args()
    source = args.source.resolve()
    manifest_path = source / "capture_manifest.json"
    manifest = json.loads(manifest_path.read_text())
    if manifest.get("artifact_id") != "RESEARCH-001-INDEPENDENT-HTTP-CAPTURE" or manifest.get("capture_role") != "independent_reviewer":
        raise SystemExit("invalid independent manifest authority")
    expected_ids = {"ON-SELECT-PACKAGE", "ON-SELECT-SCHEMA", "TOR-COA-PACKAGE", "TOR-COA-ACTIVE-SCHEMA", "TOR-COA-CLOSED-SCHEMA", "TOR-COA-2016-SCHEMA", "TOR-COA-2001-SCHEMA", "ON-OGL-TERMS", "TOR-OGL-TERMS"}
    captures = manifest.get("captures", [])
    if {item.get("evidence_id") for item in captures} != expected_ids:
        raise SystemExit("independent capture coverage mismatch")
    for item in captures:
        path = source / item["path"]
        if item["http_status"] != 200 or not path.is_file() or sha(path) != item["sha256"] or path.stat().st_size != item["byte_length"]:
            raise SystemExit(f"independent capture mismatch: {item['evidence_id']}")
    DEST.mkdir(parents=True, exist_ok=True)
    for item in captures:
        shutil.copyfile(source / item["path"], DEST / item["path"])
        item["path"] = f"artifacts/research/raw/independent/{item['path']}"
    manifest.pop("capture_directory", None)
    (DEST / "capture_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print("PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
