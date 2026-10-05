"""Unit tests for Forecast Gatekeeper and Visual Compiler."""
from __future__ import annotations

import pytest

from app.services.adaptive_dashboard.forecast_gatekeeper import (
    ChangePoint,
    ForecastGatekeeper,
    ForecastPoint,
    ForecastResult,
)
from app.services.adaptive_dashboard.visual_compiler import (
    VisualCompiler,
    VisualIntent,
    VisualQAResult,
)


def test_forecast_gatekeeper_insufficient_history():
    """Verify that series with N < 6 periods are honestly rejected."""
    periods = ["2026-01", "2026-02", "2026-03", "2026-04"]
    values = [120.0, 125.0, 118.0, 130.0]

    result = ForecastGatekeeper.evaluate_forecast(periods, values, horizon=3)
    assert result.status == "insufficient_history"
    assert result.historical_count == 4
    assert len(result.forecast_points) == 0
    assert "Minimum 6 periods required" in result.message


def test_forecast_gatekeeper_short_series_projection():
    """Verify that series with 6 <= N < 24 periods use robust trend with confidence cone."""
    periods = [f"2026-{m:02d}" for m in range(1, 13)]
    # Upward trending series
    values = [10.0 + 1.5 * i for i in range(12)]

    result = ForecastGatekeeper.evaluate_forecast(periods, values, horizon=3)
    assert result.status == "available"
    assert result.model_used == "robust_linear_ses_cone"
    assert result.characterization == "short_series"
    assert len(result.forecast_points) == 3

    # Check that upper bound > predicted > lower bound
    for pt in result.forecast_points:
        assert pt.upper_bound >= pt.predicted_value
        assert pt.lower_bound <= pt.predicted_value


def test_forecast_gatekeeper_change_point_detection():
    """Verify sudden structural shifts (>2.0 sigma) are detected."""
    periods = [f"Period-{i:02d}" for i in range(1, 15)]
    # First 6 periods flat around 100, then sudden drop to 40
    values = [100.0, 101.0, 99.0, 102.0, 100.0, 98.0, 40.0, 42.0, 39.0, 41.0, 40.0, 43.0, 38.0, 41.0]

    change_points = ForecastGatekeeper.detect_change_points(periods, values, threshold_sigma=2.0)
    assert len(change_points) >= 1
    cp = change_points[0]
    assert cp.direction == "drop"
    assert cp.period == "Period-07"
    assert cp.shift_magnitude < -30.0


def test_counterfactual_scenario_simulator():
    """Verify deterministic what-if scenario outcomes."""
    baseline = 1000.0
    scenarios = [
        ("Optimistic Target (+15%)", 15.0),
        ("Conservative Headwind (-10%)", -10.0),
    ]

    impacts = ForecastGatekeeper.simulate_scenarios(
        baseline_value=baseline,
        metric_name="monthly_active_users",
        unit="users",
        scenarios=scenarios,
    )

    assert len(impacts) == 2
    assert impacts[0].projected_outcome == 1150.0
    assert impacts[0].delta_value == 150.0
    assert impacts[1].projected_outcome == 900.0
    assert impacts[1].delta_value == -100.0


def test_visual_compiler_ranked_categories():
    """Verify compilation of horizontal ranked category bar chart with benchmark."""
    intent = VisualIntent(
        intent="compare_ranked_categories",
        metric_name="attendance_days",
        dimension_name="department",
        unit="days",
        priority="hero",
        benchmark_value=12.1,
        highlight_categories=["Operations"],
    )

    cats = ["Finance", "Marketing", "Engineering", "Operations"]
    vals = [11.2, 10.5, 14.1, 17.2]

    option = VisualCompiler.compile_ranked_categories(cats, vals, intent)
    assert "xAxis" in option
    assert "yAxis" in option
    assert option["grid"]["containLabel"] is True
    assert option["yAxis"]["data"] == ["Marketing", "Finance", "Engineering", "Operations"]
    # Verify highlight on Operations
    series = option["series"][0]
    assert series["markLine"]["data"][0]["xAxis"] == 12.1

    qa = VisualCompiler.audit_visual_qa(option)
    assert qa.passed is True


def test_visual_compiler_trend_forecast_cone():
    """Verify compilation of trend chart with confidence cone."""
    intent = VisualIntent(
        intent="trend_forecast_cone",
        metric_name="headcount",
        unit="employees",
        priority="secondary",
    )

    hist_x = ["Jan", "Feb", "Mar", "Apr"]
    hist_y = [100.0, 105.0, 110.0, 115.0]
    fc_x = ["May", "Jun"]
    fc_y = [120.0, 125.0]
    lower = [115.0, 118.0]
    upper = [125.0, 132.0]

    option = VisualCompiler.compile_trend_forecast_cone(hist_x, hist_y, fc_x, fc_y, lower, upper, intent)
    assert len(option["series"]) == 4  # history, forecast, lower band, cone area
    assert option["xAxis"]["data"] == ["Jan", "Feb", "Mar", "Apr", "May", "Jun"]

    qa = VisualCompiler.audit_visual_qa(option)
    assert qa.passed is True
