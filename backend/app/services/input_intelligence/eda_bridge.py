"""EDA Context Adapter.

Translates canonical WorkspaceContext into an EDAAnalysisContext consumed by
Exploratory Data Analysis and statistical profiling services without re-inferring semantics.
"""

from __future__ import annotations

from typing import Any
from pydantic import BaseModel, Field

from .models import (
    SemanticColumnRole,
    WorkspaceContext,
)


class EDAAnalysisContext(BaseModel):
    """Canonical context contract consumed by Exploratory Data Analysis services."""
    workspace_id: str
    domain: str
    primary_dataset_id: str | None = None
    primary_dataset_name: str = ""
    metric_candidates: list[str] = Field(default_factory=list)
    dimension_candidates: list[str] = Field(default_factory=list)
    date_fields: list[str] = Field(default_factory=list)
    semantic_roles: dict[str, str] = Field(default_factory=dict)
    units: dict[str, str] = Field(default_factory=dict)
    relationships: list[dict[str, Any]] = Field(default_factory=list)
    reporting_period: str = "Current Period"
    quality_warnings: list[str] = Field(default_factory=list)
    readiness_status: str = "READY"
    user_objective: str = ""
    prioritized_questions: list[str] = Field(default_factory=list)
    context_version: int = 1


class EDAContextAdapter:
    """Adapts WorkspaceContext for the Exploratory Data Analysis subsystem."""

    @classmethod
    def adapt(cls, context: WorkspaceContext) -> EDAAnalysisContext:
        """Constructs an EDAAnalysisContext adhering to WorkspaceContext ground truth."""
        primary_ds = None
        if context.primary_dataset_id:
            primary_ds = next((d for d in context.datasets if d.dataset_id == context.primary_dataset_id), None)
        if not primary_ds and context.datasets:
            primary_ds = context.datasets[0]

        # Gather semantic roles and units across datasets
        semantic_roles: dict[str, str] = {}
        units: dict[str, str] = {}
        date_fields: list[str] = []

        all_metrics: list[str] = []
        all_dimensions: list[str] = []

        for ds in context.datasets:
            for col in ds.columns:
                key = f"{ds.dataset_id}.{col.name}" if len(context.datasets) > 1 else col.name
                semantic_roles[key] = col.semantic_role.value
                semantic_roles[col.name] = col.semantic_role.value  # Also provide unqualified
                units[key] = col.semantic_unit.value
                units[col.name] = col.semantic_unit.value

                if col.semantic_role in (SemanticColumnRole.DATE, SemanticColumnRole.TIME):
                    if col.name not in date_fields:
                        date_fields.append(col.name)

            for m in ds.metric_candidates:
                if m not in all_metrics:
                    all_metrics.append(m)
            for d in ds.dimension_candidates:
                if d not in all_dimensions:
                    all_dimensions.append(d)

        # Quality warnings
        quality_warnings: list[str] = []
        if context.quality:
            for issue in context.quality.issues:
                msg = getattr(issue, "message", getattr(issue, "description", ""))
                quality_warnings.append(f"{issue.severity.value}: {msg}")
        for r_issue in context.readiness.issues:
            if r_issue not in quality_warnings:
                quality_warnings.append(r_issue)

        # Format relationships
        rels = []
        for r in context.relationships:
            rels.append({
                "relationship_id": r.relationship_id,
                "left_dataset_id": r.left_dataset_id,
                "left_column": r.left_column,
                "right_dataset_id": r.right_dataset_id,
                "right_column": r.right_column,
                "cardinality": r.cardinality.value,
                "is_safe": r.is_safe,
                "confidence": r.confidence,
            })

        return EDAAnalysisContext(
            workspace_id=context.workspace_id,
            domain=context.context_summary.domain,
            primary_dataset_id=context.primary_dataset_id,
            primary_dataset_name=primary_ds.name if primary_ds else context.context_summary.primary_dataset,
            metric_candidates=all_metrics,
            dimension_candidates=all_dimensions,
            date_fields=date_fields,
            semantic_roles=semantic_roles,
            units=units,
            relationships=rels,
            reporting_period=context.time_intelligence.reporting_period,
            quality_warnings=quality_warnings,
            readiness_status=context.readiness.status.value,
            user_objective=context.user_request.normalized_objective,
            prioritized_questions=context.user_request.explicit_questions,
            context_version=context.workspace_context_version
        )
