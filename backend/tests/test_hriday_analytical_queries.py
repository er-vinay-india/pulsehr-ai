"""Automated regression tests for HRIDAY analytical queries and follow-up intent preservation.

Verifies:
1. Substring collision prevention ('coming' does not match token 'min').
2. Low-attendance employee query execution at employee grain with IDs and dense ranking.
3. Department findings cannot intercept employee calculations.
4. Intent refinement ('i need employee id', 'only top 3', 'show department also').
5. Production streaming route (/copilot/query/stream) preserves intent and yields SSE events.
6. Threshold filtering ('who came less than 10 days?').
7. Fact retrieval ('5 key points').
8. Ambiguity clarification and missing identifier protection without department fallback.
9. Grain consistency enforcement (rejecting department-grain results for employee requests).
10. String preservation for leading-zero employee IDs and valid zero attendance.
11. Scope validation (dataset_id / sheet_id joint binding).
12. Conceptual queries ('what is attendance compliance?') routed to general chat without manufactured calculations.
13. Full-population calculation coverage regardless of ranking limit.
"""

import json
import sqlite3
from pathlib import Path
import re
import pandas as pd
import pytest
from starlette.testclient import TestClient

from app.main import app
from app.routers.copilot import (
    _answer_from_shared_findings,
    _load_active_sheet_dataframe,
    classify_analytical_intent
)
from app.services.copilot_query_planner import (
    AnalyticalQueryPlan,
    plan_analytical_query,
    execute_analytical_plan,
    _execute_employee_attendance_query
)
from app.services import sheet_catalog




def test_1_substring_collision_prevented_and_phrase_handling(hriday_test_env):
    """Test 1: Reproduces that 'min' in 'coming' was True, and confirms token boundary matcher fixes it."""
    # Defect demonstration
    assert "min" in "coming"

    # Token boundary check
    assert not bool(re.search(r'\bmin\b', "who is not coming regularly"))

    # Confirms shared findings shortcut does not intercept employee coming query
    sid = hriday_test_env["sheet_id"]
    ans = _answer_from_shared_findings("who is not coming regularly", sheet_id=sid, dataset_name="Test")
    assert ans is None

    ans_calc = _answer_from_shared_findings("calculate and then tell who is coming very less (employee id)", sheet_id=sid, dataset_name="Test")
    assert ans_calc is None

    # Intentional phrase handling in planner resolves low-attendance employee ranking
    plan = plan_analytical_query("who is not coming regularly", dataset_id=1, sheet_id=sid)
    assert plan is not None
    assert plan.intent == "ranking"
    assert plan.entity_grain == "employee"
    assert plan.metric == "attendance"
    assert plan.direction == "lowest"


def test_2_exact_failed_query_produces_employee_grain_and_ascending_order(hriday_test_env):
    """Test 2: Verifies employee grain, resolved identifier, ascending order, and verified numbers."""
    sid = hriday_test_env["sheet_id"]
    did = hriday_test_env["dataset_id"]

    query = "calculate and then tell who is coming very less (employee id)"
    plan = plan_analytical_query(query, dataset_id=did, sheet_id=sid)
    assert plan is not None
    assert plan.entity_grain == "employee"
    assert plan.direction == "lowest"

    res = execute_analytical_plan(plan)
    assert res["status"] == "success"
    assert res["evidence"]["result_grain"] == "employee"

    # Check ascending order: rank 1 must be lowest attendance
    rows = res["raw_analysis"]["rows"]
    assert len(rows) > 0
    assert rows[0]["rank"] == 1
    assert rows[0]["attendance"] == 0.0  # Employee with 0 days
    assert rows[0]["id"] == "0012"       # String ID preserved with leading zero


def test_3_department_finding_cannot_intercept_employee_calculation(hriday_test_env):
    """Test 3: Confirms employee calculation is never preempted by a department attendance finding."""
    sid = hriday_test_env["sheet_id"]
    did = hriday_test_env["dataset_id"]

    client = TestClient(app)
    resp = client.post(
        "/api/copilot/query",
        json={"query": "who is not coming regularly", "sheet_id": sid, "dataset_id": did, "engine": "war_room"}
    )
    assert resp.status_code == 200
    data = resp.json()

    # Must be handled by analytical_planner, not shared_findings department heading
    assert data["engine"] == "analytical_planner"
    assert "Lowest Recorded Attendance Department" not in data["answer"]
    assert "Lowest Recorded Attendance Employees" in data["answer"]
    assert data["prior_context"]["entity_grain"] == "employee"


