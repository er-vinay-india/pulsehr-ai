"""
HighView Ingestion V2 — Profiling Package (Stage 4 EDA-A)
"""

from app.services.ingestion_v2.profiling.structural_profiler import (
    compute_candidate_dimension_score,
    compute_candidate_identifier_score,
    compute_deterministic_quantiles,
    compute_pattern_signature,
    compute_shannon_entropy,
    profile_column,
    profile_dataset,
    profile_table,
)

__all__ = [
    "compute_candidate_dimension_score",
    "compute_candidate_identifier_score",
    "compute_deterministic_quantiles",
    "compute_pattern_signature",
    "compute_shannon_entropy",
    "profile_column",
    "profile_dataset",
    "profile_table",
]
