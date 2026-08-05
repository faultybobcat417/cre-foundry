# Research Basis

The v2 design was checked against current official OpenAI Codex material.

## Findings incorporated

- Agent-first teams achieved high autonomy by improving repository legibility,
  tools, tests, feedback loops, and architecture enforcement rather than asking
  the model to “try harder.”
- A short `AGENTS.md` should act as a map; structured repository documentation
  should be the system of record.
- Larger goals should be decomposed depth-first into building blocks that unlock
  progressively more capable work.
- Worktree-local applications, logs, metrics, traces, and test environments make
  outcomes directly legible to agents.
- Prompts work better when structured like strong issues: objective, paths,
  components, examples, acceptance, and relevant references.
- Best-of-N is valuable for consequential decisions, but it should not be used
  indiscriminately for trivial edits.
- Codex Skills are appropriate for stable recurring workflows.
- Interactive sessions do not by themselves solve multi-task orchestration;
  Symphony uses the task tracker as the control plane, isolated workspaces, a
  repository-owned workflow contract, retries, reconciliation, and observability.
- Codex App Server manages persistent/resumable threads and tool execution.
- CLI capabilities change over time; installed schemas/help should be probed
  rather than assuming every flag or config field is available.
- Secure execution should use legitimate sandbox and approval controls rather
  than bypassing them.

## Primary references

- OpenAI, “Harness engineering: leveraging Codex in an agent-first world,”
  February 11, 2026.
- OpenAI, “An open-source spec for Codex orchestration: Symphony,”
  April 27, 2026.
- OpenAI, “Unlocking the Codex harness: how we built the App Server,” 2026.
- OpenAI, “How OpenAI uses Codex.”
- OpenAI Codex open-source repository configuration and CLI schemas.
