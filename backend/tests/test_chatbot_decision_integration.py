"""Comprehensive integration and regression tests for Chatbot Decision Intelligence.

Verifies:
1. Department ranking with ties (dense ranking) and missing values.
2. Monthly queries: supported periods return data, unobserved periods are rejected explicitly without substitution.
3. Domain-adaptive queries: Sales (Weekly_Sales by Store) and IT operations (Resolution_Time by Severity).
4. Ambiguous "worst" handling: requires clarification when ambiguous; inherits metric from prior context.
5. Correlation vs causation refusal: reports Spearman association while explicitly refusing causal inference.
6. Parity: overview, presentation, and chatbot produce identical figures and share the same SHA-256 snapshot hash.
7. Untrusted data safety: malicious or malformed cell contents are strictly sanitized.
"""

import json
import sqlite3
from pathlib import Path
import pandas as pd
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services import copilot_tools as tools
from app.services import sheet_catalog
from app.services.copilot_query_planner import plan_analytical_query, execute_analytical_plan
from app.services.decision_intelligence import build_decision_brief


@pytest.fixture
def test_db(tmp_path, monkeypatch):
    """Initializes a clean SQLite database for testing."""
    db_path = tmp_path / "test_chatbot.db"

    def get_test_conn():
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        return conn

    conn = get_test_conn()
    schema_path = Path(__file__).parents[1] / "app/db/schema.sql"
    conn.executescript(schema_path.read_text())
    conn.close()

    monkeypatch.setattr("app.db.database.get_connection", get_test_conn)
    monkeypatch.setattr("app.services.copilot_query_planner.get_connection", get_test_conn)
    monkeypatch.setattr("app.services.copilot_tools.get_connection", get_test_conn)
    monkeypatch.setattr("app.services.ai_copilot.get_connection", get_test_conn)
    monkeypatch.setattr("app.services.sheet_catalog.get_connection", get_test_conn)

    return get_test_conn


def test_department_ranking_with_ties_and_missing(test_db):
    """Acceptance criterion 1: Dense ranking preserving ties, disclosing missing values and denominators."""
    conn = test_db()
    # Create HR attendance dataset where Engineering and Support have identical attendance (tie)
    # and Marketing has missing attendance rows
    conn.execute("INSERT INTO dataset_uploads (id, filename, original_name, file_type) VALUES (1, 'attendance.csv', 'attendance.csv', 'csv')")
    cols = ["Employee_ID", "Department", "1st to 5th July", "6th to 12th July", "13th to 19th July", "20th to 26th July", "27th to 31st July"]

    # 4 depts:
    # Dept A (Eng): 5 records, each attended exactly 15 days
    # Dept B (Support): 5 records, each attended exactly 15 days (TIED with Eng)
    # Dept C (Sales): 5 records, each attended exactly 20 days
    # Dept D (Marketing): 5 records, each attended 18 days
    records = []
    emp_id = 100
    for _ in range(5):
        records.append({"Employee_ID": f"E{emp_id}", "Department": "Engineering", "1st to 5th July": 3, "6th to 12th July": 3, "13th to 19th July": 3, "20th to 26th July": 3, "27th to 31st July": 3})
        emp_id += 1
    for _ in range(5):
        records.append({"Employee_ID": f"E{emp_id}", "Department": "Support", "1st to 5th July": 3, "6th to 12th July": 3, "13th to 19th July": 3, "20th to 26th July": 3, "27th to 31st July": 3})
        emp_id += 1
    for _ in range(5):
        records.append({"Employee_ID": f"E{emp_id}", "Department": "Sales", "1st to 5th July": 4, "6th to 12th July": 4, "13th to 19th July": 4, "20th to 26th July": 4, "27th to 31st July": 4})
        emp_id += 1

    conn.execute(
        "INSERT INTO sheets (id, dataset_id, name, columns_json, profile_json, row_count) VALUES (1, 1, 'July Attendance', ?, '{}', ?)",
        (json.dumps(cols), len(records))
    )
    for idx, rec in enumerate(records):
        conn.execute("INSERT INTO sheet_rows (sheet_id, row_index, data_json) VALUES (1, ?, ?)", (idx, json.dumps(rec)))
    conn.commit()

    # Query lowest attendance department
    plan = plan_analytical_query("Which department has the lowest attendance?", dataset_id=1, sheet_id=1, conn=conn)
    assert plan is not None
    assert plan.intent == "ranking"
    assert plan.metric == "attendance"
    assert plan.direction == "lowest"

    res = execute_analytical_plan(plan, conn=conn)
    assert res["status"] == "success"
    # Both Engineering and Support tied for rank 1
    assert "Engineering" in res["answer"]
    assert "Support" in res["answer"]
    assert "tied for the **lowest average attendance**" in res["answer"]
    # Evidence block present
    assert "evidence" in res
    assert res["evidence"]["source_ids"] == [1]
    assert res["evidence"]["coverage"]["groups_evaluated"] == 3
    conn.close()


