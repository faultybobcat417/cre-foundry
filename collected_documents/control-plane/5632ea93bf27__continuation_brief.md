# CRE Foundry Continuation Brief

## Current position

Identity and Economics material implementations were recovered, validated,
and committed.

The next genuine material task is SECURITY-001.

## Correct continuation order

1. Verify the live branch, HEAD, status, and protected hashes.
2. Classify every remaining working-tree change.
3. Restore only independently confirmed timestamp/probe noise.
4. Reconcile the control and context files so they agree:
   - Identity completed
   - Economics completed
   - Security selected and in progress
5. Validate and commit that transition.
6. Repair Identity and Economics validator byte stability.
7. Freeze the Security evaluator before material implementation.
8. Implement and validate the Security material layer.
9. Update the task result and control plane truthfully.
10. Leave all external gates open.

## Security scope

Synthetic-only machinery for:
- threat modeling
- data classification
- least privilege
- negative authorization
- untrusted-input isolation
- privacy and retention
- deletion handling
- secret and PII redaction
- live-disabled defaults
- deterministic evidence and replay

The evaluator must reject at least:
- secret logging
- PII printing
- prompt-instruction bypass
- unauthorized writes
- live defaults
- retention violations
- refused deletion
- retrieved content treated as authority
- untrusted trust-boundary crossings
- protected-detail exposure

## Completion boundary

SECURITY-001 is complete only after:
- frozen independent evaluator
- registered mutation coverage
- material implementation
- narrow validator PASS
- Security tests PASS
- full public suite PASS
- control-plane validation PASS
- byte-stable repeated validation
- truthful task-result artifact
- readiness file unchanged
