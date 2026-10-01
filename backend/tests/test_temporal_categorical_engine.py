"""Targeted unit tests for Multi-Grain Temporal & Bivariate Categorical Analytics Engine.

Tests:
1. Long-format date multi-grain temporal analytics (Daily, Weekly, Monthly, Annual).
2. Wide-format sequential period detection & annualized run-rate projections.
3. Bivariate categorical dimension x measure cross-tabulations & dispersion spreads.
4. Presentation scope detector integration for wide sequential periods.
5. Presentation data profiler integration (traceable metrics & pattern discovery).
6. Chart synthesizer fallbacks for multi-grain lines and categorical bars.
7. Dynamic visual planner line chart generation for wide datasets.
"""

import pandas as pd
import pytest

from app.services.analytics.temporal_categorical_engine import (
    extract_multi_grain_temporal_insights,
    extract_bivariate_categorical_insights,
)
from app.services.presentation.scope_detector import detect_sheet_date_range
from app.services.presentation.data_profiler import profile_presentation_dataset
from app.services.presentation.chart_fallbacks import (
    synthesize_fallback_line_chart,
    synthesize_fallback_bar_chart,
)
from app.services.planner.chart_plans import build_line_chart_plans


def test_long_format_multi_grain_temporal_insights():
    """Verify daily, weekly, monthly, and annual rollups on long date columns."""
    dates = pd.date_range("2026-01-01", periods=60, freq="D")
    data = {
        "Transaction_Date": [d.strftime("%Y-%m-%d") for d in dates],
        "Sales_Volume": [100.0 + (i % 7) * 20.0 + i * 2.0 for i in range(60)],
        "Department": ["Electronics" if i % 2 == 0 else "Apparel" for i in range(60)],
    }
    df = pd.DataFrame(data)

    res = extract_multi_grain_temporal_insights(df, list(df.columns))
    assert res["has_temporal_data"] is True
    assert res["grain_type"] == "long_format_dates"
    assert res["primary_measure"] == "Sales_Volume"

    # Daily breakdown
    daily = res["daily"]
    assert daily["has_daily"] is True
    assert len(daily["day_of_week_breakdown"]) == 7
    days = [d["day"] for d in daily["day_of_week_breakdown"]]
    assert "Monday" in days
    assert "Sunday" in days
    assert daily["peak_day"] in days

    # Weekly rollup
    weekly = res["weekly"]
    assert weekly["has_weekly"] is True
    assert len(weekly["timeline"]) >= 8
    assert weekly["peak_week"] is not None
    assert isinstance(weekly["avg_wow_velocity"], float)

    # Monthly rollup
    monthly = res["monthly"]
    assert monthly["has_monthly"] is True
    assert len(monthly["timeline"]) >= 2

    # Annual
    annual = res["annual"]
    assert annual["has_annual"] is True
    assert annual["annualized_run_rate"] > 0


def test_wide_format_sequential_periods_temporal_insights():
    """Verify sequential period brackets (e.g. 1st to 5th July) on wide tables."""
    data = {
        "Employee_ID": [f"EMP_{i:03d}" for i in range(1, 21)],
        "Department": ["Logistics", "Operations", "Finance", "HR"] * 5,
        "1st to 5th July": [4.0 + (i % 3) for i in range(20)],
        "6th to 12th July": [5.0 + (i % 3) for i in range(20)],
        "13th to 19th July": [6.0 + (i % 3) for i in range(20)],
        "20th to 26th July": [5.5 + (i % 3) for i in range(20)],
        "27th to 31st July": [4.5 + (i % 3) for i in range(20)],
        "interact_1st_to_5th_July*2": [8.0 for _ in range(20)],  # should be ignored
    }
    df = pd.DataFrame(data)
    cols = list(df.columns)

    res = extract_multi_grain_temporal_insights(df, cols)
    assert res["has_temporal_data"] is True
    assert res["grain_type"] == "wide_sequential_periods"

    weekly = res["weekly"]
    assert weekly["has_weekly"] is True
    assert len(weekly["timeline"]) == 5
    timeline_labels = [w["period_label"] for w in weekly["timeline"]]
    assert "1st to 5th July" in timeline_labels
    assert "27th to 31st July" in timeline_labels
    assert "interact_1st_to_5th_July*2" not in timeline_labels

    annual = res["annual"]
    assert annual["is_annualized_projection"] is True
    assert annual["annualized_run_rate"] > 0
    assert len(res["insights"]) >= 2


