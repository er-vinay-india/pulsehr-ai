"""Dashboard Context Adapter.

Translates canonical WorkspaceContext into a question-driven DashboardPlanningContext
consumed by Adaptive Decision Dashboard and Executive Cockpit builders.
"""

from __future__ import annotations

from typing import Any
from pydantic import BaseModel, Field

from .models import (
    AlignmentStatus,
    JoinCardinality,
    QuestionDataMapping,
    RelationshipCandidate,
    SemanticColumnRole,
    WorkspaceContext,
)


class DashboardPlanningContext(BaseModel):
    """Canonical context contract consumed by Dashboard generation subsystems."""
    workspace_id: str
    domain: str
    user_objective: str
    explicit_questions: list[str] = Field(default_factory=list)
    supported_questions: list[str] = Field(default_factory=list)
    partially_supported_questions: list[str] = Field(default_factory=list)
    unsupported_questions: list[str] = Field(default_factory=list)
    question_mappings: list[QuestionDataMapping] = Field(default_factory=list)
    priority_metrics: list[str] = Field(default_factory=list)
    dimension_candidates: list[str] = Field(default_factory=list)
    time_fields: list[str] = Field(default_factory=list)
    primary_dataset_id: str | None = None
    primary_dataset_name: str = ""
    safe_relationships: list[RelationshipCandidate] = Field(default_factory=list)
    blocked_unsafe_relationships: list[RelationshipCandidate] = Field(default_factory=list)
    units: dict[str, str] = Field(default_factory=dict)
    readiness_status: str = "READY"
    reporting_period: str = "Current Period"
    suggested_widgets: list[dict[str, Any]] = Field(default_factory=list)
    context_version: int = 1


class DashboardContextAdapter:
    """Adapts WorkspaceContext into a Question-Driven DashboardPlanningContext."""

    @classmethod
    def adapt(cls, context: WorkspaceContext) -> DashboardPlanningContext:
        """Synthesizes a DashboardPlanningContext prioritizing user intent and questions."""
        primary_ds = None
        if context.primary_dataset_id:
            primary_ds = next((d for d in context.datasets if d.dataset_id == context.primary_dataset_id), None)
        if not primary_ds and context.datasets:
            primary_ds = context.datasets[0]

        # Categorize questions by support status
        supported_q: list[str] = []
        partial_q: list[str] = []
        unsupported_q: list[str] = []

        for qm in context.question_mappings:
            if qm.alignment_status == AlignmentStatus.SUPPORTED:
                supported_q.append(qm.question)
            elif qm.alignment_status == AlignmentStatus.PARTIALLY_SUPPORTED:
                partial_q.append(qm.question)
            else:
                unsupported_q.append(qm.question)

        # Split safe vs unsafe relationships
        safe_rels = [r for r in context.relationships if r.is_safe]
        unsafe_rels = [r for r in context.relationships if not r.is_safe]

        # Extract units and time fields
        units: dict[str, str] = {}
        time_fields: list[str] = []
        metrics: list[str] = []
        dimensions: list[str] = []

        for ds in context.datasets:
            for col in ds.columns:
                units[col.name] = col.semantic_unit.value
                if col.semantic_role in (SemanticColumnRole.DATE, SemanticColumnRole.TIME):
                    if col.name not in time_fields:
                        time_fields.append(col.name)
            for m in ds.metric_candidates:
                if m not in metrics:
                    metrics.append(m)
            for d in ds.dimension_candidates:
                if d not in dimensions:
                    dimensions.append(d)

        # ---------------------------------------------------------------------
        # QUESTION-DRIVEN WIDGET SYNTHESIS
        # Prioritize widgets answering explicit questions Q1, Q2, etc.
        # ---------------------------------------------------------------------
        suggested_widgets: list[dict[str, Any]] = []

        # If user asked explicit questions, build targeted widgets for supported questions first
        if context.question_mappings:
            for idx, qm in enumerate(context.question_mappings):
                if qm.alignment_status == AlignmentStatus.UNSUPPORTED:
                    continue  # Do not generate widgets for unanswerable questions

                mapped_metric = None
                mapped_dim = None

                for concept, field in qm.mapped_fields.items():
                    if field in metrics and not mapped_metric:
                        mapped_metric = field
                    elif field in dimensions and not mapped_dim:
                        mapped_dim = field

                mapped_metric = mapped_metric or (metrics[0] if metrics else "count")
                mapped_dim = mapped_dim or (dimensions[0] if dimensions else "category")

                suggested_widgets.append({
                    "widget_id": f"q_widget_{idx+1}",
                    "title": qm.question,
                    "target_question": qm.question,
                    "widget_type": "metric_breakdown_chart" if mapped_dim else "kpi_card",
                    "primary_metric": mapped_metric,
                    "breakdown_dimension": mapped_dim,
                    "alignment": qm.alignment_status.value,
                    "priority": idx + 1,
                    "rationale": f"Directly answers user question: '{qm.question}'"
                })

        # If no explicit questions or only 1, add primary metric summary tile
        if len(suggested_widgets) < 2 and metrics:
            primary_met = metrics[0]
            suggested_widgets.append({
                "widget_id": f"std_widget_primary",
                "title": f"Total {primary_met.replace('_', ' ').title()}",
                "target_question": "Overall baseline metric summary",
                "widget_type": "primary_metric_tile",
                "primary_metric": primary_met,
                "breakdown_dimension": dimensions[0] if dimensions else None,
                "alignment": "SUPPORTED",
                "priority": len(suggested_widgets) + 1,
                "rationale": f"Primary quantitative metric '{primary_met}' in {primary_ds.name if primary_ds else 'dataset'}"
            })

        return DashboardPlanningContext(
            workspace_id=context.workspace_id,
            domain=context.context_summary.domain,
            user_objective=context.user_request.normalized_objective,
            explicit_questions=context.user_request.explicit_questions,
            supported_questions=supported_q,
            partially_supported_questions=partial_q,
            unsupported_questions=unsupported_q,
            question_mappings=context.question_mappings,
            priority_metrics=metrics,
            dimension_candidates=dimensions,
            time_fields=time_fields,
            primary_dataset_id=context.primary_dataset_id,
            primary_dataset_name=primary_ds.name if primary_ds else context.context_summary.primary_dataset,
            safe_relationships=safe_rels,
            blocked_unsafe_relationships=unsafe_rels,
            units=units,
            readiness_status=context.readiness.status.value,
            reporting_period=context.time_intelligence.reporting_period,
            suggested_widgets=suggested_widgets,
            context_version=context.workspace_context_version
        )
