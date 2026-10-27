"""Logical Story Planning & Semantic SlideTag Models (PPT-L2).

Establishes the non-negotiable architectural boundaries:
1. Structural Story Role != Semantic Topic:
   Logical slide plans cleanly separate:
     - structural_role: Generic narrative storytelling role (e.g. GEOGRAPHIC_ANALYSIS, HERO_ANALYSIS, DIAGNOSTIC_ANALYSIS).
     - semantic_topic: Extensible, domain-derived business topic (e.g. POPULATION_DENSITY, POPULATION_GROWTH, CUSTOMER_RETENTION).
   Zero enum bloat required for new datasets or domains.
2. Stable Logical Semantic Identity:
   Logical slide identity (logical_slide_id) derives directly from the meaningful semantic topic
   (e.g. POPULATION_DENSITY), never from generic structural roles like 'GEOGRAPHIC_DISTRIBUTION-1'.
   Physical slide IDs and physical layouts remain strictly for PPT-L3+.
3. Content Truth != Presentation Narrative:
   StoryPlanner selects, groups, orders, summarizes, and frames audited content items,
   but CANNOT mutate facts, units, grain, denominators, or invent facts.
4. Schema-Bound Content Binding:
   Every bound item references an audited content_id in PresentationContentPackage.
   Hallucinated or unknown IDs are strictly rejected.
5. Complete Content Accounting:
   Every item in the PresentationContentPackage is either bound to a logical slide
   or cataloged in the excluded_content ledger with an explicit ExclusionReason.
6. UserVisibleContentPolicy Enforcement:
   User-visible presentation fields omit internal pipeline jargon (SDR, JoinPlan, EVID-...)
   in normal business decks, while faithfully preserving requested terms in technical decks.
"""

from __future__ import annotations

from enum import Enum
import hashlib
import json
import re
from typing import Any
from pydantic import BaseModel, Field, model_validator

from app.services.presentation.content_models import (
    ContentKind,
    ContentRole,
    PresentationContentItem,
    PresentationContentPackage,
    UserVisibleContentPolicy,
    VisualCompleteness,
    VisualStrategy,
)


class StructuralRole(str, Enum):
    """Categorical semantic classification of a logical narrative slide's structural role.
    
    Defines the executive purpose/archetype in the storytelling arc, independent of domain topic.
    """
    TITLE = "TITLE"
    AGENDA = "AGENDA"
    EXECUTIVE_SUMMARY = "EXECUTIVE_SUMMARY"
    STRATEGIC_KPIS = "STRATEGIC_KPIS"
    HERO_ANALYSIS = "HERO_ANALYSIS"
    DIAGNOSTIC_ANALYSIS = "DIAGNOSTIC_ANALYSIS"
    GEOGRAPHIC_ANALYSIS = "GEOGRAPHIC_ANALYSIS"
    CORRELATION_ANALYSIS = "CORRELATION_ANALYSIS"
    COHORT_ANALYSIS = "COHORT_ANALYSIS"
    DEEP_DIVE = "DEEP_DIVE"
    ACTION_PLAN = "ACTION_PLAN"
    CLOSING = "CLOSING"
    THANK_YOU = "THANK_YOU"

    # Backwards compatibility aliases for PPT-L1 / early PPT-L2 tags
    GEOGRAPHIC_DISTRIBUTION = "GEOGRAPHIC_ANALYSIS"
    RELATIONAL_CORRELATION = "CORRELATION_ANALYSIS"
    COHORT_VARIANCE = "COHORT_ANALYSIS"
    DEEP_DIVE_EXPLORATION = "DEEP_DIVE"


# Aliases for backwards compatibility
SlideTag = StructuralRole
LogicalSlideTag = StructuralRole


class ContentBindingRole(str, Enum):
    """The role a bound content item plays within a logical slide unit."""
    PRIMARY = "PRIMARY"          # Main focal visual or hero message
    SUPPORTING = "SUPPORTING"    # Contextual table, secondary metric, or insight
    OPTIONAL = "OPTIONAL"        # Supplementary detail that preflight may overflow/omit


