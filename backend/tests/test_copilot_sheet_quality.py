"""Regression: sheet quality questions must not inherit a prior score ranking."""
import json

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from app.core import config
from app.db.database import get_connection
from app.main import app
from app.routers import copilot
from app.services import copilot_query_planner as planner
from app.services.copilot.sheet_quality import missing_value_summary, is_missing_values_query
from app.services.sheet_catalog import read_sheets

pytestmark = pytest.mark.copilot


@pytest.fixture
def raw_sheet():
    path = config.UPLOADS_DIR / "students.csv"
    path.write_text("gender,math score,empty\nfemale,0,\n, ,\n\n")
    with get_connection() as conn:
        conn.execute("INSERT INTO dataset_uploads(id,filename,original_name,file_type) VALUES (1,'students.csv','Students.csv','csv')")
        conn.execute("INSERT INTO sheets(id,dataset_id,name,display_name,columns_json,profile_json,row_count) VALUES (7,1,'Sheet1','Students',?, '[]',2)",
                     (json.dumps(["gender", "math score", "interact_mean_math_score"]),))
        for index, record in enumerate([{"gender": "female", "math score": 0, "interact_mean_math_score": None},
                                        {"gender": None, "math score": None, "interact_mean_math_score": None}]):
            conn.execute("INSERT INTO sheet_rows(sheet_id,row_index,data_json) VALUES (7,?,?)", (index, json.dumps(record)))
    return path


@pytest.mark.unit
def test_real_nulls_are_counted_once_and_zero_false_are_populated():
    frame = pd.DataFrame({"Score": [0, None, pd.NA, float("nan"), "NA", "N/A", "  "],
                          "Group": ["", False, "female", "null", "male", "0", "x"]})
    summary = missing_value_summary(frame)
    assert summary["missing_cells"] == 5
    assert summary["rows_with_missing"] == 5
    assert summary["total_cells"] == 14


@pytest.mark.unit
def test_none_is_a_populated_test_preparation_category():
    frame = pd.DataFrame({"test preparation course": ["none", "none", "completed"], "math score": [0, 60, 90]})
    assert missing_value_summary(frame)["missing_cells"] == 0


@pytest.mark.unit
def test_quality_intent_accepts_user_typo_but_not_definitions():
    assert is_missing_values_query("how many missing values in the raw sheeet")
    assert is_missing_values_query("Which columns contain null values?")
    assert not is_missing_values_query("What are missing values?")
    assert not is_missing_values_query("show me the math score chart again")


@pytest.mark.integration
def test_raw_audit_preserves_empty_columns_and_records(raw_sheet):
    raw = read_sheets(raw_sheet, prune_empty=False)["Sheet1"]
    assert raw.shape == (3, 3)
    assert missing_value_summary(raw)["missing_cells"] == 7
    # Reconstructed logical table removes completely empty blank separator row
    assert read_sheets(raw_sheet)["Sheet1"].shape in ((1, 2), (2, 2))


@pytest.mark.integration
@pytest.mark.parametrize("engine", ["war_room", "auto", "generic", "legacy"])
def test_json_and_stream_missing_count_override_stale_metric(monkeypatch, raw_sheet, engine):
    def unexpected(*args, **kwargs):
        raise AssertionError("A source missing-value count must not execute a ranking or LLM")
    monkeypatch.setattr(copilot, "plan_analytical_query", unexpected)
    monkeypatch.setattr(copilot, "execute_analytical_plan", unexpected)
    client = TestClient(app)
    query = "how many missing values in the raw sheeet"
    request = {"query": query, "engine": engine, "sheet_id": 7,
               "prior_context": {"metric": "math score", "dimension": "gender", "ranking_limit": 1,
                                 "sheet_id": 7, "last_ranking": [{"group": "female", "value": 63.63}]}}
    assert copilot.classify_analytical_intent(query, request["prior_context"]) == "SHEET_DATA_QUALITY"
    json_result = client.post("/api/copilot/query", json=request)
    stream_result = client.post("/api/copilot/query/stream", json=request)
    assert json_result.status_code == stream_result.status_code == 200
    done = next(event for event in stream_result.text.split("\n\n") if event.startswith("event: done"))
    result = json.loads(done.split("data: ", 1)[1])
    assert result["data_quality"] == json_result.json()["data_quality"]
    assert result["data_quality"]["missing_cells"] == 7
    assert result["data_quality"]["columns"] == 3
    assert result["engine"] == "sheet_quality"
    assert result["timings"]["llm_calls"] == 0
    assert "metric" not in result["prior_context"]
    assert "gender math score Breakdown" not in result["answer"]


@pytest.mark.integration
def test_generic_endpoint_column_count_and_missing_source(raw_sheet):
    client = TestClient(app)
    result = client.post("/api/copilot/generic", json={"query": "How many missing values in math score?", "sheet_id": 7}).json()
    assert result["data_quality"]["missing_cells"] == 2
    assert result["data_quality"]["columns"] == 1
    rows = client.post("/api/copilot/query", json={"query": "How many rows have missing values?", "sheet_id": 7}).json()
    assert "**3 rows with missing values**" in rows["answer"]
    empty = client.post("/api/copilot/query", json={"query": "How many empty rows?", "sheet_id": 7}).json()
    assert "**2 completely empty rows**" in empty["answer"]
    assert empty["data_quality"]["columns"] == 3
    column = client.post("/api/copilot/query", json={"query": "How many missing values in the empty column?", "sheet_id": 7}).json()
    assert column["data_quality"]["missing_cells"] == 3
    assert column["data_quality"]["columns"] == 1
    filtered = client.post("/api/copilot/query", json={"query": "How many missing values for female only?", "sheet_id": 7}).json()
    assert filtered["status"] == "clarification_required"
    raw_sheet.unlink()
    result = client.post("/api/copilot/query", json={"query": "How many missing values in the raw sheet?", "sheet_id": 7}).json()
    assert result["status"] == "source_unavailable"
    assert result["data_quality"] is None


@pytest.mark.integration
def test_prior_metric_cannot_make_unrelated_questions_rankings(monkeypatch, raw_sheet):
    def unexpected(*args, **kwargs):
        raise AssertionError("Unrelated questions must not invoke the ranking planner's LLM fallback")
    monkeypatch.setattr(planner, "plan_with_council_qwen", unexpected)
    context = {"metric": "math score", "dimension": "gender", "sheet_id": 7}
    assert planner.plan_analytical_query("How many missing values in the raw sheet?", sheet_id=7, prior_context=context) is None
    assert planner.plan_analytical_query("What is the uploaded file name?", sheet_id=7, prior_context=context) is None
    ranking = planner.plan_analytical_query("Which gender has the lowest math score?", sheet_id=7, prior_context=context)
    assert ranking.intent == "ranking"
    assert ranking.metric == "math score"
