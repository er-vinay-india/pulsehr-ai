"""End-to-End Production Tests for Strategy Orchestrator & Correctness Guards.

Verifies:
- S01–S20 production eligibility, execution, and truthful coverage accounting.
- Retention of all valid orchestrator findings in authoritative findings response.
- Zero required exposure formatted as N/A, never 0%.
- Removal of invented 30-day calendar fallback.
- LoggedHours retaining hours, never days per employee.
- Entity grain verification before claiming per-employee averages.
- Schedule coverage requiring explicit policy and compatible units.
- Rejection of impossible exposure partitions.
- Total removal of unsupported HR attendance reliability calculations.
- Copilot metric and directional binding (highest attendance, lowest attendance, most employees, lowest leave).
"""
import json
import pytest
from fastapi.testclient import TestClient

from app.db.database import get_connection
from app.main import app
from app.services.adaptive_dashboard.engine import run_adaptive_dashboard
from app.services.adaptive_dashboard.findings import (
    extract_findings_from_response,
    get_shared_findings_for_sheet,
)
from app.routers.copilot import _answer_from_shared_findings


@pytest.fixture
def client():
    return TestClient(app)


def test_hr_workflow_correctness_and_parity():
    """HR dataset integration:
    - S01 requires verified schedule; without it, must be truthful 'needs_inputs'.
    - S09 evaluates segment disparity on recorded attendance without fake reliability formula.
    - Top finding matches Priority Insight in Dashboard, Findings Store, and Copilot.
    """
    conn = get_connection()
    try:
        conn.execute(
            "INSERT OR REPLACE INTO dataset_uploads (id, filename, original_name, display_name, file_type) VALUES (?, ?, ?, ?, ?)",
            (99001, "hr_test.csv", "hr_test.csv", "HR Roster Check", "csv"),
        )
        cols = ["Employee_ID", "Department", "Attendance_Days", "Approved_Leave_Days"]
        conn.execute(
            "INSERT OR REPLACE INTO sheets (id, dataset_id, name, display_name, columns_json, profile_json, row_count) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (99001, 99001, "Staff", "Staff Summary", json.dumps(cols), "{}", 12),
        )

        rows = []
        for i in range(1, 7):
            rows.append({"Employee_ID": f"E{i}", "Department": "Operations", "Attendance_Days": 18, "Approved_Leave_Days": 2})
        for i in range(7, 13):
            rows.append({"Employee_ID": f"E{i}", "Department": "Sales", "Attendance_Days": 21, "Approved_Leave_Days": 1})

        conn.execute("DELETE FROM sheet_curated_rows WHERE sheet_id=99001")
        conn.execute("DELETE FROM sheet_rows WHERE sheet_id=99001")
        for idx, r in enumerate(rows):
            conn.execute(
                "INSERT INTO sheet_rows (sheet_id, row_index, data_json) VALUES (?, ?, ?)",
                (99001, idx, json.dumps(r)),
            )
        conn.commit()

        # Run end-to-end adaptive dashboard
        resp = run_adaptive_dashboard(sheet_id=99001)
        assert resp.priority_insight is not None
        assert resp.analysis_coverage is not None
        assert resp.analysis_coverage.total_strategies == 20

        # Check S01: Must be needs_inputs (no schedule roster)
        s01_cov = next(s for s in resp.analysis_coverage.strategies if s.strategy_code == "S01")
        assert s01_cov.status == "needs_inputs"
        assert any("duty roster" in p.lower() or "schedule" in p.lower() for p in s01_cov.missing_prerequisites)

        # Check S09: Must be completed
        s09_cov = next(s for s in resp.analysis_coverage.strategies if s.strategy_code == "S09")
        assert s09_cov.status == "completed"

        # Check Priority Insight
        pi = resp.priority_insight
        assert pi.strategy_code == "S09"
        assert "Recorded Attendance" in pi.short_business_title or "Attendance" in pi.short_business_title
        # Must disclaim obligation coverage without roster
        assert any("duty roster not provided" in lim.lower() for lim in pi.evidence_details.get("limitations", []))

        # Check shared findings parity
        shared = get_shared_findings_for_sheet(sheet_id=99001)
        assert len(shared) >= 1
        top_sf = shared[0]
        assert top_sf.finding_id == pi.finding_id
        assert top_sf.formatted_value == pi.prominent_number

        # Strictly check that NO finding contains "Attendance Reliability" or old formula
        for f in shared:
            assert "attendance reliability" not in f.short_business_title.lower()
            assert "def_departmental_reliability_disparity_v1" != f.definition_id
    finally:
        conn.close()


