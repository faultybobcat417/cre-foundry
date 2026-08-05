from __future__ import annotations

import csv
import gzip
import hashlib
import io
import json
import os
import tempfile
import zipfile
from collections.abc import Iterable, Iterator
from pathlib import Path
from typing import Any

EXPECTED_POLICY: dict[str, Any] = {
    "operating_mode": "shadow",
    "authoritative_artifacts_read_only": True,
    "checksum_revalidation_required": True,
    "exact_schema_required": True,
    "exact_record_count_required": True,
    "double_run_reproducibility_required": True,
    "raw_value_export_enabled": False,
    "warehouse_write_enabled": False,
    "operations_database_write_enabled": False,
    "snapshot_registration_enabled": False,
    "automatic_parser_approval": False,
    "automatic_schema_approval": False,
    "model_training_enabled": False,
    "production_ranking_enabled": False,
    "outreach_enabled": False,
}


def _atomic_json(
    path: Path,
    payload: dict[str, Any],
) -> None:
    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    descriptor, temporary_name = tempfile.mkstemp(
        dir=path.parent,
        prefix=f".{path.name}.",
        suffix=".tmp",
        text=True,
    )

    temporary_path = Path(temporary_name)

    try:
        with os.fdopen(
            descriptor,
            "w",
            encoding="utf-8",
        ) as stream:
            json.dump(
                payload,
                stream,
                indent=2,
                sort_keys=True,
            )
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())

        temporary_path.replace(path)

    except Exception:
        temporary_path.unlink(missing_ok=True)
        raise


def _atomic_text(
    path: Path,
    content: str,
) -> None:
    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    descriptor, temporary_name = tempfile.mkstemp(
        dir=path.parent,
        prefix=f".{path.name}.",
        suffix=".tmp",
        text=True,
    )

    temporary_path = Path(temporary_name)

    try:
        with os.fdopen(
            descriptor,
            "w",
            encoding="utf-8",
        ) as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())

        temporary_path.replace(path)

    except Exception:
        temporary_path.unlink(missing_ok=True)
        raise


def _load_object(
    path: Path,
) -> dict[str, Any]:
    raw: object = json.loads(path.read_text(encoding="utf-8"))

    if not isinstance(raw, dict):
        raise RuntimeError(f"Expected JSON object: {path}")

    return {str(key): value for key, value in raw.items()}


def _stable_json(
    value: object,
) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        default=str,
    ).encode("utf-8")


def _stable_hash(
    value: object,
) -> str:
    return hashlib.sha256(_stable_json(value)).hexdigest()


def _sha256(
    path: Path,
) -> str:
    digest = hashlib.sha256()

    with path.open("rb") as stream:
        for chunk in iter(
            lambda: stream.read(1024 * 1024),
            b"",
        ):
            digest.update(chunk)

    return digest.hexdigest()


def _record_view(
    raw_record: object,
) -> dict[str, object]:
    if not isinstance(raw_record, dict):
        return {"__value": raw_record}

    raw_attributes = raw_record.get("attributes")

    if isinstance(raw_attributes, dict):
        record = {str(key): value for key, value in raw_attributes.items()}

        record["__geometry_present"] = raw_record.get("geometry") is not None

        return record

    raw_properties = raw_record.get("properties")

    if isinstance(raw_properties, dict):
        record = {str(key): value for key, value in raw_properties.items()}

        record["__geometry_present"] = raw_record.get("geometry") is not None

        return record

    return {str(key): value for key, value in raw_record.items()}


def _digest_records(
    records: Iterable[dict[str, object]],
) -> tuple[
    int,
    str,
    list[str],
]:
    digest = hashlib.sha256()
    field_names: set[str] = set()
    record_count = 0

    for record in records:
        field_names.update(record)

        row_hash = hashlib.sha256(_stable_json(record)).digest()

        digest.update(row_hash)
        record_count += 1

    return (
        record_count,
        digest.hexdigest(),
        sorted(field_names),
    )


def _json_records(
    path: Path,
    *,
    encoding: str,
    record_path: str,
) -> Iterator[dict[str, object]]:
    if record_path != "$.features":
        raise RuntimeError(f"Unsupported JSON record path: {record_path}")

    with gzip.open(
        path,
        mode="rt",
        encoding=encoding,
    ) as stream:
        payload: object = json.load(stream)

    if not isinstance(payload, dict):
        raise RuntimeError("Expected a top-level JSON object.")

    raw_features = payload.get("features")

    if not isinstance(raw_features, list):
        raise RuntimeError("Expected $.features to be a list.")

    for raw_feature in raw_features:
        yield _record_view(raw_feature)


