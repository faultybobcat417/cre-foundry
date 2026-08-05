# CRE Foundry

Greenfield implementation repository for the CRE Tip Sheet mission: exactly
ten feasible physical business locations per representative route-day, or
`ABSTAIN_NO_VALID_TEN`.

The verified Project OS v2.2 and reference vault are retained under
`bootstrap/project_os_v2.2/`. Application implementation claims begin from the
repository evidence in `artifacts/bootstrap/`; the packaged synthetic campaign
does not establish field, causal, or commercial performance.

## Bootstrap checks

```bash
cd bootstrap/project_os_v2.2/CRE_Codex_Project_OS_v2.2/launch_kernel
python scripts/validate_os.py
python scripts/validate_research_readiness.py
python scripts/run_level10_campaign.py
python scripts/probe_codex_capabilities.py
python scripts/select_next_task.py
python scripts/compile_task_context.py
```

## Repository checks

```bash
uv sync --python 3.12
uv run --python 3.12 python -m unittest discover -s evals/public -p 'test_*.py'
uv run --python 3.12 python scripts/prove_known_bad_fails.py
uv run --python 3.12 python scripts/validate_control_plane.py
uv run --python 3.12 python evals/public/test_autonomous_frontier.py
uv run --python 3.12 python scripts/evaluate_autonomous_frontier.py \
  --report artifacts/evaluations/autonomous_frontier_report.json
```

The frontier evaluator intentionally returns exit 1 and the exact token
`FAIL` while repository-derivable or publicly researchable work remains. It
may return `BLOCKED_EXTERNAL` only after all autonomous gates pass and no
executable positive-value task remains.

No production data, credentials, outreach, deployment, spending, or promotion
authority is implied by this repository.
