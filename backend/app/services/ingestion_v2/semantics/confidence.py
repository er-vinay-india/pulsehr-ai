"""
HighView Ingestion Intelligence V2 — Semantics Confidence Engine
Deterministic scoring and confidence calibration for semantic column assignments.
"""

from __future__ import annotations


def calculate_semantic_confidence(
    structural_score: float,
    lexical_score: float,
    context_score: float,
    is_contradiction: bool = False,
) -> float:
    """
    Deterministic confidence calculation for semantic role and entity assignments.
    Formula:
    confidence = 0.50 * structural_score + 0.35 * lexical_score + 0.15 * context_score
    If value structure directly contradicts lexical naming (e.g. 'employee_id' with 3 department values),
    confidence is severely penalized to force AMBIGUOUS.
    """
    if is_contradiction:
        return 0.20

    raw = 0.50 * structural_score + 0.35 * lexical_score + 0.15 * context_score
    return round(min(1.0, max(0.0, raw)), 4)


def get_confidence_band(confidence: float) -> str:
    """Classifies numeric confidence into governed bands."""
    if confidence >= 0.85:
        return "HIGH"
    if confidence >= 0.65:
        return "MEDIUM"
    return "LOW"