def test_commerce_workflow_cost_preservation_and_tail_burden():
    """Commerce dataset integration:
    - S15 preserves missing costs (never assumes zero cost / fake profit).
    - S12 detects distribution skew on continuous sales revenue.
    """
    conn = get_connection()
    try:
        conn.execute(
            "INSERT OR REPLACE INTO dataset_uploads (id, filename, original_name, display_name, file_type) VALUES (?, ?, ?, ?, ?)",
            (99002, "commerce_test.csv", "commerce_test.csv", "Store Sales", "csv"),
        )
        cols = ["OrderID", "Customer", "Category", "Revenue"]
        conn.execute(
            "INSERT OR REPLACE INTO sheets (id, dataset_id, name, display_name, columns_json, profile_json, row_count) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (99002, 99002, "Orders", "Orders Data", json.dumps(cols), "{}", 15),
        )

        rows = [
            {"OrderID": f"O{i}", "Customer": f"C{i}", "Category": "Hardware", "Revenue": 50.0}
            for i in range(1, 13)
        ]
        rows.append({"OrderID": "O13", "Customer": "C13", "Category": "Enterprise", "Revenue": 1500.0})
        rows.append({"OrderID": "O14", "Customer": "C14", "Category": "Enterprise", "Revenue": 2000.0})
        rows.append({"OrderID": "O15", "Customer": "C15", "Category": "Enterprise", "Revenue": 2500.0})

        conn.execute("DELETE FROM sheet_curated_rows WHERE sheet_id=99002")
        conn.execute("DELETE FROM sheet_rows WHERE sheet_id=99002")
        for idx, r in enumerate(rows):
            conn.execute(
                "INSERT INTO sheet_rows (sheet_id, row_index, data_json) VALUES (?, ?, ?)",
                (99002, idx, json.dumps(r)),
            )
        conn.commit()

        resp = run_adaptive_dashboard(sheet_id=99002)
        assert resp.priority_insight is not None
        assert resp.analysis_coverage is not None

        # S15 must be needs_inputs because Cost is not provided (never invent zero cost)
        s15_cov = next(s for s in resp.analysis_coverage.strategies if s.strategy_code == "S15")
        assert s15_cov.status == "needs_inputs"
        assert any("cost" in p.lower() for p in s15_cov.missing_prerequisites)

        # S12 must be completed
        s12_cov = next(s for s in resp.analysis_coverage.strategies if s.strategy_code == "S12")
        assert s12_cov.status == "completed"
        assert len(s12_cov.generated_finding_ids) >= 1
    finally:
        conn.close()


