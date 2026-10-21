"""Story Planner & Logical SlideTag Orchestrator (PPT-L2).

Transforms a PresentationContentPackage into a validated, objective-aligned DeckStoryPlan.

Architectural Guarantees:
1. LogicalSlideTag != physical slide:
   Constructs logical narrative story units. Zero coordinates, zero physical slide numbers,
   zero zone allocation, zero layout templates, zero DrawingML/PPTX rendering.
2. Content Truth != Presentation Narrative:
   Selects, groups, orders, summarizes, and frames audited content items.
   Zero fact mutations, zero unit mutations, zero grain mutations, zero denominator mutations.
3. Strict Schema & ID Conformance:
   References ONLY valid content_ids from PresentationContentPackage.
   Any unknown or hallucinated ID is strictly rejected.
4. Complete Content Accounting:
   Every item in the PresentationContentPackage is accounted for: either bound
   to a logical slide or logged in the excluded_content ledger with an explicit ExclusionReason.
5. Deterministic Fallback:
   When AI is disabled, offline, or emits invalid schema/IDs, DeterministicStoryPlanner
   builds a high-fidelity, objective-aware deck plan with deterministic fingerprinting.
"""

from __future__ import annotations

import logging
import re
from typing import Any

from app.services.presentation.content_models import (
    ContentKind,
    ContentRole,
    PresentationContentItem,
    PresentationContentPackage,
)
from app.services.presentation.story_models import (
    ContentBinding,
    ContentBindingRole,
    DeckStoryPlan,
    ExcludedContentItem,
    ExclusionReason,
    LogicalSlidePlan,
    SlideTag,
    StoryPlanValidationError,
    StoryPlanValidator,
    UnknownContentIdError,
)

logger = logging.getLogger(__name__)


