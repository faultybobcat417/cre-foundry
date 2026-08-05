"""Capture public, non-row or aggregate-only research evidence with byte hashes."""

from __future__ import annotations

import argparse
import hashlib
import json
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "artifacts/research/raw"
BASE_ON = "https://data.ontario.ca/api/3/action"
BASE_TO = "https://ckan0.cf.opendata.inter.prod-toronto.ca/api/3/action"


def sql_url(base: str, sql: str) -> str:
    return f"{base}/datastore_search_sql?{urllib.parse.urlencode({'sql': sql})}"


SOURCES = {
    "on_select_package": f"{BASE_ON}/package_show?id=5f0c3532-6e42-4ed7-a92c-ecde22bfea06",
    "on_select_schema": f"{BASE_ON}/datastore_search?resource_id=5a4f44a7-c656-4977-b4d0-91bedaa0ea06&limit=0",
    "on_select_aggregate": sql_url(
        BASE_ON,
        'SELECT count(*) AS row_count, count(DISTINCT "Licence number") AS licence_count '
        'FROM "5a4f44a7-c656-4977-b4d0-91bedaa0ea06"',
    ),
    "on_select_multi_licence": sql_url(
        BASE_ON,
        'SELECT "Licence number", count(*) AS observation_count '
        'FROM "5a4f44a7-c656-4977-b4d0-91bedaa0ea06" '
        'GROUP BY "Licence number" HAVING count(*) > 1 ORDER BY observation_count DESC LIMIT 20',
    ),
    "on_ogl_terms": "https://www.ontario.ca/page/open-government-licence-ontario",
    "tor_coa_package": f"{BASE_TO}/package_show?id=committee-of-adjustment-applications",
    "tor_coa_active_schema": f"{BASE_TO}/datastore_search?resource_id=51fd09cd-99d6-430a-9d42-c24a937b0cb0&limit=0",
    "tor_coa_closed_schema": f"{BASE_TO}/datastore_search?resource_id=9c97254e-5460-4799-896f-c7823413c81c&limit=0",
    "tor_coa_2016_schema": f"{BASE_TO}/datastore_search?resource_id=b3876c3c-c706-442f-80f6-4ad3e12839c1&limit=0",
    "tor_coa_2001_schema": f"{BASE_TO}/datastore_search?resource_id=f4e0790c-74bb-4ea9-b3c4-9a7dd6173a8d&limit=0",
    "tor_coa_conflict_2016": sql_url(
        BASE_TO,
        'SELECT "SYS_ID","REFERENCE_FILE","IN_DATE","PLANNING_DISTRICT","ZONING_DESIGNATION",'
        '"DESCRIPTION","HEARING_DATE","TIME_OF_MEETING","C_OF_A_DESCISION","APPEAL_EXPIRY_DATE" '
        'FROM "b3876c3c-c706-442f-80f6-4ad3e12839c1" WHERE "SYS_ID" = 3209741',
    ),
    "tor_coa_conflict_closed": sql_url(
        BASE_TO,
        'SELECT "SYS_ID","REFERENCE_FILE#","IN_DATE","PLANNING_DISTRICT","ZONING_DESIGNATION",'
        '"DESCRIPTION","HEARING_DATE","TIME_OF_MEETING","C_OF_A_DESCISION","APPEAL_EXPIRY_DATE" '
        'FROM "9c97254e-5460-4799-896f-c7823413c81c" WHERE "SYS_ID" = \'3209741\'',
    ),
    "tor_ogl_terms": "https://open.toronto.ca/open-data-licence/",
}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--observed-at", required=True)
    parser.add_argument("--evidence", action="append", choices=sorted(SOURCES))
    args = parser.parse_args()
    observed = datetime.fromisoformat(args.observed_at.replace("Z", "+00:00"))
    if observed.tzinfo is None or observed > datetime.now(timezone.utc):
        raise SystemExit("observed-at must be timezone-aware and not future")
    OUTPUT.mkdir(parents=True, exist_ok=True)
    manifest_path = OUTPUT / "manifest.json"
    if args.evidence and manifest_path.is_file():
        prior = json.loads(manifest_path.read_text()).get("evidence", [])
        selected_ids = {item.upper().replace("_", "-") for item in args.evidence}
        manifest = [item for item in prior if item.get("evidence_id") not in selected_ids]
    else:
        manifest = []
    selected = set(args.evidence or SOURCES)
    for evidence_id, url in SOURCES.items():
        if evidence_id not in selected:
            continue
        request = urllib.request.Request(url, headers={"User-Agent": "CRE-Foundry-research/1.0"})
        raw = None
        failure = None
        for attempt in range(5):
            try:
                with urllib.request.urlopen(request, timeout=30) as response:
                    raw = response.read()
                break
            except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError) as exc:
                failure = f"{type(exc).__name__}: {exc}"
                if not isinstance(exc, urllib.error.HTTPError) or exc.code != 429 or attempt == 4:
                    break
                time.sleep(min(2 ** attempt, 8))
        if raw is None:
            manifest.append(
                {
                    "evidence_id": evidence_id.upper().replace("_", "-"),
                    "url": url,
                    "retrieved_at": args.observed_at,
                    "status": "unavailable",
                    "error": failure,
                }
            )
            continue
        try:
            payload = json.loads(raw)
            canonical = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode() + b"\n"
            suffix = ".json"
        except json.JSONDecodeError:
            canonical = raw
            suffix = ".html"
        path = OUTPUT / f"{evidence_id}{suffix}"
        path.write_bytes(canonical)
        manifest.append(
            {
                "evidence_id": evidence_id.upper().replace("_", "-"),
                "url": url,
                "retrieved_at": args.observed_at,
                "path": path.relative_to(ROOT).as_posix(),
                "sha256": hashlib.sha256(canonical).hexdigest(),
                "http_payload_sha256": hashlib.sha256(raw).hexdigest(),
                "status": "captured",
            }
        )
    manifest_path.write_text(
        json.dumps({"artifact_id": "RESEARCH-001-RAW-MANIFEST", "evidence": manifest}, indent=2) + "\n"
    )
    print("PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
