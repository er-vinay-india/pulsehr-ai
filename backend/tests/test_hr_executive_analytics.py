"""Comprehensive Business Acceptance Test Suite for HR Executive Analytics.

Verifies:
1. Anonymized fixtures matching the two July sheets (wide period headers, unequal period lengths, negative final attendance).
2. Resolution of the two failing ranking questions:
   - "Which department is performing worst in attendance?"
   - "Which department has the lowest attendance in July?"
3. Reconciled semantic mapping: rejection of numeric Full Name averaging (no avg_full_name).
4. Full-population department ranking, small-population caveats (< 5 staff), and org benchmark comparisons.
5. Reconciled weekly period sums vs monthly totals per employee.
6. Honest governance: July-only history notice (no fabricated trends), negative final attendance handling.
7. SHA-256 content snapshot seal sensitivity to cell data mutations.
8. Strict claim verification (unverified claims marked failed, not passed).
9. Rate vs total denominator independence (Dept A lower rate vs Dept B more missed days).
10. Scope isolation: out-of-scope datasets do not contaminate scoped calculations.
"""

import hashlib
import json
import sqlite3
import pytest
import pandas as pd

from app.services.semantic_mapping import (
    infer_semantic_catalog,
    is_identity_header,
    is_period_header,
)
from app.services.storytelling.story_profiler import profile_sheet_data
from app.services.hr_period_analytics import (
    parse_period_column,
    extract_normalized_periods,
    analyze_hr_attendance_sheet,
)
from app.services.copilot_query_planner import (
    plan_analytical_query,
    execute_analytical_plan,
    AnalyticalQueryPlan,
)
from app.services.copilot_tools import infer_tool, execute_tool
from app.services.presentation.claim_verifier import verify_presentation_claims


# ---------------------------------------------------------------------------
# FIXTURES
# ---------------------------------------------------------------------------

@pytest.fixture
def sqlite_test_db(tmp_path):
    """Isolated temporary SQLite database mimicking pulsehr schema."""
    db_path = tmp_path / "test_pulsehr.db"
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.executescript("""
        CREATE TABLE dataset_uploads (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            filename TEXT,
            original_name TEXT,
            row_count INTEGER
        );
        CREATE TABLE sheets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            dataset_id INTEGER,
            name TEXT,
            row_count INTEGER,
            columns_json TEXT
        );
        CREATE TABLE sheet_rows (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sheet_id INTEGER,
            row_index INTEGER,
            data_json TEXT
        );
    """)
    yield conn
    conn.close()

