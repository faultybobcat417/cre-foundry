# MASTER BUILD PROMPT v2 — Adaptive CRE Territory & Prospect Prioritization Engine
## (Built for an autonomous coding agent with full shell access — e.g., Codex CLI)

> PASTE THE ORIGINAL ASSIGNMENT BRIEF FIRST, THEN EVERYTHING BELOW THIS LINE.

---

## 0. ROLE, AUTONOMY, AND THE RULE OF RECEIPTS

You are a staff-level data scientist + software engineer pair with full shell access in the current working directory.

- Work **fully autonomously**. Do not ask questions. Where a judgment call is needed, make the most defensible choice and record it in `DECISIONS.md` (choice, alternatives, reason).
- **Rule of receipts:** never claim something works — prove it. For every verification, run the command and paste its real output (row counts, greps, diffs, exit codes).
- Do not stop until the Section 12 checklist fully passes WITH receipts, and the Section 13 red-team pass is complete.
- **Absolute stop rule:** if every real-data source fails and no real data can be obtained, STOP and report the failure. Never substitute invented data. A failed fetch is recoverable; fabricated data is disqualifying.

## 1. MISSION

Design, build, verify, and hand over a working local prototype of an **Adaptive Commercial Real Estate Territory and Prospect Prioritization Engine** for a commercial real estate (CRE) firm running field-based outbound sales in Southern Ontario, Canada.

One command produces a ranked list of **exactly 10** real businesses/commercial locations a rep should physically visit today, with complete per-recommendation reasoning, a spreadsheet built to open in **Google Sheets**, and an offline field map.

This must be genuinely usable by the firm **today**: a non-technical operator can edit config and run it without touching code.

## 2. GRADING RUBRIC (your objective function)

- Problem definition — 10%
- Data strategy — 15%
- Statistical & mathematical rigour — 20%
- Commercial & sales usefulness — 20%
- Geographic & operational design — 15%
- Engineering quality — 10%
- Honesty & critical thinking — 10%

Honesty is graded: no fabricated businesses, addresses, or performance numbers; everything simulated is labeled SIMULATED; limitations stated explicitly; never claim accuracy the evidence cannot support.

## 3. HARD CONSTRAINTS (any violation = failed build)

- No hard-coded final list of businesses — the list is computed from data + config.
- No fabricated businesses/addresses — every recommendation joins to a real snapshot record with a source reference.
- No language model as the ranking mechanism — evidence-based scoring only.
- No paid APIs, no required API keys, no logins. Free and local. (Optional Google Sheets sync MAY use a service account if the operator provides one — but nothing depends on it.)
- No placeholder/TODO/lorem/"coming soon" strings anywhere in outputs or docs. Incomplete items go in `DISCLOSURES.md`.
- Demo path runs 100% offline from the committed snapshot.
- Reproducible: same snapshot + config + seed → identical recommendations.

## 4. ENVIRONMENT & STACK (verify first)

1. Run `python3 --version`, `uname -a`, and check network reachability. Paste outputs.
2. Target: macOS Apple Silicon (8GB RAM), Python 3.11+.
3. Allowed deps only: pandas, numpy, requests, folium, pyyaml, openpyxl, scikit-learn (small jobs). No heavy stacks, no external databases (sqlite3 stdlib only if needed).
4. Create a venv, install pinned `requirements.txt`, and verify imports. Setup + run must be ≤ 5 commands in README.md.

## 5. DATA STRATEGY (real, live-fetched by you, cached for offline)

**Primary source — OpenStreetMap via Overpass API.** Fetch named commercial POIs in the configured municipalities (default: **Mississauga + Brampton, Ontario**).

Query pattern (adapt as needed, keep the name requirement):

```
[out:json][timeout:60];
area["name"="Mississauga"]["boundary"="administrative"]->.a;
area["name"="Brampton"]["boundary"="administrative"]->.b;
(
  nwr["name"]["shop"](area.a);  nwr["name"]["office"](area.a);
  nwr["name"]["industrial"](area.a); nwr["name"]["building"="warehouse"](area.a);
  nwr["name"]["amenity"~"restaurant|cafe|fast_food|dentist|clinic"](area.a);
  nwr["name"]["craft"](area.a);
  nwr["name"]["shop"](area.b);  nwr["name"]["office"](area.b);
  nwr["name"]["industrial"](area.b); nwr["name"]["building"="warehouse"](area.b);
  nwr["name"]["amenity"~"restaurant|cafe|fast_food|dentist|clinic"](area.b);
  nwr["name"]["craft"](area.b);
);
out center tags;
```

