"""Test Suite for Phase 9.11: Policy & Business-Semantics Gate.

Verifies:
1. Policy thresholds come from governed rules (not hardcoded literals)
2. Time-period eligibility is respected (calendar weeks × 3d/week)
3. Approved exceptions are handled correctly (approved leave reduces net target)
4. Units are semantically correct (% for rates, days for gap)
5. KPI names match their formulas (Office Presence Rate, Policy Compliance, Approved Leave Rate, Department Attendance Gap)
6. Scenario baselines inherit the exact same policy definitions for Phase 10
7. Evidence modals convey full mathematical and policy provenance
"""
from __future__ import annotations

import sqlite3
import pytest

from app.services.adaptive_dashboard.executive_analytics import (
    compute_governed_executive_metrics,
)
from app.services.adaptive_dashboard.policy_engine import (
    EmployeeComplianceRecord,
    PolicyCalendarEngine,
    PolicyCalendarRule,
    PolicyComplianceResult,
)


def test_policy_thresholds_come_from_governed_rules():
    """Verify that policy thresholds derive strictly from PolicyCalendarRule, not hardcoded magic numbers."""
    engine_standard = PolicyCalendarEngine(PolicyCalendarRule(target_days_per_week=3.0, default_period_work_weeks=5.0))
    assert engine_standard.compute_baseline_benchmark() == 15.0

    # Policy lever variation: 2 days/week
    engine_hybrid = PolicyCalendarEngine(PolicyCalendarRule(target_days_per_week=2.0, default_period_work_weeks=5.0))
    assert engine_hybrid.compute_baseline_benchmark() == 10.0

    # Policy lever variation: 4 days/week
    engine_strict = PolicyCalendarEngine(PolicyCalendarRule(target_days_per_week=4.0, default_period_work_weeks=5.0))
    assert engine_strict.compute_baseline_benchmark() == 20.0


def test_time_period_eligibility_and_calendar_cycles():
    """Verify that different time periods and working week lengths adjust the baseline threshold."""
    engine = PolicyCalendarEngine(PolicyCalendarRule(target_days_per_week=3.0))

    # Standard 4-week reporting month (e.g. February)
    assert engine.compute_baseline_benchmark(period_weeks=4.0) == 12.0

    # 5-week tracking cycle (e.g. July with 5 periods)
    assert engine.compute_baseline_benchmark(period_weeks=5.0) == 15.0

    # Partial period (e.g. 2.5 weeks)
    assert engine.compute_baseline_benchmark(period_weeks=2.5) == 7.5


def test_approved_leave_exceptions_are_handled_correctly():
    """Verify that approved leave exceptions reduce required office attendance target.

    Formula:
        RequiredOfficeDays(employee, period) = max(0, eligible_work_weeks × 3 - applicable_exemptions)
    """
    engine = PolicyCalendarEngine(PolicyCalendarRule(target_days_per_week=3.0, default_period_work_weeks=5.0))

    # Employee A: 14 days attendance, 0 leave -> target 15d -> NON-COMPLIANT
    gross_a, exempt_a, net_a = engine.calculate_employee_target(eligible_weeks=5.0, approved_leaves=0.0)
    assert gross_a == 15.0
    assert exempt_a == 0.0
    assert net_a == 15.0

    # Employee B: 14 days attendance, 1 day approved leave -> target 14d -> COMPLIANT
    gross_b, exempt_b, net_b = engine.calculate_employee_target(eligible_weeks=5.0, approved_leaves=1.0)
    assert gross_b == 15.0
    assert exempt_b == 1.0
    assert net_b == 14.0

    # Employee C: 10 days attendance, 6 days approved leave -> target 9d -> COMPLIANT
    gross_c, exempt_c, net_c = engine.calculate_employee_target(eligible_weeks=5.0, approved_leaves=6.0)
    assert gross_c == 15.0
    assert exempt_c == 6.0
    assert net_c == 9.0

    # Evaluate workforce batch
    mock_workforce = [
        {"Employee ID": "A", "Department": "Tech", "Total Attendance": 14.0, "Approved Leaves": 0.0},
        {"Employee ID": "B", "Department": "Tech", "Total Attendance": 14.0, "Approved Leaves": 1.0},
        {"Employee ID": "C", "Department": "Tech", "Total Attendance": 10.0, "Approved Leaves": 6.0},
    ]
    res = engine.evaluate_workforce(mock_workforce)
    assert res.eligible_count == 3
    assert res.compliant_count == 2  # B and C are compliant; A is not
    assert res.compliance_rate == 66.7


