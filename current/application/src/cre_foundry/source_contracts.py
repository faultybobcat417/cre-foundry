from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class SourceConfig(BaseModel):
    """Configuration governing one external source."""

    model_config = ConfigDict(extra="forbid")

    source_id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    base_url: str = Field(min_length=1)
    access_state: Literal[
        "approved",
        "review",
        "blocked",
    ]
    enabled: bool
    request_timeout_seconds: float = Field(
        gt=0,
        le=300,
    )
    batch_size: int = Field(
        gt=0,
        le=1000,
    )
    output_spatial_reference: int
    layers: list[int]

    base_cadence_minutes: int = Field(
        default=360,
        ge=5,
    )
    minimum_cadence_minutes: int = Field(
        default=60,
        ge=5,
    )
    maximum_cadence_minutes: int = Field(
        default=1440,
        ge=5,
    )
    critical_source: bool = False


class SnapshotRecord(BaseModel):
    """Immutable metadata for one raw source snapshot."""

    model_config = ConfigDict(extra="forbid")

    source_id: str
    run_id: str
    layer_id: int
    collected_at: datetime
    as_of_timestamp: datetime
    raw_path: str
    sha256: str
    record_count: int = Field(ge=0)
    schema_fingerprint: str
    content_type: str


class SourceRunManifest(BaseModel):
    """File-based audit record for one acquisition run."""

    model_config = ConfigDict(extra="forbid")

    source_id: str
    run_id: str
    started_at: datetime
    completed_at: datetime | None = None
    as_of_timestamp: datetime
    status: Literal[
        "running",
        "succeeded",
        "failed",
    ]
    service_url: str
    layer_snapshots: list[SnapshotRecord] = Field(default_factory=list)
    error_type: str | None = None
    error_message: str | None = None


class BulkFileSourceConfig(BaseModel):
    """Configuration for one licensed bulk-file source."""

    model_config = ConfigDict(extra="forbid")

    source_id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    source_kind: Literal["bulk_zip"]
    access_state: Literal[
        "approved",
        "review",
        "blocked",
    ]
    enabled: bool

    landing_page_url: str = Field(min_length=1)
    download_url: str = Field(min_length=1)

    license_name: str = Field(min_length=1)
    license_url: str = Field(min_length=1)
    required_attribution: str = Field(min_length=1)

    vintage_start: date
    vintage_end: date
    release_date: date

    request_timeout_seconds: float = Field(
        gt=0,
        le=600,
    )
    max_download_bytes: int = Field(
        gt=0,
    )
    max_uncompressed_bytes: int = Field(
        default=5368709120,
        gt=0,
    )
    max_member_count: int = Field(
        default=1000,
        gt=0,
        le=100000,
    )

    base_cadence_minutes: int = Field(
        ge=60,
    )
    minimum_cadence_minutes: int = Field(
        ge=60,
    )
    maximum_cadence_minutes: int = Field(
        ge=60,
    )
    critical_source: bool = False
