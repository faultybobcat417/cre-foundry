from __future__ import annotations

from pathlib import Path

import duckdb
import pytest

from cre_foundry.sql_safety import (
    DETERMINISTIC_CASE_COUNT,
    IdentifierSegment,
    QualifiedIdentifier,
    SQLIdentifierError,
    build_sql_safety_primitives_report,
    is_valid_identifier_segment,
    is_valid_qualified_identifier,
)


@pytest.mark.parametrize(
    (
        "raw",
        "expected",
    ),
    [
        (
            "table_name",
            '"table_name"',
        ),
        (
            "_internal",
            '"_internal"',
        ),
        (
            "Column123",
            '"Column123"',
        ),
        (
            "select",
            '"select"',
        ),
    ],
)
def test_identifier_segment_quotes_valid_values(
    raw: str,
    expected: str,
) -> None:
    segment = IdentifierSegment.parse(raw)

    assert segment.value == raw
    assert segment.sql == expected


@pytest.mark.parametrize(
    "raw",
    [
        "",
        " ",
        " leading",
        "trailing ",
        "1table",
        "table-name",
        "table name",
        "table;DROP TABLE guard",
        "table--comment",
        "table/*comment*/",
        'table"quote',
        "schema.table",
        "*",
        "éxternal",
        "line\nbreak",
        "null\x00byte",
        "a" * 129,
        None,
        1,
        True,
    ],
)
def test_identifier_segment_rejects_hostile_values(
    raw: object,
) -> None:
    with pytest.raises(
        SQLIdentifierError,
    ):
        IdentifierSegment.parse(raw)

    assert is_valid_identifier_segment(raw) is False


@pytest.mark.parametrize(
    (
        "raw",
        "expected",
    ),
    [
        (
            "table_name",
            '"table_name"',
        ),
        (
            "schema_name.table_name",
            ('"schema_name"."table_name"'),
        ),
        (
            ("catalog_name.schema_name.table_name"),
            ('"catalog_name"."schema_name"."table_name"'),
        ),
        (
            "select.from",
            '"select"."from"',
        ),
    ],
)
def test_qualified_identifier_quotes_every_segment(
    raw: str,
    expected: str,
) -> None:
    identifier = QualifiedIdentifier.parse(raw)

    assert identifier.sql == expected

    assert is_valid_qualified_identifier(raw) is True


@pytest.mark.parametrize(
    "raw",
    [
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
        None,
        1,
        True,
    ],
)
def test_qualified_identifier_rejects_injection_shapes(
    raw: object,
) -> None:
    with pytest.raises(
        SQLIdentifierError,
    ):
        QualifiedIdentifier.parse(raw)

    assert is_valid_qualified_identifier(raw) is False


def test_from_segments_preserves_boundaries() -> None:
    identifier = QualifiedIdentifier.from_segments(
        "catalog_name",
        "schema_name",
        "table_name",
    )

    assert identifier.values == (
        "catalog_name",
        "schema_name",
        "table_name",
    )

    assert identifier.sql == ('"catalog_name"."schema_name"."table_name"')


def test_reserved_keyword_identifier_executes_safely() -> None:
    connection = duckdb.connect(":memory:")

    try:
        identifier = QualifiedIdentifier.parse("select")

        connection.execute(f"CREATE TABLE {identifier.sql} (value INTEGER)")

        connection.execute(
            f"INSERT INTO {identifier.sql} VALUES (?)",
            [42],
        )

        row = connection.execute(f"SELECT value FROM {identifier.sql}").fetchone()

        assert row == (42,)

    finally:
        connection.close()


def test_parameterized_parquet_path_cannot_inject_sql(
    tmp_path: Path,
) -> None:
    connection = duckdb.connect(":memory:")

    hostile_path = tmp_path / ("payload'; DROP TABLE guard; --.parquet")

    try:
        connection.execute("CREATE TABLE guard (value INTEGER)")

        connection.execute(
            "INSERT INTO guard VALUES (?)",
            [7],
        )

        connection.sql("SELECT 42 AS value").write_parquet(str(hostile_path))

        row = connection.execute(
            "SELECT value FROM read_parquet(?)",
            [str(hostile_path)],
        ).fetchone()

        assert row == (42,)

        guard_row = connection.execute("SELECT value FROM guard").fetchone()

        assert guard_row == (7,)

    finally:
        connection.close()


def test_sql_safety_report_is_deterministic(
    tmp_path: Path,
) -> None:
    first = build_sql_safety_primitives_report(
        tmp_path,
        write_contracts=True,
    )

    report_path = tmp_path / "docs" / "security" / "sql_safety_primitives_report.json"

    first_bytes = report_path.read_bytes()

    second = build_sql_safety_primitives_report(
        tmp_path,
        write_contracts=True,
    )

    second_bytes = report_path.read_bytes()

    assert first == second
    assert first_bytes == second_bytes

    assert first["deterministic_case_count"] == DETERMINISTIC_CASE_COUNT

    assert first["deterministic_case_violation_count"] == 0

    assert first["hostile_example_acceptance_count"] == 0

    assert first["invalid_qualified_acceptance_count"] == 0

    assert first["all_properties_passed"] is True

    assert first["automatic_source_rewrite_count"] == 0

    assert first["automatic_suppression_count"] == 0

    assert first["application_database_access_count"] == 0
