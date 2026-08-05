# SQL Safety Wave 1A Canary

## Selected statement

The canary is the fixed-arity insert into the temporary `directory_rows`
relation in `build_brampton_business_directory_silver`.

## Why this statement was selected

The target relation is fixed, the row shape is fixed at 48 values and every
value was already supplied through `executemany` parameters. The only dynamic
SQL component was construction of the 48 question-mark markers.

## Migration

The dynamic f-string and placeholder-builder assignment were replaced with
one static SQL literal containing exactly 48 parameter markers.

No identifiers or data values are interpolated.

## Equivalence evidence

The canary tests verify:

- the query is an AST string constant;
- exactly 48 parameter markers exist;
- no interpolation syntax remains;
- two complete 48-column rows round-trip through an isolated in-memory
  DuckDB database;
- the resulting relation retains 48 columns;
- the source contains no remaining `placeholders` variable.

## Boundaries

This checkpoint does not access the application warehouse, register
snapshots, insert outcome events, train models, run a pilot, rank prospects or
perform outreach.

No scanner suppression or risk acceptance is introduced.
