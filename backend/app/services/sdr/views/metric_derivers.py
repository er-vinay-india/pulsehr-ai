"""
HighView Semantic Data Refinery — Phase SDR-6
Local vs. Relational Metric Derivers

Enforces architectural boundary:
- LocalMetricDeriver: Operates within a single sheet/table at the same grain with NO JoinPlan.
- RelationalMetricDeriver: Cross-sheet derivation requiring an authorized, validated JoinPlan.
  Rejects derivation if join_plan_id is missing, unauthorized, or refers to an unsafe join.
"""

from __future__ import annotations

from typing import Any, Mapping
from app.services.sdr.contracts.views import (
    ControlledExpression,
    ExpressionOp,
    SDRAnalyticalFact,
    SDRDerivedMeasureSpec,
    compute_analytical_fact_fingerprint,
)
from app.services.sdr.contracts.relationships import SDRJoinPlan, JoinSafetyStatus
from app.services.sdr.views.expression_engine import compile_controlled_expression_to_sql, evaluate_expression_on_row


class MetricDerivationError(ValueError):
    """Raised when a metric derivation violates governance constraints."""
    pass


class LocalMetricDeriver:
    """
    Derives metrics strictly within a single sheet/table at the identical grain.
    Zero JoinPlan required. Banned from accepting cross-sheet join_plan_id.
    """

    @classmethod
    def derive_metric(
        cls,
        dataset_id: str,
        sheet_id: str,
        metric_name: str,
        expression: ControlledExpression,
        grain: str,
        unit: str | None = None,
        measure_class: str = "ADDITIVE",
        join_plan_id: str | None = None,
        source_evidence_ids: list[str] | None = None,
        unit_metadata: Mapping[str, str] | None = None,
        dataset_version: str = "v1",
        analytical_view_id: str = "",
    ) -> SDRDerivedMeasureSpec:
        """
        Creates a validated local derived measure spec.
        Enforces join_plan_id must be None.
        """
        if join_plan_id is not None:
            raise MetricDerivationError(
                f"LocalMetricDeriver forbids cross-sheet join_plan_id: '{join_plan_id}'. "
                "Use RelationalMetricDeriver for cross-table metrics."
            )

        # Validate expression and compile formula representation
        formula_sql, resolved_unit = compile_controlled_expression_to_sql(
            expression,
            unit_metadata=unit_metadata,
        )

        final_unit = unit or resolved_unit

        return SDRDerivedMeasureSpec(
            measure_name=metric_name,
            expression=expression,
            unit=final_unit,
            measure_class=measure_class,
            formula_repr=formula_sql,
        )


class RelationalMetricDeriver:
    """
    Derives metrics across multiple sheets/tables.
    MANDATORY requirement: Validated, authorized SDRJoinPlan.
    Missing join_plan_id or unsafe join status immediately blocks derivation.
    """

    @classmethod
    def derive_metric(
        cls,
        dataset_id: str,
        metric_name: str,
        expression: ControlledExpression,
        join_plan: SDRJoinPlan | None,
        result_grain: str,
        unit: str | None = None,
        measure_class: str = "ADDITIVE",
        source_evidence_ids: list[str] | None = None,
        unit_metadata: Mapping[str, str] | None = None,
        ratio_columns: set[str] | None = None,
        denominator_metadata: Mapping[str, str] | None = None,
        dataset_version: str = "v1",
        analytical_view_id: str = "",
    ) -> SDRDerivedMeasureSpec:
        """
        Creates a validated relational derived measure spec.
        Enforces presence and authorization of SDRJoinPlan.
        """
        if join_plan is None:
            raise MetricDerivationError(
                f"RelationalMetricDeriver requires an authorized SDRJoinPlan for cross-table metric '{metric_name}'. "
                "join_plan_id cannot be None or empty."
            )

        # Gate on JoinSafetyStatus
        if join_plan.safety_status not in (JoinSafetyStatus.SAFE, JoinSafetyStatus.SAFE_WITH_PREAGGREGATION):
            status_val = join_plan.safety_status.value if hasattr(join_plan.safety_status, "value") else str(join_plan.safety_status)
            raise MetricDerivationError(
                f"Cannot derive relational metric '{metric_name}' using {status_val} join plan '{join_plan.join_plan_id}'. "
                "Only SAFE or SAFE_WITH_PREAGGREGATION join plans are authorized."
            )

        formula_sql, resolved_unit = compile_controlled_expression_to_sql(
            expression,
            unit_metadata=unit_metadata,
            ratio_columns=ratio_columns,
            denominator_metadata=denominator_metadata,
        )

        final_unit = unit or resolved_unit

        return SDRDerivedMeasureSpec(
            measure_name=metric_name,
            expression=expression,
            unit=final_unit,
            measure_class=measure_class,
            formula_repr=formula_sql,
        )
