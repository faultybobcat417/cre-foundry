from datetime import date
from pathlib import Path

from cre_foundry.pipeline import run_pipeline

ROOT = Path(__file__).resolve().parents[1]


def test_demo_pipeline_is_end_to_end_and_abstains(tmp_path):
    rows, summary = run_pipeline(
        businesses_path=ROOT / "fixtures" / "businesses.csv",
        events_path=ROOT / "fixtures" / "events.csv",
        output_dir=tmp_path / "out",
        as_of=date(2026, 8, 15),
    )
    assert rows
    assert rows[0].business.business_id == "biz:northstar"
    assert summary["events"] == 7
    assert summary["abstained"] >= 2
    assert (tmp_path / "out" / "ranked_accounts.json").exists()
    assert (tmp_path / "out" / "briefs").is_dir()


def test_pipeline_is_deterministic(tmp_path):
    kwargs = dict(
        businesses_path=ROOT / "fixtures" / "businesses.csv",
        events_path=ROOT / "fixtures" / "events.csv",
        as_of=date(2026, 8, 15),
    )
    rows1, _ = run_pipeline(output_dir=tmp_path / "a", **kwargs)
    rows2, _ = run_pipeline(output_dir=tmp_path / "b", **kwargs)
    assert [(r.business.business_id, r.priority_score) for r in rows1] == [
        (r.business.business_id, r.priority_score) for r in rows2
    ]
