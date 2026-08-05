# ODBus Target-Market Silver Contract

## Scope

The dataset contains historical ODBus business records associated
with Brampton or Mississauga.

It is an entity-resolution baseline, not proof that a business is
currently operating or has a current real-estate requirement.

## Ontario filter

`prov_terr = ON` after trimming and case normalization.

`PRUID` is retained as a validation field but is not a required
filter because many Ontario records have no usable PRUID.

## Municipality resolution

1. Use `CSDNAME` when it equals Brampton or Mississauga.
2. Otherwise use `city` when it equals Brampton or Mississauga.
3. Quarantine rows where both fields identify target municipalities
   but disagree with one another.

## Missing values

Blank strings, `..` and `NOT AVAILABLE` become null.

## Coordinates

Invalid or unavailable coordinates become null. The associated
quality classification remains available in `coordinate_quality`.

## Employee values

The source value is preserved. Parsed fields distinguish exact
counts, ranges, lower bounds and unknown or unparsed values.

## Current-status constraint

`current_status_verified` is always false for this historical source.
