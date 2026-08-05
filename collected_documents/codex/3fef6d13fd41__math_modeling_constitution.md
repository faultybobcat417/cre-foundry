# Mathematical, Modeling, and Experiment Constitution

## 1. Primary estimand

Let a route-day be \(j=(r,d)\), with representative \(r\) and date \(d\).

- \(A_j\): assigned list policy/treatment.
- \(Y_j^{F9}(W)\): number of adjudicated F9 bookings within outcome window \(W\).
- \(Y_j(a)\): potential F9 outcome under policy \(a\).

Primary incremental estimand:

\[
\tau_{a,b} = \mathbb{E}[Y_j(a)-Y_j(b)]
\]

The confirmatory analysis is intention-to-treat at the route-day level, adjusted
for preregistered blocks and clustering.

## 2. Candidate opportunity model

For candidate-location \(i\) at prediction time \(t\):

\[
p_i^{F9}(W) = P(T_i^{F9}\le W \mid X_{i,t}, R_r, M_t)
\]

where \(X_{i,t}\) is point-in-time evidence, \(R_r\) representative context, and
\(M_t\) market/time context.

If treatment-effect identification is supported:

\[
\delta_i = \mathbb{E}[Y_i(1)-Y_i(0)\mid X_{i,t}]
\]

Otherwise use calibrated booking probability as a ranking proxy and label it
explicitly as non-causal.

## 3. Commercial value

A candidate's distributional net value is:

\[
V_i =
\delta_i\,
p_i^{attend}\,
p_i^{mandate}\,
p_i^{transaction}\,
\mathbb{E}[Commission_i]
-
C_i
-
\lambda\,Risk_i
\]

If \(\delta_i\) is unavailable, substitute the calibrated non-causal proxy and
cap the claim accordingly.

Costs include representative time, acquisition/processing, service/access
friction, and system costs. Company-vehicle energy/depreciation starts at zero
ranking weight, while time and completion remain constrained.

## 4. List and route optimization

For primary set \(S\):

\[
\max_{|S|=10}
\left[
\sum_{i\in S} V_i
-
Redundancy(S)
-
InterferenceRisk(S)
\right]
\]

subject to:

- eligibility and protected-account clearance;
- one candidate per required entity grain;
- composition/diversity limits;
- representative shift/time feasibility;
- uncertainty and access constraints;
- exact-ten or abstention.

Proximity is optimized only among lists retaining the registered business-value
floor relative to the best admissible list.

## 5. Time-to-event and competing risks

Use survival/competing-risk formulations when event timing and censoring matter:

- F9 booking;
- closure/ineligibility;
- relocation/expansion/contraction;
- mandate/transaction progression.

Do not convert censored or immature examples into negatives.

## 6. Baseline ladder

Every complex model competes against:

1. incumbent representative selection;
2. stratified random eligible locations;
3. transparent rules;
4. recency-only/source-family heuristics;
5. regularized calibrated models;
6. survival/competing-risk models;
7. tree/boosting or other complex models;
8. uplift/causal models only when identification and data support them.

## 7. Metrics

### Data/identity

- coverage and valid-zero rate;
- entity precision and conflict recall;
- protected false-clear count;
- temporal leakage count;
- source latency and missingness.

### Probability/model

- log loss and Brier score;
- calibration intercept/slope and reliability curves;
- discrimination/ranking metrics;
- uncertainty coverage;
- temporal and subgroup stability;
- source/mechanism ablation.

### Decision/list

- expected net value;
- precision/value among ten;
- exact-ten availability and abstention;
- route completion probability;
- diversity/redundancy;
- representative adherence and substitution.

### Causal/commercial

- ITT F9 lift per route-day;
- confidence/credible interval;
- practical threshold;
- attendance, mandate, transaction, and commission lift;
- incremental cost and net ROI.

## 8. Validation design

- nested temporal validation;
- municipality/period/source holdouts;
- point-in-time feature reconstruction;
- negative controls and placebo dates;
- missingness and label sensitivity;
- entity-link perturbation;
- route/provider sensitivity;
- mutation and fault testing;
- prospective shadow before field treatment.

## 9. Power

Do not hardcode a confirmatory sample size before observing:

- baseline F9 rate;
- route-day variance;
- representative/pod intracluster correlation;
- interference radius/exposure;
- adherence and substitution;
- attrition and outcome maturity;
- minimum economically meaningful lift.

Use an instrumentation phase to estimate these, then preregister the confirmatory
calculation.

## 10. Promotion rule

Promote only when the candidate approach beats meaningful baselines on
point-in-time, calibration, operational, economic, and required causal evidence,
with rollback and monitoring.
