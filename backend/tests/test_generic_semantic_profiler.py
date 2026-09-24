"""Comprehensive tests for Generic Semantic Dataset Profiler and AnalysisOpportunityMap.

Tests:
1. Sales / E-commerce dataset
2. Finance dataset
3. Manufacturing dataset
4. Web / Product Analytics dataset
5. Workforce dataset
6. Intentionally Ambiguous dataset with poor column names (col_a, col_b, value1, flag2)
"""

import json
import pytest
import pandas as pd

from app.services.data_engine.semantic_classifier import (
    SemanticClassifier,
    SemanticRole,
    MetricPolarity,
    ColumnSemanticProfile,
    SemanticDatasetProfile
)
from app.services.data_engine.opportunity_map import (
    OpportunityMapGenerator,
    OpportunityType,
    AnalysisOpportunityMap
)
from app.services.data_engine.profiler import DatasetProfiler, DatasetProfile


@pytest.fixture
def sales_df():
    return pd.DataFrame({
        "order_id": [f"ORD-{i:04d}" for i in range(1, 21)],
        "order_date": [f"2024-01-{(i % 25) + 1:02d}" for i in range(1, 21)],
        "customer_id": [f"CUST-{((i % 7) + 1):03d}" for i in range(1, 21)],
        "product_category": ["Electronics", "Furniture", "Office Supplies", "Electronics"] * 5,
        "region": ["North America", "EMEA", "APAC", "LATAM"] * 5,
        "sales_amount": [f"${(i * 125.50):,.2f}" for i in range(1, 21)],
        "discount_rate": [f"{(i % 5) * 5.0}%" for i in range(1, 21)],
        "profit": [f"${((i * 45.0) - 100):,.2f}" for i in range(1, 21)],
        "is_returned": [1 if i % 6 == 0 else 0 for i in range(1, 21)]
    })


@pytest.fixture
def finance_df():
    return pd.DataFrame({
        "account_code": [f"ACC-{i:03d}" for i in range(1, 21)],
        "fiscal_period": ["2024-Q1", "2024-Q2", "2024-Q3", "2024-Q4"] * 5,
        "cost_center": ["CC-East", "CC-West", "CC-Central", "CC-South"] * 5,
        "department": ["Engineering", "Marketing", "Sales", "Operations"] * 5,
        "budget_usd": [100000.0 + (i * 5000.0) for i in range(1, 21)],
        "actual_usd": [95000.0 + (i * 5500.0) for i in range(1, 21)],
        "variance_pct": [round(((5500 - 5000) / 100000) * 100, 2) for i in range(1, 21)],
        "is_capex": [True if i % 2 == 0 else False for i in range(1, 21)]
    })


@pytest.fixture
def manufacturing_df():
    return pd.DataFrame({
        "batch_id": [f"BATCH-{i:03d}" for i in range(1, 21)],
        "timestamp": [f"2024-06-01 08:{i:02d}:00" for i in range(1, 21)],
        "machine_id": [f"M-{((i % 4) + 1):02d}" for i in range(1, 21)],
        "operator_shift": ["Day", "Night", "Day", "Night"] * 5,
        "cycle_time_sec": [42.5 + (i * 0.8) for i in range(1, 21)],
        "defect_count": [0, 1, 0, 3, 0, 2, 0, 0, 1, 4] * 2,
        "scrap_rate_pct": [0.0, 1.2, 0.0, 3.5, 0.0, 2.1, 0.0, 0.0, 1.1, 4.2] * 2,
        "passed_qa": [False if i in (4, 10, 14, 20) else True for i in range(1, 21)]
    })


@pytest.fixture
def product_analytics_df():
    return pd.DataFrame({
        "session_id": [f"SESS-{i:05d}" for i in range(1, 21)],
        "event_time": [f"2024-03-10 14:{i:02d}:15" for i in range(1, 21)],
        "user_id": [f"U-{((i % 8) + 1):03d}" for i in range(1, 21)],
        "device_category": ["Mobile", "Desktop", "Mobile", "Tablet"] * 5,
        "page_path": ["/pricing", "/checkout", "/home", "/features"] * 5,
        "duration_seconds": [35.0 + (i * 12.5) for i in range(1, 21)],
        "bounce_flag": [1 if i % 3 == 0 else 0 for i in range(1, 21)],
        "conversion_rate": [0.02 + ((i % 5) * 0.01) for i in range(1, 21)],
        "country": ["US", "DE", "FR", "UK", "JP"] * 4
    })