class ContentBinding(BaseModel):
    """Binds an audited PresentationContentItem by ID to a LogicalSlidePlan."""
    content_id: str = Field(description="Audited ID matching PresentationContentItem.content_id")
    binding_role: ContentBindingRole = Field(default=ContentBindingRole.PRIMARY)
    notes: str | None = Field(default=None, description="Narrative purpose of this binding")
    visual_id: str | None = Field(default=None, description="Bound visual identifier")
    visual_strategy: VisualStrategy = Field(default=VisualStrategy.PRESENTATION_RECOMMENDATION)
    visual_completeness: VisualCompleteness = Field(default=VisualCompleteness.COMPLETE_VISUAL)
    visual_type: str | None = Field(default=None, description="Bound visual type / chart family")
    visual_spec: dict[str, Any] | None = Field(default=None, description="Bound visual specification")
    source_surface: str | None = Field(default=None, description="Originating surface (e.g. dashboard, data_explorer)")


class ExclusionReason(str, Enum):
    """Strict categorical rationale for why candidate content was not included in the deck."""
    REDUNDANT = "REDUNDANT"
    LOW_RELEVANCE_FOR_OBJECTIVE = "LOW_RELEVANCE_FOR_OBJECTIVE"
    CAPACITY_LIMIT = "CAPACITY_LIMIT"
    OFF_OBJECTIVE = "OFF_OBJECTIVE"
    SUPERSEDED_BY_HERO = "SUPERSEDED_BY_HERO"
    
    # Backwards compatibility alias for typo fix
    SUPERCEDED_BY_HERO = "SUPERSEDED_BY_HERO"


class ExcludedContentItem(BaseModel):
    """Audited ledger entry for unused content items from the PresentationContentPackage."""
    content_id: str = Field(description="Audited ID matching PresentationContentItem.content_id")
    reason: ExclusionReason = Field(description="Categorical reason for exclusion")
    notes: str | None = Field(default=None, description="Detailed explanation for narrative audit")
    importance_score: float | None = Field(default=None, description="Original importance score from ranker")


def normalize_semantic_topic(topic: str) -> str:
    """Normalizes an arbitrary domain topic category into a canonical semantic identifier.
    
    Examples:
      'Population Density' -> 'POPULATION_DENSITY'
      'Customer Retention' -> 'CUSTOMER_RETENTION'
      'attendance_compliance' -> 'ATTENDANCE_COMPLIANCE'
    """
    if not topic or not topic.strip():
        return "GENERAL_TOPIC"
    cleaned = re.sub(r"[^\w\s-]", "", topic.strip())
    slug = re.sub(r"[\s-]+", "_", cleaned).upper()
    return slug or "GENERAL_TOPIC"


