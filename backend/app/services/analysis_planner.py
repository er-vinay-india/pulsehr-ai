"""Bounded AI Analysis Planner & Dynamic Chart Selector.

Executes the bounded analytics workflow:
Profile -> Interpret -> Discover Relationships -> Propose Analyses & Charts -> Validate Prerequisites -> Compute -> Verify.

Guardrails:
- Pure deterministic computation (no arbitrary model code execution).
- Complete eligible datasets for metrics (no sample extrapolation).
- Row counts are never assumed to equal unique employee counts without verified unique identifiers.
- Rates require verified denominators.
- Non-additive measures (ratings, rates, percentages) are never summed.
- Time-series charts require valid temporal columns with sufficient points.

Modular components are implemented under app.services.planner.*
"""

from .planner.sanitizer import sanitize_untrusted_text
from .planner.entity_classifier import classify_row_entity
from .planner.numeric_parser import parse_numeric_series
from .planner.chart_evaluator import evaluate_chart_prerequisites

__all__ = [
    "sanitize_untrusted_text",
    "classify_row_entity",
    "parse_numeric_series",
    "evaluate_chart_prerequisites",
]
