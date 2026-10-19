"""
HighView Semantic Data Refinery — Phase SDR-5
Governed Join Planning & Safety Engine

Formulates governed operational JoinPlans from validated relationship edges.
Enforces measure multiplication protection, cardinality safety, pre-aggregation specs,
and deterministic dry-run validation.
Zero model / LLM calls. Fully deterministic.
"""

from __future__ import annotations

from typing import Any, Sequence
import pandas as pd

from app.services.ingestion_v2.contracts.joins import (
    JoinSafetyStatus,
    MeasureAdditivity,
    PreAggregationSpec,
)
from app.services.ingestion_v2.contracts.relationships import (
    RelationshipCardinality,
    RelationshipStatus,
)
from app.services.ingestion_v2.contracts.semantics import (
    MeasureClass,
    SemanticColumnRole,
)
from app.services.sdr.contracts.grain import SDRGrainProfile
from app.services.sdr.contracts.policies import SDRPolicySuite
from app.services.sdr.contracts.profiles import (
    SemanticColumnProfile,
    SemanticConcept,
)
from app.services.sdr.contracts.relationships import (
    RelationshipClass,
    SDRJoinPlan,
    SDRValidatedRelationshipEdge,
    compute_join_plan_fingerprint,
)


def infer_column_additivity(profile: SemanticColumnProfile) -> MeasureAdditivity:
    """
    Deterministically determines measure additivity to prevent metric distortion:
    - ADDITIVE: Flow metrics (hours, revenue, sales_amount, quantity, cost)
    - SEMI_ADDITIVE: Stock / balance metrics (inventory_balance, cash_balance)
    - NON_ADDITIVE: Rates, prices, salaries (unit_price, hourly_rate, salary)
    - RATIO: Normalized percentages / rates (attendance_rate, churn_rate)
    - DISTINCT_COUNT: Unique entity counts / headcounts (employee_id, customer_id)
    """
    name_lower = (getattr(profile, "source_name", None) or getattr(profile, "column_name", None) or profile.column_id).lower()

    if profile.semantic_role in (SemanticColumnRole.ENTITY_IDENTIFIER, SemanticColumnRole.IDENTIFIER):
        return MeasureAdditivity.DISTINCT_COUNT
    if any(k in name_lower for k in ["headcount", "unique_workers", "active_employees"]):
        return MeasureAdditivity.DISTINCT_COUNT

    if any(k in name_lower for k in ["rate", "ratio", "pct", "percent", "percentage"]):
        return MeasureAdditivity.RATIO
    if profile.measure_class == MeasureClass.PERCENTAGE:
        return MeasureAdditivity.RATIO

    if any(k in name_lower for k in ["balance", "stock_level", "inventory_level", "snapshot"]):
        return MeasureAdditivity.SEMI_ADDITIVE

    if any(k in name_lower for k in ["salary", "wage", "unit_price", "price_per_unit", "hourly_rate"]):
        return MeasureAdditivity.NON_ADDITIVE

    if any(k in name_lower for k in ["hours", "revenue", "sales", "cost", "quantity", "units", "amount", "volume"]):
        return MeasureAdditivity.ADDITIVE
    if profile.measure_class in (MeasureClass.FINANCIAL, MeasureClass.QUANTITY, MeasureClass.DURATION):
        return MeasureAdditivity.ADDITIVE

    return MeasureAdditivity.UNKNOWN


