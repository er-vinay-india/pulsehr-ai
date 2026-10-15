"""Attendance/leave chart requests must deliver source-backed series, not rankings."""
import json

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.routers import copilot
from app.services.copilot.chat_visuals import answer_chat_visual

pytestmark = pytest.mark.copilot
QUERY = "give me chart of How do attendance and leave records balance?"


@pytest.fixture
def attendance():
    return pd.DataFrame({
        "Department": ["Engineering", "Operations"],
        "Total Attendance": [18, 14],
        "Approved Leaves": [2, 6],
        "Final Attendance": [16, 8],
    })


def ask(frame, query=QUERY, prior=None, sheet=7):
    return answer_chat_visual(query, frame, "Sheet1", sheet, 3, prior)


@pytest.mark.unit
def test_balance_request_compares_recorded_totals_and_recomputes_followups(attendance):
    result = ask(attendance)
    assert result["status"] == "success"
    chart = result["visual_charts"][0]
    assert chart["categories"] == ["Total Attendance", "Approved Leaves", "Final Attendance"]
    assert chart["series"][0]["values"] == [32, 8, 24]
    assert chart["unit"] == "days"
    assert "Lowest" not in result["answer"]
    assert result["evidence"]["source_columns"] == chart["categories"]
    changed = attendance.copy()
    changed["Final Attendance"] = [10, 8]
    followup = ask(changed, "show it as a bar chart", result["prior_context"])
    assert followup["visual_charts"][0]["series"][0]["values"] == [32, 8, 18]
    assert followup["visual_charts"][0]["chart_type"] == "bar"
    assert ask(changed, "show it as a chart", result["prior_context"], sheet=8)["status"] == "clarification_required"


@pytest.mark.unit
def test_comparison_excludes_incomplete_nonfinite_and_negative_rows(attendance):
    invalid = pd.DataFrame({"Total Attendance": [None, float("inf"), -2, 10],
                            "Approved Leaves": [1, 2, 3, "10%"],
                            "Final Attendance": [1, 2, 3, 9]})
    result = ask(pd.concat([attendance, invalid], ignore_index=True))
    assert result["visual_charts"][0]["series"][0]["values"] == [32, 8, 24]
    assert result["evidence"]["coverage"] == {"total_rows": 6, "used_rows": 2, "excluded_rows": 4}
    assert "4" in result["visual_charts"][0]["aggregation_disclosure"]
    assert ask(invalid)["status"] == "no_data"


@pytest.mark.unit
def test_optional_final_attendance_is_not_invented_or_added_to_a_pie(attendance):
    result = ask(attendance.drop(columns="Final Attendance"), "draw a pie chart comparing attendance and leave")
    assert result["visual_charts"][0]["categories"] == ["Total Attendance", "Approved Leaves"]
    assert result["visual_charts"][0]["series"][0]["values"] == [32, 8]
    assert result["visual_charts"][0]["chart_type"] == "column"
    assert "overlap" in result["answer"]


@pytest.mark.unit
@pytest.mark.parametrize("suffix", [" for Engineering only", " in July", " by Department", " above 10", " on average"])
def test_comparison_never_discards_filters_periods_grouping_or_operations(attendance, suffix):
    result = ask(attendance, QUERY + suffix)
    assert result["status"] == "clarification_required"
    assert result["visual_charts"] == []


@pytest.mark.unit
def test_missing_or_ambiguous_day_columns_require_clarification(attendance):
    for frame in [attendance.rename(columns={"Approved Leaves": "Leave Rate"}),
                  attendance.assign(Attendance_Days=[18, 14]),
                  attendance.rename(columns={"Total Attendance": "Attendance Rate", "Final Attendance": "Attendance Percentage"})]:
        result = ask(frame)
        assert result["status"] == "clarification_required"
        assert result["visual_charts"] == []


@pytest.mark.unit
def test_shared_findings_cannot_replace_a_chart_request_with_a_leave_ranking(monkeypatch):
    from app.services.adaptive_dashboard import engine

    def unexpected(*args, **kwargs):
        pytest.fail("Chart request reached the text-only department finding shortcut")

    monkeypatch.setattr(engine, "run_adaptive_dashboard", unexpected)
    assert copilot._answer_from_shared_findings(QUERY, 7, "Sheet1") is None


@pytest.mark.integration
def test_greeting_then_balance_chart_has_same_payload_in_json_and_sse(monkeypatch, attendance):
    from app.services.copilot import council_coordinator

    monkeypatch.setattr(copilot, "_load_active_sheet_dataframe", lambda *args: (attendance, "Sheet1", None, 7))
    def unexpected(*args, **kwargs):
        pytest.fail("A supported chart request must not reach model generation")
    monkeypatch.setattr(council_coordinator, "query_copilot", unexpected)
    monkeypatch.setattr(council_coordinator, "stream_copilot_generator", unexpected)
    client = TestClient(app)
    greeting = client.post("/api/copilot/query", json={"query": "hi", "sheet_id": 7}).json()
    payload = {"query": QUERY, "sheet_id": 7, "engine": "war_room", "prior_context": greeting.get("prior_context")}
    result = client.post("/api/copilot/query", json=payload).json()
    streaming = client.post("/api/copilot/query/stream", json=payload)
    done = [event for event in streaming.text.split("\n\n") if event.startswith("event: done")]
    assert len(done) == 1
    streamed = json.loads(done[0].split("data: ", 1)[1])
    assert result["status"] == streamed["status"] == "success"
    assert len(result["visual_charts"]) == 1
    assert result["visual_charts"] == streamed["visual_charts"]
    assert streamed["coordinator"]["verified_delivery"] is True
    assert streamed["visual_charts"][0]["series"][0]["values"] == [32, 8, 24]
