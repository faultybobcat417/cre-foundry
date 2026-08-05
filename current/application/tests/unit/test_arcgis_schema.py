from __future__ import annotations

from cre_foundry.connectors.arcgis import (
    infer_object_id_field,
)


def test_infers_object_id_from_field_schema() -> None:
    metadata = {
        "fields": [
            {
                "name": "APPLICATION",
                "type": "esriFieldTypeString",
            },
            {
                "name": "OBJECTID",
                "type": "esriFieldTypeOID",
            },
        ]
    }

    assert infer_object_id_field(metadata) == "OBJECTID"


def test_direct_object_id_metadata_has_priority() -> None:
    metadata = {
        "objectIdField": "FID",
        "fields": [
            {
                "name": "OBJECTID",
                "type": "esriFieldTypeOID",
            }
        ],
    }

    assert infer_object_id_field(metadata) == "FID"
