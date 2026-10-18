"""
HighView Ingestion V2 — Phase I4: Join Planner
Stage: Governed Join Planning

Formulates governed JoinPlans specifying target grain, pre-aggregations, measure additivity rules,
and permitted/forbidden operations.
Zero join execution (planning only). Zero model / LLM calls. Fully deterministic.
"""

from __future__ import annotations

import re
from typing import Sequence
import pandas as pd

from app.services.ingestion_v2.contracts.grain import GrainProfile, TableGrainProfile
from app.services.ingestion_v2.contracts.joins import (
    GovernedJoinPlanSet,
    JoinPlan,
    JoinSafetyAssessment,
    JoinSafetyStatus,
    MeasureAdditivity,
    PreAggregationSpec,
)
from app.services.ingestion_v2.contracts.normalization import NormalizedDataset
from app.services.ingestion_v2.contracts.profiling import StructuralProfile
from app.services.ingestion_v2.contracts.relationships import (
    CandidateKeyType,
    RelationshipCardinality,
    RelationshipStatus,
    ValidatedRelationshipEdge,
)
from app.services.ingestion_v2.contracts.semantics import (
    MeasureClass,
    SemanticColumnAssignment,
    SemanticColumnRole,
    SemanticModel,
    TableSemanticModel,
)
from app.services.ingestion_v2.joins.join_safety import JoinSafetyAnalyzer


def infer_measure_additivity(
    col_name: str,
    assignment: SemanticColumnAssignment | None,
) -> MeasureAdditivity:
    """
    Deterministically infer measure additivity to protect against metric distortion:
    - ADDITIVE: Flow metrics (hours_worked, revenue, sales_amount, units_sold)
    - SEMI_ADDITIVE: Stock / balance metrics (inventory_balance, account_balance, cash_balance)
    - NON_ADDITIVE: Unit prices, continuous rates, salaries (salary, hourly_rate, unit_price)
    - RATIO: Normalized quotients (attendance_rate, churn_rate, defect_rate)
    - DISTINCT_COUNT: Headcount and unique entity counts (employee_id, customer_id)
    """
    name_lower = col_name.lower()

    c_role = getattr(assignment, "role", getattr(assignment, "semantic_role", None)) if assignment else None

    # Distinct Count protection for identifiers / headcounts
    if assignment and c_role == SemanticColumnRole.ENTITY_IDENTIFIER:
        return MeasureAdditivity.DISTINCT_COUNT
    if any(k in name_lower for k in ["headcount", "unique_workers", "active_employees"]):
        return MeasureAdditivity.DISTINCT_COUNT

    # Ratio protection
    if any(k in name_lower for k in ["rate", "ratio", "pct", "percent", "percentage"]):
        return MeasureAdditivity.RATIO
    if assignment and assignment.measure_class == MeasureClass.PERCENTAGE:
        return MeasureAdditivity.RATIO

    # Semi-additive (balances additive across entities but not across time)
    if any(k in name_lower for k in ["balance", "stock_level", "inventory_level", "headcount_snapshot"]):
        return MeasureAdditivity.SEMI_ADDITIVE

    # Non-additive unit prices and salaries
    if any(k in name_lower for k in ["salary", "wage", "unit_price", "price_per_unit", "hourly_rate"]):
        return MeasureAdditivity.NON_ADDITIVE

    # Additive flow metrics
    if any(k in name_lower for k in ["hours", "revenue", "sales", "cost", "quantity", "units", "amount", "volume"]):
        return MeasureAdditivity.ADDITIVE
    if assignment and assignment.measure_class in (MeasureClass.FINANCIAL, MeasureClass.QUANTITY, MeasureClass.DURATION):
        return MeasureAdditivity.ADDITIVE

    return MeasureAdditivity.UNKNOWN