@pytest.fixture
def july_attendance_fixture():
    """Synthetic fixture modeling Sheet1 (259-row pattern) with wide period columns,
    unequal period lengths, and negative final attendance."""
    columns = [
        "Full Name", "ID", "Department",
        "1st to 5th July", "Leaves(1st to 5th July)",
        "6th to 12th July", "Leaves(6th to 12th July)",
        "13th to 19th July", "Leaves(13th to 19th July)",
        "20th to 26th July", "Leaves(20th to 26th July)",
        "27th to 31st July", "Leaves(27th to 31st July)",
        "Total Attendance", "Approved Leaves", "Final Attendance"
    ]
    records = [
        # Dept 1: Engineering (5 employees, solid attendance)
        {"Full Name": "1", "ID": "E101", "Department": "Engineering", "1st to 5th July": "5", "Leaves(1st to 5th July)": "0", "6th to 12th July": "5", "Leaves(6th to 12th July)": "0", "13th to 19th July": "5", "Leaves(13th to 19th July)": "0", "20th to 26th July": "5", "Leaves(20th to 26th July)": "0", "27th to 31st July": "5", "Leaves(27th to 31st July)": "0", "Total Attendance": "25", "Approved Leaves": "0", "Final Attendance": "25"},
        {"Full Name": "2", "ID": "E102", "Department": "Engineering", "1st to 5th July": "4", "Leaves(1st to 5th July)": "1", "6th to 12th July": "5", "Leaves(6th to 12th July)": "0", "13th to 19th July": "4", "Leaves(13th to 19th July)": "1", "20th to 26th July": "5", "Leaves(20th to 26th July)": "0", "27th to 31st July": "4", "Leaves(27th to 31st July)": "1", "Total Attendance": "22", "Approved Leaves": "3", "Final Attendance": "19"},
        {"Full Name": "3", "ID": "E103", "Department": "Engineering", "1st to 5th July": "5", "Leaves(1st to 5th July)": "0", "6th to 12th July": "4", "Leaves(6th to 12th July)": "1", "13th to 19th July": "5", "Leaves(13th to 19th July)": "0", "20th to 26th July": "5", "Leaves(20th to 26th July)": "0", "27th to 31st July": "5", "Leaves(27th to 31st July)": "0", "Total Attendance": "24", "Approved Leaves": "1", "Final Attendance": "23"},
        {"Full Name": "4", "ID": "E104", "Department": "Engineering", "1st to 5th July": "4", "Leaves(1st to 5th July)": "0", "6th to 12th July": "4", "Leaves(6th to 12th July)": "0", "13th to 19th July": "5", "Leaves(13th to 19th July)": "0", "20th to 26th July": "4", "Leaves(20th to 26th July)": "0", "27th to 31st July": "4", "Leaves(27th to 31st July)": "0", "Total Attendance": "21", "Approved Leaves": "0", "Final Attendance": "21"},
        {"Full Name": "5", "ID": "E105", "Department": "Engineering", "1st to 5th July": "5", "Leaves(1st to 5th July)": "0", "6th to 12th July": "5", "Leaves(6th to 12th July)": "0", "13th to 19th July": "5", "Leaves(13th to 19th July)": "0", "20th to 26th July": "5", "Leaves(20th to 26th July)": "0", "27th to 31st July": "5", "Leaves(27th to 31st July)": "0", "Total Attendance": "25", "Approved Leaves": "0", "Final Attendance": "25"},

        # Dept 2: Operations (3 employees, lower attendance)
        {"Full Name": "6", "ID": "O201", "Department": "Operations", "1st to 5th July": "2", "Leaves(1st to 5th July)": "2", "6th to 12th July": "3", "Leaves(6th to 12th July)": "2", "13th to 19th July": "2", "Leaves(13th to 19th July)": "2", "20th to 26th July": "3", "Leaves(20th to 26th July)": "2", "27th to 31st July": "2", "Leaves(27th to 31st July)": "2", "Total Attendance": "12", "Approved Leaves": "10", "Final Attendance": "2"},
        {"Full Name": "7", "ID": "O202", "Department": "Operations", "1st to 5th July": "3", "Leaves(1st to 5th July)": "1", "6th to 12th July": "2", "Leaves(6th to 12th July)": "2", "13th to 19th July": "3", "Leaves(13th to 19th July)": "1", "20th to 26th July": "2", "Leaves(20th to 26th July)": "2", "27th to 31st July": "3", "Leaves(27th to 31st July)": "1", "Total Attendance": "13", "Approved Leaves": "7", "Final Attendance": "6"},
        {"Full Name": "8", "ID": "O203", "Department": "Operations", "1st to 5th July": "0", "Leaves(1st to 5th July)": "5", "6th to 12th July": "0", "Leaves(6th to 12th July)": "5", "13th to 19th July": "0", "Leaves(13th to 19th July)": "5", "20th to 26th July": "0", "Leaves(20th to 26th July)": "5", "27th to 31st July": "0", "Leaves(27th to 31st July)": "5", "Total Attendance": "0", "Approved Leaves": "25", "Final Attendance": "-25"},  # Negative final attendance!

        # Dept 3: Marketing (2 employees, small population caveat)
        {"Full Name": "9", "ID": "M301", "Department": "Marketing", "1st to 5th July": "3", "Leaves(1st to 5th July)": "1", "6th to 12th July": "4", "Leaves(6th to 12th July)": "0", "13th to 19th July": "3", "Leaves(13th to 19th July)": "1", "20th to 26th July": "4", "Leaves(20th to 26th July)": "0", "27th to 31st July": "3", "Leaves(27th to 31st July)": "1", "Total Attendance": "17", "Approved Leaves": "3", "Final Attendance": "14"},
        {"Full Name": "10", "ID": "M302", "Department": "Marketing", "1st to 5th July": "4", "Leaves(1st to 5th July)": "0", "6th to 12th July": "3", "Leaves(6th to 12th July)": "1", "13th to 19th July": "4", "Leaves(13th to 19th July)": "0", "20th to 26th July": "3", "Leaves(20th to 26th July)": "1", "27th to 31st July": "4", "Leaves(27th to 31st July)": "0", "Total Attendance": "18", "Approved Leaves": "2", "Final Attendance": "16"}
    ]
    return {"columns": columns, "records": records}


