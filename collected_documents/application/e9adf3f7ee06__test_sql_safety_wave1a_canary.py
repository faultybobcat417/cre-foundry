from __future__ import annotations

import ast
from pathlib import Path

import duckdb

PROJECT_ROOT = Path(__file__).resolve().parents[2]

SOURCE_PATH = PROJECT_ROOT / "src" / "cre_foundry" / "brampton_business_directory_silver.py"

FUNCTION_NAME = "build_brampton_business_directory_silver"


def _target_function() -> ast.FunctionDef | ast.AsyncFunctionDef:
    source = SOURCE_PATH.read_text(encoding="utf-8")

    tree = ast.parse(
        source,
        filename=str(SOURCE_PATH),
    )

    for node in tree.body:
        if (
            isinstance(
                node,
                (
                    ast.FunctionDef,
                    ast.AsyncFunctionDef,
                ),
            )
            and node.name == FUNCTION_NAME
        ):
            return node

    raise AssertionError("Could not locate the canary function.")


def _static_insert_query() -> str:
    function = _target_function()

    matches: list[str] = []

    for node in ast.walk(function):
        if not isinstance(
            node,
            ast.Call,
        ):
            continue

        if not isinstance(
            node.func,
            ast.Attribute,
        ):
            continue

        if node.func.attr != "executemany":
            continue

        if len(node.args) < 2:
            continue

        query_node = node.args[0]
        values_node = node.args[1]

        if not (
            isinstance(
                values_node,
                ast.Name,
            )
            and values_node.id == "rows"
        ):
            continue

        if not (
            isinstance(
                query_node,
                ast.Constant,
            )
            and isinstance(
                query_node.value,
                str,
            )
        ):
            continue

        if "INSERT INTO directory_rows" in query_node.value:
            matches.append(query_node.value)

    assert len(matches) == 1

    return matches[0]


def test_canary_query_is_static_and_fixed_arity() -> None:
    query = _static_insert_query()

    assert query == (
        "INSERT INTO directory_rows VALUES ("
        "?, ?, ?, ?, ?, ?, ?, ?, "
        "?, ?, ?, ?, ?, ?, ?, ?, "
        "?, ?, ?, ?, ?, ?, ?, ?, "
        "?, ?, ?, ?, ?, ?, ?, ?, "
        "?, ?, ?, ?, ?, ?, ?, ?, "
        "?, ?, ?, ?, ?, ?, ?, ?)"
    )

    assert query.count("?") == 48

    assert "{" not in query
    assert "}" not in query
    assert "%s" not in query


def test_canary_query_preserves_row_and_schema_shape() -> None:
    query = _static_insert_query()

    connection = duckdb.connect(":memory:")

    try:
        columns = ", ".join(f"column_{index:02d} INTEGER" for index in range(48))

        connection.execute(f"CREATE TABLE directory_rows ({columns})")

        rows = [
            tuple(
                range(
                    0,
                    48,
                )
            ),
            tuple(
                range(
                    100,
                    148,
                )
            ),
        ]

        connection.executemany(
            query,
            rows,
        )

        stored_rows = connection.execute(
            """
            SELECT *
            FROM directory_rows
            ORDER BY column_00
            """
        ).fetchall()

        description = connection.execute(
            """
            SELECT *
            FROM directory_rows
            LIMIT 0
            """
        ).description

        row_count = connection.execute(
            """
            SELECT COUNT(*)
            FROM directory_rows
            """
        ).fetchone()

        assert stored_rows == rows
        assert len(description) == 48
        assert row_count == (2,)

    finally:
        connection.close()


def test_canary_function_contains_no_placeholder_builder() -> None:
    function = _target_function()

    placeholder_names = [
        node
        for node in ast.walk(function)
        if (
            isinstance(
                node,
                ast.Name,
            )
            and node.id == "placeholders"
        )
    ]

    joined_queries = [
        node
        for node in ast.walk(function)
        if isinstance(
            node,
            ast.JoinedStr,
        )
        and ("INSERT INTO directory_rows" in ast.unparse(node))
    ]

    assert not placeholder_names
    assert not joined_queries
