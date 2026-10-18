"""
HighView Ingestion V2 — Analytics Helpers
Stage 8: Analytical EDA-B
Unified accessors for column profiles, semantic models, and types across contract representations.
"""

from __future__ import annotations

from typing import Any
from app.services.ingestion_v2.contracts.profiling import ColumnStructuralProfile
from app.services.ingestion_v2.contracts.semantics import (
    SemanticColumnAssignment,
    SemanticColumnRole,
    SemanticConcept,
)


def get_column_name(col_profile: ColumnStructuralProfile | Any) -> str:
    return getattr(col_profile, "column_name", None) or getattr(col_profile, "name", "")


def get_column_type(col_profile: ColumnStructuralProfile | Any) -> str:
    raw_type = getattr(col_profile, "physical_type", None) or getattr(col_profile, "inferred_type", "STRING")
    return str(raw_type).upper()


def get_column_role(assignment: SemanticColumnAssignment | Any | None) -> SemanticColumnRole:
    if assignment is None:
        return SemanticColumnRole.ATTRIBUTE
    role = getattr(assignment, "role", None) or getattr(assignment, "semantic_role", None)
    if isinstance(role, SemanticColumnRole):
        return role
    if role:
        try:
            return SemanticColumnRole(str(role).upper())
        except ValueError:
            pass
    return SemanticColumnRole.ATTRIBUTE


def get_column_concept(assignment: SemanticColumnAssignment | Any | None) -> SemanticConcept:
    if assignment is None:
        return SemanticConcept.UNKNOWN
    concept = getattr(assignment, "semantic_concept", None)
    if isinstance(concept, SemanticConcept):
        return concept
    if concept:
        try:
            return SemanticConcept(str(concept).upper())
        except ValueError:
            pass
    return SemanticConcept.UNKNOWN