def plan_join(
    relationship: ValidatedRelationshipEdge,
    analysis_purpose: str,
    grain_profile: GrainProfile,
    semantic_model: SemanticModel,
    structural_profile: StructuralProfile | None = None,
    target_grain: str | None = None,
    table_data: dict[str, pd.DataFrame] | None = None,
) -> JoinPlan:
    """
    Formulate a governed operational JoinPlan for a validated relationship edge.

    Rules:
    - Declares explicit target grain.
    - Specifies required pre-aggregations if grain mismatch or fanout risk exists.
    - Enforces measure additivity rules (preventing naive SUM of rates or salaries).
    - Specifies dimension propagation.
    - Declares explicit safe operations and forbidden operations.
    - Zero execution: plan is formulated without evaluating or mutating data.
    """
    grain_map: dict[str, TableGrainProfile] = {t.table_id: t for t in (getattr(grain_profile, "table_grains", None) or getattr(grain_profile, "tables", []))}
    sem_map: dict[str, TableSemanticModel] = {t.table_id: t for t in semantic_model.tables}

    s_grain_prof = grain_map.get(relationship.source_table_id)
    t_grain_prof = grain_map.get(relationship.target_table_id)

    s_grain = s_grain_prof.grain_expression if s_grain_prof else "UNKNOWN"
    t_grain = t_grain_prof.grain_expression if t_grain_prof else "UNKNOWN"

    # Assess join safety
    safety_assessment = JoinSafetyAnalyzer.assess_edge_safety(
        relationship,
        grain_profile,
        structural_profile,
        semantic_model,
        analysis_purpose=analysis_purpose,
        requested_target_grain=target_grain,
    )

    safety_status = safety_assessment.safety_status

    # Target grain resolution
    resolved_target_grain = target_grain or safety_assessment.recommended_target_grain or t_grain
    if resolved_target_grain == "UNKNOWN":
        resolved_target_grain = s_grain if s_grain != "UNKNOWN" else "COMPOSITE"

    # Resolve join keys as pairs of (source_col_name, target_col_name)
    s_sem = sem_map.get(relationship.source_table_id)
    t_sem = sem_map.get(relationship.target_table_id)

    s_sem_cols = (getattr(s_sem, "columns", None) or getattr(s_sem, "column_assignments", [])) if s_sem else []
    t_sem_cols = (getattr(t_sem, "columns", None) or getattr(t_sem, "column_assignments", [])) if t_sem else []

    join_keys = list(zip(relationship.source_column_ids, relationship.target_column_ids))

    # Join type
    if safety_status in (JoinSafetyStatus.SAFE, JoinSafetyStatus.SAFE_WITH_PREAGGREGATION):
        if safety_assessment.dimension_propagation_safe:
            join_type = "LEFT"
        else:
            join_type = "INNER"
    else:
        join_type = "LEFT"

    # Pre-aggregation specification
    pre_agg: PreAggregationSpec | None = None
    if (
        safety_status == JoinSafetyStatus.SAFE_WITH_PREAGGREGATION
        or (target_grain and target_grain != t_grain and " x " in t_grain)
        or ("PREAGGREGATION" in (analysis_purpose or "").upper())
    ):
        # Target grain determines pre-aggregation grouping
        group_cols = [relationship.target_column_ids[0]] if relationship.target_column_ids else ["employee_id"]

        # Collect aggregate measures from target table
        t_aggs: dict[str, str] = {}
        for col_assign in t_sem_cols:
            c_role = getattr(col_assign, "role", getattr(col_assign, "semantic_role", None))
            if c_role == SemanticColumnRole.MEASURE:
                additivity = infer_measure_additivity(col_assign.column_name, col_assign)
                if additivity == MeasureAdditivity.ADDITIVE:
                    t_aggs[col_assign.column_name] = "SUM"
                elif additivity == MeasureAdditivity.RATIO:
                    t_aggs[col_assign.column_name] = "AVG"
                elif additivity == MeasureAdditivity.NON_ADDITIVE:
                    t_aggs[col_assign.column_name] = "MAX"

        if not t_aggs:
            t_aggs = {"row_count": "COUNT"}

        pre_agg = PreAggregationSpec(
            source_table_id=relationship.target_table_id,
            group_by_columns=group_cols,
            aggregations=t_aggs,
            target_grain=resolved_target_grain,
        )

    # Dimension propagation
    dim_propagation: list[str] = []
    if s_sem and safety_assessment.dimension_propagation_safe:
        for c in s_sem_cols:
            c_role = getattr(c, "role", getattr(c, "semantic_role", None))
            if c_role in (SemanticColumnRole.DIMENSION, SemanticColumnRole.CATEGORY, SemanticColumnRole.ENTITY_LABEL) and \
               c.column_name not in relationship.source_column_ids:
                dim_propagation.append(c.column_name)

    # Measure additivity rules across both tables
    measure_rules: dict[str, MeasureAdditivity] = {}
    for c in s_sem_cols:
        c_role = getattr(c, "role", getattr(c, "semantic_role", None))
        if c_role in (SemanticColumnRole.MEASURE, SemanticColumnRole.ENTITY_IDENTIFIER):
            measure_rules[c.column_name] = infer_measure_additivity(c.column_name, c)
    for c in t_sem_cols:
        c_role = getattr(c, "role", getattr(c, "semantic_role", None))
        if c_role in (SemanticColumnRole.MEASURE, SemanticColumnRole.ENTITY_IDENTIFIER):
            measure_rules[c.column_name] = infer_measure_additivity(c.column_name, c)

    # Safe operations & Forbidden operations
    safe_ops: list[str] = []
    forbidden_ops: list[str] = []

    if safety_status == JoinSafetyStatus.SAFE:
        safe_ops.append(f"DIRECT_JOIN({relationship.source_table_id}, {relationship.target_table_id})")
        for dim in dim_propagation:
            safe_ops.append(f"DIMENSION_ENRICHMENT({dim})")
        for m_name, additivity in measure_rules.items():
            if additivity == MeasureAdditivity.ADDITIVE:
                safe_ops.append(f"SUM({m_name})")
            elif additivity == MeasureAdditivity.DISTINCT_COUNT:
                safe_ops.append(f"COUNT(DISTINCT {m_name})")
                forbidden_ops.append(f"COUNT({m_name}) FOR HEADCOUNT")
            elif additivity == MeasureAdditivity.RATIO:
                forbidden_ops.append(f"SUM({m_name})")
            elif additivity == MeasureAdditivity.NON_ADDITIVE:
                forbidden_ops.append(f"SUM({m_name})")

    elif safety_status == JoinSafetyStatus.SAFE_WITH_PREAGGREGATION:
        safe_ops.append("PRE_AGGREGATE_BEFORE_JOIN")
        for agg_col, agg_fn in (pre_agg.aggregations if pre_agg else {}).items():
            safe_ops.append(f"{agg_fn}(pre_aggregated.{agg_col})")
        forbidden_ops.append("DIRECT_JOIN_WITHOUT_PRE_AGGREGATION")
        for m_name, additivity in measure_rules.items():
            if additivity in (MeasureAdditivity.NON_ADDITIVE, MeasureAdditivity.RATIO):
                forbidden_ops.append(f"SUM(raw_{m_name}_after_join)")

    else:  # UNSAFE or AMBIGUOUS
        forbidden_ops.append("DIRECT_JOIN_EXECUTION")
        forbidden_ops.append(f"RAW_FANOUT_JOIN(multiplier={relationship.estimated_row_multiplier}x)")
        if safety_assessment.many_to_many_risk:
            forbidden_ops.append("MANY_TO_MANY_CARTESIAN_JOIN")

    # Row multiplier bounds
    max_multiplier = 1.0 if safety_status == JoinSafetyStatus.SAFE else relationship.estimated_row_multiplier

    # Expected rows
    left_rows = int(relationship.validation_evidence.get("left_distinct", 100))
    right_rows = int(relationship.validation_evidence.get("right_distinct", 100))
    expected_out = int(relationship.validation_evidence.get("expected_joined_rows", max(left_rows, right_rows)))

    plan_id = f"join_plan_{relationship.edge_id}"

    return JoinPlan(
        join_plan_id=plan_id,
        edge_id=relationship.edge_id,
        left_table_id=relationship.source_table_id,
        left_grain=s_grain,
        right_table_id=relationship.target_table_id,
        right_grain=t_grain,
        target_grain=resolved_target_grain,
        join_type=join_type,
        safety_status=safety_status,
        measure_additivity_rules=measure_rules,
        pre_aggregation=pre_agg,
        forbidden_reason=safety_assessment.rationale if safety_status == JoinSafetyStatus.UNSAFE else None,
        safe_operations=safe_ops,
        forbidden_operations=forbidden_ops,
        join_keys=join_keys,
        max_expected_multiplier=max_multiplier,
        expected_input_rows=left_rows + right_rows,
        expected_output_rows=expected_out,
        dimension_propagation=dim_propagation,
        post_aggregations=[],
    )