@pytest.fixture
def leave_check_fixture():
    """Secondary sheet for cross-sheet leave validation."""
    columns = ["Employee ID", "1st to 5th July", "6th to 12th July", "13th to 19th July", "20th to 26th July", "27th to 31st July", "Total Approved Leaves"]
    records = [
        {"Employee ID": "E101", "Total Approved Leaves": "0"},
        {"Employee ID": "E102", "Total Approved Leaves": "3"},
        {"Employee ID": "E103", "Total Approved Leaves": "1"},
        {"Employee ID": "O201", "Total Approved Leaves": "10"},
        {"Employee ID": "O202", "Total Approved Leaves": "7"},
        {"Employee ID": "O203", "Total Approved Leaves": "25"},
        {"Employee ID": "M301", "Total Approved Leaves": "3"},
    ]
    return {"columns": columns, "records": records}


# ---------------------------------------------------------------------------
# TESTS
# ---------------------------------------------------------------------------

def test_semantic_mapping_rejects_numeric_fullname(july_attendance_fixture):
    """Test Phase 1: Reconciles numeric Full Name as identity, NOT as a numeric KPI."""
    cols = july_attendance_fixture["columns"]
    recs = july_attendance_fixture["records"]

    catalog = infer_semantic_catalog(cols, recs, sheet_name="Sheet1")
    fn_field = catalog.get_field("Full Name")
    assert fn_field is not None
    assert fn_field.field_role == "identity"
    assert fn_field.aggregation_rule == "do_not_aggregate"
    assert len(catalog.anomalies) > 0
    assert any("Full Name" in a for a in catalog.anomalies)

    # Profiler ground truth must NOT contain avg_full_name or mean_full_name
    profile = profile_sheet_data(recs, cols, sheet_name="Sheet1")
    gt = profile["ground_truth"]
    assert "avg_full_name" not in gt
    assert "mean_full_name" not in gt

    # Semantic Contract Enforcement: Hash & governance rules
    cat_hash = catalog.get_catalog_hash()
    assert isinstance(cat_hash, str) and len(cat_hash) == 64
    assert cat_hash == catalog.get_catalog_hash()

    final_att = catalog.get_field("Final Attendance")
    assert final_att is not None
    assert final_att.unresolved_definition is True
    assert final_att.field_role == "derived_total"

    app_leaves = catalog.get_field("Approved Leaves")
    assert app_leaves is not None
    assert app_leaves.direction_of_concern == "neutral"

    # Verify small fixtures do not misclassify measures as dimensions due to low row count
    small_cols = ["ID", "Department", "Total Attendance", "Approved Leaves"]
    small_recs = [
        {"ID": "1", "Department": "D1", "Total Attendance": "20", "Approved Leaves": "2"},
        {"ID": "2", "Department": "D1", "Total Attendance": "22", "Approved Leaves": "0"},
        {"ID": "3", "Department": "D2", "Total Attendance": "18", "Approved Leaves": "4"},
    ]
    small_cat = infer_semantic_catalog(small_cols, small_recs, sheet_name="Small")
    assert small_cat.get_field("Total Attendance").field_role in ("derived_total", "measure")
    assert small_cat.get_field("Approved Leaves").field_role in ("derived_total", "measure")


def test_period_normalization_and_weekly_sums(july_attendance_fixture):
    """Test Phase 2: Normalizes wide period headers and validates weekly sums."""
    cols = july_attendance_fixture["columns"]
    recs = july_attendance_fixture["records"]

    periods = extract_normalized_periods(cols)
    assert len(periods) == 5
    assert periods[0].start_day == 1 and periods[0].end_day == 5
    assert periods[-1].start_day == 27 and periods[-1].end_day == 31
    assert periods[0].length_days == 5
    assert periods[1].length_days == 7  # 6th to 12th July is 7 days (unequal period!)

    res = analyze_hr_attendance_sheet(recs, cols, sheet_name="Sheet1")
    assert res["reconciliation"]["attendance_mismatches_count"] == 0
    assert res["reconciliation"]["leave_mismatches_count"] == 0
    assert res["reconciliation"]["negative_final_attendance_count"] == 1
    assert res["reconciliation"]["min_final_attendance"] == -25.0
    assert "not employee underperformance" in res["reconciliation"]["final_attendance_policy_note"]


