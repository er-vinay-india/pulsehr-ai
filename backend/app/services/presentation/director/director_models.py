from __future__ import annotations

import re
from enum import Enum
from typing import Any
from pydantic import BaseModel, Field


class SlideCountMode(str, Enum):
    """Modes governing presentation slide count allocation."""
    ADAPTIVE = "ADAPTIVE"
    FIXED = "FIXED"
    MINIMUM = "MINIMUM"
    MAXIMUM = "MAXIMUM"
    RANGE = "RANGE"


class SlideCountConstraint(BaseModel):
    """Enforces dynamic or bounded presentation slide count constraints."""
    mode: SlideCountMode = SlideCountMode.ADAPTIVE
    target: int | None = None
    min_slides: int | None = None
    max_slides: int | None = None

    @classmethod
    def from_inputs(
        cls,
        instructions: str = "",
        target_length: int | None = None,
        default_mode: str = "ADAPTIVE"
    ) -> SlideCountConstraint:
        """Parses natural language instructions and explicit target settings to determine slide constraint."""
        text = instructions.lower() if instructions else ""

        # Check for range: e.g. "8-12 slides", "between 8 and 12 slides", "8 to 12 slides"
        range_match = re.search(r'(?:between\s+)?(\d+)\s*(?:-|to|and)\s*(\d+)\s*slides?', text)
        if range_match:
            low, high = int(range_match.group(1)), int(range_match.group(2))
            if low > high:
                low, high = high, low
            return cls(mode=SlideCountMode.RANGE, min_slides=low, max_slides=high, target=low)

        # Check for exact / fixed: e.g. "exactly 5 slides", "5 slides", "limit to 5 slides"
        exact_match = re.search(r'(?:exactly|precisely|strictly)\s+(\d+)\s*slides?', text)
        if exact_match:
            n = int(exact_match.group(1))
            return cls(mode=SlideCountMode.FIXED, target=n, min_slides=n, max_slides=n)

        # Check for minimum: e.g. "at least 10 slides", "minimum 10 slides", ">= 10 slides"
        min_match = re.search(r'(?:at\s+least|minimum|min|no\s+less\s+than|>=\s*)\s*(\d+)\s*slides?', text)
        if min_match:
            n = int(min_match.group(1))
            return cls(mode=SlideCountMode.MINIMUM, min_slides=n, target=n)

        # Check for maximum: e.g. "at most 8 slides", "maximum 8 slides", "under 8 slides", "<= 8 slides"
        max_match = re.search(r'(?:at\s+most|maximum|max|no\s+more\s+than|under|up\s+to|<=\s*)\s*(\d+)\s*slides?', text)
        if max_match:
            n = int(max_match.group(1))
            return cls(mode=SlideCountMode.MAXIMUM, max_slides=n, target=n)


        # If user explicitly passed target_length parameter
        if target_length and target_length > 0:
            # If default_mode is FIXED or if target_length was explicitly set
            if default_mode.upper() == "FIXED":
                return cls(mode=SlideCountMode.FIXED, target=target_length, min_slides=target_length, max_slides=target_length)
            # By default, target_length provides a baseline target but in ADAPTIVE mode it adapts around it
            return cls(mode=SlideCountMode.ADAPTIVE, target=target_length, min_slides=max(4, target_length - 4), max_slides=target_length + 6)

        return cls(mode=SlideCountMode.ADAPTIVE, min_slides=4, max_slides=25)

    def is_satisfied(self, count: int) -> bool:
        """Evaluates whether an actual slide count satisfies this constraint."""
        if self.mode == SlideCountMode.FIXED:
            return self.target is None or count == self.target
        elif self.mode == SlideCountMode.MINIMUM:
            return self.min_slides is None or count >= self.min_slides
        elif self.mode == SlideCountMode.MAXIMUM:
            return self.max_slides is None or count <= self.max_slides
        elif self.mode == SlideCountMode.RANGE:
            min_ok = self.min_slides is None or count >= self.min_slides
            max_ok = self.max_slides is None or count <= self.max_slides
            return min_ok and max_ok
        return True  # ADAPTIVE is always satisfied


