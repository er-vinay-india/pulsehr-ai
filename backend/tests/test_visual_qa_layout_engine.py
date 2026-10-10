"""Tests for Phase 9.9 Rendered Visual QA & Adaptive Layout Engine.

Validates:
1. ChartFormatterValidator (zero unresolved {token} or literal {value}% output)
2. AdaptiveChartLayoutEngine (dynamic height scaling, label margins, plot-area ratio)
3. Five Permanent Visual Gates (Theme, Accessibility, Layout, Formatter, Render)
"""
import pytest
from app.services.adaptive_dashboard.formatter_validator import ChartFormatterValidator
from app.services.adaptive_dashboard.layout_engine import AdaptiveChartLayoutEngine
from app.services.adaptive_dashboard.theme_validator import ThemeIntegrityValidator
from app.services.adaptive_dashboard.visual_compiler import VisualCompiler, VisualIntent


def test_axis_never_renders_literal_value_token():
    """Verify that literal '{value}%' on axis labels is flagged by FormatterValidator."""
    broken_option = {
        "xAxis": {"type": "category", "data": ["A", "B"]},
        "yAxis": {"type": "value", "axisLabel": {"formatter": "{value}%"}},
        "series": [{"type": "bar", "data": [10, 20]}],
    }

    report = ChartFormatterValidator.validate_option(broken_option)
    assert not report.passed, "Expected FormatterValidator to reject literal {value}%"
    assert any("unresolved token" in v for v in report.violations)

    # Sanitize and verify repair
    repaired = ChartFormatterValidator.sanitize_option(broken_option)
    assert "formatter" not in repaired["yAxis"]["axisLabel"]
    assert repaired["yAxis"]["axisLabel"].get("_unit_suffix") == "%"


def test_tooltip_never_contains_unresolved_formatter():
    """Verify tooltip containing broken tokens like {metric_name} is rejected."""
    bad_tooltip_option = {
        "tooltip": {"formatter": "Department: {b}, Gap: {value} {metric_name}"},
        "xAxis": {"type": "category"},
        "yAxis": {"type": "value"},
        "series": [],
    }
    report = ChartFormatterValidator.validate_option(bad_tooltip_option)
    assert not report.passed
    assert any("tooltip.formatter" in v for v in report.violations)


def test_label_never_contains_template_placeholder():
    """Verify series labels and markLine labels do not contain broken placeholders."""
    bad_markline_option = {
        "xAxis": {"type": "value"},
        "yAxis": {"type": "category"},
        "series": [
            {
                "type": "bar",
                "markLine": {
                    "data": [
                        {"xAxis": 15.0, "label": {"formatter": "Target: {target_val}"}}
                    ]
                },
            }
        ],
    }
    report = ChartFormatterValidator.validate_option(bad_markline_option)
    assert not report.passed
    assert any("markLine" in v for v in report.violations)


def test_adaptive_layout_scales_height_with_categories():
    """Dynamic height rule: 3 categories ~260px, 8 categories ~400px, 15 categories ~650px."""
    plan_3 = AdaptiveChartLayoutEngine.plan(
        chart_type="horizontal_bar",
        category_count=3,
        longest_label_chars=6,
    )
    assert plan_3.chart_height >= 260
    assert plan_3.chart_height <= 300

    plan_8 = AdaptiveChartLayoutEngine.plan(
        chart_type="horizontal_bar",
        category_count=8,
        longest_label_chars=10,
    )
    assert plan_8.chart_height >= 390
    assert plan_8.chart_height <= 450

    plan_15 = AdaptiveChartLayoutEngine.plan(
        chart_type="horizontal_bar",
        category_count=15,
        longest_label_chars=12,
    )
    assert plan_15.chart_height >= 600
    assert plan_15.chart_height <= 660


def test_adaptive_layout_reserves_margin_for_long_labels():
    """For 37-character category labels, engine must reserve >= 200px on left grid."""
    plan_short = AdaptiveChartLayoutEngine.plan(
        chart_type="horizontal_bar",
        longest_label_chars=8,
    )
    assert plan_short.grid_left < 120

    plan_long = AdaptiveChartLayoutEngine.plan(
        chart_type="horizontal_bar",
        longest_label_chars=37,
    )
    assert plan_long.grid_left >= 200, f"Expected grid_left >= 200px for 37 chars, got {plan_long.grid_left}"


def test_adaptive_layout_enforces_plot_area_ratio():
    """Engine must guarantee plot area ratio >= 0.55."""
    plan = AdaptiveChartLayoutEngine.plan(
        chart_type="horizontal_bar",
        container_width=1000,
        container_height=400,
        category_count=5,
        longest_label_chars=15,
    )
    assert plan.plot_area_ratio >= 0.55, f"Expected ratio >= 0.55, got {plan.plot_area_ratio}"


