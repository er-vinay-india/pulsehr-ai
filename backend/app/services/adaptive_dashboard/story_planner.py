"""Governed AI Story Planner & Evidence Hydration Engine.

Transforms ranked evidence nodes into an executive narrative storyboard:
1. Recommends narrative angle and executive focus.
2. Selects hero and supporting evidence nodes (EVID-xxx).
3. Produces grounded claims strictly bound to evidence nodes.
4. Enforces causal-language boundaries:
   - OBSERVED: verified empirical differences and aggregations
   - ASSOCIATED: correlations and co-movements
   - INFERRED: statistical projections and counterfactual estimates
   - HYPOTHESIS: operational interpretations and recommended actions
5. Hydrates templates deterministically to prevent numeric hallucination.
"""
from __future__ import annotations

import logging
from typing import Any, Literal
from pydantic import BaseModel, ConfigDict, Field

from .evidence_graph import EvidenceGraph, EvidenceItem
from .insight_ranker import RankedInsight
from .visual_compiler import VisualIntent

logger = logging.getLogger(__name__)


class GroundedClaim(BaseModel):
    """Governed analytical claim bound to immutable evidence nodes."""
    model_config = ConfigDict(extra="forbid")

    claim_id: str
    evidence_ids: list[str]
    causal_type: Literal["OBSERVED", "ASSOCIATED", "INFERRED", "HYPOTHESIS"]
    claim_template: str
    rendered_text: str
    strategic_implication: str | None = None
    recommended_action: str | None = None


class StoryPlan(BaseModel):
    """Executive story plan and visual layout intent."""
    model_config = ConfigDict(extra="forbid")

    narrative_angle: str
    executive_summary: str
    hero_evidence_id: str
    supporting_evidence_ids: list[str] = Field(default_factory=list)
    claims: list[GroundedClaim] = Field(default_factory=list)
    visual_intent: VisualIntent | None = None
    generated_by: Literal["deterministic_planner", "qwen_story_planner"] = "deterministic_planner"


class StoryPlanner:
    """Plans executive storylines with deterministic evidence hydration."""

    @classmethod
    def plan_story(
        cls,
        graph: EvidenceGraph,
        ranked: list[RankedInsight],
        domain: str = "general_tabular",
    ) -> StoryPlan:
        """Constructs an evidence-grounded StoryPlan from prioritized findings."""
        if not ranked:
            return StoryPlan(
                narrative_angle="Operational Baseline Overview",
                executive_summary="Baseline operational metrics are within expected ranges.",
                hero_evidence_id="EVID-001" if graph.nodes else "none",
                supporting_evidence_ids=[],
                claims=[],
                visual_intent=None,
                generated_by="deterministic_planner",
            )

        hero = ranked[0].evidence
        supporting = [r.evidence for r in ranked[1:4]]

        # Clean business subject
        clean_subj = hero.subject
        if domain == "workforce":
            clean_subj = clean_subj.replace("Sheet1", "Attendance").replace("Leave Calculation Check", "Approved Leave")
        clean_subj = clean_subj.replace(" × ", " & ")

        # 1. Determine narrative angle in clean business language
        if domain == "workforce" and "Attendance" in clean_subj and "Leave" in clean_subj:
            angle = "Attendance & Leave: Where the gap is concentrated"
        elif hero.claim_type == "segment_difference":
            if domain == "workforce":
                angle = f"Department Disparity & Variance in {clean_subj}"
            elif domain == "environmental":
                angle = f"Regional Disparity & Station Variance in {clean_subj}"
            else:
                angle = f"Segment Disparity & Distribution Variance in {clean_subj}"
        elif hero.claim_type in ("capacity_gap", "target_gap"):
            angle = f"Operational Exposure & Capacity Deficit: {clean_subj}"
        elif hero.claim_type == "trend_change":
            angle = f"Structural Shift & Dynamic Trajectory in {clean_subj}"
        else:
            angle = f"Executive Overview: {clean_subj}"

        # 2. Build grounded claims
        claims: list[GroundedClaim] = []
        
        # Hero claim
        hero_claim_id = "CLM-001"
        hero_template = "{subject} recorded {formatted_value}, showing {difference_pct}% variance compared to {comparison}."
        if hero.difference_pct is None or hero.difference_pct == 0.0:
            hero_template = "{subject} established {formatted_value} across {population} observed records."
        elif "cross" in hero.metric.lower() or "&" in clean_subj or "×" in hero.subject:
            entity_label = "employee records" if domain == "workforce" else "records"
            hero_template = f"{{subject}} showed {{formatted_value}} consistency across common {entity_label}."
            
        hero_rendered = graph.hydrate_template(hero_template, [hero.evidence_id])
        if domain == "workforce":
            hero_rendered = hero_rendered.replace("Sheet1 × Leave Calculation Check", "Attendance & Approved Leave").replace("Sheet1", "Attendance").replace("Leave Calculation Check", "Approved Leave")
        
        claims.append(
            GroundedClaim(
                claim_id=hero_claim_id,
                evidence_ids=[hero.evidence_id],
                causal_type=hero.causal_classification,
                claim_template=hero_template,
                rendered_text=hero_rendered,
                strategic_implication=f"Focus operational attention on {clean_subj} to address identified disparity.",
                recommended_action=f"Conduct targeted review of operational drivers in {clean_subj}.",
            )
        )

        # Supporting claims
        for idx, sup in enumerate(supporting, start=2):
            clm_id = f"CLM-{idx:03d}"
            sup_template = "{subject} observed at {formatted_value}."
            if sup.difference_pct is not None and abs(sup.difference_pct) > 0:
                sup_template = "{subject} diverged by {difference_pct}% from baseline with {formatted_value}."
            sup_rendered = graph.hydrate_template(sup_template, [sup.evidence_id])
            sup_rendered = sup_rendered.replace("Sheet1 × Leave Calculation Check", "Attendance & Approved Leave").replace("Sheet1", "Attendance").replace("Leave Calculation Check", "Approved Leave")

            claims.append(
                GroundedClaim(
                    claim_id=clm_id,
                    evidence_ids=[sup.evidence_id],
                    causal_type=sup.causal_classification,
                    claim_template=sup_template,
                    rendered_text=sup_rendered,
                    strategic_implication=f"Contextual driver for overall operational balance.",
                    recommended_action=f"Verify data continuity across reporting cycles.",
                )
            )

        # 3. Formulate executive summary
        summary = (
            f"{angle}. "
            f"{hero_rendered} "
            f"Supported by {len(supporting)} related operational findings across the dataset."
        )

        # 4. Formulate visual intent
        visual_intent: VisualIntent | None = None
        if hero.claim_type == "segment_difference":
            visual_intent = VisualIntent(
                intent="compare_ranked_categories",
                metric_name=hero.metric,
                dimension_name="segment",
                unit=hero.tokens.get("unit", ""),
                priority="hero",
                purpose="Highlight significant cohort variance",
                benchmark_value=float(hero.comparison_value) if hero.comparison_value is not None else None,
                highlight_categories=[hero.subject],
            )
        elif hero.claim_type == "trend_change":
            visual_intent = VisualIntent(
                intent="trend_forecast_cone",
                metric_name=hero.metric,
                unit=hero.tokens.get("unit", ""),
                priority="hero",
                purpose="Display trajectory with projection cone",
            )

        return StoryPlan(
            narrative_angle=angle,
            executive_summary=summary,
            hero_evidence_id=hero.evidence_id,
            supporting_evidence_ids=[s.evidence_id for s in supporting],
            claims=claims,
            visual_intent=visual_intent,
            generated_by="deterministic_planner",
        )
