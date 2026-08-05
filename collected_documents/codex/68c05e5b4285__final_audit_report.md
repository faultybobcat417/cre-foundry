# Final Steel-Man Audit

## Verdict

The v1 harness had the correct direction but was still too prompt-centric.
v2 replaces “one large instruction that says continue” with a project operating
system whose control surfaces are machine-readable and independently testable.

## Material repairs

### 1. One-launch semantics

**Repair:** Separate interactive, headless-resumable, and tracker-orchestrated
execution modes. The prompt no longer implies that a single interactive turn
can literally execute forever.

### 2. Prompt duplication

**Repair:** Reduce the launch prompt to an initialization contract. Durable
operating rules live in `AGENTS.md`, the kernel, and the current task packet.

### 3. Hidden evaluator paradox

**Repair:** Split evaluation into public tests, sealed protected adversarial
tests, and a genuinely external hidden holdout. The builder is not asked to
create a “hidden” test that it can read and edit.

### 4. Horizontal build risk

**Repair:** Add an early thin vertical slice. The system must prove one complete
source-to-shadow-route-to-outcome-fixture path before building every subsystem
horizontally.

### 5. Expert-role overload

**Repair:** Every task classifies all expertise domains as ACTIVE, CONSULT, or
NOT_APPLICABLE with a reason. Only relevant reviewers load detailed context.

### 6. Token/context entropy

**Repair:** Add a deterministic context compiler that assembles a bounded,
task-specific packet with mission, invariants, state, task, evidence, skills,
decisions, and evaluator commands.

### 7. Ambiguous “best next task”

**Repair:** Use hard vetoes first, then lexicographic priority, then a numeric
tie-breaker. Security, authority, evaluator integrity, temporal leakage,
protected accounts, and exact-ten behavior cannot be traded away.

### 8. Configuration drift

**Repair:** Replace unverified Codex settings with a capability probe and a
minimal config template. Installed CLI/app-server capabilities are detected
before launch commands are generated.

### 9. Endless planning

**Repair:** Add a build/learn bias. After repository truth and evaluators,
prioritize the smallest useful vertical slice and empirical information gain.

### 10. State fragility

**Repair:** Claims, assumptions, hypotheses, questions, decisions, tasks,
artifacts, gates, and transitions now have canonical agent-facing primitives.

## Final conclusion

There is no magic phrase that guarantees a 0.01% outcome. The highest-probability
input is a compact invariant kernel plus a repository-legible feedback system
that makes correct behavior easier to perform and wrong behavior mechanically
visible.
