from __future__ import annotations

import logging
from typing import Any

from ....core import config
from .director_models import (
    InformationDestination,
    InformationSourceType,
    InformationUnit,
    NarrativeStrategy,
    PlanningValidationResult,
    PresentationIntent,
    PresentationPlanningContext,
    PresentationPlanSpec,
    SlideCountConstraint,
    SlideCountMode,
    SlidePlan,
)
from .intent_planner import plan_intent
from .information_extractor import extract_and_triage_information
from .narrative_planner import plan_narrative
from .slide_planner import plan_slides
from .plan_validator import validate_plan
from .plan_adapter import adapt_plan_to_deck_spec

logger = logging.getLogger(__name__)


class PresentationDirector:
    """The central Presentation Director (Qwen 3.5).

    Orchestrates bounded, hierarchical presentation intelligence:
    Stage 1: Intent Determination
    Stage 2: Information Extraction & Strict Truth Triage
    Stage 3: Narrative Arc & Pacing Strategy
    Stage 4: Adaptive Slide Boundary Planning
    Stage 5: Plan Validation & Quality Auditing
    """

    def __init__(
        self,
        enabled: bool | None = None,
        model_name: str | None = None,
        max_retries: int | None = None
    ):
        self.enabled = enabled if enabled is not None else getattr(config, "PRESENTATION_DIRECTOR_ENABLED", True)
        self.model_name = model_name or getattr(config, "PRESENTATION_DIRECTOR_MODEL", "qwen3.5:9b")
        self.max_retries = max_retries if max_retries is not None else getattr(config, "PRESENTATION_DIRECTOR_MAX_RETRIES", 2)

    def plan_presentation(self, ctx: PresentationPlanningContext) -> PresentationPlanSpec:
        """Executes the full hierarchical planning flow to generate a PresentationPlanSpec."""
        logger.info(
            f"Presentation Director planning deck for domain='{ctx.domain}', "
            f"objective='{ctx.objective[:40]}...', constraint_mode={ctx.slide_count_constraint.mode.value}"
        )

        retries = self.max_retries if self.enabled else -1

        # Stage 1: Intent Determination
        intent = plan_intent(ctx, max_retries=retries)

        # Stage 2: Information Extraction & Truth Triage
        information_units = extract_and_triage_information(ctx, intent, max_retries=retries)

        # Stage 3: Narrative Arc & Thematic Structure
        narrative = plan_narrative(ctx, intent, information_units, max_retries=retries)

        # Stage 4: Slide Boundary & Visual Allocation
        slides = plan_slides(ctx, intent, narrative, information_units, max_retries=retries)

        # Stage 5: Plan Validation
        validation = validate_plan(ctx, intent, slides)

        # Bounded recovery if duplicate concepts detected
        if validation.duplicate_concepts_detected and retries > 0:
            logger.info("Validation detected duplicate concepts; triggering bounded slide replanning.")
            slides = plan_slides(ctx, intent, narrative, information_units, max_retries=0)
            validation = validate_plan(ctx, intent, slides)

        # Gather evidence usage
        used_evidence_ids = list({eid for s in slides for eid in s.evidence_ids if eid})
        used_hist_refs = [
            {"slide_id": s.slide_id, "ref": ref}
            for s in slides
            for ref in s.historical_context_refs
        ]

        deck_title = f"{ctx.domain.title()} Performance Review"
        if slides and slides[0].headline:
            deck_title = slides[0].headline

        return PresentationPlanSpec(
            spec_version="2.0",
            deck_title=deck_title,
            intent=intent,
            narrative_strategy=narrative,
            information_units=information_units,
            sections=narrative.sections,
            slides=slides,
            slide_count=len(slides),
            evidence_usage=used_evidence_ids,
            retrieved_context_usage=used_hist_refs,
            planning_validation=validation,
            metadata={
                "director_model": self.model_name,
                "domain": ctx.domain,
                "slide_count_mode": ctx.slide_count_constraint.mode.value,
                "dataset_label": ctx.dataset_label,
                "total_records": ctx.total_records,
                "snapshot_hash": ctx.snapshot_hash
            }
        )

    def plan_and_adapt(
        self,
        ctx: PresentationPlanningContext,
        theme: dict[str, Any],
        theme_id: str = "executive_dark",
        chart_pack: dict[str, Any] | None = None,
        profiled_data: dict[str, Any] | None = None,
        evidence_ledger: list[dict[str, Any]] | None = None,
        on_slide_progress: Any = None
    ) -> dict[str, Any]:
        """Convenience wrapper: Plans the presentation and adapts it into a valid PresentationDeckSpec."""
        plan_spec = self.plan_presentation(ctx)
        return adapt_plan_to_deck_spec(
            plan=plan_spec,
            ctx=ctx,
            theme=theme,
            theme_id=theme_id,
            chart_pack=chart_pack,
            profiled_data=profiled_data,
            evidence_ledger=evidence_ledger,
            on_slide_progress=on_slide_progress
        )


# Global singleton
presentation_director = PresentationDirector()
