from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

import httpx
import yaml
from pydantic import Field

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


class PermitSourceConfig(SourceConfig):
    """Governance and query contract for permit acquisition."""

    license_name: str = Field(min_length=1)
    license_url: str = Field(min_length=1)
    required_attribution: str = Field(min_length=1)
    where_clause: str = Field(min_length=1)
    approved_subdescriptions: list[str] = Field(min_length=1)


def load_permit_config(
    path: Path,
) -> PermitSourceConfig:
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))

    if not isinstance(payload, dict):
        raise ValueError(f"Invalid source configuration: {path}")

    return PermitSourceConfig.model_validate(payload)


class BramptonPermitConnector:
    """Filtered collector for Brampton industrial permits."""

    def __init__(
        self,
        *,
        project_root: Path,
        config: PermitSourceConfig,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self.project_root = project_root
        self.config = config
        self.transport = transport

    def _assert_acquisition_approved(
        self,
    ) -> None:
        if not self.config.enabled:
            raise RuntimeError(f"Source {self.config.source_id} is disabled.")

        if self.config.access_state != "approved":
            raise RuntimeError(f"Source {self.config.source_id} is not approved for acquisition.")

    def _layer_id(self) -> int:
        if len(self.config.layers) != 1:
            raise RuntimeError("Permit source must configure exactly one approved layer.")

        return self.config.layers[0]

    def inspect_service(self) -> dict[str, Any]:
        layer_id = self._layer_id()

        with ArcGISClient(
            base_url=self.config.base_url,
            timeout_seconds=(self.config.request_timeout_seconds),
            transport=self.transport,
        ) as client:
            service = client.service_metadata()
            metadata = client.layer_metadata(layer_id)

        return {
            "source_id": self.config.source_id,
            "name": self.config.name,
            "access_state": (self.config.access_state),
            "enabled": self.config.enabled,
            "service_url": self.config.base_url,
            "layer_id": layer_id,
            "layer_name": metadata.get("name"),
            "object_id_field": (infer_object_id_field(metadata)),
            "geometry_type": metadata.get("geometryType"),
            "field_names": [
                field.get("name") for field in metadata.get("fields", []) if isinstance(field, dict)
            ],
            "where_clause": (self.config.where_clause),
            "approved_subdescriptions": (self.config.approved_subdescriptions),
            "license_name": (self.config.license_name),
            "license_url": (self.config.license_url),
            "required_attribution": (self.config.required_attribution),
            "service_max_record_count": (service.get("maxRecordCount")),
            "supported_query_formats": (service.get("supportedQueryFormats")),
        }

    def _validate_collection(
        self,
        collection: dict[str, Any],
    ) -> None:
        features = collection.get("features")

        if not isinstance(features, list):
            raise RuntimeError("Permit collection has no valid feature list.")

        approved = set(self.config.approved_subdescriptions)

        invalid: list[str] = []

        for feature in features:
            if not isinstance(feature, dict):
                raise RuntimeError("Permit collection contains an invalid feature.")

            properties = feature.get("properties")

            if not isinstance(
                properties,
                dict,
            ):
                raise RuntimeError("Permit feature has no valid properties.")

            subdescription = properties.get("SUBDESC")

            if subdescription not in approved:
                invalid.append(str(subdescription))

        if invalid:
            values = sorted(set(invalid))

            raise RuntimeError(
                f"Permit query returned records outside the approved industrial scope: {values}"
            )

    def acquire(
        self,
        *,
        run_id: str,
        as_of_timestamp: datetime,
    ) -> dict[str, Any]:
        self._assert_acquisition_approved()

        layer_id = self._layer_id()
        started_at = utc_now()

        manifest = SourceRunManifest(
            source_id=self.config.source_id,
            run_id=run_id,
            started_at=started_at,
            as_of_timestamp=as_of_timestamp,
            status="running",
            service_url=self.config.base_url,
        )

        try:
            with ArcGISClient(
                base_url=self.config.base_url,
                timeout_seconds=(self.config.request_timeout_seconds),
                transport=self.transport,
            ) as client:
                metadata = client.layer_metadata(layer_id)

                collection = client.feature_collection(
                    layer_id,
                    batch_size=(self.config.batch_size),
                    output_spatial_reference=(self.config.output_spatial_reference),
                    where=(self.config.where_clause),
                )

            self._validate_collection(collection)

            snapshot = write_layer_snapshot(
                project_root=self.project_root,
                source_id=self.config.source_id,
                run_id=run_id,
                layer_id=layer_id,
                collected_at=utc_now(),
                as_of_timestamp=as_of_timestamp,
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

        manifest_path = write_manifest(
            project_root=self.project_root,
            manifest=manifest,
        )

        snapshot_path = self.project_root / snapshot.raw_path

        return {
            "source_id": self.config.source_id,
            "run_id": run_id,
            "status": manifest.status,
            "layer_id": layer_id,
            "record_count": (snapshot.record_count),
            "raw_path": snapshot.raw_path,
            "raw_sha256": snapshot.sha256,
            "schema_fingerprint": (snapshot.schema_fingerprint),
            "manifest_path": str(manifest_path.relative_to(self.project_root)),
            "bytes_written": (snapshot_path.stat().st_size + manifest_path.stat().st_size),
            "where_clause": (self.config.where_clause),
            "approved_subdescriptions": (self.config.approved_subdescriptions),
            "required_attribution": (self.config.required_attribution),
            "outreach_eligible": False,
        }
