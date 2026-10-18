"""
HighView Ingestion V2 — Phase I4: Relationship Discovery & Candidate Signals
Component: Independent Evidence Signal Computation

Computes multi-dimensional signals across semantic, lexical, structural, and value-overlap domains.
Zero LLM calls. Fully deterministic.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence
import pandas as pd

from app.services.ingestion_v2.contracts.normalization import CanonicalPhysicalType
from app.services.ingestion_v2.contracts.profiling import ColumnStructuralProfile, TableStructuralProfile
from app.services.ingestion_v2.contracts.semantics import SemanticColumnAssignment, SemanticColumnRole, SemanticEntityType
from app.services.ingestion_v2.relationships.candidate_rules import (
    compute_entity_type_compatibility,
    compute_name_similarity,
    compute_physical_type_compatibility,
    compute_semantic_role_compatibility,
)


@dataclass(frozen=True)
class ValueOverlapMetrics:
    intersection_size: int
    left_distinct: int
    right_distinct: int
    left_coverage: float
    right_coverage: float
    jaccard_overlap: float
    left_null_ratio: float
    right_null_ratio: float
    left_rows: int
    right_rows: int


@dataclass(frozen=True)
class CandidateEvidenceSignals:
    semantic_role_score: float
    entity_type_score: float
    datatype_compatibility: float
    lexical_similarity: float
    pattern_compatibility: float
    candidate_id_score: float
    overlap_metrics: ValueOverlapMetrics | None
    is_composite: bool


def _extract_clean_key_set(series: pd.Series) -> tuple[set[str], float]:
    """
    Extract non-null, string-normalized key set preserving textual representations (e.g. leading zeros '00421').
    Returns (clean_key_set, null_ratio).
    """
    total_len = len(series)
    if total_len == 0:
        return set(), 0.0

    # Drop nulls, NAs, and empty strings
    valid_mask = series.notna()
    null_count = int((~valid_mask).sum())

    clean_vals = series[valid_mask].astype(str).str.strip()
    # Filter empty strings as nulls
    non_empty = clean_vals[clean_vals != ""]
    null_count += len(clean_vals) - len(non_empty)

    null_ratio = round(null_count / total_len, 4)
    key_set = set(non_empty.values)
    return key_set, null_ratio


def compute_value_overlap_single(
    series_left: pd.Series,
    series_right: pd.Series,
) -> ValueOverlapMetrics:
    """Compute value overlap and coverage between two single-column series."""
    left_keys, left_null_ratio = _extract_clean_key_set(series_left)
    right_keys, right_null_ratio = _extract_clean_key_set(series_right)

    left_distinct = len(left_keys)
    right_distinct = len(right_keys)

    if left_distinct == 0 or right_distinct == 0:
        return ValueOverlapMetrics(
            intersection_size=0,
            left_distinct=left_distinct,
            right_distinct=right_distinct,
            left_coverage=0.0,
            right_coverage=0.0,
            jaccard_overlap=0.0,
            left_null_ratio=left_null_ratio,
            right_null_ratio=right_null_ratio,
            left_rows=len(series_left),
            right_rows=len(series_right),
        )

    intersection = left_keys & right_keys
    inter_size = len(intersection)
    union_size = len(left_keys | right_keys)

    left_cov = round(inter_size / left_distinct, 4)
    right_cov = round(inter_size / right_distinct, 4)
    jaccard = round(inter_size / union_size, 4) if union_size > 0 else 0.0

    return ValueOverlapMetrics(
        intersection_size=inter_size,
        left_distinct=left_distinct,
        right_distinct=right_distinct,
        left_coverage=left_cov,
        right_coverage=right_cov,
        jaccard_overlap=jaccard,
        left_null_ratio=left_null_ratio,
        right_null_ratio=right_null_ratio,
        left_rows=len(series_left),
        right_rows=len(series_right),
    )


def compute_value_overlap_composite(
    df_left: pd.DataFrame,
    left_cols: Sequence[str],
    df_right: pd.DataFrame,
    right_cols: Sequence[str],
) -> ValueOverlapMetrics:
    """Compute value overlap and coverage for multi-column composite keys."""
    if len(left_cols) != len(right_cols) or not left_cols:
        return ValueOverlapMetrics(0, 0, 0, 0.0, 0.0, 0.0, 1.0, 1.0, len(df_left), len(df_right))

    sub_left = df_left[list(left_cols)].dropna()
    sub_right = df_right[list(right_cols)].dropna()

    left_null_ratio = round((len(df_left) - len(sub_left)) / max(1, len(df_left)), 4)
    right_null_ratio = round((len(df_right) - len(sub_right)) / max(1, len(df_right)), 4)

    # Form composite tuples of string values
    left_tuples = set(zip(*(sub_left[c].astype(str).str.strip() for c in left_cols)))
    right_tuples = set(zip(*(sub_right[c].astype(str).str.strip() for c in right_cols)))

    left_distinct = len(left_tuples)
    right_distinct = len(right_tuples)

    if left_distinct == 0 or right_distinct == 0:
        return ValueOverlapMetrics(0, left_distinct, right_distinct, 0.0, 0.0, 0.0, left_null_ratio, right_null_ratio, len(df_left), len(df_right))

    intersection = left_tuples & right_tuples
    inter_size = len(intersection)
    union_size = len(left_tuples | right_tuples)

    left_cov = round(inter_size / left_distinct, 4)
    right_cov = round(inter_size / right_distinct, 4)
    jaccard = round(inter_size / union_size, 4) if union_size > 0 else 0.0

    return ValueOverlapMetrics(
        intersection_size=inter_size,
        left_distinct=left_distinct,
        right_distinct=right_distinct,
        left_coverage=left_cov,
        right_coverage=right_cov,
        jaccard_overlap=jaccard,
        left_null_ratio=left_null_ratio,
        right_null_ratio=right_null_ratio,
        left_rows=len(df_left),
        right_rows=len(df_right),
    )


def compute_pattern_compatibility(
    pattern_a: str | None,
    pattern_b: str | None,
) -> float:
    """Evaluate structural pattern compatibility (e.g. 'AAAA-DDDD' vs 'AAAA-DDDD')."""
    if not pattern_a or not pattern_b:
        return 0.50  # Neutral if pattern unknown

    if pattern_a == pattern_b:
        return 1.0

    # If same length and high token similarity
    if len(pattern_a) == len(pattern_b) and len(pattern_a) > 0:
        matches = sum(1 for c1, c2 in zip(pattern_a, pattern_b) if c1 == c2)
        return round(matches / len(pattern_a), 3)

    return 0.20


def evaluate_candidate_signals(
    source_col_name: str,
    source_profile: ColumnStructuralProfile,
    source_sem: SemanticColumnAssignment,
    target_col_name: str,
    target_profile: ColumnStructuralProfile,
    target_sem: SemanticColumnAssignment,
    overlap_metrics: ValueOverlapMetrics | None = None,
) -> CandidateEvidenceSignals:
    """Evaluate candidate evidence signals across all dimensions for single column pair."""
    sem_role_score = compute_semantic_role_compatibility(source_sem.semantic_role, target_sem.semantic_role)
    entity_type_score = compute_entity_type_compatibility(source_sem.entity_type, target_sem.entity_type)
    datatype_score = compute_physical_type_compatibility(source_profile.physical_type, target_profile.physical_type)
    lexical_score = compute_name_similarity(source_col_name, target_col_name)
    pattern_score = compute_pattern_compatibility(source_profile.dominant_pattern, target_profile.dominant_pattern)

    # Average candidate identifier scores
    cand_id_score = round((source_profile.candidate_identifier_score + target_profile.candidate_identifier_score) / 2.0, 4)

    return CandidateEvidenceSignals(
        semantic_role_score=sem_role_score,
        entity_type_score=entity_type_score,
        datatype_compatibility=datatype_score,
        lexical_similarity=lexical_score,
        pattern_compatibility=pattern_score,
        candidate_id_score=cand_id_score,
        overlap_metrics=overlap_metrics,
        is_composite=False,
    )