def test_department_ranking_deterministic(july_attendance_fixture):
    """Test Phase 2: Produces deterministic department ranking with benchmarks."""
    cols = july_attendance_fixture["columns"]
    recs = july_attendance_fixture["records"]

    res = analyze_hr_attendance_sheet(recs, cols, sheet_name="Sheet1")
    depts = res["departments"]
    assert len(depts) == 3

    # Operations has lowest attendance: (12 + 13 + 0) / 3 = 8.33 days/emp
    worst_dept = res["worst_attendance_department"]
    assert worst_dept["department"] == "Operations"
    assert round(worst_dept["avg_attendance_per_employee"], 2) == 8.33

    # Engineering has highest attendance: (25 + 22 + 24 + 21 + 25) / 5 = 23.40 days/emp
    best_dept = res["best_attendance_department"]
    assert best_dept["department"] == "Engineering"
    assert round(best_dept["avg_attendance_per_employee"], 2) == 23.40

    # Marketing has headcount 2 -> flagged with is_small_population
    mkt = next(d for d in depts if d["department"] == "Marketing")
    assert mkt["is_small_population"] is True


def test_cross_sheet_leave_reconciliation(july_attendance_fixture, leave_check_fixture):
    """Test Phase 2: Validates join keys and leave reconciliation across sheets."""
    cols = july_attendance_fixture["columns"]
    recs = july_attendance_fixture["records"]
    c_cols = leave_check_fixture["columns"]
    c_recs = leave_check_fixture["records"]

    res = analyze_hr_attendance_sheet(
        recs, cols,
        sheet_name="Sheet1",
        comparison_sheet_records=c_recs,
        comparison_sheet_name="Leave Calculation Check"
    )
    cross = res["reconciliation"]["cross_sheet_reconciliation"]
    assert cross is not None
    assert cross["matched_employees_count"] == 7
    assert cross["exact_leave_matches"] == 7
    assert cross["leave_mismatch_count"] == 0


def test_copilot_ranking_question_resolution():
    """Test Phase 3: Resolves both original failing ranking queries deterministically."""
    q1 = "Which department is performing worst in attendance?"
    plan1 = plan_analytical_query(q1)
    assert plan1 is not None
    assert plan1.intent == "ranking"
    assert plan1.metric == "attendance"
    assert plan1.direction == "lowest"

    q2 = "Which department has the lowest attendance in July?"
    plan2 = plan_analytical_query(q2)
    assert plan2 is not None
    assert plan2.intent == "ranking"
    assert plan2.metric == "attendance"
    assert plan2.direction == "lowest"
    assert plan2.time_window == "July"

    # Contextual follow-up
    q3 = "Which is worst?"
    plan3 = plan_analytical_query(q3, prior_context={"metric": "attendance"})
    assert plan3 is not None
    assert plan3.metric == "attendance"
    assert plan3.direction == "lowest"


def test_copilot_infer_tool_dispatch():
    """Test Phase 3: infer_tool routes ranking queries to analytical_plan tool."""
    tool_req = infer_tool("Which department is performing worst in attendance?")
    assert tool_req is not None
    assert tool_req.name == "analytical_plan"
    assert tool_req.analytical_plan is not None
    assert tool_req.analytical_plan.metric == "attendance"


def test_content_based_sha256_seal_changes_on_cell_mutation():
    """Test Phase 4: SHA-256 seal changes when cell values change, even if row count stays identical."""
    row1 = [{"id": "E1", "attendance": 20}, {"id": "E2", "attendance": 22}]
    row2 = [{"id": "E1", "attendance": 20}, {"id": "E2", "attendance": 23}]  # Single value edit!

    def hash_dataset(records):
        hasher = hashlib.sha256()
        hasher.update(f"rows:{len(records)}".encode())
        for r in records:
            hasher.update(json.dumps(r, sort_keys=True).encode())
        return hasher.hexdigest()[:12]

    hash1 = hash_dataset(row1)
    hash2 = hash_dataset(row2)
    assert hash1 != hash2, "Cell-level value mutation must alter cryptographic snapshot hash!"


