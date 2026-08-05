from __future__ import annotations

import hashlib
import json
import os
import stat
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any


class UnsafeArchiveError(RuntimeError):
    """Raised when an archive violates extraction-safety rules."""


def sha256_file(
    path: Path,
    *,
    chunk_size: int = 1024 * 1024,
) -> str:
    digest = hashlib.sha256()

    with path.open("rb") as handle:
        while chunk := handle.read(chunk_size):
            digest.update(chunk)

    return digest.hexdigest()


def write_json_atomic(
    path: Path,
    payload: dict[str, Any],
) -> None:
    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    temporary = path.with_name(f".{path.name}.tmp.{os.getpid()}")

    with temporary.open(
        "w",
        encoding="utf-8",
    ) as handle:
        json.dump(
            payload,
            handle,
            indent=2,
            sort_keys=True,
        )
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())

    os.replace(
        temporary,
        path,
    )


def validate_zip_archive(
    path: Path,
    *,
    max_member_count: int,
    max_uncompressed_bytes: int,
) -> dict[str, Any]:
    """Validate ZIP integrity without extracting any files."""
    members: list[dict[str, Any]] = []
    total_compressed = 0
    total_uncompressed = 0

    try:
        archive = zipfile.ZipFile(
            path,
            mode="r",
        )
    except zipfile.BadZipFile as exc:
        raise UnsafeArchiveError("Downloaded file is not a valid ZIP archive.") from exc

    with archive:
        entries = archive.infolist()

        if len(entries) > max_member_count:
            raise UnsafeArchiveError("ZIP archive exceeds the configured member-count limit.")

        for entry in entries:
            original_name = entry.filename
            normalized_name = original_name.replace(
                "\\",
                "/",
            )

            if "\x00" in normalized_name:
                raise UnsafeArchiveError("ZIP member contains a null byte.")

            member_path = PurePosixPath(normalized_name)

            first_part = member_path.parts[0] if member_path.parts else ""

            unsafe_path = (
                member_path.is_absolute()
                or normalized_name.startswith("/")
                or normalized_name.startswith("\\")
                or ".." in member_path.parts
                or first_part.endswith(":")
            )

            if unsafe_path:
                raise UnsafeArchiveError(f"Unsafe ZIP member path: {original_name}")

            unix_mode = (entry.external_attr >> 16) & 0xFFFF

            if stat.S_ISLNK(unix_mode):
                raise UnsafeArchiveError(f"ZIP symbolic links are not permitted: {original_name}")

            if entry.flag_bits & 0x1:
                raise UnsafeArchiveError(
                    f"Encrypted ZIP members are not permitted: {original_name}"
                )

            total_compressed += entry.compress_size
            total_uncompressed += entry.file_size

            if total_uncompressed > max_uncompressed_bytes:
                raise UnsafeArchiveError(
                    "ZIP archive exceeds the configured uncompressed-size limit."
                )

            members.append(
                {
                    "name": original_name,
                    "is_directory": entry.is_dir(),
                    "compressed_bytes": (entry.compress_size),
                    "uncompressed_bytes": (entry.file_size),
                    "crc32": f"{entry.CRC:08x}",
                    "compression_type": (entry.compress_type),
                }
            )

        corrupt_member = archive.testzip()

        if corrupt_member is not None:
            raise UnsafeArchiveError(f"ZIP CRC validation failed for: {corrupt_member}")

    return {
        "member_count": len(members),
        "total_compressed_bytes": (total_compressed),
        "total_uncompressed_bytes": (total_uncompressed),
        "members": members,
    }
