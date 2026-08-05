# Browser and Computer-Vision Acquisition

Browser automation is a governed fallback acquisition channel, not the default
method.

## Acquisition precedence

1. Authorized official API
2. Authorized network-response capture
3. Authorized bulk or file download
4. Browser DOM or accessibility-tree extraction
5. Computer-vision fallback
6. Human exception review

## Required evidence

A future browser worker must capture:

- navigation recipe version;
- source and domain authorization;
- isolated browser profile;
- request and concurrency limits;
- DOM or accessibility-tree evidence;
- network archive when available;
- screenshots before and after visual actions;
- extracted artifact checksum;
- layout and selector versions;
- complete run logs;
- quarantine reason on ambiguity or drift.

## Computer-vision use

Computer vision may be used when authorized data cannot be extracted reliably
through APIs, network responses, files, DOM selectors or accessibility
semantics.

Visual actions must fail closed when:

- the expected screen or anchor is absent;
- multiple targets are plausible;
- page layout changes materially;
- authentication state is uncertain;
- a CAPTCHA or access restriction appears;
- the action could be destructive.

## Current state

Governance and hardware/package auditing are implemented. Browser and
computer-vision execution remain disabled until source-specific recipes,
permissions and replay fixtures exist.
