import pytest
import pandas as pd
import json
from app.services.data_engine.semantic_classifier import SemanticClassifier
from app.services.data_engine.analysis_context import (
    IntentDataReconciler,
    AnalysisContext,
    BusinessRule,
    ProvenanceType
)
from app.services.data_engine.opportunity_map import OpportunityMapGenerator, OpportunityType
from app.services.data_engine.candidate_fact_discovery import CandidateFactDiscoveryEngine
from app.services.data_engine.interestingness_ranker import FactInterestingnessRanker
from app.services.reporting.workflow_orchestrator import WorkflowOrchestrator
from app.services.copilot.generic_copilot_engine import GenericCopilotEngine
from app.db.database import get_connection, init_db


@pytest.fixture
def wfo_df():
    """A realistic WFO dataset with Department, Employee ID, WFO Days, and Leave Days."""
    data = {
        "Department": ["Engineering", "Engineering", "Engineering", "Sales", "Sales", "Sales", "HR", "HR"],
        "Employee_ID": ["E1", "E2", "E3", "E4", "E5", "E6", "E7", "E8"],
        "WFO_Days": [3.5, 4.0, 2.0, 1.5, 2.0, 1.0, 4.0, 5.0],
        "Leave_Days": [1.0, 0.5, 2.0, 5.0, 4.0, 6.0, 0.0, 1.0],
    }
    return pd.DataFrame(data)