def test_support_operations_workflow_and_pareto():
    """Support operations integration:
    - S08 evaluates Pareto distribution across incident categories.
    """
    conn = get_connection()
    try:
        conn.execute(
            "INSERT OR REPLACE INTO dataset_uploads (id, filename, original_name, display_name, file_type) VALUES (?, ?, ?, ?, ?)",
            (99003, "support_test.csv", "support_test.csv", "Support Desk", "csv"),
        )
        cols = ["TicketID", "IncidentType", "DurationMins"]
        conn.execute(
            "INSERT OR REPLACE INTO sheets (id, dataset_id, name, display_name, columns_json, profile_json, row_count) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (99003, 99003, "Tickets", "Incident Log", json.dumps(cols), "{}", 20),
        )

        rows = []
        for i in range(1, 15):
            rows.append({"TicketID": f"T{i}", "IncidentType": "Network Outage", "DurationMins": 45})
        for i in range(15, 18):
            rows.append({"TicketID": f"T{i}", "IncidentType": "Password Reset", "DurationMins": 10})
        for i in range(18, 21):
            rows.append({"TicketID": f"T{i}", "IncidentType": "Hardware Fault", "DurationMins": 90})

        conn.execute("DELETE FROM sheet_curated_rows WHERE sheet_id=99003")
        conn.execute("DELETE FROM sheet_rows WHERE sheet_id=99003")
        for idx, r in enumerate(rows):
            conn.execute(
                "INSERT INTO sheet_rows (sheet_id, row_index, data_json) VALUES (?, ?, ?)",
                (99003, idx, json.dumps(r)),
            )
        conn.commit()

        resp = run_adaptive_dashboard(sheet_id=99003)
        assert resp.priority_insight is not None
        assert resp.analysis_coverage is not None

        # S08 must be completed
        s08_cov = next(s for s in resp.analysis_coverage.strategies if s.strategy_code == "S08")
        assert s08_cov.status == "completed"
        assert len(s08_cov.generated_finding_ids) >= 1
    finally:
        conn.close()


def test_retention_of_multiple_orchestrator_findings():
    """All valid orchestrator findings must be retained in orchestrator_findings and shared findings."""
    conn = get_connection()
    try:
        conn.execute(
            "INSERT OR REPLACE INTO dataset_uploads (id, filename, original_name, display_name, file_type) VALUES (?, ?, ?, ?, ?)",
            (99005, "multi_test.csv", "multi_test.csv", "Multi Strategy Data", "csv"),
        )
        cols = ["Employee_ID", "Department", "Attendance_Days", "Reason", "Performance_Score"]
        conn.execute(
            "INSERT OR REPLACE INTO sheets (id, dataset_id, name, display_name, columns_json, profile_json, row_count) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (99005, 99005, "Data", "Multi Sheet", json.dumps(cols), "{}", 20),
        )

        rows = []
        for i in range(1, 11):
            rows.append({
                "Employee_ID": f"E{i}",
                "Department": "Engineering",
                "Attendance_Days": 20,
                "Reason": "Project Delivery",
                "Performance_Score": 88.0 + i,
            })
        for i in range(11, 21):
            rows.append({
                "Employee_ID": f"E{i}",
                "Department": "Marketing",
                "Attendance_Days": 16,
                "Reason": "Campaign Launch",
                "Performance_Score": 72.0 + i,
            })

        conn.execute("DELETE FROM sheet_curated_rows WHERE sheet_id=99005")
        conn.execute("DELETE FROM sheet_rows WHERE sheet_id=99005")
        for idx, r in enumerate(rows):
            conn.execute(
                "INSERT INTO sheet_rows (sheet_id, row_index, data_json) VALUES (?, ?, ?)",
                (99005, idx, json.dumps(r)),
            )
        conn.commit()

        resp = run_adaptive_dashboard(sheet_id=99005)
        # Must retain multiple valid orchestrator findings
        assert len(resp.orchestrator_findings) >= 2
        categories = {f.decision_category for f in resp.orchestrator_findings}
        assert "segment_disparity" in categories
        assert "friction_concentration" in categories or "spread_tail_burden" in categories

        # Authoritative shared findings must include all orchestrator findings
        shared = extract_findings_from_response(resp)
        assert len(shared) >= len(resp.orchestrator_findings)
        # Winner must be at index 0
        assert shared[0].finding_id == resp.priority_insight.finding_id
    finally:
        conn.close()