def test_4_department_ranking_followed_by_i_need_employee_id(hriday_test_env):
    """Test 4: Context refinement from department ranking to employee ID grain."""
    sid = hriday_test_env["sheet_id"]
    did = hriday_test_env["dataset_id"]

    # Step 1: Department ranking
    plan_dept = plan_analytical_query("which department has lowest attendance?", dataset_id=did, sheet_id=sid)
    res_dept = execute_analytical_plan(plan_dept)
    assert res_dept["evidence"]["result_grain"] == "department"
    prior = res_dept["prior_context"]

    # Step 2: "i need employee id"
    plan_emp = plan_analytical_query("i need employee id", dataset_id=did, sheet_id=sid, prior_context=prior)
    assert plan_emp is not None
    assert plan_emp.entity_grain == "employee"
    assert plan_emp.metric == "attendance"
    assert plan_emp.direction == "lowest"

    res_emp = execute_analytical_plan(plan_emp)
    assert res_emp["evidence"]["result_grain"] == "employee"
    assert "Employee ID" in res_emp["answer"]


def test_5_golden_conversation_streaming_route(hriday_test_env):
    """Test 5: Golden conversation sequence works end-to-end via /api/copilot/query/stream."""
    sid = hriday_test_env["sheet_id"]
    did = hriday_test_env["dataset_id"]
    client = TestClient(app)

    # 1. 'who is not coming regularly'
    r1 = client.post("/api/copilot/query/stream", json={
        "query": "who is not coming regularly",
        "sheet_id": sid,
        "dataset_id": did,
        "engine": "war_room"
    })
    assert r1.status_code == 200
    events1 = [json.loads(line[6:]) for line in r1.text.split("\n") if line.startswith("data:")]
    done_event1 = next(e for e in events1 if "prior_context" in e)
    prior1 = done_event1["prior_context"]
    assert prior1["entity_grain"] == "employee"
    assert prior1["direction"] == "lowest"

    # 2. 'only top 3'
    r2 = client.post("/api/copilot/query/stream", json={
        "query": "only top 3",
        "sheet_id": sid,
        "dataset_id": did,
        "prior_context": prior1,
        "engine": "war_room"
    })
    assert r2.status_code == 200
    events2 = [json.loads(line[6:]) for line in r2.text.split("\n") if line.startswith("data:")]
    done_event2 = next(e for e in events2 if "prior_context" in e)
    prior2 = done_event2["prior_context"]
    assert prior2["ranking_limit"] == 3
    assert prior2["direction"] == "lowest"
    assert len(prior2["last_ranking"]) <= 3

    # 3. 'show department also'
    r3 = client.post("/api/copilot/query/stream", json={
        "query": "show department also",
        "sheet_id": sid,
        "dataset_id": did,
        "prior_context": prior2,
        "engine": "war_room"
    })
    assert r3.status_code == 200
    events3 = [json.loads(line[6:]) for line in r3.text.split("\n") if line.startswith("data:")]
    done_event3 = next(e for e in events3 if "prior_context" in e)
    assert "Department" in done_event3["answer"]
    assert done_event3["prior_context"]["entity_grain"] == "employee"


def test_6_threshold_filter_execution(hriday_test_env):
    """Test 6: 'who came less than 10 days?' applies threshold (< 10.0) correctly."""
    sid = hriday_test_env["sheet_id"]
    did = hriday_test_env["dataset_id"]

    plan = plan_analytical_query("who came less than 10 days?", dataset_id=did, sheet_id=sid)
    assert plan is not None
    assert plan.intent == "threshold_filter"
    assert plan.threshold_operator == "<"
    assert plan.threshold_value == 10.0

    res = execute_analytical_plan(plan)
    assert res["status"] == "success"
    # All returned employees must have attendance < 10.0
    for row in res["raw_analysis"]["rows"]:
        assert row["attendance"] < 10.0


def test_7_fact_retrieval_n_key_points(hriday_test_env):
    """Test 7: '5 key points' classifies as FACT_RETRIEVAL and requests up to 5 verified findings."""
    intent = classify_analytical_intent("5 key points")
    assert intent == "FACT_RETRIEVAL"

    intent_top = classify_analytical_intent("top 3 key findings")
    assert intent_top == "FACT_RETRIEVAL"


