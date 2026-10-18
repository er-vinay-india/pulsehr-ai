"""
HighView Ingestion Intelligence V2 — Governed Grain Rule Registry
Deterministic rules, composite patterns, and thresholds for table grain inference.
"""

from __future__ import annotations

from app.services.ingestion_v2.contracts.grain import CanonicalGrain, TemporalGrain
from app.services.ingestion_v2.contracts.semantics import SemanticEntityType

# Governed Thresholds
MIN_GRAIN_KEY_UNIQUENESS: float = 0.85
COMPOSITE_GRAIN_UNIQUENESS_THRESHOLD: float = 0.90
MAX_GRAIN_COMBINATION_WIDTH: int = 3
MAX_COMPOSITE_CANDIDATES_EVALUATION: int = 5

# Entity to CanonicalGrain Mapping
ENTITY_TO_GRAIN_MAP: dict[SemanticEntityType, CanonicalGrain] = {
    SemanticEntityType.PERSON: CanonicalGrain.PERSON,
    SemanticEntityType.DEPARTMENT: CanonicalGrain.DEPARTMENT,
    SemanticEntityType.STORE: CanonicalGrain.STORE,
    SemanticEntityType.PRODUCT: CanonicalGrain.PRODUCT,
    SemanticEntityType.LOCATION: CanonicalGrain.LOCATION,
    SemanticEntityType.ORGANIZATION: CanonicalGrain.ORGANIZATION,
    SemanticEntityType.TRANSACTION: CanonicalGrain.TRANSACTION,
    SemanticEntityType.EVENT: CanonicalGrain.EVENT,
    SemanticEntityType.UNKNOWN: CanonicalGrain.UNKNOWN,
    SemanticEntityType.AMBIGUOUS: CanonicalGrain.AMBIGUOUS,
}


def map_temporal_frequency(
    col_name: str,
    date_span_days: int | None,
    distinct_count: int,
) -> TemporalGrain:
    """Infers temporal granularity level (DAY, WEEK, MONTH, etc.) from column structure."""
    name_lower = col_name.lower()

    if "month" in name_lower or "mon" in name_lower or "yyyymm" in name_lower:
        return TemporalGrain.MONTH
    if "week" in name_lower or "wk" in name_lower:
        return TemporalGrain.WEEK
    if "quarter" in name_lower or "qtr" in name_lower:
        return TemporalGrain.QUARTER
    if "year" in name_lower or "annual" in name_lower:
        return TemporalGrain.YEAR

    if date_span_days is not None and distinct_count > 0:
        ratio = date_span_days / max(1, distinct_count)
        if ratio <= 2.0:
            return TemporalGrain.DAY
        if 5.0 <= ratio <= 9.0:
            return TemporalGrain.WEEK
        if 25.0 <= ratio <= 35.0:
            return TemporalGrain.MONTH

    return TemporalGrain.DAY
