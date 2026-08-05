from __future__ import annotations

import json
import os
import re
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final

MAX_IDENTIFIER_SEGMENT_LENGTH: Final = 128
MAX_QUALIFIED_IDENTIFIER_SEGMENTS: Final = 3
DETERMINISTIC_CASE_COUNT: Final = 4096

_IDENTIFIER_PATTERN: Final = re.compile(
    r"^[A-Za-z_][A-Za-z0-9_]{0,127}$",
    flags=re.ASCII,
)


class SQLIdentifierError(ValueError):
    """Raised when a value violates the identifier contract."""


def _validated_segment(
    raw: object,
) -> str:
    if not isinstance(
        raw,
        str,
    ):
        raise SQLIdentifierError("Identifier segment must be a string.")

    if not raw:
        raise SQLIdentifierError("Identifier segment cannot be empty.")

    if raw != raw.strip():
        raise SQLIdentifierError("Identifier segment cannot have leading or trailing whitespace.")

    if len(raw) > MAX_IDENTIFIER_SEGMENT_LENGTH:
        raise SQLIdentifierError(
            f"Identifier segment exceeds the {MAX_IDENTIFIER_SEGMENT_LENGTH}-character limit."
        )

    if _IDENTIFIER_PATTERN.fullmatch(raw) is None:
        raise SQLIdentifierError("Identifier segment must match [A-Za-z_][A-Za-z0-9_]*.")

    return raw


@dataclass(
    frozen=True,
    slots=True,
)
class IdentifierSegment:
    """One strictly validated SQL identifier segment."""

    value: str

    def __post_init__(self) -> None:
        _validated_segment(self.value)

    @classmethod
    def parse(
        cls,
        raw: object,
    ) -> IdentifierSegment:
        return cls(_validated_segment(raw))

    @property
    def sql(self) -> str:
        escaped = self.value.replace(
            '"',
            '""',
        )

        return '"' + escaped + '"'


@dataclass(
    frozen=True,
    slots=True,
)
class QualifiedIdentifier:
    """A validated one-to-three-segment SQL identifier."""

    segments: tuple[
        IdentifierSegment,
        ...,
    ]

    def __post_init__(self) -> None:
        segment_count = len(self.segments)

        if segment_count < 1 or segment_count > MAX_QUALIFIED_IDENTIFIER_SEGMENTS:
            raise SQLIdentifierError(
                "Qualified identifier must contain between one and three segments."
            )

    @classmethod
    def parse(
        cls,
        raw: object,
    ) -> QualifiedIdentifier:
        if not isinstance(
            raw,
            str,
        ):
            raise SQLIdentifierError("Qualified identifier must be a string.")

        if raw != raw.strip():
            raise SQLIdentifierError(
                "Qualified identifier cannot have leading or trailing whitespace."
            )

        if not raw:
            raise SQLIdentifierError("Qualified identifier cannot be empty.")

        return cls(tuple(IdentifierSegment.parse(segment) for segment in raw.split(".")))

    @classmethod
    def from_segments(
        cls,
        *segments: object,
    ) -> QualifiedIdentifier:
        return cls(tuple(IdentifierSegment.parse(segment) for segment in segments))

    @property
    def sql(self) -> str:
        return ".".join(segment.sql for segment in self.segments)

    @property
    def values(self) -> tuple[str, ...]:
        return tuple(segment.value for segment in self.segments)


def is_valid_identifier_segment(
    value: object,
) -> bool:
    try:
        IdentifierSegment.parse(value)

    except SQLIdentifierError:
        return False

    return True


def is_valid_qualified_identifier(
    value: object,
) -> bool:
    try:
        QualifiedIdentifier.parse(value)

    except SQLIdentifierError:
        return False

    return True


def _deterministic_case(
    index: int,
) -> tuple[str, bool]:
    selector = index % 8

    if selector == 0:
        return (
            f"valid_name_{index}",
            True,
        )

    if selector == 1:
        return (
            f"{index}starts_with_digit",
            False,
        )

    if selector == 2:
        return (
            f"name_{index};DROP_TABLE",
            False,
        )

    if selector == 3:
        return (
            f"name_{index}--comment",
            False,
        )

    if selector == 4:
        return (
            f"name {index}",
            False,
        )

    if selector == 5:
        return (
            f'name_{index}"quote',
            False,
        )

    if selector == 6:
        return (
            f"name_{index}.second",
            False,
        )

    return (
        f"unicode_é_{index}",
        False,
    )


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


