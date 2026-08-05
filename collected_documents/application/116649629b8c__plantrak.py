from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

import httpx
import yaml

from cre_foundry.connectors.arcgis import (
    ArcGISClient,
    infer_object_id_field,
)
from cre_foundry.raw_storage import (
    utc_now,
    write_layer_snapshot,
    write_manifest,
)
from cre_foundry.source_contracts import (
    SourceConfig,
    SourceRunManifest,
)


def load_source_config(
    path: Path,
) -> SourceConfig:
    payload = yaml.safe_load(path.read_text())

    if not isinstance(payload, dict):
        raise ValueError(f"Invalid source configuration: {path}")

    return SourceConfig.model_validate(payload)


class PlantrakConnector:
    """Point-in-time Brampton Plantrak collector."""

    def __init__(
        self,
        *,
        project_root: Path,
        config: SourceConfig,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self.project_root = project_root
        self.config = config
        self.transport = transport

    def inspect_service(self) -> dict[str, Any]:
        """Inspect metadata without acquiring full source records."""
        with ArcGISClient(
            base_url=self.config.base_url,
            timeout_seconds=(self.config.request_timeout_seconds),
            transport=self.transport,
        ) as client:
            service = client.service_metadata()
            layer_summaries: list[dict[str, Any]] = []

            for layer_id in self.config.layers:
                metadata = client.layer_metadata(layer_id)

                layer_summaries.append(
                    {
                        "id": layer_id,
                        "name": metadata.get("name"),
                        "geometryType": (metadata.get("geometryType")),
                        "objectIdField": (infer_object_id_field(metadata)),
                        "fieldCount": len(metadata.get("fields", [])),
                        "maxRecordCount": metadata.get(
                            "maxRecordCount",
                            service.get("maxRecordCount"),
                        ),
                    }
                )

            return {
                "source_id": self.config.source_id,
                "name": self.config.name,
                "access_state": self.config.access_state,
                "service_url": self.config.base_url,
                "service_description": service.get("serviceDescription"),
                "service_max_record_count": service.get("maxRecordCount"),
                "supported_query_formats": service.get("supportedQueryFormats"),
                "layers": layer_summaries,
            }

    def _assert_bulk_access_approved(
        self,
    ) -> None:
        """Reject acquisition before constructing any HTTP client."""
        if not self.config.enabled:
            raise RuntimeError(f"Source {self.config.source_id} is disabled.")

        if self.config.access_state != "approved":
            raise RuntimeError(
                f"Source {self.config.source_id} is not approved "
                "for bulk acquisition. Metadata inspection only."
            )

    def fetch(
        self,
        *,
        layer_ids: list[int],
        as_of_timestamp: datetime | None = None,
    ) -> SourceRunManifest:
        # This must execute before any network operation.
        self._assert_bulk_access_approved()

        invalid_layers = sorted(set(layer_ids) - set(self.config.layers))

        if invalid_layers:
            raise ValueError(f"Layers are not approved in configuration: {invalid_layers}")

        started_at = utc_now()
        as_of = as_of_timestamp or started_at

        run_id = f"{started_at:%Y%m%dT%H%M%SZ}-{uuid4().hex[:10]}"

        manifest = SourceRunManifest(
            source_id=self.config.source_id,
            run_id=run_id,
            started_at=started_at,
            as_of_timestamp=as_of,
            status="running",
            service_url=self.config.base_url,
        )

        try:
            with ArcGISClient(
                base_url=self.config.base_url,
                timeout_seconds=(self.config.request_timeout_seconds),
                transport=self.transport,
            ) as client:
                for layer_id in layer_ids:
                    metadata = client.layer_metadata(layer_id)

                    collection = client.feature_collection(
                        layer_id,
                        batch_size=self.config.batch_size,
                        output_spatial_reference=(self.config.output_spatial_reference),
                    )

                    snapshot = write_layer_snapshot(
                        project_root=self.project_root,
                        source_id=self.config.source_id,
                        run_id=run_id,
                        layer_id=layer_id,
                        collected_at=utc_now(),
                        as_of_timestamp=as_of,
                        layer_metadata=metadata,
                        feature_collection=collection,
                    )

                    manifest.layer_snapshots.append(snapshot)

            manifest.status = "succeeded"
            manifest.completed_at = utc_now()

        except Exception as exc:
            manifest.status = "failed"
            manifest.completed_at = utc_now()
            manifest.error_type = type(exc).__name__
            manifest.error_message = str(exc)

            write_manifest(
                project_root=self.project_root,
                manifest=manifest,
            )

            raise

        write_manifest(
            project_root=self.project_root,
            manifest=manifest,
        )

        return manifest