def _csv_records(
    path: Path,
    *,
    archive_member: str,
    encoding: str,
    delimiter: str,
) -> tuple[
    Iterator[dict[str, object]],
    list[str],
]:
    archive = zipfile.ZipFile(
        path,
        mode="r",
    )

    try:
        binary_stream = archive.open(
            archive_member,
            mode="r",
        )

    except Exception:
        archive.close()
        raise

    text_stream = io.TextIOWrapper(
        binary_stream,
        encoding=encoding,
        newline="",
    )

    reader = csv.DictReader(
        text_stream,
        delimiter=delimiter,
    )

    raw_headers = reader.fieldnames

    if not raw_headers:
        text_stream.close()
        archive.close()

        raise RuntimeError("Delimited member lacks a header.")

    headers = [str(value) for value in raw_headers]

    if len(headers) != len(set(headers)):
        text_stream.close()
        archive.close()

        raise RuntimeError("Delimited member has duplicate headers.")

    def iterator() -> Iterator[dict[str, object]]:
        try:
            for row_number, row in enumerate(
                reader,
                start=2,
            ):
                if None in row:
                    raise RuntimeError(
                        f"Delimited row has more values than headers at line {row_number}."
                    )

                yield {
                    str(key): (None if value is None or value == "" else value)
                    for key, value in row.items()
                    if key is not None
                }

        finally:
            text_stream.close()
            archive.close()

    return (
        iterator(),
        headers,
    )


def _run_contract(
    project_root: Path,
    contract: dict[str, Any],
) -> dict[str, Any]:
    source_id = str(contract["source_id"])

    artifact_path = str(contract["artifact_path"])

    expected_sha256 = str(contract["artifact_sha256"])

    parser_type = str(contract["parser_type"])

    encoding = str(contract["encoding"])

    expected_record_count = int(contract["expected_record_count"])

    expected_schema_fingerprint = str(contract["expected_schema_fingerprint"])

    raw_expected_fields = contract["expected_fields"]

    if not isinstance(
        raw_expected_fields,
        list,
    ):
        raise RuntimeError("Expected fields must be a list.")

    expected_fields = [str(value) for value in raw_expected_fields]

    path = (project_root / artifact_path).resolve(strict=True)

    root = project_root.resolve()

    try:
        path.relative_to(root)

    except ValueError as error:
        raise RuntimeError("Artifact is outside the project boundary.") from error

    if path.is_symlink():
        raise RuntimeError("Artifact symlinks are not allowed.")

    actual_sha256 = _sha256(path)

    if actual_sha256 != expected_sha256:
        raise RuntimeError(f"Checksum mismatch for {source_id}.")

    if parser_type == "gzip_json_feature_collection":
        record_path = str(contract["record_path"])

        (
            record_count,
            dataset_digest,
            fields,
        ) = _digest_records(
            _json_records(
                path,
                encoding=encoding,
                record_path=record_path,
            )
        )

        schema_fingerprint = _stable_hash(fields)

    elif parser_type == "zip_csv_member":
        archive_member = str(contract["archive_member"])

        delimiter = str(contract["delimiter"])

        records, headers = _csv_records(
            path,
            archive_member=archive_member,
            encoding=encoding,
            delimiter=delimiter,
        )

        (
            record_count,
            dataset_digest,
            fields,
        ) = _digest_records(records)

        schema_fingerprint = _stable_hash(headers)

    else:
        raise RuntimeError(f"Unsupported parser type: {parser_type}")

    validation_errors = []

    if record_count != expected_record_count:
        validation_errors.append("record_count_mismatch")

    if fields != sorted(expected_fields):
        validation_errors.append("field_set_mismatch")

    if schema_fingerprint != expected_schema_fingerprint:
        validation_errors.append("schema_fingerprint_mismatch")

    return {
        "source_id": source_id,
        "artifact_path": artifact_path,
        "artifact_sha256": actual_sha256,
        "parser_type": parser_type,
        "record_count": record_count,
        "field_count": len(fields),
        "fields": fields,
        "schema_fingerprint": (schema_fingerprint),
        "dataset_digest": dataset_digest,
        "validation_errors": (validation_errors),
        "validation_complete": (not validation_errors),
        "raw_values_exported": False,
        "warehouse_write_performed": False,
        "operations_database_write_performed": False,
        "snapshot_registration_performed": False,
    }


