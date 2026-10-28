"""Visual Selection Intelligence — Data Contracts.

Defines the DataShapeProfile, VisualSelectionDecision, and telemetry records
governing semantic visual representation choices prior to slide composition.
"""
from __future__ import annotations

from enum import Enum
from typing import Any, Optional
from pydantic import BaseModel, Field

from ..content_models import VisualStrategy, VisualCompleteness
from ..presentation_visual_spec import VisualFamily


class VisualSelectionSource(str, Enum):
    """Origin of the visual selection decision."""
    REUSE_EXISTING = "REUSE_EXISTING"
    DETERMINISTIC_SELECTION = "DETERMINISTIC_SELECTION"
    DETERMINISTIC_FALLBACK = "DETERMINISTIC_FALLBACK"


class DataShapeProfile(BaseModel):
    """Deterministic structural profile of grounded evidence and content attributes."""
    content_id: str
    is_temporal: bool = False
    is_geographic: bool = False
    is_scenario: bool = False
    is_ranked: bool = False
    is_distribution: bool = False
    is_record_detail: bool = False

    categorical_dimension_count: int = 0
    continuous_dimension_count: int = 0
    metric_count: int = 0
    category_count: int = 0
    row_count: int = 0
    column_count: int = 0

    has_benchmark: bool = False
    has_before_after: bool = False
    has_actual_target: bool = False
    has_existing_visual: bool = False

    existing_visual_type: Optional[str] = None
    existing_visual_id: Optional[str] = None
    source_surface: Optional[str] = None
    max_label_length: int = 0


class VisualSelectionDecision(BaseModel):
    """Structured semantic decision selecting WHAT visual representation to use.
    
    CRITICAL INVARIANTS:
    1. Zero physical coordinates (x, y, width, height).
    2. Zero typography measurements (pt sizes, line heights).
    3. Zero colors (hex, rgb).
    4. Zero DrawingML / SVG / HTML layout instructions.
    5. Purely semantic visual morphology selection and reuse policy.
    """
    content_id: str = Field(description="Audited content item identifier")
    selected_visual_family: VisualFamily = Field(description="Canonical visual family representation")
    selected_visual_variant: str = Field(default="standard", description="Sub-variant, e.g. horizontal, clustered")
    reuse_strategy: VisualStrategy = Field(
        default=VisualStrategy.PRESENTATION_RECOMMENDATION,
        description="Whether to reuse existing source visual or derive new visual"
    )
    visual_completeness: VisualCompleteness = Field(
        default=VisualCompleteness.COMPLETE_VISUAL,
        description="COMPLETE_VISUAL (intact, vetoes split) vs DETAIL_VISUAL (combinable/splittable)"
    )
    source_visual_id: Optional[str] = Field(default=None, description="Identifier of source visual asset if reused")
    reason_codes: list[str] = Field(default_factory=list, description="Audited structured rationale codes")
    confidence: float = Field(default=1.0, ge=0.0, le=1.0, description="Confidence in visual suitability")
    decision_source: VisualSelectionSource = Field(
        default=VisualSelectionSource.DETERMINISTIC_SELECTION,
        description="Mechanism used to reach this decision"
    )
    candidate_families: list[VisualFamily] = Field(
        default_factory=list,
        description="Valid candidate families considered during selection"
    )
    diagnostic_notes: Optional[str] = Field(default=None, description="Brief diagnostic annotation")


class VisualConsumptionTelemetry(BaseModel):
    """Telemetry tracking preservation and consumption of VisualSpec downstream."""
    content_id: str
    visual_selection_consumed: bool = False
    visual_spec_preserved: bool = False
    composition_mutation_detected: bool = False
    renderer_family_preserved: bool = False
    renderer_fallback_applied: bool = False
    original_visual: Optional[str] = None
    fallback_visual: Optional[str] = None
    fallback_reason: Optional[str] = None
