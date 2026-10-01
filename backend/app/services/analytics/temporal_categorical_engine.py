"""
Multi-Grain Temporal & Bivariate Categorical Analytics Engine.

Provides deep, verifiable data insights across:
1. Temporal Grains:
   - Per Day: Day-of-week distributions, weekday vs weekend disparity.
   - Per Week: ISO calendar weeks, weekly totals/averages, week-over-week velocity.
   - Per Month: Monthly rollups, seasonality, month-over-month trajectory.
   - Per Annum / Annualized: Annual actuals or verified annualized run-rate with partial-year disclosures.
   - Wide-Format Sequential Periods: Brackets like '1st to 5th July', '6th to 12th July', etc.
2. Bivariate Categorical Insights:
   - Dimension × Measure cross-tabulations.
   - Group Means, Sums, Medians, Share of Total %, Dispersion Ratios (Max/Min spread).
   - Cohort Leaderboards (Top vs Bottom disparity).
"""

from __future__ import annotations

import logging
import math
import re
from typing import Any
import numpy as np
import pandas as pd

from ..display_formatters import format_display_label
from ..time_series_forecast import infer_measure_unit

logger = logging.getLogger(__name__)

WEEKDAY_ORDER = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
WEEKDAY_SET = set(w.lower() for w in WEEKDAY_ORDER)

PERIOD_REGEX = re.compile(
    r"(?:\d+(?:st|nd|rd|th))\s+to\s+(?:\d+(?:st|nd|rd|th))\s*([a-z]+)?|"
    r"\b\d{4}-\d{2}-\d{2}\b|"
    r"\b(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\s*(?:\d{1,2}|week\s*\d+)?\b|"
    r"\bweek\s*\d+\b|\bwk\s*\d+\b|\bq[1-4]\b",
    re.IGNORECASE
)


def _clean_numeric_series(series: pd.Series) -> pd.Series:
    """Converts a series to clean float numeric values, stripping currency, commas, and percentage signs."""
    if pd.api.types.is_numeric_dtype(series):
        return pd.to_numeric(series, errors="coerce")
    str_s = series.astype(str).str.replace(r"[^\d.-]", "", regex=True)
    return pd.to_numeric(str_s, errors="coerce")


def extract_multi_grain_temporal_insights(
    df: pd.DataFrame,
    columns: list[str] | None = None
) -> dict[str, Any]:
    """Extracts comprehensive multi-grain temporal insights across Daily, Weekly, Monthly, and Annual grains."""
    if df is None or df.empty:
        return _empty_temporal_result()

    cols = columns or list(df.columns)
    
    # 1. Check for Long-Format Date Columns
    date_col = None
    parsed_dates = None
    n_rows = len(df)

    for c in cols:
        if c not in df.columns:
            continue
        c_clean = str(c).lower().replace("_", "").replace(" ", "")
        if any(k in c_clean for k in ("date", "timestamp", "datetime", "day", "period", "transactiondate", "recordedat", "createdat")):
            # Multi-pass parsing
            try:
                p = pd.to_datetime(df[c], errors="coerce", format="mixed", dayfirst=True)
                if p.notna().sum() >= max(3, int(n_rows * 0.35)):
                    date_col = c
                    parsed_dates = p
                    break
            except Exception:
                pass
            try:
                p = pd.to_datetime(df[c], errors="coerce", format="mixed", dayfirst=False)
                if p.notna().sum() >= max(3, int(n_rows * 0.35)):
                    date_col = c
                    parsed_dates = p
                    break
            except Exception:
                pass

    # Find candidate numeric measures to measure across time
    candidate_measures = []
    for c in cols:
        if c not in df.columns or c == date_col:
            continue
        c_clean = str(c).lower().replace("_", "").replace(" ", "")
        if any(term in c_clean for term in ("id", "code", "phone", "email", "url", "key", "index", "flag")):
            continue
        num_s = _clean_numeric_series(df[c])
        if num_s.notna().sum() >= max(3, int(n_rows * 0.35)) and num_s.nunique() > 1:
            candidate_measures.append(c)

    primary_measure = None
    if candidate_measures:
        # Prioritize key performance words
        primary_measure = next(
            (m for m in candidate_measures if any(k in m.lower() for k in ("sales", "attendance", "volume", "hour", "revenue", "price", "distance", "count"))),
            candidate_measures[0]
        )

    # PATH A: Long-Format Date Processing
    if date_col and parsed_dates is not None and primary_measure:
        return _process_long_format_temporal(df, date_col, parsed_dates, primary_measure, candidate_measures)

    # PATH B: Wide-Format Sequential Period Columns (e.g. '1st to 5th July', '6th to 12th July', etc.)
    wide_periods = _detect_wide_period_columns(cols, df)
    if wide_periods and len(wide_periods) >= 2:
        return _process_wide_format_temporal(df, wide_periods)

    return _empty_temporal_result()


