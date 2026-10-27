"""Slide Composition Intelligence — Slide Composition Engine.

Orchestrates composition intelligence across all logical slides in a DeckStoryPlan.
Translates domain-neutral CompositionDecisions into downstream layout family hints
and preferred visual archetypes while preserving all story invariants.
"""

from __future__ import annotations

import logging
import uuid
from typing import Any, Optional

from ..content_models import PresentationContentPackage
from ..story_models import DeckStoryPlan, LogicalSlidePlan
from .composition_models import (
    CompositionArchetype,
    CompositionConsumptionRecord,
    CompositionDecision,
    CompositionDecisionSource,
    DeckCompositionPlan,
)
from .composition_provider import (
    AICompositionProvider,
    CompositionProvider,
    DeterministicCompositionProvider,
)

logger = logging.getLogger(__name__)

# Canonical mapping from semantic composition archetype to downstream layout family
COMPOSITION_TO_LAYOUT_FAMILY: dict[CompositionArchetype, str] = {
    CompositionArchetype.TITLE_COVER: "title_cover",
    CompositionArchetype.KPI_GRID: "kpi_summary",
    CompositionArchetype.HERO_METRIC: "kpi_summary",
    CompositionArchetype.VISUAL_HERO: "full_chart_takeaway",
    CompositionArchetype.VISUAL_WITH_INSIGHT: "chart_narrative",
    CompositionArchetype.VISUAL_WITH_SUPPORTING_METRICS: "chart_narrative",
    CompositionArchetype.COMPARISON: "comparison_split",
    CompositionArchetype.RANKING: "chart_narrative",
    CompositionArchetype.DISTRIBUTION: "chart_narrative",
    CompositionArchetype.CORRELATION: "chart_narrative",
    CompositionArchetype.SCENARIO: "comparison_split",
    CompositionArchetype.TABLE_DEEP_DIVE: "table_detail",
    CompositionArchetype.OUTLIER_SUMMARY: "chart_narrative",
    CompositionArchetype.MULTI_INSIGHT: "chart_narrative",
    CompositionArchetype.EXECUTIVE_SYNTHESIS: "chart_narrative",
    CompositionArchetype.CLOSING_SUMMARY: "action_plan",
}

# Canonical mapping from semantic composition archetype to existing story preferred_archetype strings
COMPOSITION_TO_PREFERRED_ARCHETYPE: dict[CompositionArchetype, str] = {
    CompositionArchetype.TITLE_COVER: "TITLE_HERO",
    CompositionArchetype.KPI_GRID: "KPI_GRID",
    CompositionArchetype.HERO_METRIC: "KPI_GRID",
    CompositionArchetype.VISUAL_HERO: "VISUAL_HERO",
    CompositionArchetype.VISUAL_WITH_INSIGHT: "CHART_WITH_INSIGHT",
    CompositionArchetype.VISUAL_WITH_SUPPORTING_METRICS: "CHART_WITH_METRICS",
    CompositionArchetype.COMPARISON: "COMPARISON",
    CompositionArchetype.RANKING: "RANKING",
    CompositionArchetype.DISTRIBUTION: "DISTRIBUTION",
    CompositionArchetype.CORRELATION: "CORRELATION",
    CompositionArchetype.SCENARIO: "COMPARISON",
    CompositionArchetype.TABLE_DEEP_DIVE: "DATA_TABLE_DETAIL",
    CompositionArchetype.OUTLIER_SUMMARY: "OUTLIER_SUMMARY",
    CompositionArchetype.MULTI_INSIGHT: "EXECUTIVE_SUMMARY",
    CompositionArchetype.EXECUTIVE_SYNTHESIS: "EXECUTIVE_SUMMARY",
    CompositionArchetype.CLOSING_SUMMARY: "CLOSING_SIGN_OFF",
}


