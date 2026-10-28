"""Visual Selection Intelligence Module.

Provides deterministic data profiling, candidate generation, visual selection,
and canonical PresentationVisualSpec synthesis before StoryPlanner and Granite Composition.
"""
from .selection_models import (
    DataShapeProfile,
    VisualConsumptionTelemetry,
    VisualSelectionDecision,
    VisualSelectionSource,
)
from .normalization import normalize_to_visual_family, RAW_TO_VISUAL_FAMILY
from .candidate_generator import VisualCandidateGenerator
from .validator import VisualSelectionValidator, VisualSelectionValidationError
from .selection_provider import DeterministicVisualSelectionProvider
from .spec_builder import PresentationVisualSpecBuilder
from .visual_intelligence_service import VisualSelectionIntelligence

__all__ = [
    "DataShapeProfile",
    "VisualConsumptionTelemetry",
    "VisualSelectionDecision",
    "VisualSelectionSource",
    "normalize_to_visual_family",
    "RAW_TO_VISUAL_FAMILY",
    "VisualCandidateGenerator",
    "VisualSelectionValidator",
    "VisualSelectionValidationError",
    "DeterministicVisualSelectionProvider",
    "PresentationVisualSpecBuilder",
    "VisualSelectionIntelligence",
]