class LogicalSlidePlan(BaseModel):
    """A logical narrative chapter or story unit.
    
    CRITICAL INVARIANTS:
    1. A LogicalSlidePlan is NOT a physical slide.
    2. structural_role represents the generic storytelling archetype (e.g. GEOGRAPHIC_ANALYSIS).
    3. semantic_topic represents the extensible business topic (e.g. POPULATION_DENSITY).
    4. logical_slide_id is derived from semantic_topic, NOT generic role numbers.
    5. Zero physical coordinates, zero physical slide numbers, zero zone layouts.
    """
    logical_slide_id: str = Field(description="Semantic logical identity derived from topic, e.g. POPULATION_DENSITY")
    structural_role: StructuralRole = Field(description="Narrative structural role (e.g. GEOGRAPHIC_ANALYSIS)")
    semantic_topic: str = Field(description="Extensible business topic (e.g. POPULATION_DENSITY)")
    section_name: str = Field(description="High-level presentation section, e.g. Thematic Analysis")
    purpose: str = Field(description="Executive objective or question this slide unit answers")
    headline: str = Field(description="Action-oriented executive headline")
    takeaway: str = Field(default="", description="Key strategic takeaway")
    content_bindings: list[ContentBinding] = Field(default_factory=list, description="Bound content IDs")
    preferred_archetype: str | None = Field(default=None, description="Suggested visual archetype (e.g. CHART_WITH_INSIGHT)")
    allow_split: bool = Field(default=True, description="Whether preflight is permitted to split this unit")
    logical_order: int = Field(default=0, description="Logical story order (1-indexed sequence)")
    visual_id: str | None = Field(default=None, description="Primary visual identity for this logical slide")
    visual_strategy: VisualStrategy = Field(default=VisualStrategy.PRESENTATION_RECOMMENDATION)
    visual_completeness: VisualCompleteness = Field(default=VisualCompleteness.COMPLETE_VISUAL)
    visual_type: str | None = Field(default=None, description="Primary visual type / chart family")
    visual_spec: dict[str, Any] | None = Field(default=None, description="Primary visual specification")
    source_surface: str | None = Field(default=None, description="Primary visual surface")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Arbitrary metadata such as cover framing")

    # Backwards compatibility property for code expecting .tag
    @property
    def tag(self) -> StructuralRole:
        return self.structural_role

    @model_validator(mode="before")
    @classmethod
    def _backwards_compatible_tag(cls, data: Any) -> Any:
        if isinstance(data, dict):
            # If tag was supplied instead of structural_role
            if "tag" in data and "structural_role" not in data:
                data["structural_role"] = data["tag"]
            # If semantic_topic was not supplied, infer from tag or headline
            if "semantic_topic" not in data:
                inferred = data.get("topic_category") or data.get("headline") or str(data.get("structural_role") or "TOPIC")
                data["semantic_topic"] = normalize_semantic_topic(inferred)
            # If logical_slide_id was not supplied, infer from semantic_topic
            if "logical_slide_id" not in data:
                data["logical_slide_id"] = data["semantic_topic"]
        return data


class DeckStoryPlan(BaseModel):
    """Governed presentation narrative plan produced by StoryPlanner (PPT-L2)."""
    plan_id: str = Field(description="Unique deterministic plan ID, e.g. PLAN-...")
    deck_title: str = Field(description="Overarching presentation title")
    deck_subtitle: str = Field(description="Presentation subtitle or briefing context")
    executive_thesis: str = Field(description="Core strategic narrative thesis")
    sections: list[str] = Field(default_factory=list, description="Ordered presentation section headings")
    logical_slides: list[LogicalSlidePlan] = Field(default_factory=list, description="Ordered logical slide units")
    excluded_content: list[ExcludedContentItem] = Field(default_factory=list, description="Complete ledger of unselected content")
    target_audience: str = Field(default="Stakeholders")
    user_objective: str = Field(default="")
    story_fingerprint: str = Field(default="", description="Deterministic SHA-256 fingerprint over story structure")
    metadata: dict[str, Any] = Field(default_factory=dict)

    def compute_story_fingerprint(self) -> str:
        """Computes a deterministic SHA-256 fingerprint over canonical story plan properties."""
        canonical_slides = []
        for s in sorted(self.logical_slides, key=lambda x: (x.logical_order, x.logical_slide_id, x.structural_role.value)):
            sorted_bindings = sorted(s.content_bindings, key=lambda b: (b.content_id, b.binding_role.value))
            canonical_slides.append({
                "logical_slide_id": s.logical_slide_id,
                "structural_role": s.structural_role.value,
                "semantic_topic": s.semantic_topic,
                "section": s.section_name,
                "headline": s.headline,
                "purpose": s.purpose,
                "takeaway": s.takeaway,
                "archetype": s.preferred_archetype or "",
                "allow_split": s.allow_split,
                "visual_id": s.visual_id or "",
                "visual_strategy": s.visual_strategy.value if hasattr(s.visual_strategy, "value") else str(s.visual_strategy or ""),
                "visual_type": s.visual_type or "",
                "bindings": [
                    {
                        "id": b.content_id,
                        "role": b.binding_role.value,
                        "visual_id": b.visual_id or "",
                        "visual_strategy": b.visual_strategy.value if hasattr(b.visual_strategy, "value") else str(b.visual_strategy or ""),
                        "visual_type": b.visual_type or "",
                    }
                    for b in sorted_bindings
                ]
            })

        canonical_exclusions = [
            {"id": e.content_id, "reason": e.reason.value}
            for e in sorted(self.excluded_content, key=lambda x: x.content_id)
        ]

        payload = {
            "title": self.deck_title,
            "subtitle": self.deck_subtitle,
            "thesis": self.executive_thesis,
            "sections": list(self.sections),
            "audience": self.target_audience,
            "objective": self.user_objective,
            "slides": canonical_slides,
            "exclusions": canonical_exclusions,
        }
        encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()


