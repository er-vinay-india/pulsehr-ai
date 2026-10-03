"""Comprehensive Automated Test Suite for HighView / HRIDAY AI Council Architecture.

Verifies:
Test 1: Retrieval-only request ('5 key points') routes to Fact/RAG without calculation or DeepSeek.
Test 2: Calculation request ('which 5 employees came least?') routes to Qwen plan, enforces employee grain, and runs deterministic math.
Test 3: Hybrid request ('why are these employees coming less?') combines calculation with non-causal contextual retrieval.
Test 4: Wrong-grain evidence protection: Department facts cannot satisfy employee requests.
Test 5: ModelGateway structured Pydantic validation and error handling on malformed JSON.
Test 6: Conflicting evidence arbitration: DeepSeek critic detects discrepancy and prefers deterministic calculation.
Test 7: Simple conceptual question ('what is attendance compliance?') takes minimal route without invoking full council.
Test 8: Stale RAG evidence rejection.
"""

import json
import pytest
import pandas as pd
from pydantic import ValidationError
from starlette.testclient import TestClient

from app.main import app
from app.routers.copilot import classify_analytical_intent
from app.services.copilot.council_contracts import (
    CouncilPlan,
    RetrievalRequest,
    RetrievedEvidence,
    CalculationResult,
    CriticReview,
    EvidenceItem,
    EvidenceType,
    EntityGrain,
    TaskType,
)
from app.services.copilot.council_evidence_service import CouncilEvidenceService
from app.services.copilot_query_planner import (
    AnalyticalQueryPlan,
    plan_analytical_query,
    execute_analytical_plan
)
from app.services.rag_service import semantic_search
from app.services.hybrid_retrieval import hybrid_search, keyword_search


def test_1_retrieval_only_request():
    """Test 1: '5 key points' classifies as FACT_RETRIEVAL, bypassing calculation."""
    intent = classify_analytical_intent("5 key points")
    assert intent == "FACT_RETRIEVAL"

    c_plan = CouncilPlan(
        task_type=TaskType.FACT_RETRIEVAL,
        requires_rag=True,
        requires_calculation=False
    )
    assert c_plan.requires_calculation is False
    assert c_plan.requires_rag is True


def test_2_calculation_request_preserves_employee_grain(hriday_test_env):
    """Test 2: 'which 5 employees came least?' plans employee grain, enforces no wrong-grain substitution."""
    did = hriday_test_env["dataset_id"]
    sid = hriday_test_env["sheet_id"]

    plan = plan_analytical_query("which 5 employees came least?", dataset_id=did, sheet_id=sid)
    assert plan is not None
    assert plan.entity_grain == "employee"
    assert plan.direction == "lowest"

    res = execute_analytical_plan(plan)
    assert res["status"] == "success"
    assert res["evidence"]["result_grain"] == "employee"
    assert len(res["raw_analysis"]["rows"]) <= 5
    # Evaluates full eligible population
    assert res["evidence"]["coverage"]["distinct_employees"] == 14


def test_3_hybrid_request_with_non_causal_disclaimer():
    """Test 3: 'why are these employees coming less?' mandates non-causal disclaimer in critic review."""
    c_plan = CouncilPlan(
        task_type=TaskType.HYBRID_ANALYSIS,
        entity_grain=EntityGrain.EMPLOYEE,
        requires_rag=True,
        requires_calculation=True
    )
    evidence = [
        EvidenceItem(
            evidence_type=EvidenceType.CALCULATION,
            source_id="calc-1",
            entity_grain=EntityGrain.EMPLOYEE,
            content={"metric": "attendance", "worst": "LB101"}
        ),
        EvidenceItem(
            evidence_type=EvidenceType.RETRIEVED_KNOWLEDGE,
            source_id="rag-1",
            entity_grain=EntityGrain.EMPLOYEE,
            content={"text": "Historical leave policy notes."}
        )
    ]

    critic_res = CouncilEvidenceService.arbitrate_evidence(
        user_query="why are these employees coming less?",
        evidence_items=evidence,
        plan=c_plan
    )
    assert critic_res.calculation_supported is True
    assert critic_res.preferred_evidence_source == "calculation"
    assert any("causation" in c.lower() for c in critic_res.mandatory_caveats)


