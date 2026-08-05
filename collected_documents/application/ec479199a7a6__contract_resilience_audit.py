from __future__ import annotations

import copy
import hashlib
import json
import math
import os
import random
import re
import tempfile
import tomllib
import unicodedata
import uuid
from collections.abc import Callable
from pathlib import Path
from typing import Any
from urllib.parse import quote

EXPECTED_POLICY: dict[str, Any] = {
    "operating_mode": "shadow",
    "deterministic_fuzzing_required": True,
    "strict_json_parsing_required": True,
    "serialization_round_trip_required": True,
    "duplicate_key_rejection_required": True,
    "non_finite_number_rejection_required": True,
    "atomic_write_recovery_required": True,
    "configuration_versioning_required": True,
    "future_version_rejection_required": True,
    "deterministic_migration_rehearsal_required": True,
    "software_inventory_required": True,
    "audit_evidence_index_required": True,
    "steelman_audit_plan_required": True,
    "compliance_claim_permitted": False,
    "approval_invention_forbidden": True,
    "client_value_invention_forbidden": True,
    "network_access_enabled": False,
    "database_access_enabled": False,
    "database_write_enabled": False,
    "snapshot_registration_enabled": False,
    "automatic_acquisition_enabled": False,
    "persistent_outcome_ledger_enabled": False,
    "outcome_event_insertion_enabled": False,
    "point_in_time_materialization_enabled": False,
    "model_training_enabled": False,
    "backtest_execution_enabled": False,
    "pilot_execution_enabled": False,
    "production_ranking_enabled": False,
    "outreach_enabled": False,
}


SOURCE_FIELDS = {
    "source_id",
    "evidence_bundle_digest",
    "parser_contract_approved",
    "schema_contract_approved",
    "approved_record_key",
    "approved_temporal_fields",
    "capture_policy_approved",
    "change_contract_approved",
    "registration_approved",
    "reviewer_id",
    "reviewed_at",
    "evidence_reference",
}


CLIENT_FIELDS = {
    "input_id",
    "authoritative_value",
    "confirmed",
    "confirmed_by",
    "confirmed_at",
    "evidence_reference",
}


VERSION_FIELDS = (
    "config_version",
    "decision_bundle_version",
    "model_version",
)


class StrictJSONError(ValueError):
    """Raised when strict JSON invariants are violated."""


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
                allow_nan=False,
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


def _duplicate_rejecting_hook(
    pairs: list[tuple[str, Any]],
) -> dict[str, Any]:
    result: dict[str, Any] = {}

    for key, value in pairs:
        if key in result:
            raise StrictJSONError(f"Duplicate JSON key: {key}")

        result[key] = value

    return result


def _reject_constant(
    value: str,
) -> None:
    raise StrictJSONError(f"Non-finite JSON number: {value}")


def _strict_json_loads(
    text: str,
) -> Any:
    return json.loads(
        text,
        object_pairs_hook=(_duplicate_rejecting_hook),
        parse_constant=_reject_constant,
    )


def _load_object(
    path: Path,
) -> dict[str, Any]:
    raw = _strict_json_loads(path.read_text(encoding="utf-8"))

    if not isinstance(
        raw,
        dict,
    ):
        raise StrictJSONError(f"Expected JSON object: {path}")

    return {str(key): value for key, value in raw.items()}


