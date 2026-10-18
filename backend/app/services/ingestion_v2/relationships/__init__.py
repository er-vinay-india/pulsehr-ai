"""
HighView Ingestion V2 — Relationship Discovery & Validation Package
Stages 6 & 7: Relationship Discovery and Relationship Validation
"""

from app.services.ingestion_v2.relationships.candidate_generator import (
    CandidateGenerationStats,
    generate_candidates,
)
from app.services.ingestion_v2.relationships.candidate_rules import (
    AMBIGUITY_THRESHOLD,
    AUTO_ACCEPT_THRESHOLD,
    compute_name_similarity,
    compute_semantic_role_compatibility,
    compute_entity_type_compatibility,
    compute_physical_type_compatibility,
)
from app.services.ingestion_v2.relationships.candidate_signals import (
    CandidateEvidenceSignals,
    ValueOverlapMetrics,
    compute_value_overlap_composite,
    compute_value_overlap_single,
    evaluate_candidate_signals,
)
from app.services.ingestion_v2.relationships.relationship_validator import (
    compute_expected_fanout,
    validate_candidates,
)

__all__ = [
    "generate_candidates",
    "validate_candidates",
    "CandidateGenerationStats",
    "compute_name_similarity",
    "compute_semantic_role_compatibility",
    "compute_entity_type_compatibility",
    "compute_physical_type_compatibility",
    "compute_value_overlap_single",
    "compute_value_overlap_composite",
    "compute_expected_fanout",
    "evaluate_candidate_signals",
    "CandidateEvidenceSignals",
    "ValueOverlapMetrics",
    "AUTO_ACCEPT_THRESHOLD",
    "AMBIGUITY_THRESHOLD",
]