def test_five_visual_gates_evaluation():
    """ThemeIntegrityValidator must evaluate all Five Permanent Visual Gates."""
    intent = VisualIntent(
        intent="compare_ranked_categories",
        metric_name="Attendance Days",
        unit="days",
        benchmark_value=15.0,
    )
    option = VisualCompiler.compile_ranked_categories(
        categories=["Engineering", "Operations", "Design"],
        values=[18.5, 21.2, 8.2],
        intent=intent,
    )

    qa = ThemeIntegrityValidator.evaluate_five_visual_gates(option)
    assert qa.passed, f"Expected 5 visual gates to pass, warnings: {qa.warnings}"
    assert qa.theme_integrity.passed
    assert qa.accessibility_integrity.passed
    assert qa.layout_integrity.passed
    assert qa.formatter_integrity is not None and qa.formatter_integrity.passed
    assert qa.render_integrity is not None and qa.render_integrity.passed


def test_tick_labels_have_minimum_spacing():
    """Verify that required tick spacing >= estimated label width + minimum gap."""
    spacing = AdaptiveChartLayoutEngine.estimate_tick_spacing(
        container_width=800.0,
        grid_left=50.0,
        grid_right=30.0,
        category_count=5,
    )
    assert spacing == 144.0

    label_width = AdaptiveChartLayoutEngine.estimate_label_width(longest_label_chars=7)
    min_gap = 12.0
    assert spacing >= (label_width + min_gap)


def test_time_axis_uses_compact_period_labels():
    """Verify deterministic conversion of verbose period strings to compact executive format."""
    assert AdaptiveChartLayoutEngine.compact_period_label("1st–5th Jul") == "1–5 Jul"
    assert AdaptiveChartLayoutEngine.compact_period_label("6th to 12th July") == "6–12 Jul"
    assert AdaptiveChartLayoutEngine.compact_period_label("13th–19th Jul") == "13–19 Jul"
    assert AdaptiveChartLayoutEngine.compact_period_label("20th to 26th July") == "20–26 Jul"
    assert AdaptiveChartLayoutEngine.compact_period_label("27th–31st Jul") == "27–31 Jul"

    compact_list = AdaptiveChartLayoutEngine.compact_categories([
        "1st–5th Jul", "6th–12th Jul", "13th–19th Jul", "20th–26th Jul", "27th–31st Jul"
    ])
    assert compact_list == ["1–5 Jul", "6–12 Jul", "13–19 Jul", "20–26 Jul", "27–31 Jul"]


def test_chart_switches_when_density_is_too_high():
    """Verify engine switches dense multi-series categorical charts to line charts."""
    # Narrow mobile container with 8 categories and 2 series
    should_switch = AdaptiveChartLayoutEngine.should_switch_to_line_chart(
        chart_type="grouped_bar",
        category_count=8,
        series_count=2,
        container_width=380.0,
        longest_label_chars=12,
    )
    assert should_switch, "Expected grouped bar with crowded tick spacing to switch to line chart"

    plan = AdaptiveChartLayoutEngine.plan(
        chart_type="grouped_bar",
        category_count=8,
        series_count=2,
        container_width=380.0,
        longest_label_chars=12,
    )
    assert plan.recommended_chart_type == "line"


def test_legend_does_not_reduce_plot_below_threshold():
    """Legend in multi-series shallow charts moves to top, keeping plot area ratio >= 0.55."""
    plan = AdaptiveChartLayoutEngine.plan(
        chart_type="line",
        container_width=600.0,
        container_height=250.0,
        category_count=5,
        series_count=2,
        longest_label_chars=8,
    )
    assert plan.legend_position == "top"
    assert plan.plot_area_ratio >= 0.55


def test_readability_integrity_passes():
    """Verify that ThemeIntegrityValidator evaluates and passes ReadabilityIntegrity for compact layout."""
    clean_option = {
        "_container_width": 750,
        "_planned_height": 260,
        "grid": {"left": 50, "right": 30, "top": 36, "bottom": 28, "containLabel": True},
        "legend": {"top": 4, "right": 10},
        "xAxis": {
            "type": "category",
            "data": ["1–5 Jul", "6–12 Jul", "13–19 Jul", "20–26 Jul", "27–31 Jul"],
            "axisLabel": {"fontSize": 11},
        },
        "yAxis": {"type": "value", "axisLabel": {"fontSize": 11}},
        "series": [
            {"type": "line", "name": "Office Attendance", "data": [128, 142, 136, 145, 138]},
            {"type": "line", "name": "Approved Leave", "data": [14, 18, 12, 16, 21]},
        ],
    }

    qa = ThemeIntegrityValidator.evaluate_six_visual_gates(clean_option)
    assert qa.passed, f"Expected 6 visual gates to pass, warnings: {qa.warnings}"
    assert qa.readability_integrity is not None
    assert qa.readability_integrity.passed
    assert len(qa.readability_integrity.violations) == 0

