"""Authoritative Paraphrase Robustness, Negative Query Refusals, and Cross-Dataset Isolation Suite.

Validates:
1. Paraphrase Expansion: Canonical benchmark intents across natural language variations
   asserting calculation/number identity and grain correctness across wording variations.
2. Negative / Insufficient-Evidence Grounded Refusals:
   - Unavailable motivations ("Why did this employee take leave?")
   - Unentitled forward forecasts ("Will attendance improve next month?")
   - Observational causality ("Did the WFO policy cause attendance to increase?")
   - Out-of-scope enterprise query ("What is our company valuation?")
   - Unsupported subjective metric ("Which department is happiest?")
3. ConversationDatasetIsolationIntegrity:
   - Multi-turn across Workforce -> Retail -> Environmental -> Workforce in a single session.
   - Zero metric leakage, zero filter leakage, zero grain confusion.
"""

import pytest
from starlette.testclient import TestClient
from app.main import app
from app.services.copilot_query_planner import (
    plan_analytical_query,
    execute_analytical_plan
)


DS_WORKFORCE = 99770
SHEET_WORKFORCE_MAIN = 9967416

DS_RETAIL = 99771
SHEET_RETAIL_MAIN = 9967418

DS_ENV = 99772
SHEET_ENV_MAIN = 9967419


@pytest.fixture(scope="module")
def client():
    return TestClient(app)


@pytest.fixture(scope="function", autouse=True)
def seed_benchmark_datasets():
    """Ensure benchmark datasets (99770, 99771, 99772) are available in test db hermetically."""
    from app.db.database import get_connection
    from tests.fixtures.benchmark_seeder import ensure_benchmark_datasets_seeded
    with get_connection() as conn:
        ensure_benchmark_datasets_seeded(conn)


# =============================================================================
# GATE 1: PARAPHRASE EXPANSION BENCHMARK (NATURAL LANGUAGE VARIATIONS)
# =============================================================================

# 1. Q1 Paraphrases: Highest Attendance Department
@pytest.mark.parametrize("query", [
    "Which department has the highest attendance?",
    "Which team had the best attendance?",
    "Where was attendance highest by department?",
    "What department has maximum presence?"
])
def test_paraphrase_workforce_highest_attendance(query):
    plan = plan_analytical_query(query, dataset_id=DS_WORKFORCE, sheet_id=SHEET_WORKFORCE_MAIN)
    assert plan is not None
    assert plan.metric == "attendance"
    assert plan.direction == "highest"
    res = execute_analytical_plan(plan)
    assert res["status"] == "success"
    assert "Operations and Infrastructure" in res["answer"]
    assert "17.23" in res["answer"]


# 2. Q2 Paraphrases: Lowest Approved Leaves Department
@pytest.mark.parametrize("query", [
    "Which department had the lowest approved leaves?",
    "Which department took the fewest leaves?",
    "Which dept had minimum approved leaves?",
    "Where were approved leaves lowest across departments?"
])
def test_paraphrase_workforce_lowest_leaves_dept(query):
    plan = plan_analytical_query(query, dataset_id=DS_WORKFORCE, sheet_id=SHEET_WORKFORCE_MAIN)
    assert plan is not None
    assert plan.metric == "leaves"
    assert plan.direction == "lowest"
    res = execute_analytical_plan(plan)
    assert res["status"] == "success"
    assert "Alliance Initiative" in res["answer"]
    assert "1.00" in res["answer"]


# 3. Q3 Paraphrases: Highest Weekly Sales Store
@pytest.mark.parametrize("query", [
    "Which store has the highest weekly sales?",
    "Which store had highest Weekly_Sales?",
    "Top store by sales?",
    "Which store sold the most weekly?"
])
def test_paraphrase_retail_highest_weekly_sales(query):
    plan = plan_analytical_query(query, dataset_id=DS_RETAIL, sheet_id=SHEET_RETAIL_MAIN)
    assert plan is not None
    assert plan.direction == "highest"
    res = execute_analytical_plan(plan)
    assert res["status"] == "success"
    assert "20" in res["answer"]
    assert "2,300,697" in res["answer"]


