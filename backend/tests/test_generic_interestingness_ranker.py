"""Tests for Fact Interestingness and 'Surprise Me' Ranker (Phase 2B).

Verifies:
1. Multi-signal scoring across diverse domains (Sales, Finance, Manufacturing, Product Analytics, Workforce, Ambiguous).
2. Separation of statistically valid facts from interesting facts (boring facts pushed down).
3. Independence from raw number magnitude.
4. Neutral analytical insight categories.
5. Diversity controls preventing monotonous rankings.
6. Deterministic execution and reproducibility.
"""

import pytest
import pandas as pd
import numpy as np

from app.services.data_engine.semantic_classifier import SemanticClassifier, MetricPolarity
from app.services.data_engine.opportunity_map import OpportunityMapGenerator, OpportunityType
from app.services.data_engine.candidate_fact import CandidateFact, ReliabilityStatus
from app.services.data_engine.candidate_fact_discovery import CandidateFactDiscoveryEngine
from app.services.data_engine.interestingness_ranker import (
    FactInterestingnessRanker,
    RankedFact,
    InsightCategory
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
def ambiguous_df():
    return pd.DataFrame({
        "col_a": [f"A{i}" for i in range(1, 11)],
        "col_b": ["X", "Y", "X", "Z", "Y", "X", "Z", "Y", "X", "Z"],
        "value1": [10.5, 12.0, 9.2, 14.1, 11.0, 8.5, 13.4, 10.2, 12.1, 9.8],
        "flag2": [0, 1, 0, 0, 1, 0, 1, 0, 0, 1]
    })


# -----------------------------------------------------------------------------
# TEST CASES
# -----------------------------------------------------------------------------

def test_interestingness_ranking_structure_and_types(sales_df):
    """Test 1: Ranker returns structured RankedFact objects with scoring components and reasons."""
    profile = SemanticClassifier.profile_dataset(sales_df, "Sales")
    opp_map = OpportunityMapGenerator.generate(profile)
    reliable, _ = CandidateFactDiscoveryEngine.discover_facts(sales_df, profile, opp_map)

    ranked = FactInterestingnessRanker.rank_interesting_facts(reliable, limit=5)
    assert len(ranked) == 5

    for idx, r in enumerate(ranked, start=1):
        assert r.rank == idx
        assert 0.0 <= r.interestingness_score <= 1.0
        assert 0.0 <= r.diversity_adjusted_score <= 1.0
        assert isinstance(r.insight_category, InsightCategory)
        assert len(r.scoring_components) > 0
        assert len(r.ranking_reason) > 10
        assert r.fact.reliability_status == ReliabilityStatus.RELIABLE


def test_separation_of_valid_vs_boring_facts(sales_df):
    """Test 2: Facts with minimal deviation or effect size are categorized as STABLE/boring and ranked low."""
    boring_fact = CandidateFact(
        fact_id="FACT-BORING",
        fact_type=OpportunityType.SEGMENT_COMPARISON.value,
        metric="sales_amount",
        dimensions={"product_category": "Electronics"},
        value=665.15,
        baseline_value=660.28,
        absolute_difference=4.88,
        relative_difference=0.7,
        sample_size=10,
        statistical_info={
            "between_group_f_stat": 0.01,
            "baseline_mean": 660.28,
            "baseline_std": 200.0,
            "group_std": 190.0,
            "total_segments": 3
        },
        source_columns=["product_category", "sales_amount"],
        polarity=MetricPolarity.HIGHER_IS_BETTER,
        statement="Segment 'Electronics' in product_category has mean sales_amount = $665.15; overall baseline = $660.28; difference = +$4.88 (+0.7% relative); n = 10.",
        reliability_status=ReliabilityStatus.RELIABLE
    )

    exciting_fact = CandidateFact(
        fact_id="FACT-EXCITING",
        fact_type=OpportunityType.ENTITY_CONCENTRATION.value,
        metric="sales_amount",
        dimensions={"entity_column": "customer_id", "concentration_tier": "top_20_percent"},
        value=68.5,
        baseline_value=20.0,
        absolute_difference=48.5,
        relative_difference=242.5,
        sample_size=20,
        statistical_info={
            "gini_coefficient": 0.58,
            "top_20_entity_count": 4,
            "top_1_entity_share_pct": 32.0,
            "total_volume": 150000.0
        },
        source_columns=["customer_id", "sales_amount"],
        polarity=MetricPolarity.HIGHER_IS_BETTER,
        statement="Top 20% of customer_id entities account for 68.5% of total sales_amount (Gini = 0.58).",
        reliability_status=ReliabilityStatus.RELIABLE
    )

    ranked = FactInterestingnessRanker.rank_interesting_facts([boring_fact, exciting_fact], limit=2)
    assert ranked[0].fact_id == "FACT-EXCITING"
    assert ranked[0].insight_category == InsightCategory.CONCENTRATION
    assert ranked[0].interestingness_score > 0.60

    assert ranked[1].fact_id == "FACT-BORING"
    assert ranked[1].insight_category == InsightCategory.STABLE_OR_NO_DIFFERENCE
    assert ranked[1].interestingness_score < 0.20


def test_no_raw_number_bias():
    """Test 3: Huge raw numbers with 0 deviation score lower than modest numbers with huge deviation."""
    huge_flat = CandidateFact(
        fact_id="FACT-HUGE-FLAT",
        fact_type=OpportunityType.SEGMENT_COMPARISON.value,
        metric="huge_budget",
        dimensions={"dept": "Finance"},
        value=10000100.0,
        baseline_value=10000000.0,
        absolute_difference=100.0,
        relative_difference=0.001,
        sample_size=50,
        statistical_info={"between_group_f_stat": 0.001, "baseline_std": 500000.0},
        statement="Huge budget is $10M vs $10M (+0.0% diff)",
        reliability_status=ReliabilityStatus.RELIABLE
    )

    small_jump = CandidateFact(
        fact_id="FACT-SMALL-JUMP",
        fact_type=OpportunityType.SEGMENT_COMPARISON.value,
        metric="error_rate",
        dimensions={"dept": "Logistics"},
        value=8.5,
        baseline_value=2.0,
        absolute_difference=6.5,
        relative_difference=325.0,
        sample_size=30,
        statistical_info={"between_group_f_stat": 18.5, "baseline_std": 1.5},
        statement="Error rate is 8.5% vs 2.0% (+325.0% diff)",
        reliability_status=ReliabilityStatus.RELIABLE
    )

    ranked = FactInterestingnessRanker.rank_interesting_facts([huge_flat, small_jump], limit=2)
    assert ranked[0].fact_id == "FACT-SMALL-JUMP"
    assert ranked[0].interestingness_score > ranked[1].interestingness_score


def test_diversity_controls_prevent_metric_monotony(product_analytics_df):
    """Test 4: Diversity controls down-weight repetitive facts on the same metric/dimension."""
    profile = SemanticClassifier.profile_dataset(product_analytics_df, "Web Analytics")
    opp_map = OpportunityMapGenerator.generate(profile)
    reliable, _ = CandidateFactDiscoveryEngine.discover_facts(product_analytics_df, profile, opp_map)

    # Rank top 5 facts
    ranked = FactInterestingnessRanker.rank_interesting_facts(reliable, limit=5, diversity_lambda=0.60)
    top_metrics = [r.fact.metric for r in ranked]
    top_types = [r.fact.fact_type for r in ranked]

    # Must contain multiple distinct metrics and multiple distinct fact types
    assert len(set(top_metrics)) >= 2
    assert len(set(top_types)) >= 2


def test_neutral_categories_no_unsupported_business_judgment(ambiguous_df):
    """Test 5: Ambiguous dataset facts maintain strictly neutral analytical categories."""
    profile = SemanticClassifier.profile_dataset(ambiguous_df, "Ambiguous")
    opp_map = OpportunityMapGenerator.generate(profile)
    reliable, _ = CandidateFactDiscoveryEngine.discover_facts(ambiguous_df, profile, opp_map)

    ranked = FactInterestingnessRanker.rank_interesting_facts(reliable, limit=5)
    for r in ranked:
        # Category must be one of the defined neutral categories
        assert isinstance(r.insight_category, InsightCategory)
        # Reason must not invent business sentiment
        assert "good" not in r.ranking_reason.lower()
        assert "bad" not in r.ranking_reason.lower()
        assert "failure" not in r.ranking_reason.lower()
        assert "success" not in r.ranking_reason.lower()


def test_deterministic_reproducibility(manufacturing_df):
    """Test 6: Repeated runs yield identical scores, rankings, and reasons."""
    profile = SemanticClassifier.profile_dataset(manufacturing_df, "Manufacturing")
    opp_map = OpportunityMapGenerator.generate(profile)
    reliable, _ = CandidateFactDiscoveryEngine.discover_facts(manufacturing_df, profile, opp_map)

    run_1 = FactInterestingnessRanker.rank_interesting_facts(reliable, limit=5)
    run_2 = FactInterestingnessRanker.rank_interesting_facts(reliable, limit=5)

    assert len(run_1) == len(run_2)
    for r1, r2 in zip(run_1, run_2):
        assert r1.fact_id == r2.fact_id
        assert r1.interestingness_score == r2.interestingness_score
        assert r1.diversity_adjusted_score == r2.diversity_adjusted_score
        assert r1.ranking_reason == r2.ranking_reason
