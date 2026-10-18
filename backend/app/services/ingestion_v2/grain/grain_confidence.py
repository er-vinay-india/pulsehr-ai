"""
HighView Ingestion Intelligence V2 — Grain Confidence Engine
Deterministic scoring and confidence calibration for table grain inference.
"""

from __future__ import annotations


def calculate_grain_confidence(
    key_uniqueness: float,
    entity_confidence: float,
    temporal_confidence: float = 1.0,
    has_surrogate_key_distraction: bool = False,
) -> float:
    """
    Deterministic confidence calculation for table grain inference.
    Formula:
    confidence = 0.50 * key_uniqueness + 0.35 * entity_confidence + 0.15 * temporal_confidence
    """
    base = 0.50 * key_uniqueness + 0.35 * entity_confidence + 0.15 * temporal_confidence
    if has_surrogate_key_distraction:
        # Penalize slightly if relying purely on generic surrogate key rather than business entity
        base = max(0.60, base - 0.10)
    return round(min(1.0, max(0.0, base)), 4)
