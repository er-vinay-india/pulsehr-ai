"""Benchmark evaluation corpus for HRIDAY AI Observability (Phase D).

Defines 50+ benchmark evaluation cases across 16 analytical categories and multiple domains:
- simple lookup
- ranking
- comparison
- trend
- distribution
- relationship
- outlier
- why/root-cause
- scenario
- presentation
- ambiguous request
- unsupported request
- cross-dataset request
- causal overclaim
- insufficient evidence
- approval-required
"""
from __future__ import annotations

from typing import Any
from pydantic import BaseModel, ConfigDict, Field


class BenchmarkTestCase(BaseModel):
    """Specification of an expected benchmark evaluation inquiry."""
    model_config = ConfigDict(extra="ignore")

    case_id: str
    prompt: str
    category: str
    domain: str = "workforce"
    dataset_id: int | str = 99767
    caller: str = "hriday"

    expected_intent: str
    expected_workflow: str
    expected_tools: list[str] = Field(default_factory=list)
    max_model_calls: int = 1
    allows_scenario: bool = False
    requires_approval: bool = False
    prohibits_causal_verbs: bool = True


BENCHMARK_CORPUS: list[BenchmarkTestCase] = [
    # 1. Simple Lookup (5 cases)
    BenchmarkTestCase(
        case_id="lookup-01",
        prompt="What is the overall attendance distribution in the company?",
        category="simple_lookup",
        expected_intent="DATA_LOOKUP",
        expected_workflow="quick_answer",
        expected_tools=["calculate_distribution"],
    ),
    BenchmarkTestCase(
        case_id="lookup-02",
        prompt="Get attendance statistics for all employees",
        category="simple_lookup",
        expected_intent="DATA_LOOKUP",
        expected_workflow="quick_answer",
        expected_tools=["calculate_distribution"],
    ),
    BenchmarkTestCase(
        case_id="lookup-03",
        prompt="Show distribution of leave metrics",
        category="simple_lookup",
        expected_intent="DATA_LOOKUP",
        expected_workflow="quick_answer",
        expected_tools=["calculate_distribution"],
    ),
    BenchmarkTestCase(
        case_id="lookup-04",
        prompt="Lookup dataset schema and columns",
        category="simple_lookup",
        expected_intent="DATA_LOOKUP",
        expected_workflow="quick_answer",
        expected_tools=["calculate_distribution"],
    ),
    BenchmarkTestCase(
        case_id="lookup-05",
        prompt="Get workforce overview metrics",
        category="simple_lookup",
        expected_intent="DATA_LOOKUP",
        expected_workflow="quick_answer",
        expected_tools=["calculate_distribution"],
    ),

    # 2. Ranking (5 cases)
    BenchmarkTestCase(
        case_id="ranking-01",
        prompt="Top 5 departments by attendance",
        category="ranking",
        expected_intent="RANKING",
        expected_workflow="quick_answer",
        expected_tools=["rank_entities"],
    ),
    BenchmarkTestCase(
        case_id="ranking-02",
        prompt="Rank lowest 3 departments by attendance",
        category="ranking",
        expected_intent="RANKING",
        expected_workflow="quick_answer",
        expected_tools=["rank_entities"],
    ),
    BenchmarkTestCase(
        case_id="ranking-03",
        prompt="Which department has the best attendance record?",
        category="ranking",
        expected_intent="RANKING",
        expected_workflow="quick_answer",
        expected_tools=["rank_entities"],
    ),
    BenchmarkTestCase(
        case_id="ranking-04",
        prompt="Rank top teams with highest leave rates",
        category="ranking",
        expected_intent="RANKING",
        expected_workflow="quick_answer",
        expected_tools=["rank_entities"],
    ),
    BenchmarkTestCase(
        case_id="ranking-05",
        prompt="Bottom 5 groups by compliance",
        category="ranking",
        expected_intent="RANKING",
        expected_workflow="quick_answer",
        expected_tools=["rank_entities"],
    ),

    # 3. Comparison (5 cases)
    BenchmarkTestCase(
        case_id="compare-01",
        prompt="Compare Engineering vs Sales attendance",
        category="comparison",
        expected_intent="COMPARISON",
        expected_workflow="quick_answer",
        expected_tools=["compare_segments"],
    ),
    BenchmarkTestCase(
        case_id="compare-02",
        prompt="What is the difference between Operations and Marketing attendance?",
        category="comparison",
        expected_intent="COMPARISON",
        expected_workflow="quick_answer",
        expected_tools=["compare_segments"],
    ),
    BenchmarkTestCase(
        case_id="compare-03",
        prompt="Compare Sales vs Product leave rates",
        category="comparison",
        expected_intent="COMPARISON",
        expected_workflow="quick_answer",
        expected_tools=["compare_segments"],
    ),
    BenchmarkTestCase(
        case_id="compare-04",
        prompt="Finance versus Human Resources attendance performance",
        category="comparison",
        expected_intent="COMPARISON",
        expected_workflow="quick_answer",
        expected_tools=["compare_segments"],
    ),
    BenchmarkTestCase(
        case_id="compare-05",
        prompt="Compare department attendance against benchmark",
        category="comparison",
        expected_intent="COMPARISON",
        expected_workflow="quick_answer",
        expected_tools=["compare_segments"],
    ),

    # 4. Trend Analysis (4 cases)
    BenchmarkTestCase(
        case_id="trend-01",
        prompt="Show attendance trend over time",
        category="trend",
        expected_intent="TREND",
        expected_workflow="quick_answer",
        expected_tools=["get_trend"],
    ),
    BenchmarkTestCase(
        case_id="trend-02",
        prompt="What is the monthly trajectory of employee presence?",
        category="trend",
        expected_intent="TREND",
        expected_workflow="quick_answer",
        expected_tools=["get_trend"],
    ),
    BenchmarkTestCase(
        case_id="trend-03",
        prompt="Historical change in department leave rates",
        category="trend",
        expected_intent="TREND",
        expected_workflow="quick_answer",
        expected_tools=["get_trend"],
    ),
    BenchmarkTestCase(
        case_id="trend-04",
        prompt="Quarterly attendance history",
        category="trend",
        expected_intent="TREND",
        expected_workflow="quick_answer",
        expected_tools=["get_trend"],
    ),

    # 5. Relationship & Correlation (4 cases)
    BenchmarkTestCase(
        case_id="rel-01",
        prompt="Is there a correlation between attendance and leave?",
        category="relationship",
        expected_intent="RELATIONSHIP",
        expected_workflow="quick_answer",
        expected_tools=["analyze_relationship"],
    ),
    BenchmarkTestCase(
        case_id="rel-02",
        prompt="Analyze the relationship between department size and attendance",
        category="relationship",
        expected_intent="RELATIONSHIP",
        expected_workflow="quick_answer",
        expected_tools=["analyze_relationship"],
    ),
    BenchmarkTestCase(
        case_id="rel-03",
        prompt="What is the statistical association between leave patterns and presence?",
        category="relationship",
        expected_intent="RELATIONSHIP",
        expected_workflow="quick_answer",
        expected_tools=["analyze_relationship"],
    ),
    BenchmarkTestCase(
        case_id="rel-04",
        prompt="Are higher absences linked to lower attendance across units?",
        category="relationship",
        expected_intent="RELATIONSHIP",
        expected_workflow="quick_answer",
        expected_tools=["analyze_relationship"],
    ),

    # 6. Why & Root Cause / Multi-step (5 cases)
    BenchmarkTestCase(
        case_id="why-01",
        prompt="Why is there attendance variation across departments?",
        category="why_root_cause",
        expected_intent="MULTI_STEP_ANALYSIS",
        expected_workflow="analytical_investigation",
        expected_tools=["compare_segments", "analyze_relationship"],
    ),
    BenchmarkTestCase(
        case_id="why-02",
        prompt="Investigate root cause of attendance decline in Sales",
        category="why_root_cause",
        expected_intent="MULTI_STEP_ANALYSIS",
        expected_workflow="analytical_investigation",
        expected_tools=["compare_segments", "analyze_relationship"],
    ),
    BenchmarkTestCase(
        case_id="why-03",
        prompt="Explain why Operations is falling behind target compliance",
        category="why_root_cause",
        expected_intent="MULTI_STEP_ANALYSIS",
        expected_workflow="analytical_investigation",
        expected_tools=["compare_segments", "analyze_relationship"],
    ),
    BenchmarkTestCase(
        case_id="why-04",
        prompt="Deep dive into why absences are concentrating in specific teams",
        category="why_root_cause",
        expected_intent="MULTI_STEP_ANALYSIS",
        expected_workflow="analytical_investigation",
        expected_tools=["compare_segments", "analyze_relationship"],
    ),
    BenchmarkTestCase(
        case_id="why-05",
        prompt="Identify drivers behind leave rate discrepancies",
        category="why_root_cause",
        expected_intent="MULTI_STEP_ANALYSIS",
        expected_workflow="analytical_investigation",
        expected_tools=["compare_segments", "analyze_relationship"],
    ),

    # 7. Scenario Simulation (5 cases)
    BenchmarkTestCase(
        case_id="scen-01",
        prompt="What if we simulate changing days per week lever to 4?",
        category="scenario",
        expected_intent="SCENARIO_ANALYSIS",
        expected_workflow="scenario_analysis",
        expected_tools=["get_valid_levers", "run_counterfactual"],
        allows_scenario=True,
    ),
    BenchmarkTestCase(
        case_id="scen-02",
        prompt="Simulate impact if we increase in-office requirement by 1 day",
        category="scenario",
        expected_intent="SCENARIO_ANALYSIS",
        expected_workflow="scenario_analysis",
        expected_tools=["get_valid_levers", "run_counterfactual"],
        allows_scenario=True,
    ),
    BenchmarkTestCase(
        case_id="scen-03",
        prompt="Scenario analysis on workforce compliance with policy shift",
        category="scenario",
        expected_intent="SCENARIO_ANALYSIS",
        expected_workflow="scenario_analysis",
        expected_tools=["get_valid_levers", "run_counterfactual"],
        allows_scenario=True,
    ),
    BenchmarkTestCase(
        case_id="scen-04",
        prompt="What if we simulate a 3-day mandate across all departments?",
        category="scenario",
        expected_intent="SCENARIO_ANALYSIS",
        expected_workflow="scenario_analysis",
        expected_tools=["get_valid_levers", "run_counterfactual"],
        allows_scenario=True,
    ),
    BenchmarkTestCase(
        case_id="scen-05",
        prompt="Simulate counterfactual leave exemption credit lever",
        category="scenario",
        expected_intent="SCENARIO_ANALYSIS",
        expected_workflow="scenario_analysis",
        expected_tools=["get_valid_levers", "run_counterfactual"],
        allows_scenario=True,
    ),

    # 8. Presentation Creation (5 cases)
    BenchmarkTestCase(
        case_id="pres-01",
        prompt="Create executive slide presentation deck for attendance",
        category="presentation",
        expected_intent="PRESENTATION_CREATION",
        expected_workflow="presentation_creation",
        expected_tools=["rank_entities", "create_deck"],
    ),
    BenchmarkTestCase(
        case_id="pres-02",
        prompt="Generate slide deck briefing for leadership on workforce",
        category="presentation",
        expected_intent="PRESENTATION_CREATION",
        expected_workflow="presentation_creation",
        expected_tools=["rank_entities", "create_deck"],
    ),
    BenchmarkTestCase(
        case_id="pres-03",
        prompt="Build executive presentation on attendance metrics",
        category="presentation",
        expected_intent="PRESENTATION_CREATION",
        expected_workflow="presentation_creation",
        expected_tools=["rank_entities", "create_deck"],
    ),
    BenchmarkTestCase(
        case_id="pres-04",
        prompt="Prepare strategic briefing slides for board meeting",
        category="presentation",
        expected_intent="PRESENTATION_CREATION",
        expected_workflow="presentation_creation",
        expected_tools=["rank_entities", "create_deck"],
    ),
    BenchmarkTestCase(
        case_id="pres-05",
        prompt="Create slide deck summarizing department attendance performance",
        category="presentation",
        expected_intent="PRESENTATION_CREATION",
        expected_workflow="presentation_creation",
        expected_tools=["rank_entities", "create_deck"],
    ),

    # 9. Environmental Domain Cases (5 cases)
    BenchmarkTestCase(
        case_id="env-01",
        prompt="Rank top stations by PM10 concentration",
        category="ranking",
        domain="environmental",
        dataset_id=99768,
        expected_intent="RANKING",
        expected_workflow="quick_answer",
        expected_tools=["rank_entities"],
    ),
    BenchmarkTestCase(
        case_id="env-02",
        prompt="Compare Station A vs Station B particulate emissions",
        category="comparison",
        domain="environmental",
        dataset_id=99768,
        expected_intent="COMPARISON",
        expected_workflow="quick_answer",
        expected_tools=["compare_segments"],
    ),
    BenchmarkTestCase(
        case_id="env-03",
        prompt="Show trend of pollution measurements over time",
        category="trend",
        domain="environmental",
        dataset_id=99768,
        expected_intent="TREND",
        expected_workflow="quick_answer",
        expected_tools=["get_trend"],
    ),
    BenchmarkTestCase(
        case_id="env-04",
        prompt="Why is there pollution variation across monitoring stations?",
        category="why_root_cause",
        domain="environmental",
        dataset_id=99768,
        expected_intent="MULTI_STEP_ANALYSIS",
        expected_workflow="analytical_investigation",
        expected_tools=["compare_segments", "analyze_relationship"],
    ),
    BenchmarkTestCase(
        case_id="env-05",
        prompt="Create executive slide presentation deck for environmental data",
        category="presentation",
        domain="environmental",
        dataset_id=99768,
        expected_intent="PRESENTATION_CREATION",
        expected_workflow="presentation_creation",
        expected_tools=["rank_entities", "create_deck"],
    ),

    # 10. Governance & Edge Cases (12 cases)
    BenchmarkTestCase(
        case_id="gov-unauth-01",
        prompt="Simulate counterfactual salary adjustment",
        category="unsupported_request",
        caller="viewer",
        expected_intent="SCENARIO_ANALYSIS",
        expected_workflow="scenario_analysis",
        expected_tools=[],
    ),
    BenchmarkTestCase(
        case_id="gov-unauth-02",
        prompt="Simulate policy lever adjustment",
        category="unsupported_request",
        caller="viewer",
        expected_intent="SCENARIO_ANALYSIS",
        expected_workflow="scenario_analysis",
        expected_tools=[],
    ),
    BenchmarkTestCase(
        case_id="gov-cross-01",
        prompt="Join attendance with foreign dataset 88888",
        category="cross_dataset",
        expected_intent="DATA_LOOKUP",
        expected_workflow="quick_answer",
        expected_tools=[],
    ),
    BenchmarkTestCase(
        case_id="gov-approval-01",
        prompt="Rank top 5 departments",
        category="approval_required",
        requires_approval=True,
        expected_intent="RANKING",
        expected_workflow="quick_answer",
        expected_tools=["rank_entities"],
    ),
    BenchmarkTestCase(
        case_id="causal-01",
        prompt="Did leave rates cause attendance to drop?",
        category="causal_overclaim",
        expected_intent="RELATIONSHIP",
        expected_workflow="quick_answer",
        expected_tools=["analyze_relationship"],
        prohibits_causal_verbs=True,
    ),
    BenchmarkTestCase(
        case_id="causal-02",
        prompt="Explain what drove the decline of workforce compliance",
        category="causal_overclaim",
        expected_intent="MULTI_STEP_ANALYSIS",
        expected_workflow="analytical_investigation",
        expected_tools=["compare_segments", "analyze_relationship"],
        prohibits_causal_verbs=True,
    ),
    BenchmarkTestCase(
        case_id="ambiguous-01",
        prompt="Analyze the company",
        category="ambiguous_request",
        expected_intent="DATA_LOOKUP",
        expected_workflow="quick_answer",
        expected_tools=["calculate_distribution"],
    ),
    BenchmarkTestCase(
        case_id="ambiguous-02",
        prompt="Show me interesting numbers",
        category="ambiguous_request",
        expected_intent="DATA_LOOKUP",
        expected_workflow="quick_answer",
        expected_tools=["calculate_distribution"],
    ),
    BenchmarkTestCase(
        case_id="unsupported-01",
        prompt="Predict employee stock prices for next year",
        category="unsupported_request",
        expected_intent="DATA_LOOKUP",
        expected_workflow="quick_answer",
        expected_tools=["calculate_distribution"],
    ),
    BenchmarkTestCase(
        case_id="unsupported-02",
        prompt="Delete records from the database table",
        category="unsupported_request",
        expected_intent="DATA_LOOKUP",
        expected_workflow="quick_answer",
        expected_tools=["calculate_distribution"],
    ),
    BenchmarkTestCase(
        case_id="insufficient-01",
        prompt="Why did employee performance drop when there are no records?",
        category="insufficient_evidence",
        expected_intent="MULTI_STEP_ANALYSIS",
        expected_workflow="analytical_investigation",
        expected_tools=["compare_segments", "analyze_relationship"],
    ),
    BenchmarkTestCase(
        case_id="env-no-scen-01",
        prompt="What if we simulate changing days per week lever in environmental data?",
        category="scenario",
        domain="environmental",
        dataset_id=99768,
        expected_intent="SCENARIO_ANALYSIS",
        expected_workflow="scenario_analysis",
        expected_tools=["get_valid_levers"],
    ),
]
