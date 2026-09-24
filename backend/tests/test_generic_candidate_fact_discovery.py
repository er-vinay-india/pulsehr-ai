"""Tests for Generic Candidate Fact Discovery Engine (Phase 2A).

Verifies deterministic empirical discovery of candidate facts across diverse domains:
- Sales / E-commerce
- Financial Transactions
- Manufacturing / Plant Telemetry
- Product Usage / Web Analytics
- Workforce / HR
- Intentionally Ambiguous Dataset

Verifies statistical responsibility, deliberate rejections of insufficient evidence,
preservation of UNKNOWN polarity, and domain neutrality.
"""

import pytest
import pandas as pd
import numpy as np

from app.services.data_engine.semantic_classifier import (
    SemanticClassifier,
    SemanticRole,
    MetricPolarity
)
from app.services.data_engine.opportunity_map import (
    OpportunityMapGenerator,
    OpportunityType
)
from app.services.data_engine.candidate_fact import (
    CandidateFact,
    ReliabilityStatus
)
from app.services.data_engine.candidate_fact_discovery import (
    CandidateFactDiscoveryEngine
)


# -----------------------------------------------------------------------------
# FIXTURES
# -----------------------------------------------------------------------------

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
    return pd.DataFrame({
        "col_a": [f"A{i}" for i in range(1, 11)],
        "col_b": ["X", "Y", "X", "Z", "Y", "X", "Z", "Y", "X", "Z"],
        "value1": [10.5, 12.0, 9.2, 14.1, 11.0, 8.5, 13.4, 10.2, 12.1, 9.8],
        "flag2": [0, 1, 0, 0, 1, 0, 1, 0, 0, 1]
    })


# -----------------------------------------------------------------------------
# TEST SUITE
# -----------------------------------------------------------------------------

def test_sales_candidate_fact_discovery(sales_df):
    """Test 1: Sales dataset fact discovery across multiple opportunity types."""
    profile = SemanticClassifier.profile_dataset(sales_df, "Online Sales")
    opp_map = OpportunityMapGenerator.generate(profile)

    reliable, unreliable = CandidateFactDiscoveryEngine.discover_facts(sales_df, profile, opp_map)

    assert len(reliable) > 0
    fact_types = {f.fact_type for f in reliable}
    assert OpportunityType.SEGMENT_COMPARISON.value in fact_types
    assert OpportunityType.PERIOD_TREND.value in fact_types

    # Find segment comparison fact
    seg_facts = [f for f in reliable if f.fact_type == OpportunityType.SEGMENT_COMPARISON.value]
    assert len(seg_facts) > 0
    seg = seg_facts[0]
    assert seg.sample_size > 0
    assert seg.baseline_value is not None
    assert seg.value is not None
    assert "between_group_f_stat" in seg.statistical_info
    assert "n = " in seg.statement
    # Check no AI buzzwords
    assert "terribly" not in seg.statement.lower()
    assert "amazing" not in seg.statement.lower()


def test_manufacturing_fact_discovery(manufacturing_df):
    """Test 2: Manufacturing telemetry fact discovery, including correlation and causation check."""
    profile = SemanticClassifier.profile_dataset(manufacturing_df, "Plant Telemetry")
    opp_map = OpportunityMapGenerator.generate(profile)

    reliable, unreliable = CandidateFactDiscoveryEngine.discover_facts(manufacturing_df, profile, opp_map)

    # Check measure relationship / correlation
    rel_facts = [f for f in reliable if f.fact_type == OpportunityType.MEASURE_RELATIONSHIP.value]
    assert len(rel_facts) > 0
    rel = rel_facts[0]
    assert "pearson_r" in rel.statistical_info
    assert "without implying causation" in rel.statement
    assert rel.polarity == MetricPolarity.NEUTRAL

    # Check target association
    tgt_facts = [f for f in reliable if f.fact_type == OpportunityType.TARGET_ASSOCIATION.value]
    assert len(tgt_facts) > 0
    tgt = tgt_facts[0]
    assert tgt.sample_size == 20
    assert "t_statistic" in tgt.statistical_info or "overall_target_rate_pct" in tgt.statistical_info