# ==============================================================================
# VALIDATION & INVARIANT AUDIT
# ==============================================================================

class StoryPlanValidationError(Exception):
    """Raised when a DeckStoryPlan violates architectural invariants."""
    pass


class UnknownContentIdError(StoryPlanValidationError):
    """Raised when a story plan references content IDs not present in the content package."""
    pass


class UnaccountedContentError(StoryPlanValidationError):
    """Raised when an item in the content package is neither bound nor listed in excluded_content."""
    pass


class PhysicalLayoutLeakageError(StoryPlanValidationError):
    """Raised if physical geometry or physical slide layout leaks into PPT-L2."""
    pass


class GovernanceLeakageError(StoryPlanValidationError):
    """Raised when internal governance jargon leaks into normal business presentations."""
    pass


class StoryPlanValidator:
    """Validates DeckStoryPlan compliance against PresentationContentPackage and PPT-L2 invariants."""

    FORBIDDEN_PHYSICAL_FIELDS = {
        "x", "y", "width", "height", "left", "top",
        "slide_number", "page_number", "zones", "layers",
        "bounding_box", "coordinate_space", "pt_x", "pt_y",
        "canvas_width", "canvas_height", "font_size_pt", "emu",
        "layout_template", "physical_slide_id", "physical_slide_number"
    }

    FORBIDDEN_GOVERNANCE_PATTERNS = [
        r"\bSDR\b",
        r"\bSDR-\d+\b",
        r"\bJoinPlan\b",
        r"\bJoinGraph\b",
        r"\bEVID-[A-Za-z0-9_\-]+\b",
        r"\b[a-f0-9]{32,64}\b",  # Checksums / hashes
        r"\bcontrol\s+plane\b",
        r"\borchestrator\s+task\b",
    ]

    @classmethod
    def validate(
        cls,
        plan: DeckStoryPlan,
        package: PresentationContentPackage,
        strict_exclusions: bool = True
    ) -> None:
        """Validates all architectural invariants of the DeckStoryPlan.
        
        Args:
            plan: The DeckStoryPlan to validate.
            package: The source PresentationContentPackage.
            strict_exclusions: If True, requires every item in package.items to be either
                              bound to a slide or recorded in plan.excluded_content.
        """
        # 1. Collect all known valid content IDs from package
        known_item_ids = {it.content_id: it for it in package.items}
        known_kpi_ids = {it.content_id: it for it in package.global_kpis}
        all_known_ids = set(known_item_ids.keys()) | set(known_kpi_ids.keys())

        # 2. Check each logical slide
        bound_ids: set[str] = set()
        seen_logical_ids: set[str] = set()

        for idx, slide in enumerate(plan.logical_slides):
            # Check structural role validity
            if not isinstance(slide.structural_role, StructuralRole):
                raise StoryPlanValidationError(
                    f"Slide {idx} has invalid structural_role type: {type(slide.structural_role)} (value: {slide.structural_role})"
                )

            # Check semantic topic presence
            if not slide.semantic_topic or not slide.semantic_topic.strip():
                raise StoryPlanValidationError(
                    f"Slide {idx} ('{slide.headline}') has empty semantic_topic. Extensible topic is required."
                )

            # Check logical_slide_id
            if not slide.logical_slide_id or not slide.logical_slide_id.strip():
                raise StoryPlanValidationError(
                    f"Slide {idx} has empty logical_slide_id. Semantic logical identity is required."
                )
            seen_logical_ids.add(slide.logical_slide_id)

            # Check section registration
            if slide.section_name and slide.section_name not in plan.sections:
                raise StoryPlanValidationError(
                    f"Slide {idx} ('{slide.headline}') references unregistered section: '{slide.section_name}'"
                )

            for b in slide.content_bindings:
                if b.content_id not in all_known_ids:
                    raise UnknownContentIdError(
                        f"Logical slide '{slide.headline}' binds unknown content_id: '{b.content_id}'. "
                        f"Allowed IDs from package: {sorted(all_known_ids)}"
                    )
                bound_ids.add(b.content_id)

        # 3. Check for physical layout leakage
        cls._check_no_physical_layout_leakage(plan)

        # 4. Strict content accounting: every package item must be bound or excluded
        if strict_exclusions:
            excluded_ids = {e.content_id for e in plan.excluded_content}
            
            # Check for unknown IDs in excluded content
            unknown_excluded = excluded_ids - all_known_ids
            if unknown_excluded:
                raise UnknownContentIdError(
                    f"Excluded content ledger contains unknown IDs: {sorted(unknown_excluded)}"
                )

            # Check that every package item is accounted for
            unaccounted = set(known_item_ids.keys()) - (bound_ids | excluded_ids)
            if unaccounted:
                raise UnaccountedContentError(
                    f"The following {len(unaccounted)} items from PresentationContentPackage are "
                    f"neither bound to a slide nor recorded in excluded_content: {sorted(unaccounted)}. "
                    f"Silent content loss is strictly prohibited."
                )

        # 5. Truth preservation: verify that bound items preserve exact metrics
        for b_id in bound_ids:
            pkg_item = known_item_ids.get(b_id) or known_kpi_ids.get(b_id)
            if pkg_item is None:
                continue
            if pkg_item.metric_value is not None and not str(pkg_item.metric_value).strip():
                raise StoryPlanValidationError(f"Bound item {b_id} has blank metric value")

        # 6. Governance leakage audit for normal business decks
        cls._check_governance_leakage(plan)

    @classmethod
    def _check_no_physical_layout_leakage(cls, plan: DeckStoryPlan) -> None:
        """Verifies that 0 physical coordinates, slide numbers, or zone fields exist."""
        plan_dict = plan.model_dump()
        
        def _scan(obj: Any, path: str = "") -> None:
            if isinstance(obj, dict):
                for k, v in obj.items():
                    # Upstream chart payloads (such as scatter points or data coordinates in visual_spec)
                    # contain mathematical data attributes ('x', 'y'), not slide layout geometry.
                    if k == "visual_spec":
                        continue
                    if k.lower() in cls.FORBIDDEN_PHYSICAL_FIELDS:
                        raise PhysicalLayoutLeakageError(
                            f"Physical layout property '{k}' found at '{path}.{k}'. "
                            f"PPT-L2 must contain 0 physical coordinates, 0 slide numbers, and 0 zone geometry."
                        )
                    _scan(v, f"{path}.{k}" if path else k)
            elif isinstance(obj, list):
                for i, item in enumerate(obj):
                    _scan(item, f"{path}[{i}]")

        _scan(plan_dict)

    @classmethod
    def _check_governance_leakage(cls, plan: DeckStoryPlan) -> None:
        """Audits user-visible narrative text for unwanted internal engineering jargon."""
        # Check if technical terms are explicitly requested in objective
        obj_lower = (plan.user_objective or "").lower()
        is_technical_request = any(
            kw in obj_lower
            for kw in ["sdr", "joinplan", "joingraph", "technical architecture", "governance review", "pipeline audit"]
        )
        if is_technical_request:
            return  # Explicit technical terminology is permitted when requested

        # Check user-visible fields in normal business presentations
        visible_texts: list[tuple[str, str]] = [
            ("deck_title", plan.deck_title),
            ("deck_subtitle", plan.deck_subtitle),
            ("executive_thesis", plan.executive_thesis),
        ]
        for s in plan.logical_slides:
            visible_texts.extend([
                (f"slide[{s.logical_slide_id}].headline", s.headline),
                (f"slide[{s.logical_slide_id}].purpose", s.purpose),
                (f"slide[{s.logical_slide_id}].takeaway", s.takeaway),
            ])

        for field_path, text in visible_texts:
            for pattern in cls.FORBIDDEN_GOVERNANCE_PATTERNS:
                if re.search(pattern, text, re.IGNORECASE):
                    raise GovernanceLeakageError(
                        f"Internal governance term matching '{pattern}' leaked into user-visible field '{field_path}': '{text}'"
                    )