def test_zero_required_exposure_is_na_never_zero():
    """When required exposure is zero (all duty excused), attendance rate is N/A, never 0%."""
    from app.services.adaptive_dashboard.obligations import evaluate_scheduled_obligations
    res = evaluate_scheduled_obligations(
        total_calendar_days=30,
        scheduled_days=20.0,
        fulfilled_days=0.0,
        excused_days=20.0,  # All scheduled duty excused under policy
        policy_excludes_excused=True,
    )
    assert not res.is_applicable
    assert res.covered_rate is None
    assert "Attendance rate is not applicable" in res.what_it_does_not_establish


def test_no_invented_30_day_calendar_fallback():
    """When calendar dates are missing, S01 must report needs_inputs rather than defaulting to 30 days."""
    from app.services.adaptive_dashboard.contracts import SourceManifest, SemanticContract
    from app.services.adaptive_dashboard.orchestrator import orchestrate_sheet_strategies

    manifest = SourceManifest(
        sheet_id=99006, file_name="sched.csv", sheet_name="Roster",
        display_name="Roster", row_count=10, col_count=3, snapshot="test_snap",
        date_range=None,
    )
    contract = SemanticContract(
        layout="long_tabular", entity_type="employee", entity_identifiers=["EmpID"],
        distinct_entity_count=10, date_column=None, primary_measure="Roster_Days",
        grain_description="10 records", domain="workforce_hr",
        analyst_persona="HR Analyst", verified_mappings={}, unresolved_meanings=[],
        verification_basis="Direct mapping",
    )
    # Has roster column and attendance column, but NO date column
    rows = [{"EmpID": f"E{i}", "Roster_Days": 20, "Attendance_Days": 19} for i in range(10)]
    cov, findings, pi = orchestrate_sheet_strategies(99006, rows, manifest, contract)
    s01_item = next(s for s in cov.strategies if s.strategy_code == "S01")
    # Must report needs_inputs due to missing calendar dates
    assert s01_item.status == "needs_inputs"
    assert any("calendar" in p.lower() for p in s01_item.missing_prerequisites)


def test_logged_hours_retains_hours_not_days():
    """LoggedHours metric must retain 'hours', never be mislabeled as 'days per employee'."""
    from app.services.adaptive_dashboard.contracts import SourceManifest, SemanticContract
    from app.services.adaptive_dashboard.orchestrator import orchestrate_sheet_strategies

    manifest = SourceManifest(
        sheet_id=99007, file_name="hours.csv", sheet_name="Timesheet",
        display_name="Timesheet", row_count=14, col_count=3, snapshot="snap7",
        date_range=None,
    )
    contract = SemanticContract(
        layout="long_tabular", entity_type="employee", entity_identifiers=["EmpID"],
        distinct_entity_count=14, date_column=None, primary_measure="LoggedHours",
        grain_description="14 records", domain="workforce_hr",
        analyst_persona="HR Analyst", verified_mappings={}, unresolved_meanings=[],
        verification_basis="Direct mapping",
    )
    rows = []
    for i in range(1, 8):
        rows.append({"EmpID": f"E{i}", "Department": "TeamA", "LoggedHours": 160.0})
    for i in range(8, 15):
        rows.append({"EmpID": f"E{i}", "Department": "TeamB", "LoggedHours": 140.0})

    cov, findings, pi = orchestrate_sheet_strategies(99007, rows, manifest, contract)
    s09_finding = next((f for f in findings if f.decision_category == "segment_disparity"), None)
    assert s09_finding is not None
    # Must retain hours unit
    assert "hours" in s09_finding.unit.lower()
    assert "presence days" not in s09_finding.formatted_value.lower()
    assert "days/emp" not in s09_finding.formatted_value.lower()