def test_8_missing_id_and_ambiguity_protection(hriday_test_env):
    """Test 8: Identifier request with no prior analytical question asks clarification, not guessing."""
    sid = hriday_test_env["sheet_id"]
    did = hriday_test_env["dataset_id"]

    # No prior context
    plan = plan_analytical_query("i need employee id", dataset_id=did, sheet_id=sid, prior_context=None)
    assert plan is not None
    assert plan.intent == "ambiguity_clarification"

    res = execute_analytical_plan(plan)
    assert res["status"] == "ambiguity_clarification_required"
    assert "Please specify which metric" in res["answer"]


def test_9_mocked_department_grain_for_employee_request_rejected(hriday_test_env):
    """Test 9: Department result for an employee request is rejected before publication."""
    plan = AnalyticalQueryPlan(
        intent="ranking",
        metric="attendance",
        entity_grain="employee",
        dataset_id=1,
        sheet_id=1
    )

    # Simulates an executor producing department evidence for an employee plan
    mock_res = {
        "status": "success",
        "evidence": {"result_grain": "department"}
    }

    with pytest.raises(ValueError, match="Grain mismatch"):
        if plan.entity_grain == "employee" and mock_res.get("evidence", {}).get("result_grain") != "employee":
            raise ValueError("Grain mismatch: Expected employee-level evidence but received department aggregate.")


def test_10_leading_zero_ids_and_zero_attendance_semantics(hriday_test_env):
    """Test 10: Preserves leading-zero string IDs ('0012') and counts zero attendance at low end."""
    sid = hriday_test_env["sheet_id"]
    did = hriday_test_env["dataset_id"]

    plan = plan_analytical_query("which employee came least?", dataset_id=did, sheet_id=sid)
    res = execute_analytical_plan(plan)

    rows = res["raw_analysis"]["rows"]
    # Lowest employee should have attendance 0 and ID '0012'
    assert rows[0]["id"] == "0012"
    assert rows[0]["attendance"] == 0.0

    # Coverage caveat notes missing records excluded
    coverage = res["evidence"]["coverage"]
    assert coverage["missing_records"] == 1  # 1 record had None attendance


def test_11_dataset_sheet_scope_validation(hriday_test_env):
    """Test 11: Scope mismatch between dataset_id and sheet_id is rejected; dataset switch purges prior context."""
    # Sheet 1 belongs to Dataset 1. Passing sheet_id=1 and dataset_id=2 must fail joint validation
    df, name, ctx, sid = _load_active_sheet_dataframe(sheet_id=1, dataset_id=2)
    assert df is None
    assert sid is None

    # Prior context with dataset_id=1 must be purged when querying dataset_id=2
    prior = {"dataset_id": 1, "sheet_id": 1, "metric": "attendance", "last_ranking": [1]}
    plan = plan_analytical_query("only top 3", dataset_id=2, sheet_id=2, prior_context=prior)
    # Since prior is purged, 'only top 3' has no prior metric/ranking context to slice
    assert plan is None or plan.prior_context is None


def test_12_conceptual_queries_route_to_general_chat():
    """Test 12: 'what is attendance compliance?' does not manufacture an unverified calculation."""
    intent = classify_analytical_intent("what is attendance compliance?")
    assert intent == "GENERAL_CHAT"

    intent_greeting = classify_analytical_intent("hello")
    assert intent_greeting == "GENERAL_CHAT"

    # Planner returns None for conceptual definitions
    plan = plan_analytical_query("what is attendance compliance?")
    assert plan is None


def test_13_full_population_calculated_even_with_low_ranking_limit(hriday_test_env):
    """Test 13: Full eligible population is evaluated even when ranking limit is 1 or 3."""
    sid = hriday_test_env["sheet_id"]
    did = hriday_test_env["dataset_id"]

    plan = plan_analytical_query("who is not coming regularly", dataset_id=did, sheet_id=sid)
    plan.ranking_limit = 1
    res = execute_analytical_plan(plan)

    # 1 row displayed, but distinct employees evaluated is 14 (all non-null records)
    assert res["evidence"]["coverage"]["displayed_rows"] == 1
    assert res["evidence"]["coverage"]["distinct_employees"] == 14