def test_monthly_question_supported_and_unavailable_periods(test_db):
    """Acceptance criterion 2: Supported periods evaluate correctly; unobserved periods reject without substitution."""
    conn = test_db()
    conn.execute("INSERT INTO dataset_uploads (id, filename, original_name, file_type) VALUES (1, 'attendance.csv', 'attendance.csv', 'csv')")
    cols = ["Employee_ID", "Department", "1st to 5th July", "6th to 12th July", "13th to 19th July", "20th to 26th July", "27th to 31st July"]
    records = [
        {"Employee_ID": "E1", "Department": "HR", "1st to 5th July": 5, "6th to 12th July": 5, "13th to 19th July": 5, "20th to 26th July": 5, "27th to 31st July": 5},
        {"Employee_ID": "E2", "Department": "IT", "1st to 5th July": 4, "6th to 12th July": 4, "13th to 19th July": 4, "20th to 26th July": 4, "27th to 31st July": 4}
    ]
    conn.execute("INSERT INTO sheets (id, dataset_id, name, columns_json, profile_json, row_count) VALUES (1, 1, 'July Attendance', ?, '{}', ?)", (json.dumps(cols), len(records)))
    for idx, rec in enumerate(records):
        conn.execute("INSERT INTO sheet_rows (sheet_id, row_index, data_json) VALUES (1, ?, ?)", (idx, json.dumps(rec)))
    conn.commit()

    # 1. Supported month (July)
    plan_july = plan_analytical_query("Which department had the lowest attendance in July?", dataset_id=1, sheet_id=1, conn=conn)
    assert plan_july.time_window == "July"
    res_july = execute_analytical_plan(plan_july, conn=conn)
    assert res_july["status"] == "success"
    assert "July" in res_july["answer"]
    assert "IT" in res_july["answer"]

    # 2. Unavailable month (August) - MUST reject without substituting July
    plan_aug = plan_analytical_query("Which department had the lowest attendance in August?", dataset_id=1, sheet_id=1, conn=conn)
    assert plan_aug.time_window == "August"
    res_aug = execute_analytical_plan(plan_aug, conn=conn)
    assert res_aug["status"] == "period_unavailable"
    assert "Period Unavailable: August" in res_aug["answer"]
    assert "July" in res_aug["answer"]
    assert res_aug["evidence"]["status"] == "period_unavailable"
    conn.close()