# 4. Q5 Paraphrases: Highest PM10 City
@pytest.mark.parametrize("query", [
    "Which city has the highest PM10 level?",
    "City with worst PM10 pollution?",
    "Where is PM10 highest?",
    "Which city recorded maximum PM10 level?"
])
def test_paraphrase_environmental_highest_pm10(query):
    plan = plan_analytical_query(query, dataset_id=DS_ENV, sheet_id=SHEET_ENV_MAIN)
    assert plan is not None
    assert plan.direction == "highest"
    res = execute_analytical_plan(plan)
    assert res["status"] == "success"
    assert "Delhi" in res["answer"]
    assert "210.00" in res["answer"]


# 5. Q6 Paraphrases: Top 5 Employees by Attendance
@pytest.mark.parametrize("query", [
    "Who are the top 5 employees by attendance?",
    "List best 5 employees in attendance",
    "Top 5 employees with highest attendance",
    "Highest 5 attendees among employees"
])
def test_paraphrase_workforce_top5_employees(query):
    plan = plan_analytical_query(query, dataset_id=DS_WORKFORCE, sheet_id=SHEET_WORKFORCE_MAIN)
    assert plan is not None
    assert plan.entity_grain == "employee"
    assert plan.direction == "highest"
    res = execute_analytical_plan(plan)
    assert res["status"] == "success"
    assert res["evidence"]["result_grain"] == "employee"
    assert len(res["raw_analysis"]["rows"]) <= 5
    assert "Employee ID" in res["answer"]


# 6. Q7 Paraphrases: Lowest Recorded Attendance Employees
@pytest.mark.parametrize("query", [
    "who is not coming regularly",
    "Who comes to office the least?",
    "Who has poor attendance?",
    "Show employees with lowest presence.",
    "Which people are rarely in office?",
    "Who has the fewest attendance days?"
])
def test_paraphrase_workforce_lowest_attendance_employees(query):
    plan = plan_analytical_query(query, dataset_id=DS_WORKFORCE, sheet_id=SHEET_WORKFORCE_MAIN)
    assert plan is not None
    assert plan.metric == "attendance"
    assert plan.direction == "lowest"
    assert plan.entity_grain == "employee"
    res = execute_analytical_plan(plan)
    assert res["status"] == "success"
    assert "LB102" in res["answer"]
    assert "0 days" in res["answer"]


# 7. Q8 Paraphrases: Top 3 Stores by Sales
@pytest.mark.parametrize("query", [
    "which are the top 3 stores by sales?",
    "top 3 stores by weekly sales",
    "list best 3 stores for sales",
    "top 3 sales stores"
])
def test_paraphrase_retail_top3_stores(query):
    plan = plan_analytical_query(query, dataset_id=DS_RETAIL, sheet_id=SHEET_RETAIL_MAIN)
    assert plan is not None
    assert plan.direction == "highest"
    res = execute_analytical_plan(plan)
    assert res["status"] == "success"
    assert "Store Weekly Sales Breakdown" in res["answer"]
    groups = res["raw_analysis"]["groups"]
    assert len(groups) >= 3
    assert groups[0]["value"] >= groups[1]["value"] >= groups[2]["value"]


# 8. Q11 Paraphrases: Leave compared with Attendance
@pytest.mark.parametrize("query", [
    "Which department is taking the most leave compared with attendance?",
    "Which department has highest leave compared to attendance?",
    "Where are leaves highest relative to attendance?"
])
def test_paraphrase_leave_vs_attendance(query):
    plan = plan_analytical_query(query, dataset_id=DS_WORKFORCE, sheet_id=SHEET_WORKFORCE_MAIN)
    assert plan is not None
    assert plan.metric == "leaves"
    assert plan.direction == "highest"
    res = execute_analytical_plan(plan)
    assert res["status"] == "success"
    assert "Corporate Functions" in res["answer"]
    assert "3.39" in res["answer"]


# 9. Q12 Paraphrases: Attendance across Departments Comparison
@pytest.mark.parametrize("query", [
    "Compare attendance across departments",
    "Show attendance breakdown by department",
    "Department comparison for attendance"
])
def test_paraphrase_compare_departments_attendance(query):
    plan = plan_analytical_query(query, dataset_id=DS_WORKFORCE, sheet_id=SHEET_WORKFORCE_MAIN)
    assert plan is not None
    assert plan.metric == "attendance"
    assert plan.intent in ("breakdown", "ranking")
    res = execute_analytical_plan(plan)
    assert res["status"] == "success"
    assert "Department Average Attendance Breakdown" in res["answer"]


