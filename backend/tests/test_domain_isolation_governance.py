"""Test Suite for Phase 13.5: Domain Isolation & Analytical Capability Governance.

Verifies:
1. test_sales_dataset_never_generates_hr_kpis
2. test_sales_dataset_never_generates_attendance_visuals
3. test_sales_dataset_never_loads_policy_calendar_engine
4. test_missing_concept_is_not_zero
5. test_unsupported_metric_is_not_rendered
6. test_scenario_controls_are_domain_specific
7. test_domain_capability_gate_blocks_invalid_analytics
8. test_retail_dataset_generates_sales_metrics
9. test_finance_dataset_does_not_generate_hr_metrics
10. test_workforce_dataset_still_generates_workforce_metrics
11. test_domain_is_invariant_to_column_name_collision
12. test_cross_domain_leakage_rate_zero (Cross-domain benchmark matrix)
"""
from __future__ import annotations

import json
import sqlite3
import pytest

from app.db.database import get_connection
from app.services.adaptive_dashboard.domain_governance import (
    AnalyticalEntitlementIntegrity,
    DatasetDomain,
    DomainCapabilityGate,
)
from app.services.adaptive_dashboard.executive_analytics import (
    ExecutiveAnalyticsRegistry,
    compute_governed_executive_metrics,
)
from app.services.adaptive_dashboard.composition_planner import (
    ExecutiveCompositionPlanner,
    RetailSalesCompositionStrategy,
    WorkforceCompositionStrategy,
)
from app.services.adaptive_dashboard.scenario_engine import (
    DeterministicScenarioEngine,
    GovernedScenarioParameters,
    RetailSalesScenarioStrategy,
    ScenarioClassification,
    ScenarioRegistry,
    WorkforceScenarioStrategy,
)
from app.services.adaptive_dashboard.policy_engine import PolicyCalendarEngine


# ------------------------------------------------------------------------------
# Test Fixtures & Samples
# ------------------------------------------------------------------------------

WALMART_COLUMNS = [
    "Store", "Date", "Weekly_Sales", "Holiday_Flag",
    "Temperature", "Fuel_Price", "CPI", "Unemployment"
]

WALMART_ROWS = [
    {"Store": 1, "Date": "05-02-2010", "Weekly_Sales": 1643690.90, "Holiday_Flag": 0, "Temperature": 42.31, "Fuel_Price": 2.572, "CPI": 211.0963582, "Unemployment": 8.106},
    {"Store": 2, "Date": "05-02-2010", "Weekly_Sales": 2136242.25, "Holiday_Flag": 0, "Temperature": 40.19, "Fuel_Price": 2.572, "CPI": 210.7526051, "Unemployment": 8.324},
    {"Store": 20, "Date": "05-02-2010", "Weekly_Sales": 2401395.47, "Holiday_Flag": 0, "Temperature": 25.92, "Fuel_Price": 2.784, "CPI": 204.2471938, "Unemployment": 8.187},
    {"Store": 33, "Date": "05-02-2010", "Weekly_Sales": 274605.73, "Holiday_Flag": 0, "Temperature": 58.40, "Fuel_Price": 2.962, "CPI": 126.4420645, "Unemployment": 10.115},
    {"Store": 1, "Date": "12-02-2010", "Weekly_Sales": 1641957.44, "Holiday_Flag": 1, "Temperature": 38.51, "Fuel_Price": 2.548, "CPI": 211.2421698, "Unemployment": 8.106},
    {"Store": 20, "Date": "12-02-2010", "Weekly_Sales": 2109107.90, "Holiday_Flag": 1, "Temperature": 22.12, "Fuel_Price": 2.773, "CPI": 204.3857473, "Unemployment": 8.187},
    {"Store": 33, "Date": "12-02-2010", "Weekly_Sales": 285002.50, "Holiday_Flag": 1, "Temperature": 54.34, "Fuel_Price": 2.962, "CPI": 126.4962581, "Unemployment": 10.115},
]

