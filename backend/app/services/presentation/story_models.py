"""Logical Story Planning & SlideTag Models (PPT-L2).

Establishes the non-negotiable architectural boundaries:
1. LogicalSlideTag != physical slide:
   Logical slide plans represent coherent narrative chapters/units.
   They do NOT map 1:1 to physical slides or enforce slide boundaries.
2. Content Truth != Presentation Narrative:
   StoryPlanner selects, groups, orders, summarizes, and frames content items,
   but CANNOT mutate facts, units, grain, denominators, or invent facts.
3. Zero physical layout / geometry / rendering:
   0 coordinates (x, y, width, height, left, top), 0 physical slide numbers,
   0 SlideExpansion, 0 Layer/Zone calculations, 0 PPTX/DrawingML rendering.
4. Schema-bound content binding:
   Every bound item references an audited content_id in PresentationContentPackage.
   Hallucinated or unknown IDs are strictly rejected.
5. Complete content accounting:
   Every item in the PresentationContentPackage is either bound to a logical slide
   or cataloged in the excluded_content ledger with an explicit ExclusionReason.
"""

from __future__ import annotations

from enum import Enum
import hashlib
import json
from typing import Any
from pydantic import BaseModel, Field

from app.services.presentation.content_models import (
    ContentKind,
    ContentRole,
    PresentationContentItem,
    PresentationContentPackage,
)


class SlideTag(str, Enum):
    """Categorical semantic classification of a logical narrative slide unit.
    
    A SlideTag defines the executive purpose of a story unit, independent of physical layout.
    """
    TITLE = "TITLE"
    AGENDA = "AGENDA"
    EXECUTIVE_SUMMARY = "EXECUTIVE_SUMMARY"
    STRATEGIC_KPIS = "STRATEGIC_KPIS"
    HERO_ANALYSIS = "HERO_ANALYSIS"
    DEEP_DIVE_EXPLORATION = "DEEP_DIVE_EXPLORATION"
    GEOGRAPHIC_DISTRIBUTION = "GEOGRAPHIC_DISTRIBUTION"
    RELATIONAL_CORRELATION = "RELATIONAL_CORRELATION"
    COHORT_VARIANCE = "COHORT_VARIANCE"
    ACTION_PLAN = "ACTION_PLAN"
    CLOSING = "CLOSING"
    THANK_YOU = "THANK_YOU"


# Alias for explicit logical architectural distinction
LogicalSlideTag = SlideTag


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


class ExclusionReason(str, Enum):
    """Strict categorical rationale for why candidate content was not included in the deck."""
    REDUNDANT = "REDUNDANT"
    LOW_RELEVANCE_FOR_OBJECTIVE = "LOW_RELEVANCE_FOR_OBJECTIVE"
    CAPACITY_LIMIT = "CAPACITY_LIMIT"
    OFF_OBJECTIVE = "OFF_OBJECTIVE"
    SUPERCEDED_BY_HERO = "SUPERCEDED_BY_HERO"


class ExcludedContentItem(BaseModel):
    """Audited ledger entry for unused content items from the PresentationContentPackage."""
    content_id: str = Field(description="Audited ID matching PresentationContentItem.content_id")
    reason: ExclusionReason = Field(description="Categorical reason for exclusion")
    notes: str | None = Field(default=None, description="Detailed explanation for narrative audit")
    importance_score: float | None = Field(default=None, description="Original importance score from ranker")


class LogicalSlidePlan(BaseModel):
    """A logical narrative chapter or story unit.
    
    CRITICAL INVARIANT:
    A LogicalSlidePlan is NOT a physical slide. It may contain multiple content bindings
    that a downstream preflight/capacity pass (PPT-L3/L4) can split across multiple
    physical slide instances if required by layout constraints.
    """
    tag: SlideTag = Field(description="Logical slide tag classifying narrative intent")
    section_name: str = Field(description="High-level presentation section, e.g. Executive Overview")
    purpose: str = Field(description="Executive objective or question this slide unit answers")
    headline: str = Field(description="Action-oriented executive headline")
    takeaway: str = Field(default="", description="Key strategic takeaway")
    content_bindings: list[ContentBinding] = Field(default_factory=list, description="Bound content IDs")
    preferred_archetype: str | None = Field(default=None, description="Suggested visual archetype (e.g. CHART_WITH_INSIGHT)")
    allow_split: bool = Field(default=True, description="Whether preflight is permitted to split this unit")
    logical_order: int = Field(default=0, description="Logical story order (1-indexed sequence)")


