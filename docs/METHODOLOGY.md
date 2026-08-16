# Priority methodology

The showcase priority score is deliberately simple and transparent:

```text
score = 100 × (
  0.30 × recency
+ 0.25 × magnitude
+ 0.20 × corroboration
+ 0.15 × entity_confidence
+ 0.10 × signal_diversity
)
```

It is **not** presented as a probability of conversion.

## Components

- `recency`: nonlinear decay from the most recent accepted event.
- `magnitude`: bounded event-size heuristic; permit value uses broad bands rather than fake precision.
- `corroboration`: increases when independent evidence events converge on an account.
- `entity_confidence`: confidence from conservative account/event resolution.
- `signal_diversity`: rewards multiple signal families rather than duplicates from one source.

## Entity-resolution gate

A candidate is accepted only when its score clears an absolute confidence threshold **and** the winning candidate is sufficiently separated from the runner-up. Otherwise the event abstains and is excluded from scoring.

This prevents a high-value event at a shared address from becoming a confident recommendation without enough evidence.