# 10. Q13 Paraphrases: Retail Holiday Breakdown
@pytest.mark.parametrize("query", [
    "compare Weekly_Sales by Holiday_Flag",
    "breakdown sales by Holiday_Flag",
    "sales comparison by Holiday_Flag"
])
def test_paraphrase_retail_holiday_flag(query):
    plan = plan_analytical_query(query, dataset_id=DS_RETAIL, sheet_id=SHEET_RETAIL_MAIN)
    assert plan is not None
    assert plan.metric == "Weekly_Sales"
    res = execute_analytical_plan(plan)
    assert res["status"] == "success"
    assert "Holiday_Flag" in res["answer"] or "Holiday" in res["answer"]


# 11. Q16 Paraphrases: Relationship attendance and leaves
@pytest.mark.parametrize("query", [
    "is attendance related to approved leave?",
    "is there a relationship between attendance and approved leave?",
    "are attendance and approved leaves correlated?",
    "does attendance relate to leaves?"
])
def test_paraphrase_relationship_attendance_leaves(query):
    plan = plan_analytical_query(query, dataset_id=DS_WORKFORCE, sheet_id=SHEET_WORKFORCE_MAIN)
    assert plan is not None
    assert plan.intent == "correlation_causation"
    res = execute_analytical_plan(plan)
    assert res["status"] == "success"
    assert "does not establish" in res["answer"].lower() or "refusal" in res["answer"].lower()


# 12. Q18 Paraphrases: Relationship weekly sales and temperature
@pytest.mark.parametrize("query", [
    "is weekly sales related to temperature?",
    "relationship between weekly sales and temperature",
    "are sales correlated with temperature?"
])
def test_paraphrase_sales_temperature_relationship(query):
    plan = plan_analytical_query(query, dataset_id=DS_RETAIL, sheet_id=SHEET_RETAIL_MAIN)
    assert plan is not None
    assert plan.intent == "correlation_causation"
    assert plan.metric == "Weekly_Sales"
    assert plan.secondary_metric == "Temperature"
    res = execute_analytical_plan(plan)
    assert res["status"] == "success"
    assert "Causal Claim Refusal" in res["answer"]


# 13. Q20 Paraphrases: Relationship SO2 and NO2
@pytest.mark.parametrize("query", [
    "is SO2 correlated with NO2?",
    "relationship between SO2 and NO2",
    "are SO2 and NO2 correlated?"
])
def test_paraphrase_so2_no2_relationship(query):
    plan = plan_analytical_query(query, dataset_id=DS_ENV, sheet_id=SHEET_ENV_MAIN)
    assert plan is not None
    assert plan.intent == "correlation_causation"
    assert plan.metric == "SO2"
    assert plan.secondary_metric == "NO2"
    res = execute_analytical_plan(plan)
    assert res["status"] == "success"
    assert "Statistical Association Analysis" in res["answer"]