class AudienceSeniority(str, Enum):
    C_SUITE = "C_SUITE"
    VP_DIRECTOR = "VP_DIRECTOR"
    MANAGEMENT = "MANAGEMENT"
    TECHNICAL_OPERATIONAL = "TECHNICAL_OPERATIONAL"
    GENERAL = "GENERAL"


class DeliveryMode(str, Enum):
    LIVE_EXECUTIVE_PITCH = "LIVE_EXECUTIVE_PITCH"
    BOARD_REVIEW = "BOARD_REVIEW"
    STANDALONE_READ = "STANDALONE_READ"
    TECHNICAL_WORKSHOP = "TECHNICAL_WORKSHOP"
    STATUS_UPDATE = "STATUS_UPDATE"


class NarrativeArcType(str, Enum):
    PROBLEM_SOLUTION = "PROBLEM_SOLUTION"
    EXECUTIVE_BRIEFING = "EXECUTIVE_BRIEFING"
    DIAGNOSTIC_DEEP_DIVE = "DIAGNOSTIC_DEEP_DIVE"
    STRATEGIC_RECOMMENDATION = "STRATEGIC_RECOMMENDATION"
    COMPARATIVE_EVALUATION = "COMPARATIVE_EVALUATION"
    PROGRESS_UPDATE = "PROGRESS_UPDATE"
    TECHNICAL_ARCHITECTURE = "TECHNICAL_ARCHITECTURE"


class InformationSourceType(str, Enum):
    CURRENT_EVIDENCE = "CURRENT_EVIDENCE"
    HISTORICAL_MEMORY = "HISTORICAL_MEMORY"
    USER_PROMPT = "USER_PROMPT"
    DATASET_PROFILE = "DATASET_PROFILE"


class InformationDestination(str, Enum):
    MAIN_DECK = "MAIN_DECK"
    APPENDIX = "APPENDIX"
    SPEAKER_NOTES = "SPEAKER_NOTES"
    OMIT = "OMIT"


class InformationUnit(BaseModel):
    """An atomic verified piece of information evaluated during planning."""
    id: str
    title: str
    statement: str
    evidence_id: str | None = None
    source_type: InformationSourceType = InformationSourceType.CURRENT_EVIDENCE
    source_ref: str | None = None
    confidence: float = 1.0
    priority: str = "HIGH"  # HIGH | MEDIUM | LOW
    destination: InformationDestination = InformationDestination.MAIN_DECK
    rationale: str = ""
    metrics: dict[str, Any] = Field(default_factory=dict)


class PresentationIntent(BaseModel):
    """High-level semantic framing extracted from user request and business context."""
    domain: str
    purpose: str
    primary_goal: str
    target_audience: str
    audience_seniority: AudienceSeniority = AudienceSeniority.C_SUITE
    technical_depth: str = "balanced"  # high_level | balanced | deep_dive
    delivery_mode: DeliveryMode = DeliveryMode.LIVE_EXECUTIVE_PITCH
    key_takeaways: list[str] = Field(default_factory=list)
    key_questions_to_answer: list[str] = Field(default_factory=list)


class PresentationSection(BaseModel):
    """Logical thematic section of the deck grouping one or more slides."""
    section_id: str
    title: str
    purpose: str
    narrative_function: str = ""
    target_slide_count: int = 1


class NarrativeStrategy(BaseModel):
    """Narrative structure, tone, and pacing governing deck progression."""
    arc_type: NarrativeArcType = NarrativeArcType.EXECUTIVE_BRIEFING
    tone: str = "decisive_objective"
    pacing: str = "concise"
    executive_thesis: str = ""
    sections: list[PresentationSection] = Field(default_factory=list)


class VisualIntent(BaseModel):
    """Specifies the visual component, chart type, or data structure for a slide."""
    visual_type: str = "none"  # none | line_chart | bar_chart | donut_chart | rel_chart | table | kpi_grid | model_hook | action_plan | raci_matrix
    layout_recommendation: str = "title_hero"
    metrics_to_display: list[dict[str, Any]] = Field(default_factory=list)
    comparison_focus: str | None = None
    model_hook: str | None = None


