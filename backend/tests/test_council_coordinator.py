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


@pytest.mark.parametrize('query', ['Hello average Math Score', 'Hi show gender counts', 'Hello explain median', 'Hey missing values'])
def test_greeting_prefix_does_not_replace_a_real_request(query):
    decision = CouncilCoordinator.coordinate(query)
    assert decision.worker_target != WorkerTarget.IMMEDIATE_IDENTITY


@pytest.mark.parametrize('query', ['Hi there!', 'Hello HRIDAY!', 'Good morning HRIDAY'])
def test_pure_greetings_still_use_the_immediate_responder(query):
    decision = CouncilCoordinator.coordinate(query)
    assert decision.worker_target == WorkerTarget.IMMEDIATE_IDENTITY
    assert 'HRIDAY' in CouncilCoordinator.execute_sync(decision, query)['answer']


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


@pytest.mark.parametrize('query', [
    'what is good about this data you have', "what's good about my uploaded data?",
    'what are the strengths of this sheet', 'give me 3 good points',
])
def test_dataset_strengths_precede_conceptual_routing(query):
    decision = CouncilCoordinator.coordinate(query, prior_context={'metric': 'math_score', 'sheet_id': 1})
    assert decision.worker_target == WorkerTarget.ANALYTICAL_PLANNER
    assert decision.resolved_context == {}


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
        ("what is the log of 10 base 2", "log(10, 2)", 3.32192809489),
        ("log 10 base 2", "log(10, 2)", 3.32192809489),
        ("log10 of 100", "log10(100)", 2.0),
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

    # Turn 4: What is the log of 10 base 2
    d4 = CouncilCoordinator.coordinate("what is the log of 10 base 2", prior_context=ctx2, df=students, sheet_id=7)
    assert d4.assignment == RoutingAssignment.SAFE_CALCULATOR
    assert d4.worker_target == WorkerTarget.DETERMINISTIC_CALCULATOR
    assert d4.extracted_expression == "log(10, 2)"
    assert d4.resolved_context == {}  # Context isolation

    r4 = CouncilCoordinator.execute_sync(d4, "what is the log of 10 base 2", df=students, sheet_name="Students", sheet_id=7, prior_context=d4.resolved_context)
    assert r4["status"] == "success"
    assert "3.321928" in r4["answer"]
    assert r4["tool_used"] == "arithmetic"
    assert r4["timings"]["is_deterministic"] is True

    # Turn 5: Streaming SSE for log calculation
    stream_events = list(CouncilCoordinator.stream_events(d4, "what is the log of 10 base 2", df=students, sheet_name="Students", sheet_id=7, prior_context=d4.resolved_context))
    assert any("event: done" in ev for ev in stream_events)
    assert any("3.321928" in ev for ev in stream_events)


def test_coordinator_dataset_metadata_routing_and_execution():
    """Verify natural questions about record count, rows, and columns are fast-gated and deterministic."""
    df = pd.DataFrame({
        "math_score": [72, 69, 90, 47, 76],
        "reading_score": [72, 90, 95, 57, 78],
        "writing_score": [74, 88, 93, 44, 75],
        "gender": ["female", "female", "female", "male", "male"]
    })

    # Record / row count queries
    count_queries = [
        "how much records we have here",
        "how many records we have here",
        "how many rows in this table",
        "what is the total records",
        "total number of records"
    ]
    for q in count_queries:
        decision = CouncilCoordinator.coordinate(q, df=df, sheet_id=99)
        assert decision.worker_target == WorkerTarget.DATASET_METADATA_INSPECTOR
        res = CouncilCoordinator.execute_sync(decision, q, df=df, sheet_name="StudentsPerformance", sheet_id=99)
        assert res["status"] == "success"
        assert "5 records" in res["answer"]
        assert "4 columns" in res["answer"]
        assert res["model_used"] == "Deterministic dataset metadata inspector"

    # Column inspection queries
    col_queries = [
        "what columns are in this sheet",
        "list columns",
        "what are the column names"
    ]
    for q in col_queries:
        decision = CouncilCoordinator.coordinate(q, df=df, sheet_id=99)
        assert decision.worker_target == WorkerTarget.DATASET_METADATA_INSPECTOR
        res = CouncilCoordinator.execute_sync(decision, q, df=df, sheet_name="StudentsPerformance", sheet_id=99)
        assert res["status"] == "success"
        assert "`math_score`" in res["answer"]
        assert "`reading_score`" in res["answer"]

    # SSE streaming test for metadata
    stream_events = list(CouncilCoordinator.stream_events(
        decision, "how much records we have here", df=df, sheet_name="StudentsPerformance", sheet_id=99
    ))
    assert any("event: status" in ev for ev in stream_events)
    assert any("5 records" in ev for ev in stream_events)
    assert any("event: done" in ev for ev in stream_events)
