from __future__ import annotations

import csv
import json
from collections import Counter
from datetime import date
from pathlib import Path

from cre_foundry.briefs import render_markdown
from cre_foundry.entity_resolution import resolve_event
from cre_foundry.io import load_businesses, load_events
from cre_foundry.models import RankedAccount
from cre_foundry.scoring import score_accounts
from cre_foundry.signals import build_signal
from cre_foundry.storage import EvidenceStore


def run_pipeline(
    *,
    businesses_path: Path,
    events_path: Path,
    output_dir: Path,
    as_of: date,
) -> tuple[list[RankedAccount], dict[str, int]]:
    businesses = load_businesses(businesses_path)
    events = load_events(events_path)
    store = EvidenceStore(output_dir / "evidence.sqlite3")
    store.initialize()

    matches = []
    for event in events:
        store.put(event)
        matches.append((event, resolve_event(event, businesses)))

    matched_ids = [m.business_id for _, m in matches if not m.abstained and m.business_id]
    per_business = Counter(matched_ids)
    signals = []
    for event, match in matches:
        if match.abstained or not match.business_id:
            continue
        signals.append(
            build_signal(
                business_id=match.business_id,
                event=event,
                entity_confidence=match.confidence,
                as_of=as_of,
                corroboration_count=per_business[match.business_id],
            )
        )

    ranked = score_accounts(businesses, signals)
    output_dir.mkdir(parents=True, exist_ok=True)

    (output_dir / "ranked_accounts.json").write_text(
        json.dumps([r.model_dump(mode="json") for r in ranked], indent=2), encoding="utf-8"
    )
    with (output_dir / "ranked_accounts.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["rank", "business_id", "account", "priority_score", "confidence", "top_evidence"])
        for rank, row in enumerate(ranked, start=1):
            writer.writerow([
                rank,
                row.business.business_id,
                row.business.name,
                row.priority_score,
                row.confidence,
                row.signals[0].evidence_summary if row.signals else "",
            ])

    briefs_dir = output_dir / "briefs"
    briefs_dir.mkdir(exist_ok=True)
    for rank, account in enumerate(ranked, start=1):
        slug = account.business.business_id.replace(":", "-")
        (briefs_dir / f"{rank:02d}-{slug}.md").write_text(
            render_markdown(account, rank), encoding="utf-8"
        )

    summary = {
        "businesses": len(businesses),
        "events": len(events),
        "matched": sum(not m.abstained for _, m in matches),
        "abstained": sum(m.abstained for _, m in matches),
        "signals": len(signals),
        "ranked_accounts": len(ranked),
        "evidence_records": store.count(),
    }
    (output_dir / "run_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return ranked, summary
