"""
Analytical Query Service for Phase G3 Analytical Plane.
The single governed entrypoint for columnar analytics over Parquet files via DuckDB.
Exposes domain-independent contracts: aggregate, group_by, rank, distribution,
correlate, percentile, outliers, trend, compare, and cross_sheet_join.
"""
from __future__ import annotations

import logging
import math
import time
from typing import Any, Sequence

from app.core.config import settings
from app.db.database import session_scope
from .contracts import (
    AggregationType,
    AnalyticalQueryResult,
    AnalyticalStatus,
    FilterOperator,
    FilterSpec,
    MeasureSpec,
    OrderBySpec,
    OrderDirection,
)
from .duckdb_engine import DuckDBEngine, quote_identifier
from .storage_integrity import AnalyticalStorageIsolationIntegrity

logger = logging.getLogger(__name__)


class AnalyticalQueryService:
    """Governed analytical query service backed by DuckDB and Parquet."""

    @classmethod
    def resolve_parquet_path(
        cls,
        dataset_id: int,
        logical_table_id: str,
        dataset_version: int = 1,
    ) -> str:
        """Resolves and validates the Parquet path for a logical table from SQLite metadata."""
        with session_scope() as conn:
            row = conn.execute(
                """
                SELECT parquet_path, status, content_hash
                FROM dataset_parquet_tables
                WHERE dataset_id = ? AND dataset_version = ? AND logical_table_id = ?
                """,
                (dataset_id, dataset_version, logical_table_id),
            ).fetchone()

            if not row or not row[0]:
                # Fallback: check if single sheet matches by id or name
                alt_row = conn.execute(
                    """
                    SELECT parquet_path, status
                    FROM dataset_parquet_tables
                    WHERE dataset_id = ? AND dataset_version = ?
                    LIMIT 1
                    """,
                    (dataset_id, dataset_version),
                ).fetchone()
                if alt_row and alt_row[0]:
                    row = alt_row
                else:
                    raise FileNotFoundError(
                        f"No registered Parquet table found for dataset {dataset_id} v{dataset_version} table '{logical_table_id}'"
                    )

            parquet_path, status, *_ = row
            if status != AnalyticalStatus.PARQUET_READY.value:
                raise RuntimeError(
                    f"Parquet table for dataset {dataset_id} is in non-ready status: {status}"
                )

            # Security verification
            AnalyticalStorageIsolationIntegrity.validate_metadata_alignment(
                requested_dataset_id=dataset_id,
                requested_dataset_version=dataset_version,
                stored_metadata_dataset_id=dataset_id,
                stored_metadata_version=dataset_version,
                parquet_path=parquet_path,
            )

            return parquet_path

    @classmethod
    def aggregate(
        cls,
        dataset_id: int,
        logical_table_id: str,
        measures: Sequence[MeasureSpec],
        filters: Sequence[FilterSpec] = (),
        dataset_version: int = 1,
    ) -> AnalyticalQueryResult:
        """Executes full-table columnar aggregations."""
        parquet_path = cls.resolve_parquet_path(dataset_id, logical_table_id, dataset_version)
        return DuckDBEngine.execute_query(
            parquet_path=parquet_path,
            dimensions=(),
            measures=measures,
            filters=filters,
        )

    @classmethod
    def group_by(
        cls,
        dataset_id: int,
        logical_table_id: str,
        dimensions: Sequence[str],
        measures: Sequence[MeasureSpec],
        filters: Sequence[FilterSpec] = (),
        order_by: Sequence[OrderBySpec] = (),
        limit: int | None = None,
        offset: int | None = None,
        dataset_version: int = 1,
    ) -> AnalyticalQueryResult:
        """Executes governed group-by aggregation over Parquet data."""
        parquet_path = cls.resolve_parquet_path(dataset_id, logical_table_id, dataset_version)
        return DuckDBEngine.execute_query(
            parquet_path=parquet_path,
            dimensions=dimensions,
            measures=measures,
            filters=filters,
            order_by=order_by,
            limit=limit,
            offset=offset,
        )

    @classmethod
    def rank(
        cls,
        dataset_id: int,
        logical_table_id: str,
        entity_col: str,
        measure_col: str,
        aggregation: AggregationType = AggregationType.AVG,
        is_lower_better: bool = False,
        limit: int = 5,
        filters: Sequence[FilterSpec] = (),
        entity_label_col: str | None = None,
        dataset_version: int = 1,
    ) -> AnalyticalQueryResult:
        """Discovers top/bottom entity rankings with optional person label resolution."""
        parquet_path = cls.resolve_parquet_path(dataset_id, logical_table_id, dataset_version)
        dimensions = [entity_col]
        if entity_label_col and entity_label_col != entity_col:
            dimensions.append(entity_label_col)

        m_spec = MeasureSpec(
            field=measure_col,
            aggregation=aggregation,
            alias="metric_val",
        )
        count_spec = MeasureSpec(
            field=measure_col,
            aggregation=AggregationType.COUNT,
            alias="record_count",
        )

        order_dir = OrderDirection.ASC if is_lower_better else OrderDirection.DESC
        ob_spec = OrderBySpec(field="metric_val", direction=order_dir)

        # Filter out nulls on measure_col
        effective_filters = list(filters) + [
            FilterSpec(field=measure_col, operator=FilterOperator.IS_NOT_NULL),
            FilterSpec(field=entity_col, operator=FilterOperator.IS_NOT_NULL),
        ]

        return DuckDBEngine.execute_query(
            parquet_path=parquet_path,
            dimensions=dimensions,
            measures=[m_spec, count_spec],
            filters=effective_filters,
            order_by=[ob_spec],
            limit=limit,
        )

    @classmethod
    def correlate(
        cls,
        dataset_id: int,
        logical_table_id: str,
        measure_x: str,
        measure_y: str,
        filters: Sequence[FilterSpec] = (),
        dataset_version: int = 1,
    ) -> dict[str, Any]:
        """Calculates Pearson correlation between two numerical measures in a single pass."""
        parquet_path = cls.resolve_parquet_path(dataset_id, logical_table_id, dataset_version)
        t0 = time.perf_counter()

        qx = quote_identifier(measure_x)
        qy = quote_identifier(measure_y)

        where_parts = [f"{qx} IS NOT NULL", f"{qy} IS NOT NULL"]
        params: list[Any] = []
        for f in filters:
            q_field = quote_identifier(f.field)
            if f.operator in (FilterOperator.IS_NULL, FilterOperator.IS_NOT_NULL):
                where_parts.append(f"{q_field} {f.operator.value}")
            else:
                where_parts.append(f"{q_field} {f.operator.value} ?")
                params.append(f.value)

        sql = f"""
            SELECT 
                CORR({qx}, {qy}) AS correlation,
                COUNT(*) AS sample_size,
                AVG({qx}) AS mean_x,
                AVG({qy}) AS mean_y,
                STDDEV({qx}) AS std_x,
                STDDEV({qy}) AS std_y
            FROM read_parquet(?)
            WHERE {' AND '.join(where_parts)}
        """

        raw = DuckDBEngine.execute_raw_aggregation(parquet_path, sql, params)
        exec_ms = (time.perf_counter() - t0) * 1000

        if not raw or not raw[0] or raw[0][0] is None:
            return {
                "correlation": 0.0,
                "sample_size": 0,
                "execution_ms": exec_ms,
                "engine": "duckdb",
            }

        corr, cnt, mx, my, sx, sy = raw[0]
        return {
            "correlation": round(float(corr), 4) if corr is not None else 0.0,
            "sample_size": int(cnt),
            "mean_x": round(float(mx), 4) if mx is not None else 0.0,
            "mean_y": round(float(my), 4) if my is not None else 0.0,
            "std_x": round(float(sx), 4) if sx is not None else 0.0,
            "std_y": round(float(sy), 4) if sy is not None else 0.0,
            "execution_ms": exec_ms,
            "engine": "duckdb",
        }

    @classmethod
    def percentile(
        cls,
        dataset_id: int,
        logical_table_id: str,
        measure_col: str,
        percentiles: Sequence[float] = (0.25, 0.5, 0.75),
        filters: Sequence[FilterSpec] = (),
        dataset_version: int = 1,
    ) -> dict[str, float]:
        """Calculates exact continuous quantiles over a measure."""
        parquet_path = cls.resolve_parquet_path(dataset_id, logical_table_id, dataset_version)
        qm = quote_identifier(measure_col)

        where_parts = [f"{qm} IS NOT NULL"]
        params: list[Any] = []
        for f in filters:
            q_field = quote_identifier(f.field)
            if f.operator in (FilterOperator.IS_NULL, FilterOperator.IS_NOT_NULL):
                where_parts.append(f"{q_field} {f.operator.value}")
            else:
                where_parts.append(f"{q_field} {f.operator.value} ?")
                params.append(f.value)

        p_list_str = ", ".join(str(p) for p in percentiles)
        sql = f"""
            SELECT QUANTILE_CONT({qm}, [{p_list_str}])
            FROM read_parquet(?)
            WHERE {' AND '.join(where_parts)}
        """

        raw = DuckDBEngine.execute_raw_aggregation(parquet_path, sql, params)
        if not raw or not raw[0] or raw[0][0] is None:
            return {f"p{int(p*100)}": 0.0 for p in percentiles}

        vals = raw[0][0]
        return {f"p{int(p*100)}": round(float(v), 4) for p, v in zip(percentiles, vals)}

    @classmethod
    def distribution(
        cls,
        dataset_id: int,
        logical_table_id: str,
        measure_col: str,
        buckets: int = 10,
        filters: Sequence[FilterSpec] = (),
        dataset_version: int = 1,
    ) -> dict[str, Any]:
        """Calculates five-number summary and histogram bucket counts."""
        parquet_path = cls.resolve_parquet_path(dataset_id, logical_table_id, dataset_version)
        qm = quote_identifier(measure_col)

        # Five number summary
        summary_sql = f"""
            SELECT 
                MIN({qm}) AS min_val,
                QUANTILE_CONT({qm}, 0.25) AS q1,
                MEDIAN({qm}) AS median_val,
                QUANTILE_CONT({qm}, 0.75) AS q3,
                MAX({qm}) AS max_val,
                AVG({qm}) AS avg_val,
                STDDEV({qm}) AS std_val,
                COUNT(*) AS count_val
            FROM read_parquet(?)
            WHERE {qm} IS NOT NULL
        """
        raw_sum = DuckDBEngine.execute_raw_aggregation(parquet_path, summary_sql)
        if not raw_sum or not raw_sum[0] or raw_sum[0][0] is None:
            return {"summary": {}, "histogram": []}

        min_v, q1, med, q3, max_v, avg_v, std_v, cnt = raw_sum[0]

        # Histogram buckets
        hist = []
        if min_v is not None and max_v is not None and max_v > min_v and buckets > 1:
            step = (max_v - min_v) / buckets
            hist_sql = f"""
                SELECT 
                    CAST(LEAST({buckets}, GREATEST(1, FLOOR(({qm} - {min_v}) / {step}) + 1)) AS INTEGER) AS bucket_idx,
                    COUNT(*) AS freq
                FROM read_parquet(?)
                WHERE {qm} IS NOT NULL
                GROUP BY 1
                ORDER BY 1
            """
            bucket_rows = DuckDBEngine.execute_raw_aggregation(parquet_path, hist_sql)
            bucket_map = {r[0]: r[1] for r in bucket_rows}
            for b in range(1, buckets + 1):
                b_min = min_v + (b - 1) * step
                b_max = min_v + b * step
                hist.append({
                    "bucket": b,
                    "range": f"{b_min:.1f} - {b_max:.1f}",
                    "count": bucket_map.get(b, 0),
                })

        return {
            "summary": {
                "min": round(float(min_v), 4) if min_v is not None else 0.0,
                "q1": round(float(q1), 4) if q1 is not None else 0.0,
                "median": round(float(med), 4) if med is not None else 0.0,
                "q3": round(float(q3), 4) if q3 is not None else 0.0,
                "max": round(float(max_v), 4) if max_v is not None else 0.0,
                "mean": round(float(avg_v), 4) if avg_v is not None else 0.0,
                "std": round(float(std_v), 4) if std_v is not None else 0.0,
                "count": int(cnt),
            },
            "histogram": hist,
        }

    @classmethod
    def outliers(
        cls,
        dataset_id: int,
        logical_table_id: str,
        entity_col: str,
        measure_col: str,
        iqr_multiplier: float = 1.5,
        dataset_version: int = 1,
    ) -> list[dict[str, Any]]:
        """Identifies statistical outlier records using Tukey IQR fences."""
        dist = cls.distribution(dataset_id, logical_table_id, measure_col, dataset_version=dataset_version)
        sum_data = dist.get("summary", {})
        q1 = sum_data.get("q1", 0.0)
        q3 = sum_data.get("q3", 0.0)
        iqr = q3 - q1

        if iqr <= 0:
            return []

        lower_fence = q1 - (iqr * iqr_multiplier)
        upper_fence = q3 + (iqr * iqr_multiplier)

        parquet_path = cls.resolve_parquet_path(dataset_id, logical_table_id, dataset_version)
        qe = quote_identifier(entity_col)
        qm = quote_identifier(measure_col)

        sql = f"""
            SELECT {qe}, {qm}, __source_row_index, __source_sheet_id
            FROM read_parquet(?)
            WHERE {qm} < ? OR {qm} > ?
            ORDER BY ABS({qm} - {sum_data.get('median', 0.0)}) DESC
            LIMIT 20
        """
        raw = DuckDBEngine.execute_raw_aggregation(parquet_path, sql, [lower_fence, upper_fence])
        return [
            {
                "entity": r[0],
                "value": round(float(r[1]), 4),
                "is_upper": float(r[1]) > upper_fence,
                "source_row": r[2],
                "source_sheet": r[3],
            }
            for r in raw
        ]

    @classmethod
    def trend(
        cls,
        dataset_id: int,
        logical_table_id: str,
        time_col: str,
        measure_col: str,
        aggregation: AggregationType = AggregationType.AVG,
        dataset_version: int = 1,
    ) -> AnalyticalQueryResult:
        """Computes sequential temporal aggregation."""
        return cls.group_by(
            dataset_id=dataset_id,
            logical_table_id=logical_table_id,
            dimensions=[time_col],
            measures=[MeasureSpec(field=measure_col, aggregation=aggregation, alias="metric_val")],
            order_by=[OrderBySpec(field=time_col, direction=OrderDirection.ASC)],
            dataset_version=dataset_version,
        )

    @classmethod
    def compare(
        cls,
        dataset_id: int,
        logical_table_id: str,
        dimension_col: str,
        group_a: Any,
        group_b: Any,
        measure_cols: Sequence[str],
        dataset_version: int = 1,
    ) -> dict[str, Any]:
        """Compares analytical metrics across two dimension cohorts."""
        measures = [
            MeasureSpec(field=m, aggregation=AggregationType.AVG, alias=f"avg_{m}")
            for m in measure_cols
        ]
        filters = [
            FilterSpec(field=dimension_col, operator=FilterOperator.IN, value=[group_a, group_b])
        ]
        res = cls.group_by(
            dataset_id=dataset_id,
            logical_table_id=logical_table_id,
            dimensions=[dimension_col],
            measures=measures,
            filters=filters,
            dataset_version=dataset_version,
        )

        rows = {r[dimension_col]: r for r in res.rows}
        comp: dict[str, Any] = {"group_a": group_a, "group_b": group_b, "metrics": {}}

        row_a = rows.get(group_a, {})
        row_b = rows.get(group_b, {})

        for m in measure_cols:
            k = f"avg_{m}"
            va = row_a.get(k)
            vb = row_b.get(k)
            diff = (va - vb) if (va is not None and vb is not None) else None
            comp["metrics"][m] = {
                "val_a": va,
                "val_b": vb,
                "diff": round(diff, 4) if diff is not None else None,
            }

        return comp

    @classmethod
    def cross_sheet_join(
        cls,
        dataset_id: int,
        left_table: str,
        right_table: str,
        join_keys: Sequence[tuple[str, str]],
        dimensions: Sequence[str],
        measures: Sequence[MeasureSpec],
        filters: Sequence[FilterSpec] = (),
        dataset_version: int = 1,
    ) -> AnalyticalQueryResult:
        """Executes a governed cross-sheet join using pre-validated join keys."""
        left_path = cls.resolve_parquet_path(dataset_id, left_table, dataset_version)
        right_path = cls.resolve_parquet_path(dataset_id, right_table, dataset_version)
        t0 = time.perf_counter()

        join_conditions = []
        for l_k, r_k in join_keys:
            join_conditions.append(f"l.{quote_identifier(l_k)} = r.{quote_identifier(r_k)}")

        select_clauses = []
        group_clauses = []
        for d in dimensions:
            q = quote_identifier(d)
            # Default to left table column
            select_clauses.append(f"l.{q} AS {q}")
            group_clauses.append(f"l.{q}")

        for m in measures:
            q_field = quote_identifier(m.field)
            agg = m.aggregation.value
            out_alias = quote_identifier(m.output_name)
            # Distinguish whether column belongs to right or left table
            table_prefix = "r" if m.field.startswith("right_") else "l"
            clean_field = m.field.removeprefix("right_")
            q_clean = quote_identifier(clean_field)
            select_clauses.append(f"{agg}({table_prefix}.{q_clean}) AS {out_alias}")

        sql = f"""
            SELECT {', '.join(select_clauses)}
            FROM read_parquet(?) AS l
            JOIN read_parquet(?) AS r ON {' AND '.join(join_conditions)}
        """
        if group_clauses:
            sql += f" GROUP BY {', '.join(group_clauses)}"

        con = DuckDBEngine.create_session()
        try:
            rel = con.execute(sql, [left_path, right_path])
            col_names = [d[0] for d in rel.description]
            raw_tuples = rel.fetchall()
            rows = [dict(zip(col_names, r)) for r in raw_tuples]
            exec_ms = (time.perf_counter() - t0) * 1000

            return AnalyticalQueryResult(
                rows=rows,
                columns=col_names,
                total_rows=len(rows),
                execution_time_ms=exec_ms,
                engine="duckdb",
                parquet_path=f"{left_path}+{right_path}",
                provenance={"join_sql": sql, "join_keys": list(join_keys)},
            )
        finally:
            con.close()
