# Project Workflow

## Core cycle

```text
ORIENT
→ VERIFY AUTHORITY AND REPOSITORY TRUTH
→ RECONCILE STATE
→ SELECT HIGHEST-VALUE EXECUTABLE TASK
→ COMPILE MINIMUM TASK CONTEXT
→ RESEARCH / EXPLORE
→ DEFINE OR VERIFY EVALUATOR
→ PLAN
→ BUILD
→ EVALUATE
→ INDEPENDENT SWEEP
→ REPAIR / COMBINE / REVERT
→ INTEGRATE
→ CHECKPOINT
→ GENERATE FOLLOW-UP TASKS
→ SELECT AGAIN
```

## Depth-first build rule

After M00 and M01, prove a thin end-to-end vertical slice:

```text
source fixture
→ normalized evidence
→ entity/location
→ candidate
→ transparent score
→ exactly-ten synthetic list
→ route manifest
→ field/outcome fixture
→ replay/evaluation
```

Do not finish every subsystem horizontally before the first integrated path.

## Task contract

Every task states:

- objective and business reason;
- dependencies and gates;
- repository paths/components;
- inputs and assumptions;
- non-goals and writable roots;
- required expertise;
- evaluator and known-bad cases;
- acceptance and artifacts;
- rollback and stop budget.

## Research loop

- ask only questions that can change a decision;
- prefer primary/official/reproducible evidence;
- preserve dates and provenance;
- classify fact, inference, assumption, hypothesis, and unknown;
- seek counterevidence;
- convert results into primitives, tests, decisions, or tasks.

## Identity loop

```text
raw source record
→ normalized address with unit
→ candidate legal/operating/location/property identities
→ temporal edges and alternatives
→ corroboration and conflict class
→ protected-account intersection
→ candidate eligibility
```

Name/address similarity alone is research evidence, not live eligibility.

## Improvement loop

1. measure baseline;
2. identify weakest load-bearing dimension;
3. generate focused alternatives;
4. implement one bounded experiment;
5. rerun evaluators;
6. inspect artifacts and failure modes;
7. retain, synthesize, or revert;
8. update state and scores.

## Best-of-N trigger

Use 3–5 materially different approaches when the decision is foundational,
expensive to reverse, quantitatively uncertain, security-sensitive, or likely
to constrain multiple later tasks.

## Agent use

- main orchestrator owns decisions, integration, and state;
- parallelize independent read-heavy research/review;
- use one writer per worktree;
- use non-overlapping writable roots;
- builder is not sole verifier;
- cap reviewers to the smallest sufficient set;
- integrate only after relevant reviewer results arrive.

## Checkpoint

Persist task result, state transition, artifact hashes, commands, evaluator
results, decisions, assumptions, risks, gates, rollback, and selected next task.