WORKFORCE_COLUMNS = ["Employee_ID", "Department", "Total_Attendance", "Approved_Leaves", "Date"]

WORKFORCE_ROWS = [
    {"Employee_ID": f"EMP{i:03d}", "Department": dept, "Total_Attendance": att, "Approved_Leaves": lvs, "Date": "2026-07-31"}
    for i, (dept, att, lvs) in enumerate([
        ("Operations", 16.0, 2.0),
        ("Engineering", 12.0, 3.0),
        ("Functions", 15.0, 1.0),
        ("NRP", 14.0, 2.0),
        ("Design", 10.0, 4.0),
        ("Alliance Initiat", 8.0, 5.0),
    ] * 10, start=1)
]

FINANCE_COLUMNS = ["Account_Code", "Entity", "Date", "Gross_Revenue", "COGS", "Operating_Margin", "EBITDA"]
FINANCE_ROWS = [
    {"Account_Code": "REV-100", "Entity": "North America", "Date": "2026-Q1", "Gross_Revenue": 5000000.0, "COGS": 2500000.0, "Operating_Margin": 25.0, "EBITDA": 1250000.0},
    {"Account_Code": "REV-200", "Entity": "EMEA", "Date": "2026-Q1", "Gross_Revenue": 3500000.0, "COGS": 1800000.0, "Operating_Margin": 22.0, "EBITDA": 770000.0},
]


@pytest.fixture
def sales_dataset_in_db():
    """Populates an isolated dataset with Walmart Sales records."""
    conn = get_connection()
    try:
        ds_id = conn.execute(
            "INSERT INTO dataset_uploads(filename, original_name, file_type, display_name) VALUES (?, ?, ?, ?)",
            ("walmart_sales.csv", "Walmart Sales Analysis.csv", "csv", "Walmart Sales Analysis")
        ).lastrowid

        s_id = conn.execute(
            "INSERT INTO sheets(dataset_id, name, columns_json, profile_json, row_count) VALUES (?, ?, ?, ?, ?)",
            (ds_id, "Sales_Data", json.dumps(WALMART_COLUMNS), "[]", len(WALMART_ROWS))
        ).lastrowid

        for idx, r in enumerate(WALMART_ROWS):
            conn.execute(
                "INSERT INTO sheet_rows(sheet_id, row_index, data_json) VALUES (?, ?, ?)",
                (s_id, idx, json.dumps(r))
            )
        conn.commit()
        return ds_id
    finally:
        conn.close()


@pytest.fixture
def workforce_dataset_in_db():
    """Populates an isolated dataset with July Workforce Attendance records."""
    conn = get_connection()
    try:
        ds_id = conn.execute(
            "INSERT INTO dataset_uploads(filename, original_name, file_type, display_name) VALUES (?, ?, ?, ?)",
            ("july_wfo.xlsx", "July 2026 Attendance.xlsx", "xlsx", "July 2026 Workforce")
        ).lastrowid

        s_id = conn.execute(
            "INSERT INTO sheets(dataset_id, name, columns_json, profile_json, row_count) VALUES (?, ?, ?, ?, ?)",
            (ds_id, "Attendance_Sheet", json.dumps(WORKFORCE_COLUMNS), "[]", len(WORKFORCE_ROWS))
        ).lastrowid

        for idx, r in enumerate(WORKFORCE_ROWS):
            conn.execute(
                "INSERT INTO sheet_rows(sheet_id, row_index, data_json) VALUES (?, ?, ?)",
                (s_id, idx, json.dumps(r))
            )
        conn.commit()
        return ds_id
    finally:
        conn.close()


# ------------------------------------------------------------------------------
# Test 1: test_domain_capability_gate_blocks_invalid_analytics
# ------------------------------------------------------------------------------

