# SQL Safety Count Semantics

## Original semantic baseline

`config/security_blocker_baseline.json` retains the original twenty semantic
B608 identities. This baseline does not shrink as findings are remediated.

It is neither a suppression list nor a risk-acceptance list.

## Current inventory gate

`config/sql_safety_remediation_inventory.json` records the exact blocker count
expected from the current source tree.

After the first canary remediation, this value is nineteen.

## Generated inventory policy

The generated remediation summary preserves the original governed policy
baseline of twenty while separately reporting the observed current
`blocking_b608_count` of nineteen.

Therefore, the valid canary state is:

- generated policy baseline: 20;
- configured current-count gate: 19;
- observed current blocker count: 19;
- semantic ratchet baseline: 20;
- semantic remediated count: 1;
- new semantic blockers: 0.
