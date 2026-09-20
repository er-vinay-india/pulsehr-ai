import pytest
from app.services.display_formatters import (
    format_display_label,
    generate_analytical_title,
    sanitize_llm_text,
    RECOGNIZED_ACRONYMS,
)


def test_format_display_label_snake_case():
    assert format_display_label("Weekly_Sales") == "Weekly sales"
    assert format_display_label("Holiday_Flag") == "Holiday flag"
    assert format_display_label("Fuel_Price") == "Fuel price"
    assert format_display_label("average_monthly_income") == "Average monthly income"
    assert format_display_label("DEPARTMENT_NAME") == "Department name"


def test_format_display_label_camel_and_kebab_case():
    assert format_display_label("employeeID") == "Employee ID"
    assert format_display_label("monthlyIncome") == "Monthly income"
    assert format_display_label("total-headcount") == "Total headcount"
    assert format_display_label("firstName") == "First name"


def test_format_display_label_acronym_preservation():
    assert format_display_label("CPI") == "CPI"
    assert format_display_label("HR_Department") == "HR department"
    assert format_display_label("FTE_Count") == "FTE count"
    assert format_display_label("Employee_KPI_Score") == "Employee KPI score"
    assert format_display_label("USD_Gross_Revenue") == "USD gross revenue"
    assert format_display_label("OLS_Regression_Fit") == "OLS regression fit"


def test_format_display_label_joined_prefixes():
    assert format_display_label("left.Weekly_Sales") == "left Weekly sales"
    assert format_display_label("right.Store") == "right Store"


def test_format_display_label_edge_cases():
    assert format_display_label("") == ""
    assert format_display_label(None) == ""
    assert format_display_label("Store") == "Store"
    assert format_display_label("Date") == "Date"


def test_generate_analytical_title_binary_holiday_comparison():
    title, subtitle = generate_analytical_title(
        calc_type="Arithmetic Mean",
        metric_col="Weekly_Sales",
        group_col="Holiday_Flag",
        comparison_type="binary_flag"
    )
    assert title == "Average weekly sales: Holiday vs non-holiday"
    assert "holiday and regular weeks" in subtitle.lower()


def test_generate_analytical_title_categorical_ranking():
    title, subtitle = generate_analytical_title(
        calc_type="Arithmetic Mean",
        metric_col="Weekly_Sales",
        group_col="Store",
        total_count=45
    )
    assert title == "Average weekly sales by store"
    assert subtitle == "Ranked across 45 store entities by average weekly sales"


def test_generate_analytical_title_time_series():
    title, subtitle = generate_analytical_title(
        calc_type="Summation",
        metric_col="Weekly_Sales",
        group_col="Date",
        comparison_type="time_series",
        total_count=143
    )
    assert title == "Total network weekly sales over time"
    assert subtitle == "Longitudinal progression across 143 recorded periods"


def test_generate_analytical_title_donut():
    title, subtitle = generate_analytical_title(
        calc_type="Distribution",
        metric_col="Periods",
        group_col="Holiday_Flag",
        comparison_type="donut",
        total_count=6435
    )
    assert title == "Distribution: Holiday vs non-holiday"
    assert "6435 recorded periods" in subtitle


def test_sanitize_llm_text_replaces_outside_code_blocks():
    text = "The Weekly_Sales showed variance. In SQL: `SELECT Weekly_Sales FROM table`."
    mapping = {"Weekly_Sales": "weekly sales"}
    sanitized = sanitize_llm_text(text, mapping)
    assert "The weekly sales showed variance." in sanitized
    assert "`SELECT Weekly_Sales FROM table`" in sanitized