def test_domain_capability_gate_blocks_invalid_analytics():
    """Verify DomainCapabilityGate correctly resolves retail_sales and blocks workforce analytics."""
    profile = DomainCapabilityGate.resolve_domain(
        columns=WALMART_COLUMNS,
        sample_rows=WALMART_ROWS,
        dataset_name="Walmart Sales Analysis",
    )
    assert profile.domain == DatasetDomain.RETAIL_SALES
    assert profile.confidence >= 0.70

    # Retail capabilities must be allowed
    assert "sales_trend" in profile.allowed_capabilities
    assert "store_ranking" in profile.allowed_capabilities
    assert "holiday_analysis" in profile.allowed_capabilities

    # Workforce capabilities must be explicitly blocked
    assert "attendance_policy" in profile.blocked_capabilities
    assert "leave_analysis" in profile.blocked_capabilities
    assert "office_presence" in profile.blocked_capabilities
    assert "workforce_compliance" in profile.blocked_capabilities


# ------------------------------------------------------------------------------
# Test 2: test_domain_is_invariant_to_column_name_collision
# ------------------------------------------------------------------------------

def test_domain_is_invariant_to_column_name_collision():
    """Verify that a sales dataset containing a 'Department' or 'Dept' column does NOT falsely become WORKFORCE."""
    collision_columns = ["Store", "Department", "Date", "Weekly_Sales", "Holiday_Flag", "CPI", "Fuel_Price"]
    collision_rows = [
        {"Store": 1, "Department": "Electronics", "Date": "05-02-2010", "Weekly_Sales": 450000.0, "Holiday_Flag": 0, "CPI": 211.0, "Fuel_Price": 2.57},
        {"Store": 1, "Department": "Grocery", "Date": "05-02-2010", "Weekly_Sales": 850000.0, "Holiday_Flag": 0, "CPI": 211.0, "Fuel_Price": 2.57},
    ]

    profile = DomainCapabilityGate.resolve_domain(
        columns=collision_columns,
        sample_rows=collision_rows,
        dataset_name="Retail Store Department Sales",
    )
    # Must remain RETAIL_SALES despite 'Department' column!
    assert profile.domain == DatasetDomain.RETAIL_SALES
    assert "attendance_policy" in profile.blocked_capabilities


# ------------------------------------------------------------------------------
# Test 3: test_sales_dataset_never_generates_hr_kpis
# ------------------------------------------------------------------------------

def test_sales_dataset_never_generates_hr_kpis(sales_dataset_in_db):
    """Verify that Walmart Sales Analysis never generates workforce/HR KPIs."""
    metrics = compute_governed_executive_metrics(dataset_id=sales_dataset_in_db)
    kpis = metrics.get("kpis", [])
    labels = [k["label"].lower() for k in kpis]

    assert len(kpis) >= 3

    # HR KPIs must NEVER appear
    assert "office presence rate" not in labels
    assert "policy compliance" not in labels
    assert "approved leave rate" not in labels
    assert "department attendance gap" not in labels

    # Retail KPIs MUST appear
    assert any("sales" in l for l in labels)
    assert any("store" in l for l in labels or "lift" in l)


# ------------------------------------------------------------------------------
# Test 4: test_sales_dataset_never_generates_attendance_visuals
# ------------------------------------------------------------------------------

def test_sales_dataset_never_generates_attendance_visuals(sales_dataset_in_db):
    """Verify that executive topics for Walmart Sales Analysis never generate attendance visual stories."""
    metrics = compute_governed_executive_metrics(dataset_id=sales_dataset_in_db)
    topics = ExecutiveCompositionPlanner.plan_composition(
        selected_insights=[],
        dataset_name="Walmart Sales Analysis",
        dataset_id=sales_dataset_in_db,
        gov_metrics=metrics,
    )

    assert len(topics) >= 4
    topic_titles = [t.title.lower() for t in topics]

    # Workforce templates must NOT appear
    for title in topic_titles:
        assert "attendance" not in title, f"Domain leakage detected in topic: {title}"
        assert "approved leave" not in title, f"Domain leakage detected in topic: {title}"
        assert "office days" not in title, f"Domain leakage detected in topic: {title}"

    # Retail topics MUST appear
    assert any("store sales ranking" in t for t in topic_titles)
    assert any("weekly sales trend" in t or "commercial lift" in t for t in topic_titles)


