from __future__ import annotations

from urllib.parse import parse_qs

import httpx

from cre_foundry.connectors.arcgis import ArcGISClient


def handler(
    request: httpx.Request,
) -> httpx.Response:
    path = request.url.path

    if path.endswith("/MapServer"):
        return httpx.Response(
            200,
            json={
                "serviceDescription": "Test service",
                "maxRecordCount": 1000,
                "supportedQueryFormats": ("JSON, geoJSON, PBF"),
            },
        )

    if path.endswith("/MapServer/1"):
        return httpx.Response(
            200,
            json={
                "id": 1,
                "name": "Development Apps",
                "geometryType": ("esriGeometryPolygon"),
                "fields": [
                    {
                        "name": "OBJECTID",
                        "type": "esriFieldTypeOID",
                    },
                    {
                        "name": "APP_NUMBER",
                        "type": ("esriFieldTypeString"),
                    },
                ],
            },
        )

    if path.endswith("/MapServer/1/query"):
        if request.method == "GET":
            params = request.url.params

            if params.get("returnIdsOnly") == "true":
                return httpx.Response(
                    200,
                    json={
                        "objectIdFieldName": "OBJECTID",
                        "objectIds": [3, 1, 2],
                    },
                )

        if request.method == "POST":
            form = parse_qs(request.content.decode())

            object_ids = {int(value) for value in form["objectIds"][0].split(",")}

            features = [
                {
                    "type": "Feature",
                    "properties": {
                        "OBJECTID": object_id,
                        "APP_NUMBER": (f"APP-{object_id}"),
                    },
                    "geometry": None,
                }
                for object_id in sorted(
                    object_ids,
                    reverse=True,
                )
            ]

            return httpx.Response(
                200,
                json={
                    "type": "FeatureCollection",
                    "features": features,
                },
            )

    return httpx.Response(
        404,
        json={"error": {"message": "Not found"}},
    )


def test_arcgis_fetches_all_ids_using_post_batches() -> None:
    transport = httpx.MockTransport(handler)

    with ArcGISClient(
        base_url=("https://example.test/arcgis/rest/services/Plantrak/MapServer"),
        timeout_seconds=10,
        transport=transport,
    ) as client:
        collection = client.feature_collection(
            1,
            batch_size=2,
            output_spatial_reference=4326,
        )

    object_ids = [feature["properties"]["OBJECTID"] for feature in collection["features"]]

    assert object_ids == [1, 2, 3]


def test_arcgis_service_metadata() -> None:
    transport = httpx.MockTransport(handler)

    with ArcGISClient(
        base_url=("https://example.test/arcgis/rest/services/Plantrak/MapServer"),
        timeout_seconds=10,
        transport=transport,
    ) as client:
        metadata = client.service_metadata()

    assert metadata["maxRecordCount"] == 1000
    assert "geoJSON" in metadata["supportedQueryFormats"]
