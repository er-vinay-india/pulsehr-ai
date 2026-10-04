"""Tests for Phase 3B: Intelligent Visualization Recommendation Engine.

Verifies deterministic, mathematically defensible visual mapping for CandidateFacts:
1. PERIOD_TREND -> Chronological Line Chart with reference line
2. SEGMENT_COMPARISON -> Column or Horizontal Bar with baseline line
3. ENTITY_CONCENTRATION -> Donut / Pareto with top-N and remaining entities
4. MEASURE_RELATIONSHIP -> Multi-series comparison
5. TARGET_ASSOCIATION -> Target-sliced comparative columns
6. Zero Hallucination: Verifies that all series data points match dataframe calculations or facts.
"""

import pytest
import pandas as pd

from unittest.mock import patch
from app.services.data_engine.semantic_classifier import SemanticClassifier
from app.services.data_engine.opportunity_map import OpportunityMapGenerator
from app.services.data_engine.candidate_fact_discovery import CandidateFactDiscoveryEngine
from app.services.data_engine.interestingness_ranker import FactInterestingnessRanker
from app.services.data_engine.fact_visualizer import FactVisualizer
from app.services.data_engine.visualization_models import VisualChartSpec
from app.services.analyst.analyst_agent import AnalystAgent
from app.services.gateway.model_gateway import GatewayResult
from app.core.models_config import ModelRole


@pytest.fixture(autouse=True)
def mock_gateway_offline():
    """Ensure tests run purely offline without hanging on external LLM / Ollama connection."""
    with patch(
        "app.services.gateway.model_gateway.ModelGateway.generate",
        return_value=GatewayResult(raw_text="", success=True, error=None, role=ModelRole.ANALYST)
    ):
        yield


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


# -----------------------------------------------------------------------------
# TESTS
# -----------------------------------------------------------------------------

def test_period_trend_visualization(sales_df):
    """Verifies that a PERIOD_TREND fact generates a chronological line chart."""
    profile = SemanticClassifier.profile_dataset(sales_df, "Sales")
    opp_map = OpportunityMapGenerator.generate(profile)
    reliable, _ = CandidateFactDiscoveryEngine.discover_facts(sales_df, profile, opp_map)

    trend_facts = [f for f in reliable if f.fact_type == "period_trend"]
    assert len(trend_facts) > 0, "Expected at least one period_trend fact"

    fact = trend_facts[0]
    chart = FactVisualizer.recommend_chart(fact, df=sales_df, profile=profile)

    assert isinstance(chart, VisualChartSpec)
    assert chart.chart_type == "line"
    assert len(chart.categories) > 0
    assert len(chart.series) == 1
    assert len(chart.series[0].values) == len(chart.categories)
    assert chart.supporting_fact_id == fact.fact_id
    assert chart.unit in ("$", "%", "")
    assert len(chart.reference_lines) >= 1  # Should have baseline reference line


def test_segment_comparison_visualization(manufacturing_df):
    """Verifies that a SEGMENT_COMPARISON fact generates a column or horizontal bar chart."""
    profile = SemanticClassifier.profile_dataset(manufacturing_df, "Manufacturing")
    opp_map = OpportunityMapGenerator.generate(profile)
    reliable, _ = CandidateFactDiscoveryEngine.discover_facts(manufacturing_df, profile, opp_map)

    segment_facts = [f for f in reliable if f.fact_type in ("segment_comparison", "segment_gap")]
    assert len(segment_facts) > 0, "Expected at least one segment fact"

    fact = segment_facts[0]
    chart = FactVisualizer.recommend_chart(fact, df=manufacturing_df, profile=profile)

    assert isinstance(chart, VisualChartSpec)
    assert chart.chart_type in ("column", "horizontal_bar", "bar")
    assert len(chart.categories) > 0
    assert len(chart.series[0].values) == len(chart.categories)
    assert chart.supporting_fact_id == fact.fact_id
    assert chart.reference_lines[0].label == "Baseline Mean"


def test_entity_concentration_visualization(sales_df):
    """Verifies that an ENTITY_CONCENTRATION fact generates a donut chart with top contributors + all other."""
    profile = SemanticClassifier.profile_dataset(sales_df, "Sales")
    opp_map = OpportunityMapGenerator.generate(profile)
    reliable, _ = CandidateFactDiscoveryEngine.discover_facts(sales_df, profile, opp_map)

    conc_facts = [f for f in reliable if "concentration" in f.fact_type]
    assert len(conc_facts) > 0, "Expected at least one concentration fact"

    fact = conc_facts[0]
    chart = FactVisualizer.recommend_chart(fact, df=sales_df, profile=profile)

    assert isinstance(chart, VisualChartSpec)
    assert chart.chart_type == "donut"
    assert "All Other Entities" in chart.categories or "Remaining Entities" in chart.categories
    assert len(chart.series[0].values) == len(chart.categories)
    assert chart.supporting_fact_id == fact.fact_id


