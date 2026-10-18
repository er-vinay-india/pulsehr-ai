"""
HighView Ingestion V2 — Trend & Temporal Analysis
Stage 8: Analytical EDA-B
Evaluates temporal patterns, period-over-period changes, and semi-additive measure aggregations.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any
from app.services.ingestion_v2.analytics.finding_registry import FindingRegistry
from app.services.ingestion_v2.analytics.helpers import (
    get_column_concept,
    get_column_name,
    get_column_role,
    get_column_type,
)
from app.services.ingestion_v2.contracts.analytics import FindingType
from app.services.ingestion_v2.contracts.profiling import TableStructuralProfile
from app.services.ingestion_v2.contracts.semantics import SemanticColumnRole, SemanticConcept


def _parse_date(val: Any) -> datetime | None:
    if val is None:
        return None
    if isinstance(val, datetime):
        return val
    s = str(val).strip()
    for fmt in (
        "%Y-%m-%d",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%dT%H:%M:%S",
        "%m/%d/%Y",
        "%d/%m/%Y",
        "%Y%m%d",
    ):
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            pass
    return None


def analyze_trends(
    table_id: str,
    table_profile: TableStructuralProfile,
    column_semantics: dict[str, Any],
    rows: list[dict[str, Any]],
    registry: FindingRegistry,
    target_grain: str | None = None,
) -> None:
    """
    Computes temporal trends and period-over-period changes for numeric metrics.
    Preserves semi-additive semantics (e.g., period-end balance for inventory/stock).
    """
    if not rows or len(rows) < 10:
        return

    # Find temporal anchor column
    time_col: str | None = None
    for col_profile in table_profile.columns:
        col_id = get_column_name(col_profile)
        col_type = get_column_type(col_profile)
        sem = column_semantics.get(col_id)
        role = get_column_role(sem)
        if col_type in ("DATE", "DATETIME", "TIMESTAMP") or role == SemanticColumnRole.TIME:
            time_col = col_id
            break

    if not time_col:
        return

    # Find numeric metric columns
    metric_cols = []
    for col_profile in table_profile.columns:
        col_id = get_column_name(col_profile)
        if col_id == time_col:
            continue
        col_type = get_column_type(col_profile)
        sem = column_semantics.get(col_id)
        role = get_column_role(sem)
        if col_type in ("INTEGER", "FLOAT") and role in (
            SemanticColumnRole.MEASURE,
            SemanticColumnRole.ATTRIBUTE,
        ):
            metric_cols.append(col_id)

    if not metric_cols:
        return

    # Sort rows by date
    parsed_rows = []
    for r in rows:
        dt = _parse_date(r.get(time_col))
        if dt:
            parsed_rows.append((dt, r))

    if len(parsed_rows) < 5:
        return

    parsed_rows.sort(key=lambda x: x[0])

    for metric_col in metric_cols[:2]:
        sem = column_semantics.get(metric_col)
        concept = get_column_concept(sem)
        is_semi_additive = "inventory" in metric_col.lower() or "balance" in metric_col.lower()

        # Group by month (or day if span is short)
        min_dt = parsed_rows[0][0]
        max_dt = parsed_rows[-1][0]
        date_span_days = (max_dt - min_dt).days

        bucket_format = "%Y-%m" if date_span_days > 45 else "%Y-%m-%d"
        bucket_grain = "MONTH" if date_span_days > 45 else "DAY"

        buckets: dict[str, list[float]] = {}
        for dt, r in parsed_rows:
            m_val = r.get(metric_col)
            if m_val is not None:
                try:
                    f_val = float(m_val)
                    b_key = dt.strftime(bucket_format)
                    buckets.setdefault(b_key, []).append(f_val)
                except (ValueError, TypeError):
                    pass

        if len(buckets) < 3:
            continue

        sorted_buckets = sorted(buckets.items(), key=lambda x: x[0])

        period_values = []
        for b_key, val_list in sorted_buckets:
            if is_semi_additive:
                # Semi-additive: period-end snapshot!
                period_values.append((b_key, val_list[-1]))
            else:
                period_values.append((b_key, sum(val_list)))

        # Compute period-over-period changes
        first_period, first_val = period_values[0]
        last_period, last_val = period_values[-1]

        abs_change = last_val - first_val
        pct_change = ((abs_change / first_val) * 100.0) if first_val != 0 else 0.0

        direction_str = "increased" if abs_change > 0 else ("decreased" if abs_change < 0 else "remained flat")
        agg_label = "period-end snapshot" if is_semi_additive else "total"

        desc = (
            f"Over the observed periods ({first_period} to {last_period}), '{metric_col}' {agg_label} in '{table_id}' "
            f"{direction_str} by {abs(abs_change):,.1f} ({pct_change:+.1f}%), moving from {first_val:,.1f} to {last_val:,.1f}."
        )

        registry.register(
            finding_type=FindingType.TREND,
            description=desc,
            source_table_ids=[table_id],
            source_column_ids=[time_col, metric_col],
            target_grain=target_grain or f"{table_id}_ROW",
            result={
                "temporal_column": time_col,
                "metric_column": metric_col,
                "bucket_grain": bucket_grain,
                "first_period": first_period,
                "first_value": round(first_val, 2),
                "last_period": last_period,
                "last_value": round(last_val, 2),
                "absolute_change": round(abs_change, 2),
                "percentage_change": round(pct_change, 2),
                "is_semi_additive": is_semi_additive,
                "periods_count": len(period_values),
            },
            metric_definition=f"{'PERIOD_END' if is_semi_additive else 'SUM'}({metric_col})",
            dimension_definition=time_col,
            population_definition="ALL_ROWS",
            time_range=f"{first_period}..{last_period}",
            filter_provenance={"null_filter": f"{time_col} IS NOT NULL AND {metric_col} IS NOT NULL"},
            confidence=1.0,
            analysis_method=f"TEMPORAL_TREND_{bucket_grain}",
        )
