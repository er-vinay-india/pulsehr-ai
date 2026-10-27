"""Slide Composition Intelligence Module.

Provides semantic composition intelligence between Story Planning and deterministic spatial layout.
"""

from .composition_engine import (
    COMPOSITION_TO_LAYOUT_FAMILY,
    COMPOSITION_TO_PREFERRED_ARCHETYPE,
    SlideCompositionEngine,
)
from .composition_models import (
    CompositionArchetype,
    CompositionConsumptionRecord,
    CompositionContentGroup,
    CompositionContentRole,
    CompositionDecision,
    CompositionDecisionSource,
    DeckCompositionPlan,
    DensityIntent,
    LabelSimplificationIntent,
    NarrativePlacementIntent,
    SplitIntent,
    VisualPriority,
)
from .composition_provider import (
    AICompositionProvider,
    CompositionProvider,
    DeterministicCompositionProvider,
)
from .composition_validator import CompositionDecisionValidator, CompositionValidationError
from .label_resolver import GovernedLabelResolver

__all__ = [
    "SlideCompositionEngine",
    "COMPOSITION_TO_LAYOUT_FAMILY",
    "COMPOSITION_TO_PREFERRED_ARCHETYPE",
    "CompositionArchetype",
    "CompositionConsumptionRecord",
    "CompositionContentGroup",
    "CompositionContentRole",
    "CompositionDecision",
    "CompositionDecisionSource",
    "DeckCompositionPlan",
    "DensityIntent",
    "GovernedLabelResolver",
    "LabelSimplificationIntent",
    "NarrativePlacementIntent",
    "SplitIntent",
    "VisualPriority",
    "CompositionProvider",
    "DeterministicCompositionProvider",
    "AICompositionProvider",
    "CompositionDecisionValidator",
    "CompositionValidationError",
]
