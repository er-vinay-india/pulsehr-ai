"""Composition Strangler Package (Phase G5.6).

Authoritative boundaries for semantically blind, 12-column responsive dashboard spatial composition.
"""
from __future__ import annotations

from .contracts import (
    ARCHETYPE_PROFILES,
    DEFAULT_PROFILE,
    ChartReadabilityProfile,
    CompositionCandidate,
    CompositionItem,
    CompositionRow,
    CompositionSection,
    ContentDensityMetrics,
    DashboardCardPlacement,
    DashboardLayoutPlan,
    DashboardRowLayout,
    DashboardSectionLayout,
    SpatialPlacement,
    VisualHeightClass,
    VisualLegibilityProfile,
    VisualSpatialProfile,
)
from .candidate_builder import (
    CompositionCandidateBuilder,
    analyze_content_density,
    get_legibility_profile,
    get_spatial_profile,
)
from .planner import (
    SpatialCompositionPlanner,
    score_adjacency_compatibility,
)
from .integrity import (
    CompositionIntegrity,
    CompositionIntegrityError,
)

# Backward-compatibility alias
SpatialCompositionOptimizer = SpatialCompositionPlanner

__all__ = [
    "ARCHETYPE_PROFILES",
    "ChartReadabilityProfile",
    "CompositionCandidate",
    "CompositionCandidateBuilder",
    "CompositionIntegrity",
    "CompositionIntegrityError",
    "CompositionItem",
    "CompositionRow",
    "CompositionSection",
    "ContentDensityMetrics",
    "DEFAULT_PROFILE",
    "DashboardCardPlacement",
    "DashboardLayoutPlan",
    "DashboardRowLayout",
    "DashboardSectionLayout",
    "SpatialCompositionOptimizer",
    "SpatialCompositionPlanner",
    "SpatialPlacement",
    "VisualHeightClass",
    "VisualLegibilityProfile",
    "VisualSpatialProfile",
    "analyze_content_density",
    "get_legibility_profile",
    "get_spatial_profile",
    "score_adjacency_compatibility",
]