# ------------------------------------------------------------------------------
# Test 5: test_sales_dataset_never_loads_policy_calendar_engine
# ------------------------------------------------------------------------------

def test_sales_dataset_never_loads_policy_calendar_engine(sales_dataset_in_db, monkeypatch):
    """Verify that Scenario Explorer never instantiates PolicyCalendarEngine when processing sales data."""
    policy_engine_instantiations = []

    original_init = PolicyCalendarEngine.__init__
    def tracked_init(self, *args, **kwargs):
        policy_engine_instantiations.append(True)
        return original_init(self, *args, **kwargs)

    monkeypatch.setattr(PolicyCalendarEngine, "__init__", tracked_init)

    # 1. Fetch benchmark scenarios
    scenarios = DeterministicScenarioEngine.get_benchmark_scenarios(sales_dataset_in_db)
    assert len(scenarios) >= 3

    # 2. Run simulation
    sim_card = DeterministicScenarioEngine.simulate_scenario(
        dataset_id=sales_dataset_in_db,
        params=GovernedScenarioParameters(promo_multiplier=1.25, markdown_discount_pct=10.0),
    )
    assert sim_card.scenario_id == "SCEN-CUSTOM"

    # Invariant: PolicyCalendarEngine must NEVER have been called!
    assert len(policy_engine_instantiations) == 0, "CRITICAL: PolicyCalendarEngine was invoked for a retail sales dataset!"


# ------------------------------------------------------------------------------
# Test 6: test_missing_concept_is_not_zero
# ------------------------------------------------------------------------------

def test_missing_concept_is_not_zero():
    """Verify that AnalyticalEntitlementIntegrity blocks missing concepts rather than defaulting to 0."""
    entitled, status = AnalyticalEntitlementIntegrity.verify_metric_entitlement(
        metric_concept="approved_leave_rate",
        dataset_columns=WALMART_COLUMNS,
        detected_entities=["store_location", "periodic_sales"],
    )
    assert entitled is False
    assert status == "UNSUPPORTED_CONCEPT"

    entitled, status = AnalyticalEntitlementIntegrity.verify_metric_entitlement(
        metric_concept="office_presence_rate",
        dataset_columns=WALMART_COLUMNS,
        detected_entities=["store_location", "periodic_sales"],
    )
    assert entitled is False
    assert status == "UNSUPPORTED_CONCEPT"


# ------------------------------------------------------------------------------
# Test 7: test_unsupported_metric_is_not_rendered
# ------------------------------------------------------------------------------

def test_unsupported_metric_is_not_rendered(sales_dataset_in_db):
    """Verify that unsupported metrics (e.g. Leave Rate = 0%) are omitted completely, not rendered as 0."""
    metrics = compute_governed_executive_metrics(dataset_id=sales_dataset_in_db)
    kpis = metrics.get("kpis", [])

    for kpi in kpis:
        # No KPI should claim 0% leave or 0% policy compliance
        label = kpi["label"].lower()
        assert "leave" not in label
        assert "compliance" not in label
        assert "presence" not in label


# ------------------------------------------------------------------------------
# Test 8: test_scenario_controls_are_domain_specific
# ------------------------------------------------------------------------------

