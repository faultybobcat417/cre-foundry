# Continue and Stop Policy

Continue while there is an authorized, executable task with positive expected
project value.

Do not stop because the first implementation works, documentation is extensive,
a patch is merged, or the current context window ends.

A task loop stops when its acceptance passes, it is reverted, or a precise gate
blocks it.

A session checkpoint occurs before approval boundaries, context exhaustion,
environment shutdown, or handoff.

The project pauses only when:

- all positive-value work is blocked by named external/empirical gates;
- registered search/improvement budgets show non-positive marginal value;
- integrity requires failed-safe termination;
- or the required production and commercial end state is actually proven.

“Paused and resumable” is not “finished.”
