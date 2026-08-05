# OBSERVABILITY-001 material lineage layer

This synthetic, non-influencing layer creates complete deterministic
lineage across source, snapshot, identity, feature, model, policy, route,
evaluator, and outcome stages.

Every lineage artifact binds an artifact identifier, owner, version,
as-of clock, content SHA-256, and explicit parent edge. The decision and
general log event share one correlation identifier. Replay identity is
recomputed from canonical decision inputs.

General logs reject secret, credential, token, account, address, contact,
email, and phone-like synthetic payloads. Live permissions and external
effects remain disabled.

The material implementation is independent from both the frozen
OBSERVABILITY-001 evaluator and the legacy observability-lineage evaluator.

Public proof level 4 establishes synthetic contract conformance only. It
does not establish production telemetry completeness, durability,
recovery, operational effectiveness, sealed independence, or deployment
readiness.
