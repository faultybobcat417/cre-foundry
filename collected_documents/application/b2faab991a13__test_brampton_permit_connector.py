from __future__ import annotations

import gzip
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import parse_qs

import httpx
import orjson
import pytest

from cre_foundry.connectors.brampton_permits import (
    BramptonPermitConnector,
    PermitSourceConfig,
)


def permit_config(
    *,
    access_state: str = "approved",
) -> PermitSourceConfig:
    return PermitSourceConfig.model_validate(
        {
            "source_id": ("brampton_building_permits"),
            "name": "Brampton Permits",
            "base_url": ("https://example.test/arcgis/rest/services/BuildingPermit/FeatureServer"),
            "access_state": access_state,
            "enabled": True,
            "request_timeout_seconds": 10,
            "batch_size": 2,
            "output_spatial_reference": 4326,
            "layers": [0],
            "base_cadence_minutes": 360,
            "minimum_cadence_minutes": 60,
            "maximum_cadence_minutes": 1440,
            "critical_source": False,
            "license_name": ("City of Brampton Open Data"),
            "license_url": ("https://example.test/open-data"),
            "required_attribution": ("City of Brampton Open Data"),
            "where_clause": ("SUBDESC IN ('F1: Industrial', 'F2: Industrial', 'F3: Industrial')"),
            "approved_subdescriptions": [
                "F1: Industrial",
                "F2: Industrial",
                "F3: Industrial",
            ],
        }
    )


def valid_transport(
    seen_where: list[str],
) -> httpx.MockTransport:
    def handler(
        request: httpx.Request,
    ) -> httpx.Response:
        path = request.url.path

        if path.endswith("/FeatureServer"):
            return httpx.Response(
                200,
                json={
                    "serviceDescription": ("Permit service"),
                    "maxRecordCount": 2000,
                    "supportedQueryFormats": ("JSON, geoJSON, PBF"),
                },
            )

        if path.endswith("/FeatureServer/0"):
            return httpx.Response(
                200,
                json={
                    "id": 0,
                    "name": "Building Permits",
                    "objectIdField": "OBJECTID",
                    "geometryType": ("esriGeometryPoint"),
                    "fields": [
                        {
                            "name": "OBJECTID",
                            "type": ("esriFieldTypeOID"),
                        },
                        {
                            "name": "SUBDESC",
                            "type": ("esriFieldTypeString"),
                        },
                        {
                            "name": "PERMITNUMBER",
                            "type": ("esriFieldTypeString"),
                        },
                        {
                            "name": "INDATE",
                            "type": ("esriFieldTypeDate"),
                        },
                    ],
                },
            )

        if path.endswith("/FeatureServer/0/query"):
            if request.method == "GET":
                where = request.url.params.get("where")

                if where is not None:
                    seen_where.append(where)

                return httpx.Response(
                    200,
                    json={
                        "objectIdFieldName": ("OBJECTID"),
                        "objectIds": [3, 1, 2],
                    },
                )

            form = parse_qs(request.content.decode())

            object_ids = [int(value) for value in form["objectIds"][0].split(",")]

            features = []

            for object_id in object_ids:
                category = {
                    1: "F1: Industrial",
                    2: "F2: Industrial",
                    3: "F3: Industrial",
                }[object_id]

                features.append(
                    {
                        "type": "Feature",
                        "properties": {
                            "OBJECTID": object_id,
                            "SUBDESC": category,
                            "PERMITNUMBER": (f"26-{object_id:06d}-000-00"),
                            "INDATE": (1784952000000),
                        },
                        "geometry": None,
                    }
                )

            return httpx.Response(
                200,
                json={
                    "type": ("FeatureCollection"),
                    "features": features,
                },
            )

        return httpx.Response(
            404,
            json={"error": {"message": "Not found"}},
        )

    return httpx.MockTransport(handler)


def test_acquires_only_approved_industrial_scope(
    tmp_path: Path,
) -> None:
    seen_where: list[str] = []
    config = permit_config()

    connector = BramptonPermitConnector(
        project_root=tmp_path,
        config=config,
        transport=valid_transport(seen_where),
    )

    result = connector.acquire(
        run_id="RUN-test-permits",
        as_of_timestamp=datetime(
            2026,
            7,
            26,
            tzinfo=UTC,
        ),
    )

    assert result["record_count"] == 3
    assert result["outreach_eligible"] is False
    assert seen_where == [config.where_clause]

    raw_path = tmp_path / result["raw_path"]

    manifest_path = tmp_path / result["manifest_path"]

    assert raw_path.exists()
    assert manifest_path.exists()

    with gzip.open(
        raw_path,
        "rb",
    ) as handle:
        payload = orjson.loads(handle.read())

    object_ids = [feature["properties"]["OBJECTID"] for feature in payload["features"]]

    assert object_ids == [1, 2, 3]


def test_acquisition_fails_closed_without_approval(
    tmp_path: Path,
) -> None:
    requests_made = 0

    def handler(
        request: httpx.Request,
    ) -> httpx.Response:
        nonlocal requests_made
        requests_made += 1

        return httpx.Response(500)

    connector = BramptonPermitConnector(
        project_root=tmp_path,
        config=permit_config(access_state="review"),
        transport=httpx.MockTransport(handler),
    )

    with pytest.raises(
        RuntimeError,
        match="not approved",
    ):
        connector.acquire(
            run_id="RUN-review",
            as_of_timestamp=datetime(
                2026,
                7,
                26,
                tzinfo=UTC,
            ),
        )

    assert requests_made == 0
    assert not list(tmp_path.rglob("*.geojson.gz"))


def test_rejects_records_outside_query_scope(
    tmp_path: Path,
) -> None:
    def handler(
        request: httpx.Request,
    ) -> httpx.Response:
        path = request.url.path

        if path.endswith("/FeatureServer/0"):
            return httpx.Response(
                200,
                json={
                    "id": 0,
                    "name": "Building Permits",
                    "objectIdField": "OBJECTID",
                    "fields": [
                        {
                            "name": "OBJECTID",
                            "type": ("esriFieldTypeOID"),
                        }
                    ],
                },
            )

        if path.endswith("/FeatureServer/0/query"):
            if request.method == "GET":
                return httpx.Response(
                    200,
                    json={
                        "objectIdFieldName": ("OBJECTID"),
                        "objectIds": [1],
                    },
                )

            return httpx.Response(
                200,
                json={
                    "type": ("FeatureCollection"),
                    "features": [
                        {
                            "type": "Feature",
                            "properties": {
                                "OBJECTID": 1,
                                "SUBDESC": ("Two Unit Dwelling"),
                            },
                            "geometry": None,
                        }
                    ],
                },
            )

        return httpx.Response(404)

    connector = BramptonPermitConnector(
        project_root=tmp_path,
        config=permit_config(),
        transport=httpx.MockTransport(handler),
    )

    with pytest.raises(
        RuntimeError,
        match="outside the approved",
    ):
        connector.acquire(
            run_id="RUN-invalid-scope",
            as_of_timestamp=datetime(
                2026,
                7,
                26,
                tzinfo=UTC,
            ),
        )

    manifests = list(tmp_path.rglob("manifest.json"))

    assert len(manifests) == 1

    manifest = orjson.loads(manifests[0].read_bytes())

    assert manifest["status"] == "failed"