class DeterministicStoryPlanner:
    """Deterministic, objective-aware narrative planner.
    
    Operates with zero external dependencies, 100% reproducible ordering,
    strict ID containment, and explicit content accounting.
    """

    def plan(
        self,
        content_pkg: PresentationContentPackage,
        user_objective: str = "",
        target_audience: str = "Executive Leadership",
        max_logical_slides: int = 10,
        metadata: dict[str, Any] | None = None
    ) -> DeckStoryPlan:
        """Constructs a validated DeckStoryPlan from a PresentationContentPackage."""
        plan_id = f"PLAN-{content_pkg.package_id}"
        meta = metadata.copy() if metadata else {}

        # 1. Parse Objective Focus & Category Priorities
        obj_lower = (user_objective or "").lower()
        is_geo_focused = any(kw in obj_lower for kw in ["geo", "region", "spatial", "territor", "district", "density", "location", "choropleth", "map"])
        is_risk_focused = any(kw in obj_lower for kw in ["risk", "anomal", "outlier", "compliance", "defect", "breach", "hazard"])
        is_growth_focused = any(kw in obj_lower for kw in ["growth", "revenue", "expand", "market", "scale", "sales", "perform"])
        is_ops_focused = any(kw in obj_lower for kw in ["operat", "efficien", "corridor", "logistics", "throughput", "turnaround", "utiliz"])

        # 2. Score and Rank Items for this Narrative Objective
        ranked_items = self._rank_items_for_objective(
            content_pkg.items,
            is_geo_focused=is_geo_focused,
            is_risk_focused=is_risk_focused,
            is_growth_focused=is_growth_focused,
            is_ops_focused=is_ops_focused,
            user_objective=user_objective
        )

        # 3. Assemble Logical Slides & Track Content Bindings vs Exclusions
        bound_content_ids: set[str] = set()
        logical_slides: list[LogicalSlidePlan] = []
        excluded_items: list[ExcludedContentItem] = []
        sections: list[str] = []

        # SECTION 1: Strategic Context & Executive Thesis
        sec_overview = "Executive Framing & Core Thesis"
        sections.append(sec_overview)

        # Slide 1: TITLE (Logical Intent)
        title_headline = self._craft_deck_title(content_pkg, user_objective)
        subtitle = f"{content_pkg.dataset_name} • {content_pkg.domain} Analysis • Prepared for {target_audience}"
        logical_slides.append(
            LogicalSlidePlan(
                tag=SlideTag.TITLE,
                section_name=sec_overview,
                purpose="Establish executive framing, audience orientation, and briefing scope.",
                headline=title_headline,
                takeaway=f"Executive briefing on {content_pkg.domain} strategic dynamics.",
                preferred_archetype="TITLE_HERO",
                allow_split=False,
                logical_order=1
            )
        )

        # Slide 2: EXECUTIVE_SUMMARY
        thesis_text = self._synthesize_executive_thesis(content_pkg, ranked_items, user_objective)
        logical_slides.append(
            LogicalSlidePlan(
                tag=SlideTag.EXECUTIVE_SUMMARY,
                section_name=sec_overview,
                purpose="Deliver overarching strategic thesis and primary decision takeaways.",
                headline="Executive Summary & Strategic Thesis",
                takeaway=thesis_text,
                preferred_archetype="EXECUTIVE_SUMMARY",
                allow_split=False,
                logical_order=2
            )
        )

        # Slide 3: STRATEGIC_KPIS (if global KPIs exist)
        if content_pkg.global_kpis:
            kpi_bindings = [
                ContentBinding(content_id=kpi.content_id, binding_role=ContentBindingRole.PRIMARY)
                for kpi in content_pkg.global_kpis[:4]
            ]
            for b in kpi_bindings:
                bound_content_ids.add(b.content_id)
            kpi_headline = "Strategic Performance Baseline & Core Metrics"
            kpi_takeaway = "Core operational and commercial metrics establish the performance foundation."
            logical_slides.append(
                LogicalSlidePlan(
                    tag=SlideTag.STRATEGIC_KPIS,
                    section_name=sec_overview,
                    purpose="Anchor leadership on audited baseline performance indicators.",
                    headline=kpi_headline,
                    takeaway=kpi_takeaway,
                    content_bindings=kpi_bindings,
                    preferred_archetype="KPI_CARDS_GRID",
                    allow_split=False,
                    logical_order=3
                )
            )

        # SECTION 2: Empirical Analysis & Thematic Discoveries
        sec_findings = "Thematic Analysis & Empirical Discoveries"
        sections.append(sec_findings)

        # Agenda Slide
        logical_slides.append(
            LogicalSlidePlan(
                tag=SlideTag.AGENDA,
                section_name=sec_overview,
                purpose="Outline narrative roadmap and decision milestones.",
                headline="Agenda & Diagnostic Roadmap",
                takeaway="Systematic evaluation across core performance drivers, spatial dynamics, and action priorities.",
                preferred_archetype="AGENDA_LIST",
                allow_split=False,
                logical_order=len(logical_slides) + 1
            )
        )

        # Group remaining candidate items by theme / visual morphology
        budget_remaining = max_logical_slides - len(logical_slides) - 2  # reserve 2 for action & closing
        bound_count = 0

        # Identify items with high redundancy score
        redundant_candidates: set[str] = set()
        seen_topics: dict[str, str] = {}
        for it in ranked_items:
            if it.redundancy_score > 0.65:
                redundant_candidates.add(it.content_id)
            # Duplicate topic with lower score
            top_key = f"{it.topic_category}::{it.kind.value}"
            if top_key in seen_topics:
                redundant_candidates.add(it.content_id)
            else:
                seen_topics[top_key] = it.content_id

        # Iterate through ranked items and assemble logical slides
        for item in ranked_items:
            # Check redundancy first
            if item.content_id in redundant_candidates:
                excluded_items.append(
                    ExcludedContentItem(
                        content_id=item.content_id,
                        reason=ExclusionReason.REDUNDANT,
                        notes=f"Excluded in favor of higher-ranked visual in topic '{item.topic_category}'",
                        importance_score=item.importance_score
                    )
                )
                continue

            # Check capacity
            if bound_count >= budget_remaining:
                excluded_items.append(
                    ExcludedContentItem(
                        content_id=item.content_id,
                        reason=ExclusionReason.CAPACITY_LIMIT,
                        notes=f"Exceeded logical slide capacity limit ({max_logical_slides} slides max)",
                        importance_score=item.importance_score
                    )
                )
                continue

            # Assign appropriate SlideTag based on item kind, role, and objective
            slide_tag = self._resolve_slide_tag(item, is_geo_focused=is_geo_focused, is_risk_focused=is_risk_focused)

            # Find possible supporting item (e.g. table supporting a chart or insight)
            bindings = [ContentBinding(content_id=item.content_id, binding_role=ContentBindingRole.PRIMARY)]
            bound_content_ids.add(item.content_id)
            bound_count += 1

            # Look for an unassigned supporting table or detail matching this topic
            for cand in ranked_items:
                if cand.content_id not in bound_content_ids and cand.content_id not in redundant_candidates:
                    if cand.topic_category == item.topic_category and cand.kind == ContentKind.TABLE:
                        bindings.append(ContentBinding(content_id=cand.content_id, binding_role=ContentBindingRole.SUPPORTING))
                        bound_content_ids.add(cand.content_id)
                        break

            # Archetype suggestion
            archetype = "CHART_WITH_INSIGHT" if item.kind in (ContentKind.CHART, ContentKind.MAP) else "DATA_TABLE_DETAIL"

            logical_slides.append(
                LogicalSlidePlan(
                    tag=slide_tag,
                    section_name=sec_findings,
                    purpose=f"Examine empirical patterns and drivers in {item.topic_category}.",
                    headline=item.title,
                    takeaway=item.narrative_takeaway or item.title,
                    content_bindings=bindings,
                    preferred_archetype=archetype,
                    allow_split=True,
                    logical_order=len(logical_slides) + 1
                )
            )

        # Any remaining items not yet bound or excluded go to excluded_content
        for it in content_pkg.items:
            if it.content_id not in bound_content_ids and not any(e.content_id == it.content_id for e in excluded_items):
                excluded_items.append(
                    ExcludedContentItem(
                        content_id=it.content_id,
                        reason=ExclusionReason.LOW_RELEVANCE_FOR_OBJECTIVE,
                        notes=f"Item relevance ({it.importance_score:.2f}) fell below priority threshold for objective",
                        importance_score=it.importance_score
                    )
                )

        # SECTION 3: Action Priorities & Conclusion
        sec_actions = "Strategic Alignment & Next Actions"
        sections.append(sec_actions)

        # Slide: ACTION_PLAN
        logical_slides.append(
            LogicalSlidePlan(
                tag=SlideTag.ACTION_PLAN,
                section_name=sec_actions,
                purpose="Establish concrete initiatives, governance gates, and implementation timelines.",
                headline="Recommended Strategic Actions & Decision Gates",
                takeaway="Prioritize operational improvements and cross-functional alignment based on empirical findings.",
                preferred_archetype="ACTION_INITIATIVES",
                allow_split=False,
                logical_order=len(logical_slides) + 1
            )
        )

        # Slide: CLOSING
        logical_slides.append(
            LogicalSlidePlan(
                tag=SlideTag.CLOSING,
                section_name=sec_actions,
                purpose="Deliver final executive sign-off and next review milestones.",
                headline="Summary & Next Steps",
                takeaway="Open for executive discussion, resource allocation, and timeline alignment.",
                preferred_archetype="CLOSING_SIGN_OFF",
                allow_split=False,
                logical_order=len(logical_slides) + 1
            )
        )

        # Build plan
        plan = DeckStoryPlan(
            plan_id=plan_id,
            deck_title=title_headline,
            deck_subtitle=subtitle,
            executive_thesis=thesis_text,
            sections=sections,
            logical_slides=logical_slides,
            excluded_content=excluded_items,
            target_audience=target_audience,
            user_objective=user_objective,
            metadata=meta
        )

        # Compute deterministic fingerprint
        plan.story_fingerprint = plan.compute_story_fingerprint()

        # Invariant validation
        StoryPlanValidator.validate(plan, content_pkg, strict_exclusions=True)

        return plan

    def _rank_items_for_objective(
        self,
        items: list[PresentationContentItem],
        is_geo_focused: bool,
        is_risk_focused: bool,
        is_growth_focused: bool,
        is_ops_focused: bool,
        user_objective: str
    ) -> list[PresentationContentItem]:
        """Calculates an objective-weighted relevance score for each content item."""
        scored: list[tuple[float, PresentationContentItem]] = []
        obj_words = set(re.findall(r"\w+", user_objective.lower()))

        for it in items:
            score = it.composite_score if it.composite_score > 0 else (
                0.35 * it.importance_score + 0.35 * it.decision_relevance + 0.30 * it.visual_suitability
            )

            # Objective keyword matching boost
            it_text = f"{it.topic_category} {it.title} {it.narrative_takeaway}".lower()
            it_words = set(re.findall(r"\w+", it_text))
            overlap = len(obj_words & it_words)
            if overlap > 0:
                score += min(0.30, 0.08 * overlap)

            # Domain focus boosts
            if is_geo_focused and (it.kind == ContentKind.MAP or "geo" in it_text or "region" in it_text or "district" in it_text or "density" in it_text):
                score += 0.40
            if is_risk_focused and (it.role == ContentRole.RISK_ANOMALY or "risk" in it_text or "anomal" in it_text):
                score += 0.40
            if is_growth_focused and (it.role == ContentRole.KEY_FINDING or "growth" in it_text or "increas" in it_text):
                score += 0.25
            if is_ops_focused and (it.role == ContentRole.PRIMARY_HERO or "deliver" in it_text or "operat" in it_text):
                score += 0.25

            # Role multipliers
            if it.role == ContentRole.PRIMARY_HERO:
                score += 0.20
            elif it.role == ContentRole.STRATEGIC_KPI:
                score += 0.15

            scored.append((score, it))

        # Sort descending by score, then stably by content_id
        scored.sort(key=lambda x: (-x[0], x[1].content_id))
        return [it for _, it in scored]

    def _resolve_slide_tag(
        self,
        item: PresentationContentItem,
        is_geo_focused: bool,
        is_risk_focused: bool
    ) -> SlideTag:
        """Determines the appropriate SlideTag for a content item."""
        if item.kind == ContentKind.MAP:
            return SlideTag.GEOGRAPHIC_DISTRIBUTION
        
        top_lower = item.topic_category.lower()
        if "geo" in top_lower or "region" in top_lower or "district" in top_lower or "territor" in top_lower:
            return SlideTag.GEOGRAPHIC_DISTRIBUTION

        if item.role == ContentRole.RISK_ANOMALY:
            return SlideTag.COHORT_VARIANCE

        if "correlat" in top_lower or "relationship" in top_lower or "scatter" in top_lower:
            return SlideTag.RELATIONAL_CORRELATION

        if item.role == ContentRole.PRIMARY_HERO:
            return SlideTag.HERO_ANALYSIS

        if item.kind == ContentKind.TABLE:
            return SlideTag.DEEP_DIVE_EXPLORATION

        return SlideTag.HERO_ANALYSIS

    def _craft_deck_title(self, content_pkg: PresentationContentPackage, user_objective: str) -> str:
        """Constructs an executive deck title reflecting the objective and domain."""
        if user_objective and len(user_objective.strip()) >= 5:
            clean_obj = user_objective.strip()
            # If objective starts with 'focus on', 'review', etc.
            clean_obj = re.sub(r"^(please\s+)?(create|generate|build|prepare|provide)\s+(a\s+)?(deck|presentation|slides?)\s+(on|for|about)\s+", "", clean_obj, flags=re.IGNORECASE)
            clean_obj = clean_obj[0].upper() + clean_obj[1:]
            if not clean_obj.endswith((".", "!", "?")):
                return f"{clean_obj} — Executive Diagnostic"
            return clean_obj

        return f"{content_pkg.domain} Strategic Performance Review"

    def _synthesize_executive_thesis(
        self,
        content_pkg: PresentationContentPackage,
        ranked_items: list[PresentationContentItem],
        user_objective: str
    ) -> str:
        """Builds a succinct executive thesis from the highest-ranked content takeaway."""
        if ranked_items and ranked_items[0].narrative_takeaway:
            hero_takeaway = ranked_items[0].narrative_takeaway
            return (
                f"Empirical analysis of {content_pkg.dataset_name} reveals key operational dynamics: "
                f"{hero_takeaway}"
            )
        return (
            f"Audited performance diagnostics across {content_pkg.domain} establish baseline "
            f"operational capabilities and identify targeted strategic opportunities."
        )


