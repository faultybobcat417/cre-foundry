# SQL Safety Wave 1A Migration Plan

This plan isolates the seven B608 call sites that already use database parameters elsewhere in the same statement.

- Candidates: `6`
- Affected files: `4`
- Source modifications: `0`
- Automatic rewrites: `0`
- Suppressions: `0`
- Risk acceptances: `0`

## Exact queue

### 1. src/cre_foundry/brampton_cross_source_reconciliation.py:549

- Scope: `build_brampton_cross_source_reconciliation`
- Classification: `manual_query_shape_review`
- Query kind: `dynamic_insert`
- AST digest: `12c5d1b3d88c19def44f9248514de8779749e20850c670118bcca99eacc0f998`
- Test references: `1`

Inspect the complete statement and separate every identifier from every data value before selecting the canary migration.

```python
connection.executemany(
                f"""
                INSERT INTO
                    silver.brampton_permit_cross_source_reconciliation
                VALUES ({placeholders})
                """,
                rows,
            )
```

### 2. src/cre_foundry/brampton_permit_silver.py:361

- Scope: `build_brampton_permit_silver`
- Classification: `identifier_candidate`
- Query kind: `dynamic_insert`
- AST digest: `8d3ccb6c507035cd13f652faadf316a6e0ae43002f21080cb30d3677ad473e81`
- Test references: `1`

Separate schema, table and column tokens from data values and route each token through the strict SQL identifier primitives.

```python
staging.executemany(
            f"""
            INSERT INTO permit_rows
            VALUES ({placeholders})
            """,
            rows,
        )
```

### 3. src/cre_foundry/brampton_verification_ledger.py:1066

- Scope: `project_verification_state`
- Classification: `manual_query_shape_review`
- Query kind: `dynamic_insert`
- AST digest: `814a568f5461ebc08c77d965078c5cf0a4cf576c6000fb0aa54f149f31a356a3`
- Test references: `1`

Inspect the complete statement and separate every identifier from every data value before selecting the canary migration.

```python
connection.executemany(
                f"""
                INSERT INTO
                    control.brampton_verification_task_state
                VALUES ({placeholders})
                """,
                state_rows,
            )
```

### 4. src/cre_foundry/brampton_verification_ledger.py:1109

- Scope: `project_verification_state`
- Classification: `manual_query_shape_review`
- Query kind: `dynamic_insert`
- AST digest: `3e02d2434645b505bc536416b4e22b598ee4eb2eabffca6d5b4d5c88e2565302`
- Test references: `1`

Inspect the complete statement and separate every identifier from every data value before selecting the canary migration.

```python
connection.executemany(
                f"""
                INSERT INTO
                    control.brampton_verification_workflow_state
                VALUES ({placeholders})
                """,
                workflow_rows,
            )
```

### 5. src/cre_foundry/primitive_quality.py:554

- Scope: `_duckdb_profile_relation`
- Classification: `identifier_candidate`
- Query kind: `dynamic_distinct_projection`
- AST digest: `d2c6d0391e77af00d446b040ec0f2a099b5217ce1a2d8b44c145c1ce586b825d`
- Test references: `5`

Separate schema, table and column tokens from data values and route each token through the strict SQL identifier primitives.

```python
safety_rows = connection.execute(
                f"""
                SELECT DISTINCT
                    CAST(
                        {quoted_column}
                        AS VARCHAR
                    )
                FROM {relation_identifier}
                WHERE
                    {quoted_column}
                    IS NOT NULL
                ORDER BY 1
                LIMIT ?
                """,
                [maximum_safety_values],
            ).fetchall()
```

### 6. src/cre_foundry/primitive_quality.py:675

- Scope: `_sqlite_profile_relation`
- Classification: `identifier_candidate`
- Query kind: `dynamic_distinct_projection`
- AST digest: `2f354e74662a536a32875996b033f5c01827a760719b362c1d2b656e142c8378`
- Test references: `5`

Separate schema, table and column tokens from data values and route each token through the strict SQL identifier primitives.

```python
safety_rows = connection.execute(
                f"""
                SELECT DISTINCT
                    CAST(
                        {quoted_column}
                        AS TEXT
                    )
                FROM {relation_identifier}
                WHERE
                    {quoted_column}
                    IS NOT NULL
                ORDER BY 1
                LIMIT ?
                """,
                (maximum_safety_values,),
            ).fetchall()
```
