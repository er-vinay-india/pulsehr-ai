"""Unit tests for the Council Coordinator routing engine and delivery guards."""
import pytest
import pandas as pd
from app.services.copilot.coordinator_models import RoutingAssignment, WorkerTarget
from app.services.copilot.council_coordinator import CouncilCoordinator


def test_coordinator_arithmetic_routing():
    """Verify safe calculator routing for mathematical expressions."""
    for expr in ["what is 2+2=?", "2 + 2", "calculate 1500 / 12", "solve (45 * 100) / 5", "100 - 35"]:
        decision = CouncilCoordinator.coordinate(expr)
        assert decision.assignment == RoutingAssignment.SAFE_CALCULATOR
        assert decision.worker_target == WorkerTarget.DETERMINISTIC_CALCULATOR
        assert decision.timeout_seconds <= 0.5
        assert decision.max_retries == 0


def test_coordinator_greeting_routing():
    """Verify immediate greeting routing with 0 LLM overhead."""
    for greeting in ["Hello", "hi", "hey there", "good morning", "thank you", "who are you"]:
        decision = CouncilCoordinator.coordinate(greeting)
        assert decision.assignment == RoutingAssignment.IMMEDIATE_GREETING
        assert decision.worker_target == WorkerTarget.IMMEDIATE_IDENTITY
        assert decision.timeout_seconds <= 0.2
        assert decision.max_retries == 0


def test_coordinator_concept_explanation_routing():
    """Verify single lightweight specialist routing for conceptual questions."""
    for concept in [
        "What does cohort average mean?",
        "Define Bradford Factor",
        "What is Simpson's Paradox?",
        "Explain p-value in statistics",
        "what does turnover rate mean"
    ]:
        decision = CouncilCoordinator.coordinate(concept)
        assert decision.assignment == RoutingAssignment.LIGHTWEIGHT_EXPLANATION
        assert decision.worker_target == WorkerTarget.SINGLE_SPECIALIST_MODEL
        assert decision.timeout_seconds <= 6.0


def test_coordinator_dataset_calculation_routing():
    """Verify deterministic dataset calculation routing."""
    df = pd.DataFrame({
        "math_score": [75, 80, 90],
        "reading_score": [68, 72, 85],
        "gender": ["female", "male", "female"]
    })
    for query in ["Average Math Score", "calculate mean reading_score", "count of students with math_score > 70"]:
        decision = CouncilCoordinator.coordinate(query, df=df)
        assert decision.assignment == RoutingAssignment.DATASET_CALCULATION
        assert decision.worker_target == WorkerTarget.ANALYTICAL_PLANNER
        assert decision.timeout_seconds <= 4.0


def test_coordinator_follow_up_chart_resolution():
    """Verify that 'Show that in chart format' resolves prior calculation context and routes to chart library."""
    prior_context = {
        "visualization_context": {
            "metric": "math_score",
            "operation": "mean"
        },
        "metric": "math_score"
    }
    decision = CouncilCoordinator.coordinate("Show that in chart format", prior_context=prior_context)
    assert decision.assignment == RoutingAssignment.VISUAL_CHART
    assert decision.worker_target == WorkerTarget.CHART_LIBRARY
    assert decision.requires_visual is True
    assert decision.is_follow_up is True
    assert decision.resolved_context.get("active_metric") == "math_score"


def test_coordinator_sheet_quality_routing():
    """Verify raw file quality check routing."""
    for q in [
        "How many missing values in the raw sheet?",
        "check missing values",
        "how many null cells are in the sheet?",
        "unmatched rows in dataset"
    ]:
        decision = CouncilCoordinator.coordinate(q)
        assert decision.assignment == RoutingAssignment.SHEET_QUALITY
        assert decision.worker_target == WorkerTarget.SHEET_QUALITY_INSPECTOR
        assert decision.timeout_seconds <= 2.0


def test_coordinator_council_deliberation_routing():
    """Verify that complex root-cause and policy trade-offs assemble the full Council."""
    for q in [
        "Why are scores declining, and what should we do?",
        "What are the root causes and recommended strategic interventions for turnover?",
        "Assemble the council to deliberate on store performance trade-offs"
    ]:
        decision = CouncilCoordinator.coordinate(q)
        assert decision.assignment == RoutingAssignment.COUNCIL_DELIBERATION
        assert decision.worker_target == WorkerTarget.UNION_WAR_ROOM
        assert decision.timeout_seconds <= 30.0


def test_coordinator_delivery_verification_attaches_chart():
    """Verify delivery guard attaches a visual chart when requested if missing from worker output."""
    decision = CouncilCoordinator.coordinate("Show that in chart format", prior_context={"metric": "Attendance"})
    decision.requires_visual = True

    df = pd.DataFrame({"department": ["Sales", "Engineering"], "attendance": [85, 92]})
    raw_result = {
        "answer": "Attendance is 85 in Sales and 92 in Engineering.",
        "calculation": {
            "column": "attendance",
            "results": [
                {"group": "Sales", "value": 85},
                {"group": "Engineering", "value": 92}
            ],
            "unit": "%"
        }
    }

    verified = CouncilCoordinator.verify_delivery(decision, raw_result, df=df, sheet_name="Test Sheet", sheet_id=1)
    assert "visual_charts" in verified
    assert len(verified["visual_charts"]) == 1
    assert verified["visual_charts"][0]["chart_type"] in ("column", "bar")
    assert verified["coordinator"]["verified_delivery"] is True


def test_coordinator_execution_sync_arithmetic():
    """Verify synchronous execution of arithmetic expression."""
    decision = CouncilCoordinator.coordinate("what is 2+2=?")
    res = CouncilCoordinator.execute_sync(decision, "what is 2+2=?")
    assert "4" in res["answer"]
    assert res["status"] == "success"
    assert res["timings"]["is_deterministic"] is True


def test_coordinator_execution_sync_greeting():
    """Verify synchronous execution of greeting."""
    decision = CouncilCoordinator.coordinate("Hello")
    res = CouncilCoordinator.execute_sync(decision, "Hello")
    assert "HRIDAY" in res["answer"]
    assert res["status"] == "success"
    assert res["timings"]["is_deterministic"] is True
