from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import parse_qs

import httpx
import orjson
import pytest

from cre_foundry.connectors.brampton_business_directory import (
    BLOCKED_UAT_BASE_URL,
    BLOCKED_UAT_ITEM_ID,
    PRODUCTION_BASE_URL,
    PRODUCTION_ITEM_ID,
    BramptonBusinessDirectoryConnector,
    BusinessDirectorySourceConfig,
)


def directory_config(
    *,
    access_state: str = "approved",
) -> BusinessDirectorySourceConfig:
    return BusinessDirectorySourceConfig.model_validate(
        {
            "source_id": ("brampton_business_directory"),
            "name": ("Brampton Business Directory"),
            "base_url": (PRODUCTION_BASE_URL),
            "source_item_id": (PRODUCTION_ITEM_ID),
            "prd_experience_item_id": ("66674743f40f4b4c85d004bdf6a831f2"),
            "access_state": access_state,
            "enabled": True,
            "request_timeout_seconds": 10,
            "batch_size": 2,
            "output_spatial_reference": 4326,
            "layers": [0],
            "license_name": "CC BY",
            "license_url": ("https://example.test/item"),
            "required_attribution": ("Brampton Economic Development"),
            "where_clause": ("OPERATIONAL = 'YES'"),
            "approved_operational_values": ["YES"],
            "blocked_uat_item_id": (BLOCKED_UAT_ITEM_ID),
            "blocked_uat_base_url": (BLOCKED_UAT_BASE_URL),
            "base_cadence_minutes": 1440,
            "minimum_cadence_minutes": 360,
            "maximum_cadence_minutes": 10080,
            "critical_source": False,
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
                    "serviceDescription": ("Business directory"),
                    "maxRecordCount": 2000,
                    "supportedQueryFormats": ("JSON, geoJSON, PBF"),
                },
            )

        if path.endswith("/FeatureServer/0"):
            return httpx.Response(
                200,
                json={
                    "id": 0,
                    "name": ("Business Directory"),
                    "objectIdField": "OBJECTID",
                    "geometryType": ("esriGeometryPoint"),
                    "maxRecordCount": 2000,
                    "supportedQueryFormats": ("JSON, geoJSON, PBF"),
                    "fields": [
                        {
                            "name": "OBJECTID",
                            "type": ("esriFieldTypeOID"),
                        },
                        {
                            "name": "COMPANY_NAME",
                            "type": ("esriFieldTypeString"),
                        },
                        {
                            "name": "OPERATIONAL",
                            "type": ("esriFieldTypeString"),
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

            return httpx.Response(
                200,
                json={
                    "type": ("FeatureCollection"),
                    "features": [
                        {
                            "type": "Feature",
                            "properties": {
                                "OBJECTID": object_id,
                                "COMPANY_NAME": (f"Business {object_id}"),
                                "OPERATIONAL": "YES",
                            },
                            "geometry": None,
                        }
                        for object_id in object_ids
                    ],
                },
            )

        return httpx.Response(
            404,
            json={"error": {"message": "Not found"}},
        )

    return httpx.MockTransport(handler)


def test_acquires_only_operational_production_rows(
    tmp_path: Path,
) -> None:
    seen_where: list[str] = []
    config = directory_config()

    connector = BramptonBusinessDirectoryConnector(
        project_root=tmp_path,
        config=config,
        transport=valid_transport(seen_where),
    )

    result = connector.acquire(
        run_id="RUN-directory-test",
        as_of_timestamp=datetime(
            2026,
            7,
            26,
            tzinfo=UTC,
        ),
    )

    assert result["record_count"] == 3
    assert result["current_status_verified"] is False
    assert result["outreach_eligible"] is False
    assert seen_where == [config.where_clause]

    assert (tmp_path / result["raw_path"]).exists()

    assert (tmp_path / result["manifest_path"]).exists()


def test_uat_identity_fails_before_network(
    tmp_path: Path,
) -> None:
    requests_made = 0

    def handler(
        request: httpx.Request,
    ) -> httpx.Response:
        nonlocal requests_made
        requests_made += 1

        return httpx.Response(500)

    config = directory_config().model_copy(
        update={
            "source_item_id": (BLOCKED_UAT_ITEM_ID),
            "base_url": (BLOCKED_UAT_BASE_URL),
        }
    )

    connector = BramptonBusinessDirectoryConnector(
        project_root=tmp_path,
        config=config,
        transport=httpx.MockTransport(handler),
    )

    with pytest.raises(
        RuntimeError,
        match="approved production",
    ):
        connector.acquire(
            run_id="RUN-uat-blocked",
            as_of_timestamp=datetime(
                2026,
                7,
                26,
                tzinfo=UTC,
            ),
        )

    assert requests_made == 0
    assert not list(tmp_path.rglob("manifest.json"))


def test_rejects_non_operational_records(
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
                    "name": ("Business Directory"),
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
                                "OPERATIONAL": "NO",
                            },
                            "geometry": None,
                        }
                    ],
                },
            )

        return httpx.Response(404)

    connector = BramptonBusinessDirectoryConnector(
        project_root=tmp_path,
        config=directory_config(),
        transport=httpx.MockTransport(handler),
    )

    with pytest.raises(
        RuntimeError,
        match="outside the approved",
    ):
        connector.acquire(
            run_id="RUN-invalid-operational",
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