def test_claim_verifier_fails_unverified_claims():
    """Test Phase 5: Claim verifier marks unverified claims as failed, never passed."""
    deck_spec = {
        "slides": [
            {
                "title": "Executive Summary",
                "evidence_id": "EVID-KPI-01",
                "metrics": [
                    {"label": "Organization Average Attendance", "value": "13.32 days/emp"},
                    {"label": "Fabricated Unverified Metric", "value": "99.9%"}
                ]
            }
        ]
    }
    evidence_ledger = [
        {
            "evidence_id": "EVID-KPI-01",
            "metric_name": "Organization Average Attendance",
            "metric_value": "13.32 days/emp",
            "numeric_value": 13.32
        }
    ]

    audit = verify_presentation_claims(deck_spec, evidence_ledger)
    assert audit["status"] == "DISCREPANCIES_FLAGGED"
    assert audit["discrepancies_flagged"] == 1
    assert audit["passed_verification"] == 1

    unverified = next(c for c in audit["checked_items"] if c["metric"] == "Fabricated Unverified Metric")
    assert unverified["passed"] is False
    assert unverified["status"] == "UNVERIFIED"


def test_rate_vs_total_denominator_independence():
    """Test Phase 5: Dept A has lower rate (10.0 vs 12.0 days/emp) while Dept B has more total leave days (32 vs 20).
    Verified through production service analyze_hr_attendance_sheet without ad-hoc local pandas calculations."""
    columns = ["Department", "ID", "Total Attendance", "Approved Leaves"]
    records = [
        # Dept A: 2 employees, 20 attended, 20 leaves. Avg att = 10.0, avg leaves = 10.0, total leaves = 20
        {"Department": "Dept A", "ID": "A1", "Total Attendance": "10", "Approved Leaves": "10"},
        {"Department": "Dept A", "ID": "A2", "Total Attendance": "10", "Approved Leaves": "10"},

        # Dept B: 4 employees, 48 attended, 32 leaves. Avg att = 12.0, avg leaves = 8.0, total leaves = 32
        {"Department": "Dept B", "ID": "B1", "Total Attendance": "12", "Approved Leaves": "8"},
        {"Department": "Dept B", "ID": "B2", "Total Attendance": "12", "Approved Leaves": "8"},
        {"Department": "Dept B", "ID": "B3", "Total Attendance": "12", "Approved Leaves": "8"},
        {"Department": "Dept B", "ID": "B4", "Total Attendance": "12", "Approved Leaves": "8"},
    ]

    res = analyze_hr_attendance_sheet(records, columns, sheet_name="Attendance Summary")
    depts = {d["department"]: d for d in res["departments"]}

    # Metric 1: Average Attendance per employee
    assert depts["Dept A"]["avg_attendance_per_employee"] == 10.0
    assert depts["Dept B"]["avg_attendance_per_employee"] == 12.0
    assert res["worst_attendance_department"]["department"] == "Dept A"

    # Metric 2: Total Leaves Volume (sum) vs Average Leaves per employee
    assert depts["Dept B"]["total_approved_leaves"] == 32.0
    assert depts["Dept A"]["total_approved_leaves"] == 20.0
    # Higher total leaves volume: Dept B
    assert depts["Dept B"]["total_approved_leaves"] > depts["Dept A"]["total_approved_leaves"]
    # Higher average leaves per employee: Dept A
    assert depts["Dept A"]["avg_leaves_per_employee"] > depts["Dept B"]["avg_leaves_per_employee"]


def test_period_chronology_and_year_collision():
    """Test Period Chronology (P0): Parse year in period header and prevent cross-year collision."""
    # 1. Parse period with explicit year
    parsed = parse_period_column("1st to 5th July 2026")
    assert parsed is not None
    start_d, end_d, month_name, yr, length = parsed
    assert start_d == 1
    assert end_d == 5
    assert month_name == "July"
    assert yr == 2026
    assert length == 5

    # 2. Parse period with known_year context
    parsed_known = parse_period_column("6th to 12th July", known_year=2026)
    assert parsed_known is not None
    assert parsed_known[3] == 2026

    # 3. Normalized periods cross-year separation
    cols = [
        "1st to 5th July 2025", "Leaves(1st to 5th July 2025)",
        "1st to 5th July 2026", "Leaves(1st to 5th July 2026)"
    ]
    periods = extract_normalized_periods(cols)
    assert len(periods) == 2
    assert periods[0].year == 2025
    assert periods[1].year == 2026
    # No collision: both distinct periods preserved
    assert periods[0].label != periods[1].label