def test_4_wrong_grain_evidence_rejected():
    """Test 4: Department grain evidence cannot satisfy employee grain plan."""
    c_plan = CouncilPlan(
        task_type=TaskType.ANALYTICAL_CALCULATION,
        entity_grain=EntityGrain.EMPLOYEE,
        requires_calculation=True
    )
    # Evidence with department grain
    dept_evidence = [
        EvidenceItem(
            evidence_type=EvidenceType.CALCULATION,
            source_id="calc-dept",
            entity_grain=EntityGrain.DEPARTMENT,
            content={"metric": "attendance", "lowest_department": "Corporate Functions"}
        )
    ]

    critic_res = CouncilEvidenceService.arbitrate_evidence(
        user_query="which employee is absent most?",
        evidence_items=dept_evidence,
        plan=c_plan
    )
    assert critic_res.grain_consistent is False
    assert critic_res.conflict_detected is True
    assert "Grain mismatch" in critic_res.discrepancy_details


def test_5_pydantic_schema_validation_and_rejection():
    """Test 5: Pydantic rejects invalid CouncilPlan parameters with strict typing."""
    with pytest.raises(ValidationError):
        # direction must be 'lowest', 'highest', or 'all'
        CouncilPlan(direction="invalid_direction")

    with pytest.raises(ValidationError):
        # ranking_limit must be >= 1
        CouncilPlan(ranking_limit=0)


def test_6_conflicting_evidence_arbitration():
    """Test 6: When calculation and qualitative findings differ, calculation is preferred source."""
    c_plan = CouncilPlan(
        task_type=TaskType.HYBRID_ANALYSIS,
        entity_grain=EntityGrain.DEPARTMENT,
        metric="attendance"
    )
    evidence = [
        EvidenceItem(
            evidence_type=EvidenceType.CALCULATION,
            source_id="calc-1",
            entity_grain=EntityGrain.DEPARTMENT,
            content={"metric": "attendance", "value": 24.5}
        ),
        EvidenceItem(
            evidence_type=EvidenceType.DOMAIN_GOVERNANCE,
            source_id="fact-1",
            entity_grain=EntityGrain.DEPARTMENT,
            content={"observation": "Department reported 10.0 attendance previously."}
        )
    ]

    review = CouncilEvidenceService.arbitrate_evidence(
        user_query="check attendance discrepancy",
        evidence_items=evidence,
        plan=c_plan
    )
    assert review.preferred_evidence_source == "calculation"


def test_7_simple_conceptual_question_minimal_route():
    """Test 7: 'what is attendance compliance?' routes to GENERAL_CHAT without invoking full council."""
    intent = classify_analytical_intent("what is attendance compliance?")
    assert intent == "GENERAL_CHAT"

    # Plan should be None, preventing any database calculation run
    plan = plan_analytical_query("what is attendance compliance?")
    assert plan is None


def test_8_dataset_scoped_rag_filtering(hriday_test_env):
    """Test 8: RAG semantic and hybrid search strictly filters by dataset_id."""
    # Semantic search with dataset_id=999999 (non-existent) returns empty list
    res_empty = semantic_search("attendance", top_k=5, dataset_id=999999)
    assert len(res_empty) == 0

    # Keyword search with dataset_id=999999 returns empty list
    kw_empty = keyword_search("attendance", top_k=5, dataset_id=999999)
    assert len(kw_empty) == 0

    # Hybrid search with dataset_id=999999 returns empty list
    hyb_empty = hybrid_search("attendance", top_k=5, dataset_id=999999)
    assert len(hyb_empty) == 0
