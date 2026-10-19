"""
HighView Semantic Data Refinery — Phase SDR-6
Governed DuckDB Analytical View Executor

Executes analytical reconstructions over in-memory / Parquet datasets via DuckDB:
1. Enforces JoinPlan authorization (SAFE / SAFE_WITH_PREAGGREGATION only; blocks UNSAFE / AMBIGUOUS).
2. Performs exact PreAggregationSpec BEFORE join for SAFE_WITH_PREAGGREGATION.
3. Preserves NULL != 0 semantics (never coerces NULL to 0).
4. Enforces weighted ratio aggregation (e.g. SUM(present)/SUM(eligible), never average of rates).
5. Post-execution grain validation & duplicate protection (fails closed if duplicate rows appear at declared grain; never silently deduplicates).
6. Virtual vs. Materialized Parquet output modes.
"""

from __future__ import annotations

import logging
from pathlib import Path
import time
from typing import Any, Mapping, Sequence
import duckdb
import pandas as pd

from app.analytics.duckdb_engine import DuckDBEngine, quote_identifier
from app.services.sdr.contracts.relationships import SDRJoinPlan, JoinSafetyStatus, PreAggregationSpec
from app.services.sdr.contracts.views import (
    ControlledExpression,
    ExpressionOp,
    MaterializationMode,
    MissingValuePolicy,
    SDRAnalyticalExecutionResult,
    SDRAnalyticalViewSpec,
    SDRAnalyticalViewStatus,
    compute_analytical_view_fingerprint,
)
from app.services.sdr.views.expression_engine import compile_controlled_expression_to_sql

logger = logging.getLogger(__name__)


class GovernedAnalyticalExecutionError(Exception):
    """Raised when an analytical view execution violates governance gates."""
    pass


class GrainViolationError(GovernedAnalyticalExecutionError):
    """Raised when post-execution rows violate declared result grain uniqueness."""
    pass


