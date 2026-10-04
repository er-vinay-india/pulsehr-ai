"""Tests for Deterministic Business Impact Translation Engine ($ Cost, Lost Hours, Headcount Risk).

Verifies:
1. Turnover / Attrition translates to Headcount at Risk and $ Replacement Cost (1.5x salary).
2. Absence / Overtime translates to Lost Productive Hours and FTE-months capacity drag.
3. Commercial discount/scrap translates to gross margin leakage ($).
4. Discovered CandidateFacts are enriched automatically with business_impact.
5. FactInterestingnessRanker prioritizes facts with critical/high business impact.
"""

import pytest
import pandas as pd

from app.services.data_engine.candidate_fact import CandidateFact, ReliabilityStatus
from app.services.data_engine.semantic_classifier import (
    SemanticClassifier,
    SemanticDatasetProfile,
    SemanticRole,
    ColumnSemanticProfile,
)
from app.services.data_engine.opportunity_map import OpportunityMapGenerator, OpportunityType
from app.services.data_engine.candidate_fact_discovery import CandidateFactDiscoveryEngine
from app.services.data_engine.interestingness_ranker import FactInterestingnessRanker
from app.services.function_library import AnalyticalFunctionRegistry, ImpactType, ImpactSeverity


@pytest.fixture(autouse=True)
def load_catalog():
    AnalyticalFunctionRegistry.load_catalog()


def test_turnover_headcount_and_financial_translation():
    """Test 1: Turnover candidate fact translates deterministically to headcount at risk and $ replacement cost."""
    df = pd.DataFrame({
        "emp_id": [f"E{i}" for i in range(1, 101)],
        "department": ["Engineering"] * 50 + ["Sales"] * 50,
        "attrition_flag": [1 if i <= 15 else 0 for i in range(1, 101)],
        "annual_salary": [100000.0] * 100
    })
    profile = SemanticClassifier.profile_dataset(df, "Workforce Comp")

    fact = CandidateFact(
        fact_id="FACT-101",
        fact_type="segment_comparison",
        metric="attrition_flag",
        dimensions={"department": "Engineering"},
        value=0.30,  # 30% attrition in Engineering (15 out of 50)
        baseline_value=0.15,
        absolute_difference=0.15,
        relative_difference=100.0,
        sample_size=50,
        reliability_status=ReliabilityStatus.RELIABLE
    )

    impact = AnalyticalFunctionRegistry.evaluate_business_impact(fact, df, profile)
    assert impact is not None
    assert impact.impact_type == ImpactType.HEADCOUNT_AT_RISK
    # 30% of 50 = 15 employees at risk
    assert impact.impact_value == 15.0
    # $100K salary * 1.5 * 15 = $2.25M
    assert "$2,250,000" in impact.formatted_impact
    assert impact.severity == ImpactSeverity.CRITICAL
    assert "15 At Risk" in impact.formatted_impact
    assert "SHRM replacement multiplier" in impact.formula_explanation


def test_absence_lost_productive_hours_translation():
    """Test 2: Absence candidate fact translates deterministically to lost productive hours and FTE drag."""
    df = pd.DataFrame({
        "emp_id": [f"E{i}" for i in range(1, 41)],
        "department": ["Warehouse"] * 20 + ["Retail"] * 20,
        "absence_days": [10.0] * 20 + [2.0] * 20
    })
    profile = SemanticClassifier.profile_dataset(df, "Attendance")

    fact = CandidateFact(
        fact_id="FACT-102",
        fact_type="segment_comparison",
        metric="absence_days",
        dimensions={"department": "Warehouse"},
        value=10.0,
        baseline_value=6.0,
        absolute_difference=4.0,  # +4 days per person across 20 people = +80 days = 640 hours
        relative_difference=66.7,
        sample_size=20,
        reliability_status=ReliabilityStatus.RELIABLE
    )

    impact = AnalyticalFunctionRegistry.evaluate_business_impact(fact, df, profile)
    assert impact is not None
    assert impact.impact_type == ImpactType.LOST_CAPACITY_HOURS
    assert impact.impact_value == 640.0
    assert "640 Lost Hours" in impact.formatted_impact or "640 Hours" in impact.formatted_impact
    assert "FTE-mo" in impact.formatted_impact or "FTE-months" in impact.layman_takeaway
    assert impact.severity in (ImpactSeverity.CRITICAL, ImpactSeverity.HIGH)


