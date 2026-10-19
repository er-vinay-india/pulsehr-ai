"""
HighView Semantic Data Refinery — Phase SDR-6
Governed Analytical View Engine

Orchestrates:
1. Dry-run validation of AnalyticalViewSpec before execution.
2. Safe multi-sheet reconstruction via SDRDuckDBExecutor.
3. Production of reproducible, governed SDRAnalyticalFact records with immutable provenance.
4. Dependency invalidation checking.
"""

from __future__ import annotations

import logging
from typing import Any, Mapping, Sequence
import pandas as pd

from app.services.sdr.contracts.relationships import SDRJoinPlan, JoinSafetyStatus
from app.services.sdr.contracts.views import (
    ControlledExpression,
    ExpressionOp,
    MaterializationMode,
    SDRAnalyticalExecutionResult,
    SDRAnalyticalFact,
    SDRAnalyticalViewSpec,
    SDRAnalyticalViewStatus,
    check_analytical_view_invalidation,
    compute_analytical_fact_fingerprint,
)
from app.services.sdr.views.duckdb_executor import GovernedAnalyticalExecutionError, SDRDuckDBExecutor
from app.services.sdr.views.expression_engine import (
    RatioAggregationTrapError,
    UnitConflictError,
    compile_controlled_expression_to_sql,
)

logger = logging.getLogger(__name__)


class SDRAnalyticalViewEngine:
    """
    Governed Analytical View Engine for Phase SDR-6.
    Ensures safe join execution, grain preservation, and fact provenance.
    """

    def __init__(self, executor: SDRDuckDBExecutor | None = None):
        self.executor = executor or SDRDuckDBExecutor()

    def dry_run_validate(
        self,
        view_spec: SDRAnalyticalViewSpec,
        source_tables: Mapping[str, Any],
        join_plans_by_id: Mapping[str, SDRJoinPlan] | None = None,
    ) -> tuple[bool, str | None]:
        """
        Validates all view prerequisites BEFORE materialization or execution.
        Returns (is_valid, error_reason).
        """
        plans = dict(join_plans_by_id or {})

        # 1. Source sheets existence
        for sheet_id in view_spec.source_sheet_ids:
            if sheet_id not in source_tables:
                return False, f"Missing source table data for sheet '{sheet_id}'"

        # 2. JoinPlans safety validation
        if len(view_spec.source_sheet_ids) > 1:
            if not view_spec.join_plan_ids:
                return False, f"Multi-sheet view '{view_spec.analytical_view_id}' requires JoinPlan IDs"
            for jid in view_spec.join_plan_ids:
                plan = plans.get(jid)
                if not plan:
                    return False, f"JoinPlan '{jid}' not found"
                if plan.safety_status not in (JoinSafetyStatus.SAFE, JoinSafetyStatus.SAFE_WITH_PREAGGREGATION):
                    status_str = plan.safety_status.value if hasattr(plan.safety_status, "value") else str(plan.safety_status)
                    return False, f"JoinPlan '{jid}' is {status_str} (Execution Blocked)"

        # 3. Unit and Ratio Validation on Derived Measures
        ratio_cols = set(view_spec.denominator_metadata.keys())
        for der in view_spec.derived_measure_specs:
            try:
                compile_controlled_expression_to_sql(
                    der.expression,
                    unit_metadata=view_spec.unit_metadata,
                    ratio_columns=ratio_cols,
                    denominator_metadata=view_spec.denominator_metadata,
                )
            except (UnitConflictError, RatioAggregationTrapError) as err:
                return False, str(err)
            except Exception as ex:
                return False, f"Expression validation failed for '{der.measure_name}': {ex}"

        # 4. Result grain declared
        if not view_spec.result_grain or view_spec.result_grain.strip() == "":
            return False, "Result grain cannot be omitted"

        return True, None

    def execute_and_reconstruct(
        self,
        view_spec: SDRAnalyticalViewSpec,
        source_tables: Mapping[str, pd.DataFrame | list[dict[str, Any]]],
        join_plans_by_id: Mapping[str, SDRJoinPlan] | None = None,
    ) -> tuple[SDRAnalyticalExecutionResult, list[SDRAnalyticalFact]]:
        """
        Performs dry run validation, executes view in DuckDB, and emits reproducible SDRAnalyticalFact records.
        """
        # Step 1: Dry run preflight
        is_valid, err = self.dry_run_validate(view_spec, source_tables, join_plans_by_id)
        if not is_valid:
            blocked_status = SDRAnalyticalViewStatus.UNSAFE
            if "AMBIGUOUS" in (err or ""):
                blocked_status = SDRAnalyticalViewStatus.AMBIGUOUS
            result = SDRAnalyticalExecutionResult(
                view_id=view_spec.analytical_view_id,
                status=blocked_status,
                row_count=0,
                result_grain=view_spec.result_grain,
                error_message=f"Dry run preflight failed: {err}",
            )
            return result, []

        # Step 2: Execute in DuckDB
        result = self.executor.execute_view(view_spec, source_tables, join_plans_by_id)
        if result.status == SDRAnalyticalViewStatus.UNSAFE:
            return result, []

        # Step 3: Produce governed SDRAnalyticalFact records
        facts: list[SDRAnalyticalFact] = []
        for metric_name, m_res in result.measure_results.items():
            val = m_res.get("sum") if m_res.get("sum") is not None else m_res.get("mean")
            unit_val = view_spec.unit_metadata.get(metric_name)

            # Determine provenance type
            prov_type = "OBSERVED"
            if view_spec.provenance.get("derived_enrichment"):
                prov_type = "DERIVED_ENRICHMENT"
            elif view_spec.join_plan_ids:
                prov_type = "DERIVED_RELATIONAL"
            elif any(d.measure_name == metric_name for d in view_spec.derived_measure_specs):
                prov_type = "DERIVED_LOCAL"

            denom_val = None
            if metric_name in view_spec.denominator_metadata:
                denom_col = view_spec.denominator_metadata[metric_name]
                if denom_col in result.measure_results:
                    denom_val = result.measure_results[denom_col].get("sum")

            fact_fp = compute_analytical_fact_fingerprint(
                dataset_id=view_spec.dataset_id,
                dataset_version=view_spec.dataset_version,
                analytical_view_id=view_spec.analytical_view_id,
                metric=metric_name,
                value=val,
                unit=unit_val,
                grain=view_spec.result_grain,
                denominator_value=denom_val,
                source_evidence_ids=view_spec.provenance.get("source_evidence_ids", []),
                join_plan_ids=view_spec.join_plan_ids,
                provenance_type=prov_type,
            )

            fact_id = f"FACT-{view_spec.dataset_id}-{metric_name}-{fact_fp[:8]}"
            formatted = f"{val:.2f}" if isinstance(val, (int, float)) else str(val)
            if unit_val:
                formatted = f"{formatted} {unit_val}"

            fact = SDRAnalyticalFact(
                fact_id=fact_id,
                metric=metric_name,
                value=val,
                formatted_value=formatted,
                unit=unit_val,
                grain=view_spec.result_grain,
                denominator_value=denom_val,
                dataset_id=view_spec.dataset_id,
                dataset_version=view_spec.dataset_version,
                source_evidence_ids=view_spec.provenance.get("source_evidence_ids", []),
                analytical_view_id=view_spec.analytical_view_id,
                join_plan_ids=view_spec.join_plan_ids,
                provenance_type=prov_type,
                tokens={"count": m_res.get("count"), "mean": m_res.get("mean")},
                artifact_fingerprint=fact_fp,
            )
            facts.append(fact)

        return result, facts
