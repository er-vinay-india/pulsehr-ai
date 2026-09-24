"""Tests and benchmark for Phase 3A: Evidence-Grounded AI Interpretation.

Runs Qwen 3.5 (ANALYST role) on verified CandidateFacts across 4 diverse datasets:
1. Sales
2. Manufacturing
3. Product Analytics
4. Ambiguous Dataset

Audits outputs using InterpretationClaimValidator:
- Citation correctness
- Numeric fidelity
- Polarity neutrality
- Non-causality in observations
"""

import time
import pytest
import pandas as pd

from app.services.data_engine.semantic_classifier import SemanticClassifier
from app.services.data_engine.opportunity_map import OpportunityMapGenerator
from app.services.data_engine.candidate_fact_discovery import CandidateFactDiscoveryEngine
from app.services.data_engine.interestingness_ranker import FactInterestingnessRanker
from app.services.analyst.analyst_agent import AnalystAgent
from app.services.analyst.interpretation_validator import InterpretationClaimValidator


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
# TESTS
# -----------------------------------------------------------------------------

def test_manufacturing_interpretation(manufacturing_df):
    """Manufacturing interpretation: verifies shift & QA cross-fact connection."""
    profile = SemanticClassifier.profile_dataset(manufacturing_df, "Plant Telemetry")
    opp_map = OpportunityMapGenerator.generate(profile)
    reliable, _ = CandidateFactDiscoveryEngine.discover_facts(manufacturing_df, profile, opp_map)
    ranked = FactInterestingnessRanker.rank_interesting_facts(reliable, limit=8)
    facts_lookup = {f.fact_id: f for f in reliable}

    t0 = time.perf_counter()
    response, result = AnalystAgent.interpret(profile, ranked, max_facts=8)
    elapsed = time.perf_counter() - t0

    print(f"\n--- Manufacturing Latency: {elapsed:.2f}s ---")
    print(f"Executive Synthesis:\n{response.executive_synthesis}\n")
    for ins in response.insights:
        print(f"[{ins.insight_id}] {ins.title}")
        print(f"  OBS: {ins.observation}")
        print(f"  INT: {ins.interpretation}")
        print(f"  Q's: {ins.questions_to_investigate}")
        print(f"  Facts: {ins.supporting_fact_ids}")

    assert result.success is True
    assert len(response.insights) >= 1

    audit = InterpretationClaimValidator.audit_response(response, facts_lookup, profile=profile)
    print(f"Audit Result: passed={audit.passed_insights}/{audit.total_insights}, violations={audit.total_violations}")
    for r in audit.reports:
        if not r.passed:
            for v in r.violations:
                print(f"  Violation in {r.insight_id}: [{v.violation_type}] {v.message}")

    assert audit.all_passed, f"Audit failed with violations: {audit.reports}"


def test_sales_interpretation(sales_df):
    """Sales interpretation: verifies multi-metric commercial synthesis."""
    profile = SemanticClassifier.profile_dataset(sales_df, "Regional Sales")
    opp_map = OpportunityMapGenerator.generate(profile)
    reliable, _ = CandidateFactDiscoveryEngine.discover_facts(sales_df, profile, opp_map)
    ranked = FactInterestingnessRanker.rank_interesting_facts(reliable, limit=8)
    facts_lookup = {f.fact_id: f for f in reliable}

    t0 = time.perf_counter()
    response, result = AnalystAgent.interpret(profile, ranked, max_facts=8)
    elapsed = time.perf_counter() - t0

    print(f"\n--- Sales Latency: {elapsed:.2f}s ---")
    print(f"Executive Synthesis:\n{response.executive_synthesis}\n")
    for ins in response.insights:
        print(f"[{ins.insight_id}] {ins.title}")
        print(f"  OBS: {ins.observation}")
        print(f"  INT: {ins.interpretation}")
        print(f"  Q's: {ins.questions_to_investigate}")

    assert result.success is True
    assert len(response.insights) >= 1

    audit = InterpretationClaimValidator.audit_response(response, facts_lookup, profile=profile)
    print(f"Audit Result: passed={audit.passed_insights}/{audit.total_insights}, violations={audit.total_violations}")
    for r in audit.reports:
        if not r.passed:
            for v in r.violations:
                print(f"  Violation in {r.insight_id}: [{v.violation_type}] {v.message}")

    assert audit.all_passed, f"Audit failed with violations: {audit.reports}"


