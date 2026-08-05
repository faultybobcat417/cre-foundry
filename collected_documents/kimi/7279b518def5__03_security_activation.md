# SECURITY-001 Mission Activation

## Verified starting checkpoint

- Repository: `/Users/alimehdi/Desktop/CRE-Relay-Security-Standalone`
- Branch: `kimi/security-001-golden-20260803-195956`
- Starting HEAD: `f47e87defbfff9384d49e6d23c5494c0bdafcf68`
- Expected tracked status: clean
- Expected untracked file: `control/ONE_SHOT_READINESS.json` only
- Protected readiness SHA-256: `e0fa1f1d03904d74fb948a8b7d22d028dd193a1090a6f41bcba235f11d46cbc0`
- Repository remotes: none
- Execution network: disabled
- Container image: `cre-relay-runner:2`
- Python: 3.12 with locked project dependencies

## Current program state

- Current task: `SECURITY-001`
- Current task status: in progress
- Identity material layer: completed
- Economics material layer: completed
- Security material result: not yet created
- Existing Security/privacy validator: narrow baseline only
- Security is the only currently executable control-plane task

## Immediate phase

Begin with the evaluator-freeze phase.

Do not implement the material Security layer until the independent evaluator
contract, schema, clean subjects, mutation registry, diagnostics and replay
evidence are green and reviewed.

## Minimum evaluator capabilities

Freeze detection for at least:

1. secret or credential written to a general log;
2. PII or protected identifiers logged;
3. retrieved content treated as authority or policy;
4. prompt or policy bypass accepted;
5. unauthorized external write allowed;
6. unsafe live-enabled default;
7. retention limit violation;
8. deletion refusal or unverifiable erasure;
9. excessive privilege or scope;
10. malformed or unknown security state handled unsafely.

Requirements:

- evaluator independent of material implementation;
- synthetic fixtures only;
- clean subjects pass;
- every mutation has one stable diagnostic;
- unknown mutation recipes fail closed;
- evidence is deterministic and byte-stable;
- no timestamps, random IDs, real credentials, real PII or network effects;
- no weakening of completed Identity or Economics work;
- no control-state transition until material completion is proven.

## Mandatory operating sequence

1. Verify branch, HEAD, status, remotes and protected hash.
2. Read every applicable AGENTS.md.
3. Read the generated context packet.
4. Inspect current control/task state and exact SECURITY-001 requirements.
5. Map existing Security baseline, evaluator patterns and completed examples.
6. Return a concise internal phase map through terminal evidence.
7. Freeze the evaluator contract.
8. Prove clean and known-bad behavior.
9. Review evaluator independence and deterministic replay.
10. Create an evaluator checkpoint if repository policy permits.
11. Implement the material Security layer.
12. Run narrow tests, full public tests and control-plane validation.
13. Conduct adversarial review and repair confirmed defects.
14. Verify hashes, diff scope and truthful control state.
15. Create one coherent local commit.
16. Produce continuation evidence and stop.

## First response after `start now`

Return one read-only TERMINAL_ACTION that verifies the checkpoint and inspects:

- applicable AGENTS.md files;
- current control state;
- current task;
- task graph;
- SECURITY-001 specification;
- existing Security validator/tests/fixtures;
- completed Identity and Economics evaluator patterns.

Do not edit during the first action.