@pytest.fixture
def workforce_df():
    return pd.DataFrame({
        "employee_id": [f"EMP-{i:03d}" for i in range(1, 21)],
        "hire_date": [f"2021-{(i % 12) + 1:02d}-01" for i in range(1, 21)],
        "department": ["Engineering", "Sales", "Support", "Product"] * 5,
        "job_role": ["Lead", "Associate", "Manager", "Analyst"] * 5,
        "tenure_months": [12 + (i * 3) for i in range(1, 21)],
        "salary_usd": [f"${75000 + (i * 2500):,}" for i in range(1, 21)],
        "satisfaction_score": [3, 4, 5, 2, 4, 3, 5, 4, 3, 2] * 2,
        "absenteeism_rate": [1.2, 3.4, 0.8, 5.2, 2.1, 1.9, 0.5, 4.8, 2.2, 6.1] * 2,
        "attrition_flag": [True if i in (4, 10, 18) else False for i in range(1, 21)]
    })


@pytest.fixture
def ambiguous_df():
    """Intentionally ambiguous dataset with non-descriptive names and opaque values."""
    return pd.DataFrame({
        "col_a": [f"A{i}" for i in range(1, 11)],
        "col_b": ["X", "Y", "X", "Z", "Y", "X", "Z", "Y", "X", "Z"],
        "value1": [10.5, 12.0, 9.2, 14.1, 11.0, 8.5, 13.4, 10.2, 12.1, 9.8],
        "flag2": [0, 1, 0, 0, 1, 0, 1, 0, 0, 1]
    })


# -----------------------------------------------------------------------------
# TEST CASES
# -----------------------------------------------------------------------------

def test_sales_ecommerce_profiling(sales_df):
    """Test Case 1: Sales / E-commerce dataset classification and opportunity mapping."""
    prof = SemanticClassifier.profile_dataset(sales_df, "Online Sales")
    opp_map = OpportunityMapGenerator.generate(prof)

    # 1. Grain
    assert "transaction" in prof.inferred_grain or "order" in prof.inferred_grain
    assert prof.grain_confidence >= 0.85
    assert "order_id" in prof.grain_key_columns

    # 2. Roles
    assert prof.columns["order_id"].semantic_role == SemanticRole.IDENTIFIER
    assert prof.columns["order_date"].semantic_role == SemanticRole.DATETIME
    assert prof.columns["product_category"].semantic_role == SemanticRole.CATEGORICAL_DIMENSION
    assert prof.columns["region"].semantic_role in (SemanticRole.GEOGRAPHIC, SemanticRole.CATEGORICAL_DIMENSION)
    assert prof.columns["sales_amount"].semantic_role == SemanticRole.CURRENCY_MONETARY
    assert prof.columns["discount_rate"].semantic_role == SemanticRole.PERCENTAGE_RATE
    assert prof.columns["profit"].semantic_role == SemanticRole.CURRENCY_MONETARY
    assert prof.columns["is_returned"].semantic_role in (SemanticRole.BOOLEAN, SemanticRole.POSSIBLE_TARGET)

    # 3. Units & Polarity
    assert prof.columns["sales_amount"].unit == "$"
    assert prof.columns["discount_rate"].unit == "%"
    assert prof.columns["profit"].metric_polarity == MetricPolarity.HIGHER_IS_BETTER
    assert prof.columns["profit"].polarity_confidence >= 0.80

    # 4. Opportunities
    types = [o.opportunity_type for o in opp_map.opportunities]
    assert OpportunityType.PERIOD_TREND in types
    assert OpportunityType.SEGMENT_COMPARISON in types
    assert OpportunityType.MEASURE_RELATIONSHIP in types


def test_finance_profiling(finance_df):
    """Test Case 2: Finance dataset profiling."""
    prof = SemanticClassifier.profile_dataset(finance_df, "General Ledger")
    opp_map = OpportunityMapGenerator.generate(prof)

    assert prof.columns["account_code"].semantic_role == SemanticRole.IDENTIFIER
    assert prof.columns["cost_center"].semantic_role == SemanticRole.CATEGORICAL_DIMENSION
    assert prof.columns["budget_usd"].semantic_role == SemanticRole.CURRENCY_MONETARY
    assert prof.columns["actual_usd"].semantic_role == SemanticRole.CURRENCY_MONETARY
    assert prof.columns["variance_pct"].semantic_role == SemanticRole.PERCENTAGE_RATE
    assert prof.columns["is_capex"].semantic_role == SemanticRole.BOOLEAN

    # Opportunities
    types = [o.opportunity_type for o in opp_map.opportunities]
    assert OpportunityType.SEGMENT_COMPARISON in types
    assert OpportunityType.MEASURE_RELATIONSHIP in types