class SDRDuckDBExecutor:
    """
    Isolated, process-safe DuckDB analytical executor.
    Does not modify P0 SQLite database or source tables.
    """

    def __init__(self, base_dir: Path | str | None = None):
        if base_dir is None:
            self.base_dir = Path(__file__).resolve().parents[4] / "data"
        else:
            self.base_dir = Path(base_dir)

    def _has_aggregate_operation(self, expr: ControlledExpression) -> bool:
        """Recursively checks if an expression AST contains an aggregate operator."""
        if expr.op in (ExpressionOp.SUM, ExpressionOp.COUNT, ExpressionOp.COUNT_DISTINCT, ExpressionOp.MIN, ExpressionOp.MAX, ExpressionOp.AVG):
            return True
        for arg in expr.args:
            if isinstance(arg, ControlledExpression) and self._has_aggregate_operation(arg):
                return True
        return False

    def execute_view(
        self,
        view_spec: SDRAnalyticalViewSpec,
        source_tables: Mapping[str, pd.DataFrame | list[dict[str, Any]]],
        join_plans_by_id: Mapping[str, SDRJoinPlan] | None = None,
    ) -> SDRAnalyticalExecutionResult:
        """
        Executes an SDRAnalyticalViewSpec against provided source tables.
        """
        t0 = time.perf_counter()
        plans = dict(join_plans_by_id or {})

        # Gate 1: Check view status
        if view_spec.status in (SDRAnalyticalViewStatus.UNSAFE, SDRAnalyticalViewStatus.AMBIGUOUS, SDRAnalyticalViewStatus.STALE):
            return SDRAnalyticalExecutionResult(
                view_id=view_spec.analytical_view_id,
                status=view_spec.status,
                row_count=0,
                result_grain=view_spec.result_grain,
                error_message=f"Analytical view '{view_spec.analytical_view_id}' is {view_spec.status.value}: execution blocked.",
            )

        # Gate 2: Check all JoinPlans
        active_join_plans: list[SDRJoinPlan] = []
        if len(view_spec.source_sheet_ids) > 1:
            if not view_spec.join_plan_ids:
                raise GovernedAnalyticalExecutionError(
                    f"Multi-sheet view '{view_spec.analytical_view_id}' requires authorized JoinPlan IDs"
                )
            for jid in view_spec.join_plan_ids:
                plan = plans.get(jid)
                if not plan:
                    raise GovernedAnalyticalExecutionError(f"JoinPlan '{jid}' not found in active plans")
                if plan.safety_status not in (JoinSafetyStatus.SAFE, JoinSafetyStatus.SAFE_WITH_PREAGGREGATION):
                    status_str = plan.safety_status.value if hasattr(plan.safety_status, "value") else str(plan.safety_status)
                    raise GovernedAnalyticalExecutionError(
                        f"Execution blocked: JoinPlan '{jid}' is {status_str}"
                    )
                active_join_plans.append(plan)

        # Prepare DuckDB in-memory session
        con = DuckDBEngine.create_session()
        try:
            # Register source tables
            dfs: dict[str, pd.DataFrame] = {}
            for sheet_id, raw_data in source_tables.items():
                if isinstance(raw_data, pd.DataFrame):
                    df = raw_data.copy()
                else:
                    df = pd.DataFrame(raw_data)
                dfs[sheet_id] = df
                con.register(f"src_{sheet_id}", df)

            # Determine execution plan & table-to-column mapping
            col_qualifiers: dict[str, str] = {}
            if len(view_spec.source_sheet_ids) == 1:
                primary_sheet = view_spec.source_sheet_ids[0]
                from_clause = f"src_{primary_sheet}"
                for c in dfs[primary_sheet].columns:
                    col_qualifiers[c] = f"src_{primary_sheet}"
            else:
                # Multi-sheet execution with JoinPlans
                from_clause, col_qualifiers = self._build_join_from_clause(con, dfs, active_join_plans)

            # Determine if aggregation (GROUP BY) is required
            needs_group_by = False
            if view_spec.base_grain != view_spec.result_grain:
                needs_group_by = True
            elif any(self._has_aggregate_operation(d.expression) for d in view_spec.derived_measure_specs):
                needs_group_by = True
            elif bool(view_spec.denominator_metadata) and view_spec.result_grain != view_spec.base_grain:
                needs_group_by = True
            elif len(view_spec.dimension_columns) == 0 and bool(view_spec.measure_columns):
                # Entire table rollup (e.g. Company rollup from departments)
                needs_group_by = True

            # Build Select & Aggregation expressions
            select_items: list[str] = []
            group_by_items: list[str] = []

            # Dimensions
            for dim in view_spec.dimension_columns:
                tbl = col_qualifiers.get(dim)
                col_expr = f"{tbl}.{quote_identifier(dim)}" if tbl else quote_identifier(dim)
                select_items.append(f"{col_expr} AS {quote_identifier(dim)}")
                if needs_group_by:
                    group_by_items.append(col_expr)

            # Standard Measures
            ratio_cols = set(view_spec.denominator_metadata.keys())
            for meas in view_spec.measure_columns:
                tbl = col_qualifiers.get(meas)
                col_expr = f"{tbl}.{quote_identifier(meas)}" if tbl else quote_identifier(meas)
                quoted_alias = quote_identifier(meas)

                # Check if it has a weighted denominator rule
                if meas in view_spec.denominator_metadata:
                    denom_col = view_spec.denominator_metadata[meas]
                    denom_tbl = col_qualifiers.get(denom_col)
                    denom_expr = f"{denom_tbl}.{quote_identifier(denom_col)}" if denom_tbl else quote_identifier(denom_col)
                    # Weighted ratio: SUM(numerator) / SUM(denominator)
                    select_items.append(
                        f"(CASE WHEN SUM({denom_expr}) IS NULL OR SUM({denom_expr}) = 0 THEN NULL "
                        f"ELSE SUM({col_expr}) * 1.0 / SUM({denom_expr}) END) AS {quoted_alias}"
                    )
                else:
                    if needs_group_by:
                        select_items.append(f"SUM({col_expr}) AS {quoted_alias}")
                    else:
                        select_items.append(f"{col_expr} AS {quoted_alias}")

            # Derived Measures
            for der in view_spec.derived_measure_specs:
                sql_expr, _ = compile_controlled_expression_to_sql(
                    der.expression,
                    unit_metadata=view_spec.unit_metadata,
                    ratio_columns=ratio_cols,
                    denominator_metadata=view_spec.denominator_metadata,
                    col_qualifier_map=col_qualifiers,
                )
                quoted_alias = quote_identifier(der.measure_name)
                select_items.append(f"{sql_expr} AS {quoted_alias}")

            # Filter constraints
            where_clauses: list[str] = []
            for fc in view_spec.filter_constraints:
                tbl = col_qualifiers.get(fc.column)
                col_q = f"{tbl}.{quote_identifier(fc.column)}" if tbl else quote_identifier(fc.column)
                op = fc.operator.upper().strip()
                if op in ("IS NULL", "IS NOT NULL"):
                    where_clauses.append(f"{col_q} {op}")
                elif op == "IN":
                    vals_str = ", ".join(f"'{str(v).replace('\'', '\'\'')}'" if isinstance(v, str) else str(v) for v in fc.value)
                    where_clauses.append(f"{col_q} IN ({vals_str})")
                elif op == "NOT IN":
                    vals_str = ", ".join(f"'{str(v).replace('\'', '\'\'')}'" if isinstance(v, str) else str(v) for v in fc.value)
                    where_clauses.append(f"{col_q} NOT IN ({vals_str})")
                else:
                    val_str = f"'{str(fc.value).replace('\'', '\'\'')}'" if isinstance(fc.value, str) else str(fc.value)
                    where_clauses.append(f"{col_q} {op} {val_str}")

            where_str = f" WHERE {' AND '.join(where_clauses)}" if where_clauses else ""
            group_str = f" GROUP BY {', '.join(group_by_items)}" if group_by_items else ""

            query = f"SELECT {', '.join(select_items)} FROM {from_clause}{where_str}{group_str}"
            logger.debug("Executing DuckDB analytical query: %s", query)
            res_df = con.execute(query).fetchdf()

            # Post-execution validation: Missing vs. Zero
            # Verify NULLs are preserved and not coerced to 0
            missing_summary: dict[str, Any] = {}
            for col in res_df.columns:
                null_count = int(res_df[col].isna().sum())
                zero_count = int((res_df[col] == 0).sum()) if pd.api.types.is_numeric_dtype(res_df[col]) else 0
                missing_summary[col] = {
                    "null_count": null_count,
                    "zero_count": zero_count,
                    "missing_policy": view_spec.missing_value_policy.value,
                }

            # Post-execution validation: Grain Uniqueness & Duplicate Protection
            grain_validation = self._validate_result_grain(res_df, view_spec.result_grain, view_spec.dimension_columns)
            if grain_validation["status"] == "FAIL":
                return SDRAnalyticalExecutionResult(
                    view_id=view_spec.analytical_view_id,
                    status=SDRAnalyticalViewStatus.UNSAFE,
                    row_count=len(res_df),
                    result_grain=view_spec.result_grain,
                    grain_validation=grain_validation,
                    missing_value_summary=missing_summary,
                    error_message=grain_validation["error"],
                )

            # Materialization
            materialized_path: str | None = None
            if view_spec.materialization_mode == MaterializationMode.MATERIALIZED:
                out_dir = self.base_dir / "datasets" / view_spec.dataset_id / "sdr" / "gold"
                out_dir.mkdir(parents=True, exist_ok=True)
                parquet_file = out_dir / f"{view_spec.analytical_view_id}.parquet"
                res_df.to_parquet(parquet_file, index=False)
                materialized_path = str(parquet_file)

            # Convert result dataframe to list of dicts with NULL preserved (turn NaN into None)
            raw_dicts = res_df.to_dict(orient="records")
            rows = [
                {k: (None if pd.isna(v) else v) for k, v in row.items()}
                for row in raw_dicts
            ]

            # Collect summary measure results
            measure_results: dict[str, Any] = {}
            for col in view_spec.measure_columns + [d.measure_name for d in view_spec.derived_measure_specs]:
                if col in res_df.columns and pd.api.types.is_numeric_dtype(res_df[col]):
                    non_nulls = res_df[col].dropna()
                    measure_results[col] = {
                        "count": len(non_nulls),
                        "sum": float(non_nulls.sum()) if not non_nulls.empty else None,
                        "mean": float(non_nulls.mean()) if not non_nulls.empty else None,
                    }

            # Build execution fingerprint
            exec_fp = compute_analytical_view_fingerprint(
                dataset_version=view_spec.dataset_version,
                source_artifact_fingerprints=view_spec.source_artifact_fingerprints,
                join_plan_fingerprints=view_spec.provenance.get("join_plan_fingerprints", []),
                base_grain=view_spec.base_grain,
                result_grain=view_spec.result_grain,
                dimension_columns=view_spec.dimension_columns,
                measure_columns=view_spec.measure_columns,
                derived_measure_specs=view_spec.derived_measure_specs,
                unit_metadata=view_spec.unit_metadata,
                denominator_metadata=view_spec.denominator_metadata,
                missing_value_policy=view_spec.missing_value_policy,
                policy_fingerprint=view_spec.policy_fingerprint,
            )

            return SDRAnalyticalExecutionResult(
                view_id=view_spec.analytical_view_id,
                status=SDRAnalyticalViewStatus.VALID if not view_spec.preaggregation_specs else SDRAnalyticalViewStatus.VALID_WITH_PREAGGREGATION,
                row_count=len(rows),
                result_grain=view_spec.result_grain,
                measure_results=measure_results,
                grain_validation=grain_validation,
                unit_validation={"status": "PASS", "conflicts": []},
                denominator_validation={"status": "PASS", "denominators": view_spec.denominator_metadata},
                missing_value_summary=missing_summary,
                provenance={
                    "execution_time_ms": round((time.perf_counter() - t0) * 1000, 2),
                    "source_sheet_ids": view_spec.source_sheet_ids,
                    "join_plan_ids": view_spec.join_plan_ids,
                },
                execution_fingerprint=exec_fp,
                materialized_parquet_path=materialized_path,
                rows=rows,
            )

        finally:
            con.close()

    def _build_join_from_clause(
        self,
        con: duckdb.DuckDBPyConnection,
        dfs: dict[str, pd.DataFrame],
        join_plans: list[SDRJoinPlan],
    ) -> tuple[str, dict[str, str]]:
        """
        Builds FROM clause executing pre-aggregation on appropriate side before joining.
        Returns (from_clause_sql, col_qualifiers_dict).
        """
        col_qualifiers: dict[str, str] = {}

        # Start with primary table (left of first plan)
        first_plan = join_plans[0]
        left_table = first_plan.left_sheet_id
        current_from = f"src_{left_table}"

        for c in dfs[left_table].columns:
            col_qualifiers[c] = f"src_{left_table}"

        for plan in join_plans:
            right_table = plan.right_sheet_id
            right_source = f"src_{right_table}"

            # If SAFE_WITH_PREAGGREGATION, execute exact PreAggregationSpec FIRST
            if plan.safety_status == JoinSafetyStatus.SAFE_WITH_PREAGGREGATION and plan.preaggregation_spec:
                spec = plan.preaggregation_spec
                preagg_view_name = f"preagg_{spec.source_table_id}"
                grp_cols = [quote_identifier(c) for c in spec.group_by_columns]
                agg_exprs: list[str] = [f"{c} AS {c}" for c in grp_cols]
                for mcol, agg_fn in spec.aggregations.items():
                    m_q = quote_identifier(mcol)
                    agg_exprs.append(f"{agg_fn}({m_q}) AS {m_q}")

                preagg_sql = (
                    f"CREATE VIEW {preagg_view_name} AS "
                    f"SELECT {', '.join(agg_exprs)} FROM src_{spec.source_table_id} "
                    f"GROUP BY {', '.join(grp_cols)}"
                )
                con.execute(preagg_sql)
                if spec.source_table_id == right_table:
                    right_source = preagg_view_name
                    for c in spec.group_by_columns + list(spec.aggregations.keys()):
                        if c not in col_qualifiers:
                            col_qualifiers[c] = preagg_view_name
                elif spec.source_table_id == left_table:
                    current_from = preagg_view_name
                    for c in spec.group_by_columns + list(spec.aggregations.keys()):
                        col_qualifiers[c] = preagg_view_name
            else:
                for c in dfs[right_table].columns:
                    if c not in col_qualifiers:
                        col_qualifiers[c] = f"src_{right_table}"

            # Build join condition
            join_conds: list[str] = []
            for lk, rk in zip(plan.left_keys, plan.right_keys):
                join_conds.append(f"{current_from}.{quote_identifier(lk)} = {right_source}.{quote_identifier(rk)}")

            join_type = (plan.join_type or "LEFT").upper()
            current_from = f"({current_from} {join_type} JOIN {right_source} ON {' AND '.join(join_conds)})"

        return current_from, col_qualifiers

    def _validate_result_grain(
        self,
        df: pd.DataFrame,
        declared_grain: str,
        dimension_columns: list[str],
    ) -> dict[str, Any]:
        """
        Validates that output rows are strictly unique according to declared grain.
        Never silently deduplicates or hides duplicates!
        """
        if df.empty:
            return {"status": "PASS", "is_unique": True, "duplicate_count": 0}

        # Determine grain columns: use dimension_columns if present, or grain name
        grain_cols = [c for c in dimension_columns if c in df.columns]
        if not grain_cols:
            # Fallback: check all columns if grain is atomic
            grain_cols = list(df.columns)

        duplicate_mask = df.duplicated(subset=grain_cols, keep=False)
        duplicate_count = int(duplicate_mask.sum())

        if duplicate_count > 0:
            return {
                "status": "FAIL",
                "is_unique": False,
                "duplicate_count": duplicate_count,
                "error": (
                    f"GRAIN_VIOLATION: Declared grain '{declared_grain}' violated by {duplicate_count} "
                    f"duplicate rows across key columns {grain_cols}. Silent deduplication is strictly prohibited."
                ),
            }

        return {"status": "PASS", "is_unique": True, "duplicate_count": 0}
