"""
HighView Semantic Data Refinery — Phase SDR-9
HRIDAY SDR Controlled Adoption Bridge
Provides governed SDR facts, validated JoinPlans, and relational context to HRIDAY
while strictly preserving answer styles, prompts, personality, and model routing.
"""

from __future__ import annotations

import logging
from typing import Any

from app.services.ingestion_v2.contracts.cutover import Route
from app.services.ingestion_v2.contracts.hriday_context import (
    GovernedJoinContext,
    GovernedMetricContext,
    HridayNormalizedContext,
)
from app.services.sdr.shadow.contracts import FactIdentity
from app.services.sdr.shadow.shadow_evaluator import SDRShadowArtifactLoader

logger = logging.getLogger(__name__)


def build_sdr_hriday_context(
    query: str,
    dataset_id: str,
    v2_context: HridayNormalizedContext,
    loader: SDRShadowArtifactLoader | None = None,
) -> HridayNormalizedContext:
    """
    Builds an SDR-adopted HridayNormalizedContext envelope.
    Enforces that:
    - Route is set to Route.SDR.
    - Governed metrics include both single-table and cross-sheet SDR relational metrics.
    - Preserves V2 evidence references and formatting.
    - Zero prompt or personality modifications.
    """
    artifact_loader = loader or SDRShadowArtifactLoader()
    sdr_facts, safety_meta = artifact_loader.load_governed_facts(str(dataset_id))

    # Map governed facts to GovernedMetricContext objects
    adopted_metrics: list[GovernedMetricContext] = []
    seen_metrics: set[str] = set()

    for fact in sdr_facts:
        if fact.metric_id not in seen_metrics:
            adopted_metrics.append(
                GovernedMetricContext(
                    metric_id=fact.metric_id,
                    metric_name=fact.metric_id.replace("_", " ").title(),
                    formula=f"{fact.metric_id}",
                    unit=fact.unit or "",
                    grain=fact.grain or "DATASET",
                    denominator=str(fact.denominator) if fact.denominator is not None else None,
                )
            )
            seen_metrics.add(fact.metric_id)

    # Build governed summary lines
    summary_lines = []
    for fact in sdr_facts:
        val_str = fact.formatted_value or str(fact.value)
        unit_str = f" {fact.unit}" if fact.unit else ""
        summary_lines.append(f"{fact.metric_id}: {val_str}{unit_str}")
    sdr_catalog_summary = ". ".join(summary_lines) + "."

    # Build validated join contexts
    sdr_joins: list[GovernedJoinContext] = []
    for plan in safety_meta.get("valid_join_plans", []):
        sdr_joins.append(
            GovernedJoinContext(
                join_plan_id=plan.get("join_plan_id", "JP-UNKNOWN"),
                left_table=plan.get("left_sheet", ""),
                right_table=plan.get("right_sheet", ""),
                join_type=plan.get("join_type", "INNER"),
                join_safety=plan.get("safety_status", "SAFE"),
                requires_preaggregation=plan.get("requires_preaggregation", False),
            )
        )

    # Update decision envelope if present
    updated_decision = v2_context.route_decision
    if updated_decision:
        updated_decision = updated_decision.model_copy(
            update={
                "selected_route": Route.SDR,
                "sdr_adoption_state": "SDR_ADOPTED",
            }
        )

    return HridayNormalizedContext(
        route_selected=Route.SDR,
        route_decision=updated_decision,
        catalog_summary_text=sdr_catalog_summary if summary_lines else v2_context.catalog_summary_text,
        metrics=adopted_metrics if adopted_metrics else v2_context.metrics,
        join_plans=sdr_joins if sdr_joins else v2_context.join_plans,
        evidence_samples_json=v2_context.evidence_samples_json,
        telemetry=dict(v2_context.telemetry),
    )