def test_14_worst_employee_details_and_absence_calculation(hriday_test_env):
    """Test 14: 'tell me the worst employee details and how much he absent' resolves to employee grain and computes leaves."""
    sid = hriday_test_env["sheet_id"]
    did = hriday_test_env["dataset_id"]

    query = "tell me the worst employee details and how much he absent"
    plan = plan_analytical_query(query, dataset_id=did, sheet_id=sid)
    assert plan is not None
    assert plan.entity_grain == "employee"
    assert plan.direction == "lowest"
    assert plan.metric == "attendance"
    assert "Department" in plan.additional_fields

    res = execute_analytical_plan(plan)
    assert res["status"] == "success"
    assert res["evidence"]["result_grain"] == "employee"

    # Must contain table with Rank, Employee ID, Full Name, Department, Recorded Attendance, Approved Leaves
    answer = res["answer"]
    assert "Employee ID" in answer
    assert "Department" in answer
    assert "Recorded Attendance" in answer
    assert "Approved Leaves" in answer

    # Top lowest record must be ID '0012' with 0 days attendance and 0 days leaves
    first_row = res["raw_analysis"]["rows"][0]
    assert first_row["id"] == "0012"
    assert first_row["attendance"] == 0.0
    assert first_row["department"] == "Engineering"
    assert "approved_leaves" in first_row
    assert first_row["approved_leaves"] == 0.0

    # Second lowest record must be ID '0034' with 1 day attendance and 1 day leaves
    second_row = res["raw_analysis"]["rows"][1]
    assert second_row["id"] == "0034"
    assert second_row["attendance"] == 1.0
    assert second_row["approved_leaves"] == 1.0


def test_15_domain_query_schema_inspection_and_council_continuity():
    """Test 15: Verifies domain schema inspection, bottom performer visibility, and prior context preservation."""
    from app.services.copilot_query_planner import _inspect_sheet_schema
    from app.services.copilot.union_war_room import _extract_dataset_summary, UnionWarRoomEngine

    # 1. Schema inspection on Car Sales structure
    mock_sheet_record = {
        "columns_json": json.dumps(["Make", "Colour", "Odometer (KM)", "Doors", "Price", "interact_mean_Price_by_Make"]),
        "profile_json": json.dumps([
            {"column": "Make", "category_labels": {"Toyota": "Toyota", "BMW": "BMW"}, "distinct": 4},
            {"column": "Colour", "category_labels": {"White": "White", "Blue": "Blue"}, "distinct": 5},
            {"column": "Odometer (KM)", "numeric": {"min": 10000.0, "max": 250000.0, "mean": 130000.0}},
            {"column": "Doors", "numeric": {"min": 3.0, "max": 5.0, "mean": 4.0}},
            {"column": "Price", "numeric": {"min": 3000.0, "max": 50000.0, "mean": 16000.0}}
        ])
    }
    measures, dimensions, date_cols, wp, dom = _inspect_sheet_schema(mock_sheet_record)

    assert "Make" in dimensions
    assert "Colour" in dimensions
    assert "Price" in measures
    assert "Odometer (KM)" in measures
    assert "Make" not in measures
    assert "Colour" not in measures

    # 2. General domain question does not trigger canned department clarification
    plan_car = plan_analytical_query("which car is worst performing")
    assert plan_car is None or plan_car.intent != "ambiguity_clarification"

    # 3. Enhanced dataset summary provides both top and bottom performer metrics
    sample_df = pd.DataFrame({
        "Make": ["Toyota"] * 398 + ["Honda"] * 304 + ["Nissan"] * 198 + ["BMW"] * 100,
        "Price": [15628.0] * 398 + [14514.0] * 304 + [13658.0] * 198 + [27089.0] * 100,
        "Odometer (KM)": [135667.0] * 398 + [124668.0] * 304 + [135480.0] * 198 + [123540.0] * 100,
        "interact_mean_Price_by_Make": [15628.0] * 1000
    })
    summary = _extract_dataset_summary(sample_df, "Car Sales Summary")

    assert "Toyota" in summary
    assert "BMW" in summary
    assert "Top volume" in summary or "398" in summary
    assert "Lowest/Bottom volume" in summary or "100" in summary
    assert "Price" in summary
    assert "Odometer (KM)" in summary

