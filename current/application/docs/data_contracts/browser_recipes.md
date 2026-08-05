# Browser Recipe Framework

Browser recipes describe authorized, deterministic acquisition navigation.

## Recipe lifecycle

- `design_pending`: incomplete architecture placeholder;
- `disabled`: complete but not available for review or execution;
- `review_ready`: complete and awaiting authorization;
- `executable`: only valid after browser runtime is separately enabled.

The current runtime rejects executable recipes.

## Required executable fields

An executable recipe must include:

- registered source ID;
- recipe version;
- start URL;
- domain allowlist;
- deterministic steps;
- assertions for expected page state;
- DOM and screenshot evidence rules;
- extraction checksum;
- layout-drift quarantine behavior.

## Visual fallback

Computer vision is available only after API, network, file, DOM and
accessibility-tree methods are unavailable or unreliable.

Visual ambiguity, missing anchors, unexpected layouts, CAPTCHAs and uncertain
authentication state must fail closed.