def test_product_analytics_interpretation(product_analytics_df):
    """Product analytics interpretation: verifies engagement/conversion patterns."""
    profile = SemanticClassifier.profile_dataset(product_analytics_df, "Session Analytics")
    opp_map = OpportunityMapGenerator.generate(profile)
    reliable, _ = CandidateFactDiscoveryEngine.discover_facts(product_analytics_df, profile, opp_map)
    ranked = FactInterestingnessRanker.rank_interesting_facts(reliable, limit=8)
    facts_lookup = {f.fact_id: f for f in reliable}

    t0 = time.perf_counter()
    response, result = AnalystAgent.interpret(profile, ranked, max_facts=8)
    elapsed = time.perf_counter() - t0

    print(f"\n--- Product Analytics Latency: {elapsed:.2f}s ---")
    print(f"Executive Synthesis:\n{response.executive_synthesis}\n")
    for ins in response.insights:
        print(f"[{ins.insight_id}] {ins.title}")
        print(f"  OBS: {ins.observation}")
        print(f"  INT: {ins.interpretation}")
        print(f"  Q's: {ins.questions_to_investigate}")

    assert result.success is True
    assert len(response.insights) >= 1

    audit = InterpretationClaimValidator.audit_response(response, facts_lookup, profile=profile)
    print(f"Audit Result: passed={audit.passed_insights}/{audit.total_insights}, violations={audit.total_violations}")
    for r in audit.reports:
        if not r.passed:
            for v in r.violations:
                print(f"  Violation in {r.insight_id}: [{v.violation_type}] {v.message}")

    assert audit.all_passed, f"Audit failed with violations: {audit.reports}"


def test_ambiguous_interpretation(ambiguous_df):
    """Ambiguous dataset: verifies neutral polarity and cautious non-domain reasoning."""
    profile = SemanticClassifier.profile_dataset(ambiguous_df, "Masked Telemetry")
    opp_map = OpportunityMapGenerator.generate(profile)
    reliable, _ = CandidateFactDiscoveryEngine.discover_facts(ambiguous_df, profile, opp_map)
    ranked = FactInterestingnessRanker.rank_interesting_facts(reliable, limit=8)
    facts_lookup = {f.fact_id: f for f in reliable}

    t0 = time.perf_counter()
    response, result = AnalystAgent.interpret(profile, ranked, max_facts=8)
    elapsed = time.perf_counter() - t0

    print(f"\n--- Ambiguous Dataset Latency: {elapsed:.2f}s ---")
    print(f"Executive Synthesis:\n{response.executive_synthesis}\n")
    for ins in response.insights:
        print(f"[{ins.insight_id}] {ins.title}")
        print(f"  OBS: {ins.observation}")
        print(f"  INT: {ins.interpretation}")
        print(f"  Q's: {ins.questions_to_investigate}")

    assert result.success is True
    assert len(response.insights) >= 1

    audit = InterpretationClaimValidator.audit_response(response, facts_lookup, profile=profile)
    print(f"Audit Result: passed={audit.passed_insights}/{audit.total_insights}, violations={audit.total_violations}")
    for r in audit.reports:
        if not r.passed:
            for v in r.violations:
                print(f"  Violation in {r.insight_id}: [{v.violation_type}] {v.message}")

    assert audit.all_passed, f"Audit failed with violations: {audit.reports}"