- Overpass mirrors (try in order on failure, log each attempt): `https://overpass-api.de/api/interpreter`, `https://overpass.kumi.systems/api/interpreter`, `https://overpass.private.coffee/api/interpreter`.
- Parse to `data/snapshot_YYYY-MM-DD.csv`: name, category (mapped to a clean taxonomy: industrial/warehouse, retail, office, food_service, medical, services, other_commercial), lat, lon (use `center` for ways/relations), address fields (addr:* when present — flag when partial), osm_type, osm_id, source=OSM, fetched_at (UTC).
- **Verify with receipts:** print total rows, counts per municipality, counts per category, % with full address. Sanity-assert: no null names, no duplicate osm_ids, all lat/lon within Southern Ontario bounds (42.5–44.5, -81.5– -78.5). If the fetch yields < 500 usable rows, try the next mirror.
- Copy the verified fetch to `data/snapshot_demo.csv` and commit it. The demo NEVER touches the network.
- **Optional enrichment:** Mississauga/Brampton open-data portals (business licences, building permits). Attempt; on failure log it in `data/source_log.md` and continue. Never block on optional sources.
- **DATA_REGISTER.md**: per source — contribution, update frequency, coverage, limitations, reliability, licensing (OSM = ODbL; include the © OpenStreetMap contributors attribution on the map), fallback behavior.

## 6. SYSTEM DESIGN

### 6.1 Unit of analysis & target
- Unit: **business-location-day**.
- Objective function (documented in METHODOLOGY.md):
  `priority = P(real estate need) × P(reach decision-maker) × E(mandate value) × urgency multiplier − travel cost penalty`
- All weights in config, never in code.

### 6.2 Opportunity engines (4 required)
Buyer, Seller, Investor, Leasing — landlord intent and tenant intent modeled separately inside leasing. Each engine has its own signal-weight profile in config. Each candidate receives a most-likely opportunity type plus the engine's reasoning.

### 6.3 Signals (each classified as measured / inferred / proxy)
- Category-based CRE-need priors (industrial/warehouse → expansion/relocation/lease; retail → lease turnover; office → downsize/right-size; etc.)
- Local business density & commercial-corridor proximity
- Property-mix imbalance (e.g., retail island inside industrial zone)
- Anchor-tenant proximity
- Recent-change signals only where timestamps exist — labeled unreliable where unsupported
- Competitive saturation proxy
- Road accessibility proxy
- Listing/vacancy signals only if enrichment succeeded (else omitted + logged)

### 6.4 Freshness & adaptation
- Per-signal `fetched_at`; exponential decay with configurable half-life per signal class.
- Feedback: Beta-style Bayesian shrinkage on P(need) priors per category × engine from `feedback_log.csv`. Minimum n before any update; clamped per-update deltas; every update timestamped in `data/update_log.jsonl`. Document the guard against noisy rep input.

### 6.5 Confidence
- `confidence = f(signal agreement, freshness, source reliability)` → 0–1 + High/Med/Low band + per-recommendation explanation string. Config has min-confidence filter.

### 6.6 Territory & routing
- Cluster scored candidates (k-means on lat/lon or greedy density).
- Select best cluster given rep start (config lat/lon; default Mississauga City Hall: 43.5890, -79.6441).
- Order 10 stops: nearest-neighbor + 2-opt, haversine distances. Output route_position 1–10, total km, est. minutes. Respect max travel radius.
- If filters leave < 10 candidates, log a clear warning naming the binding filter (do NOT pad with fabricated or out-of-config entries); the shipped default config MUST yield ≥ 10.

### 6.7 Configuration (config.yaml — non-technical editable, commented)
Date, representative, start location, municipalities, max travel radius, asset classes, opportunity types, number of recommendations, previously-visited list, excluded businesses, excluded industries, minimum confidence, freshness requirements, all weights, decay half-lives, seed.

### 6.8 Feedback loop
- `python3 feedback.py` records interactively: visited, decision-maker reached, conversation completed, interest level, opportunity type discovered, follow-up required, appointment booked, lead created, incorrect-recommendation flag, failure reason, notes.
- Appends to `feedback_log.csv`; updates priors per 6.4; previously-visited + exclusions respected in all future runs.

## 7. OUTPUTS (per run → `outputs/YYYY-MM-DD/`)

1. **daily_list.xlsx** — exactly 10 rows × ALL 15 required columns (name, full address, municipality, category, most-likely opportunity type, priority score, confidence, reasons, signals/evidence, data-source references, recommended timing, conversation angle, field instruction, uncertainty/warning, route position). Format it to import cleanly into **Google Sheets**: also emit `daily_list.csv`, freeze header row, bold headers, conditional colour on confidence. Workbook has two tabs: `ROUTE` and `FEEDBACK` (feedback columns matching feedback.py fields, so a rep can log outcomes in Sheets and export CSV).
2. **daily_map.html** — folium: colour-coded by opportunity engine, numbered route markers in visit order, start marker, popups with key fields, OSM attribution. Opens offline from disk.
3. **run_manifest.json** — config hash, snapshot id, seed, timestamp, candidate counts per pipeline stage, degraded sources. The audit trail.
4. Optional `sync_sheets.py` — pushes ROUTE/FEEDBACK to a Google Sheet via gspread IF the operator drops in service-account creds; clearly optional, documented, never required.
- Single entry point: `python3 run.py --config config.yaml`. Zero manual steps.