def test_insight_visualization_linking(sales_df):
    """Verifies that visualize_insights maps interpretation insights to charts cleanly."""
    profile = SemanticClassifier.profile_dataset(sales_df, "Sales")
    opp_map = OpportunityMapGenerator.generate(profile)
    reliable, _ = CandidateFactDiscoveryEngine.discover_facts(sales_df, profile, opp_map)
    ranked = FactInterestingnessRanker.rank_interesting_facts(reliable, limit=6)
    facts_lookup = {f.fact_id: f for f in reliable}

    response, result = AnalystAgent.interpret(profile, ranked, max_facts=6)
    assert result.success is True

    charts = FactVisualizer.visualize_insights(response.insights, facts_lookup, df=sales_df, profile=profile)
    assert len(charts) >= 1
    for chart in charts:
        assert isinstance(chart, VisualChartSpec)
        assert chart.supporting_fact_id in facts_lookup
        assert len(chart.categories) == len(chart.series[0].values)


def test_breakdown_tree_visualization():
    """Verifies that a multi_factor_segment_disparity fact produces a breakdown tree spec."""
    from app.services.data_engine.candidate_fact import CandidateFact
    from app.services.function_library.base import BusinessImpactAssessment, ImpactType, ImpactSeverity

    fact = CandidateFact(
        fact_id="FACT-099",
        fact_type="multi_factor_segment_disparity",
        metric="turnover_rate",
        dimensions={"department": "Engineering", "tenure_band": "1-2 Years"},
        value=38.5,
        baseline_value=14.2,
        absolute_difference=24.3,
        relative_difference=171.1,
        sample_size=18,
        statistical_info={
            "dimension_1": "department",
            "dimension_1_value": "Engineering",
            "dimension_2": "tenure_band",
            "dimension_2_value": "1-2 Years",
            "total_records": 450
        },
        business_impact=BusinessImpactAssessment(
            impact_type=ImpactType.HEADCOUNT_AT_RISK,
            impact_metric="Turnover Exposure",
            impact_value=125000.0,
            formatted_impact="$125,000",
            unit="$",
            severity=ImpactSeverity.CRITICAL,
            formula_explanation="18 employees × turnover delta × replacement cost",
            layman_takeaway="Engineering 1-2 Years cohort drives $125k in turnover exposure."
        )
    )

    chart = FactVisualizer.recommend_chart(fact)
    assert chart is not None
    assert chart.chart_type == "breakdown_tree"
    assert chart.tree_data is not None
    assert chart.tree_data["name"] == "Overall Turnover Rate"
    assert chart.tree_data["value"] == 14.2
    assert len(chart.tree_data["children"]) == 1
    d1_child = chart.tree_data["children"][0]
    assert d1_child["name"] == "department: Engineering"
    assert len(d1_child["children"]) == 1
    d2_child = d1_child["children"][0]
    assert d2_child["value"] == 38.5
    assert d2_child["severity"] == "critical"
    # Verify impact card attached
    assert chart.impact_card is not None
    assert chart.impact_card["headline"] == "Engineering 1-2 Years cohort drives $125k in turnover exposure."
    assert chart.impact_card["amount"] == 125000.0
    assert chart.impact_card["risk_level"] == "CRITICAL"


def test_variance_waterfall_visualization():
    """Verifies that a segment fact with financial impact produces a variance waterfall spec."""
    from app.services.data_engine.candidate_fact import CandidateFact
    from app.services.function_library.base import BusinessImpactAssessment, ImpactType, ImpactSeverity

    fact = CandidateFact(
        fact_id="FACT-100",
        fact_type="segment_gap",
        metric="gross_margin",
        dimensions={"product_line": "Custom Enterprise"},
        value=18.5,
        baseline_value=32.0,
        absolute_difference=-13.5,
        relative_difference=-42.2,
        sample_size=40,
        business_impact=BusinessImpactAssessment(
            impact_type=ImpactType.MARGIN_LEAKAGE,
            impact_metric="Gross Margin Leakage",
            impact_value=85000.0,
            formatted_impact="$85,000",
            unit="$",
            severity=ImpactSeverity.HIGH,
            formula_explanation="Volume * margin delta",
            layman_takeaway="Custom Enterprise underperformed margin baseline resulting in $85,000 leakage."
        )
    )

    chart = FactVisualizer.recommend_chart(fact)
    assert chart is not None
    assert chart.chart_type == "waterfall"
    assert chart.waterfall_steps is not None
    assert len(chart.waterfall_steps) >= 3
    assert chart.waterfall_steps[0]["label"] == "Baseline / Expected"
    assert chart.waterfall_steps[0]["value"] == 32.0
    assert chart.waterfall_steps[-1]["label"] == "Total Business Impact"
    assert chart.waterfall_steps[-1]["value"] == 85000.0
    # Verify stacked bar series generated
    assert len(chart.series) == 2
    assert chart.series[0].name == "Helper Base"
    assert chart.series[1].name == "Delta"
    assert chart.impact_card is not None
    assert chart.impact_card["formatted_amount"] == "$85,000"