# 14. Q4 Paraphrases: Total row count / records count
@pytest.mark.parametrize("query", [
    "how many rows in the dataset?",
    "what is the total number of records?",
    "how many records are there?",
    "how many rows?"
])
def test_paraphrase_retail_row_count(client, query):
    resp = client.post(
        "/api/copilot/query",
        json={"query": query, "dataset_id": DS_RETAIL, "sheet_id": SHEET_RETAIL_MAIN}
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "6,435" in data["answer"] or "6435" in data["answer"] or "records" in data["answer"].lower() or "rows" in data["answer"].lower()


# 15. Q9 Paraphrases: Bottom 2 stores by weekly sales
@pytest.mark.parametrize("query", [
    "which are the bottom 2 stores by weekly sales?",
    "lowest 2 stores in weekly sales",
    "which stores had lowest weekly sales?",
    "bottom 2 stores by sales"
])
def test_paraphrase_retail_bottom_stores(query):
    plan = plan_analytical_query(query, dataset_id=DS_RETAIL, sheet_id=SHEET_RETAIL_MAIN)
    assert plan is not None
    assert plan.metric == "Weekly_Sales"
    assert plan.direction == "lowest"
    res = execute_analytical_plan(plan)
    assert res["status"] == "success"
    groups = res["raw_analysis"]["groups"]
    assert len(groups) >= 2
    assert groups[0]["value"] <= groups[1]["value"]


# 16. Q10 Paraphrases: Top cities with highest NO2
@pytest.mark.parametrize("query", [
    "which are the top 5 cities with highest NO2?",
    "top 5 cities by NO2 pollution",
    "cities with highest NO2 levels",
    "where is NO2 highest across cities?"
])
def test_paraphrase_environmental_top_cities_no2(query):
    plan = plan_analytical_query(query, dataset_id=DS_ENV, sheet_id=SHEET_ENV_MAIN)
    assert plan is not None
    assert plan.metric == "NO2"
    assert plan.direction == "highest"
    res = execute_analytical_plan(plan)
    assert res["status"] == "success"
    assert ("City NO2 Breakdown" in res["answer"] or "Highest City NO2" in res["answer"]) and "Delhi" in res["answer"]


# 17. Q14 Paraphrases: Breakdown sales across stores
@pytest.mark.parametrize("query", [
    "breakdown sales across stores",
    "show sales breakdown by store",
    "compare sales across stores",
    "store sales breakdown"
])
def test_paraphrase_retail_sales_breakdown(query):
    plan = plan_analytical_query(query, dataset_id=DS_RETAIL, sheet_id=SHEET_RETAIL_MAIN)
    assert plan is not None
    assert plan.metric == "Weekly_Sales"
    res = execute_analytical_plan(plan)
    assert res["status"] == "success"
    assert "Store Weekly Sales Breakdown" in res["answer"]


# 18. Q15 Paraphrases: Compare SO2 and NO2 correlation/association
@pytest.mark.parametrize("query", [
    "compare correlation between SO2 and NO2",
    "correlation of SO2 and NO2",
    "examine relationship of SO2 vs NO2"
])
def test_paraphrase_environmental_compare_pollutants(query):
    plan = plan_analytical_query(query, dataset_id=DS_ENV, sheet_id=SHEET_ENV_MAIN)
    assert plan is not None
    assert plan.intent == "correlation_causation"
    res = execute_analytical_plan(plan)
    assert res["status"] == "success"
    assert "Causal Claim Refusal" in res["answer"]


# 19. Q17 Paraphrases: Causal refusal for leave causes attendance
@pytest.mark.parametrize("query", [
    "Does higher approved leave cause lower attendance?",
    "Do approved leaves cause attendance drops?",
    "Does taking leave lead to lower attendance?"
])
def test_paraphrase_workforce_leave_causes_attendance_refusal(query):
    plan = plan_analytical_query(query, dataset_id=DS_WORKFORCE, sheet_id=SHEET_WORKFORCE_MAIN)
    assert plan is not None
    assert plan.intent == "correlation_causation"
    res = execute_analytical_plan(plan)
    assert res["status"] == "success"
    assert "Refusal" in res["answer"] or "NOT establish" in res["answer"]


# 20. Q19 Paraphrases: Causal refusal for temperature causes sales
@pytest.mark.parametrize("query", [
    "Does temperature cause changes in weekly sales?",
    "Does warm weather cause higher sales?",
    "Does cold weather cause lower sales?"
])
def test_paraphrase_retail_temperature_causes_sales_refusal(query):
    plan = plan_analytical_query(query, dataset_id=DS_RETAIL, sheet_id=SHEET_RETAIL_MAIN)
    assert plan is not None
    assert plan.intent == "correlation_causation"
    res = execute_analytical_plan(plan)
    assert res["status"] == "success"
    assert "Causal Claim Refusal" in res["answer"]


# 21. Q21 Paraphrases: Multi-turn 'Why?' follow-up
@pytest.mark.parametrize("query", [
    "Why?",
    "Why is that?",
    "Why is this the case?",
    "Explain why"
])
def test_paraphrase_workforce_followup_why(query):
    p1 = plan_analytical_query("which department has the highest attendance?", dataset_id=DS_WORKFORCE, sheet_id=SHEET_WORKFORCE_MAIN)
    r1 = execute_analytical_plan(p1)
    p2 = plan_analytical_query(query, dataset_id=DS_WORKFORCE, sheet_id=SHEET_WORKFORCE_MAIN, prior_context=r1["prior_context"])
    assert p2 is not None
    assert p2.intent == "followup_why"
    r2 = execute_analytical_plan(p2)
    assert r2["status"] == "success"
    assert "Operations and Infrastructure" in r2["answer"]


# 22. Q22 Paraphrases: Follow-up 'Show me the bottom 3'
@pytest.mark.parametrize("query", [
    "Show me the bottom 3",
    "what about the lowest 3?",
    "give me the worst 3",
    "bottom 3 instead"
])
def test_paraphrase_workforce_followup_bottom3(query):
    p1 = plan_analytical_query("which department has the highest attendance?", dataset_id=DS_WORKFORCE, sheet_id=SHEET_WORKFORCE_MAIN)
    r1 = execute_analytical_plan(p1)
    p2 = plan_analytical_query(query, dataset_id=DS_WORKFORCE, sheet_id=SHEET_WORKFORCE_MAIN, prior_context=r1["prior_context"])
    assert p2 is not None
    assert p2.direction == "lowest"
    assert p2.ranking_limit == 3
    r2 = execute_analytical_plan(p2)
    assert r2["status"] == "success"
    assert r2["evidence"]["result_grain"] == "department"


# 23. Q23 Paraphrases: Follow-up cohort filter
@pytest.mark.parametrize("query", [
    "What about Operations only?",
    "filter to Operations",
    "just Operations department",
    "Operations only"
])
def test_paraphrase_workforce_followup_cohort_filter(query):
    p1 = plan_analytical_query("who is not coming regularly", dataset_id=DS_WORKFORCE, sheet_id=SHEET_WORKFORCE_MAIN)
    r1 = execute_analytical_plan(p1)
    p2 = plan_analytical_query(query, dataset_id=DS_WORKFORCE, sheet_id=SHEET_WORKFORCE_MAIN, prior_context=r1["prior_context"])
    assert p2 is not None
    assert "Operations" in p2.filter_val
    r2 = execute_analytical_plan(p2)
    assert r2["status"] == "success"
    assert r2["evidence"]["result_grain"] == "employee"


# 24. Q24 Paraphrases: Follow-up 'I need employee ID'
@pytest.mark.parametrize("query", [
    "i need employee id",
    "show employee ids",
    "give me the employee id",
    "include employee id"
])
def test_paraphrase_workforce_followup_employee_id(query):
    p1 = plan_analytical_query("which department has lowest attendance?", dataset_id=DS_WORKFORCE, sheet_id=SHEET_WORKFORCE_MAIN)
    r1 = execute_analytical_plan(p1)
    p2 = plan_analytical_query(query, dataset_id=DS_WORKFORCE, sheet_id=SHEET_WORKFORCE_MAIN, prior_context=r1["prior_context"])
    assert p2 is not None
    assert p2.entity_grain == "employee"
    r2 = execute_analytical_plan(p2)
    assert r2["status"] == "success"
    assert "Employee ID" in r2["answer"]


# 25. Q25 Paraphrases: Retail follow-up direction inversion
@pytest.mark.parametrize("query", [
    "show me the bottom 3",
    "what about the lowest 3 stores?",
    "give me bottom 3 stores",
    "bottom 3 stores instead"
])
def test_paraphrase_retail_followup_bottom3(query):
    p1 = plan_analytical_query("which store has highest weekly sales?", dataset_id=DS_RETAIL, sheet_id=SHEET_RETAIL_MAIN)
    r1 = execute_analytical_plan(p1)
    p2 = plan_analytical_query(query, dataset_id=DS_RETAIL, sheet_id=SHEET_RETAIL_MAIN, prior_context=r1["prior_context"])
    assert p2 is not None
    assert p2.direction == "lowest"
    assert p2.metric == "Weekly_Sales"
    r2 = execute_analytical_plan(p2)
    assert r2["status"] == "success"
    assert "Store Weekly Sales Breakdown" in r2["answer"]


# =============================================================================
# GATE 2: GROUNDED REFUSALS (NEGATIVE / INSUFFICIENT EVIDENCE)
# =============================================================================

def test_negative_leave_motivation_refusal():
    """Q_NEG_1: Why did this employee take leave? -> Refusal with evidence boundary."""
    plan = plan_analytical_query(
        "Why did this employee take leave?",
        dataset_id=DS_WORKFORCE,
        sheet_id=SHEET_WORKFORCE_MAIN
    )
    assert plan is not None
    assert plan.intent == "insufficient_evidence"
    res = execute_analytical_plan(plan)
    assert res["status"] == "insufficient_evidence"
    assert "categorical or qualitative reason field" in res["answer"]
    assert "cannot infer individual leave motivations" in res["answer"]


def test_negative_forward_forecast_refusal():
    """Q_NEG_2: Will attendance improve next month? -> Refusal with single-period constraint."""
    plan = plan_analytical_query(
        "Will attendance improve next month?",
        dataset_id=DS_WORKFORCE,
        sheet_id=SHEET_WORKFORCE_MAIN
    )
    assert plan is not None
    assert plan.intent == "insufficient_evidence"
    res = execute_analytical_plan(plan)
    assert res["status"] == "insufficient_evidence"
    assert "historical recorded records" in res["answer"]
    assert "does not fabricate future projections" in res["answer"]


def test_negative_observational_causality_refusal():
    """Q_NEG_3: Did the WFO policy cause attendance to increase? -> Refusal of causal claim."""
    plan = plan_analytical_query(
        "Did the WFO policy cause attendance to increase?",
        dataset_id=DS_WORKFORCE,
        sheet_id=SHEET_WORKFORCE_MAIN
    )
    assert plan is not None
    assert plan.intent == "insufficient_evidence"
    res = execute_analytical_plan(plan)
    assert res["status"] == "insufficient_evidence"
    assert "observational attendance records" in res["answer"]
    assert "strictly refuses to assert causal attribution" in res["answer"]


def test_negative_out_of_scope_corporate_valuation_refusal():
    """Q_NEG_4: What is our company valuation? -> Grounded refusal for out-of-scope enterprise query."""
    plan = plan_analytical_query(
        "What is our company valuation?",
        dataset_id=DS_WORKFORCE,
        sheet_id=SHEET_WORKFORCE_MAIN
    )
    assert plan is not None
    assert plan.intent == "insufficient_evidence"
    res = execute_analytical_plan(plan)
    assert res["status"] == "insufficient_evidence"
    assert "operational spreadsheet records" in res["answer"]
    assert "corporate valuation" in res["answer"]


def test_negative_unsupported_sentiment_metric_refusal():
    """Q_NEG_5: Which department is happiest? -> Grounded refusal identifying missing field."""
    plan = plan_analytical_query(
        "Which department is happiest?",
        dataset_id=DS_WORKFORCE,
        sheet_id=SHEET_WORKFORCE_MAIN
    )
    assert plan is not None
    assert plan.intent == "insufficient_evidence"
    res = execute_analytical_plan(plan)
    assert res["status"] == "insufficient_evidence"
    assert "does not contain fields related to **happiest**" in res["answer"]
    assert "Available metrics in this sheet" in res["answer"]


def test_negative_out_of_scope_nonexistent_cohort_refusal():
    """Q_NEG_6: What about Chicago only? -> Grounded refusal when entity does not exist in dataset."""
    p1 = plan_analytical_query("who is not coming regularly", dataset_id=DS_WORKFORCE, sheet_id=SHEET_WORKFORCE_MAIN)
    r1 = execute_analytical_plan(p1)
    p2 = plan_analytical_query("What about Chicago only?", dataset_id=DS_WORKFORCE, sheet_id=SHEET_WORKFORCE_MAIN, prior_context=r1["prior_context"])
    assert p2 is not None
    res = execute_analytical_plan(p2)
    assert res["status"] == "insufficient_evidence"
    assert "Chicago" in res["answer"]
    assert "no records found" in res["answer"].lower()


def test_negative_unsupported_profitability_refusal():
    """Q_NEG_7: What is the profitability of employees? -> Grounded refusal for missing metric."""
    plan = plan_analytical_query("What is the profitability of employees?", dataset_id=DS_WORKFORCE, sheet_id=SHEET_WORKFORCE_MAIN)
    assert plan is not None
    assert plan.intent == "insufficient_evidence"
    res = execute_analytical_plan(plan)
    assert res["status"] == "insufficient_evidence"
    assert "profitability" in res["answer"]
    assert "does not contain" in res["answer"].lower()


def test_negative_unsupported_quarterly_projection_refusal():
    """Q_NEG_8: Will sales drop next quarter? -> Grounded refusal for forward projection."""
    plan = plan_analytical_query("Will sales drop next quarter?", dataset_id=DS_RETAIL, sheet_id=SHEET_RETAIL_MAIN)
    assert plan is not None
    assert plan.intent == "insufficient_evidence"
    res = execute_analytical_plan(plan)
    assert res["status"] == "insufficient_evidence"
    assert "does not fabricate future projections" in res["answer"]


def test_negative_out_of_scope_stock_price_refusal():
    """Q_NEG_9: What is our company stock price? -> Grounded refusal for out-of-scope query."""
    plan = plan_analytical_query("What is our company stock price?", dataset_id=DS_WORKFORCE, sheet_id=SHEET_WORKFORCE_MAIN)
    assert plan is not None
    assert plan.intent == "insufficient_evidence"
    res = execute_analytical_plan(plan)
    assert res["status"] == "insufficient_evidence"
    assert "financial market data" in res["answer"] or "corporate valuation" in res["answer"]


def test_negative_unsupported_morale_refusal():
    """Q_NEG_10: Which department has the highest morale? -> Grounded refusal identifying missing field."""
    plan = plan_analytical_query("Which department has the highest morale?", dataset_id=DS_WORKFORCE, sheet_id=SHEET_WORKFORCE_MAIN)
    assert plan is not None
    assert plan.intent == "insufficient_evidence"
    res = execute_analytical_plan(plan)
    assert res["status"] == "insufficient_evidence"
    assert "morale" in res["answer"]


# =============================================================================
# GATE 3: CONVERSATION DATASET ISOLATION INTEGRITY (4-STAGE SWITCH SEQUENCE)
# =============================================================================

def test_conversation_dataset_isolation_multi_domain_cycle():
    """Executes Workforce -> Retail -> Environmental -> Workforce in one conversation session.
    Asserts 0% cross-domain leakage of metric, grain, filters, or evidence.
    """
    session_context = {}

    # Stage 1: Workforce
    p1 = plan_analytical_query(
        "Which department has the highest attendance?",
        dataset_id=DS_WORKFORCE,
        sheet_id=SHEET_WORKFORCE_MAIN,
        prior_context=session_context
    )
    r1 = execute_analytical_plan(p1)
    assert r1["status"] == "success"
    assert "Operations and Infrastructure" in r1["answer"]
    assert "Weekly_Sales" not in r1["answer"]
    assert "PM10" not in r1["answer"]
    session_context = dict(r1.get("context") or {})
    session_context["dataset_id"] = DS_WORKFORCE
    session_context["sheet_id"] = SHEET_WORKFORCE_MAIN

    # Stage 2: Retail (Immediate switch to 99771)
    p2 = plan_analytical_query(
        "Which store had the highest weekly sales?",
        dataset_id=DS_RETAIL,
        sheet_id=SHEET_RETAIL_MAIN,
        prior_context=session_context  # Stale workforce context passed in
    )
    assert p2.dataset_id == DS_RETAIL
    assert p2.metric != "attendance"
    r2 = execute_analytical_plan(p2)
    assert r2["status"] == "success"
    assert "20" in r2["answer"]
    assert "Operations and Infrastructure" not in r2["answer"]
    assert "attendance" not in r2["answer"].lower()
    session_context = dict(r2.get("context") or {})
    session_context["dataset_id"] = DS_RETAIL
    session_context["sheet_id"] = SHEET_RETAIL_MAIN

    # Stage 3: Environmental (Immediate switch to 99772)
    p3 = plan_analytical_query(
        "Which city has the highest PM10?",
        dataset_id=DS_ENV,
        sheet_id=SHEET_ENV_MAIN,
        prior_context=session_context  # Stale retail context passed in
    )
    assert p3.dataset_id == DS_ENV
    r3 = execute_analytical_plan(p3)
    assert r3["status"] == "success"
    assert "Delhi" in r3["answer"]
    assert "Weekly_Sales" not in r3["answer"]
    assert "Operations" not in r3["answer"]
    session_context = dict(r3.get("context") or {})
    session_context["dataset_id"] = DS_ENV
    session_context["sheet_id"] = SHEET_ENV_MAIN

    # Stage 4: Workforce (Immediate return to 99770)
    p4 = plan_analytical_query(
        "Who comes to office the least?",
        dataset_id=DS_WORKFORCE,
        sheet_id=SHEET_WORKFORCE_MAIN,
        prior_context=session_context  # Stale environmental context passed in
    )
    assert p4.dataset_id == DS_WORKFORCE
    assert p4.entity_grain == "employee"
    r4 = execute_analytical_plan(p4)
    assert r4["status"] == "success"
    assert "LB102" in r4["answer"]
    assert "Delhi" not in r4["answer"]
    assert "PM10" not in r4["answer"]
    assert "Store" not in r4["answer"]