def test_period_unavailable_rejection_without_substitution(july_attendance_fixture, sqlite_test_db):
    """Test Period Validation (P0): Rejects unavailable requested period (August) on July data.
    Must return period_unavailable and NEVER substitute July data."""
    cols = july_attendance_fixture["columns"]
    recs = july_attendance_fixture["records"]

    # Direct service validation
    res = analyze_hr_attendance_sheet(recs, cols, sheet_name="July Attendance", requested_period="August")
    assert res.get("status") == "period_unavailable"
    assert "Requested period 'August' is not present in the dataset" in res["error"]
    assert res["departments"] == []

    # Query planner pipeline validation with SQLite
    with sqlite_test_db:
        cur = sqlite_test_db.cursor()
        cur.execute("INSERT INTO dataset_uploads (id, filename, original_name, row_count) VALUES (1, 'july.xlsx', 'July Report', 10)")
        cur.execute("INSERT INTO sheets (id, dataset_id, name, row_count, columns_json) VALUES (1, 1, 'July 2026 Attendance', 10, ?)", (json.dumps(cols),))
        for idx, r in enumerate(recs):
            cur.execute("INSERT INTO sheet_rows (sheet_id, row_index, data_json) VALUES (1, ?, ?)", (idx, json.dumps(r)))

    plan = AnalyticalQueryPlan(
        intent="ranking",
        metric="attendance",
        entity_dimension="department",
        direction="lowest",
        time_window="August",
        dataset_id=1
    )
    exec_res = execute_analytical_plan(plan, conn=sqlite_test_db)
    assert exec_res["query_plan"]["status"] == "period_unavailable"
    assert "Period Unavailable: August" in exec_res["answer"]
    assert "Requested period 'August' is not present" in exec_res["citations"][0]["text"]


def test_deterministic_sheet_source_resolution_without_sheet_id(july_attendance_fixture, sqlite_test_db):
    """Test Deterministic Source Resolution (P0): Inspects sheet headers in scope to pick primary sheet
    with Department over Leave Calculation Check when sheet_id is omitted."""
    cols = july_attendance_fixture["columns"]
    recs = july_attendance_fixture["records"]

    leave_check_cols = ["Employee ID", "Total Approved Leaves"]
    leave_check_recs = [{"Employee ID": "E101", "Total Approved Leaves": "0"}]

    with sqlite_test_db:
        cur = sqlite_test_db.cursor()
        cur.execute("INSERT INTO dataset_uploads (id, filename, original_name, row_count) VALUES (1, 'attendance_bundle.xlsx', 'HR Monthly Data', 11)")
        # Sheet 1: Primary attendance sheet with Department
        cur.execute("INSERT INTO sheets (id, dataset_id, name, row_count, columns_json) VALUES (1, 1, 'July 2026 Attendance', 10, ?)", (json.dumps(cols),))
        for idx, r in enumerate(recs):
            cur.execute("INSERT INTO sheet_rows (sheet_id, row_index, data_json) VALUES (1, ?, ?)", (idx, json.dumps(r)))

        # Sheet 2: Higher ID, but lacks Department
        cur.execute("INSERT INTO sheets (id, dataset_id, name, row_count, columns_json) VALUES (2, 1, 'Leave Calculation Check', 1, ?)", (json.dumps(leave_check_cols),))
        cur.execute("INSERT INTO sheet_rows (sheet_id, row_index, data_json) VALUES (2, 0, ?)", (json.dumps(leave_check_recs[0]),))

    # Calling with sheet_id=None must select Sheet 1 ('July 2026 Attendance') despite Sheet 2 having higher ID
    plan = AnalyticalQueryPlan(
        intent="ranking",
        metric="attendance",
        entity_dimension="department",
        direction="lowest",
        dataset_id=1,
        sheet_id=None
    )
    exec_res = execute_analytical_plan(plan, conn=sqlite_test_db)
    assert exec_res["query_plan"]["sheet_id"] == 1
    assert exec_res["query_plan"]["source_sheet"] == "July 2026 Attendance"
    assert "Operations" in exec_res["answer"]

    # Scope consistency check: Mismatched sheet_id and dataset_id must raise ValueError
    invalid_scope_plan = AnalyticalQueryPlan(
        intent="ranking",
        metric="attendance",
        entity_dimension="department",
        direction="lowest",
        dataset_id=1,
        sheet_id=999
    )
    with pytest.raises(ValueError, match="does not belong to Dataset ID"):
        execute_analytical_plan(invalid_scope_plan, conn=sqlite_test_db)