class SlideCompositionEngine:
    """Orchestrator for Slide Composition Intelligence."""

    def __init__(
        self,
        provider: Optional[CompositionProvider] = None,
        use_ai: bool = False,
    ):
        if provider is not None:
            self.provider = provider
        elif use_ai:
            self.provider = AICompositionProvider(use_ai=True)
        else:
            self.provider = DeterministicCompositionProvider()

    def compose_deck(
        self,
        story_plan: DeckStoryPlan,
        content_pkg: Optional[PresentationContentPackage] = None,
        metadata: Optional[dict[str, Any]] = None,
    ) -> DeckCompositionPlan:
        """Runs composition intelligence across each logical slide in the deck story plan.
        
        Enriches each LogicalSlidePlan with:
        - preferred_archetype (aligned with composition archetype)
        - metadata["planned_layout_family"]
        - metadata["composition_decision"]
        - metadata["density_intent"]
        - metadata["narrative_placement"]
        - metadata["label_simplification_intents"]
        """
        metadata = metadata or {}
        plan_id = f"COMP-PLAN-{uuid.uuid4().hex[:8].upper()}"
        decisions: list[CompositionDecision] = []
        ai_count = 0
        fallback_count = 0

        for l_slide in story_plan.logical_slides:
            decision = self.provider.compose_slide(
                logical_slide=l_slide,
                content_pkg=content_pkg,
                metadata=metadata,
            )
            decisions.append(decision)

            if decision.decision_source == CompositionDecisionSource.AI_MODEL:
                ai_count += 1
            else:
                fallback_count += 1

            # Update logical slide properties for downstream preflight and expansion
            mapped_archetype = COMPOSITION_TO_PREFERRED_ARCHETYPE.get(
                decision.composition_archetype,
                decision.composition_archetype.value,
            )
            l_slide.preferred_archetype = mapped_archetype

            layout_family = COMPOSITION_TO_LAYOUT_FAMILY.get(
                decision.composition_archetype,
                "chart_narrative",
            )
            l_slide.metadata["planned_layout_family"] = layout_family
            l_slide.metadata["composition_decision"] = decision.model_dump()
            l_slide.metadata["density_intent"] = decision.density_intent.value
            l_slide.metadata["narrative_placement"] = decision.narrative_placement.value
            l_slide.metadata["composition_archetype"] = decision.composition_archetype.value

            if decision.label_intents:
                l_slide.metadata["label_simplification_intents"] = [
                    li.model_dump() for li in decision.label_intents
                ]

            # PPT-L2.5 Diagnostic Consumption Tracking (Prevents Phantom Composition)
            decision.consumption = CompositionConsumptionRecord(
                logical_slide_id=l_slide.logical_slide_id,
                archetype_consumed=True,
                content_grouping_consumed=bool(decision.content_groups),
                visual_priority_consumed=True,
                density_consumed=True,
                narrative_placement_consumed=True,
                split_intent_consumed=True,
                label_intent_consumed=bool(decision.label_intents),
            )
            l_slide.metadata["composition_consumption"] = decision.consumption.model_dump()

        composition_plan = DeckCompositionPlan(
            plan_id=plan_id,
            deck_title=story_plan.deck_title,
            slide_decisions=decisions,
            ai_decisions_count=ai_count,
            fallback_decisions_count=fallback_count,
            consumption_summary={
                "archetype_consumed_count": len(decisions),
                "content_grouping_consumed_count": sum(1 for d in decisions if d.consumption and d.consumption.content_grouping_consumed),
                "visual_priority_consumed_count": len(decisions),
                "density_consumed_count": len(decisions),
                "narrative_placement_consumed_count": len(decisions),
                "split_intent_consumed_count": len(decisions),
                "label_intent_consumed_count": sum(1 for d in decisions if d.consumption and d.consumption.label_intent_consumed),
            },
            metadata={
                "story_plan_id": story_plan.plan_id,
                "story_fingerprint": story_plan.story_fingerprint,
                "total_slides": len(story_plan.logical_slides),
                **metadata,
            },
        )

        # Attach telemetry to deck story plan
        story_plan.metadata["composition_plan_id"] = plan_id
        story_plan.metadata["composition_telemetry"] = {
            "plan_id": plan_id,
            "total_slides": len(story_plan.logical_slides),
            "ai_decisions_count": ai_count,
            "fallback_decisions_count": fallback_count,
        }

        logger.info(
            "SlideCompositionEngine composed DeckStoryPlan %s (%d slides: %d AI, %d fallback) into plan %s",
            story_plan.plan_id,
            len(story_plan.logical_slides),
            ai_count,
            fallback_count,
            plan_id,
        )

        return composition_plan
