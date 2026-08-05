# Codex Trial Protocol

Structural validation is not behavioral proof. Before production use, run this
launch system in clean Codex threads/workspaces.

## Trial set

1. repository absent;
2. repository present but empty;
3. repository with conflicting old architecture;
4. repository with a known-bad evaluator case;
5. task requiring Best-of-N;
6. task with irrelevant expertise domains;
7. task with a blocked external permission;
8. interrupted/resumed task;
9. parallel read reviewers plus one writer;
10. thin vertical-slice implementation.

## Measures

- mission/invariant retention;
- repository fact accuracy;
- context packet relevance;
- unnecessary file loading;
- task quality and DAG correctness;
- evaluator independence;
- appropriate expert activation;
- implementation correctness;
- claim/proof calibration;
- checkpoint/resume success;
- token, time, and human-intervention cost.

## Promotion

Run multiple independent trials. Keep the prompt/kernel version only if it
improves the aggregate rubric without introducing a critical failure. Preserve
unsuccessful trial artifacts and reasons.