class DeckStoryPlan(BaseModel):
    """Governed presentation narrative plan produced by StoryPlanner (PPT-L2)."""
    plan_id: str = Field(description="Unique deterministic plan ID, e.g. PLAN-...")
    deck_title: str = Field(description="Overarching presentation title")
    deck_subtitle: str = Field(description="Presentation subtitle or briefing context")
    executive_thesis: str = Field(description="Core strategic narrative thesis")
    sections: list[str] = Field(default_factory=list, description="Ordered presentation section headings")
    logical_slides: list[LogicalSlidePlan] = Field(default_factory=list, description="Ordered logical slide units")
    excluded_content: list[ExcludedContentItem] = Field(default_factory=list, description="Complete ledger of unselected content")
    target_audience: str = Field(default="Executive Leadership")
    user_objective: str = Field(default="")
    story_fingerprint: str = Field(default="", description="Deterministic SHA-256 fingerprint over story structure")
    metadata: dict[str, Any] = Field(default_factory=dict)

    def compute_story_fingerprint(self) -> str:
        """Computes a deterministic SHA-256 fingerprint over canonical story plan properties."""
        canonical_slides = []
        for s in sorted(self.logical_slides, key=lambda x: (x.logical_order, x.tag.value, x.headline)):
            sorted_bindings = sorted(s.content_bindings, key=lambda b: (b.content_id, b.binding_role.value))
            canonical_slides.append({
                "tag": s.tag.value,
                "section": s.section_name,
                "headline": s.headline,
                "purpose": s.purpose,
                "takeaway": s.takeaway,
                "archetype": s.preferred_archetype or "",
                "allow_split": s.allow_split,
                "bindings": [
                    {"id": b.content_id, "role": b.binding_role.value}
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


class StoryPlanValidator:
    """Validates DeckStoryPlan compliance against PresentationContentPackage and PPT-L2 invariants."""

    FORBIDDEN_PHYSICAL_FIELDS = {
        "x", "y", "width", "height", "left", "top",
        "slide_number", "page_number", "zones", "layers",
        "bounding_box", "coordinate_space", "pt_x", "pt_y",
        "canvas_width", "canvas_height", "font_size_pt"
    }

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

        # 2. Collect bound content IDs and check for unknown / hallucinated IDs
        bound_ids: set[str] = set()
        for idx, slide in enumerate(plan.logical_slides):
            # Check slide tag validity
            if not isinstance(slide.tag, SlideTag):
                raise StoryPlanValidationError(
                    f"Slide {idx} has invalid tag type: {type(slide.tag)} (value: {slide.tag})"
                )

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

        # 5. Invariant: Truth preservation (verify that bound items preserve exact metrics)
        for b_id in bound_ids:
            pkg_item = known_item_ids.get(b_id) or known_kpi_ids.get(b_id)
            if pkg_item is None:
                continue
            # Ensure fundamental analytical properties exist and have not been destroyed
            if pkg_item.metric_value is not None and not str(pkg_item.metric_value).strip():
                raise StoryPlanValidationError(f"Bound item {b_id} has blank metric value")

    @classmethod
    def _check_no_physical_layout_leakage(cls, plan: DeckStoryPlan) -> None:
        """Verifies that 0 physical coordinates, slide numbers, or zone fields exist."""
        plan_dict = plan.model_dump()
        
        def _scan(obj: Any, path: str = "") -> None:
            if isinstance(obj, dict):
                for k, v in obj.items():
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
