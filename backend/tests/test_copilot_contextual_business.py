import json
import sqlite3
from pathlib import Path

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services import copilot_tools as tools
from app.services import copilot_query_planner as planner
from app.services import sheet_catalog, ai_copilot


@pytest.fixture
def business_env(tmp_path, monkeypatch):
    db_path = tmp_path / "business_test.db"

    def connection():
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        return conn

    conn = connection()
    conn.executescript((Path(__file__).parents[1] / "app/db/schema.sql").read_text())

    # Dataset 1: Workforce Operations (Attendance & Overtime)
    conn.execute(
        "INSERT INTO dataset_uploads(id, filename, original_name, file_type) VALUES (1, 'workforce.csv', 'workforce.csv', 'csv')"
    )
    # Dataset 2: Retail Commercial Operations
    conn.execute(
        "INSERT INTO dataset_uploads(id, filename, original_name, file_type) VALUES (2, 'retail.csv', 'retail.csv', 'csv')"
    )
    conn.commit()
    conn.close()

    # Generate workforce records: Support has low attendance (80%) and high overtime (15 hrs)
    # Sales has high attendance (96%) and low overtime (2 hrs)
    # Engineering has medium attendance (90%) and medium overtime (6 hrs)
    records_wf = []
    for _ in range(30):
        records_wf.append({"Department": "Support", "attendance_rate": 80.0, "overtime_hours": 15.0})
    for _ in range(30):
        records_wf.append({"Department": "Sales", "attendance_rate": 96.0, "overtime_hours": 2.0})
    for _ in range(30):
        records_wf.append({"Department": "Engineering", "attendance_rate": 90.0, "overtime_hours": 6.0})

    df_wf = pd.DataFrame(records_wf)
    df_wf.to_csv(tmp_path / "workforce.csv", index=False)

    # Generate retail records
    df_ret = pd.DataFrame({
        "Store": ["Store A"] * 20 + ["Store B"] * 20,
        "weekly_sales": [50000.0] * 20 + [25000.0] * 20,
        "fuel_price": [3.45] * 40
    })
    df_ret.to_csv(tmp_path / "retail.csv", index=False)

    conn = connection()
    sheet_catalog.insert_sheets(
        conn,
        1,
        sheet_catalog.prepare_sheets(sheet_catalog.read_sheets(tmp_path / "workforce.csv"), "workforce.csv", embed=False)
    )
    sheet_catalog.insert_sheets(
        conn,
        2,
        sheet_catalog.prepare_sheets(sheet_catalog.read_sheets(tmp_path / "retail.csv"), "retail.csv", embed=False)
    )
    conn.commit()
    conn.close()

    monkeypatch.setattr(sheet_catalog, "get_connection", connection)
    monkeypatch.setattr(tools, "get_connection", connection)
    monkeypatch.setattr(planner, "get_connection", connection)
    monkeypatch.setattr(ai_copilot, "get_connection", connection)
    monkeypatch.setattr(tools.config, "UPLOADS_DIR", tmp_path)

    return {"db_path": db_path, "connection": connection}


def test_3_good_points_resolves_directly_without_asking_columns(business_env):
    """'Give me 3 good points' resolves positive findings directly from the server brief."""
    conn = business_env["connection"]()
    plan = planner.plan_analytical_query("give me 3 good points", dataset_id=1, conn=conn)
    assert plan is not None
    assert plan.intent == "summary_positives"
    assert plan.ranking_limit == 3

    res = planner.execute_analytical_plan(plan, conn=conn)
    assert res["status"] == "success"
    assert "Executive Overview: Verified Positive Findings" in res["answer"]
    # Evidence must contain snapshot_hash
    assert "snapshot_hash" in res["evidence"]
    assert res["evidence"]["positives_returned"] > 0
    # Prior context must be returned for follow-ups
    assert "prior_context" in res
    assert res["prior_context"]["dataset_id"] == 1
    assert res["prior_context"]["last_finding"] is not None
    conn.close()