def test_margin_leakage_translation():
    """Test 3: Commercial discount disparity translates deterministically to gross margin leakage."""
    df = pd.DataFrame({
        "order_id": [f"O{i}" for i in range(1, 31)],
        "region": ["APAC"] * 10 + ["EMEA"] * 20,
        "discount_rate": [0.25] * 10 + [0.10] * 20,
        "sales_amount": [1000.0] * 30
    })
    profile = SemanticClassifier.profile_dataset(df, "Sales Orders")

    fact = CandidateFact(
        fact_id="FACT-103",
        fact_type="segment_comparison",
        metric="discount_rate",
        dimensions={"region": "APAC"},
        value=0.25,
        baseline_value=0.15,
        absolute_difference=0.10,
        relative_difference=66.7,
        sample_size=10,
        reliability_status=ReliabilityStatus.RELIABLE
    )

    impact = AnalyticalFunctionRegistry.evaluate_business_impact(fact, df, profile)
    assert impact is not None
    assert impact.impact_type == ImpactType.MARGIN_LEAKAGE
    assert impact.unit == "$"
    assert "Margin Leakage" in impact.formatted_impact
    assert impact.impact_value > 0


def test_candidate_fact_discovery_auto_enrichment():
    """Test 4: CandidateFactDiscoveryEngine automatically enriches reliable facts with business_impact."""
    workforce_df = pd.DataFrame({
        "employee_id": [f"EMP-{i:03d}" for i in range(1, 31)],
        "department": ["Sales"] * 15 + ["Engineering"] * 15,
        "shift": (["Day"] * 5 + ["Night"] * 10) * 2,
        "absence_days": [1.0] * 10 + [8.0] * 10 + [2.0] * 10,
        "attrition_flag": [0] * 22 + [1] * 8
    })
    profile = SemanticClassifier.profile_dataset(workforce_df, "Workforce Auto Enrich")
    opp_map = OpportunityMapGenerator.generate(profile)

    reliable, _ = CandidateFactDiscoveryEngine.discover_facts(workforce_df, profile, opp_map)
    assert len(reliable) > 0

    # At least some reliable facts must have business_impact attached
    impact_enriched = [f for f in reliable if f.business_impact is not None]
    assert len(impact_enriched) > 0

    first_impact = impact_enriched[0].business_impact
    assert first_impact.formatted_impact != ""
    assert first_impact.layman_takeaway != ""
    assert first_impact.formula_explanation != ""


def test_interestingness_ranker_business_impact_boost():
    """Test 5: FactInterestingnessRanker boosts facts with critical/high business impact."""
    fact_normal = CandidateFact(
        fact_id="FACT-NORM",
        fact_type="segment_comparison",
        metric="tenure_years",
        value=4.2,
        baseline_value=4.0,
        absolute_difference=0.2,
        relative_difference=5.0,
        sample_size=20,
        reliability_status=ReliabilityStatus.RELIABLE
    )

    fact_critical = CandidateFact(
        fact_id="FACT-CRIT",
        fact_type="segment_comparison",
        metric="attrition_flag",
        value=0.40,
        baseline_value=0.10,
        absolute_difference=0.30,
        relative_difference=300.0,
        sample_size=20,
        reliability_status=ReliabilityStatus.RELIABLE,
        business_impact=AnalyticalFunctionRegistry.get_function("fn_turnover_exposure").metadata.impact_rule.default_severity
    )
    # Give it a real BusinessImpactAssessment
    from app.services.function_library.base import BusinessImpactAssessment
    fact_critical.business_impact = BusinessImpactAssessment(
        impact_type=ImpactType.HEADCOUNT_AT_RISK,
        impact_metric="Turnover Headcount & Financial Exposure",
        impact_value=8.0,
        formatted_impact="8 At Risk (~$900,000 Exposure)",
        unit="$",
        severity=ImpactSeverity.CRITICAL,
        formula_explanation="8 employees × $75K × 1.5",
        layman_takeaway="8 employees at risk of leaving"
    )

    ranked = FactInterestingnessRanker.rank_interesting_facts([fact_normal, fact_critical], limit=2)
    # The critical business impact fact should be ranked first
    assert ranked[0].fact_id == "FACT-CRIT"