def test_bivariate_categorical_insights():
    """Verify categorical dimension x measure cross-tabulations and dispersion spreads."""
    data = {
        "Department": ["Logistics"] * 10 + ["Operations"] * 10 + ["Engineering"] * 10,
        "Daily_Attendance": [3.5] * 10 + [4.8] * 10 + [5.2] * 10,
        "Overtime_Hours": [12.0] * 10 + [6.0] * 10 + [2.0] * 10,
    }
    df = pd.DataFrame(data)
    cols = list(df.columns)

    res = extract_bivariate_categorical_insights(df, cols)
    assert res["has_categorical_data"] is True
    assert "Department" in res["dimensions"]
    assert "Daily_Attendance" in res["measures"] or "Overtime_Hours" in res["measures"]

    dept_att = res["breakdowns"]["Department"]["Daily_Attendance"]
    assert dept_att["top_category"] == "Engineering"
    assert dept_att["top_mean"] == 5.2
    assert dept_att["bottom_category"] == "Logistics"
    assert dept_att["bottom_mean"] == 3.5
    assert dept_att["dispersion_ratio"] == round(5.2 / 3.5, 2)
    assert dept_att["disparity_pct"] > 0
    assert len(dept_att["table_rows"]) == 3
    assert len(res["insights"]) >= 1


def test_scope_detector_wide_sequential_periods():
    """Verify detect_sheet_date_range fallback detects wide sequential periods."""
    records = [
        {"1st to 5th July": 4.5, "6th to 12th July": 5.0, "13th to 19th July": 5.5, "Department": "Ops"},
        {"1st to 5th July": 4.0, "6th to 12th July": 4.8, "13th to 19th July": 5.2, "Department": "HR"},
        {"1st to 5th July": 4.2, "6th to 12th July": 4.9, "13th to 19th July": 5.4, "Department": "Finance"},
    ]
    cols = ["Department", "1st to 5th July", "6th to 12th July", "13th to 19th July"]

    date_info = detect_sheet_date_range(records, cols)
    assert date_info["has_date"] is True
    assert "1st to 5th July" in date_info["period_label"]
    assert "13th to 19th July" in date_info["period_label"]
    assert date_info["is_partial_year"] is True
    assert date_info["days_span"] == 21


def test_presentation_data_profiler_enrichment():
    """Verify profile_presentation_dataset attaches temporal and categorical profiles."""
    records = [
        {"Dept": "Engineering", "Week_1": 40.0, "Week_2": 42.0, "Week_3": 44.0},
        {"Dept": "Logistics", "Week_1": 35.0, "Week_2": 36.0, "Week_3": 34.0},
        {"Dept": "Operations", "Week_1": 38.0, "Week_2": 39.0, "Week_3": 40.0},
    ]
    cols = ["Dept", "Week_1", "Week_2", "Week_3"]

    profile = profile_presentation_dataset(records, cols)
    assert profile["total_records"] == 3
    assert "temporal_profile" in profile
    assert "categorical_profile" in profile

    metric_ids = [m["metric_id"] for m in profile["traceable_metrics"]]
    assert any("TEMP" in m_id or "CAT" in m_id for m_id in metric_ids)


def test_chart_fallbacks_synthesize_clean_specs():
    """Verify fallback line and bar charts synthesize rich specs from analytics."""
    sheet_candidates = [{
        "id": 1,
        "name": "July Attendance",
        "original_name": "Attendance_July_2026.xlsx",
        "columns": ["Department", "Week 1", "Week 2", "Week 3", "Week 4"],
        "records": [
            {"Department": "Engineering", "Week 1": 40.0, "Week 2": 42.0, "Week 3": 43.0, "Week 4": 44.0},
            {"Department": "Sales", "Week 1": 36.0, "Week 2": 37.0, "Week 3": 38.0, "Week 4": 39.0},
            {"Department": "Support", "Week 1": 32.0, "Week 2": 33.0, "Week 3": 34.0, "Week 4": 35.0},
        ]
    }]

    line_chart = synthesize_fallback_line_chart(sheet_candidates)
    assert line_chart is not None
    assert line_chart["chart_type"] == "line"
    assert len(line_chart["categories"]) == 4
    assert len(line_chart["series"][0]["values"]) == 4
    assert line_chart["overall_mean"] > 0

    bar_chart = synthesize_fallback_bar_chart(sheet_candidates)
    assert bar_chart is not None
    assert bar_chart["chart_type"] in ("bar", "column")
    assert len(bar_chart["categories"]) == 3
    assert "Engineering" in bar_chart["categories"]
    assert bar_chart["series"][0]["values"][0] >= bar_chart["series"][0]["values"][-1]


def test_dynamic_chart_plans_for_wide_sequential():
    """Verify build_line_chart_plans creates line chart plan on wide sequential tables."""
    data = {
        "Employee_ID": [f"E{i}" for i in range(10)],
        "Week 1": [10.0 + i for i in range(10)],
        "Week 2": [12.0 + i for i in range(10)],
        "Week 3": [14.0 + i for i in range(10)],
    }
    df = pd.DataFrame(data)
    sorted_numeric = [("Week 1", {"clean_col": "Week 1", "unit": "hrs", "is_additive": False, "valid_count": 10, "missing_count": 0})]

    plans = build_line_chart_plans(
        df=df,
        n_rows=10,
        date_cols=[],  # No long-format date column
        sorted_numeric=sorted_numeric,
        original_file="test_attendance.xlsx"
    )

    assert len(plans) >= 1
    assert plans[0]["chart_type"] == "line"
    assert len(plans[0]["points"]) == 3