## 8. VALIDATION (honest — graded under rigour AND honesty)

- `validate.py` vs. 4 baselines on the same snapshot: random selection, nearest-business, business-density ranking, fixed-rule score.
- Outcomes via a documented **SIMULATED** response model (parameters in config; assumptions in VALIDATION.md).
- Metrics: expected decision-makers reached, qualified conversations, leads, expected pipeline value, km travelled, false-positive rate, lift vs. each baseline.
- VALIDATION.md explicitly separates measured vs. backtested vs. SIMULATED vs. assumed vs. not-yet-establishable. Zero real-world accuracy claims.

## 9. DOCUMENTATION (maps to assignment deliverables A–H)

- **README.md** — setup + run + demo script, every command verified by you.
- **OPERATOR_GUIDE.md** — for the firm, non-technical: daily run, editing config, reading the sheet/map, logging feedback, importing to Google Sheets.
- **METHODOLOGY.md** — target, unit of analysis, method + alternatives considered and why rejected (incl. supervised ML: rejected — no labeled outcome data yet; named as the Phase-2 plan), assumptions, confidence calc, validation, adaptation, weaknesses, when NOT to trust the system.
- **DATA_REGISTER.md**, **FEATURE_REGISTER.md** (per variable: meaning, why predictive, calculation, dynamic vs. stable, normalization, missing-value handling, redundancy risk, bias/leakage risk).
- **ARCHITECTURE.md** — mermaid or ASCII diagram: collection → storage → features → scoring → territory optimization → config → output → feedback → monitoring → recalibration.
- **DECISIONS.md** — every autonomous judgment call + reason.
- **DISCLOSURES.md** — everything simulated, inferred, mocked, or incomplete.
- **DEMO_CHEATSHEET.md** — plain English: how it works in 10 bullets; which 3 recommendations to explain live + what to say; one config input to change live + what visibly changes; the feedback demo; missing/stale-data handling; likely questions + answers; next production stage.

## 10. BUILD ORDER

1. Env verify + scaffold + venv + deps (receipts).
2. Live data fetch → verify counts (receipts) → commit `snapshot_demo.csv`.
3. Signals + features with sanity asserts.
4. Scoring + engines + confidence.
5. Clustering + routing.
6. Outputs (xlsx + csv + map + manifest).
7. Feedback loop.
8. Validation + baselines.
9. All documentation.
10. Clean-room: fresh venv, follow README exactly — no fixes allowed; if it breaks, fix code/README until it doesn't.

## 11. ACCEPTANCE CHECKLIST — receipts required for every line

Iterate: run → inspect → fix root cause → re-run, until ALL pass. Paste the command output for each.

- [ ] `python3 run.py --config config.yaml` exits 0 from a fresh venv per README.
- [ ] Output = exactly 10 recommendations, all 15 fields populated. Receipt: row/col counts.
- [ ] Zero placeholders. Receipt: `grep -ri "todo\|placeholder\|lorem\|coming soon\|xxx" outputs/ *.md` → no hits (excluding this prompt's own docs references).
- [ ] Every business joins to a snapshot record (join check printed); none invented.
- [ ] No duplicates; populated exclusion + previously-visited lists provably respected (test with test entries, show before/after).
- [ ] Map renders with network disabled (open file:// URL, confirm markers/route).
- [ ] Changing one config input (max radius or excluded industry) visibly changes the list. Receipt: before/after diff of names.
- [ ] One feedback entry provably changes a future output. Receipt: prior value vs. updated value from `update_log.jsonl`.
- [ ] `validate.py` prints the 4-baseline comparison table; VALIDATION.md labels simulated results SIMULATED.
- [ ] Reproducibility: two runs, same snapshot+config+seed → identical priority scores. Receipt: diff of manifests.
- [ ] Full demo runs with WiFi OFF.
- [ ] Every command in README + DEMO_CHEATSHEET executed and behaves as written.

## 12. RED-TEAM PASS (after checklist passes)

Grade your own output against each of the 7 rubric lines (Section 2), as a hostile evaluator. List the top 3 weaknesses, fix them, re-run the affected checks. Repeat up to 3 rounds; stop when no fixable weakness remains. Log each round in `DECISIONS.md`.

## 13. FINAL REPORT (print at the very end)

1. What is real / what is simulated / what is incomplete.
2. Exact demo commands (offline).
3. Receipts summary for the checklist.
4. Known limitations + next production stage.
5. File tree of everything delivered.

## 14. WORKING STYLE

- Small verifiable steps; execute after each step; fix root causes, never patch over errors.
- A source/approach that fails twice → documented fallback + entry in DISCLOSURES.md.
- Simple, correct, explainable math beats complex math — the rubric explicitly rewards this.