def test_followup_why_refers_to_preceding_finding_with_non_causal_disclaimer(business_env):
    """'Why?' refers to preceding finding and strictly refuses causal inference."""
    conn = business_env["connection"]()
    plan_pos = planner.plan_analytical_query("give me 3 good points", dataset_id=1, conn=conn)
    res_pos = planner.execute_analytical_plan(plan_pos, conn=conn)
    prior_ctx = res_pos["prior_context"]

    # User immediately follows up with "why?"
    plan_why = planner.plan_analytical_query("why?", dataset_id=1, prior_context=prior_ctx, conn=conn)
    assert plan_why is not None
    assert plan_why.intent == "followup_why"

    res_why = planner.execute_analytical_plan(plan_why, conn=conn)
    assert res_why["status"] == "success"
    assert "Analytical Context & Non-Causal Explanation" in res_why["answer"]
    # Must refuse causal inference explicitly
    assert "Refusal of Causal Inference" in res_why["answer"]
    assert "strictly refuses unverified causal claims" in res_why["answer"]
    conn.close()


def test_worst_department_uses_polarity_and_identifies_overtime_worst(business_env):
    """'which department is worst?' for overtime sorts highest because higher is worse."""
    conn = business_env["connection"]()
    # Establish context that we are discussing overtime
    prior_ctx = {"dataset_id": 1, "metric": "overtime_hours", "dimension": "Department"}

    plan = planner.plan_analytical_query("which department is worst?", dataset_id=1, prior_context=prior_ctx, conn=conn)
    assert plan is not None
    assert plan.intent == "ranking"
    # Overtime: higher is worse -> direction should be 'highest'
    assert plan.direction == "highest"
    assert plan.metric == "overtime_hours"

    res = planner.execute_analytical_plan(plan, conn=conn)
    assert res["status"] == "success"
    # Support has 15.0 hrs overtime, so Support must be the highest/worst
    assert "Support" in res["answer"]
    assert "15.00" in res["answer"]
    conn.close()


def test_worst_department_without_metric_triggers_focused_clarification(business_env):
    """'which department is worst?' without metric in query or prior context asks ONE focused clarification question."""
    conn = business_env["connection"]()
    plan = planner.plan_analytical_query("which department is worst?", dataset_id=1, prior_context=None, conn=conn)
    assert plan is not None
    assert plan.intent == "ambiguity_clarification"
    assert plan.clarification_question is not None
    assert "specify which metric you would like to evaluate" in plan.clarification_question

    res = planner.execute_analytical_plan(plan, conn=conn)
    assert res["status"] == "ambiguity_clarification_required"
    assert "Clarification Required: Metric Specification" in res["answer"]
    conn.close()


def test_switching_datasets_clears_prior_context(business_env):
    """Switching dataset_id from 1 to 2 purges prior context so findings never leak."""
    conn = business_env["connection"]()
    prior_ctx = {
        "dataset_id": 1,
        "sheet_id": 1,
        "metric": "overtime_hours",
        "last_finding": {"title": "Support overtime is high"}
    }

    # Query on dataset 2 with prior context from dataset 1:
    # "which department is worst?" on dataset 2 should NOT inherit overtime_hours from dataset 1!
    plan = planner.plan_analytical_query("which department is worst?", dataset_id=2, prior_context=prior_ctx, conn=conn)
    # Since dataset 1 context was purged, this is now an ambiguous query on dataset 2!
    assert plan is not None
    assert plan.intent == "ambiguity_clarification"
    conn.close()


def test_honest_limitations_when_fewer_positives_than_requested(business_env):
    """If user asks for 5 good points but fewer exist, return supported count and explain why honestly."""
    conn = business_env["connection"]()
    plan = planner.plan_analytical_query("give me 5 good points", dataset_id=1, conn=conn)
    assert plan.ranking_limit == 5

    res = planner.execute_analytical_plan(plan, conn=conn)
    assert res["status"] == "success"
    if res["evidence"]["positives_returned"] < 5:
        assert "Honest Limitation" in res["answer"]
    conn.close()


def test_copilot_api_endpoint_flow(business_env):
    """End-to-end test of /api/copilot/query with prior context and decision brief integration."""
    client = TestClient(app)

    # 1. Ask for 3 good points
    res1 = client.post("/api/copilot/query", json={"query": "give me 3 good points", "dataset_id": 1})
    assert res1.status_code == 200
    data1 = res1.json()
    assert "Verified Positive Findings" in data1["answer"]
    assert "prior_context" in data1
    p_ctx = data1["prior_context"]

    # 2. Ask "why?" passing prior_context
    res2 = client.post("/api/copilot/query", json={"query": "why?", "dataset_id": 1, "prior_context": p_ctx})
    assert res2.status_code == 200
    data2 = res2.json()
    assert "Non-Causal Explanation" in data2["answer"]
    assert "Refusal of Causal Inference" in data2["answer"]
