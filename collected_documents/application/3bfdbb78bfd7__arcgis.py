from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import httpx
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential_jitter,
)


class ArcGISServiceError(RuntimeError):
    """Raised when an ArcGIS service returns an invalid response."""


def infer_object_id_field(
    metadata: dict[str, Any],
) -> str | None:
    """Infer the ArcGIS object-ID field from layer metadata."""
    for key in ("objectIdField", "objectIdFieldName"):
        value = metadata.get(key)

        if isinstance(value, str) and value:
            return value

    fields = metadata.get("fields", [])

    if not isinstance(fields, list):
        return None

    for field in fields:
        if not isinstance(field, dict):
            continue

        if field.get("type") != "esriFieldTypeOID":
            continue

        name = field.get("name")

        if isinstance(name, str) and name:
            return name

    return None


class ArcGISClient:
    """Read-only ArcGIS REST client with deterministic ID batching."""

    def __init__(
        self,
        *,
        base_url: str,
        timeout_seconds: float,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")

        self._client = httpx.Client(
            timeout=httpx.Timeout(timeout_seconds),
            follow_redirects=True,
            transport=transport,
            headers={"User-Agent": ("CRE-Foundry/0.1 (municipal-open-data research)")},
        )

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> ArcGISClient:
        return self

    def __exit__(
        self,
        exc_type: object,
        exc_value: object,
        traceback: object,
    ) -> None:
        self.close()

    @staticmethod
    def _validate_payload(
        payload: object,
        *,
        response_url: str,
    ) -> dict[str, Any]:
        if not isinstance(payload, dict):
            raise ArcGISServiceError(f"Expected an object response from {response_url}.")

        error = payload.get("error")

        if error:
            raise ArcGISServiceError(f"ArcGIS error from {response_url}: {error}")

        return payload

    @retry(
        reraise=True,
        stop=stop_after_attempt(4),
        wait=wait_exponential_jitter(initial=1, max=12),
        retry=retry_if_exception_type(
            (
                httpx.TimeoutException,
                httpx.NetworkError,
                httpx.RemoteProtocolError,
            )
        ),
    )
    def _get_json(
        self,
        url: str,
        *,
        params: dict[str, str],
    ) -> dict[str, Any]:
        response = self._client.get(url, params=params)
        response.raise_for_status()

        return self._validate_payload(
            response.json(),
            response_url=str(response.url),
        )

    @retry(
        reraise=True,
        stop=stop_after_attempt(4),
        wait=wait_exponential_jitter(initial=1, max=12),
        retry=retry_if_exception_type(
            (
                httpx.TimeoutException,
                httpx.NetworkError,
                httpx.RemoteProtocolError,
            )
        ),
    )
    def _post_json(
        self,
        url: str,
        *,
        data: dict[str, str],
    ) -> dict[str, Any]:
        response = self._client.post(url, data=data)
        response.raise_for_status()

        return self._validate_payload(
            response.json(),
            response_url=str(response.url),
        )

    def service_metadata(self) -> dict[str, Any]:
        return self._get_json(
            self.base_url,
            params={"f": "pjson"},
        )

    def layer_metadata(
        self,
        layer_id: int,
    ) -> dict[str, Any]:
        return self._get_json(
            f"{self.base_url}/{layer_id}",
            params={"f": "pjson"},
        )

    def object_ids(
        self,
        layer_id: int,
        *,
        where: str = "1=1",
    ) -> tuple[str, list[int]]:
        payload = self._get_json(
            f"{self.base_url}/{layer_id}/query",
            params={
                "f": "json",
                "where": where,
                "returnIdsOnly": "true",
                "returnGeometry": "false",
            },
        )

        object_field = payload.get("objectIdFieldName") or payload.get("objectIdField")

        if not isinstance(object_field, str) or not object_field:
            metadata = self.layer_metadata(layer_id)
            object_field = infer_object_id_field(metadata)

        if object_field is None:
            raise ArcGISServiceError(f"Layer {layer_id} has no identifiable OID field.")

        raw_ids = payload.get("objectIds", [])

        if raw_ids is None:
            raw_ids = []

        if not isinstance(raw_ids, list):
            raise ArcGISServiceError(f"Layer {layer_id} returned invalid object IDs.")

        object_ids: list[int] = []

        for raw_id in raw_ids:
            if isinstance(raw_id, bool):
                object_ids.append(int(raw_id))
            elif isinstance(raw_id, int):
                object_ids.append(raw_id)
            elif isinstance(raw_id, (float, str)):
                try:
                    object_ids.append(int(raw_id))
                except ValueError:
                    continue

        return object_field, sorted(set(object_ids))

    @staticmethod
    def _chunks(
        values: list[int],
        size: int,
    ) -> Iterator[list[int]]:
        for start in range(0, len(values), size):
            yield values[start : start + size]

    def feature_collection(
        self,
        layer_id: int,
        *,
        batch_size: int,
        output_spatial_reference: int,
        where: str = "1=1",
    ) -> dict[str, Any]:
        object_field, object_ids = self.object_ids(
            layer_id,
            where=where,
        )

        all_features: list[dict[str, Any]] = []

        for object_id_batch in self._chunks(
            object_ids,
            batch_size,
        ):
            # POST prevents long object-ID lists from overflowing
            # proxy or server URL-length limits.
            payload = self._post_json(
                f"{self.base_url}/{layer_id}/query",
                data={
                    "f": "geojson",
                    "objectIds": ",".join(str(object_id) for object_id in object_id_batch),
                    "outFields": "*",
                    "returnGeometry": "true",
                    "outSR": str(output_spatial_reference),
                },
            )

            features = payload.get("features", [])

            if not isinstance(features, list):
                raise ArcGISServiceError(f"Layer {layer_id} returned invalid features.")

            for feature in features:
                if isinstance(feature, dict):
                    all_features.append(feature)

        def object_id_value(
            feature: dict[str, Any],
        ) -> int:
            properties = feature.get("properties", {})

            if not isinstance(properties, dict):
                return -1

            raw_value: object = properties.get(object_field)

            if isinstance(raw_value, bool):
                return int(raw_value)

            if isinstance(raw_value, int):
                return raw_value

            if isinstance(raw_value, (float, str)):
                try:
                    return int(raw_value)
                except ValueError:
                    return -1

            return -1

        all_features.sort(key=object_id_value)

        return {
            "type": "FeatureCollection",
            "features": all_features,
        }
