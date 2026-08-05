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

PRODUCTION_ITEM_ID = "3cd59a895f404612b57e4c84fc8931be"

PRODUCTION_BASE_URL = (
    "https://services3.arcgis.com/"
    "rl7ACuZkiFsmDA2g/arcgis/rest/services/"
    "Economic_Development/FeatureServer"
)

PRD_EXPERIENCE_ITEM_ID = "66674743f40f4b4c85d004bdf6a831f2"

BLOCKED_UAT_ITEM_ID = "9e0656bfa1174df08d99c1ef4c11759e"

BLOCKED_UAT_BASE_URL = (
    "https://services3.arcgis.com/"
    "rl7ACuZkiFsmDA2g/arcgis/rest/services/"
    "Economic_Development_UAT/FeatureServer"
)


class BusinessDirectorySourceConfig(SourceConfig):
    """Governed production-directory configuration."""

    source_item_id: str = Field(
        min_length=32,
        max_length=32,
    )
    prd_experience_item_id: str = Field(
        min_length=32,
        max_length=32,
    )

    license_name: str = Field(min_length=1)
    license_url: str = Field(min_length=1)
    required_attribution: str = Field(min_length=1)

    where_clause: str = Field(min_length=1)
    approved_operational_values: list[str] = Field(min_length=1)

    blocked_uat_item_id: str = Field(
        min_length=32,
        max_length=32,
    )
    blocked_uat_base_url: str = Field(min_length=1)


def load_business_directory_config(
    path: Path,
) -> BusinessDirectorySourceConfig:
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))

    if not isinstance(payload, dict):
        raise ValueError(f"Invalid source configuration: {path}")

    return BusinessDirectorySourceConfig.model_validate(payload)


class BramptonBusinessDirectoryConnector:
    """Approved Brampton production-directory collector."""

    def __init__(
        self,
        *,
        project_root: Path,
        config: BusinessDirectorySourceConfig,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self.project_root = project_root
        self.config = config
        self.transport = transport

    def _assert_governance(
        self,
    ) -> None:
        if not self.config.enabled:
            raise RuntimeError(f"Source {self.config.source_id} is disabled.")

        if self.config.access_state != "approved":
            raise RuntimeError(f"Source {self.config.source_id} is not approved for acquisition.")

        configured_url = self.config.base_url.rstrip("/")

        if (
            self.config.source_item_id != PRODUCTION_ITEM_ID
            or configured_url != PRODUCTION_BASE_URL
        ):
            raise RuntimeError(
                "Business-directory acquisition "
                "is restricted to the approved "
                "production feature service."
            )

        if self.config.prd_experience_item_id != PRD_EXPERIENCE_ITEM_ID:
            raise RuntimeError("Unexpected PRD experience item.")

        if (
            self.config.blocked_uat_item_id != BLOCKED_UAT_ITEM_ID
            or self.config.blocked_uat_base_url.rstrip("/") != BLOCKED_UAT_BASE_URL
        ):
            raise RuntimeError("UAT governance block is missing or inconsistent.")

        if (
            configured_url == BLOCKED_UAT_BASE_URL
            or self.config.source_item_id == BLOCKED_UAT_ITEM_ID
        ):
            raise RuntimeError("The UAT business directory is blocked from acquisition.")

    def _layer_id(
        self,
    ) -> int:
        if len(self.config.layers) != 1:
            raise RuntimeError("Business directory must configure exactly one approved layer.")

        return self.config.layers[0]

    def inspect_service(
        self,
    ) -> dict[str, Any]:
        self._assert_governance()

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
            "source_item_id": (self.config.source_item_id),
            "prd_experience_item_id": (self.config.prd_experience_item_id),
            "service_url": (self.config.base_url),
            "layer_id": layer_id,
            "layer_name": metadata.get("name"),
            "object_id_field": (infer_object_id_field(metadata)),
            "geometry_type": metadata.get("geometryType"),
            "field_names": [
                field.get("name")
                for field in metadata.get(
                    "fields",
                    [],
                )
                if isinstance(field, dict)
            ],
            "where_clause": (self.config.where_clause),
            "approved_operational_values": (self.config.approved_operational_values),
            "license_name": (self.config.license_name),
            "license_url": (self.config.license_url),
            "required_attribution": (self.config.required_attribution),
            "blocked_uat_item_id": (self.config.blocked_uat_item_id),
            "service_max_record_count": (
                service.get("maxRecordCount") or metadata.get("maxRecordCount")
            ),
            "supported_query_formats": (
                metadata.get("supportedQueryFormats") or service.get("supportedQueryFormats")
            ),
            "editing_info": metadata.get("editingInfo"),
        }

    def _validate_collection(
        self,
        collection: dict[str, Any],
    ) -> None:
        features = collection.get("features")

        if not isinstance(features, list):
            raise RuntimeError("Business directory has no valid feature list.")

        approved = {value.strip().casefold() for value in (self.config.approved_operational_values)}

        invalid_values: list[str] = []

        for feature in features:
            if not isinstance(feature, dict):
                raise RuntimeError("Business directory contains an invalid feature.")

            properties = feature.get("properties")

            if not isinstance(
                properties,
                dict,
            ):
                raise RuntimeError("Business-directory feature has no valid properties.")

            raw_operational = properties.get("OPERATIONAL")

            normalized = str(raw_operational or "").strip().casefold()

            if normalized not in approved:
                invalid_values.append(str(raw_operational))

        if invalid_values:
            raise RuntimeError(
                "Business-directory query returned "
                "records outside the approved "
                "operational scope: "
                f"{sorted(set(invalid_values))}"
            )

    def acquire(
        self,
        *,
        run_id: str,
        as_of_timestamp: datetime,
    ) -> dict[str, Any]:
        self._assert_governance()

        layer_id = self._layer_id()
        started_at = utc_now()

        manifest = SourceRunManifest(
            source_id=self.config.source_id,
            run_id=run_id,
            started_at=started_at,
            as_of_timestamp=(as_of_timestamp),
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
                as_of_timestamp=(as_of_timestamp),
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
                project_root=(self.project_root),
                manifest=manifest,
            )

            raise

        manifest_path = write_manifest(
            project_root=self.project_root,
            manifest=manifest,
        )

        snapshot_path = self.project_root / snapshot.raw_path

        return {
            "source_id": (self.config.source_id),
            "run_id": run_id,
            "status": manifest.status,
            "source_item_id": (self.config.source_item_id),
            "layer_id": layer_id,
            "record_count": (snapshot.record_count),
            "raw_path": snapshot.raw_path,
            "raw_sha256": snapshot.sha256,
            "schema_fingerprint": (snapshot.schema_fingerprint),
            "manifest_path": str(manifest_path.relative_to(self.project_root)),
            "bytes_written": (snapshot_path.stat().st_size + manifest_path.stat().st_size),
            "where_clause": (self.config.where_clause),
            "required_attribution": (self.config.required_attribution),
            "current_status_verified": False,
            "outreach_eligible": False,
        }
