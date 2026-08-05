# Semantic SQL Finding Identity

## Purpose

Source line numbers remain useful evidence locations, but they are too
unstable to serve as the permanent identity of unresolved SQL-security
findings. Formatting or repairing one nearby statement can move unrelated
findings without changing their security meaning.

## Inventory evidence

Each inventoried B608 finding now records:

- scanner;
- advisory identifier;
- finding title;
- source path and current line evidence;
- enclosing function or class;
- normalized statement-text digest;
- normalized Python AST digest with source positions excluded.

## Current boundary

This checkpoint adds semantic identity evidence only. It does not yet replace
the existing blocker-ratchet identity algorithm.

No dynamic SQL source statement is rewritten, suppressed or accepted by this
layer.

## Next checkpoint

The next checkpoint migrates the blocker baseline and ratchet from line-number
identity to semantic AST identity. It will prove that formatting and line
movement do not create false blockers while semantic query changes do.
