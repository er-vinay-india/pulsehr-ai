"""
DuckDB Query Engine for Phase G3 Analytical Plane.
Executes read-only, in-memory analytical query sessions over validated Parquet files
with parameterized filters, identifier escaping, and zero writer locking.
"""
from __future__ import annotations

import logging
import re
import time
from typing import Any, Sequence

import duckdb

from app.core.config import settings
from .contracts import (
    AggregationType,
    AnalyticalQueryResult,
    FilterOperator,
    FilterSpec,
    MeasureSpec,
    OrderBySpec,
    OrderDirection,
)

logger = logging.getLogger(__name__)


def quote_identifier(ident: str) -> str:
    """Escapes and double-quotes an identifier for DuckDB SQL."""
    # Ensure no null bytes
    clean = str(ident).replace("\x00", "")
    escaped = clean.replace('"', '""')
    return f'"{escaped}"'


class DuckDBEngine:
    """Provides isolated, in-memory analytical query execution on Parquet data."""

    @classmethod
    def create_session(cls) -> duckdb.DuckDBPyConnection:
        """Creates a fresh, isolated in-memory session with governed resource limits."""
        con = duckdb.connect(":memory:")
        try:
            threads = getattr(settings, "DUCKDB_THREADS", 2)
            max_memory = getattr(settings, "DUCKDB_MAX_MEMORY", "2GB")
            con.execute(f"SET threads = {threads};")
            con.execute(f"SET max_memory = '{max_memory}';")
        except Exception as e:
            logger.debug("Failed setting DuckDB session limits: %s", e)
        return con

    @classmethod
    def execute_query(
        cls,
        parquet_path: str,
        dimensions: Sequence[str] = (),
        measures: Sequence[MeasureSpec] = (),
        filters: Sequence[FilterSpec] = (),
        order_by: Sequence[OrderBySpec] = (),
        limit: int | None = None,
        offset: int | None = None,
        allowed_columns: set[str] | None = None,
    ) -> AnalyticalQueryResult:
        """Executes a governed analytical aggregation query over a single Parquet file."""
        t0 = time.perf_counter()

        # Validate column names against schema if provided
        all_cols = list(dimensions) + [m.field for m in measures] + [f.field for f in filters] + [o.field for o in order_by]
        if allowed_columns:
            for c in all_cols:
                if c not in allowed_columns and not c.startswith("__"):
                    raise ValueError(f"Unrecognized or forbidden column in analytical query: '{c}'")

        select_clauses: list[str] = []
        group_clauses: list[str] = []
        where_clauses: list[str] = []
        params: list[Any] = [parquet_path]

        # Dimensions
        for dim in dimensions:
            q_dim = quote_identifier(dim)
            select_clauses.append(f"{q_dim} AS {q_dim}")
            group_clauses.append(q_dim)

        # Measures
        for m in measures:
            q_field = quote_identifier(m.field)
            agg = m.aggregation.value
            out_alias = quote_identifier(m.output_name)

            if m.aggregation == AggregationType.COUNT_DISTINCT:
                expr = f"COUNT(DISTINCT {q_field})"
            elif m.aggregation == AggregationType.MEDIAN:
                expr = f"MEDIAN({q_field})"
            elif m.aggregation == AggregationType.STDDEV:
                expr = f"STDDEV({q_field})"
            elif m.aggregation == AggregationType.VAR:
                expr = f"VARIANCE({q_field})"
            else:
                expr = f"{agg}({q_field})"

            select_clauses.append(f"{expr} AS {out_alias}")

        if not select_clauses:
            select_clauses = ["*"]

        # Filters
        for f in filters:
            q_field = quote_identifier(f.field)
            op = f.operator
            if op == FilterOperator.IS_NULL:
                where_clauses.append(f"{q_field} IS NULL")
            elif op == FilterOperator.IS_NOT_NULL:
                where_clauses.append(f"{q_field} IS NOT NULL")
            elif op in (FilterOperator.IN, FilterOperator.NOT_IN):
                vals = f.value if isinstance(f.value, (list, tuple, set)) else [f.value]
                if not vals:
                    continue
                placeholders = ", ".join(["?"] * len(vals))
                where_clauses.append(f"{q_field} {op.value} ({placeholders})")
                params.extend(vals)
            else:
                where_clauses.append(f"{q_field} {op.value} ?")
                params.append(f.value)

        # Compile SQL
        sql = f"SELECT {', '.join(select_clauses)} FROM read_parquet(?)"
        if where_clauses:
            sql += f" WHERE {' AND '.join(where_clauses)}"
        if group_clauses:
            sql += f" GROUP BY {', '.join(group_clauses)}"

        # Ordering
        if order_by:
            order_clauses = []
            for ob in order_by:
                q_field = quote_identifier(ob.field)
                dir_str = "ASC" if ob.direction == OrderDirection.ASC else "DESC"
                order_clauses.append(f"{q_field} {dir_str} NULLS LAST")
            sql += f" ORDER BY {', '.join(order_clauses)}"

        # Limit & Offset
        if limit is not None:
            sql += f" LIMIT {int(limit)}"
        if offset is not None:
            sql += f" OFFSET {int(offset)}"

        con = cls.create_session()
        try:
            rel = con.execute(sql, params)
            col_names = [d[0] for d in rel.description]
            raw_tuples = rel.fetchall()

            rows = [dict(zip(col_names, r)) for r in raw_tuples]
            execution_ms = (time.perf_counter() - t0) * 1000

            return AnalyticalQueryResult(
                rows=rows,
                columns=col_names,
                total_rows=len(rows),
                execution_time_ms=execution_ms,
                engine="duckdb",
                parquet_path=parquet_path,
                provenance={"sql_compiled": sql, "param_count": len(params)},
            )
        finally:
            con.close()

    @classmethod
    def execute_raw_aggregation(
        cls,
        parquet_path: str,
        sql_template: str,
        params: Sequence[Any] = (),
    ) -> list[tuple[Any, ...]]:
        """Executes a strictly parameterized read-only query for advanced operations like correlation/quantiles."""
        con = cls.create_session()
        try:
            return con.execute(sql_template, [parquet_path, *params]).fetchall()
        finally:
            con.close()
