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


def test_coordinator_bounded_natural_language_math():
    """Verify natural-language bounded math (square root, cube root, powers) routes to deterministic calculator."""
    cases = [
        ("what is the square root of 9", "sqrt(9)", 3.0),
        ("square root of 16", "sqrt(16)", 4.0),
        ("sqrt 25", "sqrt(25)", 5.0),
        ("cube root of 27", "cbrt(27)", 3.0),
        ("9 squared", "(9) ** 2", 81.0),
        ("3 cubed", "(3) ** 3", 27.0),
        ("2 to the power of 8", "(2) ** (8)", 256.0),
    ]
    for query, expected_expr, expected_val in cases:
        decision = CouncilCoordinator.coordinate(query)
        assert decision.assignment == RoutingAssignment.SAFE_CALCULATOR
        assert decision.worker_target == WorkerTarget.DETERMINISTIC_CALCULATOR
        assert decision.extracted_expression == expected_expr
        res = CouncilCoordinator.execute_sync(decision, query)
        assert f"{expected_val:,.12g}" in res["answer"]
        assert res["status"] == "success"
        assert res["timings"]["is_deterministic"] is True


def test_complete_conversation_replay():
    """Replay exact user conversation:
    1. 'Students by Gender' (draw count distribution chart)
    2. 'draw the chart based on Cohort Average: Math Score' (recomputes 66.09)
    3. 'what is the square root of 9' (assert answer is 3 with 0 dataset/model calls)
    """
    students = pd.DataFrame({
        "Math Score": [66] * 990 + [75] * 10,
        "Reading_Score": [70] * 1000,
        "Gender": ["Female"] * 500 + ["Male"] * 500
    })

    # Turn 1: Students by Gender
    d1 = CouncilCoordinator.coordinate("draw the chart based on Students by Gender", df=students, sheet_id=7)
    r1 = CouncilCoordinator.execute_sync(d1, "draw the chart based on Students by Gender", df=students, sheet_name="Students", sheet_id=7)
    assert r1["status"] == "success"
    assert len(r1["visual_charts"]) == 1
    assert set(r1["visual_charts"][0]["categories"]) == {"Female", "Male"}

    # Turn 2: Cohort Average: Math Score
    ctx1 = r1["prior_context"]
    d2 = CouncilCoordinator.coordinate("draw the chart based on Cohort Average: Math Score", prior_context=ctx1, df=students, sheet_id=7)
    r2 = CouncilCoordinator.execute_sync(d2, "draw the chart based on Cohort Average: Math Score", df=students, sheet_name="Students", sheet_id=7, prior_context=d2.resolved_context)
    assert r2["status"] == "success"
    assert len(r2["visual_charts"]) == 1
    assert r2["visual_charts"][0]["series"][0]["values"] == [pytest.approx(66.09, abs=0.01)]

    # Turn 3: What is the square root of 9
    ctx2 = r2["prior_context"]
    d3 = CouncilCoordinator.coordinate("what is the square root of 9", prior_context=ctx2, df=students, sheet_id=7)
    assert d3.assignment == RoutingAssignment.SAFE_CALCULATOR
    assert d3.worker_target == WorkerTarget.DETERMINISTIC_CALCULATOR
    assert d3.extracted_expression == "sqrt(9)"
    assert d3.resolved_context == {}  # Execution context strictly separated from prior dataset context

    r3 = CouncilCoordinator.execute_sync(d3, "what is the square root of 9", df=students, sheet_name="Students", sheet_id=7, prior_context=d3.resolved_context)
    assert r3["status"] == "success"
    assert "**3**" in r3["answer"] or "= **3**" in r3["answer"]
    assert r3["tool_used"] == "arithmetic"
    assert r3["timings"]["is_deterministic"] is True

