"""Regression: a chart follow-up must use verified series, never an ASCII drawing."""
import json

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.routers import copilot
from app.services.copilot.chat_visuals import answer_chat_visual

pytestmark = pytest.mark.copilot


def ask(query, frame, prior=None, sheet=7):
    return answer_chat_visual(query, frame, "Student Academic Achievement", sheet, 3, prior)


@pytest.fixture
def students():
    return pd.DataFrame({"Math Score": [66] * 990 + [75] * 10,
                         "Reading_Score": [70] * 1000,
                         "Gender": ["Female"] * 500 + ["Male"] * 500})


@pytest.mark.unit
def test_cohort_average_then_chart_recomputes_from_source(students):
    first = ask("display me Cohort Average: Math Score", students)
    assert "66.09" in first["answer"]
    assert first["visual_charts"] == []
    chart = ask("show me in chart format", students, first["prior_context"])
    spec = chart["visual_charts"][0]
    assert spec["title"] == "Cohort Average: Math Score"
    assert spec["series"][0]["values"] == pytest.approx([66.09])
    assert chart["evidence"]["coverage"]["used_rows"] == 1000
    changed = students.copy()
    changed["Math Score"] = 50
    assert ask("show it as a chart", changed, first["prior_context"])["visual_charts"][0]["series"][0]["values"] == [50]


@pytest.mark.unit
def test_old_council_context_uses_question_not_model_numbers(students):
    result = ask("show me in chart format", students, {
        "sheet_id": 7, "last_query": "display me Cohort Average: Math Score",
        "last_answer": "The mean is 9999; range 0-100."})
    assert result["visual_charts"][0]["series"][0]["values"] == pytest.approx([66.09])


@pytest.mark.unit
def test_repeat_chart_request_recovers_existing_ascii_conversation(students):
    prior = {"sheet_id": 7, "last_query": "show me in chart format again",
             "last_answer": "Here is the chart: ┌ Cohort Average: Math Score ┐ 9999 (Range: 0-100)",
             "history": [{"role": "user", "content": "show me in chart format"},
                         {"role": "user", "content": "show me in chart format again"}]}
    result = ask("show me in chart format again", students, prior)
    assert result["visual_charts"][0]["series"][0]["values"] == pytest.approx([66.09])
    repeated = ask("show me in chart format again", students, result["prior_context"])
    assert repeated["visual_charts"] == result["visual_charts"]


@pytest.mark.unit
def test_grouped_chart_and_retype_preserve_operation(students):
    result = ask("show average Math Score by Gender in a bar chart", students)
    spec = result["visual_charts"][0]
    assert spec["categories"] == ["Female", "Male"]
    assert spec["series"][0]["values"] == pytest.approx([66, 66.18])
    followup = ask("switch to a column chart", students, result["prior_context"])
    assert followup["visual_charts"][0]["chart_type"] == "column"
    assert followup["visual_charts"][0]["series"] == spec["series"]
    donut = ask("show it as a donut chart", students, result["prior_context"])
    assert donut["visual_charts"][0]["chart_type"] == "bar"


@pytest.mark.unit
def test_sum_donut_and_numeric_header_normalization():
    frame = pd.DataFrame({"Sales_Amount": [100, 200, 300, 400], "Region": ["East", "West", "East", "West"]})
    result = ask("show total sales amount by Region as a donut chart", frame)
    assert result["visual_charts"][0]["chart_type"] == "donut"
    assert result["visual_charts"][0]["series"][0]["values"] == [400, 600]


@pytest.mark.unit
def test_missing_nonfinite_and_zero_are_not_fabricated():
    frame = pd.DataFrame({"Math Score": [0, 60, 90, None, "bad", float("inf")]})
    result = ask("show average Math Score as a chart", frame)
    assert result["visual_charts"][0]["series"][0]["values"] == [50]
    assert result["evidence"]["coverage"] == {"total_rows": 6, "used_rows": 3, "missing_rows": 3}
    frame["Math Score"] = [None] * 6
    result = ask("show average Math Score as a chart", frame)
    assert not result["visual_charts"]