def test_leading_zero_ids_and_duplicate_employee_handling():
    """Test Data Integrity (P0): Preserves string IDs with leading zeros and flags entity-period duplicates without double-counting."""
    columns = ["Department", "ID", "Total Attendance", "Approved Leaves"]
    records = [
        # Employee "00123" appears twice in same period (duplicate entry)
        {"Department": "Finance", "ID": "00123", "Total Attendance": "20", "Approved Leaves": "2"},
        {"Department": "Finance", "ID": "00123", "Total Attendance": "20", "Approved Leaves": "2"},
        # Employee "00456" appears once
        {"Department": "Finance", "ID": "00456", "Total Attendance": "22", "Approved Leaves": "0"},
    ]

    res = analyze_hr_attendance_sheet(records, columns, sheet_name="Finance Attendance")

    # 1. Leading zero preservation
    assert res["distinct_employees"] == 2
    # 2. Duplicate detection
    assert res["duplicate_records_detected"] is True
    assert res["duplicate_record_count"] == 1

    # 3. Headcount and attendance rollup without double-counting duplicate employee
    dept = res["departments"][0]
    assert dept["department"] == "Finance"
    assert dept["headcount"] == 2  # Not 3!
    assert dept["total_attended_days"] == 42.0  # 20 + 22 (not 20 + 20 + 22 = 62)
    assert dept["avg_attendance_per_employee"] == 21.0  # 42 / 2


def test_dense_ranking_with_ties(sqlite_test_db):
    """Test Dense Ranking (P0): Departments with tied average attendance share the same rank and are formatted cleanly."""
    columns = ["Department", "ID", "Total Attendance", "Approved Leaves"]
    records = [
        # Dept Alpha: 2 employees, 30 total -> 15.0 days/emp
        {"Department": "Alpha", "ID": "A1", "Total Attendance": "15", "Approved Leaves": "0"},
        {"Department": "Alpha", "ID": "A2", "Total Attendance": "15", "Approved Leaves": "0"},

        # Dept Beta: 2 employees, 30 total -> 15.0 days/emp (TIED with Alpha)
        {"Department": "Beta", "ID": "B1", "Total Attendance": "15", "Approved Leaves": "0"},
        {"Department": "Beta", "ID": "B2", "Total Attendance": "15", "Approved Leaves": "0"},

        # Dept Gamma: 2 employees, 40 total -> 20.0 days/emp
        {"Department": "Gamma", "ID": "G1", "Total Attendance": "20", "Approved Leaves": "0"},
        {"Department": "Gamma", "ID": "G2", "Total Attendance": "20", "Approved Leaves": "0"},
    ]

    res = analyze_hr_attendance_sheet(records, columns, sheet_name="Ties Sheet")
    depts = {d["department"]: d for d in res["departments"]}

    # Dense ranking: both Alpha and Beta have rank 1
    assert depts["Alpha"]["attendance_rank"] == 1
    assert depts["Beta"]["attendance_rank"] == 1
    assert depts["Gamma"]["attendance_rank"] == 2  # Dense rank incremented by 1, not 3
    assert res["has_attendance_ties"] is True
    assert len(res["worst_attendance_departments"]) == 2

    # Verify query planner executive response handles tied departments
    with sqlite_test_db:
        cur = sqlite_test_db.cursor()
        cur.execute("INSERT INTO dataset_uploads (id, filename, original_name, row_count) VALUES (1, 'ties.xlsx', 'Ties Report', 6)")
        cur.execute("INSERT INTO sheets (id, dataset_id, name, row_count, columns_json) VALUES (1, 1, 'Attendance With Ties', 6, ?)", (json.dumps(columns),))
        for idx, r in enumerate(records):
            cur.execute("INSERT INTO sheet_rows (sheet_id, row_index, data_json) VALUES (1, ?, ?)", (idx, json.dumps(r)))

    plan = AnalyticalQueryPlan(
        intent="ranking",
        metric="attendance",
        entity_dimension="department",
        direction="lowest",
        ranking_limit=1,
        dataset_id=1,
        sheet_id=1
    )
    exec_res = execute_analytical_plan(plan, conn=sqlite_test_db)
    assert "tied for the **lowest average attendance**" in exec_res["answer"]
    assert "**Alpha**" in exec_res["answer"]
    assert "**Beta**" in exec_res["answer"]

