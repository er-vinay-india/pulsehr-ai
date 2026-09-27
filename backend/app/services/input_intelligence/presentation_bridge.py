"""WorkspaceContext to PresentationPlanningContext Adapter.

Cleanly bridges the general-purpose WorkspaceContext into the downstream
PresentationPlanningContext consumed by the Qwen Presentation Director.
Preserves user instructions, questions, constraints, domain, and data profiles.
"""

from __future__ import annotations

import logging
from typing import Any

from .models import WorkspaceContext
from ..presentation.director.director_models import (
    PresentationPlanningContext,
    SlideCountConstraint,
)

logger = logging.getLogger(__name__)


class WorkspaceToPresentationAdapter:
    """Adapts WorkspaceContext to PresentationPlanningContext."""

    @classmethod
    def adapt(
        cls,
        context: WorkspaceContext,
        theme_id: str = "bold_signal",
        evidence_ledger: list[dict[str, Any]] | None = None,
        historical_context: dict[str, Any] | None = None,
        available_charts: dict[str, bool] | None = None,
        industrial_models: dict[str, Any] | None = None
    ) -> PresentationPlanningContext:
        """Transforms WorkspaceContext into PresentationPlanningContext."""
        req = context.user_request
        summary = context.context_summary
        time_intel = context.time_intelligence

        # Parse slide count constraint from user intent constraints or raw text
        constraint = SlideCountConstraint.from_inputs(
            instructions=f"{req.raw_instruction} {' '.join(req.presentation_constraints)}"
        )

        # Baseline metrics from profiles
        baseline_benchmark = "Verified Baseline"
        dispersion_metric = "Audited Dispersion"

        if context.datasets:
            primary_ds = next((d for d in context.datasets if d.dataset_id == context.primary_dataset_id), context.datasets[0])
            if primary_ds.numeric_ranges:
                first_num = next(iter(primary_ds.numeric_ranges.values()))
                if first_num.get("mean"):
                    baseline_benchmark = f"{first_num['mean']:,.2f} Mean"
            if primary_ds.categorical_cardinality:
                first_cat = next(iter(primary_ds.categorical_cardinality.values()))
                dispersion_metric = f"{first_cat} Cohorts"

        completeness = 100.0
        if context.quality:
            completeness = max(0.0, round((1.0 - context.quality.missingness_rate) * 100.0, 1))

        snapshot_h = context.provenance.snapshot_hash if context.provenance else "sha256:000000000000"

        return PresentationPlanningContext(
            domain=summary.domain,
            objective=req.normalized_objective or f"Executive {summary.domain} Review",
            audience=req.audience or "Executive Leadership & Board",
            instructions=req.raw_instruction,
            dataset_label=summary.primary_dataset,
            total_records=summary.record_count,
            completeness_pct=completeness,
            baseline_benchmark=baseline_benchmark,
            dispersion_metric=dispersion_metric,
            reporting_period=time_intel.reporting_period,
            is_partial_year=time_intel.is_partial_year,
            dataset_profiles=[d.model_dump() for d in context.datasets],
            current_evidence=evidence_ledger or [],
            historical_context=historical_context or {"status": "empty", "results": [], "historical_decks": []},
            available_charts=available_charts or {"line_chart": True, "bar_chart": True, "donut_chart": True},
            industrial_models=industrial_models or {},
            slide_count_constraint=constraint,
            workspace_id=context.workspace_id,
            theme_id=theme_id,
            snapshot_hash=snapshot_h
        )