def build_source_parser_contracts(
    project_root: Path,
    *,
    write_contracts: bool = True,
) -> dict[str, Any]:
    config = _load_object(project_root / "config" / "source_parser_contracts.json")

    raw_policy = config.get("policy")

    raw_contracts = config.get("contracts")

    if not isinstance(raw_policy, dict):
        raise RuntimeError("Parser policy must be an object.")

    policy = {str(key): value for key, value in raw_policy.items()}

    if policy != EXPECTED_POLICY:
        raise RuntimeError("Parser policy mismatch.")

    if not isinstance(
        raw_contracts,
        list,
    ):
        raise RuntimeError("Parser contracts must be a list.")

    validations: list[dict[str, Any]] = []

    approval_rows: list[dict[str, Any]] = []

    for raw_contract in raw_contracts:
        if not isinstance(
            raw_contract,
            dict,
        ):
            raise RuntimeError("Parser contract must be an object.")

        contract = {str(key): value for key, value in raw_contract.items()}

        first = _run_contract(
            project_root,
            contract,
        )

        second = _run_contract(
            project_root,
            contract,
        )

        compared_fields = (
            "record_count",
            "field_count",
            "fields",
            "schema_fingerprint",
            "dataset_digest",
            "validation_errors",
        )

        reproducibility_match = all(first[field] == second[field] for field in compared_fields)

        validation_complete = (
            bool(first["validation_complete"])
            and bool(second["validation_complete"])
            and reproducibility_match
        )

        validations.append(
            {
                "source_id": first["source_id"],
                "artifact_path": first["artifact_path"],
                "artifact_sha256": first["artifact_sha256"],
                "parser_type": first["parser_type"],
                "first_run": first,
                "second_run": second,
                "reproducibility_match": (reproducibility_match),
                "validation_complete": (validation_complete),
                "parser_contract_approved": False,
                "schema_contract_approved": False,
                "automatic_approval": False,
            }
        )

        approval_rows.append(
            {
                "source_id": first["source_id"],
                "artifact_sha256": first["artifact_sha256"],
                "parser_type": first["parser_type"],
                "record_count": first["record_count"],
                "schema_fingerprint": first["schema_fingerprint"],
                "dataset_digest": first["dataset_digest"],
                "candidate_record_keys": (
                    contract.get(
                        "candidate_record_keys",
                        [],
                    )
                ),
                "candidate_temporal_fields": (
                    contract.get(
                        "candidate_temporal_fields",
                        [],
                    )
                ),
                "approved_record_key": None,
                "approved_temporal_fields": [],
                "parser_contract_approved": False,
                "schema_contract_approved": False,
                "approved_by": None,
                "approved_at": None,
                "approval_evidence_reference": None,
                "registration_permitted": False,
            }
        )

    validations.sort(key=lambda item: str(item["source_id"]))

    approval_rows.sort(key=lambda item: str(item["source_id"]))

    report: dict[str, Any] = {
        "model_version": ("cre-foundry-source-parser-contract-validation-v1"),
        "contract_count": len(validations),
        "validation_complete_count": sum(bool(item["validation_complete"]) for item in validations),
        "reproducibility_match_count": sum(
            bool(item["reproducibility_match"]) for item in validations
        ),
        "parser_execution_count": (len(validations) * 2),
        "validations": validations,
        "parser_contract_approval_count": 0,
        "schema_contract_approval_count": 0,
        "raw_value_export_count": 0,
        "warehouse_write_count": 0,
        "operations_database_write_count": 0,
        "snapshot_registration_count": 0,
        "model_training_execution_count": 0,
        "production_ranking_execution_count": 0,
        "outreach_execution_count": 0,
        "policy": EXPECTED_POLICY,
    }

    approval_report: dict[str, Any] = {
        "model_version": ("cre-foundry-source-parser-approval-template-v1"),
        "approval_count": len(approval_rows),
        "approvals": approval_rows,
        "approved_parser_contract_count": 0,
        "approved_schema_contract_count": 0,
        "registration_permitted_count": 0,
        "automatic_approval": False,
        "production_ranking_enabled": False,
        "outreach_enabled": False,
    }

    if write_contracts:
        contract_root = project_root / "docs" / "data_contracts"

        _atomic_json(
            contract_root / "source_parser_contract_validation.json",
            report,
        )

        _atomic_json(
            contract_root / "source_parser_contract_approval_template.json",
            approval_report,
        )

        _atomic_text(
            contract_root / "source_parser_contracts.md",
            "\n".join(
                [
                    "# Source Parser Contracts",
                    "",
                    ("Each admitted source artifact is checksum-pinned and parsed twice."),
                    "",
                    (f"- Contracts: `{report['contract_count']}`"),
                    (f"- Validated: `{report['validation_complete_count']}`"),
                    (f"- Reproducible: `{report['reproducibility_match_count']}`"),
                    (f"- Parser executions: `{report['parser_execution_count']}`"),
                    "",
                    "- Parser approvals: `0`",
                    "- Schema approvals: `0`",
                    "- Database writes: `0`",
                    "- Snapshot registrations: `0`",
                    "",
                ]
            ),
        )

    return {
        "validation": report,
        "approval_template": (approval_report),
    }