def test_scenario_controls_are_domain_specific(sales_dataset_in_db, workforce_dataset_in_db):
    """Verify that scenario levers match the specific detected domain."""
    # 1. Retail dataset levers
    strategy_retail, domain_retail = DeterministicScenarioEngine.resolve_strategy_for_dataset(sales_dataset_in_db)
    assert domain_retail == DatasetDomain.RETAIL_SALES
    assert strategy_retail is RetailSalesScenarioStrategy
    levers_retail = strategy_retail.get_governed_levers()
    lever_ids_retail = [l["lever_id"] for l in levers_retail]
    assert "promo_multiplier" in lever_ids_retail
    assert "markdown_discount_pct" in lever_ids_retail
    assert "days_per_week" not in lever_ids_retail

    # 2. Workforce dataset levers
    strategy_wf, domain_wf = DeterministicScenarioEngine.resolve_strategy_for_dataset(workforce_dataset_in_db)
    assert domain_wf == DatasetDomain.WORKFORCE
    assert strategy_wf is WorkforceScenarioStrategy
    levers_wf = strategy_wf.get_governed_levers()
    lever_ids_wf = [l["lever_id"] for l in levers_wf]
    assert "days_per_week" in lever_ids_wf
    assert "leave_exemption_ratio" in lever_ids_wf
    assert "promo_multiplier" not in lever_ids_wf


# ------------------------------------------------------------------------------
# Test 9: test_retail_dataset_generates_sales_metrics
# ------------------------------------------------------------------------------

def test_retail_dataset_generates_sales_metrics(sales_dataset_in_db):
    """Verify that retail sales dataset produces valid sales volume and spread metrics."""
    metrics = compute_governed_executive_metrics(dataset_id=sales_dataset_in_db)
    kpis = {k["kpi_id"]: k for k in metrics.get("kpis", [])}

    assert "KPI-SALES-001" in kpis
    assert "Total Sales Volume" in kpis["KPI-SALES-001"]["label"]
    assert "$" in kpis["KPI-SALES-001"]["formatted_value"]

    assert "KPI-SALES-002" in kpis
    assert "Average Weekly Sales" in kpis["KPI-SALES-002"]["label"]

    assert "KPI-SALES-004" in kpis
    assert "Holiday Sales Lift" in kpis["KPI-SALES-004"]["label"]


# ------------------------------------------------------------------------------
# Test 10: test_finance_dataset_does_not_generate_hr_metrics
# ------------------------------------------------------------------------------

def test_finance_dataset_does_not_generate_hr_metrics():
    """Verify that finance data does not generate HR metrics."""
    profile = DomainCapabilityGate.resolve_domain(
        columns=FINANCE_COLUMNS,
        sample_rows=FINANCE_ROWS,
        dataset_name="Quarterly Financial Ledger",
    )
    assert profile.domain in (DatasetDomain.FINANCE, DatasetDomain.GENERIC_BUSINESS)
    assert "attendance_policy" in profile.blocked_capabilities
    assert "leave_analysis" in profile.blocked_capabilities

    strategy = ExecutiveAnalyticsRegistry.resolve(profile.domain)
    result = strategy.compute(dataset_id=888, rows=FINANCE_ROWS, columns=FINANCE_COLUMNS, profile=profile)
    kpis = result.get("kpis", [])
    labels = [k["label"].lower() for k in kpis]

    assert not any("office presence" in l for l in labels)
    assert not any("leave" in l for l in labels)
    assert not any("compliance" in l for l in labels)


# ------------------------------------------------------------------------------
# Test 11: test_workforce_dataset_still_generates_workforce_metrics
# ------------------------------------------------------------------------------

def test_workforce_dataset_still_generates_workforce_metrics(workforce_dataset_in_db):
    """Verify that legitimate workforce datasets continue to generate full attendance analytics."""
    metrics = compute_governed_executive_metrics(dataset_id=workforce_dataset_in_db)
    assert metrics["domain_profile"]["domain"] == "workforce"

    kpis = {k["kpi_id"]: k for k in metrics.get("kpis", [])}
    assert "KPI-001" in kpis
    assert kpis["KPI-001"]["label"] == "Office Presence Rate"
    assert "KPI-002" in kpis
    assert kpis["KPI-002"]["label"] == "Policy Compliance"
    assert "KPI-003" in kpis
    assert kpis["KPI-003"]["label"] == "Approved Leave Rate"
    assert "KPI-004" in kpis
    assert kpis["KPI-004"]["label"] == "Department Attendance Gap"


