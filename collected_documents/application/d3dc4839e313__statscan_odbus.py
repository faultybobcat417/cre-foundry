from __future__ import annotations

import hashlib
import os
import shutil
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx
import yaml

from cre_foundry.bulk_storage import (
    validate_zip_archive,
    write_json_atomic,
)
from cre_foundry.source_contracts import (
    BulkFileSourceConfig,
)


def load_odbus_config(
    path: Path,
) -> BulkFileSourceConfig:
    payload = yaml.safe_load(path.read_text())

    if not isinstance(payload, dict):
        raise ValueError(f"Invalid ODBus configuration: {path}")

    return BulkFileSourceConfig.model_validate(payload)


class ODBusConnector:
    """Licensed Statistics Canada ODBus bulk source."""

    def __init__(
        self,
        *,
        project_root: Path,
        config: BulkFileSourceConfig,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self.project_root = project_root
        self.config = config
        self.transport = transport

    def _assert_access_approved(self) -> None:
        if not self.config.enabled:
            raise RuntimeError(f"Source {self.config.source_id} is disabled.")

        if self.config.access_state != "approved":
            raise RuntimeError(f"Source {self.config.source_id} is not approved.")

    def _client(self) -> httpx.Client:
        return httpx.Client(
            timeout=httpx.Timeout(self.config.request_timeout_seconds),
            follow_redirects=True,
            transport=self.transport,
            headers={"User-Agent": ("CRE-Foundry/0.1 (licensed Statistics Canada data)")},
        )

    def preflight(self) -> dict[str, Any]:
        """Inspect the archive without downloading its body."""
        self._assert_access_approved()

        with self._client() as client:
            response = client.head(self.config.download_url)

            if response.status_code in {
                403,
                405,
                501,
            }:
                with client.stream(
                    "GET",
                    self.config.download_url,
                    headers={"Range": "bytes=0-0"},
                ) as streamed_response:
                    streamed_response.raise_for_status()

                    return self._build_preflight(streamed_response)

            response.raise_for_status()

            return self._build_preflight(response)

    def _build_preflight(
        self,
        response: httpx.Response,
    ) -> dict[str, Any]:
        raw_length = response.headers.get("content-length")

        content_length = (
            int(raw_length) if raw_length is not None and raw_length.isdigit() else None
        )

        disk = shutil.disk_usage(self.project_root)

        if content_length is not None and content_length > self.config.max_download_bytes:
            raise RuntimeError("Remote archive exceeds configured maximum download size.")

        required_free_bytes = (
            content_length * 3 if content_length is not None else self.config.max_download_bytes
        )

        return {
            "source_id": self.config.source_id,
            "access_state": self.config.access_state,
            "landing_page_url": (self.config.landing_page_url),
            "download_url": self.config.download_url,
            "resolved_download_url": str(response.url),
            "status_code": response.status_code,
            "content_type": response.headers.get("content-type"),
            "content_length_bytes": content_length,
            "content_length_mib": (
                round(
                    content_length / (1024 * 1024),
                    2,
                )
                if content_length is not None
                else None
            ),
            "etag": response.headers.get("etag"),
            "last_modified": response.headers.get("last-modified"),
            "accept_ranges": response.headers.get("accept-ranges"),
            "max_download_bytes": (self.config.max_download_bytes),
            "disk_free_bytes": disk.free,
            "disk_free_gib": round(
                disk.free / (1024**3),
                2,
            ),
            "disk_safe_for_download": (disk.free >= required_free_bytes),
            "license_name": (self.config.license_name),
            "license_url": (self.config.license_url),
            "required_attribution": (self.config.required_attribution),
            "vintage_start": (self.config.vintage_start.isoformat()),
            "vintage_end": (self.config.vintage_end.isoformat()),
            "release_date": (self.config.release_date.isoformat()),
            "intended_use": (
                "Historical entity-resolution baseline; not current operating-status evidence."
            ),
        }

    def acquire(
        self,
        *,
        run_id: str,
        as_of_timestamp: datetime,
    ) -> dict[str, Any]:
        """Download, hash and validate one immutable archive."""
        self._assert_access_approved()

        preflight = self.preflight()

        if not preflight["disk_safe_for_download"]:
            raise RuntimeError("Disk safety check failed.")

        observed = as_of_timestamp.astimezone(UTC)

        relative_run_directory = (
            Path("data")
            / "bronze"
            / self.config.source_id
            / f"{observed.year:04d}"
            / f"{observed.month:02d}"
            / f"{observed.day:02d}"
            / run_id
        )

        run_directory = self.project_root / relative_run_directory

        run_directory.mkdir(
            parents=True,
            exist_ok=False,
        )

        temporary_path = run_directory / ".ODBus_2023.zip.part"

        digest = hashlib.sha256()
        downloaded_bytes = 0
        response_headers: dict[str, str] = {}

        try:
            with (
                self._client() as client,
                client.stream(
                    "GET",
                    self.config.download_url,
                ) as response,
            ):
                response.raise_for_status()

                response_headers = {key.lower(): value for key, value in response.headers.items()}

                raw_expected = response.headers.get("content-length")

                expected_bytes = (
                    int(raw_expected)
                    if raw_expected is not None and raw_expected.isdigit()
                    else None
                )

                with temporary_path.open("xb") as handle:
                    for chunk in response.iter_bytes(1024 * 1024):
                        if not chunk:
                            continue

                        downloaded_bytes += len(chunk)

                        if downloaded_bytes > self.config.max_download_bytes:
                            raise RuntimeError("Download exceeded the configured size limit.")

                        handle.write(chunk)
                        digest.update(chunk)

                    handle.flush()
                    os.fsync(handle.fileno())

                if expected_bytes is not None and downloaded_bytes != expected_bytes:
                    raise RuntimeError("Downloaded byte count does not match Content-Length.")

            validation = validate_zip_archive(
                temporary_path,
                max_member_count=(self.config.max_member_count),
                max_uncompressed_bytes=(self.config.max_uncompressed_bytes),
            )

            archive_sha256 = digest.hexdigest()

            archive_name = f"ODBus_2023_{archive_sha256[:16]}.zip"

            final_archive_path = run_directory / archive_name

            os.replace(
                temporary_path,
                final_archive_path,
            )

            relative_archive_path = final_archive_path.relative_to(self.project_root)

            manifest = {
                "source_id": self.config.source_id,
                "run_id": run_id,
                "collected_at": (datetime.now(UTC).isoformat()),
                "as_of_timestamp": (observed.isoformat()),
                "archive_path": str(relative_archive_path),
                "archive_sha256": (archive_sha256),
                "archive_bytes": (downloaded_bytes),
                "response_headers": (response_headers),
                "member_count": validation["member_count"],
                "total_compressed_bytes": (validation["total_compressed_bytes"]),
                "total_uncompressed_bytes": (validation["total_uncompressed_bytes"]),
                "members": validation["members"],
                "license_name": (self.config.license_name),
                "license_url": (self.config.license_url),
                "required_attribution": (self.config.required_attribution),
                "vintage_start": (self.config.vintage_start.isoformat()),
                "vintage_end": (self.config.vintage_end.isoformat()),
                "release_date": (self.config.release_date.isoformat()),
                "intended_use": ("Historical entity-resolution baseline only."),
            }

            manifest_path = run_directory / "manifest.json"

            write_json_atomic(
                manifest_path,
                manifest,
            )

            manifest["manifest_path"] = str(manifest_path.relative_to(self.project_root))

            return manifest

        except Exception:
            temporary_path.unlink(missing_ok=True)
            raise
