from __future__ import annotations

from pathlib import Path

import pytest

from cre_foundry.connectors.plantrak import PlantrakConnector
from cre_foundry.source_contracts import SourceConfig


def test_bulk_fetch_fails_closed_while_under_review(
    tmp_path: Path,
) -> None:
    config = SourceConfig(
        source_id="brampton_plantrak",
        name="Brampton Plantrak",
        base_url="https://example.test/MapServer",
        access_state="review",
        enabled=True,
        request_timeout_seconds=10,
        batch_size=100,
        output_spatial_reference=4326,
        layers=[1],
    )

    connector = PlantrakConnector(
        project_root=tmp_path,
        config=config,
    )

    with pytest.raises(
        RuntimeError,
        match="not approved for bulk acquisition",
    ):
        connector.fetch(layer_ids=[1])

    assert not list(tmp_path.rglob("manifest.json"))
    assert not list(tmp_path.rglob("*.geojson.gz"))