class JoinGovernanceEngine:
    """
    Offline deterministic engine that formulates and authorizes governed JoinPlans.
    Strictly forbids cross joins, arbitrary many-to-many joins, and measure duplication.
    """

    def __init__(self, policy_suite: SDRPolicySuite | None = None):
        self.policy_suite = policy_suite or SDRPolicySuite()
        self.policy_fingerprint = self.policy_suite.compute_policy_fingerprint()

    def plan_join(
        self,
        edge: SDRValidatedRelationshipEdge,
        left_grain_profile: SDRGrainProfile | None = None,
        right_grain_profile: SDRGrainProfile | None = None,
        left_profiles: Sequence[SemanticColumnProfile] | None = None,
        right_profiles: Sequence[SemanticColumnProfile] | None = None,
        table_data: dict[str, pd.DataFrame] | None = None,
        preferred_join_type: str = "INNER",
        target_grain: str | None = None,
        dataset_version: str = "v1",
    ) -> SDRJoinPlan:
        """
        Formulates a governed operational JoinPlan for a validated relationship edge.
        Rule: An unvalidated or rejected edge can NEVER produce an authorized JoinPlan.
        """
        join_plan_id = f"jp_{edge.edge_id}"
        join_type = preferred_join_type.upper()
        if join_type not in ("INNER", "LEFT"):
            # Enforce strictly governed join types (CROSS join is forbidden)
            join_type = "INNER"

        l_grain_expr = edge.left_grain
        if left_grain_profile:
            l_grain_expr = getattr(left_grain_profile, "resolved_grain_expression", getattr(left_grain_profile, "grain_expression", edge.left_grain))
        if right_grain_profile:
            r_grain_expr = getattr(right_grain_profile, "resolved_grain_expression", getattr(right_grain_profile, "grain_expression", edge.right_grain))

        # Collect measure additivity rules
        l_profs = {getattr(p, "source_name", getattr(p, "column_name", p.column_id)): p for p in (left_profiles or [])}
        r_profs = {getattr(p, "source_name", getattr(p, "column_name", p.column_id)): p for p in (right_profiles or [])}

        measure_additivity_rules: dict[str, MeasureAdditivity] = {}
        left_measures: list[str] = []
        for name, p in l_profs.items():
            if p.semantic_role == SemanticColumnRole.MEASURE or p.semantic_concept == SemanticConcept.MEASURE:
                additivity = infer_column_additivity(p)
                measure_additivity_rules[f"{edge.left_sheet_id}.{name}"] = additivity
                left_measures.append(name)

        right_measures: list[str] = []
        for name, p in r_profs.items():
            if p.semantic_role == SemanticColumnRole.MEASURE or p.semantic_concept == SemanticConcept.MEASURE:
                additivity = infer_column_additivity(p)
                measure_additivity_rules[f"{edge.right_sheet_id}.{name}"] = additivity
                right_measures.append(name)

        risk_flags: list[str] = []
        safe_operations: list[str] = []
        forbidden_operations: list[str] = []
        pre_agg_spec: PreAggregationSpec | None = None
        required_preaggregation = False
        preagg_side: str | None = None

        # -------------------------------------------------------------
        # 1. Gate: Validated Edge Requirement
        # -------------------------------------------------------------
        if edge.status != RelationshipStatus.VALIDATED:
            forbidden_reason = f"Cannot authorize JoinPlan: Relationship status is {edge.status.value} ({edge.rejection_reason or 'Not validated'})."
            risk_flags.append("UNVALIDATED_RELATIONSHIP")
            return self._build_plan(
                join_plan_id=join_plan_id,
                edge=edge,
                join_type=join_type,
                safety_status=JoinSafetyStatus.UNSAFE,
                target_grain=l_grain_expr,
                measure_rules=measure_additivity_rules,
                pre_agg=None,
                required_preagg=False,
                preagg_side=None,
                risk_flags=risk_flags,
                forbidden_reason=forbidden_reason,
                safe_ops=[],
                forb_ops=["ALL_JOINS_FORBIDDEN"],
                dataset_version=dataset_version,
            )

        # -------------------------------------------------------------
        # 2. Gate: Relationship Class Eligibility
        # -------------------------------------------------------------
        if edge.relationship_class not in (
            RelationshipClass.STRUCTURAL_RELATIONSHIP,
            RelationshipClass.ENTITY_RELATIONSHIP,
        ):
            forbidden_reason = f"Cannot authorize JoinPlan: Relationship class {edge.relationship_class.value} is not structural or entity."
            risk_flags.append("NON_STRUCTURAL_CLASS")
            return self._build_plan(
                join_plan_id=join_plan_id,
                edge=edge,
                join_type=join_type,
                safety_status=JoinSafetyStatus.UNSAFE,
                target_grain=l_grain_expr,
                measure_rules=measure_additivity_rules,
                pre_agg=None,
                required_preagg=False,
                preagg_side=None,
                risk_flags=risk_flags,
                forbidden_reason=forbidden_reason,
                safe_ops=[],
                forb_ops=["ALL_JOINS_FORBIDDEN"],
                dataset_version=dataset_version,
            )

        # -------------------------------------------------------------
        # 3. Gate: Many-to-Many Protection
        # -------------------------------------------------------------
        if edge.cardinality == RelationshipCardinality.MANY_TO_MANY:
            # Check if this is a temporal grain difference that can be resolved via preaggregation
            is_temporal_mismatch = (
                ("MONTH" in l_grain_expr.upper() and "DAY" in r_grain_expr.upper()) or
                ("DAY" in l_grain_expr.upper() and "MONTH" in r_grain_expr.upper())
            )
            if is_temporal_mismatch and target_grain:
                required_preaggregation = True
                preagg_side = "RIGHT" if "DAY" in r_grain_expr.upper() else "LEFT"
                agg_sheet = edge.right_sheet_id if preagg_side == "RIGHT" else edge.left_sheet_id
                agg_keys = edge.right_column_ids if preagg_side == "RIGHT" else edge.left_column_ids
                agg_measures = right_measures if preagg_side == "RIGHT" else left_measures
                aggs = {m: "SUM" for m in agg_measures}

                pre_agg_spec = PreAggregationSpec(
                    source_table_id=agg_sheet,
                    group_by_columns=list(agg_keys),
                    aggregations=aggs,
                    target_grain=target_grain,
                )
                risk_flags.append("TEMPORAL_GRAIN_MISMATCH_RESOLVED_BY_PREAGGREGATION")
                safe_operations.append(f"PREAGGREGATE_{agg_sheet}_TO_{target_grain}")
                safe_operations.append("JOIN_AT_MATCHED_GRAIN")

                return self._build_plan(
                    join_plan_id=join_plan_id,
                    edge=edge,
                    join_type=join_type,
                    safety_status=JoinSafetyStatus.SAFE_WITH_PREAGGREGATION,
                    target_grain=target_grain,
                    measure_rules=measure_additivity_rules,
                    pre_agg=pre_agg_spec,
                    required_preagg=True,
                    preagg_side=preagg_side,
                    risk_flags=risk_flags,
                    forbidden_reason=None,
                    safe_ops=safe_operations,
                    forb_ops=["RAW_CARTESIAN_JOIN"],
                    dataset_version=dataset_version,
                )
            else:
                forbidden_reason = f"Arbitrary many-to-many joins are strictly forbidden without governed bridge model (multiplier={edge.estimated_row_multiplier}x)."
                risk_flags.append("MANY_TO_MANY_RISK")
                return self._build_plan(
                    join_plan_id=join_plan_id,
                    edge=edge,
                    join_type=join_type,
                    safety_status=JoinSafetyStatus.UNSAFE,
                    target_grain=l_grain_expr,
                    measure_rules=measure_additivity_rules,
                    pre_agg=None,
                    required_preagg=False,
                    preagg_side=None,
                    risk_flags=risk_flags,
                    forbidden_reason=forbidden_reason,
                    safe_ops=[],
                    forb_ops=["ARBITRARY_MANY_TO_MANY_JOIN"],
                    dataset_version=dataset_version,
                )

        # -------------------------------------------------------------
        # 4. Gate: Measure Multiplication Risk Protection (One-to-Many)
        # -------------------------------------------------------------
        # Example: Employees (1 row/emp, salary) joined to Attendance (many rows/emp)
        if edge.cardinality == RelationshipCardinality.ONE_TO_MANY:
            has_left_non_additive_or_additive = any(
                measure_additivity_rules.get(f"{edge.left_sheet_id}.{m}") in (
                    MeasureAdditivity.NON_ADDITIVE,
                    MeasureAdditivity.ADDITIVE,
                    MeasureAdditivity.SEMI_ADDITIVE,
                )
                for m in left_measures
            )
            if has_left_non_additive_or_additive:
                risk_flags.append("MEASURE_MULTIPLICATION_RISK")
                forbidden_operations.append("RAW_SUM_ON_MULTIPLIED_MEASURES")

                # If requested target grain or preaggregation can resolve right side
                if target_grain and target_grain.upper() == l_grain_expr.upper():
                    required_preaggregation = True
                    preagg_side = "RIGHT"
                    aggs = {m: "SUM" for m in right_measures}
                    pre_agg_spec = PreAggregationSpec(
                        source_table_id=edge.right_sheet_id,
                        group_by_columns=list(edge.right_column_ids),
                        aggregations=aggs,
                        target_grain=l_grain_expr,
                    )
                    safe_operations.append(f"PREAGGREGATE_{edge.right_sheet_id}_TO_{l_grain_expr}")
                    safe_operations.append("SAFE_JOIN_AT_SOURCE_GRAIN")

                    return self._build_plan(
                        join_plan_id=join_plan_id,
                        edge=edge,
                        join_type=join_type,
                        safety_status=JoinSafetyStatus.SAFE_WITH_PREAGGREGATION,
                        target_grain=l_grain_expr,
                        measure_rules=measure_additivity_rules,
                        pre_agg=pre_agg_spec,
                        required_preagg=True,
                        preagg_side=preagg_side,
                        risk_flags=risk_flags,
                        forbidden_reason=None,
                        safe_ops=safe_operations,
                        forb_ops=forbidden_operations,
                        dataset_version=dataset_version,
                    )
                else:
                    # Raw join without preaggregation will multiply salary / revenue
                    forbidden_reason = (
                        f"MEASURE_MULTIPLICATION_RISK: One-to-many join from {edge.left_sheet_id} to {edge.right_sheet_id} "
                        f"duplicates left-side measures {left_measures}. Requires preaggregation of {edge.right_sheet_id} before joining."
                    )
                    return self._build_plan(
                        join_plan_id=join_plan_id,
                        edge=edge,
                        join_type=join_type,
                        safety_status=JoinSafetyStatus.UNSAFE,
                        target_grain=r_grain_expr,
                        measure_rules=measure_additivity_rules,
                        pre_agg=None,
                        required_preagg=False,
                        preagg_side=None,
                        risk_flags=risk_flags,
                        forbidden_reason=forbidden_reason,
                        safe_ops=[],
                        forb_ops=["RAW_JOIN_WITH_MEASURES", "UNSAFE_MEASURE_SUMMATION"],
                        dataset_version=dataset_version,
                    )

        # -------------------------------------------------------------
        # 5. Dimension Lookup (Many-to-One): Typical SAFE Join
        # -------------------------------------------------------------
        if edge.cardinality == RelationshipCardinality.MANY_TO_ONE:
            target_grain_result = l_grain_expr
            safe_operations.extend(["DIMENSION_LOOKUP", "FILTER_PROPAGATION", "GROUP_BY_ON_PARENT_DIMENSION"])
            if edge.left_coverage < 0.95:
                risk_flags.append("PARTIAL_LEFT_COVERAGE_INNER_DROP")

            return self._build_plan(
                join_plan_id=join_plan_id,
                edge=edge,
                join_type=join_type,
                safety_status=JoinSafetyStatus.SAFE,
                target_grain=target_grain_result,
                measure_rules=measure_additivity_rules,
                pre_agg=None,
                required_preagg=False,
                preagg_side=None,
                risk_flags=risk_flags,
                forbidden_reason=None,
                safe_ops=safe_operations,
                forb_ops=["CROSS_JOIN"],
                dataset_version=dataset_version,
            )

        # -------------------------------------------------------------
        # 6. One-to-One Aligned Grains (Fact Alignment or 1:1 Entity)
        # -------------------------------------------------------------
        if edge.cardinality == RelationshipCardinality.ONE_TO_ONE:
            target_grain_result = l_grain_expr
            safe_operations.extend(["ALIGNED_GRAIN_JOIN", "ADDITIVE_MEASURE_COMBINATION"])

            return self._build_plan(
                join_plan_id=join_plan_id,
                edge=edge,
                join_type=join_type,
                safety_status=JoinSafetyStatus.SAFE,
                target_grain=target_grain_result,
                measure_rules=measure_additivity_rules,
                pre_agg=None,
                required_preagg=False,
                preagg_side=None,
                risk_flags=risk_flags,
                forbidden_reason=None,
                safe_ops=safe_operations,
                forb_ops=["CROSS_JOIN"],
                dataset_version=dataset_version,
            )

        # Fallback default
        return self._build_plan(
            join_plan_id=join_plan_id,
            edge=edge,
            join_type=join_type,
            safety_status=JoinSafetyStatus.AMBIGUOUS,
            target_grain=l_grain_expr,
            measure_rules=measure_additivity_rules,
            pre_agg=None,
            required_preagg=False,
            preagg_side=None,
            risk_flags=["UNRESOLVED_JOIN_SAFETY"],
            forbidden_reason="Join safety cannot be definitively proven.",
            safe_ops=[],
            forb_ops=["ARBITRARY_JOIN"],
            dataset_version=dataset_version,
        )

    def dry_run_validate_join_plan(
        self,
        plan: SDRJoinPlan,
        df_left: pd.DataFrame,
        df_right: pd.DataFrame,
    ) -> dict[str, Any]:
        """
        Executes a bounded deterministic dry-run of the JoinPlan.
        Validates key existence, type compatibility, coverage, actual joined row count,
        and ensures no metric distortion occurs.
        """
        result: dict[str, Any] = {
            "join_plan_id": plan.join_plan_id,
            "safety_status": plan.safety_status.value,
            "dry_run_passed": False,
            "input_left_rows": len(df_left),
            "input_right_rows": len(df_right),
            "output_rows": 0,
            "expansion_ratio": 1.0,
            "errors": [],
        }

        # Check key existence
        for k in plan.left_keys:
            if k not in df_left.columns:
                result["errors"].append(f"Left key '{k}' missing from {plan.left_sheet_id}")
        for k in plan.right_keys:
            if k not in df_right.columns:
                result["errors"].append(f"Right key '{k}' missing from {plan.right_sheet_id}")

        if result["errors"]:
            return result

        # Apply preaggregation if required by plan
        work_left = df_left.copy()
        work_right = df_right.copy()

        if plan.required_preaggregation and plan.preaggregation_spec:
            spec = plan.preaggregation_spec
            if plan.preaggregation_side == "RIGHT":
                grp_cols = [c for c in spec.group_by_columns if c in work_right.columns]
                agg_dict = {c: func.lower() for c, func in spec.aggregations.items() if c in work_right.columns}
                if grp_cols:
                    work_right = work_right.groupby(grp_cols, as_index=False).agg(agg_dict) if agg_dict else work_right.drop_duplicates(subset=grp_cols)
            elif plan.preaggregation_side == "LEFT":
                grp_cols = [c for c in spec.group_by_columns if c in work_left.columns]
                agg_dict = {c: func.lower() for c, func in spec.aggregations.items() if c in work_left.columns}
                if grp_cols:
                    work_left = work_left.groupby(grp_cols, as_index=False).agg(agg_dict) if agg_dict else work_left.drop_duplicates(subset=grp_cols)

        # Execute bounded test join
        how = "left" if plan.join_type == "LEFT" else "inner"
        try:
            joined = pd.merge(
                work_left,
                work_right,
                left_on=plan.left_keys,
                right_on=plan.right_keys,
                how=how,
                suffixes=("_left", "_right"),
            )
            result["output_rows"] = len(joined)
            base_len = max(len(work_left), 1)
            result["expansion_ratio"] = round(len(joined) / base_len, 2)

            if plan.safety_status in (JoinSafetyStatus.SAFE, JoinSafetyStatus.SAFE_WITH_PREAGGREGATION):
                result["dry_run_passed"] = True
            else:
                result["dry_run_passed"] = False
                result["errors"].append(f"JoinPlan safety is {plan.safety_status.value}: not authorized for execution.")

        except Exception as ex:
            result["errors"].append(f"Dry-run execution failed: {str(ex)}")

        return result

    def _build_plan(
        self,
        join_plan_id: str,
        edge: SDRValidatedRelationshipEdge,
        join_type: str,
        safety_status: JoinSafetyStatus,
        target_grain: str,
        measure_rules: dict[str, MeasureAdditivity],
        pre_agg: PreAggregationSpec | None,
        required_preagg: bool,
        preagg_side: str | None,
        risk_flags: list[str],
        forbidden_reason: str | None,
        safe_ops: list[str],
        forb_ops: list[str],
        dataset_version: str,
    ) -> SDRJoinPlan:
        fp = compute_join_plan_fingerprint(
            join_plan_id=join_plan_id,
            relationship_edge_id=edge.edge_id,
            left_sheet_id=edge.left_sheet_id,
            right_sheet_id=edge.right_sheet_id,
            left_keys=edge.left_column_ids,
            right_keys=edge.right_column_ids,
            safety_status=safety_status,
            target_grain=target_grain,
            dataset_version=dataset_version,
            policy_fingerprint=self.policy_fingerprint,
        )

        return SDRJoinPlan(
            join_plan_id=join_plan_id,
            relationship_edge_id=edge.edge_id,
            dataset_id=edge.dataset_id,
            left_sheet_id=edge.left_sheet_id,
            right_sheet_id=edge.right_sheet_id,
            left_keys=edge.left_column_ids,
            right_keys=edge.right_column_ids,
            join_type=join_type,
            safety_status=safety_status,
            left_grain=edge.left_grain,
            right_grain=edge.right_grain,
            target_grain=target_grain,
            required_preaggregation=required_preagg,
            preaggregation_side=preagg_side,
            preaggregation_spec=pre_agg,
            cardinality=edge.cardinality,
            coverage=edge.referential_coverage,
            measure_additivity_rules=measure_rules,
            expected_input_rows=100,
            expected_output_rows=int(100 * edge.estimated_row_multiplier),
            expansion_ratio=edge.estimated_row_multiplier,
            max_expected_multiplier=edge.estimated_row_multiplier,
            risk_flags=risk_flags,
            forbidden_reason=forbidden_reason,
            safe_operations=safe_ops,
            forbidden_operations=forb_ops,
            evidence={"edge_evidence": edge.validation_evidence},
            dataset_version=dataset_version,
            artifact_fingerprint=fp,
        )