class PresentationBrief(BaseModel):
    """Structured, validated presentation brief defining audience, decision, and constraints."""
    objective: str = "Executive Leadership Review"
    audience: str = "C-Suite & Operations Leadership"
    decision_requested: str = ""
    main_takeaway: str = ""
    presentation_time_minutes: int = 15
    deliverable: str = "pptx"  # "pptx" | "pdf" | "both"
    content_preferences: dict[str, list[str]] = Field(default_factory=dict)
    citation_requirement: str = "standard"  # "standard" | "strict" | "footnote_only" | "none"
    motion_preference: str = "none"  # "none" | "subtle" | "full"
    success_criterion: str = ""
    is_inferred: bool = True

    def build_success_criterion(self) -> str:
        """Computes: 'After viewing this deck, the audience should understand X and decide or do Y.'"""
        x_val = self.main_takeaway or f"operational baseline and performance metrics for {self.objective}"
        y_val = self.decision_requested or "align on operational priority initiatives"
        return f"After viewing this deck, the audience should understand {x_val} and decide or do {y_val}."


class SlidePlan(BaseModel):
    """Specification of an individual slide planned by the Presentation Director."""
    slide_id: str
    section_id: str
    sequence_number: int
    layout: str
    headline: str
    subtitle: str = ""
    key_message: str = ""
    primary_message: str = ""
    minimum_supporting_evidence: list[str] = Field(default_factory=list)
    implication_for_audience: str = ""
    transition_to_next: str = ""
    bullet_points: list[str] = Field(default_factory=list)
    visual_intent: VisualIntent = Field(default_factory=VisualIntent)
    information_unit_ids: list[str] = Field(default_factory=list)
    evidence_ids: list[str] = Field(default_factory=list)
    historical_context_refs: list[str] = Field(default_factory=list)
    speaker_notes: str = ""


class PlanningValidationResult(BaseModel):
    """Audit of planning consistency, duplicate concepts, and user question answering."""
    is_valid: bool = True
    duplicate_concepts_detected: list[str] = Field(default_factory=list)
    unanswered_user_questions: list[str] = Field(default_factory=list)
    unsupported_claims: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)


class PresentationPlanningContext(BaseModel):
    """Bounded, unified input package provided to the Presentation Director."""
    domain: str
    objective: str
    audience: str
    instructions: str = ""
    dataset_label: str = ""
    total_records: int = 0
    completeness_pct: float = 100.0
    baseline_benchmark: str = ""
    dispersion_metric: str = ""
    reporting_period: str = ""
    is_partial_year: bool = False
    brief: PresentationBrief | None = None
    dataset_profiles: list[dict[str, Any]] = Field(default_factory=list)
    current_evidence: list[dict[str, Any]] = Field(default_factory=list)
    historical_context: dict[str, Any] = Field(default_factory=dict)
    available_charts: dict[str, bool] = Field(default_factory=dict)
    industrial_models: dict[str, Any] = Field(default_factory=dict)
    slide_count_constraint: SlideCountConstraint = Field(default_factory=SlideCountConstraint)
    workspace_id: str | None = None
    theme_id: str = "executive_dark"
    snapshot_hash: str = ""


class PresentationPlanSpec(BaseModel):
    """The canonical planning artifact produced by the Qwen Presentation Director (Phase 2)."""
    spec_version: str = "2.0"
    deck_title: str
    intent: PresentationIntent
    narrative_strategy: NarrativeStrategy
    information_units: list[InformationUnit] = Field(default_factory=list)
    sections: list[PresentationSection] = Field(default_factory=list)
    slides: list[SlidePlan] = Field(default_factory=list)
    slide_count: int = 0
    evidence_usage: list[str] = Field(default_factory=list)
    retrieved_context_usage: list[dict[str, Any]] = Field(default_factory=list)
    planning_validation: PlanningValidationResult = Field(default_factory=PlanningValidationResult)
    metadata: dict[str, Any] = Field(default_factory=dict)
