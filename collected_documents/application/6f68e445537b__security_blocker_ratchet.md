# Security Blocker Ratchet

The repository currently contains known, open Bandit B608 findings. They are
not suppressed, accepted or declared safe.

The temporary ratchet permits the exact reviewed baseline to remain visible
while remediation proceeds. It fails when:

- a new blocking finding appears;
- an existing finding changes identity and is therefore treated as new;
- the scanner control plane is not operational;
- the blocker baseline is malformed or expanded.

A blocker that disappears is counted as remediated. The baseline cannot be
expanded automatically.

When the current blocker count reaches zero, CI must return to the full
`security_scan.sh --enforce` gate and this temporary ratchet must be retired.
