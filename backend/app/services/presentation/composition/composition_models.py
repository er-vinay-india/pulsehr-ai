"""Slide Composition Intelligence — Semantic Composition Models & Contracts.

Defines the semantic composition intent layer that sits between Story Planning
and deterministic spatial layout. Composition decisions specify WHAT dominates,
HOW content is grouped, and WHICH composition archetype applies, without specifying
raw coordinates, font sizes, colors, or DrawingML.
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Optional
from pydantic import BaseModel, Field


class CompositionArchetype(str, Enum):
    """Domain-neutral slide composition archetypes."""
    HERO_METRIC = "HERO_METRIC"
    KPI_GRID = "KPI_GRID"
    VISUAL_HERO = "VISUAL_HERO"
    VISUAL_WITH_INSIGHT = "VISUAL_WITH_INSIGHT"
    VISUAL_WITH_SUPPORTING_METRICS = "VISUAL_WITH_SUPPORTING_METRICS"
    COMPARISON = "COMPARISON"
    RANKING = "RANKING"
    DISTRIBUTION = "DISTRIBUTION"
    CORRELATION = "CORRELATION"
    SCENARIO = "SCENARIO"
    TABLE_DEEP_DIVE = "TABLE_DEEP_DIVE"
    OUTLIER_SUMMARY = "OUTLIER_SUMMARY"
    MULTI_INSIGHT = "MULTI_INSIGHT"
    EXECUTIVE_SYNTHESIS = "EXECUTIVE_SYNTHESIS"
    TITLE_COVER = "TITLE_COVER"
    CLOSING_SUMMARY = "CLOSING_SUMMARY"


class CompositionContentRole(str, Enum):
    """Semantic visual roles assigned to content items within a composition."""
    PRIMARY_VISUAL = "PRIMARY_VISUAL"
    PRIMARY_INSIGHT = "PRIMARY_INSIGHT"
    SUPPORTING_METRICS = "SUPPORTING_METRICS"
    SUPPORTING_INSIGHT = "SUPPORTING_INSIGHT"
    COMPARISON_CARD = "COMPARISON_CARD"
    REFERENCE_DATA = "REFERENCE_DATA"
    CONTEXT_SUMMARY = "CONTEXT_SUMMARY"
    CALLOUT = "CALLOUT"


class VisualPriority(str, Enum):
    """Relative visual emphasis of visual elements on the slide."""
    PRIMARY = "PRIMARY"
    SECONDARY = "SECONDARY"
    SUPPORTING = "SUPPORTING"
    REFERENCE = "REFERENCE"


class DensityIntent(str, Enum):
    """Semantic density guidance for layout planning."""
    SPARSE = "SPARSE"
    BALANCED = "BALANCED"
    DENSE = "DENSE"


class NarrativePlacementIntent(str, Enum):
    """Relative placement preference of narrative text relative to primary visuals."""
    NONE = "NONE"
    ABOVE_VISUAL = "ABOVE_VISUAL"
    BESIDE_VISUAL = "BESIDE_VISUAL"
    BELOW_VISUAL = "BELOW_VISUAL"
    CALLOUT = "CALLOUT"


class SplitIntent(str, Enum):
    """Composition recommendation regarding content expansion across physical slides."""
    NO_SPLIT = "NO_SPLIT"
    SPLIT_IF_REQUIRED = "SPLIT_IF_REQUIRED"
    PREFER_SPLIT = "PREFER_SPLIT"


class CompositionDecisionSource(str, Enum):
    """Provenance of the composition decision."""
    AI_MODEL = "AI_MODEL"
    DETERMINISTIC_FALLBACK = "DETERMINISTIC_FALLBACK"
    HEURISTIC_OVERRIDE = "HEURISTIC_OVERRIDE"


class CompositionContentGroup(BaseModel):
    """A semantic group of content items intended to be rendered together."""
    role: CompositionContentRole = Field(description="Visual grouping role")
    content_ids: list[str] = Field(default_factory=list, description="IDs of content items in this group")


class LabelSimplificationIntent(BaseModel):
    """Request for semantic label simplification without altering factual meaning."""
    source_label: str = Field(description="Original technical or verbose label")
    display_intent: str = Field(default="human_readable_short", description="Simplification style target")
    suggested_display_text: Optional[str] = Field(default=None, description="Suggested human-friendly label")


class CompositionConsumptionRecord(BaseModel):
    """Deterministic diagnostic reporting whether each composition field was consumed downstream."""
    logical_slide_id: str = Field(description="Logical slide unit identifier")
    archetype_consumed: bool = Field(default=False)
    content_grouping_consumed: bool = Field(default=False)
    visual_priority_consumed: bool = Field(default=False)
    density_consumed: bool = Field(default=False)
    narrative_placement_consumed: bool = Field(default=False)
    split_intent_consumed: bool = Field(default=False)
    label_intent_consumed: bool = Field(default=False)


# Central confidence floor for AI-generated composition decisions
DEFAULT_COMPOSITION_CONFIDENCE_THRESHOLD: float = 0.65


class CompositionFailureTelemetry(BaseModel):
    """Audited failure telemetry captured when AI composition fails and activates deterministic fallback."""
    logical_slide_id: str = Field(description="Target logical slide unit identifier")
    input_fingerprint: str = Field(default="", description="Deterministic SHA-256 fingerprint over input context")
    failure_type: str = Field(description="Category of failure: TIMEOUT, MODEL_ERROR, VALIDATION_ERROR, LOW_CONFIDENCE, UNGROUNDED_ID")
    model_response_valid: bool = Field(default=False, description="Whether raw model output parsed as valid JSON/schema")
    validation_error: Optional[str] = Field(default=None, description="Detailed error from validator or parser")
    fallback_used: bool = Field(default=True, description="Whether deterministic fallback was engaged")
    composition_archetype: Optional[str] = Field(default=None, description="Candidate archetype from model if parsed")
    confidence: Optional[float] = Field(default=None, description="Reported model confidence score if present")


class CompositionDecision(BaseModel):
    """Structured semantic composition decision for a single logical slide.
    
    CRITICAL INVARIANTS:
    1. Zero physical coordinates (x, y, width, height).
    2. Zero typography measurements (pt sizes, line heights).
    3. Zero colors (hex, rgb).
    4. Zero DrawingML / SVG / HTML instructions.
    5. References ONLY existing evidence / content IDs from the input.
    """
    logical_slide_id: str = Field(description="Logical slide unit identifier")
    composition_archetype: CompositionArchetype = Field(description="Selected composition archetype")
    content_groups: list[CompositionContentGroup] = Field(
        default_factory=list,
        description="Semantic groupings of content items for the slide"
    )
    primary_content_id: Optional[str] = Field(
        default=None,
        description="ID of the dominant visual or narrative content item"
    )
    visual_priority: VisualPriority = Field(
        default=VisualPriority.PRIMARY,
        description="Relative visual priority of the primary element"
    )
    density_intent: DensityIntent = Field(
        default=DensityIntent.BALANCED,
        description="Target density intent for the slide"
    )
    narrative_placement: NarrativePlacementIntent = Field(
        default=NarrativePlacementIntent.BESIDE_VISUAL,
        description="Relative placement preference of narrative relative to visual"
    )
    supporting_content_ids: list[str] = Field(
        default_factory=list,
        description="IDs of secondary/supporting content items"
    )
    split_intent: SplitIntent = Field(
        default=SplitIntent.SPLIT_IF_REQUIRED,
        description="Recommendation for preflight expansion"
    )
    label_intents: list[LabelSimplificationIntent] = Field(
        default_factory=list,
        description="Semantic simplification requests for technical labels"
    )
    reason_codes: list[str] = Field(
        default_factory=list,
        description="Structured codes explaining why this composition was selected"
    )
    confidence: float = Field(
        default=1.0,
        ge=0.0,
        le=1.0,
        description="Confidence score of the composition decision"
    )
    diagnostic_rationale: Optional[str] = Field(
        default=None,
        description="Brief optional diagnostic text (not parsed by deterministic engine)"
    )
    decision_source: CompositionDecisionSource = Field(
        default=CompositionDecisionSource.DETERMINISTIC_FALLBACK,
        description="Provenance of the decision"
    )
    fallback_reason: Optional[str] = Field(
        default=None,
        description="Reason deterministic fallback was used, if applicable"
    )
    consumption: Optional[CompositionConsumptionRecord] = Field(
        default=None,
        description="Deterministic diagnostic reporting whether each composition field was consumed downstream"
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Execution and tracing metadata"
    )


class DeckCompositionPlan(BaseModel):
    """Full composition plan for an entire presentation deck."""
    plan_id: str = Field(description="Plan identifier")
    deck_title: str = Field(description="Presentation title")
    slide_decisions: list[CompositionDecision] = Field(
        default_factory=list,
        description="Composition decisions for each logical slide"
    )
    ai_decisions_count: int = Field(default=0, description="Count of AI-generated decisions")
    fallback_decisions_count: int = Field(default=0, description="Count of deterministic fallback decisions")
    consumption_summary: dict[str, Any] = Field(
        default_factory=dict,
        description="Deck-wide aggregation of composition field consumption across slides"
    )
    metadata: dict[str, Any] = Field(default_factory=dict, description="Deck-level metadata")
