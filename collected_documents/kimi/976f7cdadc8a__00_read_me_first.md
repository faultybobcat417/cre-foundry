# Kimi CRE Campaign Control Packet

## Isolated worktree

- Path: `/Users/alimehdi/Desktop/CRE-Kimi-Security-20260803-195956`
- Branch: `kimi/security-001-golden-20260803-195956`
- Starting HEAD: `f47e87defbfff9384d49e6d23c5494c0bdafcf68`
- Source repository remains untouched at `/Users/alimehdi/Documents/cre`

## Hard budget policy

This campaign does not attempt the remaining production system in one session.
It uses scarce Kimi capacity to create one golden evaluator-first checkpoint:
`SECURITY-001`.

The repeatable campaign pattern is:

1. bounded read-only audit;
2. evaluator freeze;
3. material implementation;
4. full verification and red team;
5. coherent commit and continuation packet;
6. stop before the next task.

## Safety

- Never edit, stage, commit, regenerate or delete
  `control/ONE_SHOT_READINESS.json`.
- Never push.
- Never use real credentials or PII.
- Keep live permissions and external effects disabled.
- Work only inside the isolated worktree.
- Do not begin a second control-plane task.
