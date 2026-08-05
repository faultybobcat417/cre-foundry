# SQL Safety Primitives

## Security boundary

SQL values and SQL identifiers are separate security domains.

Data values and file paths must be passed through DuckDB parameters.
Identifiers cannot be passed as data parameters, so they must be validated
and quoted before entering SQL text.

## Identifier segments

An internal identifier segment must:

- be a string;
- contain between 1 and 128 characters;
- match `[A-Za-z_][A-Za-z0-9_]*`;
- contain no whitespace, comments, delimiters, quotes or wildcards.

## Qualified identifiers

A qualified identifier contains between one and three independently
validated segments. Every segment is independently double-quoted.

External labels, arbitrary source headings and client-provided text are data.
They must be mapped to governed internal identifiers rather than inserted
directly into SQL.

## Values and file paths

Values and paths must remain outside generated SQL text and be bound through
prepared parameters or an appropriate typed DuckDB Python API.

## Migration policy

The existing B608 findings remain open. This foundation does not suppress,
accept or declare an existing call site safe. Every call site must be
migrated, tested for semantic equivalence and rescanned independently.

## Forbidden shortcuts

- no inline `nosec`;
- no automatic suppression;
- no automatic risk acceptance;
- no unvalidated string concatenation;
- no direct file-path interpolation;
- no quoting a qualified name as one identifier segment.
