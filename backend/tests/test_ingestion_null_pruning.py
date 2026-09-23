"""Tests for ingestion null-value pruning, decision selection hints, and report null filtering."""

import pandas as pd
import pytest
from pathlib import Path
from tempfile import NamedTemporaryFile

from app.services.sheet_catalog import (
    is_null_value,
    value_key,
    read_sheets,
    compute_decision_hints,
    prepare_sheets
)
from app.services.report_generator import generate_html_executive_report


def test_is_null_value_normalization():
    """Verify that all spreadsheet null representations are recognized as missing."""
    assert is_null_value(None) is True
    assert is_null_value("") is True
    assert is_null_value("   ") is True
    assert is_null_value("NA") is True
    assert is_null_value("N/A") is True
    assert is_null_value("na") is True
    assert is_null_value("null") is True
    assert is_null_value("NULL") is True
    assert is_null_value("None") is True
    assert is_null_value("nan") is True
    assert is_null_value("-") is True
    assert is_null_value("#N/A") is True

    # Legitimate non-null values
    assert is_null_value("Active") is False
    assert is_null_value("0") is False
    assert is_null_value(0) is False
    assert is_null_value("Department A") is False
    assert is_null_value("123.45") is False


def test_value_key_null_safety():
    """Verify that value_key returns empty string for any null variant."""
    assert value_key(None) == ""
    assert value_key("   ") == ""
    assert value_key("N/A") == ""
    assert value_key("null") == ""
    assert value_key("None") == ""
    assert value_key("nan") == ""
    assert value_key("Department A") == "department a"
    assert value_key("00142") == "00142"


def test_read_sheets_prunes_100_percent_null_columns():
    """Verify that completely empty and trailing phantom Unnamed columns are pruned during read."""
    with NamedTemporaryFile(suffix='.csv', mode='w', delete=False) as f:
        # Create a CSV with valid columns, a 100% empty column, and an Unnamed phantom column
        f.write("Employee_ID,Department,Empty_Notes,Salary,Unnamed: 4\n")
        f.write("E01,Sales,,50000,\n")
        f.write("E02,Engineering,NA,85000,   \n")
        f.write("E03,Marketing,null,62000,null\n")
        f.write("E04,Sales,None,52000,-\n")
        temp_path = Path(f.name)

    try:
        frames = read_sheets(temp_path)
        assert 'Sheet1' in frames
        df = frames['Sheet1']

        # Valid columns should be retained
        assert 'Employee_ID' in df.columns
        assert 'Department' in df.columns
        assert 'Salary' in df.columns

        # Empty_Notes had all null strings ("", "NA", "null", "None") -> must be pruned!
        assert 'Empty_Notes' not in df.columns

        # Unnamed: 4 was completely empty/whitespace -> must be pruned!
        assert 'Unnamed: 4' not in df.columns
    finally:
        temp_path.unlink(missing_ok=True)


def test_compute_decision_hints():
    """Verify that compute_decision_hints recommends components based on empirical shape."""
    profiles = [
        {
            'column': 'Department',
            'canonical': 'department',
            'distinct': 4,
            'null_percentage': 0.0,
            'is_mostly_null': False
        },
        {
            'column': 'Salary',
            'canonical': 'salary',
            'distinct': 50,
            'null_percentage': 2.0,
            'is_mostly_null': False,
            'numeric': {'min': 40000, 'max': 120000, 'mean': 75000, 'sum': 3750000}
        },
        {
            'column': 'Performance_Score',
            'canonical': 'performance_score',
            'distinct': 10,
            'null_percentage': 5.0,
            'is_mostly_null': False,
            'numeric': {'min': 1, 'max': 5, 'mean': 3.8, 'sum': 190}
        },
        {
            'column': 'Review_Date',
            'canonical': 'review_date',
            'distinct': 12,
            'null_percentage': 1.0,
            'is_mostly_null': False
        }
    ]
    records = [{'Department': 'Sales', 'Salary': '50000'}] * 50

    hints = compute_decision_hints(profiles, records)

    assert hints['data_quality_score'] >= 90
    assert 'Salary' in hints['primary_metrics']
    assert 'Department' in hints['primary_dimensions']
    assert hints['has_timeline'] is True

    # With numeric and categorical dimensions present, comparison_bar and area_trend should be recommended
    assert 'comparison_bar' in hints['recommended_components']
    assert 'area_trend' in hints['recommended_components']
    assert 'gauge' in hints['recommended_components']
    assert 'heatmap' in hints['recommended_components']


def test_prepare_sheets_attaches_hints_and_null_pct():
    """Verify prepare_sheets calculates null_percentage and attaches decision_hints."""
    df = pd.DataFrame({
        'Department': ['Sales', 'IT', 'Marketing', 'Sales'],
        'Performance': ['4.2', '3.8', '4.5', '3.1'],
        'Sparse_Notes': ['some note', 'null', 'none', '']
    })
    frames = {'Sheet1': df}

    prepared = prepare_sheets(frames, 'test.csv', embed=False)
    assert len(prepared) == 1
    sheet = prepared[0]

    assert 'decision_hints' in sheet
    hints = sheet['decision_hints']
    assert 'recommended_components' in hints
    assert hints['total_records'] == 4

    # Check Sparse_Notes null_percentage
    sparse_p = next(p for p in sheet['profiles'] if p['column'] == 'Sparse_Notes')
    # 3 out of 4 values are null ("null", "none", "") -> 75%
    assert sparse_p['null_percentage'] == 75.0
    assert sparse_p['nonempty'] == 1