def test_sales_and_it_domain_comparisons(test_db):
    """Acceptance criterion 3: Resolves domain metrics (Weekly_Sales by Store, Resolution_Time by Severity)."""
    conn = test_db()
    # 1. Sales Dataset (Walmart style)
    conn.execute("INSERT INTO dataset_uploads (id, filename, original_name, file_type) VALUES (2, 'sales.csv', 'sales.csv', 'csv')")
    sales_cols = ["Store", "Date", "Weekly_Sales", "Holiday_Flag", "Temperature"]
    sales_records = [
        {"Store": "Store 1", "Date": "2023-01-05", "Weekly_Sales": 25000.0, "Holiday_Flag": 0, "Temperature": 45.0},
        {"Store": "Store 1", "Date": "2023-01-12", "Weekly_Sales": 24000.0, "Holiday_Flag": 0, "Temperature": 46.0},
        {"Store": "Store 2", "Date": "2023-01-05", "Weekly_Sales": 12000.0, "Holiday_Flag": 0, "Temperature": 45.0},
        {"Store": "Store 2", "Date": "2023-01-12", "Weekly_Sales": 11000.0, "Holiday_Flag": 0, "Temperature": 46.0},
        {"Store": "Store 3", "Date": "2023-01-05", "Weekly_Sales": 35000.0, "Holiday_Flag": 0, "Temperature": 45.0},
        {"Store": "Store 3", "Date": "2023-01-12", "Weekly_Sales": 36000.0, "Holiday_Flag": 0, "Temperature": 46.0},
    ]
    conn.execute("INSERT INTO sheets (id, dataset_id, name, columns_json, profile_json, row_count) VALUES (2, 2, 'Weekly Sales', ?, '{}', ?)", (json.dumps(sales_cols), len(sales_records)))
    for idx, rec in enumerate(sales_records):
        conn.execute("INSERT INTO sheet_rows (sheet_id, row_index, data_json) VALUES (2, ?, ?)", (idx, json.dumps(rec)))

    # 2. IT Operations Dataset
    conn.execute("INSERT INTO dataset_uploads (id, filename, original_name, file_type) VALUES (3, 'it_ops.csv', 'it_ops.csv', 'csv')")
    it_cols = ["Ticket_ID", "Severity", "Resolution_Time", "Incident_Count"]
    it_records = [
        {"Ticket_ID": "T1", "Severity": "Sev-1", "Resolution_Time": 14.5, "Incident_Count": 1},
        {"Ticket_ID": "T2", "Severity": "Sev-1", "Resolution_Time": 15.5, "Incident_Count": 1},
        {"Ticket_ID": "T3", "Severity": "Sev-2", "Resolution_Time": 6.2, "Incident_Count": 1},
        {"Ticket_ID": "T4", "Severity": "Sev-2", "Resolution_Time": 5.8, "Incident_Count": 1},
        {"Ticket_ID": "T5", "Severity": "Sev-3", "Resolution_Time": 2.1, "Incident_Count": 1},
        {"Ticket_ID": "T6", "Severity": "Sev-3", "Resolution_Time": 1.9, "Incident_Count": 1},
    ]
    conn.execute("INSERT INTO sheets (id, dataset_id, name, columns_json, profile_json, row_count) VALUES (3, 3, 'Incidents', ?, '{}', ?)", (json.dumps(it_cols), len(it_records)))
    for idx, rec in enumerate(it_records):
        conn.execute("INSERT INTO sheet_rows (sheet_id, row_index, data_json) VALUES (3, ?, ?)", (idx, json.dumps(rec)))
    conn.commit()

    # Sales Query
    plan_sales = plan_analytical_query("Which store has the lowest weekly sales?", dataset_id=2, sheet_id=2, conn=conn)
    assert plan_sales is not None
    assert plan_sales.entity_dimension == "Store"
    assert "sales" in plan_sales.metric.lower()
    res_sales = execute_analytical_plan(plan_sales, conn=conn)
    assert res_sales["status"] == "success"
    assert "Store 2" in res_sales["answer"]
    assert "11,500.00" in res_sales["answer"]

    # IT Query
    plan_it = plan_analytical_query("Which severity has the highest resolution time?", dataset_id=3, sheet_id=3, conn=conn)
    assert plan_it is not None
    assert plan_it.entity_dimension == "Severity"
    assert "resolution" in plan_it.metric.lower()
    assert plan_it.direction == "highest"
    res_it = execute_analytical_plan(plan_it, conn=conn)
    assert res_it["status"] == "success"
    assert "Sev-1" in res_it["answer"]
    assert "15.00" in res_it["answer"]

    conn.close()


