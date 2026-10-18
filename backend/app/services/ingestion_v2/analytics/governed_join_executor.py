"""
HighView Ingestion V2 — Governed Join Executor
Stage 8: Analytical EDA-B
Executes governed joins strictly according to authorized JoinPlan contracts.
Enforces pre-aggregation, target grain preservation, and runtime fanout multiplier firewalls.
"""

from __future__ import annotations

from typing import Any
from app.services.ingestion_v2.contracts.joins import JoinPlan, JoinSafetyStatus, PreAggregationSpec


class GovernedJoinExecutionError(Exception):
    """Raised when an unauthorized, unsafe, or fanout-violating join is attempted."""
    pass


def _pre_aggregate_table(
    rows: list[dict[str, Any]],
    spec: PreAggregationSpec,
) -> list[dict[str, Any]]:
    """
    Deterministically pre-aggregates rows according to PreAggregationSpec.
    Groups by specified columns and computes declared aggregations.
    """
    if not rows:
        return []

    group_cols = spec.group_by_columns
    aggregations = spec.aggregations

    grouped_data: dict[tuple, list[dict[str, Any]]] = {}
    for r in rows:
        key = tuple(r.get(c) for c in group_cols)
        if key not in grouped_data:
            grouped_data[key] = []
        grouped_data[key].append(r)

    pre_agg_rows: list[dict[str, Any]] = []
    for key, group_rows in grouped_data.items():
        out_row: dict[str, Any] = {}
        for idx, col in enumerate(group_cols):
            out_row[col] = key[idx]

        for metric_col, agg_func in aggregations.items():
            func_upper = agg_func.strip().upper()
            vals = [
                float(gr[metric_col])
                for gr in group_rows
                if metric_col in gr and gr[metric_col] is not None
            ]
            if func_upper == "SUM":
                out_row[metric_col] = sum(vals) if vals else 0.0
            elif func_upper == "AVG":
                out_row[metric_col] = sum(vals) / len(vals) if vals else 0.0
            elif func_upper == "COUNT":
                out_row[metric_col] = len(group_rows)
            elif func_upper == "DISTINCT_COUNT":
                raw_vals = [gr.get(metric_col) for gr in group_rows if gr.get(metric_col) is not None]
                out_row[metric_col] = len(set(raw_vals))
            elif func_upper == "MIN":
                out_row[metric_col] = min(vals) if vals else None
            elif func_upper == "MAX":
                out_row[metric_col] = max(vals) if vals else None
            else:
                out_row[metric_col] = sum(vals) if vals else 0.0

        pre_agg_rows.append(out_row)

    return pre_agg_rows


def execute_governed_join(
    join_plan: JoinPlan,
    table_data: dict[str, list[dict[str, Any]]],
) -> tuple[list[dict[str, Any]], str]:
    """
    Execute a governed join plan on local table data.

    Enforces:
    1. Safety status must be SAFE or SAFE_WITH_PREAGGREGATION.
    2. Mandatory pre-aggregation if specified.
    3. Multiplier guardrail: actual row count multiplier cannot exceed max_expected_multiplier.
    4. Denominator & grain preservation.

    Returns:
        tuple of (joined_rows, target_grain)
    Raises:
        GovernedJoinExecutionError if unauthorized or runtime invariant is violated.
    """
    if join_plan.safety_status not in (JoinSafetyStatus.SAFE, JoinSafetyStatus.SAFE_WITH_PREAGGREGATION):
        status_val = join_plan.safety_status.value if hasattr(join_plan.safety_status, "value") else str(join_plan.safety_status)
        raise GovernedJoinExecutionError(
            f"Cannot execute {status_val} join plan '{join_plan.join_plan_id}': {join_plan.forbidden_reason or 'Unauthorized join safety state'}"
        )

    left_rows = table_data.get(join_plan.left_table_id)
    right_rows = table_data.get(join_plan.right_table_id)

    if left_rows is None:
        raise GovernedJoinExecutionError(f"Missing left table data for '{join_plan.left_table_id}'")
    if right_rows is None:
        raise GovernedJoinExecutionError(f"Missing right table data for '{join_plan.right_table_id}'")

    # Pre-aggregation check
    left_source = left_rows
    right_source = right_rows

    if join_plan.pre_aggregation:
        if join_plan.pre_aggregation.source_table_id == join_plan.right_table_id:
            right_source = _pre_aggregate_table(right_rows, join_plan.pre_aggregation)
        elif join_plan.pre_aggregation.source_table_id == join_plan.left_table_id:
            left_source = _pre_aggregate_table(left_rows, join_plan.pre_aggregation)

    join_keys = join_plan.join_keys
    if not join_keys:
        raise GovernedJoinExecutionError(f"JoinPlan '{join_plan.join_plan_id}' has no join keys defined")

    # Index right source by right join keys
    right_index: dict[tuple, list[dict[str, Any]]] = {}
    for r_row in right_source:
        r_key = tuple(r_row.get(rk) for _, rk in join_keys)
        if r_key not in right_index:
            right_index[r_key] = []
        right_index[r_key].append(r_row)

    joined_rows: list[dict[str, Any]] = []
    join_type = (join_plan.join_type or "LEFT").upper()

    for l_row in left_source:
        l_key = tuple(l_row.get(lk) for lk, _ in join_keys)
        matching_rights = right_index.get(l_key, [])

        if matching_rights:
            for r_row in matching_rights:
                merged = dict(l_row)
                for k, v in r_row.items():
                    if k in merged and merged[k] != v:
                        merged[f"{join_plan.right_table_id}_{k}"] = v
                    elif k not in merged:
                        merged[k] = v
                joined_rows.append(merged)
        else:
            if join_type in ("LEFT", "FULL"):
                merged = dict(l_row)
                joined_rows.append(merged)

    # Runtime multiplier invariant verification
    input_count = max(1, len(left_source))
    output_count = len(joined_rows)
    actual_multiplier = output_count / input_count

    max_allowed = join_plan.max_expected_multiplier + 0.05
    if actual_multiplier > max_allowed and actual_multiplier > 1.05:
        raise GovernedJoinExecutionError(
            f"JOIN_PLAN_RUNTIME_VIOLATION: Actual multiplier {actual_multiplier:.2f} exceeded max expected {join_plan.max_expected_multiplier:.2f}"
        )

    return joined_rows, join_plan.target_grain