# ------------------------------------------------------------------------------
# Test 12: Cross-Domain Benchmark Matrix (Target: Leakage Rate = 0%)
# ------------------------------------------------------------------------------

CROSS_DOMAIN_BENCHMARK_MATRIX = [
    {
        "name": "Workforce",
        "columns": ["Employee_ID", "Department", "Attendance_Days", "Approved_Leaves"],
        "sample": [{"Employee_ID": "E1", "Department": "Eng", "Attendance_Days": 15, "Approved_Leaves": 2}],
        "must_appear": ["attendance", "leave"],
        "must_never_appear": ["weekly sales", "store ranking", "fuel price"],
    },
    {
        "name": "Retail Sales",
        "columns": ["Store", "Date", "Weekly_Sales", "Holiday_Flag", "Fuel_Price"],
        "sample": [{"Store": 1, "Date": "2020-01-01", "Weekly_Sales": 1200000, "Holiday_Flag": 0, "Fuel_Price": 2.5}],
        "must_appear": ["sales", "store"],
        "must_never_appear": ["attendance", "leave", "office presence", "policy compliance"],
    },
    {
        "name": "Finance",
        "columns": ["Account", "Date", "Gross_Revenue", "COGS", "Operating_Margin"],
        "sample": [{"Account": "A1", "Date": "2020-01-01", "Gross_Revenue": 500000, "COGS": 250000, "Operating_Margin": 20}],
        "must_appear": ["revenue", "margin", "total"],
        "must_never_appear": ["office presence", "leave rate", "attendance gap"],
    },
    {
        "name": "Academic",
        "columns": ["Student_ID", "Subject", "Final_Score", "Attendance_Pct", "Grade"],
        "sample": [{"Student_ID": "S101", "Subject": "Math", "Final_Score": 88, "Attendance_Pct": 95, "Grade": "A"}],
        "must_appear": ["score", "grade", "category"],
        "must_never_appear": ["weekly sales", "store ranking", "leave rate"],
    },
    {
        "name": "Operations",
        "columns": ["Ticket_ID", "Queue", "Resolution_Hours", "SLA_Met", "Backlog_Count"],
        "sample": [{"Ticket_ID": "T1", "Queue": "Billing", "Resolution_Hours": 4.5, "SLA_Met": 1, "Backlog_Count": 12}],
        "must_appear": ["resolution", "category", "total"],
        "must_never_appear": ["office presence", "holiday sales", "fuel price"],
    },
]


def test_cross_domain_leakage_rate_zero():
    """Executes cross-domain benchmark matrix to guarantee 0% cross-domain leakage rate."""
    total_checks = 0
    violations = []

    for benchmark in CROSS_DOMAIN_BENCHMARK_MATRIX:
        b_name = benchmark["name"]
        cols = benchmark["columns"]
        sample = benchmark["sample"]

        profile = DomainCapabilityGate.resolve_domain(
            columns=cols,
            sample_rows=sample,
            dataset_name=f"{b_name} Evaluation Set",
        )
        strategy = ExecutiveAnalyticsRegistry.resolve(profile.domain)
        result = strategy.compute(dataset_id=101, rows=sample, columns=cols, profile=profile)

        # Gather all text emitted in KPIs and topics
        kpi_text = " ".join(f"{k.get('label', '')} {k.get('subtext', '')}" for k in result.get("kpis", [])).lower()
        hero_text = (result.get("hero", {}).get("takeaway", "") + " " + result.get("hero", {}).get("action", "")).lower()
        combined_text = f"{kpi_text} {hero_text}"

        # Verify must_never_appear
        for forbidden in benchmark["must_never_appear"]:
            total_checks += 1
            if forbidden.lower() in combined_text:
                violations.append(f"Domain '{b_name}' leaked forbidden concept '{forbidden}' in: {combined_text}")

    leakage_rate = len(violations) / max(1, total_checks)
    assert leakage_rate == 0.0, f"Cross-domain leakage detected ({len(violations)} violations): {violations}"