def _detect_wide_period_columns(columns: list[str], df: pd.DataFrame) -> list[str]:
    """Detects sequential date/period column headers in wide tabular sheets."""
    matched = []
    for c in columns:
        if c not in df.columns:
            continue
        # Avoid interaction features and summary columns
        if c.startswith("interact_") or any(k in c.lower() for k in ("total", "final", "overall", "summary", "approved")) or any(op in c for op in ("+", "*", "/", "=")):
            continue
        if PERIOD_REGEX.search(c):
            # Check if column is numeric or numeric-convertible
            num_s = _clean_numeric_series(df[c])
            if num_s.notna().sum() >= max(2, int(len(df) * 0.3)):
                matched.append(c)

    # Filter into attendance/primary metrics vs leave columns if pairs exist
    primary_periods = [c for c in matched if "leave" not in c.lower()]
    if len(primary_periods) >= 2:
        return primary_periods
    return matched


def _process_long_format_temporal(
    df: pd.DataFrame,
    date_col: str,
    parsed_dates: pd.Series,
    primary_measure: str,
    candidate_measures: list[str]
) -> dict[str, Any]:
    """Computes daily, weekly, monthly, and annual rollups for long-format date datasets."""
    work_df = df.copy()
    work_df["__parsed_date"] = parsed_dates
    work_df["__meas"] = _clean_numeric_series(work_df[primary_measure])
    valid = work_df.dropna(subset=["__parsed_date", "__meas"]).sort_values("__parsed_date")

    if valid.empty:
        return _empty_temporal_result()

    min_date = valid["__parsed_date"].min()
    max_date = valid["__parsed_date"].max()
    days_span = max(1, (max_date - min_date).days)
    unit = infer_measure_unit(primary_measure)
    meas_label = format_display_label(primary_measure)

    # --- 1. Daily & Day-of-Week Breakdown ---
    valid["__day_of_week"] = valid["__parsed_date"].dt.day_name()
    dow_grp = valid.groupby("__day_of_week")["__meas"].agg(["mean", "sum", "count"]).reindex(WEEKDAY_ORDER).dropna()
    
    daily_breakdown = []
    tot_vol = valid["__meas"].sum()
    for day_name, r in dow_grp.iterrows():
        pct = round((r["sum"] / max(tot_vol, 0.001)) * 100, 1) if tot_vol > 0 else 0.0
        daily_breakdown.append({
            "day": day_name,
            "mean": round(float(r["mean"]), 2),
            "total": round(float(r["sum"]), 2),
            "count": int(r["count"]),
            "pct_of_volume": pct
        })

    peak_day = max(daily_breakdown, key=lambda x: x["mean"])["day"] if daily_breakdown else "N/A"
    lowest_day = min(daily_breakdown, key=lambda x: x["mean"])["day"] if daily_breakdown else "N/A"

    # --- 2. Weekly Rollup (Per Week) ---
    valid["__week_str"] = valid["__parsed_date"].dt.strftime("%Y-W%W")
    week_grp = valid.groupby("__week_str")["__meas"].agg(["mean", "sum", "count"]).reset_index()

    weekly_timeline = []
    prev_mean = None
    wow_velocities = []
    for _, r in week_grp.iterrows():
        w_str = str(r["__week_str"])
        w_mean = round(float(r["mean"]), 2)
        wow_pct = round(((w_mean - prev_mean) / prev_mean) * 100, 1) if prev_mean and prev_mean > 0 else None
        if wow_pct is not None:
            wow_velocities.append(wow_pct)
        prev_mean = w_mean

        weekly_timeline.append({
            "period": w_str,
            "period_label": f"Week {w_str.split('-W')[-1]}",
            "mean": w_mean,
            "total": round(float(r["sum"]), 2),
            "count": int(r["count"]),
            "wow_growth_pct": wow_pct
        })

    avg_wow_velocity = round(float(np.mean(wow_velocities)), 2) if wow_velocities else 0.0

    # --- 3. Monthly Rollup (Per Month) ---
    valid["__month_str"] = valid["__parsed_date"].dt.strftime("%Y-%m")
    month_grp = valid.groupby("__month_str")["__meas"].agg(["mean", "sum", "count"]).reset_index()

    monthly_timeline = []
    prev_m_mean = None
    for _, r in month_grp.iterrows():
        m_str = str(r["__month_str"])
        m_mean = round(float(r["mean"]), 2)
        mom_pct = round(((m_mean - prev_m_mean) / prev_m_mean) * 100, 1) if prev_m_mean and prev_m_mean > 0 else None
        prev_m_mean = m_mean
        monthly_timeline.append({
            "period": m_str,
            "period_label": pd.to_datetime(m_str + "-01").strftime("%b %Y"),
            "mean": m_mean,
            "total": round(float(r["sum"]), 2),
            "count": int(r["count"]),
            "mom_growth_pct": mom_pct
        })

    # --- 4. Annual & Annualized Run-Rate (Per Annum) ---
    valid["__year_str"] = valid["__parsed_date"].dt.strftime("%Y")
    year_grp = valid.groupby("__year_str")["__meas"].agg(["mean", "sum", "count"]).reset_index()
    annual_timeline = [
        {
            "period": str(r["__year_str"]),
            "mean": round(float(r["mean"]), 2),
            "total": round(float(r["sum"]), 2),
            "count": int(r["count"])
        }
        for _, r in year_grp.iterrows()
    ]

    is_partial_year = days_span < 330
    overall_mean = round(float(valid["__meas"].mean()), 2)
    overall_total = round(float(valid["__meas"].sum()), 2)

    if days_span >= 7:
        annualized_run_rate = round((overall_total / days_span) * 365.25, 2)
    else:
        annualized_run_rate = round(overall_total * 52, 2)

    unit_prefix = "$" if unit == "$" else ""
    unit_suffix = "" if unit == "$" else f" {unit}"
    run_rate_label = f"{unit_prefix}{annualized_run_rate:,.2f}{unit_suffix} Annualized Run-Rate"

    # --- 5. Insights Generation ---
    insights = []
    if peak_day != "N/A" and lowest_day != "N/A" and peak_day != lowest_day:
        p_val = next(d["mean"] for d in daily_breakdown if d["day"] == peak_day)
        l_val = next(d["mean"] for d in daily_breakdown if d["day"] == lowest_day)
        diff_pct = round(((p_val - l_val) / max(l_val, 0.001)) * 100, 1)
        insights.append(
            f"Daily Pattern: {peak_day}s benchmark peak {meas_label.lower()} ({unit_prefix}{p_val}{unit_suffix}), "
            f"outpacing {lowest_day}s by +{diff_pct}%."
        )

    if len(weekly_timeline) >= 2:
        top_w = max(weekly_timeline, key=lambda x: x["mean"])
        insights.append(
            f"Weekly Velocity: {top_w['period_label']} achieved highest volume at "
            f"{unit_prefix}{top_w['mean']}{unit_suffix} (average WoW momentum: {avg_wow_velocity:+.1f}%)."
        )

    if is_partial_year:
        insights.append(
            f"Annual Projection: {run_rate_label} projected across full annual operating cycle "
            f"(grounded in {days_span} observed days)."
        )

    # Form timeline_series for frontend charts
    timeline_series = [
        {
            "period": w["period_label"],
            "date": w["period"],
            "value": w["mean"],
            "total": w["total"],
            "count": w["count"]
        }
        for w in (weekly_timeline if len(weekly_timeline) >= 3 else monthly_timeline)
    ]

    return {
        "has_temporal_data": True,
        "grain_type": "long_format_dates",
        "date_column": date_col,
        "primary_measure": primary_measure,
        "unit": unit,
        "days_span": days_span,
        "is_partial_year": is_partial_year,
        "daily": {
            "has_daily": len(daily_breakdown) > 0,
            "day_of_week_breakdown": daily_breakdown,
            "peak_day": peak_day,
            "lowest_day": lowest_day
        },
        "weekly": {
            "has_weekly": len(weekly_timeline) > 0,
            "timeline": weekly_timeline,
            "peak_week": max(weekly_timeline, key=lambda x: x["mean"])["period_label"] if weekly_timeline else None,
            "avg_wow_velocity": avg_wow_velocity
        },
        "monthly": {
            "has_monthly": len(monthly_timeline) > 0,
            "timeline": monthly_timeline,
            "peak_month": max(monthly_timeline, key=lambda x: x["mean"])["period_label"] if monthly_timeline else None
        },
        "annual": {
            "has_annual": True,
            "is_annualized_projection": is_partial_year,
            "annual_timeline": annual_timeline,
            "annualized_run_rate": annualized_run_rate,
            "run_rate_label": run_rate_label
        },
        "timeline_series": timeline_series,
        "insights": insights
    }


