"""Independent material implementation of the symbolic ECV engine.

Implements the ECONOMICS-001 semantic surface with its own construction and its
own diagnostics.  It never imports ``scripts.validate_economics_ecv``; the
frozen independent evaluator judges the subject this package renders, so the two
implementations must agree byte-for-byte on the canonical clean subject and
diagnostic-for-diagnostic on every registered mutation.

The material engine is expressed as a compact declarative authoritative
economics policy (services, territories, commission, costs, conversion
uncertainty, downside, fallback) under ``contracts/economic_engine.schema.json``.
A renderer walks that policy into the frozen ``COMMERCIAL_ECONOMICS_MODEL``
document.  Standalone checks independently re-derive risk-adjusted expected net
commercial value, downside, sensitivity, omitted-cost and modeled-as-realized
separation without importing the frozen evaluator.
"""
from __future__ import annotations