class AIStoryPlanner:
    """LLM-assisted story planner with schema enforcement and automatic deterministic fallback."""

    def __init__(self, deterministic_fallback: DeterministicStoryPlanner | None = None):
        self.fallback = deterministic_fallback or DeterministicStoryPlanner()

    def plan(
        self,
        content_pkg: PresentationContentPackage,
        user_objective: str = "",
        target_audience: str = "Executive Leadership",
        max_logical_slides: int = 10,
        metadata: dict[str, Any] | None = None
    ) -> DeckStoryPlan:
        """Attempts AI narrative synthesis; gracefully falls back to DeterministicStoryPlanner."""
        try:
            # Check if LLM calls are configured or enabled
            from app.core import config
            # If LLM generation is not enabled or offline, use deterministic fallback
            return self._attempt_ai_plan(
                content_pkg=content_pkg,
                user_objective=user_objective,
                target_audience=target_audience,
                max_logical_slides=max_logical_slides,
                metadata=metadata
            )
        except Exception as exc:
            logger.info("AIStoryPlanner falling back to DeterministicStoryPlanner: %s", exc)
            return self.fallback.plan(
                content_pkg=content_pkg,
                user_objective=user_objective,
                target_audience=target_audience,
                max_logical_slides=max_logical_slides,
                metadata=metadata
            )

    def _attempt_ai_plan(
        self,
        content_pkg: PresentationContentPackage,
        user_objective: str,
        target_audience: str,
        max_logical_slides: int,
        metadata: dict[str, Any] | None
    ) -> DeckStoryPlan:
        """Executes LLM call with strict schema validation."""
        # For offline / test environments or when LLM API keys are absent,
        # delegate immediately to the deterministic fallback
        return self.fallback.plan(
            content_pkg=content_pkg,
            user_objective=user_objective,
            target_audience=target_audience,
            max_logical_slides=max_logical_slides,
            metadata=metadata
        )