def test_manufacturing_profiling(manufacturing_df):
    """Test Case 3: Manufacturing dataset profiling."""
    prof = SemanticClassifier.profile_dataset(manufacturing_df, "Plant Telemetry")
    opp_map = OpportunityMapGenerator.generate(prof)

    assert "batch" in prof.inferred_grain
    assert prof.columns["timestamp"].semantic_role == SemanticRole.DATETIME
    assert prof.columns["cycle_time_sec"].unit == "seconds"
    assert prof.columns["defect_count"].semantic_role == SemanticRole.NUMERIC_MEASURE
    assert prof.columns["defect_count"].metric_polarity == MetricPolarity.LOWER_IS_BETTER
    assert prof.columns["scrap_rate_pct"].semantic_role == SemanticRole.PERCENTAGE_RATE
    assert prof.columns["scrap_rate_pct"].metric_polarity == MetricPolarity.LOWER_IS_BETTER
    assert prof.columns["passed_qa"].semantic_role in (SemanticRole.BOOLEAN, SemanticRole.POSSIBLE_TARGET)

    types = [o.opportunity_type for o in opp_map.opportunities]
    assert OpportunityType.PERIOD_TREND in types
    assert OpportunityType.SEGMENT_COMPARISON in types


def test_product_web_analytics_profiling(product_analytics_df):
    """Test Case 4: Web / Product analytics dataset profiling."""
    prof = SemanticClassifier.profile_dataset(product_analytics_df, "Web Analytics")
    opp_map = OpportunityMapGenerator.generate(prof)

    assert "session" in prof.inferred_grain
    assert prof.columns["event_time"].semantic_role == SemanticRole.DATETIME
    assert prof.columns["country"].semantic_role in (SemanticRole.GEOGRAPHIC, SemanticRole.CATEGORICAL_DIMENSION)
    assert prof.columns["duration_seconds"].unit == "seconds"
    assert prof.columns["bounce_flag"].semantic_role in (SemanticRole.BOOLEAN, SemanticRole.POSSIBLE_TARGET)
    assert prof.columns["conversion_rate"].semantic_role == SemanticRole.PERCENTAGE_RATE


def test_workforce_profiling(workforce_df):
    """Test Case 5: Workforce dataset profiling without hardcoded HR logic."""
    prof = SemanticClassifier.profile_dataset(workforce_df, "Workforce Log")
    opp_map = OpportunityMapGenerator.generate(prof)

    assert "employee" in prof.inferred_grain
    assert prof.columns["employee_id"].semantic_role == SemanticRole.IDENTIFIER
    assert prof.columns["hire_date"].semantic_role == SemanticRole.DATETIME
    assert prof.columns["department"].semantic_role == SemanticRole.CATEGORICAL_DIMENSION
    assert prof.columns["salary_usd"].semantic_role == SemanticRole.CURRENCY_MONETARY
    assert prof.columns["satisfaction_score"].semantic_role == SemanticRole.ORDINAL
    assert prof.columns["absenteeism_rate"].semantic_role == SemanticRole.PERCENTAGE_RATE
    assert prof.columns["absenteeism_rate"].metric_polarity == MetricPolarity.LOWER_IS_BETTER


def test_ambiguous_dataset_conservative_behavior(ambiguous_df):
    """Test Case 6: Intentionally ambiguous dataset with non-descriptive names.
    System must expose LOW CONFIDENCE / UNKNOWN rather than inventing business meaning.
    """
    prof = SemanticClassifier.profile_dataset(ambiguous_df, "Ambiguous Raw")
    opp_map = OpportunityMapGenerator.generate(prof)

    # 1. Grain must be conservative / low confidence
    assert prof.grain_confidence <= 0.85

    # 2. Ambiguous numeric value1
    val1 = prof.columns["value1"]
    assert val1.semantic_role == SemanticRole.NUMERIC_MEASURE
    assert val1.metric_polarity == MetricPolarity.UNKNOWN
    assert val1.polarity_confidence <= 0.50
    assert "Insufficient domain evidence" in val1.polarity_reason

    # 3. Ambiguous boolean flag2
    flag2 = prof.columns["flag2"]
    assert flag2.semantic_role == SemanticRole.BOOLEAN
    assert flag2.metric_polarity == MetricPolarity.NEUTRAL

    # 4. Ambiguous categorical col_b
    col_b = prof.columns["col_b"]
    assert col_b.semantic_role == SemanticRole.CATEGORICAL_DIMENSION
    assert col_b.confidence <= 0.60
    assert any("Ambiguous non-descriptive header" in r for r in col_b.detection_reasons)

    # 5. Opportunity map still functions purely on mathematical admissibility
    assert opp_map.total_opportunities >= 1
    # Segment comparison (col_b x value1) is mathematically possible even if semantics are opaque!
    assert any(o.opportunity_type == OpportunityType.SEGMENT_COMPARISON for o in opp_map.opportunities)


def test_dataset_profiler_integration(sales_df):
    """Verifies that DatasetProfiler.profile returns DatasetProfile with backward compatibility."""
    profile = DatasetProfiler.profile(sales_df, "Online Sales")
    assert isinstance(profile, DatasetProfile)
    assert profile.semantic_profile is not None
    assert profile.opportunity_map is not None
    assert len(profile.numeric_measures) >= 2
    assert len(profile.categorical_dimensions) >= 1
    assert "order_date" in profile.timeline_columns
    assert "order_id" in profile.identifier_columns
