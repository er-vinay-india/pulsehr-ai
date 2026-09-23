"""Tests for the deterministic Data Engine: Validator, Profiler, and MetricEngine."""

import pandas as pd
import pytest

from app.services.data_engine.validator import DatasetValidator
from app.services.data_engine.profiler import DatasetProfiler
from app.services.data_engine.metric_engine import MetricEngine


@pytest.fixture
def sample_sales_df():
    return pd.DataFrame({
        "employee_id": ["E101", "E102", "E103", "E104", "E105", "E106", "E107", "E108"],
        "department": ["Sales", "Sales", "Sales", "Sales", "Engineering", "Engineering", "Engineering", "Engineering"],
        "revenue_thousands": [120.0, 130.0, 110.0, 140.0, 80.0, 85.0, 75.0, 90.0],
        "completion_rate": ["85%", "90%", "80%", "95%", "70%", "72%", "68%", "75%"],
        "evaluation_date": [
            "2026-01-15", "2026-01-20", "2026-02-15", "2026-02-20",
            "2026-01-18", "2026-01-22", "2026-02-18", "2026-02-22"
        ]
    })


def test_validator_valid_dataset(sample_sales_df):
    """Verifies that a valid dataset passes validation with a high quality score."""
    report = DatasetValidator.validate(sample_sales_df, dataset_name="Q1 Performance")
    assert report.is_valid is True
    assert report.total_records == 8
    assert report.total_columns == 5
    assert report.quality_score >= 90
    assert len(report.critical_errors) == 0


def test_validator_rejects_empty_dataset():
    """Verifies that an empty dataset is immediately rejected."""
    empty_df = pd.DataFrame()
    report = DatasetValidator.validate(empty_df, dataset_name="Empty CSV")
    assert report.is_valid is False
    assert report.quality_score == 0
    assert any("0 rows" in err for err in report.critical_errors)


def test_validator_detects_duplicate_columns():
    """Verifies that duplicate column headers trigger a critical error."""
    dup_df = pd.DataFrame([[1, 2]], columns=["colA", "colA"])
    report = DatasetValidator.validate(dup_df, dataset_name="Duplicate Headers")
    assert report.is_valid is False
    assert any("Duplicate column headers" in err for err in report.critical_errors)


def test_profiler_categorizes_columns(sample_sales_df):
    """Verifies that columns are categorized into identifiers, measures, dimensions, and datetimes."""
    profile = DatasetProfiler.profile(sample_sales_df, dataset_name="Sales Department")
    assert "employee_id" in profile.identifier_columns
    assert "department" in profile.categorical_dimensions
    assert "revenue_thousands" in profile.numeric_measures
    assert "completion_rate" in profile.numeric_measures
    assert "evaluation_date" in profile.timeline_columns
    assert "Commercial Sales" in profile.business_domain or "Sales" in profile.business_domain


def test_metric_engine_global_summary(sample_sales_df):
    """Verifies pure deterministic global statistical calculation."""
    summary = MetricEngine.calculate_global_summary(sample_sales_df, "revenue_thousands")
    assert summary is not None
    assert summary.count == 8
    # Mean of (120+130+110+140+80+85+75+90) / 8 = 830 / 8 = 103.75
    assert summary.mean == 103.75
    assert summary.min_value == 75.0
    assert summary.max_value == 140.0


def test_metric_engine_segment_comparison(sample_sales_df):
    """Verifies segment variance calculation against baseline."""
    segments = MetricEngine.calculate_segment_comparison(sample_sales_df, "revenue_thousands", "department")
    assert len(segments) == 2

    # Sales mean = (120+130+110+140) / 4 = 125.0
    # Engineering mean = (80+85+75+90) / 4 = 82.5
    # Overall mean = 103.75
    sales_seg = next(s for s in segments if s.segment_value == "Sales")
    eng_seg = next(s for s in segments if s.segment_value == "Engineering")

    assert sales_seg.mean == 125.0
    assert sales_seg.diff_from_baseline == round(125.0 - 103.75, 2)
    assert sales_seg.is_outperformer is True

    assert eng_seg.mean == 82.5
    assert eng_seg.diff_from_baseline == round(82.5 - 103.75, 2)
    assert eng_seg.is_underperformer is True


def test_metric_engine_candidate_facts_discovery(sample_sales_df):
    """Verifies automated discovery of deterministic candidate facts with proofs."""
    facts = MetricEngine.discover_candidate_facts(sample_sales_df, max_candidates=10)
    assert len(facts) >= 2
    for fact in facts:
        assert fact.fact_id.startswith("FACT-")
        assert fact.metric in ("revenue_thousands", "completion_rate")
        assert fact.sample_size > 0
        assert fact.raw_proof