def test_entity_grain_verified_before_claiming_per_employee():
    """Order/ticket datasets must not claim 'per employee'."""
    from app.services.adaptive_dashboard.contracts import SourceManifest, SemanticContract
    from app.services.adaptive_dashboard.orchestrator import orchestrate_sheet_strategies

    manifest = SourceManifest(
        sheet_id=99008, file_name="tickets.csv", sheet_name="Tickets",
        display_name="Tickets", row_count=16, col_count=3, snapshot="snap8",
        date_range=None,
    )
    contract = SemanticContract(
        layout="long_tabular", entity_type="ticket", entity_identifiers=["TicketID"],
        distinct_entity_count=16, date_column=None, primary_measure="DurationMins",
        grain_description="16 records", domain="operations_support",
        analyst_persona="Support Analyst", verified_mappings={}, unresolved_meanings=[],
        verification_basis="Direct mapping",
    )
    rows = []
    for i in range(1, 9):
        rows.append({"TicketID": f"T{i}", "Department": "Tier1", "DurationMins": 25.0})
    for i in range(9, 17):
        rows.append({"TicketID": f"T{i}", "Department": "Tier2", "DurationMins": 65.0})

    cov, findings, pi = orchestrate_sheet_strategies(99008, rows, manifest, contract)
    s09_finding = next((f for f in findings if f.decision_category == "segment_disparity"), None)
    assert s09_finding is not None
    # Must not claim per employee
    assert "per employee" not in s09_finding.possible_operational_implication.lower()
    assert "/emp" not in s09_finding.unit.lower()


def test_schedule_coverage_incompatible_units():
    """Schedule column in hours and attendance in days must be flagged incompatible."""
    from app.services.adaptive_dashboard.contracts import SourceManifest, SemanticContract
    from app.services.adaptive_dashboard.orchestrator import orchestrate_sheet_strategies

    manifest = SourceManifest(
        sheet_id=99009, file_name="mismatch.csv", sheet_name="Mismatch",
        display_name="Mismatch", row_count=10, col_count=4, snapshot="snap9",
        date_range={"formatted": "2026-01-01 to 2026-01-30"},
    )
    contract = SemanticContract(
        layout="long_tabular", entity_type="employee", entity_identifiers=["EmpID"],
        distinct_entity_count=10, date_column="Date", primary_measure="WorkedDays",
        grain_description="10 records", domain="workforce_hr",
        analyst_persona="HR Analyst", verified_mappings={}, unresolved_meanings=[],
        verification_basis="Direct mapping",
    )
    rows = [
        {"EmpID": f"E{i}", "Date": f"2026-01-{i:02d}", "PlannedHours": 160.0, "WorkedDays": 20.0}
        for i in range(1, 11)
    ]
    cov, findings, pi = orchestrate_sheet_strategies(99009, rows, manifest, contract)
    s01_cov = next(s for s in cov.strategies if s.strategy_code == "S01")
    assert s01_cov.status == "incompatible"
    assert "unit mismatch" in s01_cov.summary_reason.lower()


def test_impossible_exposure_partition_rejected():
    """Fulfilled + Excused exceeding scheduled duty by over 50% must be flagged incompatible."""
    from app.services.adaptive_dashboard.contracts import SourceManifest, SemanticContract
    from app.services.adaptive_dashboard.orchestrator import orchestrate_sheet_strategies

    manifest = SourceManifest(
        sheet_id=99010, file_name="impossible.csv", sheet_name="Impossible",
        display_name="Impossible", row_count=10, col_count=4, snapshot="snap10",
        date_range={"formatted": "2026-01-01 to 2026-01-30"},
    )
    contract = SemanticContract(
        layout="long_tabular", entity_type="employee", entity_identifiers=["EmpID"],
        distinct_entity_count=10, date_column="Date", primary_measure="Attendance_Days",
        grain_description="10 records", domain="workforce_hr",
        analyst_persona="HR Analyst", verified_mappings={}, unresolved_meanings=[],
        verification_basis="Direct mapping",
    )
    # Scheduled 10 days, but attended 15 + leave 10 = 25 days (impossible without overtime roster)
    rows = [
        {"EmpID": f"E{i}", "Date": f"2026-01-{i:02d}", "Scheduled_Days": 10.0, "Attendance_Days": 15.0, "Approved_Leave_Days": 10.0}
        for i in range(1, 11)
    ]
    cov, findings, pi = orchestrate_sheet_strategies(99010, rows, manifest, contract)
    s01_cov = next(s for s in cov.strategies if s.strategy_code == "S01")
    assert s01_cov.status == "incompatible"
    assert "impossible exposure partition" in s01_cov.summary_reason.lower()