def test_product_analytics_percentage_point_differences(product_analytics_df):
    """Test 3: Web analytics rate differences use percentage points, not raw percentages."""
    profile = SemanticClassifier.profile_dataset(product_analytics_df, "Product Analytics")
    opp_map = OpportunityMapGenerator.generate(profile)

    reliable, unreliable = CandidateFactDiscoveryEngine.discover_facts(product_analytics_df, profile, opp_map)

    rate_facts = [f for f in reliable if f.fact_type == OpportunityType.SUBGROUP_RATE_DISPARITY.value]
    assert len(rate_facts) > 0
    rf = rate_facts[0]
    assert "percentage points" in rf.statement
    assert rf.statistical_info["difference_unit"] == "percentage_points"


def test_workforce_candidate_facts_neutrality(workforce_df):
    """Test 4: Workforce dataset facts are domain-neutral and free of hardcoded assumptions."""
    profile = SemanticClassifier.profile_dataset(workforce_df, "Workforce")
    opp_map = OpportunityMapGenerator.generate(profile)

    reliable, unreliable = CandidateFactDiscoveryEngine.discover_facts(workforce_df, profile, opp_map)
    assert len(reliable) > 0

    for fact in reliable:
        # Statements must be purely empirical
        assert "talent" not in fact.statement.lower()
        assert "burnout" not in fact.statement.lower()
        assert "retention crisis" not in fact.statement.lower()
        assert "n = " in fact.statement


def test_ambiguous_dataset_conservative_facts(ambiguous_df):
    """Test 5: Ambiguous dataset fact discovery is conservative and preserves UNKNOWN polarity."""
    profile = SemanticClassifier.profile_dataset(ambiguous_df, "Ambiguous Raw")
    opp_map = OpportunityMapGenerator.generate(profile)

    reliable, unreliable = CandidateFactDiscoveryEngine.discover_facts(ambiguous_df, profile, opp_map)

    # Check segment comparison on value1 across col_b
    seg_facts = [f for f in reliable if f.metric == "value1"]
    assert len(seg_facts) > 0
    for f in seg_facts:
        assert f.polarity == MetricPolarity.UNKNOWN
        # Fact statement must not claim improvement or deterioration
        assert "improved" not in f.statement.lower()
        assert "worsened" not in f.statement.lower()
        assert "better" not in f.statement.lower()


def test_deliberate_rejections_and_unreliable_filtering():
    """Test 6: Statistically invalid or underpowered opportunities are properly flagged/rejected."""
    # Tiny dataset with 2 rows and constant values
    tiny_df = pd.DataFrame({
        "timestamp": ["2024-01-01", "2024-01-02"],
        "category": ["A", "A"],
        "metric_const": [10.0, 10.0],
        "metric_var": [5.0, 15.0],
        "rare_target": [0, 0]  # Zero positive target cases
    })

    profile = SemanticClassifier.profile_dataset(tiny_df, "Tiny Test")
    opp_map = OpportunityMapGenerator.generate(profile)

    reliable, unreliable = CandidateFactDiscoveryEngine.discover_facts(tiny_df, profile, opp_map)

    # Check that insufficient period trend is flagged
    unreliable_reasons = [f.reliability_reason for f in unreliable if f.reliability_reason]
    assert any("Insufficient" in r or "zero" in r.lower() or "fewer" in r.lower() or "imbalance" in r.lower() or "small" in r.lower() for r in unreliable_reasons)


def test_backward_compatibility_with_legacy_candidate_fact():
    """Test 7: CandidateFact maintains 100% backward compatibility for existing AnalystAgent."""
    fact = CandidateFact(
        fact_id="FACT-099",
        fact_type="segment_gap",
        metric="turnover_rate",
        segment="Sales",
        observed_value=24.5,
        baseline_value=15.0,
        difference=9.5,
        percentage_gap=63.3,
        sample_size=30,
        significance_score=0.88,
        raw_proof={"data": "sample"}
    )

    assert fact.fact_id == "FACT-099"
    assert fact.observed_value == 24.5
    assert fact.value == 24.5
    assert fact.difference == 9.5
    assert fact.absolute_difference == 9.5
    assert fact.percentage_gap == 63.3
    assert fact.relative_difference == 63.3
    assert fact.segment == "Sales"
    assert fact.significance_score == 0.88
    assert fact.raw_proof == {"data": "sample"}
    assert fact.reliability_status == ReliabilityStatus.RELIABLE