def test_kpi_semantic_names_and_units_match_formulas():
    """Verify that KPI names, units, and definitions strictly match business semantics.

    - Office Presence Rate: '%' (NOT 'Average Office Presence' to prevent confusion with days)
    - Policy Compliance: '%'
    - Approved Leave Rate: '%'
    - Department Attendance Gap: 'days' (NOT 'Department Gap')
    """
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("CREATE TABLE sheets (id INTEGER PRIMARY KEY, dataset_id INTEGER, name TEXT, columns_json TEXT, row_count INTEGER)")
    conn.execute("CREATE TABLE sheet_curated_rows (sheet_id INTEGER, row_index INTEGER, data_json TEXT)")
    conn.execute("CREATE TABLE sheet_rows (sheet_id INTEGER, row_index INTEGER, data_json TEXT)")

    import json
    conn.execute("INSERT INTO sheets VALUES (1, 555, 'S1', '[\"Department\", \"Total Attendance\", \"Approved Leaves\"]', 2)")
    conn.execute("INSERT INTO sheet_rows VALUES (1, 1, '{\"Department\": \"Eng\", \"Total Attendance\": 18.0, \"Approved Leaves\": 2.0}')")
    conn.execute("INSERT INTO sheet_rows VALUES (1, 2, '{\"Department\": \"Ops\", \"Total Attendance\": 12.0, \"Approved Leaves\": 1.0}')")
    conn.commit()

    metrics = compute_governed_executive_metrics(555, conn=conn)
    kpis = {k["kpi_id"]: k for k in metrics["kpis"]}

    # KPI-001: Office Presence Rate
    kpi_1 = kpis["KPI-001"]
    assert kpi_1["label"] == "Office Presence Rate"
    assert kpi_1["formatted_value"].endswith("%")
    assert "qualifying office days" in kpi_1["definition"]
    assert "SUM(actual_attendance_days)" in kpi_1["calculation"]

    # KPI-002: Policy Compliance
    kpi_2 = kpis["KPI-002"]
    assert kpi_2["label"] == "Policy Compliance"
    assert kpi_2["formatted_value"].endswith("%")
    assert "3d/wk" in kpi_2["subtext"] or "3 days" in kpi_2["definition"]
    assert "approved_leave" in kpi_2["calculation"]

    # KPI-003: Approved Leave Rate
    kpi_3 = kpis["KPI-003"]
    assert kpi_3["label"] == "Approved Leave Rate"
    assert kpi_3["formatted_value"].endswith("%")
    assert "approved leave days" in kpi_3["definition"].lower()

    # KPI-004: Department Attendance Gap
    kpi_4 = kpis["KPI-004"]
    assert kpi_4["label"] == "Department Attendance Gap"
    assert kpi_4["formatted_value"].endswith("days")
    assert "MAX(department_average" in kpi_4["calculation"]
    assert "MIN(department_average" in kpi_4["calculation"]

    conn.close()


def test_scenario_baselines_inherit_same_policy_definitions():
    """Verify that Phase 10 Scenario Explorer simulation can tune governed policy levers

    while inheriting the identical baseline calculation engine.
    """
    baseline_rule = PolicyCalendarRule(target_days_per_week=3.0, default_period_work_weeks=5.0)
    baseline_engine = PolicyCalendarEngine(baseline_rule)

    scenario_relaxed_rule = PolicyCalendarRule(target_days_per_week=2.0, default_period_work_weeks=5.0)
    scenario_relaxed_engine = PolicyCalendarEngine(scenario_relaxed_rule)

    test_population = [
        {"Employee ID": "E1", "Department": "Design", "Total Attendance": 11.0, "Approved Leaves": 0.0},
        {"Employee ID": "E2", "Department": "Design", "Total Attendance": 13.0, "Approved Leaves": 0.0},
        {"Employee ID": "E3", "Department": "Engineering", "Total Attendance": 16.0, "Approved Leaves": 0.0},
    ]

    base_res = baseline_engine.evaluate_workforce(test_population)
    relaxed_res = scenario_relaxed_engine.evaluate_workforce(test_population)

    # Under 3d/week (15d target): only E3 complies (1 out of 3 = 33.3%)
    assert base_res.compliant_count == 1
    assert base_res.compliance_rate == 33.3
    assert base_res.baseline_benchmark_days == 15.0

    # Under 2d/week (10d target): all 3 comply (3 out of 3 = 100.0%)
    assert relaxed_res.compliant_count == 3
    assert relaxed_res.compliance_rate == 100.0
    assert relaxed_res.baseline_benchmark_days == 10.0


def test_boundary_and_zero_exemption_conditions():
    """Verify mathematical boundaries: net target must never drop below 0.0."""
    engine = PolicyCalendarEngine(PolicyCalendarRule(target_days_per_week=3.0, default_period_work_weeks=5.0))

    # Employee on extended approved medical leave (20 days)
    gross, exempt, net = engine.calculate_employee_target(eligible_weeks=5.0, approved_leaves=20.0)
    assert gross == 15.0
    assert exempt == 20.0
    assert net == 0.0  # Must be bounded at min_required_days >= 0


def test_evidence_modal_contains_governed_policy_breakdown():
    """Verify that analytics results expose full policy rule documentation for evidence modals."""
    import json
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("CREATE TABLE sheets (id INTEGER PRIMARY KEY, dataset_id INTEGER, name TEXT, columns_json TEXT, row_count INTEGER)")
    conn.execute("CREATE TABLE sheet_curated_rows (sheet_id INTEGER, row_index INTEGER, data_json TEXT)")
    conn.execute("CREATE TABLE sheet_rows (sheet_id INTEGER, row_index INTEGER, data_json TEXT)")

    conn.execute("INSERT INTO sheets VALUES (1, 777, 'S1', '[\"Department\", \"Total Attendance\", \"Approved Leaves\"]', 1)")
    conn.execute("INSERT INTO sheet_rows VALUES (1, 1, '{\"Department\": \"Sales\", \"Total Attendance\": 16.0, \"Approved Leaves\": 1.0}')")
    conn.commit()

    metrics = compute_governed_executive_metrics(777, conn=conn)
    kpis = {k["kpi_id"]: k for k in metrics["kpis"]}
    hero = metrics["hero"]

    # Hero benchmark configuration
    assert hero["benchmark"] == 15.0
    assert "3d/wk" in hero["benchmark_label"]
    assert "policy_rule" in hero
    assert "policy_summary" in hero
    assert hero["policy_summary"]["target_days_per_week"] == 3.0

    # Compliance KPI evidence
    kpi_comp = kpis["KPI-002"]
    assert "policy_rule" in kpi_comp
    assert "3 days/week" in kpi_comp["policy_rule"]
    assert "approved leave" in kpi_comp["definition"].lower()

    conn.close()