def test_wfo_scenario_user_analysis_brief(wfo_df):
    """
    Verifies the complete User Analysis Brief pipeline:
    1. Context parsing & reconciliation with explicit rules.
    2. 3-day threshold marked USER_EXPLICIT.
    3. Requested questions become priority opportunities.
    4. Report puts priority compliance & questions before generic discoveries.
    5. Copilot retains context and answers rule inquiries deterministically.
    6. Unsupported assumptions (salary) are flagged and never hallucinated.
    """
    # 1. Profile the dataset
    profile = SemanticClassifier.profile_dataset(wfo_df, dataset_name="WFO_Attendance")
    assert "WFO_Days" in profile.columns
    assert "Department" in profile.columns

    # 2. Reconcile user intent
    raw_user_brief = (
        "Employees must work from office at least 3 days per week. "
        "Rank departments by compliance percentage and show which departments have the highest leave rate. "
        "Also what is the average salary?"
    )
    ctx = IntentDataReconciler.parse_and_reconcile(
        raw_text=raw_user_brief,
        profile=profile,
        dataset_id=1,
        sheet_id=10
    )

    # CHECK 1: Context is properly created and mode is INTENT_DRIVEN
    assert ctx.mode == "INTENT_DRIVEN"
    assert ctx.provenance == "USER_EXPLICIT"

    # CHECK 2: 3-day threshold marked USER_EXPLICIT
    assert len(ctx.business_rules) >= 1
    wfo_rule = next((r for r in ctx.business_rules if "WFO" in r.metric_name), None)
    assert wfo_rule is not None
    assert wfo_rule.target_value == 3.0
    assert wfo_rule.operator in (">=", ">")
    assert wfo_rule.source == "USER_EXPLICIT"

    # CHECK 6: Unsupported assumption (salary) is flagged in unsupported_requests, not hallucinated
    assert any("salary" in u.lower() for u in ctx.unsupported_requests)
    assert not any("salary" in m.lower() for m in ctx.important_metrics)

    # CHECK 3: Requested questions become priority opportunities
    opp_map = OpportunityMapGenerator.generate(profile, context=ctx)
    user_priority_opps = [o for o in opp_map.opportunities if o.is_user_priority]
    assert len(user_priority_opps) > 0

    # Specifically check that target_compliance opportunity was created for the business rule
    compliance_opp = next((o for o in opp_map.opportunities if o.opportunity_type == OpportunityType.TARGET_COMPLIANCE), None)
    assert compliance_opp is not None
    assert compliance_opp.is_user_priority is True
    assert compliance_opp.target_rule.get("threshold") == 3.0

    # 4. Generate candidate facts
    facts, _ = CandidateFactDiscoveryEngine.discover_facts(wfo_df, profile, opp_map)
    priority_facts = [f for f in facts if f.priority_type == "USER_PRIORITY"]
    assert len(priority_facts) > 0

    compliance_facts = [f for f in facts if f.fact_type == "target_compliance"]
    assert len(compliance_facts) > 0
    # Provenance must be USER_EXPLICIT for target compliance facts
    assert compliance_facts[0].provenance == "USER_EXPLICIT"

    # CHECK 4: Report puts priority compliance/questions before generic discoveries
    ranked_facts = FactInterestingnessRanker.rank_interesting_facts(facts)
    # The top ranked fact should be USER_PRIORITY
    assert ranked_facts[0].priority_type == "USER_PRIORITY"

    # Test WorkflowOrchestrator integration
    exec_result = WorkflowOrchestrator.execute(wfo_df, dataset_name="WFO_Attendance", context=ctx)
    assert exec_result.analysis_context is not None
    ctx_mode = exec_result.analysis_context.get("mode") if isinstance(exec_result.analysis_context, dict) else exec_result.analysis_context.mode
    assert ctx_mode == "INTENT_DRIVEN"
    assert exec_result.ranked_fact_count > 0

    # In deck spec, user priority slides appear first after hero
    deck_spec = exec_result.deck_spec
    assert deck_spec is not None
    assert len(deck_spec["slides"]) >= 2
    # Slide 1 is Hero
    assert deck_spec["slides"][0]["order"] == 1
    # Slide 2 should be a prioritized user context finding
    slide_2 = deck_spec["slides"][1]
    assert slide_2.get("is_user_priority") is True or slide_2.get("category") == "USER PRIORITY FINDING"

    # CHECK 5: Chatbot retains context and answers rule inquiries deterministically
    engine = GenericCopilotEngine()
    # Direct question about business rule policy
    answer = engine.answer_query(
        query="What is the mandatory WFO policy?",
        df=wfo_df,
        profile=profile,
        ranked_facts=ranked_facts,
        context=ctx
    )
    assert answer["provenance"] == "USER_EXPLICIT"
    assert "3.0" in answer["answer"] or "3" in answer["answer"]
    assert "[USER_EXPLICIT]" in answer["answer"]
    assert answer["metadata"]["intent"] == "BUSINESS_CONTEXT"

    # Question about unsupported metric
    unsupported_answer = engine.answer_query(
        query="What is the employee salary distribution?",
        df=wfo_df,
        profile=profile,
        ranked_facts=ranked_facts,
        context=ctx
    )
    assert "salary" in unsupported_answer["answer"].lower()
    # It must state that salary is not present in the dataset
    assert "not present" in unsupported_answer["answer"].lower() or "not found" in unsupported_answer["answer"].lower()


def test_discovery_fallback_when_no_brief(wfo_df):
    """
    Verifies that when no brief is provided (context=None or empty text),
    the system cleanly stays in DISCOVERY mode without breaking.
    """
    profile = SemanticClassifier.profile_dataset(wfo_df, dataset_name="WFO_Attendance")
    opp_map = OpportunityMapGenerator.generate(profile, context=None)
    assert opp_map is not None
    # All opportunities should have is_user_priority=False
    for o in opp_map.opportunities:
        assert o.is_user_priority is False

    facts, _ = CandidateFactDiscoveryEngine.discover_facts(wfo_df, profile, opp_map)
    for f in facts:
        assert f.priority_type == "DISCOVERY"

    ranked = FactInterestingnessRanker.rank_interesting_facts(facts)
    for r in ranked:
        assert r.priority_type == "DISCOVERY"

    res = WorkflowOrchestrator.execute(wfo_df, dataset_name="WFO_Attendance", context=None)
    assert res.analysis_context is None
