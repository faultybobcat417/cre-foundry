# Semantic Security Ratchet V2

## Purpose

The previous ratchet used source line numbers as part of unresolved-finding
identity. That was useful for the first fixed baseline but too brittle for
surgical remediation because harmless edits can move unrelated statements.

## Semantic identity

The V2 identity combines:

- scanner and advisory;
- finding title;
- source path;
- enclosing function or class;
- classified query shape;
- normalized Python statement AST digest with source positions removed.

Line numbers remain evidence locations but are not identity fields.

## Permitted movement

The V2 ratchet permits:

- line-number movement;
- formatting-only movement;
- existing blockers to disappear after remediation.

## Rejected movement

The V2 ratchet rejects:

- a new unresolved dynamic-SQL statement;
- semantic changes to an unresolved statement;
- movement to another source file;
- movement to another scope;
- query-shape classification changes;
- duplicate semantic identities;
- scanner and inventory count disagreement.

The baseline remains temporary and is neither suppression nor risk
acceptance. Full scanner enforcement becomes available only after the current
blocker count reaches zero.