def _canonical_bytes(
    value: object,
) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def _stable_digest(
    value: object,
) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _file_digest(
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


def _string_list(
    value: object,
    *,
    label: str,
) -> list[str]:
    if not isinstance(
        value,
        list,
    ):
        raise StrictJSONError(f"{label} must be a list.")

    result: list[str] = []

    for index, raw_value in enumerate(value):
        if not isinstance(
            raw_value,
            str,
        ):
            raise StrictJSONError(f"{label}[{index}] must be a string.")

        result.append(raw_value)

    return result


def _require_exact_fields(
    value: dict[str, Any],
    expected: set[str],
    *,
    label: str,
) -> None:
    actual = set(value)

    if actual != expected:
        raise StrictJSONError(
            f"{label} fields mismatch. Expected={sorted(expected)}, actual={sorted(actual)}"
        )


def _nullable_string(
    value: object,
    *,
    label: str,
) -> None:
    if value is not None and not isinstance(
        value,
        str,
    ):
        raise StrictJSONError(f"{label} must be string or null.")


def _validate_governance_bundle(
    bundle: object,
) -> dict[str, Any]:
    if not isinstance(
        bundle,
        dict,
    ):
        raise StrictJSONError("Governance bundle must be an object.")

    normalized = {str(key): value for key, value in bundle.items()}

    _require_exact_fields(
        normalized,
        {
            "decision_bundle_version",
            "source_decisions",
            "client_inputs",
        },
        label="governance bundle",
    )

    if normalized["decision_bundle_version"] != "cre-foundry-governance-decisions-v1":
        raise StrictJSONError("Unsupported decision bundle version.")

    raw_source_rows = normalized["source_decisions"]

    raw_client_rows = normalized["client_inputs"]

    if not isinstance(
        raw_source_rows,
        list,
    ):
        raise StrictJSONError("source_decisions must be a list.")

    if not isinstance(
        raw_client_rows,
        list,
    ):
        raise StrictJSONError("client_inputs must be a list.")

    source_ids: set[str] = set()

    for index, raw_row in enumerate(raw_source_rows):
        if not isinstance(
            raw_row,
            dict,
        ):
            raise StrictJSONError(f"source_decisions[{index}] must be an object.")

        row = {str(key): value for key, value in raw_row.items()}

        _require_exact_fields(
            row,
            SOURCE_FIELDS,
            label=(f"source_decisions[{index}]"),
        )

        source_id = row["source_id"]

        if (
            not isinstance(
                source_id,
                str,
            )
            or not source_id.strip()
        ):
            raise StrictJSONError("source_id must be non-empty.")

        if source_id in source_ids:
            raise StrictJSONError(f"Duplicate source_id: {source_id}")

        source_ids.add(source_id)

        digest = row["evidence_bundle_digest"]

        if (
            not isinstance(
                digest,
                str,
            )
            or re.fullmatch(
                r"[0-9a-f]{64}",
                digest,
            )
            is None
        ):
            raise StrictJSONError("Evidence digest must be 64 lowercase hex characters.")

        for field in (
            "parser_contract_approved",
            "schema_contract_approved",
            "capture_policy_approved",
            "change_contract_approved",
            "registration_approved",
        ):
            if type(row[field]) is not bool:
                raise StrictJSONError(f"{field} must be boolean.")

        approved_record_key = row["approved_record_key"]

        if approved_record_key is not None and not isinstance(
            approved_record_key,
            str,
        ):
            raise StrictJSONError("approved_record_key must be string or null.")

        _string_list(
            row["approved_temporal_fields"],
            label="approved_temporal_fields",
        )

        for field in (
            "reviewer_id",
            "reviewed_at",
            "evidence_reference",
        ):
            _nullable_string(
                row[field],
                label=field,
            )

    client_ids: set[str] = set()

    for index, raw_row in enumerate(raw_client_rows):
        if not isinstance(
            raw_row,
            dict,
        ):
            raise StrictJSONError(f"client_inputs[{index}] must be an object.")

        row = {str(key): value for key, value in raw_row.items()}

        _require_exact_fields(
            row,
            CLIENT_FIELDS,
            label=(f"client_inputs[{index}]"),
        )

        input_id = row["input_id"]

        if (
            not isinstance(
                input_id,
                str,
            )
            or not input_id.strip()
        ):
            raise StrictJSONError("input_id must be non-empty.")

        if input_id in client_ids:
            raise StrictJSONError(f"Duplicate input_id: {input_id}")

        client_ids.add(input_id)

        authoritative_value = row["authoritative_value"]

        if authoritative_value is not None and not isinstance(
            authoritative_value,
            dict,
        ):
            raise StrictJSONError("authoritative_value must be object or null.")

        if type(row["confirmed"]) is not bool:
            raise StrictJSONError("confirmed must be boolean.")

        for field in (
            "confirmed_by",
            "confirmed_at",
            "evidence_reference",
        ):
            _nullable_string(
                row[field],
                label=field,
            )

    return normalized


def _mutate_invalid_bundle(
    baseline: dict[str, Any],
    mutation_index: int,
) -> dict[str, Any]:
    mutated = copy.deepcopy(baseline)

    source_rows = mutated["source_decisions"]

    client_rows = mutated["client_inputs"]

    mutation_type = mutation_index % 16

    if mutation_type == 0:
        del mutated["decision_bundle_version"]

    elif mutation_type == 1:
        mutated["unexpected"] = True

    elif mutation_type == 2:
        mutated["decision_bundle_version"] = "cre-foundry-governance-decisions-v999"

    elif mutation_type == 3:
        mutated["source_decisions"] = {}

    elif mutation_type == 4:
        source_rows.append(copy.deepcopy(source_rows[0]))

    elif mutation_type == 5:
        source_rows[0]["source_id"] = 42

    elif mutation_type == 6:
        source_rows[0]["evidence_bundle_digest"] = "not-a-digest"

    elif mutation_type == 7:
        source_rows[0]["parser_contract_approved"] = "true"

    elif mutation_type == 8:
        source_rows[0]["approved_record_key"] = 123

    elif mutation_type == 9:
        source_rows[0]["approved_temporal_fields"] = "INDATE"

    elif mutation_type == 10:
        mutated["client_inputs"] = {}

    elif mutation_type == 11:
        client_rows.append(copy.deepcopy(client_rows[0]))

    elif mutation_type == 12:
        client_rows[0]["confirmed"] = "yes"

    elif mutation_type == 13:
        client_rows[0]["authoritative_value"] = "invented"

    elif mutation_type == 14:
        client_rows[0]["confirmed_by"] = ["person"]

    else:
        client_rows[0]["evidence_reference"] = {"bad": True}

    return mutated


def _shuffle_mappings(
    value: Any,
    rng: random.Random,
) -> Any:
    if isinstance(
        value,
        dict,
    ):
        items = list(value.items())

        rng.shuffle(items)

        return {
            key: _shuffle_mappings(
                item_value,
                rng,
            )
            for key, item_value in items
        }

    if isinstance(
        value,
        list,
    ):
        return [
            _shuffle_mappings(
                item,
                rng,
            )
            for item in value
        ]

    return value


def _build_fuzz_report(
    baseline: dict[str, Any],
    *,
    seed: int,
    case_count: int,
) -> dict[str, Any]:
    _validate_governance_bundle(baseline)

    rejected = 0
    escaped: list[int] = []

    for case_index in range(case_count):
        mutated = _mutate_invalid_bundle(
            baseline,
            case_index,
        )

        try:
            _validate_governance_bundle(mutated)

        except StrictJSONError:
            rejected += 1

        else:
            escaped.append(case_index)

    rng = random.Random(seed)

    permutation_case_count = min(
        512,
        case_count,
    )

    baseline_digest = _stable_digest(baseline)

    stable_permutation_count = 0

    for _ in range(permutation_case_count):
        permuted = _shuffle_mappings(
            baseline,
            rng,
        )

        _validate_governance_bundle(permuted)

        if _stable_digest(permuted) == baseline_digest:
            stable_permutation_count += 1

    return {
        "model_version": ("cre-foundry-contract-fuzz-report-v1"),
        "seed": seed,
        "baseline_valid": True,
        "baseline_digest": (baseline_digest),
        "malformed_case_count": (case_count),
        "rejected_malformed_case_count": (rejected),
        "escaped_malformed_case_count": len(escaped),
        "escaped_case_indices": escaped,
        "permutation_case_count": (permutation_case_count),
        "stable_permutation_digest_count": (stable_permutation_count),
        "all_properties_passed": bool(
            rejected == case_count
            and not escaped
            and stable_permutation_count == permutation_case_count
        ),
    }


def _random_text(
    rng: random.Random,
) -> str:
    fragments = (
        "alpha",
        "CRE",
        "Brampton",
        "é",
        "東京",
        "مرحبا",
        "🧿",
        "\n",
        "\t",
        "\\",
        '"',
        "\u0000",
    )

    result = "".join(
        rng.choice(fragments)
        for _ in range(
            rng.randint(
                0,
                5,
            )
        )
    )

    return unicodedata.normalize(
        "NFC",
        result,
    )


def _generate_json_value(
    rng: random.Random,
    *,
    depth: int,
    maximum_depth: int,
) -> Any:
    if depth >= maximum_depth:
        scalar_type = rng.randrange(6)

        if scalar_type == 0:
            return None

        if scalar_type == 1:
            return bool(rng.randrange(2))

        if scalar_type == 2:
            return rng.randint(
                -(2**53),
                2**53,
            )

        if scalar_type == 3:
            return round(
                rng.uniform(
                    -1_000_000,
                    1_000_000,
                ),
                8,
            )

        if scalar_type == 4:
            return _random_text(rng)

        return ""

    value_type = rng.randrange(8)

    if value_type < 5:
        return _generate_json_value(
            rng,
            depth=maximum_depth,
            maximum_depth=maximum_depth,
        )

    if value_type == 5:
        return [
            _generate_json_value(
                rng,
                depth=depth + 1,
                maximum_depth=maximum_depth,
            )
            for _ in range(
                rng.randint(
                    0,
                    5,
                )
            )
        ]

    result: dict[str, Any] = {}

    for index in range(
        rng.randint(
            0,
            5,
        )
    ):
        key = f"{index}:{_random_text(rng)}"

        result[key] = _generate_json_value(
            rng,
            depth=depth + 1,
            maximum_depth=maximum_depth,
        )

    return result


def _build_serialization_report(
    *,
    seed: int,
    case_count: int,
    maximum_depth: int,
) -> dict[str, Any]:
    rng = random.Random(seed)

    successful_round_trips = 0
    stable_digest_count = 0

    for _ in range(case_count):
        value = _generate_json_value(
            rng,
            depth=0,
            maximum_depth=maximum_depth,
        )

        encoded = _canonical_bytes(value)

        decoded = _strict_json_loads(encoded.decode("utf-8"))

        reencoded = _canonical_bytes(decoded)

        if encoded == reencoded:
            successful_round_trips += 1

        shuffled = _shuffle_mappings(
            value,
            rng,
        )

        if _stable_digest(value) == _stable_digest(shuffled):
            stable_digest_count += 1

    negative_cases: list[tuple[str, Callable[[], Any]]] = [
        (
            "duplicate_key",
            lambda: _strict_json_loads('{"a":1,"a":2}'),
        ),
        (
            "nan",
            lambda: _canonical_bytes(math.nan),
        ),
        (
            "positive_infinity",
            lambda: _canonical_bytes(math.inf),
        ),
        (
            "negative_infinity",
            lambda: _canonical_bytes(-math.inf),
        ),
        (
            "invalid_utf8",
            lambda: _strict_json_loads(b"\xff".decode("utf-8")),
        ),
    ]

    rejected_negative_cases: list[str] = []

    for case_id, operation in negative_cases:
        try:
            operation()

        except (
            StrictJSONError,
            ValueError,
            UnicodeDecodeError,
        ):
            rejected_negative_cases.append(case_id)

    return {
        "model_version": ("cre-foundry-serialization-roundtrip-v1"),
        "seed": seed,
        "case_count": case_count,
        "maximum_depth": maximum_depth,
        "successful_round_trip_count": (successful_round_trips),
        "stable_digest_count": (stable_digest_count),
        "negative_case_count": len(negative_cases),
        "rejected_negative_case_count": len(rejected_negative_cases),
        "rejected_negative_cases": sorted(rejected_negative_cases),
        "all_properties_passed": bool(
            successful_round_trips == case_count
            and stable_digest_count == case_count
            and len(rejected_negative_cases) == len(negative_cases)
        ),
    }


def _safe_target(
    root: Path,
    candidate: Path,
) -> Path:
    root_resolved = root.resolve()
    candidate_resolved = candidate.resolve(strict=False)

    try:
        candidate_resolved.relative_to(root_resolved)

    except ValueError as error:
        raise RuntimeError("Atomic target escapes rehearsal root.") from error

    return candidate_resolved


def _write_and_fsync(
    path: Path,
    content: str,
) -> None:
    with path.open(
        "w",
        encoding="utf-8",
    ) as stream:
        stream.write(content)
        stream.flush()
        os.fsync(stream.fileno())


def _build_atomic_recovery_report() -> dict[str, Any]:
    scenario_rows: list[dict[str, Any]] = []

    with tempfile.TemporaryDirectory(
        prefix=("cre-foundry-atomic-recovery-")
    ) as temporary_directory:
        root = Path(temporary_directory)

        target = root / "state.json"

        _atomic_json(
            target,
            {"version": 1},
        )

        baseline_digest = _file_digest(target)

        _atomic_json(
            target,
            {"version": 2},
        )

        scenario_rows.append(
            {
                "scenario_id": "normal_commit",
                "passed": bool(_load_object(target)["version"] == 2),
            }
        )

        _atomic_json(
            target,
            {"version": 1},
        )

        before_crash_digest = _file_digest(target)

        crash_temp = root / ".state.crash-before.tmp"

        _write_and_fsync(
            crash_temp,
            '{"version":2}\n',
        )

        scenario_rows.append(
            {
                "scenario_id": ("crash_before_replace"),
                "passed": bool(
                    _file_digest(target) == before_crash_digest and crash_temp.is_file()
                ),
            }
        )

        crash_temp.unlink()

        corrupt_temp = root / ".state.corrupt.tmp"

        _write_and_fsync(
            corrupt_temp,
            '{"version":',
        )

        original_still_valid = bool(_load_object(target)["version"] == 1)

        corrupt_rejected = False

        try:
            _load_object(corrupt_temp)

        except (
            StrictJSONError,
            json.JSONDecodeError,
        ):
            corrupt_rejected = True

        scenario_rows.append(
            {
                "scenario_id": ("corrupt_temporary_file"),
                "passed": bool(original_still_valid and corrupt_rejected),
            }
        )

        corrupt_temp.unlink()

        replace_temp = root / ".state.replace.tmp"

        _write_and_fsync(
            replace_temp,
            '{"version":3}\n',
        )

        replace_temp.replace(target)

        scenario_rows.append(
            {
                "scenario_id": ("replace_after_fsync"),
                "passed": bool(_load_object(target)["version"] == 3 and not replace_temp.exists()),
            }
        )

        outside = root.parent / (f"{root.name}-outside.json")

        outside.write_text(
            '{"outside":true}\n',
            encoding="utf-8",
        )

        symlink_path = root / "escape.json"

        symlink_path.symlink_to(outside)

        symlink_rejected = False

        try:
            _safe_target(
                root,
                symlink_path,
            )

        except RuntimeError:
            symlink_rejected = True

        scenario_rows.append(
            {
                "scenario_id": ("symlink_escape_rejected"),
                "passed": (symlink_rejected),
            }
        )

        symlink_path.unlink()
        outside.unlink()

        orphan_one = root / ".state.1.tmp"

        orphan_two = root / ".state.2.tmp"

        unrelated = root / "keep.txt"

        orphan_one.write_text(
            "one",
            encoding="utf-8",
        )

        orphan_two.write_text(
            "two",
            encoding="utf-8",
        )

        unrelated.write_text(
            "keep",
            encoding="utf-8",
        )

        removed_count = 0

        for orphan in root.glob(".state.*.tmp"):
            orphan.unlink()
            removed_count += 1

        scenario_rows.append(
            {
                "scenario_id": ("scoped_orphan_cleanup"),
                "passed": bool(
                    removed_count == 2
                    and unrelated.is_file()
                    and not list(root.glob(".state.*.tmp"))
                ),
            }
        )

        unrelated.unlink()

        final_digest = _file_digest(target)

        root_entries = sorted(path.name for path in root.iterdir())

    return {
        "model_version": ("cre-foundry-atomic-write-recovery-v1"),
        "scenario_count": len(scenario_rows),
        "passed_scenario_count": sum(bool(row["passed"]) for row in scenario_rows),
        "failed_scenario_count": sum(not bool(row["passed"]) for row in scenario_rows),
        "scenarios": scenario_rows,
        "initial_digest": (baseline_digest),
        "final_digest": (final_digest),
        "final_rehearsal_entries": (root_entries),
        "temporary_rehearsal_deleted": True,
        "project_file_mutation_count": 0,
    }


def _version_field(
    document: dict[str, Any],
) -> tuple[
    str | None,
    str | None,
    bool,
]:
    present = [field for field in VERSION_FIELDS if field in document]

    if len(present) != 1:
        return (
            None,
            None,
            len(present) > 1,
        )

    field = present[0]
    value = document[field]

    if not isinstance(
        value,
        str,
    ):
        return (
            field,
            None,
            False,
        )

    return (
        field,
        value,
        False,
    )


def _require_known_version(
    document: dict[str, Any],
    allowed_versions: set[str],
) -> str:
    field, version, ambiguous = _version_field(document)

    if ambiguous:
        raise RuntimeError("Multiple version fields are present.")

    if field is None or version is None:
        raise RuntimeError("Version field is missing or invalid.")

    if version not in allowed_versions:
        raise RuntimeError(f"Unsupported version: {version}")

    return version


def _migrate_rehearsal_v0(
    document: dict[str, Any],
) -> dict[str, Any]:
    _require_known_version(
        document,
        {"cre-foundry-contract-resilience-audit-v0"},
    )

    fuzz_cases = document.get("fuzz_cases")

    serialization_cases = document.get("serialization_cases")

    seed = document.get("seed")

    if not isinstance(
        fuzz_cases,
        int,
    ):
        raise RuntimeError("v0 fuzz_cases must be integer.")

    if not isinstance(
        serialization_cases,
        int,
    ):
        raise RuntimeError("v0 serialization_cases must be integer.")

    if not isinstance(
        seed,
        int,
    ):
        raise RuntimeError("v0 seed must be integer.")

    return {
        "config_version": ("cre-foundry-contract-resilience-audit-v1"),
        "seed": seed,
        "decision_fuzz_case_count": (fuzz_cases),
        "serialization_case_count": (serialization_cases),
        "migration_source_version": ("cre-foundry-contract-resilience-audit-v0"),
    }


def _build_compatibility_report(
    project_root: Path,
) -> dict[str, Any]:
    config_paths = sorted((project_root / "config").glob("*.json"))

    rows: list[dict[str, Any]] = []

    for path in config_paths:
        document = _load_object(path)

        field, version, ambiguous = _version_field(document)

        rows.append(
            {
                "path": str(path.relative_to(project_root)),
                "version_field": field,
                "version": version,
                "version_field_ambiguous": (ambiguous),
                "versioned": bool(field is not None and version is not None and not ambiguous),
                "sha256": _file_digest(path),
            }
        )

    future_version_rejected = False

    try:
        _require_known_version(
            {"config_version": ("cre-foundry-contract-resilience-audit-v999")},
            {"cre-foundry-contract-resilience-audit-v1"},
        )

    except RuntimeError:
        future_version_rejected = True

    missing_version_rejected = False

    try:
        _require_known_version(
            {"seed": 1},
            {"cre-foundry-contract-resilience-audit-v1"},
        )

    except RuntimeError:
        missing_version_rejected = True

    v0_document = {
        "config_version": ("cre-foundry-contract-resilience-audit-v0"),
        "seed": 123,
        "fuzz_cases": 64,
        "serialization_cases": 128,
    }

    first_migration = _migrate_rehearsal_v0(v0_document)

    second_migration = _migrate_rehearsal_v0(copy.deepcopy(v0_document))

    return {
        "model_version": ("cre-foundry-configuration-compatibility-v1"),
        "config_document_count": len(rows),
        "versioned_document_count": sum(bool(row["versioned"]) for row in rows),
        "unversioned_document_count": sum(not bool(row["versioned"]) for row in rows),
        "ambiguous_version_field_count": sum(bool(row["version_field_ambiguous"]) for row in rows),
        "documents": rows,
        "future_version_rejected": (future_version_rejected),
        "missing_version_rejected": (missing_version_rejected),
        "migration_rehearsal_count": 2,
        "migration_reproducible": bool(first_migration == second_migration),
        "migration_output": (first_migration),
        "configuration_mutation_count": 0,
    }


def _project_metadata(
    project_root: Path,
) -> tuple[str, str]:
    raw = tomllib.loads((project_root / "pyproject.toml").read_text(encoding="utf-8"))

    project = raw.get("project", {})

    if not isinstance(
        project,
        dict,
    ):
        return (
            "cre-foundry",
            "0.0.0",
        )

    name = project.get(
        "name",
        "cre-foundry",
    )

    version = project.get(
        "version",
        "0.0.0",
    )

    return (
        str(name),
        str(version),
    )


def _build_sbom(
    project_root: Path,
) -> dict[str, Any]:
    lock_path = project_root / "uv.lock"

    lock_digest = _file_digest(lock_path)

    raw = tomllib.loads(lock_path.read_text(encoding="utf-8"))

    raw_packages = raw.get(
        "package",
        [],
    )

    if not isinstance(
        raw_packages,
        list,
    ):
        raise RuntimeError("uv.lock package inventory is invalid.")

    components: list[dict[str, Any]] = []

    seen: set[tuple[str, str]] = set()

    for raw_package in raw_packages:
        if not isinstance(
            raw_package,
            dict,
        ):
            continue

        name_value = raw_package.get("name")

        version_value = raw_package.get("version")

        if not isinstance(
            name_value,
            str,
        ) or not isinstance(
            version_value,
            str,
        ):
            continue

        normalized_name = name_value.lower().replace(
            "_",
            "-",
        )

        identity = (
            normalized_name,
            version_value,
        )

        if identity in seen:
            continue

        seen.add(identity)

        components.append(
            {
                "type": "library",
                "name": normalized_name,
                "version": version_value,
                "purl": (f"pkg:pypi/{quote(normalized_name)}@{quote(version_value)}"),
                "properties": [{"name": ("cre-foundry:inventory-source"), "value": "uv.lock"}],
            }
        )

    components.sort(
        key=lambda row: (
            str(row["name"]),
            str(row["version"]),
        )
    )

    project_name, project_version = _project_metadata(project_root)

    serial = uuid.uuid5(
        uuid.NAMESPACE_URL,
        (f"cre-foundry:{lock_digest}"),
    )

    return {
        "bomFormat": "CycloneDX",
        "specVersion": "1.7",
        "serialNumber": (f"urn:uuid:{serial}"),
        "version": 1,
        "metadata": {
            "component": {
                "type": "application",
                "name": project_name,
                "version": project_version,
                "purl": (f"pkg:pypi/{quote(project_name)}@{quote(project_version)}"),
            },
            "properties": [
                {"name": ("cre-foundry:lockfile-sha256"), "value": lock_digest},
                {
                    "name": ("cre-foundry:schema-validation"),
                    "value": ("pending-independent-cyclonedx-validator"),
                },
            ],
        },
        "components": components,
    }


def _audit_controls() -> list[dict[str, Any]]:
    return [
        {
            "control_id": "GOV-01",
            "pillar": "authenticity",
            "description": ("Human approvals are attributable and evidence-referenced."),
            "evidence": [("docs/data_contracts/manual_decision_validation.json")],
        },
        {
            "control_id": "GOV-02",
            "pillar": "authenticity",
            "description": ("Approval evidence is bound to cryptographic digests."),
            "evidence": [("docs/data_contracts/assurance_drift_report.json")],
        },
        {
            "control_id": "GOV-03",
            "pillar": "authenticity",
            "description": ("Client values cannot be invented or auto-confirmed."),
            "evidence": [("docs/data_contracts/manual_activation_envelope_summary.json")],
        },
        {
            "control_id": "GOV-04",
            "pillar": "authenticity",
            "description": ("Protected execution gates default closed."),
            "evidence": [("docs/data_contracts/activation_state_model_summary.json")],
        },
        {
            "control_id": "REL-01",
            "pillar": "reliability",
            "description": (
                "Static analysis, typing and tests run through a single verification entrypoint."
            ),
            "evidence": ["scripts/verify.sh"],
        },
        {
            "control_id": "REL-02",
            "pillar": "reliability",
            "description": ("Parser results are deterministic across repeated executions."),
            "evidence": [("docs/data_contracts/source_parser_contract_validation.json")],
        },
        {
            "control_id": "REL-03",
            "pillar": "reliability",
            "description": ("Assurance outputs reproduce over identical inputs."),
            "evidence": [("docs/data_contracts/assurance_reproducibility_report.json")],
        },
        {
            "control_id": "REL-04",
            "pillar": "reliability",
            "description": ("Activation rules are exhaustively model-checked."),
            "evidence": [("docs/data_contracts/activation_model_check_report.json")],
        },
        {
            "control_id": "ROB-01",
            "pillar": "robustness",
            "description": ("Malformed governance documents fail closed."),
            "evidence": [("docs/security/contract_fuzz_report.json")],
        },
        {
            "control_id": "ROB-02",
            "pillar": "robustness",
            "description": ("Serialization is canonical and rejects ambiguous JSON."),
            "evidence": [("docs/security/serialization_roundtrip_report.json")],
        },
        {
            "control_id": "ROB-03",
            "pillar": "robustness",
            "description": ("Atomic-write failure modes are rehearsed."),
            "evidence": [("docs/security/atomic_write_recovery_report.json")],
        },
        {
            "control_id": "ROB-04",
            "pillar": "robustness",
            "description": ("Critical gate mutations produce counterexamples."),
            "evidence": [("docs/data_contracts/activation_mutation_report.json")],
        },
        {
            "control_id": "LON-01",
            "pillar": "longevity",
            "description": ("Configuration files carry explicit versions."),
            "evidence": [("docs/security/configuration_compatibility_matrix.json")],
        },
        {
            "control_id": "LON-02",
            "pillar": "longevity",
            "description": ("Unknown future versions fail closed."),
            "evidence": [("docs/security/configuration_compatibility_matrix.json")],
        },
        {
            "control_id": "LON-03",
            "pillar": "longevity",
            "description": ("Migration behavior is deterministic."),
            "evidence": [("docs/security/configuration_compatibility_matrix.json")],
        },
        {
            "control_id": "LON-04",
            "pillar": "longevity",
            "description": (
                "Backup restoration, retention and schema deprecation drills are required."
            ),
            "evidence": [],
        },
        {
            "control_id": "SEC-01",
            "pillar": "security",
            "description": ("Dependency inventory is generated from the locked environment."),
            "evidence": [("docs/security/software_bill_of_materials.cdx.json")],
        },
        {
            "control_id": "SEC-02",
            "pillar": "security",
            "description": (
                "Dependency vulnerability scanning must block unresolved critical findings."
            ),
            "evidence": [],
        },
        {
            "control_id": "SEC-03",
            "pillar": "security",
            "description": ("Secret scanning must cover history and incoming changes."),
            "evidence": [],
        },
        {
            "control_id": "SEC-04",
            "pillar": "security",
            "description": (
                "Static security analysis must cover application-specific dangerous sinks."
            ),
            "evidence": [],
        },
        {
            "control_id": "SUP-01",
            "pillar": "supply_chain",
            "description": ("Build dependencies are locked."),
            "evidence": ["uv.lock"],
        },
        {
            "control_id": "SUP-02",
            "pillar": "supply_chain",
            "description": ("Release provenance must be generated and independently verifiable."),
            "evidence": [],
        },
        {
            "control_id": "SUP-03",
            "pillar": "supply_chain",
            "description": ("Release artifacts must be signed and checksum-pinned."),
            "evidence": [],
        },
        {
            "control_id": "SUP-04",
            "pillar": "supply_chain",
            "description": (
                "Repository security posture must be evaluated with an independent scanner."
            ),
            "evidence": [],
        },
        {
            "control_id": "OPS-01",
            "pillar": "operations",
            "description": ("Monitoring and rollback evidence must precede production governance."),
            "evidence": [("docs/data_contracts/activation_state_machine.json")],
        },
        {
            "control_id": "OPS-02",
            "pillar": "operations",
            "description": ("Incident response roles, severity and escalation must be documented."),
            "evidence": [],
        },
        {
            "control_id": "OPS-03",
            "pillar": "operations",
            "description": ("Recovery objectives and restoration tests must be measured."),
            "evidence": [],
        },
        {
            "control_id": "OPS-04",
            "pillar": "operations",
            "description": (
                "Production changes require independent review and auditable authorization."
            ),
            "evidence": [("docs/data_contracts/governance_decision_schema.json")],
        },
    ]


def _build_control_catalog(
    project_root: Path,
    standards: list[dict[str, Any]],
) -> dict[str, Any]:
    control_rows: list[dict[str, Any]] = []

    for control in _audit_controls():
        evidence = _string_list(
            control["evidence"],
            label=(f"{control['control_id']}.evidence"),
        )

        present = [
            relative_path for relative_path in evidence if (project_root / relative_path).is_file()
        ]

        if not evidence:
            status = "planned_gap"

        elif len(present) == len(evidence):
            status = "implemented_evidence_present"

        else:
            status = "partial_evidence"

        control_rows.append(
            {
                **control,
                "evidence_present": (present),
                "evidence_missing": sorted(set(evidence) - set(present)),
                "status": status,
                "independent_verification_complete": False,
            }
        )

    status_counts: dict[str, int] = {}

    for row in control_rows:
        status = str(row["status"])

        status_counts[status] = (
            status_counts.get(
                status,
                0,
            )
            + 1
        )

    return {
        "model_version": ("cre-foundry-audit-control-catalog-v1"),
        "standards": standards,
        "control_count": len(control_rows),
        "status_counts": (status_counts),
        "controls": control_rows,
        "compliance_claimed": False,
        "certification_claimed": False,
        "independent_audit_complete": False,
        "scope_note": (
            "This catalogue records engineering "
            "evidence and gaps. It does not establish "
            "formal compliance or certification."
        ),
    }


def _build_evidence_index(
    project_root: Path,
    evidence_paths: list[str],
) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []

    for relative_path in evidence_paths:
        path = project_root / relative_path

        rows.append(
            {
                "path": relative_path,
                "exists": path.is_file(),
                "size_bytes": (path.stat().st_size if path.is_file() else None),
                "sha256": (_file_digest(path) if path.is_file() else None),
            }
        )

    return {
        "model_version": ("cre-foundry-audit-evidence-index-v1"),
        "evidence_item_count": len(rows),
        "present_evidence_item_count": sum(bool(row["exists"]) for row in rows),
        "missing_evidence_item_count": sum(not bool(row["exists"]) for row in rows),
        "items": rows,
        "index_digest": _stable_digest(rows),
        "evidence_mutation_count": 0,
    }


def _steelman_plan() -> dict[str, Any]:
    phases = [
        {
            "phase_id": "scope_and_trust_boundaries",
            "objective": (
                "Identify assets, actors, entry points, privileged paths and irreversible actions."
            ),
        },
        {
            "phase_id": "evidence_preservation",
            "objective": (
                "Freeze commit, configuration, dependency, artifact and runtime evidence."
            ),
        },
        {
            "phase_id": "threat_model_and_abuse_cases",
            "objective": (
                "Steelman the strongest plausible attacker, "
                "insider, operator-error and data-poisoning cases."
            ),
        },
        {
            "phase_id": "code_and_contract_review",
            "objective": (
                "Review parsers, validators, authorization "
                "boundaries, serialization and dangerous sinks."
            ),
        },
        {
            "phase_id": "supply_chain_review",
            "objective": (
                "Validate dependencies, SBOM, provenance, signatures and build isolation."
            ),
        },
        {
            "phase_id": "data_and_model_governance",
            "objective": (
                "Validate point-in-time correctness, lineage, "
                "consent, exclusions, labels and leakage controls."
            ),
        },
        {
            "phase_id": "resilience_and_recovery",
            "objective": (
                "Exercise atomicity, backups, restoration, "
                "rollback, degraded modes and disaster recovery."
            ),
        },
        {
            "phase_id": "adversarial_validation",
            "objective": (
                "Perform fuzzing, mutation, chaos, negative testing and privilege-boundary attacks."
            ),
        },
        {
            "phase_id": "independent_reproduction",
            "objective": (
                "Require a reviewer uninvolved in construction to reproduce critical evidence."
            ),
        },
        {
            "phase_id": "remediation_and_release_decision",
            "objective": (
                "Verify fixes, document accepted residual risk and issue a signed release decision."
            ),
        },
    ]

    steelman_questions = [
        ("What is the strongest evidence that the claimed property is actually true?"),
        ("What observation would falsify the claim?"),
        ("Can the evidence be reproduced from a clean environment by an independent reviewer?"),
        ("Could stale, reordered, duplicated or partially written input bypass the control?"),
        ("Could a valid but malicious input exhaust memory, disk, CPU or operator attention?"),
        ("Could an insider approve their own evidence or rewrite the audit trail?"),
        ("Could future data leak into historical decisions?"),
        ("Could a protected account or exclusion be lost during joins, retries or migrations?"),
        ("Could a dependency, build runner or release artifact be substituted?"),
        (
            "Can the system recover after abrupt termination "
            "without ambiguous or duplicated effects?"
        ),
        ("What happens after six months of schema drift, dependency churn and staff turnover?"),
        ("What residual risk remains even after every automated check passes?"),
    ]

    return {
        "model_version": ("cre-foundry-steelman-audit-plan-v1"),
        "phase_count": len(phases),
        "phases": phases,
        "steelman_question_count": len(steelman_questions),
        "steelman_questions": (steelman_questions),
        "required_pillars": [
            "reliability",
            "authenticity",
            "longevity",
            "robustness",
            "security",
            "supply_chain",
            "privacy",
            "data_governance",
            "operability",
            "recoverability",
            "independent_reproducibility",
        ],
        "release_decision_values": ["approved", "conditionally_approved", "rejected"],
        "default_release_decision": ("rejected"),
        "independent_review_required": True,
        "positive_evidence_required": True,
        "negative_testing_required": True,
        "residual_risk_acceptance_required": True,
        "audit_complete": False,
    }


def build_contract_resilience_audit(
    project_root: Path,
    *,
    write_contracts: bool = True,
) -> dict[str, Any]:
    config = _load_object(project_root / "config" / "contract_resilience_audit.json")

    raw_policy = config.get("policy")

    if not isinstance(
        raw_policy,
        dict,
    ):
        raise RuntimeError("Resilience policy must be an object.")

    policy = {str(key): value for key, value in raw_policy.items()}

    if policy != EXPECTED_POLICY:
        raise RuntimeError("Resilience policy mismatch.")

    seed = int(config["seed"])

    fuzz_case_count = int(config["decision_fuzz_case_count"])

    serialization_case_count = int(config["serialization_case_count"])

    maximum_depth = int(config["max_generated_depth"])

    raw_standards = config.get("standards_baseline")

    if not isinstance(
        raw_standards,
        list,
    ):
        raise RuntimeError("Standards baseline must be a list.")

    standards: list[dict[str, Any]] = []

    for raw_standard in raw_standards:
        if not isinstance(
            raw_standard,
            dict,
        ):
            raise RuntimeError("Standard entry must be an object.")

        standards.append({str(key): value for key, value in raw_standard.items()})

    evidence_paths = _string_list(
        config.get("evidence_paths"),
        label="evidence_paths",
    )

    decisions = _load_object(project_root / "config" / "governance_decisions.json")

    decisions_before = _file_digest(project_root / "config" / "governance_decisions.json")

    fuzz = _build_fuzz_report(
        decisions,
        seed=seed,
        case_count=(fuzz_case_count),
    )

    serialization = _build_serialization_report(
        seed=seed + 1,
        case_count=(serialization_case_count),
        maximum_depth=(maximum_depth),
    )

    atomic_recovery = _build_atomic_recovery_report()

    compatibility = _build_compatibility_report(project_root)

    sbom = _build_sbom(project_root)

    controls = _build_control_catalog(
        project_root,
        standards,
    )

    evidence_index = _build_evidence_index(
        project_root,
        evidence_paths,
    )

    steelman = _steelman_plan()

    decisions_after = _file_digest(project_root / "config" / "governance_decisions.json")

    summary: dict[str, Any] = {
        "model_version": ("cre-foundry-contract-resilience-audit-v1"),
        "fuzz_case_count": (fuzz["malformed_case_count"]),
        "rejected_fuzz_case_count": (fuzz["rejected_malformed_case_count"]),
        "escaped_fuzz_case_count": (fuzz["escaped_malformed_case_count"]),
        "serialization_case_count": (serialization["case_count"]),
        "successful_serialization_case_count": (serialization["successful_round_trip_count"]),
        "serialization_negative_case_count": (serialization["negative_case_count"]),
        "rejected_serialization_negative_case_count": (
            serialization["rejected_negative_case_count"]
        ),
        "atomic_recovery_scenario_count": (atomic_recovery["scenario_count"]),
        "passed_atomic_recovery_scenario_count": (atomic_recovery["passed_scenario_count"]),
        "configuration_document_count": (compatibility["config_document_count"]),
        "unversioned_configuration_count": (compatibility["unversioned_document_count"]),
        "ambiguous_configuration_version_count": (compatibility["ambiguous_version_field_count"]),
        "future_version_rejected": (compatibility["future_version_rejected"]),
        "migration_reproducible": (compatibility["migration_reproducible"]),
        "sbom_component_count": len(sbom["components"]),
        "audit_control_count": (controls["control_count"]),
        "audit_evidence_item_count": (evidence_index["evidence_item_count"]),
        "missing_audit_evidence_item_count": (evidence_index["missing_evidence_item_count"]),
        "steelman_audit_phase_count": (steelman["phase_count"]),
        "steelman_question_count": (steelman["steelman_question_count"]),
        "governance_decision_digest_unchanged": bool(decisions_before == decisions_after),
        "all_resilience_properties_passed": bool(
            fuzz["all_properties_passed"]
            and serialization["all_properties_passed"]
            and atomic_recovery["failed_scenario_count"] == 0
            and compatibility["unversioned_document_count"] == 0
            and compatibility["ambiguous_version_field_count"] == 0
            and compatibility["future_version_rejected"]
            and compatibility["missing_version_rejected"]
            and compatibility["migration_reproducible"]
            and evidence_index["missing_evidence_item_count"] == 0
            and decisions_before == decisions_after
        ),
        "compliance_claimed": False,
        "certification_claimed": False,
        "independent_audit_complete": False,
        "automatic_approval_count": 0,
        "client_value_invention_count": 0,
        "network_access_count": 0,
        "database_access_count": 0,
        "database_write_count": 0,
        "snapshot_registration_count": 0,
        "automatic_acquisition_count": 0,
        "persistent_outcome_database_creation_count": 0,
        "outcome_event_insertion_count": 0,
        "point_in_time_dataset_execution_count": 0,
        "model_training_execution_count": 0,
        "backtest_execution_count": 0,
        "pilot_execution_count": 0,
        "production_ranking_execution_count": 0,
        "outreach_execution_count": 0,
        "policy": EXPECTED_POLICY,
    }

    if write_contracts:
        security_root = project_root / "docs" / "security"

        _atomic_json(
            security_root / "contract_fuzz_report.json",
            fuzz,
        )

        _atomic_json(
            security_root / "serialization_roundtrip_report.json",
            serialization,
        )

        _atomic_json(
            security_root / "atomic_write_recovery_report.json",
            atomic_recovery,
        )

        _atomic_json(
            security_root / "configuration_compatibility_matrix.json",
            compatibility,
        )

        _atomic_json(
            security_root / "software_bill_of_materials.cdx.json",
            sbom,
        )

        _atomic_json(
            security_root / "audit_control_catalog.json",
            controls,
        )

        _atomic_json(
            security_root / "audit_evidence_index.json",
            evidence_index,
        )

        _atomic_json(
            security_root / "steelman_audit_plan.json",
            steelman,
        )

        _atomic_json(
            security_root / "contract_resilience_audit_summary.json",
            summary,
        )

        _atomic_text(
            security_root / "contract_resilience_audit.md",
            "\n".join(
                [
                    "# Contract Resilience and Audit Spine",
                    "",
                    (
                        "This layer tests contract robustness "
                        "and prepares evidence for a later "
                        "independent steelman audit."
                    ),
                    "",
                    (f"- Malformed fuzz cases: `{summary['fuzz_case_count']}`"),
                    (f"- Rejected malformed cases: `{summary['rejected_fuzz_case_count']}`"),
                    (f"- Serialization cases: `{summary['serialization_case_count']}`"),
                    (f"- Atomic recovery scenarios: `{summary['atomic_recovery_scenario_count']}`"),
                    (f"- Versioned configurations: `{summary['configuration_document_count']}`"),
                    (f"- SBOM components: `{summary['sbom_component_count']}`"),
                    (f"- Audit controls: `{summary['audit_control_count']}`"),
                    (f"- Indexed evidence items: `{summary['audit_evidence_item_count']}`"),
                    (f"- Steelman audit phases: `{summary['steelman_audit_phase_count']}`"),
                    "",
                    (
                        "- All resilience properties passed: "
                        f"`{str(summary['all_resilience_properties_passed']).lower()}`"
                    ),
                    "- Compliance claimed: `false`",
                    "- Certification claimed: `false`",
                    "- Independent audit complete: `false`",
                    "",
                    "- Network accesses: `0`",
                    "- Database accesses: `0`",
                    "- Database writes: `0`",
                    "- Snapshot registrations: `0`",
                    "- Model training executions: `0`",
                    "- Pilot executions: `0`",
                    "- Production rankings: `0`",
                    "- Outreach executions: `0`",
                    "",
                ]
            ),
        )

        _atomic_text(
            security_root / "SECURE_DEVELOPMENT_BASELINE.md",
            "\n".join(
                [
                    "# Secure Development Baseline",
                    "",
                    "## Current normative baseline",
                    "",
                    ("- NIST SSDF 1.1 is the current final secure-development baseline."),
                    ("- NIST SSDF 1.2 is tracked as draft guidance only."),
                    "",
                    "## Future verification baselines",
                    "",
                    "- OWASP ASVS 5.0.0 for the application layer.",
                    "- SLSA 1.2 for build and release provenance.",
                    "- CycloneDX 1.7 for software inventory.",
                    "- OpenSSF Scorecard for repository posture.",
                    "",
                    "## Mandatory engineering properties",
                    "",
                    "- Fail closed on unknown or stale inputs.",
                    "- Require attributable human authorization.",
                    "- Preserve immutable raw evidence and lineage.",
                    "- Use deterministic and reproducible transformations.",
                    "- Reject ambiguous serialization.",
                    "- Use atomic writes and rehearse recovery.",
                    "- Lock and inventory dependencies.",
                    "- Separate readiness from execution authorization.",
                    "- Preserve protected-account and exclusion integrity.",
                    "- Prohibit future-information leakage.",
                    "- Collect real outcomes with censoring.",
                    "- Require independent verification before production.",
                    "",
                    "## Claims boundary",
                    "",
                    (
                        "This repository records engineering "
                        "evidence. It does not currently claim "
                        "formal compliance, certification, "
                        "production readiness or proven ROI."
                    ),
                    "",
                ]
            ),
        )

        _atomic_text(
            security_root / "STEELMAN_AUDIT_CHARTER.md",
            "\n".join(
                [
                    "# Steelman Audit Charter",
                    "",
                    (
                        "The final audit must challenge the "
                        "strongest defensible version of every "
                        "system claim, not merely confirm that "
                        "documents and tests exist."
                    ),
                    "",
                    "## Audit rules",
                    "",
                    (
                        "1. Preserve the exact commit, configuration, "
                        "dependencies and artifacts under review."
                    ),
                    (
                        "2. Require positive evidence and an explicit "
                        "falsification test for every major claim."
                    ),
                    ("3. Reproduce critical evidence from a clean environment."),
                    ("4. Separate builder testimony from independent reviewer conclusions."),
                    (
                        "5. Test stale, malformed, duplicated, reordered, "
                        "partial and adversarial inputs."
                    ),
                    (
                        "6. Examine insider misuse, operator error, "
                        "dependency compromise and data poisoning."
                    ),
                    (
                        "7. Validate reliability, authenticity, longevity, "
                        "robustness, security and recoverability."
                    ),
                    (
                        "8. Record all gaps, accepted residual risks, "
                        "owners and remediation deadlines."
                    ),
                    ("9. Re-test every remediation before closure."),
                    (
                        "10. Default the release decision to rejected "
                        "until every mandatory gate is proven."
                    ),
                    "",
                    "## Final outputs",
                    "",
                    "- Signed audit scope and evidence manifest.",
                    "- Threat model and abuse-case catalogue.",
                    "- Control-by-control evidence assessment.",
                    "- Vulnerability and reliability findings.",
                    "- Recovery and rollback test results.",
                    "- Supply-chain and provenance assessment.",
                    "- Data-governance and leakage assessment.",
                    "- Residual-risk register.",
                    "- Remediation verification report.",
                    "- Signed release decision.",
                    "",
                ]
            ),
        )

    return {
        "summary": summary,
        "fuzz": fuzz,
        "serialization": serialization,
        "atomic_recovery": (atomic_recovery),
        "compatibility": compatibility,
        "sbom": sbom,
        "controls": controls,
        "evidence_index": (evidence_index),
        "steelman": steelman,
    }