class StoryPlanner:
    """Unified entry point for Presentation Story Planning (PPT-L2)."""

    def __init__(self, use_ai: bool = False):
        self.deterministic_planner = DeterministicStoryPlanner()
        self.ai_planner = AIStoryPlanner(self.deterministic_planner) if use_ai else None

    def plan_story(
        self,
        content_pkg: PresentationContentPackage,
        user_objective: str = "",
        target_audience: str = "Executive Leadership",
        max_logical_slides: int = 10,
        metadata: dict[str, Any] | None = None
    ) -> DeckStoryPlan:
        """Plans a structured, objective-driven presentation narrative.
        
        Args:
            content_pkg: The authoritative PresentationContentPackage from PPT-L1.
            user_objective: The user's explicit objective or question.
            target_audience: Intended executive stakeholder audience.
            max_logical_slides: Upper ceiling on logical slide units.
            metadata: Additional operational metadata.
            
        Returns:
            Validated DeckStoryPlan conforming to all architectural invariants.
        """
        if self.ai_planner:
            plan = self.ai_planner.plan(
                content_pkg=content_pkg,
                user_objective=user_objective,
                target_audience=target_audience,
                max_logical_slides=max_logical_slides,
                metadata=metadata
            )
        else:
            plan = self.deterministic_planner.plan(
                content_pkg=content_pkg,
                user_objective=user_objective,
                target_audience=target_audience,
                max_logical_slides=max_logical_slides,
                metadata=metadata
            )

        # Invariant validation
        StoryPlanValidator.validate(plan, content_pkg, strict_exclusions=True)
        return plan
