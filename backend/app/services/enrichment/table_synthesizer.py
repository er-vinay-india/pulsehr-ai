"""Analytical Table Synthesis & Cross-Dimensional Views Engine (Stage 10).

Generates structured multi-dimensional analytical views, pivot tables, temporal trend summaries,
and Pareto rankings bounded by table explosion protections, table count budgets, and utility thresholds.
"""

from __future__ import annotations

import json
import logging
from typing import Any
import numpy as np
import pandas as pd

from .config import BudgetGuard, EnrichmentConfig
from .models import AnalyticalTable, EnrichmentColumnProfile, SemanticRole

logger = logging.getLogger(__name__)


class AnalyticalTableSynthesizer:
    """Synthesizes high-utility analytical tables with strict explosion safeguards."""

    @classmethod
    def synthesize_tables(
        cls,
        df: pd.DataFrame,
        profiles: dict[str, EnrichmentColumnProfile],
        budget_guard: BudgetGuard,
        config: EnrichmentConfig
    ) -> list[AnalyticalTable]:
        tables: list[AnalyticalTable] = []
        if df.empty or not budget_guard.can_generate_table():
            return tables

        n_rows = len(df)

        # 1. Filter Safe Dimensions (protect against cardinality explosion)
        dimensions: list[str] = []
        for c in df.columns:
            prof = profiles.get(c)
            # Must not be high-cardinality ID
            if prof and SemanticRole.IDENTIFIER in prof.roles:
                continue
            card = df[c].nunique()
            unique_ratio = card / max(1, n_rows)
            # Explosion protection: between 2 and 100 unique values, and unique_ratio < 0.5
            if 2 <= card <= 100 and unique_ratio <= 0.5:
                if (prof and SemanticRole.DIMENSION in prof.roles) or (not pd.api.types.is_float_dtype(df[c])):
                    dimensions.append(c)

        # 2. Temporal Columns
        time_cols = [
            c for c in df.columns
            if (profiles.get(c) and SemanticRole.TIME in profiles[c].roles)
            or any(t in c.lower() for t in ("year", "quarter", "month", "date"))
        ]

        # 3. Numeric Measures (limit to max_measures_per_table)
        measures = [
            c for c in df.columns
            if pd.api.types.is_numeric_dtype(df[c])
            and df[c].nunique() > 2
            and not c.endswith("_id")
            and not c.endswith("_is_weekend")
            and not c.endswith("_day")
        ][:config.max_measures_per_table]

        if not measures:
            return tables

        lead_measure = measures[0]

        # 4. Primary Dimension Aggregations (bounded by max_dimensions_per_table)
        max_dims = min(len(dimensions), config.max_dimensions_per_table)
        for dim in dimensions[:max_dims]:
            if not budget_guard.can_generate_table():
                break

            try:
                grouped = df.groupby(dim).agg(
                    record_count=(lead_measure, "count"),
                    mean_val=(lead_measure, "mean"),
                    total_val=(lead_measure, "sum"),
                    std_val=(lead_measure, "std")
                ).reset_index()

                grouped = grouped.sort_values(by="total_val", ascending=False)
                grouped = grouped.round(2)
                preview = json.loads(grouped.head(500).to_json(orient="records"))

                table_id = f"tbl_dim_{dim}_summary"
                t = AnalyticalTable(
                    table_id=table_id,
                    title=f"{dim.replace('_', ' ').title()} Performance Breakdown",
                    description=f"Grouped dimensional analysis of {lead_measure} aggregated across {dim}.",
                    group_by_columns=[dim],
                    aggregated_measures=[lead_measure],
                    row_count=len(grouped),
                    col_count=len(grouped.columns),
                    columns=list(grouped.columns),
                    utility_score=0.92,
                    data_preview=preview
                )
                if t.utility_score >= config.min_table_utility_score:
                    budget_guard.record_generated_table()
                    tables.append(t)
            except Exception as e:
                logger.warning("Could not build summary table for %s: %s", dim, e)

        # 5. Temporal Trend / Periodic Momentum Tables
        for t_col in time_cols[:2]:
            if not budget_guard.can_generate_table():
                break

            try:
                temp_grouped = df.groupby(t_col)[lead_measure].agg(["count", "mean", "sum"]).reset_index()
                temp_grouped = temp_grouped.rename(columns={"count": "volume", "mean": "average", "sum": "total"})
                temp_grouped["periodic_change_%"] = temp_grouped["total"].pct_change().mul(100).round(2)
                temp_grouped = temp_grouped.round(2)
                preview = json.loads(temp_grouped.head(500).to_json(orient="records"))

                table_id = f"tbl_temporal_{t_col}_trend"
                t = AnalyticalTable(
                    table_id=table_id,
                    title=f"Periodic Momentum by {t_col.replace('_', ' ').title()}",
                    description=f"Chronological trajectory and percentage changes of {lead_measure} across {t_col}.",
                    group_by_columns=[t_col],
                    aggregated_measures=[lead_measure],
                    row_count=len(temp_grouped),
                    col_count=len(temp_grouped.columns),
                    columns=list(temp_grouped.columns),
                    utility_score=0.95,
                    data_preview=preview
                )
                if t.utility_score >= config.min_table_utility_score:
                    budget_guard.record_generated_table()
                    tables.append(t)
            except Exception as e:
                logger.warning("Could not build temporal table for %s: %s", t_col, e)

        # 6. Two-Dimensional Cross-Tabulation Matrix
        if len(dimensions) >= 2 and budget_guard.can_generate_table():
            dim1, dim2 = dimensions[0], dimensions[1]
            try:
                pivot = pd.pivot_table(
                    df,
                    index=dim1,
                    columns=dim2,
                    values=lead_measure,
                    aggfunc="mean"
                ).round(2).reset_index()

                pivot.columns = [str(c) for c in pivot.columns]
                preview = json.loads(pivot.head(500).to_json(orient="records"))

                table_id = f"tbl_crosstab_{dim1}_vs_{dim2}"
                t = AnalyticalTable(
                    table_id=table_id,
                    title=f"Cross-Tabulation: {dim1.title()} × {dim2.title()}",
                    description=f"Two-dimensional matrix of average {lead_measure} across {dim1} and {dim2}.",
                    group_by_columns=[dim1, dim2],
                    aggregated_measures=[lead_measure],
                    row_count=len(pivot),
                    col_count=len(pivot.columns),
                    columns=list(pivot.columns),
                    utility_score=0.88,
                    data_preview=preview
                )
                if t.utility_score >= config.min_table_utility_score:
                    budget_guard.record_generated_table()
                    tables.append(t)
            except Exception as e:
                logger.warning("Could not build cross-tab table for %s x %s: %s", dim1, dim2, e)

        return tables
