"""
HighView Semantic Data Refinery — Phase SDR-2
Grain Candidate Pruning Subsystem
"""

from __future__ import annotations

from typing import Sequence

from app.services.ingestion_v2.contracts.semantics import SemanticColumnRole
from app.services.sdr.contracts.policies import GrainConfidencePolicy
from app.services.sdr.contracts.profiles import (
    SemanticColumnProfile,
    SemanticDtype,
)

# System row identity names that must NEVER define business grain
SYSTEM_ROW_ID_TOKENS: set[str] = {
    "row_number", "row_num", "rownum", "row_id", "rowid", "line_id",
    "_id", "index", "idx", "seq", "sequence_number", "surrogate_key",
}


def is_system_row_identifier(profile: SemanticColumnProfile) -> bool:
    """Detects technical row counters and surrogate row identifiers."""
    name_clean = profile.source_name.lower().replace("-", "_").strip("_")
    if name_clean in SYSTEM_ROW_ID_TOKENS or profile.canonical_name.lower() in SYSTEM_ROW_ID_TOKENS:
        return True
    return False


def is_measure_column(profile: SemanticColumnProfile) -> bool:
    """
    CRITICAL NEGATIVE GATE:
    Measures (salary, revenue, headcount, score, rate) must NEVER become grain by accident,
    even if their continuous float values happen to be 100% unique in a sample.
    """
    if profile.semantic_role == SemanticColumnRole.MEASURE:
        return True
    if profile.measure_class is not None:
        return True
    if profile.semantic_dtype in (
        SemanticDtype.CURRENCY_AMOUNT,
        SemanticDtype.PERCENTAGE_RATE,
        SemanticDtype.DECIMAL_NUMBER,
    ) and any(
        t in profile.source_name.lower()
        for t in ("salary", "revenue", "cost", "price", "amount", "spend", "rate", "pct", "score", "headcount", "hours")
    ):
        return True
    return False


def prune_grain_candidates(
    profiles: Sequence[SemanticColumnProfile],
    policy: GrainConfidencePolicy,
) -> list[SemanticColumnProfile]:
    """
    Filters column profiles down to viable grain determinant candidates.
    Applies strict negative gates to prevent combinatorial explosion and false grain promotions.
    """
    eligible: list[SemanticColumnProfile] = []

    for p in profiles:
        # Gate 1: Exclude measures unconditionally
        if is_measure_column(p):
            continue

        # Gate 2: Exclude system row counters
        if is_system_row_identifier(p):
            continue

        # Gate 3: Exclude free text and technical metadata
        if p.semantic_role in (SemanticColumnRole.FREE_TEXT, SemanticColumnRole.TECHNICAL_METADATA):
            continue

        # Gate 4: Exclude high-null columns
        if p.features.null_ratio > policy.max_null_ratio_for_grain:
            continue

        # Gate 5: Exclude constant / empty columns
        if p.features.distinct_count <= 1:
            continue

        # Gate 6: Must have plausible identity, dimensional, or temporal role
        is_candidate_role = p.semantic_role in (
            SemanticColumnRole.ENTITY_IDENTIFIER,
            SemanticColumnRole.DIMENSION,
            SemanticColumnRole.CATEGORY,
            SemanticColumnRole.LOCATION,
            SemanticColumnRole.TIME,
            SemanticColumnRole.ATTRIBUTE,
        ) or p.semantic_dtype in (
            SemanticDtype.IDENTIFIER_CODE,
            SemanticDtype.DATE,
            SemanticDtype.DATETIME,
            SemanticDtype.CATEGORICAL_CODE,
            SemanticDtype.GEOGRAPHIC_LOCATION,
        )

        if is_candidate_role:
            eligible.append(p)

    return eligible