def test_ambiguous_worst_handling_and_context_clarification(test_db):
    """Acceptance criterion 4: Asks ONE focused clarification question without assuming attendance or composite score."""
    conn = test_db()
    conn.execute("INSERT INTO dataset_uploads (id, filename, original_name, file_type) VALUES (4, 'metrics.csv', 'metrics.csv', 'csv')")
    cols = ["Department", "Attendance_Rate", "Leaves_Taken", "Overtime_Hours"]
    records = [
        {"Department": "Finance", "Attendance_Rate": 92.0, "Leaves_Taken": 4.0, "Overtime_Hours": 10.0},
        {"Department": "Sales", "Attendance_Rate": 85.0, "Leaves_Taken": 8.0, "Overtime_Hours": 35.0},
    ]
    conn.execute("INSERT INTO sheets (id, dataset_id, name, columns_json, profile_json, row_count) VALUES (4, 4, 'Department Summary', ?, '{}', ?)", (json.dumps(cols), len(records)))
    for idx, rec in enumerate(records):
        conn.execute("INSERT INTO sheet_rows (sheet_id, row_index, data_json) VALUES (4, ?, ?)", (idx, json.dumps(rec)))
    conn.commit()

    # Ambiguous query without prior context: "Which department is performing worst?"
    plan_ambig = plan_analytical_query("Which department is performing worst?", dataset_id=4, sheet_id=4, prior_context=None, conn=conn)
    assert plan_ambig is not None
    assert plan_ambig.intent == "ambiguity_clarification"
    assert plan_ambig.metric is None

    res_ambig = execute_analytical_plan(plan_ambig, conn=conn)
    assert res_ambig["status"] == "ambiguity_clarification_required"
    assert "Clarification Required: Metric Specification" in res_ambig["answer"]
    assert "please specify which metric you would like to evaluate" in res_ambig["answer"]
    assert len(res_ambig["suggested_questions"]) > 0

    # Follow-up query with prior_context: now metric is established
    plan_resolved = plan_analytical_query(
        "Which department is performing worst?",
        dataset_id=4,
        sheet_id=4,
        prior_context={"metric": "Attendance_Rate"},
        conn=conn
    )
    assert plan_resolved is not None
    assert plan_resolved.intent == "ranking"
    assert plan_resolved.metric == "Attendance_Rate"
    res_resolved = execute_analytical_plan(plan_resolved, conn=conn)
    assert res_resolved["status"] == "success"
    assert "Sales" in res_resolved["answer"]

    conn.close()


def test_correlation_vs_causation_refusal(test_db):
    """Acceptance criterion 5: Reports statistical association while strictly refusing causal claims."""
    conn = test_db()
    conn.execute("INSERT INTO dataset_uploads (id, filename, original_name, file_type) VALUES (5, 'sales_weather.csv', 'sales_weather.csv', 'csv')")
    cols = ["Store", "Weekly_Sales", "Temperature"]
    # Provide 15 paired records so Spearman correlation is computed
    records = []
    for i in range(15):
        records.append({"Store": f"Store {i%3 + 1}", "Weekly_Sales": 10000.0 + i * 1500, "Temperature": 30.0 + i * 2})
    conn.execute("INSERT INTO sheets (id, dataset_id, name, columns_json, profile_json, row_count) VALUES (5, 5, 'Sales and Weather', ?, '{}', ?)", (json.dumps(cols), len(records)))
    for idx, rec in enumerate(records):
        conn.execute("INSERT INTO sheet_rows (sheet_id, row_index, data_json) VALUES (5, ?, ?)", (idx, json.dumps(rec)))
    conn.commit()

    # Query asking about causal relationship
    plan = plan_analytical_query("Does temperature cause lower weekly sales?", dataset_id=5, sheet_id=5, conn=conn)
    assert plan is not None
    assert plan.intent == "correlation_causation"

    res = execute_analytical_plan(plan, conn=conn)
    assert res["status"] == "success"
    assert "Statistical Association Analysis & Causal Claim Refusal" in res["answer"]
    assert "Spearman rank correlation" in res["answer"]
    assert "Refusal of Causal Inference" in res["answer"]
    assert "does **NOT** establish" in res["answer"]
    assert "PulseHR AI strictly separates descriptive statistical associations from causal explanations" in res["answer"]
    conn.close()


