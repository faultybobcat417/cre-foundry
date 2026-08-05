"""Apply declarative research mutants and invoke the normal validator on a copy."""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BUNDLE = ROOT / "artifacts/research"
ALLOWED_ARTIFACTS = {p.name for p in BUNDLE.glob("*.json")}


def reject_duplicates(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate key: {key}")
        result[key] = value
    return result


def load_recipe(path: Path) -> dict:
    recipe = json.loads(path.read_text(), object_pairs_hook=reject_duplicates)
    if set(recipe) != {"case_id", "target", "operation", "expected_before", "value", "expected_diagnostic"}:
        raise ValueError("recipe has missing or extra fields")
    if set(recipe["target"]) != {"artifact", "collection", "selector", "field"}:
        raise ValueError("target has missing or extra fields")
    if recipe["operation"] != "replace" or recipe["target"]["artifact"] not in ALLOWED_ARTIFACTS:
        raise ValueError("unsupported recipe")
    if any(part in recipe["target"]["artifact"] for part in ("/", "..")):
        raise ValueError("unsafe artifact")
    return recipe


def select(document: dict, recipe: dict) -> dict:
    target = recipe["target"]
    rows = document[target["collection"]]
    selector = target["selector"]
    matches = [row for row in rows if row.get(selector["field"]) == selector["equals"]]
    if len(matches) != 1:
        raise ValueError("selector must match exactly once")
    return matches[0]


def get_parent(row: dict, pointer: str):
    parts = [part for part in pointer.split("/") if part]
    parent = row
    for part in parts[:-1]:
        if isinstance(parent, list):
            candidates = [x for x in parent if x.get("key_id") == part]
            if len(candidates) != 1:
                raise ValueError("semantic list selector failed")
            parent = candidates[0]
        else:
            parent = parent[part]
    return parent, parts[-1]


def run_validator(bundle: Path) -> tuple[int, dict]:
    process = subprocess.run([sys.executable, str(ROOT / "scripts/validate_research_completion.py"), "--bundle", str(bundle), "--json"], cwd=ROOT, text=True, capture_output=True, timeout=30)
    return process.returncode, json.loads(process.stdout)


def refresh_manifest(bundle: Path, artifact_name: str) -> None:
    path = bundle / "bundle_manifest.json"
    manifest = json.loads(path.read_text())
    target = f"artifacts/research/{artifact_name}"
    matches = [item for item in manifest["files"] if item["path"] == target]
    if len(matches) != 1:
        raise ValueError("mutated artifact is not uniquely bundle-bound")
    matches[0]["sha256"] = hashlib.sha256((bundle / artifact_name).read_bytes()).hexdigest()
    path.write_text(json.dumps(manifest, indent=2) + "\n")


def refresh_completion_report(bundle: Path, result: str, diagnostics: list[str]) -> None:
    path = bundle / "research_completion_report.json"
    report = json.loads(path.read_text())
    report["result"] = result
    report["computed_diagnostics"] = diagnostics
    path.write_text(json.dumps(report, indent=2) + "\n")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--known-bad", type=Path)
    args = parser.parse_args()
    if not args.known_bad:
        return subprocess.call([sys.executable, str(ROOT / "scripts/validate_research_completion.py")], cwd=ROOT)
    recipe_path = args.known_bad if args.known_bad.is_absolute() else ROOT / args.known_bad
    tree_before = {p.relative_to(BUNDLE).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in BUNDLE.rglob("*") if p.is_file()}
    try:
        recipe = load_recipe(recipe_path)
        pristine_code, pristine = run_validator(BUNDLE)
        if pristine_code or pristine["diagnostics"]:
            raise ValueError("pristine bundle does not pass")
        with tempfile.TemporaryDirectory(prefix="research-mutant-") as temp:
            mutant = Path(temp) / "research"
            shutil.copytree(BUNDLE, mutant)
            artifact = mutant / recipe["target"]["artifact"]
            document = json.loads(artifact.read_text())
            row = select(document, recipe)
            parent, field = get_parent(row, recipe["target"]["field"])
            if parent[field] != recipe["expected_before"]:
                raise ValueError("wrong or stale mutation preimage")
            if parent[field] == recipe["value"]:
                raise ValueError("no-op mutation")
            parent[field] = recipe["value"]
            artifact.write_text(json.dumps(document, indent=2) + "\n")
            refresh_manifest(mutant, recipe["target"]["artifact"])
            refresh_completion_report(mutant, "FAIL", [recipe["expected_diagnostic"]])
            code, result = run_validator(mutant)
            detected = code != 0 and result["diagnostics"] == [recipe["expected_diagnostic"]]
            repair = copy.deepcopy(document)
            repaired_row = select(repair, recipe)
            repaired_parent, repaired_field = get_parent(repaired_row, recipe["target"]["field"])
            repaired_parent[repaired_field] = recipe["expected_before"]
            artifact.write_text(json.dumps(repair, indent=2) + "\n")
            refresh_manifest(mutant, recipe["target"]["artifact"])
            refresh_completion_report(mutant, "PASS", [])
            repair_code, repair_result = run_validator(mutant)
            detected = detected and repair_code == 0 and not repair_result["diagnostics"]
        tree_after = {p.relative_to(BUNDLE).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in BUNDLE.rglob("*") if p.is_file()}
        detected = detected and tree_before == tree_after
        output = {"result": "DETECTED" if detected else "SURVIVED", "case_id": recipe["case_id"], "fixture_sha256": hashlib.sha256(recipe_path.read_bytes()).hexdigest(), "diagnostic": recipe["expected_diagnostic"] if detected else "mutation protocol failed"}
    except (OSError, ValueError, KeyError, TypeError, AttributeError, json.JSONDecodeError, subprocess.SubprocessError) as exc:
        output = {"result": "SURVIVED", "case_id": "invalid", "fixture_sha256": hashlib.sha256(recipe_path.read_bytes()).hexdigest() if recipe_path.is_file() else "", "diagnostic": str(exc)}
    print(json.dumps(output, sort_keys=True))
    return 0 if output["result"] == "DETECTED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