@pytest.mark.unit
def test_unknown_metric_and_scope_switch_require_clarification(students):
    first = ask("average Math Score", students)
    for query, prior, sheet in [("show me a chart", None, 7),
                                ("show me a chart", first["prior_context"], 8),
                                ("show Math Score and Reading Score as a chart", None, 7),
                                ("show average Student ID as a chart", None, 7)]:
        result = ask(query, students, prior, sheet)
        assert result["status"] == "clarification_required"
        assert not result["visual_charts"]


@pytest.mark.unit
def test_filters_are_never_silently_removed(students):
    assert ask("average Math Score for Female only", students) is None
    for query in ["show average Math Score for Female only as a chart",
                  "show average Math Score above 60 as a chart"]:
        result = ask(query, students)
        assert result["status"] == "clarification_required"
        assert not result["visual_charts"]
    prior = {"sheet_id": 7, "last_query": "average Math Score for Female only"}
    assert ask("show me a chart", students, prior)["status"] == "clarification_required"


@pytest.mark.integration
@pytest.mark.parametrize("engine", ["war_room", "auto", "generic", "legacy"])
def test_json_and_sse_chart_followup_bypass_llm(monkeypatch, students, engine):
    monkeypatch.setattr(copilot, "_load_active_sheet_dataframe", lambda *args: (students, "Student Academic Achievement", None, 7))
    def unexpected(*args, **kwargs):
        raise AssertionError("A chart request must not reach model generation")
    monkeypatch.setattr(copilot.UnionWarRoomEngine, "stream_war_room_deliberation", unexpected)
    monkeypatch.setattr(copilot, "stream_copilot_generator", unexpected)
    monkeypatch.setattr(copilot, "query_copilot", unexpected)
    client = TestClient(app)
    first = client.post("/api/copilot/query", json={"query": "display me Cohort Average: Math Score", "engine": engine, "sheet_id": 7}).json()
    payload = {"query": "show me in chart format", "prior_context": first["prior_context"], "engine": engine, "sheet_id": 7}
    synchronous = client.post("/api/copilot/query", json=payload)
    streaming = client.post("/api/copilot/query/stream", json=payload)
    assert synchronous.status_code == streaming.status_code == 200
    done = [event for event in streaming.text.split("\n\n") if event.startswith("event: done")]
    assert len(done) == 1
    result = json.loads(done[0].split("data: ", 1)[1])
    assert result["visual_charts"] == synchronous.json()["visual_charts"]
    assert result["visual_charts"][0]["series"][0]["values"] == pytest.approx([66.09])
    assert result["timings"]["llm_calls"] == 0


@pytest.mark.integration
def test_group_by_without_deck_is_chat_analytics():
    assert copilot.classify_analytical_intent("show average Math Score grouped by Gender as a bar chart") != "SLIDE_MUTATION"
    assert copilot.classify_analytical_intent("switch chart to column", {"deck_id": 42}) == "SLIDE_MUTATION"


@pytest.mark.unit
def test_categorical_entity_count_and_dashboard_recovery(students):
    """Verify that 'Students by Gender' draws a count distribution chart without requiring a continuous numeric measure."""
    result = ask("draw the chart based on Students by Gender", students)
    assert result["status"] == "success"
    assert len(result["visual_charts"]) == 1
    spec = result["visual_charts"][0]
    assert "Gender" in spec["title"]
    assert set(spec["categories"]) == {"Female", "Male"}
    assert spec["series"][0]["values"] == [500.0, 500.0]

    # Verify recovery when user says "the chart is available on dashboard"
    followup = ask("the chart is availabe on dashboard", students, result["prior_context"])
    assert followup["status"] == "success"
    assert len(followup["visual_charts"]) == 1
    assert set(followup["visual_charts"][0]["categories"]) == {"Female", "Male"}


@pytest.mark.unit
def test_draw_chart_based_on_cohort_average(students):
    """Verify natural phrasing 'draw the chart based on Cohort Average: Math Score' succeeds directly."""
    result = ask("draw the chart based on Cohort Average: Math Score", students)
    assert result["status"] == "success"
    assert len(result["visual_charts"]) == 1
    spec = result["visual_charts"][0]
    assert spec["title"] == "Cohort Average: Math Score"
    assert spec["series"][0]["values"] == pytest.approx([66.09])


