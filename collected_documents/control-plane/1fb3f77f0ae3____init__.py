"""Independent material implementation of the synthetic temporal identity graph.

This package implements the IDENTITY-001 semantic surface with its own
construction and its own checks.  It never imports
``evals.public.temporal_identity_evaluator``; the frozen independent evaluator
judges the subject this package renders, so the two implementations must agree
byte-for-byte on the canonical clean subject and diagnostic-for-diagnostic on
every registered mutation.

The material graph is expressed as a compact declarative seed of semantic facts
(grain catalog, assertions, links, protected bundle, expansion).  A renderer
walks that seed into the frozen ``TEMPORAL_IDENTITY_SYNTHETIC_SUBJECT`` document
and independently computes every record digest, the protection snapshot, the
lineage/journal chain, and the subject binding.  Standalone checks independently
re-derive grain co-location, corporate temporal, relocation, closure, alias,
alternative resolution, protection coverage, and correction semantics.
"""
from __future__ import annotations