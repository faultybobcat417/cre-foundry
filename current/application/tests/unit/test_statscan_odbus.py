from __future__ import annotations

from pathlib import Path

import httpx
import pytest

from cre_foundry.connectors.statscan_odbus import (
    ODBusConnector,
)
from cre_foundry.source_contracts import (
    BulkFileSourceConfig,
)


def config(
    *,
    access_state: str = "approved",
) -> BulkFileSourceConfig:
    return BulkFileSourceConfig.model_validate(
        {
            "source_id": "statscan_odbus_2023",
            "name": "ODBus",
            "source_kind": "bulk_zip",
            "access_state": access_state,
            "enabled": True,
            "landing_page_url": ("https://example.test/landing"),
            "download_url": ("https://example.test/ODBus.zip"),
            "license_name": "Open Licence",
            "license_url": ("https://example.test/licence"),
            "required_attribution": ("Statistics Canada"),
            "vintage_start": "2022-05-01",
            "vintage_end": "2022-12-31",
            "release_date": "2023-11-28",
            "request_timeout_seconds": 30,
            "max_download_bytes": 1000000,
            "base_cadence_minutes": 525600,
            "minimum_cadence_minutes": 43200,
            "maximum_cadence_minutes": 525600,
            "critical_source": False,
        }
    )


def test_preflight_reads_headers_without_body(
    tmp_path: Path,
) -> None:
    def handler(
        request: httpx.Request,
    ) -> httpx.Response:
        assert request.method == "HEAD"

        return httpx.Response(
            200,
            headers={
                "content-type": "application/zip",
                "content-length": "1000",
                "etag": '"abc123"',
            },
            request=request,
        )

    connector = ODBusConnector(
        project_root=tmp_path,
        config=config(),
        transport=httpx.MockTransport(handler),
    )

    result = connector.preflight()

    assert result["content_length_bytes"] == 1000
    assert result["content_type"] == "application/zip"
    assert result["disk_safe_for_download"] is True


def test_preflight_rejects_oversized_archive(
    tmp_path: Path,
) -> None:
    def handler(
        request: httpx.Request,
    ) -> httpx.Response:
        return httpx.Response(
            200,
            headers={
                "content-length": "2000000",
            },
            request=request,
        )

    connector = ODBusConnector(
        project_root=tmp_path,
        config=config(),
        transport=httpx.MockTransport(handler),
    )

    with pytest.raises(
        RuntimeError,
        match="exceeds configured",
    ):
        connector.preflight()


def test_preflight_requires_approved_access(
    tmp_path: Path,
) -> None:
    connector = ODBusConnector(
        project_root=tmp_path,
        config=config(access_state="review"),
    )

    with pytest.raises(
        RuntimeError,
        match="not approved",
    ):
        connector.preflight()


def test_acquire_writes_hashed_archive_and_manifest(
    tmp_path: Path,
) -> None:
    import io
    import json
    import zipfile
    from datetime import UTC, datetime

    archive_buffer = io.BytesIO()

    with zipfile.ZipFile(
        archive_buffer,
        mode="w",
        compression=zipfile.ZIP_DEFLATED,
    ) as archive:
        archive.writestr(
            "data/businesses.csv",
            "name,city\nExample,Brampton\n",
        )

    archive_bytes = archive_buffer.getvalue()

    def handler(
        request: httpx.Request,
    ) -> httpx.Response:
        if request.method == "HEAD":
            return httpx.Response(
                200,
                headers={
                    "content-type": "application/zip",
                    "content-length": str(len(archive_bytes)),
                },
                request=request,
            )

        return httpx.Response(
            200,
            headers={
                "content-type": "application/zip",
                "content-length": str(len(archive_bytes)),
            },
            content=archive_bytes,
            request=request,
        )

    connector = ODBusConnector(
        project_root=tmp_path,
        config=config(),
        transport=httpx.MockTransport(handler),
    )

    result = connector.acquire(
        run_id="RUN-TEST",
        as_of_timestamp=datetime(
            2026,
            7,
            26,
            tzinfo=UTC,
        ),
    )

    archive_path = tmp_path / result["archive_path"]

    manifest_path = tmp_path / result["manifest_path"]

    assert archive_path.exists()
    assert manifest_path.exists()
    assert len(result["archive_sha256"]) == 64
    assert result["member_count"] == 1
    assert not list(archive_path.parent.glob("*.part"))

    manifest = json.loads(manifest_path.read_text())

    assert manifest["archive_sha256"] == result["archive_sha256"]


def test_zip_validation_rejects_path_traversal(
    tmp_path: Path,
) -> None:
    import zipfile

    from cre_foundry.bulk_storage import (
        UnsafeArchiveError,
        validate_zip_archive,
    )

    archive_path = tmp_path / "unsafe.zip"

    with zipfile.ZipFile(
        archive_path,
        mode="w",
    ) as archive:
        archive.writestr(
            "../escape.csv",
            "unsafe",
        )

    with pytest.raises(
        UnsafeArchiveError,
        match="Unsafe ZIP member path",
    ):
        validate_zip_archive(
            archive_path,
            max_member_count=100,
            max_uncompressed_bytes=1000000,
        )
