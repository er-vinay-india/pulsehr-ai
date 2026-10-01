"""Dimensional Group-By Segmentation & Aggregation Engine.

Discovers discrete categorical and temporal dimensions (including Day of Week, Weekday vs Weekend,
Departments, Education levels, Stores, Categories) and computes grouped aggregates (Mean, Sum, Count, Std)
across primary continuous measures with disparity insights and business projection narratives.
"""
from __future__ import annotations

import re
from typing import Any
import numpy as np
import pandas as pd

WEEKDAY_ORDER = [
    "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"
]
WEEKDAY_SET = set(w.lower() for w in WEEKDAY_ORDER)


def compute_group_by_analytics(
    records: list[dict[str, Any]] | pd.DataFrame,
    columns: list[str],
    diagnostics: dict[str, Any] | None = None
) -> dict[str, Any]:
    """Computes comprehensive group-by aggregations and comparative insights across all valid dimensions."""
    if records is None:
        return {"dimensions": [], "measures": [], "breakdowns": {}, "insights": []}

    if isinstance(records, pd.DataFrame):
        if records.empty:
            return {"dimensions": [], "measures": [], "breakdowns": {}, "insights": []}
        df = records.copy()
    else:
        if not records or not columns:
            return {"dimensions": [], "measures": [], "breakdowns": {}, "insights": []}
        df = pd.DataFrame(records)

    diag = diagnostics or {}

    # 1. Identify Candidate Measures (continuous / quantitative metrics)
    candidate_measures = []
    for c in columns:
        if c not in df.columns:
            continue
        c_lower = c.lower()
        if any(term in c_lower for term in ["name", "full_name", "id", "email", "phone", "address", "url", "code", "gender", "race", "ethnicity", "lunch", "department", "division", "team", "role", "title"]):
            continue
        if c_lower.endswith("_year") or c_lower.endswith("_month") or c_lower.endswith("_day") or c_lower.endswith("_is_weekend"):
            continue

        # Truly numeric test: do not strip letters from ordinary words
        s_clean = pd.to_numeric(df[c], errors='coerce')
        valid_ratio = s_clean.notna().sum() / max(1, len(df))
        if valid_ratio >= 0.75 and s_clean.nunique() > 2:
            candidate_measures.append(c)

    # 2. Identify Candidate Dimensions (categorical, discrete, or date-derived)
    candidate_dimensions = []
    
    # Check for genuine date columns (excluding numeric measures & math interactions)
    date_columns = []
    for c in columns:
        if c not in df.columns or c in candidate_measures or c.startswith("interact_"):
            continue
        if pd.api.types.is_numeric_dtype(df[c]):
            continue
        c_lower = c.lower()
        if any(term in c_lower for term in ["date", "day", "timestamp", "recorded_at", "created_at"]):
            try:
                sample_s = df[c].dropna().astype(str).str.strip()
                if not sample_s.empty and not sample_s.str.replace(r'^[0-9.-]+$', '', regex=True).eq('').all():
                    dt_series = pd.to_datetime(sample_s, errors='coerce', format='mixed')
                    if dt_series.notna().sum() / max(1, len(sample_s)) >= 0.7 and dt_series.dt.date.nunique() >= 2:
                        date_columns.append(c)
            except Exception:
                pass

    # If genuine date column exists, synthetically add Day of Week to df if it has >= 2 distinct days
    for d_col in date_columns:
        weekday_col = f"{d_col}_day_of_week"
        if weekday_col not in df.columns:
            try:
                dt_series = pd.to_datetime(df[d_col], errors='coerce', format='mixed')
                df[weekday_col] = dt_series.dt.day_name()
                if df[weekday_col].dropna().nunique() >= 2:
                    candidate_dimensions.append(weekday_col)
            except Exception:
                pass

    # Standard natural categorical dimensions (prioritized first)
    natural_dims = []
    secondary_dims = []
    for c in columns:
        if c not in df.columns or c in candidate_measures:
            continue
        c_lower = c.lower()
        if c_lower.endswith("_id") or c_lower == "id" or c_lower.endswith("_key") or "name" in c_lower:
            continue
        if any(sym in c for sym in ["/", "*", "+", "="]):
            continue

        non_null_count = df[c].dropna().shape[0]
        if non_null_count == 0:
            continue
        num_vals = pd.to_numeric(df[c], errors='coerce')
        if (num_vals.notna().sum() / non_null_count) >= 0.5:
            continue

        distinct_count = df[c].dropna().nunique()
        # Safe dimension: 2 to 30 unique values, and not 1:1 with rows
        if 2 <= distinct_count <= 30 and (distinct_count / max(1, len(df))) < 0.8:
            if c.startswith("interact_"):
                secondary_dims.append(c)
            else:
                natural_dims.append(c)

    candidate_dimensions.extend(natural_dims)
    candidate_dimensions.extend(secondary_dims)

    # Deduplicate dimensions while preserving order
    dimensions = list(dict.fromkeys(candidate_dimensions))
    measures = candidate_measures[:5]

    if not dimensions or not measures:
        return {"dimensions": dimensions, "measures": measures, "breakdowns": {}, "insights": []}

    breakdowns: dict[str, Any] = {}
    insights: list[str] = []

    for dim in dimensions:
        dim_breakdowns: dict[str, Any] = {}
        dim_vals = df[dim].dropna().astype(str).str.strip()
        is_weekday_dim = any(v.lower() in WEEKDAY_SET for v in dim_vals.unique()[:7])

        for meas in measures:
            try:
                sub_df = pd.DataFrame({
                    "dim": df[dim].astype(str).str.strip(),
                    "val": pd.to_numeric(df[meas].astype(str).str.replace(r'[^\d.-]', '', regex=True), errors='coerce')
                }).dropna()

                if sub_df.empty or sub_df["dim"].nunique() < 2:
                    continue

                grouped = sub_df.groupby("dim")["val"].agg(
                    count="count",
                    mean="mean",
                    total="sum",
                    std="std",
                    min="min",
                    max="max"
                ).reset_index()

                # Sorting: weekday order if day-of-week, otherwise descending by mean
                if is_weekday_dim:
                    grouped["sort_order"] = grouped["dim"].apply(
                        lambda d: WEEKDAY_ORDER.index(d) if d in WEEKDAY_ORDER else 99
                    )
                    grouped = grouped.sort_values(by="sort_order").drop(columns=["sort_order"])
                else:
                    grouped = grouped.sort_values(by="mean", ascending=False)

                grouped = grouped.round(2)
                total_records = int(grouped["count"].sum())
                overall_mean = round(float(sub_df["val"].mean()), 2)
                overall_sum = round(float(sub_df["val"].sum()), 2)

                categories = list(grouped["dim"])
                counts = [int(c) for c in grouped["count"]]
                means = [float(m) for m in grouped["mean"]]
                totals = [float(t) for t in grouped["total"]]
                stds = [float(s) if not np.isnan(s) else 0.0 for s in grouped["std"]]

                top_cat = categories[0]
                top_mean = means[0]
                bottom_cat = categories[-1]
                bottom_mean = means[-1]

                # Disparity between top and bottom
                lift_pct = 0.0
                if bottom_mean > 0:
                    lift_pct = round(((top_mean - bottom_mean) / bottom_mean) * 100, 1)

                # Special Day-of-Week (Sunday vs Weekdays) comparison
                sunday_insight = None
                if is_weekday_dim and "Sunday" in categories:
                    sun_row = grouped[grouped["dim"] == "Sunday"]
                    sun_mean = float(sun_row["mean"].iloc[0]) if not sun_row.empty else None
                    wkday_rows = grouped[grouped["dim"].isin(["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"])]
                    wkday_mean = round(float(wkday_rows["mean"].mean()), 2) if not wkday_rows.empty else None

                    if sun_mean is not None and wkday_mean is not None and wkday_mean > 0:
                        sun_lift = round(((sun_mean - wkday_mean) / wkday_mean) * 100, 1)
                        sign = "+" if sun_lift > 0 else ""
                        sunday_insight = (
                            f"Sunday pattern for {meas}: records an average of {sun_mean} "
                            f"({sign}{sun_lift}% vs weekday average of {wkday_mean})."
                        )
                        insights.append(sunday_insight)

                # General cohort insight
                dim_title = dim.replace("_", " ").title()
                cohort_insight = (
                    f"Across {dim_title}, '{top_cat}' leads in {meas} with an average of {top_mean} "
                    f"(+{lift_pct}% higher than '{bottom_cat}' at {bottom_mean})."
                )
                if not sunday_insight:
                    insights.append(cohort_insight)

                dim_breakdowns[meas] = {
                    "dimension": dim,
                    "dimension_label": dim_title,
                    "measure": meas,
                    "measure_label": meas.replace("_", " ").title(),
                    "categories": categories,
                    "counts": counts,
                    "means": means,
                    "totals": totals,
                    "stds": stds,
                    "overall_mean": overall_mean,
                    "overall_sum": overall_sum,
                    "total_records": total_records,
                    "top_category": top_cat,
                    "top_mean": top_mean,
                    "bottom_category": bottom_cat,
                    "bottom_mean": bottom_mean,
                    "disparity_pct": lift_pct,
                    "is_weekday": is_weekday_dim,
                    "sunday_insight": sunday_insight,
                    "insight": sunday_insight or cohort_insight,
                    "table_rows": [
                        {
                            "category": categories[i],
                            "count": counts[i],
                            "mean": means[i],
                            "total": totals[i],
                            "share_records_pct": round((counts[i] / max(1, total_records)) * 100, 1),
                            "share_measure_pct": round((totals[i] / max(1, overall_sum)) * 100, 1) if overall_sum > 0 else 0.0,
                        }
                        for i in range(len(categories))
                    ]
                }
            except Exception:
                continue

        if dim_breakdowns:
            breakdowns[dim] = dim_breakdowns

    valid_dimensions = [dim for dim in dimensions if dim in breakdowns and len(breakdowns[dim]) > 0]
    valid_measures = [m for m in measures if any(m in breakdowns.get(d, {}) for d in valid_dimensions)]

    return {
        "dimensions": valid_dimensions,
        "measures": valid_measures,
        "breakdowns": {d: breakdowns[d] for d in valid_dimensions},
        "insights": insights[:10]
    }
