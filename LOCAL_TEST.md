# Local test plan

## 1. Unpack and create an environment

```bash
cd cre-foundry-showcase
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -e . pytest
```

## 2. Verify the environment

```bash
cre-foundry doctor
```

## 3. Run the complete offline demo

```bash
cre-foundry demo
```

You should see three ranked accounts, with Northstar Logistics first, and a run summary showing 7 evidence events, 5 matched events, and 2 abstentions.

## 4. Inspect generated artifacts

```bash
find outputs/demo -maxdepth 2 -type f -print
cat outputs/demo/run_summary.json
cat outputs/demo/ranked_accounts.csv
```

Each ranked account also gets a Markdown evidence brief under `outputs/demo/briefs/`.

## 5. Run the tests

```bash
pytest
python -m compileall -q src tests
```

Expected result: all tests pass.

## 6. Optional live public-source smoke test

This requires internet access:

```bash
cre-foundry fetch-brampton --limit 10
```

The command uses a bounded query against the City of Brampton public building-permits ArcGIS service. It is deliberately separate from the deterministic offline demo.
