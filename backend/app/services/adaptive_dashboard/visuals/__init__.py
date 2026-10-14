"""Visual Specification and Archetype Domain (Phase G5.4).

Provides:
- VisualInput: Strictly typed input for visual generation.
- VisualSpec: Theme-agnostic visual specification with topic identity.
- VisualCapabilityRegistry: Governed catalog of chart archetypes and morphologies.
- VisualSpecFactory: Deterministic factory creating validated visual specs.
- VisualSemanticAlignmentIntegrity: Cross-domain, grain, and theme-absence guards.
- VisualSemanticsMutationIntegrity: Immutability guard against composition mutations.
"""
from __future__ import annotations

from .contracts import (
    ChartFamily,
    VisualAxis,
    VisualInput,
    VisualMorphology,
    VisualReferenceLine,
    VisualSeries,
    VisualSpec,
)
from .capability_registry import VisualCapabilityRegistry
from .integrity import (
    VisualIntegrityError,
    VisualSemanticAlignmentIntegrity,
    VisualSemanticsMutationIntegrity,
)
from .spec_factory import VisualSpecFactory

__all__ = [
    "ChartFamily",
    "VisualAxis",
    "VisualCapabilityRegistry",
    "VisualInput",
    "VisualIntegrityError",
    "VisualMorphology",
    "VisualReferenceLine",
    "VisualSemanticAlignmentIntegrity",
    "VisualSemanticsMutationIntegrity",
    "VisualSeries",
    "VisualSpec",
    "VisualSpecFactory",
]