def _process_wide_format_temporal(
    df: pd.DataFrame,
    period_columns: list[str]
) -> dict[str, Any]:
    """Computes period-over-period and annualized run-rates for wide-format sequential columns."""
    weekly_timeline = []
    prev_mean = None
    wow_velocities = []

    for idx, col in enumerate(period_columns, 1):
        num_s = _clean_numeric_series(df[col]).dropna()
        if num_s.empty:
            continue
        w_mean = round(float(num_s.mean()), 2)
        w_total = round(float(num_s.sum()), 2)
        w_count = int(num_s.count())

        wow_pct = round(((w_mean - prev_mean) / prev_mean) * 100, 1) if prev_mean and prev_mean > 0 else None
        if wow_pct is not None:
            wow_velocities.append(wow_pct)
        prev_mean = w_mean

        weekly_timeline.append({
            "period": f"Period_{idx}",
            "period_label": col,
            "mean": w_mean,
            "total": w_total,
            "count": w_count,
            "wow_growth_pct": wow_pct
        })

    if not weekly_timeline:
        return _empty_temporal_result()

    top_w = max(weekly_timeline, key=lambda x: x["mean"])
    low_w = min(weekly_timeline, key=lambda x: x["mean"])
    avg_wow_velocity = round(float(np.mean(wow_velocities)), 2) if wow_velocities else 0.0

    # Annualization: each bracket typically represents 1 week (52 weeks/year) or 1 month (12 months/year)
    bracket_count = len(weekly_timeline)
    is_monthly = any(m in period_columns[0].lower() for m in ("jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"))
    multiplier = 12 / max(bracket_count, 1) if is_monthly else 52 / max(bracket_count, 1)

    all_means = [w["mean"] for w in weekly_timeline]
    all_totals = [w["total"] for w in weekly_timeline]
    annualized_run_rate = round(float(sum(all_totals) * multiplier), 2)
    run_rate_label = f"{annualized_run_rate:,.2f} Annualized Projected Volume (based on {bracket_count} observed cycles)"

    insights = [
        f"Temporal Trajectory: '{top_w['period_label']}' reached peak volume with an average of {top_w['mean']} "
        f"(outpacing '{low_w['period_label']}' by +{round(((top_w['mean'] - low_w['mean']) / max(low_w['mean'], 0.001)) * 100, 1)}%).",
        f"Velocity Trend: Week-over-week momentum shifted at an average rate of {avg_wow_velocity:+.1f}%.",
        f"Annualized Projection: {run_rate_label}."
    ]

    timeline_series = [
        {
            "period": w["period_label"],
            "date": w["period"],
            "value": w["mean"],
            "total": w["total"],
            "count": w["count"]
        }
        for w in weekly_timeline
    ]

    return {
        "has_temporal_data": True,
        "grain_type": "wide_sequential_periods",
        "date_column": "Sequential Columns",
        "primary_measure": "Recorded Period Volume",
        "unit": "units",
        "days_span": bracket_count * 7,
        "is_partial_year": True,
        "daily": {"has_daily": False, "day_of_week_breakdown": [], "peak_day": None, "lowest_day": None},
        "weekly": {
            "has_weekly": True,
            "timeline": weekly_timeline,
            "peak_week": top_w["period_label"],
            "avg_wow_velocity": avg_wow_velocity
        },
        "monthly": {"has_monthly": False, "timeline": []},
        "annual": {
            "has_annual": True,
            "is_annualized_projection": True,
            "annual_timeline": [],
            "annualized_run_rate": annualized_run_rate,
            "run_rate_label": run_rate_label
        },
        "timeline_series": timeline_series,
        "insights": insights
    }