def test_copilot_distinct_queries():
    """Copilot must accurately bind metrics and directions for distinct management questions:
    - highest attendance
    - lowest attendance
    - most employees
    - lowest approved leave
    """
    conn = get_connection()
    try:
        conn.execute(
            "INSERT OR REPLACE INTO dataset_uploads (id, filename, original_name, display_name, file_type) VALUES (?, ?, ?, ?, ?)",
            (99011, "copilot_test.csv", "copilot_test.csv", "HR Workforce", "csv"),
        )
        cols = ["Employee_ID", "Department", "Attendance_Days", "Approved_Leave_Days"]
        conn.execute(
            "INSERT OR REPLACE INTO sheets (id, dataset_id, name, display_name, columns_json, profile_json, row_count) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (99011, 99011, "Staff", "Staff Department Data", json.dumps(cols), "{}", 14),
        )

        rows = []
        # Sales: 8 employees, high attendance (22.5d), low leave (1.0d)
        for i in range(1, 9):
            rows.append({"Employee_ID": f"E{i}", "Department": "Sales", "Attendance_Days": 22.5, "Approved_Leave_Days": 1.0})
        # Operations: 6 employees, low attendance (17.0d), higher leave (3.5d)
        for i in range(9, 15):
            rows.append({"Employee_ID": f"E{i}", "Department": "Operations", "Attendance_Days": 17.0, "Approved_Leave_Days": 3.5})

        conn.execute("DELETE FROM sheet_curated_rows WHERE sheet_id=99011")
        conn.execute("DELETE FROM sheet_rows WHERE sheet_id=99011")
        for idx, r in enumerate(rows):
            conn.execute(
                "INSERT INTO sheet_rows (sheet_id, row_index, data_json) VALUES (?, ?, ?)",
                (99011, idx, json.dumps(r)),
            )
        conn.commit()

        # 1. Highest attendance query
        ans1 = _answer_from_shared_findings("Which department has the highest attendance?", 99011, "Staff Department Data")
        assert ans1 is not None
        assert "Sales" in ans1["answer"]
        assert "22.5" in ans1["answer"]
        assert ans1["metadata"]["direction"] == "highest"
        assert ans1["metadata"]["metric"] == "attendance"

        # 2. Lowest attendance query
        ans2 = _answer_from_shared_findings("Which department has the lowest attendance?", 99011, "Staff Department Data")
        assert ans2 is not None
        assert "Operations" in ans2["answer"]
        assert "17.0" in ans2["answer"]
        assert ans2["metadata"]["direction"] == "lowest"
        assert ans2["metadata"]["metric"] == "attendance"

        # 3. Most employees query
        ans3 = _answer_from_shared_findings("Which department has the most employees?", 99011, "Staff Department Data")
        assert ans3 is not None
        assert "Sales" in ans3["answer"]
        assert "8 employees" in ans3["answer"]
        assert ans3["metadata"]["metric"] == "headcount"

        # 4. Lowest approved leave query
        ans4 = _answer_from_shared_findings("Which department has the lowest approved leave?", 99011, "Staff Department Data")
        assert ans4 is not None
        assert "Sales" in ans4["answer"]
        assert "1.0" in ans4["answer"]
        assert ans4["metadata"]["metric"] == "approved_leave"
        assert ans4["metadata"]["direction"] == "lowest"

    finally:
        conn.close()