def build_sql_safety_primitives_report(
    project_root: Path,
    *,
    write_contracts: bool = True,
) -> dict[str, Any]:
    valid_examples = (
        "table_name",
        "_internal",
        "Column123",
        "select",
        "schema_name",
    )

    hostile_examples = (
        "",
        " ",
        " leading",
        "trailing ",
        "1table",
        "table-name",
        "table name",
        "table;DROP",
        "table--comment",
        "table/*comment*/",
        'table"quoted',
        "schema.table",
        "*",
        "éxternal",
        "line\nbreak",
        "null\x00byte",
    )

    valid_example_failures = [
        value for value in valid_examples if not is_valid_identifier_segment(value)
    ]

    hostile_example_acceptances = [
        value for value in hostile_examples if is_valid_identifier_segment(value)
    ]

    accepted_case_count = 0
    rejected_case_count = 0
    deterministic_violation_count = 0

    for index in range(DETERMINISTIC_CASE_COUNT):
        value, expected = _deterministic_case(index)

        actual = is_valid_identifier_segment(value)

        if actual:
            accepted_case_count += 1

        else:
            rejected_case_count += 1

        if actual != expected:
            deterministic_violation_count += 1

    qualified_examples = {
        "table_name": '"table_name"',
        ("schema_name.table_name"): ('"schema_name"."table_name"'),
        ("catalog_name.schema_name.table_name"): ('"catalog_name"."schema_name"."table_name"'),
        "select": '"select"',
    }

    qualified_rendering_violation_count = 0

    for raw, expected_sql in qualified_examples.items():
        rendered = QualifiedIdentifier.parse(raw).sql

        if rendered != expected_sql:
            qualified_rendering_violation_count += 1

    invalid_qualified_examples = (
        "",
        ".",
        "schema.",
        ".table",
        "a..b",
        "a.b.c.d",
        "schema.*",
        "schema.table;DROP",
        " schema.table",
        "schema.table ",
        "schema.table--comment",
    )

    invalid_qualified_acceptance_count = sum(
        is_valid_qualified_identifier(value) for value in invalid_qualified_examples
    )

    all_properties_passed = bool(
        not valid_example_failures
        and not hostile_example_acceptances
        and deterministic_violation_count == 0
        and qualified_rendering_violation_count == 0
        and invalid_qualified_acceptance_count == 0
    )

    report = {
        "model_version": ("cre-foundry-sql-safety-primitives-v1"),
        "strict_ascii_identifier_policy": True,
        "identifier_segment_pattern": ("[A-Za-z_][A-Za-z0-9_]*"),
        "maximum_identifier_segment_length": (MAX_IDENTIFIER_SEGMENT_LENGTH),
        "maximum_qualified_identifier_segments": (MAX_QUALIFIED_IDENTIFIER_SEGMENTS),
        "valid_example_count": len(valid_examples),
        "valid_example_failure_count": len(valid_example_failures),
        "hostile_example_count": len(hostile_examples),
        "hostile_example_acceptance_count": len(hostile_example_acceptances),
        "deterministic_case_count": (DETERMINISTIC_CASE_COUNT),
        "accepted_deterministic_case_count": (accepted_case_count),
        "rejected_deterministic_case_count": (rejected_case_count),
        "deterministic_case_violation_count": (deterministic_violation_count),
        "qualified_rendering_case_count": len(qualified_examples),
        "qualified_rendering_violation_count": (qualified_rendering_violation_count),
        "invalid_qualified_case_count": len(invalid_qualified_examples),
        "invalid_qualified_acceptance_count": (invalid_qualified_acceptance_count),
        "identifier_segments_quoted_independently": True,
        "value_parameterization_required": True,
        "identifier_parameterization_claimed": False,
        "automatic_source_rewrite_count": 0,
        "automatic_suppression_count": 0,
        "automatic_risk_acceptance_count": 0,
        "application_database_access_count": 0,
        "application_database_write_count": 0,
        "production_action_count": 0,
        "all_properties_passed": (all_properties_passed),
    }

    if not all_properties_passed:
        raise RuntimeError("SQL-safety primitive properties failed.")

    if write_contracts:
        _atomic_json(
            project_root / "docs" / "security" / "sql_safety_primitives_report.json",
            report,
        )

    return report
