from __future__ import annotations

from pathlib import Path
from typing import Any

from cre_foundry.connectors.arcgis import (
    ArcGISClient,
    infer_object_id_field,
)
from cre_foundry.connectors.plantrak import (
    load_source_config,
)
from cre_foundry.control import (
    ControlDatabase,
    utc_now,
)
from cre_foundry.raw_storage import (
    schema_fingerprint,
)


def execute_plantrak_metadata_watch(
    *,
    project_root: Path,
    lock_ttl_minutes: int = 15,
) -> dict[str, Any]:
    """Inspect Plantrak metadata and persist operational state."""
    config_path = project_root / "config" / "sources" / "brampton_plantrak.yaml"

    database = ControlDatabase(project_root / "data" / "control" / "operations.sqlite3")

    database.initialize()

    config = load_source_config(config_path)
    database.register_source(config)

    as_of = utc_now()

    with database.source_lock(
        config.source_id,
        ttl_minutes=lock_ttl_minutes,
    ):
        run_id = database.start_run(
            source_id=config.source_id,
            run_type="metadata_watch",
            as_of_timestamp=as_of,
        )

        try:
            with ArcGISClient(
                base_url=config.base_url,
                timeout_seconds=(config.request_timeout_seconds),
            ) as client:
                service = client.service_metadata()
                layers: list[dict[str, Any]] = []
                schema_changed = False

                for layer_id in config.layers:
                    metadata = client.layer_metadata(layer_id)

                    fingerprint = schema_fingerprint(metadata)

                    state = database.record_schema(
                        source_id=config.source_id,
                        layer_key=str(layer_id),
                        fingerprint=fingerprint,
                        metadata=metadata,
                        observed_at=as_of,
                    )

                    if state == "changed":
                        schema_changed = True

                    layers.append(
                        {
                            "layer_id": layer_id,
                            "name": metadata.get("name"),
                            "object_id_field": (infer_object_id_field(metadata)),
                            "field_count": len(
                                metadata.get(
                                    "fields",
                                    [],
                                )
                            ),
                            "schema_state": state,
                            "schema_fingerprint": (fingerprint),
                        }
                    )

            summary: dict[str, Any] = {
                "source_id": config.source_id,
                "access_state": config.access_state,
                "service_description": service.get("serviceDescription"),
                "max_record_count": service.get("maxRecordCount"),
                "supported_query_formats": service.get("supportedQueryFormats"),
                "layers": layers,
            }

            database.complete_run(
                run_id=run_id,
                records_observed=len(layers),
                schema_changed=schema_changed,
                metadata=summary,
            )

            cadence = database.update_health(
                source_id=config.source_id,
                success=True,
                changed=schema_changed,
                now=as_of,
            )

        except Exception as exc:
            database.fail_run(
                run_id=run_id,
                error=exc,
            )

            database.update_health(
                source_id=config.source_id,
                success=False,
                changed=False,
                error=exc,
                now=as_of,
            )

            raise

    summary["run_id"] = run_id
    summary["schema_changed"] = schema_changed
    summary["cadence_minutes"] = cadence.cadence_minutes
    summary["next_due_at"] = cadence.next_due_at.isoformat()

    return summary