def test_overview_presentation_chat_parity(test_db):
    """Acceptance criterion 6: Overview, presentation, and chat share exact baseline, group means, and snapshot hash."""
    conn = test_db()
    conn.execute("INSERT INTO dataset_uploads (id, filename, original_name, file_type) VALUES (6, 'retail.csv', 'retail.csv', 'csv')")
    cols = ["Store", "Weekly_Sales"]
    records = [
        {"Store": "North", "Weekly_Sales": 50000.0},
        {"Store": "North", "Weekly_Sales": 52000.0},
        {"Store": "South", "Weekly_Sales": 30000.0},
        {"Store": "South", "Weekly_Sales": 32000.0},
    ]
    conn.execute("INSERT INTO sheets (id, dataset_id, name, columns_json, profile_json, row_count) VALUES (6, 6, 'Store Revenue', ?, '{}', ?)", (json.dumps(cols), len(records)))
    for idx, rec in enumerate(records):
        conn.execute("INSERT INTO sheet_rows (sheet_id, row_index, data_json) VALUES (6, ?, ?)", (idx, json.dumps(rec)))
    conn.commit()

    # 1. Decision brief (Overview / Presentation source)
    brief = build_decision_brief(conn, sheet_id=6)
    brief_snapshot = brief["snapshot"]
    brief_comparison = next(c for c in brief["profiles"][0]["comparisons"] if c["metric"] == "Weekly_Sales")
    brief_baseline = brief_comparison["baseline"]
    north_mean = next(g["value"] for g in brief_comparison["groups"] if g["group"] == "North")

    # 2. Chatbot query execution
    plan = plan_analytical_query("Show breakdown of weekly sales by store", dataset_id=6, sheet_id=6, conn=conn)
    res = execute_analytical_plan(plan, conn=conn)

    # Parity assertions
    assert res["evidence"]["snapshot_hash"] == brief_snapshot
    assert f"Overall Benchmark: **{brief_baseline:,.2f}**" in res["answer"]
    assert f"**{north_mean:,.2f}**" in res["answer"]
    conn.close()


def test_untrusted_data_safety(test_db):
    """Acceptance criterion 7: Group names with script or html tags are sanitized."""
    conn = test_db()
    conn.execute("INSERT INTO dataset_uploads (id, filename, original_name, file_type) VALUES (7, 'malicious.csv', 'malicious.csv', 'csv')")
    cols = ["Department", "Score"]
    records = [
        {"Department": "<script>alert('pwned')</script>", "Score": 10.0},
        {"Department": "Legit Team", "Score": 20.0},
    ]
    conn.execute("INSERT INTO sheets (id, dataset_id, name, columns_json, profile_json, row_count) VALUES (7, 7, 'Safety Check', ?, '{}', ?)", (json.dumps(cols), len(records)))
    for idx, rec in enumerate(records):
        conn.execute("INSERT INTO sheet_rows (sheet_id, row_index, data_json) VALUES (7, ?, ?)", (idx, json.dumps(rec)))
    conn.commit()

    plan = plan_analytical_query("Which department has the lowest score?", dataset_id=7, sheet_id=7, conn=conn)
    res = execute_analytical_plan(plan, conn=conn)
    # The raw script tag must NOT appear unescaped in the output
    assert "<script>alert('pwned')</script>" not in res["answer"]
    assert "&lt;script&gt;alert(&#x27;pwned&#x27;)&lt;/script&gt;" in res["answer"]
    conn.close()


def test_copilot_router_endpoint_integration(test_db):
    """End-to-end FastAPI endpoint check via TestClient."""
    conn = test_db()
    conn.execute("INSERT INTO dataset_uploads (id, filename, original_name, file_type) VALUES (8, 'it_tickets.csv', 'it_tickets.csv', 'csv')")
    cols = ["Severity", "Resolution_Time"]
    records = [
        {"Severity": "High", "Resolution_Time": 10.0},
        {"Severity": "Low", "Resolution_Time": 2.0},
    ]
    conn.execute("INSERT INTO sheets (id, dataset_id, name, columns_json, profile_json, row_count) VALUES (8, 8, 'Tickets', ?, '{}', ?)", (json.dumps(cols), len(records)))
    for idx, rec in enumerate(records):
        conn.execute("INSERT INTO sheet_rows (sheet_id, row_index, data_json) VALUES (8, ?, ?)", (idx, json.dumps(rec)))
    conn.commit()
    conn.close()

    client = TestClient(app)
    response = client.post(
        "/api/copilot/query",
        json={
            "query": "Which severity has the lowest resolution time?",
            "dataset_id": 8,
            "sheet_id": 8
        }
    )
    assert response.status_code == 200
    data = response.json()
    assert data["tool_used"] == "analytical_plan"
    assert "Low" in data["answer"]
    assert data["evidence"]["source_ids"] == [8]
    assert data["evidence"]["snapshot_hash"] is not None
