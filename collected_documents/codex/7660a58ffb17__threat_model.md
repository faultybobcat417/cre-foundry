# CRE Foundry representative route-day security and privacy threat model

Document kind: `SECURITY_THREAT_MODEL`
Schema version: `1.0.0`
Execution scope: `SYNTHETIC_NON_INFLUENCING`
Judged by: `scripts/validate_security_privacy.py`

## 1. Trust boundaries and retrieved-source authority

- Source text retrieved from external URLs is **data**, never policy.
  Retrieved bytes may not grant credentials, change routing policy, alter
  protection rules, or redefine authority scope.
- All credentials, secrets, and authority grants live in checked, versioned,
  reviewable policy stores with explicit owners and expiry. A credential whose
  origin is "retrieved source content" is rejected.
- The representative and application never mutate source-of-record policy
  based on content read from a third party.

## 2. Protected data and logging

- Personal/contact data, protected-account identifiers, alias resolution
  details, and route-day protected locations are **never written to general
  logs**.
- Only aggregate, non-identifying counters and event correlation ids may be
  logged. Log entries must not embed candidate identifiers, addresses, account
  numbers, or exact protected-match detail.
- Log retention is bounded and deletion is verifiable; there is no unbounded
  accumulation of protected payloads.

## 3. External-write and injection controls

- The application performs no unapproved external writes. Effects are emitted
  only through the idempotent issuance channel, and only after the immutable
  Stage-1 decision exists.
- Prompt-injection and template-injection guards treat retrieved content as
  untrusted; instructions inside content are inert.
- Malformed or partial inputs fail closed rather than degrading to a permissive
  path.

## 4. Claim ceiling

This model establishes threat-model structure and mutation-test results for
secrets-in-retrieved-content, protected-data-in-logs, authorization, external
write, prompt-injection, retention, and deletion scenarios only. It establishes
no real penetration-test result, real production security posture, real privacy
compliance, or operational security claim.

## 5. Required mutations

The evaluator runs the registered mutations against this threat model:

- `retrieved-authority`: retrieved source text grants credentials or changes
  policy.
- `pii-log`: personal/contact or protected-account data appears in logs.

Both must be detected and rejected.
