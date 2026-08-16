# Verification

This repository is designed so a reviewer can verify the important claims in minutes.

## Environment used

- macOS on Apple Silicon
- Python 3.12.13
- isolated virtual environment
- package installed editable from the repository root

## Offline verification

Commands:

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -e . pytest
cre-foundry doctor
cre-foundry validate fixtures
cre-foundry demo
pytest
python -m compileall -q src tests
```

Observed results:

```text
Fixtures:           OK
Operating mode:     review-only
Businesses:         6
Evidence events:    7
Accepted matches:   5
Abstentions:        2
Signals:            5
Ranked accounts:    3
Evidence records:   7
Tests:              7 passed
Compile check:      PASS
```

The two abstentions are intentional. The fixture set includes ambiguous identity conditions so the resolver proves it can refuse a weak match rather than manufacturing certainty.

## Live-source verification

Command:

```bash
cre-foundry fetch-brampton --limit 10
```

Observed result:

```text
Fetched 10 permit event(s).
- 88595: 9 Van Der Graaf Crt, Brampton, ON, L6T 5E5 — 2000-12-20
- 88629: 7525 Financial Dr, Brampton, ON, L6Y 5P4 — 2004-04-23
- 88665: 8480 Highway 50, Unit 1, Brampton, ON — 2024-01-02
- 88695: 25 Production Rd, Brampton, ON, L6T 4N8 — 2016-11-09
- 88713: 151 East Dr, Brampton, ON, L6T 1B5 — 2023-10-11
```

Only five rows are displayed by the CLI for readability; the adapter reported ten fetched records.

The live adapter is intentionally a smoke test of the source boundary. The checked-in demo remains synthetic and deterministic, so cloning the repository does not depend on current network state.

## Release boundary

Passing these checks establishes that the repository installs, runs its deterministic pipeline, passes its current test suite, compiles, and can acquire a bounded sample from the configured public source.

It does **not** establish proven commercial lift, production readiness, or authorization for automated outreach.
