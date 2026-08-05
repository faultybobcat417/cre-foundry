# COLD_START_AND_EXPERIMENT_POWER_V2.md

Machine authority:
`../../contracts/cold_start_experiment_design_v2.json`.

Power artifact:
`../../artifacts/research/route-day-power.json`.

## Treatment and estimand

The treatment unit is the representative route-day. The primary estimand is the
incremental number of qualifying F9 appointments caused by assignment to the
Tip Sheet policy.

## Planning sensitivity

The table uses a two-sided 5% significance level, 80% power, ten visits per
route-day and a 1.25 overdispersion planning factor. It is not the final power
model.

| Baseline visit F9 | Relative lift | F9/route control | F9/route treatment | Days/arm | Total days |
| --- | --- | --- | --- | --- | --- |
| 2% | 25% | 0.2 | 0.25 | 1766 | 3532 |
| 2% | 50% | 0.2 | 0.3 | 491 | 982 |
| 2% | 100% | 0.2 | 0.4 | 148 | 296 |
| 4% | 25% | 0.4 | 0.5 | 883 | 1766 |
| 4% | 50% | 0.4 | 0.6 | 246 | 492 |
| 4% | 100% | 0.4 | 0.8 | 74 | 148 |
| 6% | 25% | 0.6 | 0.75 | 589 | 1178 |
| 6% | 50% | 0.6 | 0.9 | 164 | 328 |
| 6% | 100% | 0.6 | 1.2 | 50 | 100 |

## Consequence

Thirty route-days remain a valuable instrumentation minimum. They are not a
generally powered appointment-lift experiment.

The confirmatory sample size must be frozen after estimating real route-day
base rates, clustering, overdispersion, representative effects and adherence.

## Causal safeguards

- block randomization by representative, weekday and territory/corridor;
- preserve intention-to-treat as primary;
- record incumbent choices before revealing assignment;
- separate policy quality, route feasibility and representative adherence;
- preregister practical-value, rejection and safety thresholds;
- never stop because a noisy point estimate looks exciting.