def extract_bivariate_categorical_insights(
    df: pd.DataFrame,
    columns: list[str] | None = None
) -> dict[str, Any]:
    """Computes comprehensive group-by cross-tabulations and category disparity insights."""
    if df is None or df.empty:
        return _empty_categorical_result()

    cols = columns or list(df.columns)
    n_rows = len(df)

    # 1. Identify Candidate Dimensions (Discrete, Categorical)
    candidate_dims = []
    for c in cols:
        if c not in df.columns:
            continue
        c_clean = str(c).lower().replace("_", "").replace(" ", "")
        if c.startswith("interact_") or any(op in c for op in ("+", "*", "/", "=")) or any(t in c_clean for t in ("id", "code", "phone", "email", "url", "index", "name", "fullname", "employeename")):
            continue
        is_num = pd.api.types.is_numeric_dtype(df[c])
        if is_num:
            is_dim_keyword = any(k in c_clean for k in ("store", "cluster", "tier", "band", "flag", "group", "class", "grade"))
            if pd.api.types.is_float_dtype(df[c]) and not is_dim_keyword:
                continue
            num_s = pd.to_numeric(df[c], errors="coerce").dropna()
            if num_s.empty or num_s.nunique() > 12 or not (num_s == num_s.round()).all():
                continue
            if not is_dim_keyword and num_s.nunique() > 8:
                continue

        series_clean = df[c].dropna().astype(str).str.strip()
        n_unique = series_clean.nunique()
        if 2 <= n_unique <= 40 and (n_unique / max(n_rows, 1)) < 0.75:
            candidate_dims.append(c)

    # 2. Identify Candidate Continuous Measures
    candidate_meas = []
    for c in cols:
        if c not in df.columns or c in candidate_dims:
            continue
        c_clean = str(c).lower().replace("_", "").replace(" ", "")
        if c.startswith("interact_") or any(op in c for op in ("+", "*", "/", "=")) or any(t in c_clean for t in ("id", "code", "phone", "email", "url", "key", "name", "fullname", "employeename")):
            continue
        num_s = _clean_numeric_series(df[c])
        if num_s.notna().sum() >= max(3, int(n_rows * 0.35)) and num_s.nunique() > 2:
            candidate_meas.append(c)

    if not candidate_dims or not candidate_meas:
        return _empty_categorical_result()

    # Prioritize key dimensions (Department, Role, Region, Store, Category, Shift)
    candidate_dims.sort(key=lambda d: (
        0 if any(k in d.lower() for k in ("dept", "department", "team", "division", "store", "role", "region", "category", "shift")) else 1
    ))

    breakdowns: dict[str, dict[str, Any]] = {}
    prioritized_insights: list[str] = []

    for dim in candidate_dims[:5]:
        breakdowns[dim] = {}
        dim_label = format_display_label(dim)

        for meas in candidate_meas[:4]:
            meas_label = format_display_label(meas)
            unit = infer_measure_unit(meas)
            unit_prefix = "$" if unit == "$" else ""
            unit_suffix = "" if unit == "$" else f" {unit}"

            sub_df = pd.DataFrame({
                "cat": df[dim].astype(str).str.strip(),
                "val": _clean_numeric_series(df[meas])
            }).dropna()

            if sub_df.empty or sub_df["cat"].nunique() < 2:
                continue

            grp = sub_df.groupby("cat")["val"].agg(["mean", "sum", "count"]).sort_values("mean", ascending=False)
            tot_population = len(sub_df)
            tot_sum = sub_df["val"].sum()

            categories = []
            means = []
            totals = []
            counts = []
            shares = []
            table_rows = []

            for cat_name, r in grp.iterrows():
                m_val = round(float(r["mean"]), 2)
                t_val = round(float(r["sum"]), 2)
                c_val = int(r["count"])
                s_pct = round((c_val / max(tot_population, 1)) * 100, 1)

                categories.append(str(cat_name))
                means.append(m_val)
                totals.append(t_val)
                counts.append(c_val)
                shares.append(s_pct)

                table_rows.append({
                    "category": str(cat_name),
                    "mean": m_val,
                    "total": t_val,
                    "count": c_val,
                    "share_pct": s_pct
                })

            top_cat = categories[0]
            top_mean = means[0]
            bot_cat = categories[-1]
            bot_mean = means[-1]

            disp_ratio = round(top_mean / max(bot_mean, 0.001), 2)
            disparity_pct = round(((top_mean - bot_mean) / max(bot_mean, 0.001)) * 100, 1)
            pop_mean = round(float(sub_df["val"].mean()), 2)

            insight = (
                f"Across {dim_label}, '{top_cat}' leads in {meas_label} with an average of "
                f"{unit_prefix}{top_mean}{unit_suffix} (+{disparity_pct}% higher than '{bot_cat}' at "
                f"{unit_prefix}{bot_mean}{unit_suffix}, representing a {disp_ratio}x dispersion spread)."
            )

            breakdowns[dim][meas] = {
                "dimension": dim,
                "measure": meas,
                "dimension_label": dim_label,
                "measure_label": meas_label,
                "unit": unit,
                "categories": categories,
                "means": means,
                "totals": totals,
                "counts": counts,
                "shares": shares,
                "table_rows": table_rows,
                "top_category": top_cat,
                "top_mean": top_mean,
                "bottom_category": bot_cat,
                "bottom_mean": bot_mean,
                "disparity_pct": disparity_pct,
                "dispersion_ratio": disp_ratio,
                "overall_mean": pop_mean,
                "total_records": tot_population,
                "insight": insight
            }

            if len(prioritized_insights) < 6:
                prioritized_insights.append(insight)

    return {
        "has_categorical_data": len(breakdowns) > 0,
        "dimensions": list(breakdowns.keys()),
        "measures": candidate_meas[:4],
        "breakdowns": breakdowns,
        "insights": prioritized_insights
    }


def _empty_temporal_result() -> dict[str, Any]:
    return {
        "has_temporal_data": False,
        "grain_type": "none",
        "date_column": None,
        "primary_measure": None,
        "unit": "units",
        "days_span": 0,
        "is_partial_year": False,
        "daily": {"has_daily": False, "day_of_week_breakdown": [], "peak_day": None, "lowest_day": None},
        "weekly": {"has_weekly": False, "timeline": [], "peak_week": None, "avg_wow_velocity": 0.0},
        "monthly": {"has_monthly": False, "timeline": [], "peak_month": None},
        "annual": {"has_annual": False, "is_annualized_projection": False, "annual_timeline": [], "annualized_run_rate": 0.0, "run_rate_label": ""},
        "timeline_series": [],
        "insights": []
    }


def _empty_categorical_result() -> dict[str, Any]:
    return {
        "has_categorical_data": False,
        "dimensions": [],
        "measures": [],
        "breakdowns": {},
        "insights": []
    }
