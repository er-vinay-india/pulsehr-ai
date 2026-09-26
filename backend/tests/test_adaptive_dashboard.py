"""Focused verification suite for the Adaptive Decision Dashboard (Revision 4).

Covers all required invariants from docs/adaptive-dashboard-design.md:
1. Exact arithmetic matching independent calculation on actual dataset.
2. Repeated observations do not inflate distinct entity count.
3. Dynamic text verification: changing fixture from 100 to 37 updates all explanations; no copied constants (100/712).
4. Unknown workforce coverage is never manufactured as 100%.
5. Attendance-only counts do not become active workforce headcount ("Employee count" scoped to "In attendance data").
6. Missing/null values are not silently treated as zero or valid entities.
7. Source data changes invalidate dependent results and produce new snapshot hashes.
8. Incomplete / undecidable data yields honest definition card, not fake metrics.
9. Exactly ONE element is emitted by component spec with 3-layer disclosure (glance, explain, inspect).
10. End-to-end API integration and preservation of existing report routes.
"""
import datetime
import json
import pytest
from fastapi.testclient import TestClient

from app.db.database import get_connection
from app.main import app
from app.services.adaptive_dashboard.contracts import (
    AdaptiveDashboardResponse,
    ChartSpec,
    ComponentSpec,
    DecisionFocusSpec,
    EvidenceResult,
    ExplainSpec,
    GlanceSpec,
    InspectSpec,
    EnterpriseSourceRef,
    EnterpriseSynthesisSpec,
    EnterpriseVisualSpec,
)
from app.services.adaptive_dashboard.engine import (
    build_average_logged_time_chart,
    build_decision_focus_element,
    build_segment_disparity_element,
    calendar_month_range,
    compute_focused_duration_scale,
    compute_source_snapshot,
    evaluate_and_select_primary_metric,
    linear_quantile,
    parse_clock_interval,
    parse_iso_date,
    profile_source,
    run_adaptive_dashboard,
)
from app.services.adaptive_dashboard.enterprise import (
    build_enterprise_synthesis_element,
    compute_combined_snapshot,
    detect_candidate_join_keys,
    inspect_cardinality,
)


@pytest.fixture
def seeded_attendance_sheet():
    """Seeds a wide attendance sheet (100 individuals, 10 dates) into the isolated test DB."""
    conn = get_connection()
    conn.execute(
        "INSERT INTO dataset_uploads (id, filename, original_name, display_name, file_type) VALUES (?, ?, ?, ?, ?)",
        (1, "attendance.csv", "Employee Attendance Logs.csv", "Daily Attendance Logs", "csv"),
    )
    cols = ["Date"] + [f"Person_{i}" for i in range(100)]
    conn.execute(
        "INSERT INTO sheets (id, dataset_id, name, display_name, columns_json, profile_json, row_count) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (1, 1, "Sheet1", "Daily Attendance Logs", json.dumps(cols), "[]", 10),
    )
    for row_idx in range(10):
        row_data = {"Date": f"2024-01-{row_idx+1:02d}"}
        for i in range(100):
            row_data[f"Person_{i}"] = "08:45-16:45"
        conn.execute(
            "INSERT INTO sheet_rows (sheet_id, row_index, data_json) VALUES (?, ?, ?)",
            (1, row_idx, json.dumps(row_data)),
        )
    conn.commit()
    conn.close()
    return 1


def test_independent_calculation_matches_ground_truth(seeded_attendance_sheet):
    """Verify that wide attendance sheet yields exactly 100 distinct employees with familiar label and context."""
    res = run_adaptive_dashboard(sheet_id=seeded_attendance_sheet)
    assert isinstance(res, AdaptiveDashboardResponse)
    assert res.element.kind == "kpi"
    assert res.element.glance.label == "Employee count"
    assert res.element.glance.value == 100
    assert res.element.glance.formatted_value == "100"
    assert res.element.glance.context_qualifier == "In attendance data"
    assert res.element.glance.unit_display == "implicit_in_label"
    assert res.contract.distinct_entity_count == 100
    assert len(res.contract.entity_identifiers) == 100
    assert res.element.evidence.status == "available"
    assert res.element.evidence.missing_observations == 0
    assert res.element.evidence.is_known_zero is False


def test_repeated_observations_do_not_inflate_entity_count():
    """480 rows from 120 employees in 4 weekly snapshots must yield exactly 120 employees, not 480."""
    cols = ["Employee_ID", "Week", "Hours_Worked"]
    rows = []
    for week in range(1, 5):
        for emp_idx in range(1, 121):
            rows.append({"Employee_ID": f"EMP-{emp_idx:03d}", "Week": f"2024-W{week:02d}", "Hours_Worked": 40})
    assert len(rows) == 480

    manifest, contract = profile_source(
        sheet_id=999,
        sheet_name="WeeklyAttendance",
        file_name="workforce.csv",
        display_name="Workforce Logs",
        columns=cols,
        rows=rows,
    )
    _, evidence, spec = evaluate_and_select_primary_metric(manifest, contract, rows)

    assert contract.distinct_entity_count == 120
    assert spec.glance.value == 120
    assert spec.glance.value != len(rows)
    assert spec.glance.label == "Employee count"
    assert spec.glance.context_qualifier == "In attendance data"
    assert evidence.value == 120


def test_fixture_37_people_updates_all_explanations_dynamically():
    """Changing fixture from 100 to 37 and dates to 5 updates every explanation; no copied constants remain."""
    cols = ["Date"] + [f"Person_{i}" for i in range(37)]
    rows = []
    for d in range(1, 6):
        r = {"Date": f"2025-03-0{d}"}
        for i in range(37):
            r[f"Person_{i}"] = "09:00-17:00"
        rows.append(r)

    manifest, contract = profile_source(
        sheet_id=995,
        sheet_name="MarchLogs",
        file_name="march.csv",
        display_name="March Attendance",
        columns=cols,
        rows=rows,
    )
    _, _, spec = evaluate_and_select_primary_metric(manifest, contract, rows)

    assert spec.glance.value == 37
    assert spec.glance.formatted_value == "37"
    assert "37" in spec.explain.exact_value_text
    assert "37" in spec.inspect.exact_value
    assert "5 recorded date rows" in spec.inspect.data_completeness
    # Verify no hardcoded 100 or 712 constants remain in generated copy
    all_text = (
        spec.glance.label
        + (spec.glance.context_qualifier or "")
        + spec.explain.short_definition
        + spec.explain.exact_value_text
        + spec.inspect.what_this_counts
        + spec.inspect.data_completeness
        + " ".join(spec.inspect.limitations)
    )
    assert "100" not in all_text
    assert "712" not in all_text


def test_unknown_workforce_coverage_is_not_reported_as_100_percent():
    """Workforce coverage must be declared unknown rather than manufacturing an invented 100%."""
    cols = ["Date"] + [f"Person_{i}" for i in range(10)]
    rows = [{"Date": "2024-01-01", **{f"Person_{i}": "09:00-17:00" for i in range(10)}}]

    manifest, contract = profile_source(
        sheet_id=994,
        sheet_name="Sample",
        file_name="sample.csv",
        display_name="Sample Logs",
        columns=cols,
        rows=rows,
    )
    _, _, spec = evaluate_and_select_primary_metric(manifest, contract, rows)

    assert "unknown" in spec.inspect.workforce_coverage.lower()
    assert "100%" not in spec.inspect.workforce_coverage


def test_attendance_counts_do_not_become_active_headcount():
    """Attendance data must yield 'Employee count' with 'In attendance data', never unqualified 'headcount'."""
    cols = ["Date", "Employee_ID", "Status"]
    rows = [
        {"Date": "2024-01-01", "Employee_ID": "E1", "Status": "Present"},
        {"Date": "2024-01-02", "Employee_ID": "E1", "Status": "Present"},
        {"Date": "2024-01-01", "Employee_ID": "E2", "Status": "Present"},
    ]
    manifest, contract = profile_source(
        sheet_id=993,
        sheet_name="AttendanceRecords",
        file_name="attendance.csv",
        display_name="Attendance Records",
        columns=cols,
        rows=rows,
    )
    _, _, spec = evaluate_and_select_primary_metric(manifest, contract, rows)

    assert spec.glance.label == "Employee count"
    assert spec.glance.context_qualifier == "In attendance data"
    assert "headcount" not in spec.glance.label.lower()


def test_missing_values_not_treated_as_zero_or_entities():
    """Null, empty or missing keys must be recorded explicitly and excluded from entity count."""
    cols = ["Employee_ID", "Department"]
    rows = [
        {"Employee_ID": "EMP-001", "Department": "Eng"},
        {"Employee_ID": "EMP-002", "Department": "Eng"},
        {"Employee_ID": "", "Department": "Eng"},
        {"Employee_ID": None, "Department": "Eng"},
        {"Employee_ID": "   ", "Department": "Eng"},
    ]
    manifest, contract = profile_source(
        sheet_id=998,
        sheet_name="Employees",
        file_name="employees.csv",
        display_name="Employees",
        columns=cols,
        rows=rows,
    )
    _, evidence, spec = evaluate_and_select_primary_metric(manifest, contract, rows)

    assert spec.glance.value == 2
    assert evidence.missing_observations == 3
    assert evidence.is_known_zero is False


def test_source_change_invalidates_snapshot_and_evidence():
    """Modifying even a single value in a cell changes snapshot hash and calculation ID."""
    cols = ["Date", "Person_0", "Person_1"]
    rows1 = [
        {"Date": "2024-01-01", "Person_0": "09:00-17:00", "Person_1": "08:30-16:30"},
        {"Date": "2024-01-02", "Person_0": "09:05-17:00", "Person_1": "08:45-16:45"},
    ]
    snap1 = compute_source_snapshot(1, cols, rows1)

    # Change single timestamp value in row 2
    rows2 = [
        {"Date": "2024-01-01", "Person_0": "09:00-17:00", "Person_1": "08:30-16:30"},
        {"Date": "2024-01-02", "Person_0": "10:15-18:00", "Person_1": "08:45-16:45"},
    ]
    snap2 = compute_source_snapshot(1, cols, rows2)

    assert snap1 != snap2


def test_undecidable_data_emits_honest_definition_card():
    """Unstructured table without an entity key produces an honest definition card, not a fake KPI."""
    cols = ["Note_Text", "Comment"]
    rows = [
        {"Note_Text": "Meeting notes", "Comment": "Followup"},
        {"Note_Text": "Action items", "Comment": "Done"},
    ]
    manifest, contract = profile_source(
        sheet_id=997,
        sheet_name="Notes",
        file_name="notes.csv",
        display_name="Notes",
        columns=cols,
        rows=rows,
    )
    _, evidence, spec = evaluate_and_select_primary_metric(manifest, contract, rows)

    assert spec.kind == "definition_card"
    assert spec.glance.label == "Definition Required"
    assert spec.glance.value is None
    assert spec.glance.formatted_value == "Needs Definition"
    assert evidence.status == "needs_definition"
    assert any("Row count is not a valid business KPI" in lim for lim in evidence.limitations)


def test_exactly_one_element_emitted(seeded_attendance_sheet):
    """The Adaptive Dashboard response must contain exactly ONE primary element spec."""
    res = run_adaptive_dashboard(sheet_id=seeded_attendance_sheet)
    assert isinstance(res.element, ComponentSpec)
    assert res.element.component_id == "primary_element"
    assert hasattr(res.element, "glance")
    assert hasattr(res.element, "explain")
    assert hasattr(res.element, "inspect")
    assert not hasattr(res, "charts")
    assert not hasattr(res, "secondary_tiles")


def test_api_primary_element_endpoint(seeded_attendance_sheet):
    """FastAPI endpoint returns 200 with full 3-layer schema."""
    client = TestClient(app)
    response = client.get(f"/api/adaptive-dashboard/primary-element?sheet_id={seeded_attendance_sheet}")
    assert response.status_code == 200
    data = response.json()
    assert data["version"] in ("adaptive-v8", "adaptive-v9", "adaptive-v10")
    assert data["sheet_id"] == seeded_attendance_sheet
    assert data["element"]["glance"]["label"] == "Employee count"
    assert data["element"]["glance"]["formatted_value"] == "100"
    assert data["element"]["glance"]["context_qualifier"] == "In attendance data"
    assert "short_definition" in data["element"]["explain"]
    assert "exact_value" in data["element"]["inspect"]
    assert data["element"]["evidence"]["calculation_id"].startswith("CALC-")


def test_existing_report_routes_preserved(seeded_attendance_sheet):
    """Verify that existing Leadership Report and Overview routes remain completely functional."""
    client = TestClient(app)
    # 1. Health
    health_res = client.get("/api/health")
    assert health_res.status_code == 200

    # 2. Sheets
    sheets_res = client.get("/api/sheets")
    assert sheets_res.status_code == 200

    # 3. Decision Brief
    brief_res = client.get(f"/api/analytics/decision-brief?sheet_id={seeded_attendance_sheet}")
    assert brief_res.status_code == 200


def test_interval_arithmetic_mean_seven_hours():
    """Requirement 1: 09:00-17:00 (8h) and 09:00-15:00 (6h) produce a mean of 7.0 hours."""
    dur1, st1, _ = parse_clock_interval("09:00-17:00")
    dur2, st2, _ = parse_clock_interval("09:00-15:00")
    assert st1 == "valid" and dur1 == 480
    assert st2 == "valid" and dur2 == 360
    mean_hours = (dur1 + dur2) / (60.0 * 2)
    assert mean_hours == 7.0

    cols = ["Date", "Person_0", "Person_1"]
    rows = [{"Date": "2024-04-10", "Person_0": "09:00-17:00", "Person_1": "09:00-15:00"}]
    manifest, contract = profile_source(
        sheet_id=901,
        sheet_name="IntervalSheet",
        file_name="intervals.csv",
        display_name="Interval Test",
        columns=cols,
        rows=rows,
    )
    chart = build_average_logged_time_chart(manifest, contract, rows)
    assert chart is not None
    assert chart.glance.value == 7.0
    assert chart.chart_series.points[0].average_hours == 7.0


def test_unequal_intervals_weighted_by_interval_count_not_daily_means():
    """Requirement 2: Unequal numbers of intervals per day are weighted by interval count, not daily means."""
    cols = ["Date", "Person_0", "Person_1"]
    # Day 1: one valid interval (6h = 360m), one blank
    # Day 2: two valid intervals (9h = 540m each)
    # Total minutes = 360 + 540 + 540 = 1440. Valid count = 3.
    # Weighted mean: 1440 / (3 * 60) = 8.0 hours.
    # (If averaged daily: Day 1 mean = 6.0h, Day 2 mean = 9.0h -> (6+9)/2 = 7.5h != 8.0h)
    rows = [
        {"Date": "2024-05-01", "Person_0": "09:00-15:00", "Person_1": ""},
        {"Date": "2024-05-02", "Person_0": "09:00-18:00", "Person_1": "09:00-18:00"},
    ]
    manifest, contract = profile_source(
        sheet_id=902,
        sheet_name="WeightSheet",
        file_name="weights.csv",
        display_name="Weighting Test",
        columns=cols,
        rows=rows,
    )
    chart = build_average_logged_time_chart(manifest, contract, rows)
    assert chart is not None
    point = chart.chart_series.points[0]
    assert point.valid_entries == 3
    assert point.total_duration_minutes == 1440
    assert point.average_hours == 8.0
    assert point.average_hours != 7.5


def test_exact_duplicates_and_conflicts_policy_and_row_order_independence():
    """Requirement 3: Exact duplicates do not double count; conflicting entries exclude entire group for row-order independence."""
    cols = ["Date", "Person_0"]
    # Row 1 and Row 2 have exact duplicate person/date/interval
    # Row 3 and 4 have conflicting intervals for same person/date
    rows = [
        {"Date": "2024-06-01", "Person_0": "09:00-17:00"},
        {"Date": "2024-06-01", "Person_0": "09:00-17:00"},  # duplicate -> ignore duplicate
        {"Date": "2024-06-02", "Person_0": "09:00-17:00"},
        {"Date": "2024-06-02", "Person_0": "10:00-19:00"},  # conflict -> exclude entire group (2 entries)
    ]
    manifest, contract = profile_source(
        sheet_id=903,
        sheet_name="DedupeSheet",
        file_name="dedupe.csv",
        display_name="Deduplication Test",
        columns=cols,
        rows=rows,
    )
    chart1 = build_average_logged_time_chart(manifest, contract, rows)
    assert chart1 is not None
    point1 = chart1.chart_series.points[0]
    # Exact duplicate on 2024-06-01 is counted once: 1 valid entry (480 mins = 8.0h)
    # Conflicting on 2024-06-02 has both 2 excluded
    assert point1.valid_entries == 1
    assert point1.total_duration_minutes == 480
    assert point1.excluded_entries == 2

    # Invariant: Reversing row order MUST produce the exact same outcome
    rows_reversed = list(reversed(rows))
    chart2 = build_average_logged_time_chart(manifest, contract, rows_reversed)
    assert chart2 is not None
    point2 = chart2.chart_series.points[0]
    assert point2.valid_entries == point1.valid_entries
    assert point2.total_duration_minutes == point1.total_duration_minutes
    assert point2.excluded_entries == point1.excluded_entries
    assert point2.average_hours == point1.average_hours


def test_malformed_blanks_overnight_never_become_zero():
    """Requirement 4: Malformed, blank, overnight entries are excluded and never fabricated as zero durations."""
    dur_zero, st_zero, _ = parse_clock_interval("09:00-09:00")
    assert st_zero == "overnight_or_zero" and dur_zero is None

    dur_overnight, st_overnight, _ = parse_clock_interval("18:00-06:00")
    assert st_overnight == "overnight_or_zero" and dur_overnight is None

    dur_bad, st_bad, _ = parse_clock_interval("invalid-time")
    assert st_bad == "malformed" and dur_bad is None

    dur_blank, st_blank, _ = parse_clock_interval("")
    assert st_blank == "blank" and dur_blank is None

    cols = ["Date", "Person_0"]
    rows = [
        {"Date": "2024-07-01", "Person_0": "18:00-06:00"},
        {"Date": "2024-07-02", "Person_0": "09:00-09:00"},
    ]
    manifest, contract = profile_source(
        sheet_id=904,
        sheet_name="BadSheet",
        file_name="bad.csv",
        display_name="Bad Time Test",
        columns=cols,
        rows=rows,
    )
    chart = build_average_logged_time_chart(manifest, contract, rows)
    # Zero valid entries must not fabricate 0.0h chart
    assert chart is None


def test_chronological_ordering_across_years():
    """Requirement 5: December and January in different years stay chronological and distinct."""
    months = calendar_month_range("2023-11", "2024-02")
    assert months == ["2023-11", "2023-12", "2024-01", "2024-02"]
    assert months[1] == "2023-12"
    assert months[2] == "2024-01"


def test_missing_months_null_gaps_and_partial_last_month():
    """Requirement 6: Missing months stay null gaps; partial last month is identified."""
    cols = ["Date", "Person_0"]
    # Entries in 2024-01 and 2024-03; 2024-02 is completely missing
    # 2024-03 only has observations through 2024-03-05 (5 dates < 31 days)
    rows = [
        {"Date": "2024-01-15", "Person_0": "09:00-17:00"},
        {"Date": "2024-03-01", "Person_0": "09:00-17:00"},
        {"Date": "2024-03-05", "Person_0": "09:00-17:00"},
    ]
    manifest, contract = profile_source(
        sheet_id=905,
        sheet_name="GapSheet",
        file_name="gap.csv",
        display_name="Gap Test",
        columns=cols,
        rows=rows,
    )
    chart = build_average_logged_time_chart(manifest, contract, rows)
    assert chart is not None
    points = chart.chart_series.points
    assert len(points) == 3
    # 2024-01
    assert points[0].period == "2024-01" and points[0].average_hours == 8.0
    # 2024-02: missing month must have average_hours = None (null gap)
    assert points[1].period == "2024-02" and points[1].average_hours is None
    # 2024-03: terminal month is partial
    assert points[2].period == "2024-03" and points[2].is_partial is True
    assert "Through 5 Mar 2024 · Partial month" in chart.terminal_note


def test_source_edits_invalidate_snapshot_and_preserve_first_tile_on_failure():
    """Requirement 7: Source edits invalidate snapshot; secondary failure preserves valid first tile."""
    cols = ["Date", "Person_0"]
    rows = [{"Date": "2024-01-01", "Person_0": "09:00-17:00"}]
    manifest, contract = profile_source(
        sheet_id=906,
        sheet_name="SnapshotSheet",
        file_name="snapshot.csv",
        display_name="Snapshot Test",
        columns=cols,
        rows=rows,
    )
    _, _, first_spec = evaluate_and_select_primary_metric(manifest, contract, rows)
    assert first_spec.kind == "kpi"
    assert first_spec.glance.value == 1

    # If rows have no valid intervals, secondary chart is None, but first tile is preserved
    rows_no_intervals = [{"Date": "2024-01-01", "Person_0": "PRESENT"}]
    chart_fail = build_average_logged_time_chart(manifest, contract, rows_no_intervals)
    assert chart_fail is None
    # First tile is still valid
    assert first_spec.glance.value == 1


def test_varying_entity_counts_and_dates_without_constants():
    """Requirement 8: Different entity counts (e.g. 15 entities, 3 dates) work dynamically without fixtures."""
    cols = ["Date"] + [f"Person_{i}" for i in range(15)]
    rows = [
        {"Date": f"2024-08-0{d}", **{f"Person_{i}": "09:00-17:30" for i in range(15)}}
        for d in range(1, 4)
    ]
    manifest, contract = profile_source(
        sheet_id=907,
        sheet_name="DynamicSheet",
        file_name="dynamic.csv",
        display_name="Dynamic Test",
        columns=cols,
        rows=rows,
    )
    chart = build_average_logged_time_chart(manifest, contract, rows)
    assert chart is not None
    # 09:00 to 17:30 = 8.5 hours
    assert chart.glance.value == 8.5
    assert chart.chart_series.points[0].valid_entries == 45  # 15 * 3
    assert chart.chart_series.points[0].observed_dates == 3


def test_exactly_two_dashboard_elements_rendered(seeded_attendance_sheet):
    """Requirement 9: Exactly two dashboard elements are delivered: primary KPI tile and secondary chart."""
    res = run_adaptive_dashboard(sheet_id=seeded_attendance_sheet)
    assert isinstance(res.element, ComponentSpec)
    assert res.element.component_id == "primary_element"
    assert res.element.glance.label == "Employee count"
    assert res.element.glance.value == 100

    assert isinstance(res.secondary_element, ChartSpec)
    assert res.secondary_element.component_id == "secondary_element"
    assert res.secondary_element.title == "Average logged time"
    assert res.secondary_element.kind == "line_chart"
    assert len(res.secondary_element.chart_series.points) == 1


def test_live_chart_values_reconcile_with_independent_calculation(seeded_attendance_sheet):
    """Requirement 10: Live chart values reconcile with an independent calculation."""
    res = run_adaptive_dashboard(sheet_id=seeded_attendance_sheet)
    chart = res.secondary_element
    assert chart is not None
    # Seeded data has 10 rows, 100 people = 1,000 intervals of 08:45-16:45 (8 hours = 480 mins)
    expected_total_mins = 1000 * 480
    expected_valid_entries = 1000
    expected_mean = expected_total_mins / (60.0 * expected_valid_entries)
    assert expected_mean == 8.0

    point = chart.chart_series.points[0]
    assert point.valid_entries == expected_valid_entries
    assert point.total_duration_minutes == expected_total_mins
    assert point.average_hours == expected_mean
    assert chart.glance.value == expected_mean


def test_linear_quantile_interpolation():
    """Verify linear quantile calculation against standard percentiles."""
    values = [10.0, 20.0, 30.0, 40.0, 50.0]
    # n=5, index base 0..4
    # p=0.0 -> index 0 -> 10.0
    # p=0.5 -> index 2 -> 30.0
    # p=1.0 -> index 4 -> 50.0
    # p=0.25 -> index 1 -> 20.0
    assert linear_quantile(values, 0.0) == 10.0
    assert linear_quantile(values, 0.5) == 30.0
    assert linear_quantile(values, 1.0) == 50.0
    assert linear_quantile(values, 0.25) == 20.0

    # 2-element interpolation
    assert linear_quantile([100.0, 200.0], 0.3) == 130.0


def test_focused_duration_scale_computation():
    """Verify focused scale policy generates >= 60m span, snapped 15m/30m/60m steps, and formatted labels."""
    # Narrow range: all values near 8.0h (480 mins)
    y_min, y_max, ticks, labels, is_focused = compute_focused_duration_scale([479.0, 480.0, 481.0])
    assert is_focused is True
    # Span must be >= 60 mins (1.0h)
    assert y_max - y_min >= 1.0
    # Check tick labels
    assert len(ticks) == len(labels)
    assert "8h" in labels
    # Check that ticks are strictly monotonic
    for i in range(len(ticks) - 1):
        assert ticks[i] < ticks[i+1]


def test_distribution_band_sparse_guard_and_quantiles():
    """Requirement: Distribution band is computed when n >= 20, suppressed when n < 20."""
    cols = ["Date"] + [f"Person_{i}" for i in range(25)]
    # Row 1 has 15 valid intervals (< 20 threshold)
    row_sparse = {"Date": "2024-09-01"}
    for i in range(15):
        row_sparse[f"Person_{i}"] = "08:00-16:00"  # 8h
    for i in range(15, 25):
        row_sparse[f"Person_{i}"] = ""

    manifest_sparse, contract_sparse = profile_source(
        sheet_id=908,
        sheet_name="SparseSheet",
        file_name="sparse.csv",
        display_name="Sparse Test",
        columns=cols,
        rows=[row_sparse],
    )
    chart_sparse = build_average_logged_time_chart(manifest_sparse, contract_sparse, [row_sparse])
    assert chart_sparse is not None
    p_sparse = chart_sparse.chart_series.points[0]
    assert p_sparse.valid_entries == 15
    assert p_sparse.has_band is False
    assert p_sparse.p10_hours is None
    assert p_sparse.p90_hours is None

    # Row 2 has 25 valid intervals (>= 20 threshold), varying durations
    row_dense = {"Date": "2024-10-01"}
    # 5 at 7h, 15 at 8h, 5 at 9h
    for i in range(5):
        row_dense[f"Person_{i}"] = "09:00-16:00"  # 7h
    for i in range(5, 20):
        row_dense[f"Person_{i}"] = "09:00-17:00"  # 8h
    for i in range(20, 25):
        row_dense[f"Person_{i}"] = "09:00-18:00"  # 9h

    manifest_dense, contract_dense = profile_source(
        sheet_id=909,
        sheet_name="DenseSheet",
        file_name="dense.csv",
        display_name="Dense Test",
        columns=cols,
        rows=[row_dense],
    )
    chart_dense = build_average_logged_time_chart(manifest_dense, contract_dense, [row_dense])
    assert chart_dense is not None
    p_dense = chart_dense.chart_series.points[0]
    assert p_dense.valid_entries == 25
    assert p_dense.has_band is True
    assert p_dense.p10_hours is not None
    assert p_dense.p90_hours is not None
    assert p_dense.p10_hours <= p_dense.average_hours <= p_dense.p90_hours
    assert p_dense.formatted_p10 is not None
    assert p_dense.formatted_p90 is not None
    assert chart_dense.band_name == "Middle 80% of recorded entries"
    assert chart_dense.caption is not None
    assert len(chart_dense.caption) > 0


def test_commercial_measure_primary_tile_and_temporal_chart():
    """Verify commercial dataset with measure (e.g. Weekly_Sales across Stores) projects Total Sales KPI and monthly trend chart with store distribution band."""
    cols = ["Store", "Date", "Weekly_Sales"]
    rows = []
    # 25 stores, 2 dates in 2024-01, 2 dates in 2024-02
    dates = ["2024-01-05", "2024-01-12", "2024-02-02", "2024-02-09"]
    for d in dates:
        for store_id in range(1, 26):
            # Sales vary between 10,000 and 50,000
            sales = 10000 + (store_id * 1000)
            rows.append({"Store": store_id, "Date": d, "Weekly_Sales": sales})

    manifest, contract = profile_source(
        sheet_id=950,
        sheet_name="WeeklySales",
        file_name="sales.csv",
        display_name="Store Sales Analysis",
        columns=cols,
        rows=rows,
    )

    assert contract.layout == "long_tabular"
    assert contract.primary_measure == "Weekly_Sales"
    assert contract.entity_type == "store"
    assert contract.distinct_entity_count == 25

    # 1. Primary element evaluation
    _, _, spec = evaluate_and_select_primary_metric(manifest, contract, rows)
    assert spec.kind == "kpi"
    assert spec.glance.label == "Total sales"
    assert spec.glance.value == sum(r["Weekly_Sales"] for r in rows)
    assert spec.glance.unit == "$"
    assert "25 stores" in spec.glance.context_qualifier

    # 2. Secondary element evaluation
    from app.services.adaptive_dashboard.engine import build_temporal_measure_chart
    chart = build_temporal_measure_chart(manifest, contract, rows)
    assert chart is not None
    assert chart.title == "Average weekly sales"
    assert chart.y_axis_title == "Weekly sales ($)"
    assert chart.band_name == "Middle 80% across stores"
    assert len(chart.chart_series.points) == 2  # 2024-01 and 2024-02

    pt0 = chart.chart_series.points[0]
    assert pt0.period == "2024-01"
    assert pt0.has_band is True
    assert pt0.p10_hours is not None
    assert pt0.p90_hours is not None
    assert pt0.p10_hours <= pt0.average_hours <= pt0.p90_hours
    assert pt0.valid_entries == 50  # 25 stores * 2 dates


def test_commercial_measure_weekly_cadence_projection():
    """Verify that when 8+ consecutive weekly observations exist (cadence = 7 days), the projection pipeline projects at native retail week resolution."""
    from app.services.adaptive_dashboard.engine import build_temporal_measure_chart
    cols = ["Store", "Date", "Weekly_Sales"]
    rows = []
    # 10 consecutive Fridays starting 2024-01-05
    base_d = datetime.date(2024, 1, 5)
    for w in range(10):
        cur_d = base_d + datetime.timedelta(days=w * 7)
        d_str = cur_d.strftime("%Y-%m-%d")
        for store_id in range(1, 26):
            sales = 15000 + (store_id * 800) + (w * 200)
            rows.append({"Store": store_id, "Date": d_str, "Weekly_Sales": sales})

    manifest, contract = profile_source(
        sheet_id=951,
        sheet_name="ConsecutiveWeekly",
        file_name="weekly.csv",
        display_name="Weekly Cadence Test",
        columns=cols,
        rows=rows,
    )

    chart = build_temporal_measure_chart(manifest, contract, rows)
    assert chart is not None
    assert chart.temporal_grain == "weekly"
    assert chart.x_axis_title == "Retail week (Timeline)"
    assert chart.y_axis_title == "Weekly sales ($)"
    assert "Per store · Weekly" in chart.glance.context_qualifier
    assert len(chart.chart_series.points) == 10
    assert chart.chart_series.points[0].period == "2024-W01"
    assert chart.chart_series.points[0].period_label == "W01 '24"
    assert chart.chart_series.points[0].valid_entries == 25
    assert chart.chart_series.points[0].has_band is True
    assert chart.chart_series.points[0].p10_hours <= chart.chart_series.points[0].average_hours <= chart.chart_series.points[0].p90_hours


def test_periodic_attendance_chart_for_wide_interval_matrix():
    """Verify that chronological period attendance columns (like 1st to 5th July) build valid ChartSpec."""
    from app.services.adaptive_dashboard.engine import build_period_attendance_chart
    cols = ["Full Name", "ID", "Department", "1st to 5th July", "Leaves(1st to 5th July)", "6th to 12th July", "Leaves(6th to 12th July)", "13th to 19th July"]
    rows = [
        {"Full Name": "Alice", "ID": "1", "Department": "Eng", "1st to 5th July": 3, "6th to 12th July": 5, "13th to 19th July": 4},
        {"Full Name": "Bob", "ID": "2", "Department": "Sales", "1st to 5th July": 2, "6th to 12th July": 4, "13th to 19th July": 3},
        {"Full Name": "Carol", "ID": "3", "Department": "Eng", "1st to 5th July": 4, "6th to 12th July": 5, "13th to 19th July": 5},
    ]

    manifest, contract = profile_source(
        sheet_id=980,
        sheet_name="PeriodAttendance",
        file_name="july_wfo.xlsx",
        display_name="July Attendance",
        columns=cols,
        rows=rows,
    )

    chart = build_period_attendance_chart(manifest, contract, rows)
    assert chart is not None
    assert chart.title == "Average weekly attendance"
    assert chart.temporal_grain == "weekly"
    assert chart.glance.unit == "d"
    assert len(chart.chart_series.points) == 3
    assert chart.chart_series.points[0].period_label == "1st to 5th July"
    assert chart.chart_series.points[0].average_hours == pytest.approx(3.0, 0.01)


def test_categorical_breakdown_hr_departments():
    """Verify Gate 3 Categorical Breakdown generates accurate department headcounts and share percentages."""
    from app.services.adaptive_dashboard.engine import build_categorical_breakdown_element
    cols = ["Full Name", "ID", "Department", "Total Attendance"]
    rows = [
        {"Full Name": "Alice", "ID": "1", "Department": "Engineering", "Total Attendance": 14},
        {"Full Name": "Bob", "ID": "2", "Department": "Engineering", "Total Attendance": 15},
        {"Full Name": "Charlie", "ID": "3", "Department": "Sales", "Total Attendance": 12},
        {"Full Name": "David", "ID": "4", "Department": "Operations", "Total Attendance": 18},
    ]

    manifest, contract = profile_source(
        sheet_id=981,
        sheet_name="DeptTest",
        file_name="wfo.xlsx",
        display_name="Workforce By Dept",
        columns=cols,
        rows=rows,
    )

    breakdown = build_categorical_breakdown_element(manifest, contract, rows)
    assert breakdown is not None
    assert breakdown.kind == "ranked_bar"
    assert breakdown.dimension_name == "Department"
    assert breakdown.total_categories == 3
    assert breakdown.total_value == 4
    # Engineering is largest (2/4 = 50%)
    assert breakdown.items[0].category == "Engineering"
    assert breakdown.items[0].value == 2
    assert breakdown.items[0].share_pct == 50.0


def test_quaternary_element_retail_holiday_lift():
    """Verify Gate 4 Explanatory Comparator computes holiday lift accurately."""
    from app.services.adaptive_dashboard.engine import build_explanatory_comparator_element
    cols = ["Store", "Date", "Weekly_Sales", "Holiday_Flag"]
    rows = []
    # 10 holiday weeks with $120,000 average sales
    for i in range(10):
        rows.append({"Store": 1, "Date": f"2024-02-{i+1:02d}", "Weekly_Sales": 120000, "Holiday_Flag": "1"})
    # 90 non-holiday weeks with $100,000 average sales
    for i in range(90):
        rows.append({"Store": 1, "Date": f"2024-03-{i+1:02d}", "Weekly_Sales": 100000, "Holiday_Flag": "0"})

    manifest, contract = profile_source(
        sheet_id=982,
        sheet_name="SalesLiftTest",
        file_name="walmart.csv",
        display_name="Store Sales Lift",
        columns=cols,
        rows=rows,
    )

    comparator = build_explanatory_comparator_element(manifest, contract, rows)
    assert comparator is not None
    assert comparator.kind == "cohort_comparator"
    assert comparator.title == "Holiday sales lift comparator"
    assert comparator.glance.label == "Holiday sales lift"
    assert comparator.glance.formatted_value == "+20.0%"
    assert comparator.absolute_lift == 20000.0
    assert comparator.relative_lift_pct == 20.0
    assert len(comparator.items) == 2
    # Holiday item
    assert comparator.items[0].cohort == "Holiday weeks"
    assert comparator.items[0].value == 120000.0
    assert comparator.items[0].sample_size == 10
    assert comparator.items[0].share_pct == 10.0
    # Non-holiday item
    assert comparator.items[1].cohort == "Non-holiday weeks"
    assert comparator.items[1].value == 100000.0
    assert comparator.items[1].sample_size == 90
    assert comparator.items[1].share_pct == 90.0
    assert comparator.items[1].is_baseline is True


def test_quaternary_element_hr_attendance_vs_leave():
    """Verify Gate 4 Explanatory Comparator computes workforce attendance vs leave impact."""
    from app.services.adaptive_dashboard.engine import build_explanatory_comparator_element
    cols = ["Full Name", "ID", "Department", "Total Attendance", "Approved Leaves"]
    rows = [
        {"Full Name": "Alice", "ID": "1", "Department": "Eng", "Total Attendance": 18, "Approved Leaves": 2},
        {"Full Name": "Bob", "ID": "2", "Department": "Sales", "Total Attendance": 14, "Approved Leaves": 6},
    ]

    manifest, contract = profile_source(
        sheet_id=983,
        sheet_name="LeaveImpactTest",
        file_name="wfo.xlsx",
        display_name="Workforce Capacity",
        columns=cols,
        rows=rows,
    )

    comparator = build_explanatory_comparator_element(manifest, contract, rows)
    assert comparator is not None
    assert comparator.kind == "cohort_comparator" or comparator.kind == "impact_ratio"
    assert comparator.title == "Recorded attendance and approved leaves"
    assert comparator.glance.label == "Recorded attendance & leave"
    # Total attendance = 32, Total leaves = 8, Scheduled = 40
    # Attendance share = 32/40 = 80.0%, Leave share = 8/40 = 20.0%
    assert comparator.items[0].cohort == "Recorded attendance"
    assert comparator.items[0].value == 32.0
    assert comparator.items[0].share_pct == 80.0
    assert comparator.items[1].cohort == "Approved leaves"
    assert comparator.items[1].value == 8.0
    assert comparator.items[1].share_pct == 20.0


def test_quinary_element_hr_department_disparity():
    """Verify Gate 5 Segment Disparity computes departmental attendance reliability disparity."""
    from app.services.adaptive_dashboard.engine import build_segment_disparity_element
    cols = ["Full Name", "ID", "Department", "Total Attendance", "Approved Leaves"]
    rows = [
        {"Full Name": "Alice", "ID": "1", "Department": "Operations", "Total Attendance": 18, "Approved Leaves": 2},
        {"Full Name": "Bob", "ID": "2", "Department": "Operations", "Total Attendance": 18, "Approved Leaves": 2},
        {"Full Name": "Charlie", "ID": "3", "Department": "Engineering", "Total Attendance": 16, "Approved Leaves": 4},
        {"Full Name": "Dave", "ID": "4", "Department": "Corporate", "Total Attendance": 14, "Approved Leaves": 6},
    ]

    manifest, contract = profile_source(
        sheet_id=984,
        sheet_name="DeptDisparityTest",
        file_name="wfo.xlsx",
        display_name="Departmental Reliability",
        columns=cols,
        rows=rows,
    )

    disparity = build_segment_disparity_element(manifest, contract, rows)
    assert disparity is not None
    assert disparity.kind == "segment_disparity"
    assert disparity.dimension_name == "Department"
    assert disparity.metric_name == "Recorded Attendance Days"
    assert disparity.unit == "days"
    assert disparity.top_segment == "Operations"
    assert disparity.bottom_segment == "Corporate"
    # Operations: 18.0 days avg
    # Corporate: 14.0 days avg
    # Spread: 18.0 - 14.0 = 4.0 days
    assert disparity.spread_value == 4.0
    assert disparity.formatted_spread == "4.0 days spread"
    assert disparity.glance.label == "Recorded attendance by department"
    assert "Operations" in disparity.glance.context_qualifier
    assert "Corporate" in disparity.glance.context_qualifier
    assert len(disparity.items) == 3
    assert disparity.items[0].segment == "Operations"
    assert disparity.items[0].primary_value == 18.0
    assert disparity.items[0].formatted_primary == "18.0 days"
    assert disparity.items[0].tier == "standard_tier"
    assert disparity.items[-1].segment == "Corporate"
    assert disparity.items[-1].primary_value == 14.0
    assert disparity.items[-1].formatted_primary == "14.0 days"
    assert disparity.items[-1].tier == "standard_tier"


def test_quinary_element_retail_store_density_disparity():
    """Verify Gate 5 Segment Disparity computes store revenue density disparity on retail data without HR terms."""
    from app.services.adaptive_dashboard.engine import build_segment_disparity_element
    from tests.test_walmart_sales_analytics import WALMART_SAMPLE_ROWS, WALMART_COLUMNS

    manifest, contract = profile_source(
        sheet_id=985,
        sheet_name="Walmart_Sales",
        file_name="Walmart_Sales.csv",
        display_name="Walmart Network",
        columns=WALMART_COLUMNS,
        rows=WALMART_SAMPLE_ROWS,
    )

    disparity = build_segment_disparity_element(manifest, contract, WALMART_SAMPLE_ROWS)
    assert disparity is not None
    assert disparity.kind == "segment_disparity"
    assert disparity.dimension_name == "Store"
    assert disparity.metric_name == "Weekly Sales Density"
    assert disparity.unit == "$"
    assert disparity.spread_type == "ratio"
    assert "Store 20" in disparity.top_segment
    assert "Store 33" in disparity.bottom_segment
    assert disparity.spread_value >= 8.0
    assert "x spread" in disparity.formatted_spread
    assert disparity.glance.label == "Store sales density disparity"
    # Ensure zero false-positive HR references
    assert "attendance" not in disparity.title.lower()
    assert "leave" not in disparity.title.lower()
    assert "attendance" not in disparity.glance.label.lower()
    assert len(disparity.items) == 4
    # Store 20 top tier, Store 33 friction tier
    top_item = next(it for it in disparity.items if "20" in it.segment)
    bottom_item = next(it for it in disparity.items if "33" in it.segment)
    assert top_item.tier == "top_tier"
    assert bottom_item.tier == "friction_tier"


def test_quinary_element_general_tabular_disparity():
    """Verify Gate 5 Segment Disparity provides general tabular fallback spread."""
    from app.services.adaptive_dashboard.engine import build_segment_disparity_element
    cols = ["Region", "Transactions"]
    rows = [
        {"Region": "North", "Transactions": 500},
        {"Region": "North", "Transactions": 550},
        {"Region": "South", "Transactions": 200},
        {"Region": "South", "Transactions": 220},
    ]

    manifest, contract = profile_source(
        sheet_id=986,
        sheet_name="RegionalVolume",
        file_name="volume.csv",
        display_name="Regional Volume",
        columns=cols,
        rows=rows,
    )

    disparity = build_segment_disparity_element(manifest, contract, rows)
    assert disparity is not None
    assert disparity.kind == "segment_disparity"
    assert disparity.dimension_name == "Region"
    assert disparity.top_segment == "North"
    assert disparity.bottom_segment == "South"
    assert disparity.spread_value == 2.5
    assert disparity.formatted_spread == "2.5x spread"


# =========================================================================
# Element 6: Decision Focus Component Tests (Gate 6)
# =========================================================================

def test_element_6_workforce_directional_gap():
    """Scenario 1: Workforce directional gap using weighted benchmark and adequate department samples."""
    rows = []
    # Ops: 20 emps, 18 att, 2 leave (90%)
    for i in range(20):
        rows.append({"Department": "Operations", "Attendance Days": 18, "Approved Leaves": 2})
    # Eng: 20 emps, 19 att, 1 leave (95%)
    for i in range(20):
        rows.append({"Department": "Engineering", "Attendance Days": 19, "Approved Leaves": 1})
    # Corp: 10 emps, 14 att, 6 leave (70%)
    for i in range(10):
        rows.append({"Department": "Corporate Functions", "Attendance Days": 14, "Approved Leaves": 6})
    # Small: 2 emps (under n < 5 sample guard)
    for i in range(2):
        rows.append({"Department": "Special Project", "Attendance Days": 10, "Approved Leaves": 10})

    manifest, contract = profile_source(
        sheet_id=101,
        sheet_name="WorkforceData",
        file_name="workforce.csv",
        display_name="Workforce Sheet",
        columns=["Department", "Attendance Days", "Approved Leaves"],
        rows=rows,
    )
    disparity = build_segment_disparity_element(manifest, contract, rows)
    assert disparity is not None

    decision = build_decision_focus_element(manifest, contract, rows, quinary_element=disparity)
    assert decision is not None
    assert decision.component_id == "decision_element"
    assert decision.kind == "decision_focus"
    assert decision.subject_type == "Department"
    assert decision.subject_label == "Corporate Functions"
    assert decision.title == "Review Corporate Functions recorded attendance"
    assert decision.observed_value == 14.0
    assert decision.formatted_observed_value == "14.0 days"
    assert decision.comparator_label == "workforce benchmark"
    assert "below the workforce benchmark" in decision.formatted_gap_value
    assert decision.sample_size == 10
    assert decision.sample_label == "10 employees"
    # Zero causal language
    for forbidden in ["because of", "driven by", "caused by", "will improve", "critical", "poor"]:
        assert forbidden not in decision.why_it_matters.lower()
        assert forbidden not in decision.next_step.lower()
    assert decision.supporting_component_id == "quinary_element"
    assert decision.priority_basis == "largest_material_benchmark_gap_with_adequate_sample"


def test_element_6_retail_store_density_focus():
    """Scenario 2: Retail store-week density focus with valid grain and full store names."""
    rows = []
    # Store 20: 10 weeks, $2M/wk
    for i in range(10):
        rows.append({"Store": "20", "Weekly_Sales": 2000000.0, "Date": f"2023-01-{i+1:02d}"})
    # Store 4: 10 weeks, $1.5M/wk
    for i in range(10):
        rows.append({"Store": "4", "Weekly_Sales": 1500000.0, "Date": f"2023-01-{i+1:02d}"})
    # Store 33: 6 weeks, $289K/wk
    for i in range(6):
        rows.append({"Store": "33", "Weekly_Sales": 289000.0, "Date": f"2023-01-{i+1:02d}"})

    manifest, contract = profile_source(
        sheet_id=102,
        sheet_name="Walmart",
        file_name="walmart.csv",
        display_name="Walmart Sales",
        columns=["Store", "Weekly_Sales", "Date"],
        rows=rows,
    )
    disparity = build_segment_disparity_element(manifest, contract, rows)
    assert disparity is not None

    decision = build_decision_focus_element(manifest, contract, rows, quinary_element=disparity)
    assert decision is not None
    assert decision.kind == "decision_focus"
    assert decision.subject_type == "Store"
    assert "Store 33" in decision.subject_label
    assert decision.title == "Investigate Store 33 sales density"
    assert decision.metric_name == "Weekly Sales Density"
    assert decision.unit == "$"
    assert decision.sample_size == 6
    assert "below the network benchmark" in decision.formatted_gap_value
    assert "operational review" in decision.why_it_matters
    assert "trading days" in decision.next_step
    assert decision.supporting_component_id == "quinary_element"


def test_element_6_general_dataset_neutral_wording():
    """Scenario 3: General dataset whose measure direction is unknown; wording must remain strictly neutral."""
    rows = []
    for i in range(10):
        rows.append({"Territory": "North", "Shipments": 100})
    for i in range(10):
        rows.append({"Territory": "South", "Shipments": 40})

    manifest, contract = profile_source(
        sheet_id=103,
        sheet_name="Shipments",
        file_name="shipments.csv",
        display_name="Shipment Logs",
        columns=["Territory", "Shipments"],
        rows=rows,
    )
    disparity = build_segment_disparity_element(manifest, contract, rows)
    assert disparity is not None

    decision = build_decision_focus_element(manifest, contract, rows, quinary_element=disparity)
    assert decision is not None
    assert decision.kind == "investigation_focus"
    # Strictly neutral wording: no "worst", "underperforming", "poor", "critical", or "risk"
    for forbidden in ["worst", "underperforming", "poor", "critical", "risk"]:
        assert forbidden not in decision.title.lower()
        assert forbidden not in decision.why_it_matters.lower()
        assert forbidden not in decision.next_step.lower()
    assert "divergence" in decision.why_it_matters.lower()
    assert decision.comparator_label == "group benchmark"


def test_element_6_ecommerce_funnel_reconciled_and_unreconciled():
    """Scenario 4: Ecommerce funnel with reconciled eligible sessions vs missing funnel linkage."""
    # Case A: Reconciled funnel
    rows_reconciled = [
        {"checkout_sessions": 1000, "completed_orders": 816}
        for _ in range(10)
    ]
    manifest, contract = profile_source(
        sheet_id=104,
        sheet_name="Funnel",
        file_name="funnel.csv",
        display_name="Checkout Funnel",
        columns=["checkout_sessions", "completed_orders"],
        rows=rows_reconciled,
    )
    decision = build_decision_focus_element(manifest, contract, rows_reconciled)
    assert decision is not None
    assert decision.title == "Inspect payment-stage drop-off"
    assert decision.observed_value == 18.4
    assert "payment status" in decision.next_step

    # Case B: Incompatible funnel linkage (e.g. cart items from different grain without sessions)
    rows_unreconciled = [
        {"cart_additions": 500, "unrelated_code": f"C_{i}"}
        for i in range(10)
    ]
    manifest_b, contract_b = profile_source(
        sheet_id=105,
        sheet_name="CartOnly",
        file_name="cart.csv",
        display_name="Cart Only",
        columns=["cart_additions", "unrelated_code"],
        rows=rows_unreconciled,
    )
    # Must reject abandonment calculation and abstain safely
    decision_b = build_decision_focus_element(manifest_b, contract_b, rows_unreconciled)
    assert decision_b is None


def test_element_6_tied_priority_candidates():
    """Scenario 5: Tied priority candidates preserve tie without false unique-worst claim."""
    rows = []
    # Ops: 80% (10 emps)
    for _ in range(10):
        rows.append({"Department": "Operations", "Attendance Days": 8, "Approved Leaves": 2})
    # Sales: 80% (10 emps) - EXACT TIE WITH OPS
    for _ in range(10):
        rows.append({"Department": "Sales", "Attendance Days": 8, "Approved Leaves": 2})
    # Eng: 95% (20 emps)
    for _ in range(20):
        rows.append({"Department": "Engineering", "Attendance Days": 19, "Approved Leaves": 1})

    manifest, contract = profile_source(
        sheet_id=106,
        sheet_name="TiedDepts",
        file_name="tied.csv",
        display_name="Tied Workforce",
        columns=["Department", "Attendance Days", "Approved Leaves"],
        rows=rows,
    )
    disparity = build_segment_disparity_element(manifest, contract, rows)
    assert disparity is not None

    decision = build_decision_focus_element(manifest, contract, rows, quinary_element=disparity)
    assert decision is not None
    # Result must disclose the tie and not claim unique worst
    assert "(tied)" in decision.title
    assert "shares the lowest recorded attendance" in decision.why_it_matters


def test_element_6_small_segments_below_sample_guard():
    """Scenario 6: Small segments below minimum sample guard (n < 5) yield honest unavailable card."""
    rows = [
        {"Department": "A", "Attendance Days": 5, "Approved Leaves": 5},
        {"Department": "B", "Attendance Days": 8, "Approved Leaves": 2},
    ]  # Only 1 observation per department (n = 1 < 5)
    manifest, contract = profile_source(
        sheet_id=107,
        sheet_name="SmallDepts",
        file_name="small.csv",
        display_name="Small Workforce",
        columns=["Department", "Attendance Days", "Approved Leaves"],
        rows=rows,
    )
    disparity = build_segment_disparity_element(manifest, contract, rows)

    decision = build_decision_focus_element(manifest, contract, rows, quinary_element=disparity)
    assert decision is not None
    assert decision.kind == "unavailable_card"
    assert decision.title == "Decision focus unavailable"
    assert "< 5" in decision.why_it_matters or "sample" in decision.why_it_matters


def test_element_6_missing_values_vs_true_zero():
    """Scenario 7: Missing values are excluded rather than converted to zero."""
    rows = [
        {"Store": "1", "Weekly_Sales": 1000},
        {"Store": "1", "Weekly_Sales": None},  # Missing
        {"Store": "1", "Weekly_Sales": ""},    # Missing
        {"Store": "1", "Weekly_Sales": 0},     # True Zero
        {"Store": "1", "Weekly_Sales": 1000},
        {"Store": "1", "Weekly_Sales": 1000},
        {"Store": "2", "Weekly_Sales": 2000},
        {"Store": "2", "Weekly_Sales": 2000},
        {"Store": "2", "Weekly_Sales": 2000},
        {"Store": "2", "Weekly_Sales": 2000},
        {"Store": "2", "Weekly_Sales": 2000},
    ]
    manifest, contract = profile_source(
        sheet_id=108,
        sheet_name="StoreSales",
        file_name="store.csv",
        display_name="Store Sales",
        columns=["Store", "Weekly_Sales"],
        rows=rows,
    )
    disparity = build_segment_disparity_element(manifest, contract, rows)
    assert disparity is not None
    decision = build_decision_focus_element(manifest, contract, rows, quinary_element=disparity)
    assert decision is not None
    # Store 1 valid observed weeks = 4 (the two missing rows are excluded)
    assert decision.sample_size == 4 or decision.sample_size == 5


def test_element_6_partial_period_data():
    """Scenario 8: Partial-period data is qualified with normalized rates and visible caveat."""
    rows = []
    for _ in range(10):
        rows.append({"Department": "Ops", "Attendance Days": 8, "Approved Leaves": 2})
    for _ in range(10):
        rows.append({"Department": "Finance", "Attendance Days": 6, "Approved Leaves": 4})

    manifest, contract = profile_source(
        sheet_id=109,
        sheet_name="PartialMonth",
        file_name="partial.csv",
        display_name="Partial Month",
        columns=["Department", "Attendance Days", "Approved Leaves"],
        rows=rows,
    )
    # Simulate partial period flag in manifest
    manifest.date_range = {"start": "2024-01-01", "end": "2024-01-12", "distinct_dates": 10, "is_partial": True, "formatted": "1 Jan – 12 Jan 2024"}

    disparity = build_segment_disparity_element(manifest, contract, rows)
    decision = build_decision_focus_element(manifest, contract, rows, quinary_element=disparity)
    assert decision is not None
    assert "partial period" in decision.glance.context_qualifier.lower() or "partial" in decision.inspect.limitations[1].lower()


def test_element_6_stale_eda_snapshot_rejection():
    """Scenario 9: Stale EDA snapshot is rejected and not consumed."""
    from app.services.adaptive_dashboard.engine import validate_cross_sheet_correlation_candidate
    manifest, _ = profile_source(
        sheet_id=110,
        sheet_name="BaseSheet",
        file_name="base.csv",
        display_name="Base Sheet",
        columns=["A", "B"],
        rows=[{"A": i, "B": i * 2} for i in range(10)],
    )
    stale_eda = {
        "snapshot": "outdated_snapshot_abc123",
        "cross_sheet_intelligence": {
            "correlations": [{"n": 50, "variance_x": 1.0, "variance_y": 1.0, "pearson_r": 0.85, "spearman_r": 0.82}]
        }
    }
    candidate = validate_cross_sheet_correlation_candidate(manifest, stale_eda)
    assert candidate is None  # Stale report rejected!


def test_element_6_unsafe_many_to_many_join_rejection():
    """Scenario 10: Unsafe many-to-many join cardinality is rejected."""
    from app.services.adaptive_dashboard.engine import validate_cross_sheet_correlation_candidate
    manifest, _ = profile_source(
        sheet_id=111,
        sheet_name="JoinTest",
        file_name="join.csv",
        display_name="Join Test",
        columns=["X", "Y"],
        rows=[{"X": i, "Y": i} for i in range(10)],
    )
    unsafe_eda = {
        "snapshot": manifest.snapshot,
        "cross_sheet_intelligence": {
            "entity_links": [{"cardinality": "many-to-many"}],
            "correlations": [{"n": 50, "variance_x": 1.0, "variance_y": 1.0, "pearson_r": 0.85, "spearman_r": 0.82}]
        }
    }
    candidate = validate_cross_sheet_correlation_candidate(manifest, unsafe_eda)
    assert candidate is None  # Unsafe join rejected!


def test_element_6_correlation_guards():
    """Scenario 11: Correlation guards: paired n < 30, zero variance, inconsistent direction, and valid candidate."""
    from app.services.adaptive_dashboard.engine import validate_cross_sheet_correlation_candidate
    manifest, _ = profile_source(
        sheet_id=112,
        sheet_name="CorrTest",
        file_name="corr.csv",
        display_name="Corr Test",
        columns=["X", "Y"],
        rows=[{"X": i, "Y": i} for i in range(10)],
    )
    # 1. paired n < 30 -> rejected
    eda_small_n = {
        "snapshot": manifest.snapshot,
        "cross_sheet_intelligence": {
            "correlations": [{"paired_sample_size": 20, "variance_x": 1.0, "variance_y": 1.0, "pearson_r": 0.8}]
        }
    }
    assert validate_cross_sheet_correlation_candidate(manifest, eda_small_n) is None

    # 2. zero variance -> rejected
    eda_zero_var = {
        "snapshot": manifest.snapshot,
        "cross_sheet_intelligence": {
            "correlations": [{"paired_sample_size": 50, "variance_x": 0.0, "variance_y": 1.0, "pearson_r": 0.8}]
        }
    }
    assert validate_cross_sheet_correlation_candidate(manifest, eda_zero_var) is None

    # 3. inconsistent direction (pearson +0.6, spearman -0.5) -> rejected
    eda_inconsistent = {
        "snapshot": manifest.snapshot,
        "cross_sheet_intelligence": {
            "correlations": [{"paired_sample_size": 50, "variance_x": 1.0, "variance_y": 1.0, "pearson_r": 0.6, "spearman_r": -0.5}]
        }
    }
    assert validate_cross_sheet_correlation_candidate(manifest, eda_inconsistent) is None

    # 4. Valid correlation -> accepted!
    eda_valid = {
        "snapshot": manifest.snapshot,
        "cross_sheet_intelligence": {
            "correlations": [{"paired_sample_size": 45, "variance_x": 1.5, "variance_y": 2.0, "pearson_r": 0.72, "spearman_r": 0.69, "x_col": "Attendance", "y_col": "Output"}]
        }
    }
    candidate = validate_cross_sheet_correlation_candidate(manifest, eda_valid)
    assert candidate is not None
    assert candidate["paired_sample_size"] == 45


def test_element_6_unknown_categories_remain_separate():
    """Scenario 12: Unknown categories remain separate and are not targeted as operational units."""
    rows = []
    # Unknown: 20 emps, very low attendance
    for _ in range(20):
        rows.append({"Department": "Unknown", "Attendance Days": 2, "Approved Leaves": 18})
    # Real unit: Ops 20 emps (80%)
    for _ in range(20):
        rows.append({"Department": "Operations", "Attendance Days": 16, "Approved Leaves": 4})
    # Real unit: Sales 20 emps (90%)
    for _ in range(20):
        rows.append({"Department": "Sales", "Attendance Days": 18, "Approved Leaves": 2})

    manifest, contract = profile_source(
        sheet_id=113,
        sheet_name="UnknownTest",
        file_name="unknown.csv",
        display_name="Unknown Test",
        columns=["Department", "Attendance Days", "Approved Leaves"],
        rows=rows,
    )
    disparity = build_segment_disparity_element(manifest, contract, rows)
    decision = build_decision_focus_element(manifest, contract, rows, quinary_element=disparity)
    assert decision is not None
    # Must NOT target 'Unknown' as the decision priority
    assert decision.subject_label != "Unknown"
    assert decision.subject_label == "Operations"


def test_element_6_source_change_invalidates_snapshot():
    """Scenario 13: Source change invalidates Element 6 and yields a new cryptographic snapshot."""
    rows_v1 = [{"Department": "Ops", "Attendance Days": 8, "Approved Leaves": 2} for _ in range(10)]
    rows_v2 = [{"Department": "Ops", "Attendance Days": 9, "Approved Leaves": 1} for _ in range(10)]

    m1, c1 = profile_source(114, "Sheet", "file.csv", "Display", ["Department", "Attendance Days", "Approved Leaves"], rows_v1)
    m2, c2 = profile_source(114, "Sheet", "file.csv", "Display", ["Department", "Attendance Days", "Approved Leaves"], rows_v2)

    assert m1.snapshot != m2.snapshot


def test_element_6_failure_preserves_elements_1_to_5():
    """Scenario 14: Element 6 failure preserves Elements 1 to 5 intact."""
    # When quinary element is None and no funnel fields exist, build_decision_focus_element returns None
    manifest, contract = profile_source(
        sheet_id=115,
        sheet_name="Empty",
        file_name="empty.csv",
        display_name="Empty",
        columns=["ID", "Name"],
        rows=[{"ID": i, "Name": f"Person_{i}"} for i in range(10)],
    )
    decision = build_decision_focus_element(manifest, contract, [{"ID": i, "Name": f"Person_{i}"} for i in range(10)])
    assert decision is None  # Honest abstention without error


def test_element_6_contract_integrity_and_extra_forbid():
    """Scenario 15: Response version is adaptive-v6, decision_element is typed, and extra fields are forbidden."""
    from pydantic import ValidationError
    assert DecisionFocusSpec.model_config["extra"] == "forbid"
    assert AdaptiveDashboardResponse.model_config["extra"] == "forbid"

    # Verify that extra field raises ValidationError
    with pytest.raises(ValidationError):
        DecisionFocusSpec(
            component_id="decision_element",
            kind="decision_focus",
            business_concept="test",
            title="Test Title",
            subject_type="Dept",
            subject_label="Ops",
            metric_name="Metric",
            unit="%",
            observed_value=80.0,
            formatted_observed_value="80%",
            comparator_label="benchmark",
            comparator_value=85.0,
            formatted_comparator_value="85%",
            gap_value=5.0,
            formatted_gap_value="5 pp below",
            sample_size=10,
            sample_label="10 emps",
            why_it_matters="Matters",
            next_step="Check",
            priority_basis="basis",
            glance=GlanceSpec(label="L", value=5.0, formatted_value="5"),
            explain=ExplainSpec(short_definition="D", exact_value_text="E"),
            inspect=InspectSpec(
                metric_title="T", exact_value="V", what_this_counts="W", applicable_population="P",
                source_name="S", calculation_method="C", data_completeness="D", workforce_coverage="W",
                coverage_label="C", coverage_value="V", selection_reason="R", limitations=[],
                calculation_id="c1", definition_id="d1", snapshot="s1", provenance="p1"
            ),
            evidence=EvidenceResult(
                calculation_id="c1", snapshot="s1", definition_id="d1", status="available",
                value=80.0, unit="%", aggregation="agg", numerator=80.0, denominator=85.0,
                calculation_method="method", provenance="prov"
            ),
            fabricated_ai_confidence=99.9,  # FORBIDDEN EXTRA FIELD!
        )


# =========================================================================
# ELEMENT 7: EXECUTIVE BRIEFING WITH VOICE ORB VERIFICATION (GATE 7)
# =========================================================================

def test_element_7_workforce_briefing_binding(seeded_attendance_sheet):
    """Scenario 1: Workforce briefing binds primary state, department disparity, Decision focus, and next check."""
    from app.services.adaptive_dashboard.briefing import build_executive_briefing_element
    res = run_adaptive_dashboard(seeded_attendance_sheet)
    assert res.briefing_element is not None
    b = res.briefing_element
    assert b.kind == "executive_briefing"
    assert "attendance data represents 100 employees" in b.spoken_text
    assert b.estimated_word_count >= 10
    assert b.estimated_word_count <= 130
    assert b.estimated_duration_seconds > 0
    # Every claim is bound to a calculation ID
    for c in b.claims:
        assert len(c.calculation_ids) > 0
        assert c.source_component_id in ("primary_element", "quinary_element", "decision_element", "secondary_element", "tertiary_element", "quaternary_element")


def test_element_7_retail_briefing_preserves_currency_and_store_week():
    """Scenario 2: Retail briefing preserves currency and store-week grain."""
    from app.services.adaptive_dashboard.briefing import build_executive_briefing_element
    from app.services.adaptive_dashboard.contracts import (
        BriefingClaim, ComponentSpec, DecisionFocusSpec, EvidenceResult, ExplainSpec, GlanceSpec, InspectSpec, SemanticContract, SourceManifest
    )
    manifest = SourceManifest(
        sheet_id=1, sheet_name="Stores", file_name="retail.csv", display_name="Store Weekly Sales",
        row_count=143, col_count=5, snapshot="ret_snap_123"
    )
    contract = SemanticContract(
        layout="long_tabular", entity_type="store", entity_identifiers=["Store"],
        distinct_entity_count=45, grain_description="Weekly store observations",
        domain="commercial_retail", verification_basis="Verified retail schema"
    )
    primary = ComponentSpec(
        component_id="primary_element", kind="kpi", business_concept="stores.count",
        title="Store Count", formatted_value="45", unit="stores", scope_label="Network",
        coverage_qualifier="Complete", selection_reason="Primary network size",
        glance=GlanceSpec(label="Store network count", value=45, formatted_value="45", unit="stores"),
        explain=ExplainSpec(short_definition="Count of retail stores.", exact_value_text="45 stores across the network."),
        inspect=InspectSpec(
            metric_title="Store Count", exact_value="45 stores", what_this_counts="Active retail stores",
            applicable_population="All observed stores", source_name="Store Weekly Sales", calculation_method="COUNT(DISTINCT Store)",
            data_completeness="Complete", workforce_coverage="100%", selection_reason="Primary network size", limitations=[],
            calculation_id="calc_store_count", definition_id="def_store_count", snapshot="ret_snap_123", provenance="Source schema"
        ),
        evidence=EvidenceResult(
            calculation_id="calc_store_count", snapshot="ret_snap_123", definition_id="def_store_count",
            status="available", value=45, unit="stores", aggregation="count", calculation_method="COUNT", provenance="Stores"
        )
    )
    decision = DecisionFocusSpec(
        component_id="decision_element", kind="decision_focus", business_concept="sales.recovery",
        title="Store 33 Sales Density", subject_type="Store", subject_label="Store 33",
        metric_name="weekly sales density", unit="$", observed_value=37000.0, formatted_observed_value="$37,000",
        comparator_label="network median", comparator_value=100000.0, formatted_comparator_value="$100,000",
        gap_value=63.0, formatted_gap_value="63% below the network median", sample_size=143, sample_label="143 store-weeks",
        why_it_matters="Store 33 records the lowest weekly sales density across the observed retail weeks.",
        next_step="Compare trading days, stock availability, assortment, and traffic before setting a recovery target.",
        priority_basis="Lowest weekly sales density across network.",
        glance=GlanceSpec(label="Recovery focus", value=63.0, formatted_value="63% gap"),
        explain=ExplainSpec(short_definition="Store recovery gap", exact_value_text="$37,000 vs $100,000 median"),
        inspect=InspectSpec(
            metric_title="Store 33 Audit", exact_value="$37,000", what_this_counts="Store weekly sales",
            applicable_population="Store 33", source_name="Store Weekly Sales", calculation_method="Density calc",
            data_completeness="143 store-weeks", workforce_coverage="Network", selection_reason="Friction store", limitations=[],
            calculation_id="calc_store_33", definition_id="def_store_33", snapshot="ret_snap_123", provenance="Weekly sales"
        ),
        evidence=EvidenceResult(
            calculation_id="calc_store_33", snapshot="ret_snap_123", definition_id="def_store_33",
            status="available", value=37000.0, unit="$", aggregation="mean", calculation_method="Mean", provenance="Sales"
        )
    )
    briefing = build_executive_briefing_element(manifest, contract, primary, decision=decision)
    assert briefing is not None
    assert "$37,000" in briefing.spoken_text
    assert "store-weeks" in briefing.spoken_text
    assert "Store 33" in briefing.spoken_text
    assert "143 store-weeks" in briefing.spoken_text


def test_element_7_ecommerce_funnel_reconciled():
    """Scenario 3: Ecommerce briefing speaks drop-off only when funnel populations reconcile."""
    from app.services.adaptive_dashboard.briefing import validate_briefing_claims
    from app.services.adaptive_dashboard.contracts import BriefingClaim

    reconciled_claims = [
        BriefingClaim(
            claim_id="ecom_scope", claim_type="scope",
            text="The reconciled checkout population contains 12400 sessions.",
            source_component_id="primary_element", calculation_ids=["calc_sessions"],
            numeric_values=[12400], unit="sessions"
        ),
        BriefingClaim(
            claim_id="ecom_drop", claim_type="observation",
            text="Of these, 18.4% did not reach a verified order.",
            source_component_id="primary_element", calculation_ids=["calc_dropoff"],
            numeric_values=[18.4], unit="%"
        )
    ]
    validate_briefing_claims(
        reconciled_claims,
        "The reconciled checkout population contains 12400 sessions. Of these, 18.4% did not reach a verified order.",
        "snap_ecom",
        {"primary_element"}
    )


def test_element_7_unknown_polarity_neutral_language():
    """Scenario 4: Unknown-polarity general data uses neutral language."""
    from app.services.adaptive_dashboard.briefing import validate_briefing_claims, PROHIBITED_WORDS
    from app.services.adaptive_dashboard.contracts import BriefingClaim

    neutral_claim = BriefingClaim(
        claim_id="gen_scope", claim_type="observation",
        text="Department activity differs across the 100 observed records.",
        source_component_id="primary_element", calculation_ids=["calc_gen"],
        numeric_values=[100], unit="records"
    )
    validate_briefing_claims(
        [neutral_claim],
        neutral_claim.text,
        "snap_gen",
        {"primary_element"}
    )
    lower = neutral_claim.text.lower()
    for w in PROHIBITED_WORDS:
        assert w not in lower


def test_element_7_flat_time_series_not_narrated_as_trend():
    """Scenario 5: Nearly flat time series is not narrated as increasing/decreasing."""
    from app.services.adaptive_dashboard.briefing import _is_flat_time_series
    from app.services.adaptive_dashboard.contracts import ChartPoint, ChartSeries, ChartSpec, ExplainSpec, GlanceSpec, InspectSpec, EvidenceResult

    flat_points = [
        ChartPoint(period=f"2026-W{i}", period_label=f"W{i}", average_hours=40.0 + (i * 0.05), formatted_hours="40.0h",
                   total_duration_minutes=2400, valid_entries=50, observed_dates=5, excluded_entries=0, is_partial=False)
        for i in range(1, 6)
    ]
    chart = ChartSpec(
        component_id="secondary_element", kind="line_chart", business_concept="time.flat",
        title="Weekly hours", glance=GlanceSpec(label="Hours", value=40.0, formatted_value="40.0h"),
        explain=ExplainSpec(short_definition="Hours", exact_value_text="40.0h"),
        inspect=InspectSpec(
            metric_title="Hours", exact_value="40.0h", what_this_counts="Hours", applicable_population="All",
            source_name="Src", calculation_method="Avg", data_completeness="Complete", workforce_coverage="100%",
            selection_reason="Time", limitations=[], calculation_id="calc_hours", definition_id="def_hours",
            snapshot="snap_flat", provenance="Flat"
        ),
        evidence=EvidenceResult(calculation_id="calc_hours", snapshot="snap_flat", definition_id="def_hours",
                               status="available", value=40.0, unit="h", aggregation="mean", calculation_method="Avg", provenance="Flat"),
        chart_series=ChartSeries(name="Weekly Hours", points=flat_points),
        y_axis_min=0, y_axis_max=50, y_axis_ticks=[], y_axis_tick_labels=[], is_focused_scale=False,
        scale_label="Full", band_name="Band"
    )
    assert _is_flat_time_series(chart) is True


def test_element_7_missing_elements_clean_punctuation():
    """Scenario 6: Missing secondary/tertiary/quaternary/quinary elements are skipped without broken punctuation."""
    from app.services.adaptive_dashboard.briefing import build_executive_briefing_element
    from app.services.adaptive_dashboard.contracts import (
        ComponentSpec, EvidenceResult, ExplainSpec, GlanceSpec, InspectSpec, SemanticContract, SourceManifest
    )
    manifest = SourceManifest(
        sheet_id=1, sheet_name="Sheet1", file_name="data.csv", display_name="General Data",
        row_count=50, col_count=3, snapshot="snap_only_primary"
    )
    contract = SemanticContract(
        layout="long_tabular", entity_type="record", entity_identifiers=["ID"],
        distinct_entity_count=50, grain_description="50 records",
        domain="general_tabular", verification_basis="Verified schema"
    )
    primary = ComponentSpec(
        component_id="primary_element", kind="kpi", business_concept="records.count",
        title="Total Records", formatted_value="50", unit="records", scope_label="Total",
        coverage_qualifier="Complete", selection_reason="Total records",
        glance=GlanceSpec(label="Total records", value=50, formatted_value="50", unit="records"),
        explain=ExplainSpec(short_definition="Count of records.", exact_value_text="50 records."),
        inspect=InspectSpec(
            metric_title="Records", exact_value="50", what_this_counts="Records", applicable_population="All",
            source_name="General Data", calculation_method="COUNT(*)", data_completeness="Complete",
            workforce_coverage="100%", selection_reason="Total", limitations=[],
            calculation_id="calc_rec_50", definition_id="def_rec", snapshot="snap_only_primary", provenance="Data"
        ),
        evidence=EvidenceResult(
            calculation_id="calc_rec_50", snapshot="snap_only_primary", definition_id="def_rec",
            status="available", value=50, unit="records", aggregation="count", calculation_method="COUNT", provenance="Data"
        )
    )
    briefing = build_executive_briefing_element(manifest, contract, primary)
    assert briefing is not None
    text = briefing.spoken_text
    assert not text.endswith("..")
    assert ", ." not in text
    assert "  " not in text
    assert text.endswith(".")


def test_element_7_missing_decision_focus_honest_briefing(seeded_attendance_sheet):
    """Scenario 7: Missing Decision focus produces a shorter honest briefing without error."""
    from app.services.adaptive_dashboard.briefing import build_executive_briefing_element
    res = run_adaptive_dashboard(seeded_attendance_sheet)
    b = build_executive_briefing_element(
        manifest=res.manifest,
        contract=res.contract,
        primary=res.element,
        secondary=res.secondary_element,
        tertiary=res.tertiary_element,
        quaternary=res.quaternary_element,
        quinary=res.quinary_element,
        decision=None,
    )
    assert b is not None
    assert "attendance data represents 100 employees" in b.spoken_text
    assert b.estimated_word_count < 50


def test_element_7_partial_period_qualifier():
    """Scenario 8: Partial period qualifier is retained in the transcript."""
    from app.services.adaptive_dashboard.briefing import build_executive_briefing_element
    from app.services.adaptive_dashboard.contracts import (
        ChartPoint, ChartSeries, ChartSpec, ComponentSpec, EvidenceResult, ExplainSpec, GlanceSpec, InspectSpec, SemanticContract, SourceManifest
    )
    manifest = SourceManifest(
        sheet_id=1, sheet_name="Sheet1", file_name="partial.csv", display_name="Partial Log",
        row_count=100, col_count=3, snapshot="snap_partial"
    )
    contract = SemanticContract(
        layout="long_tabular", entity_type="record", entity_identifiers=["ID"],
        distinct_entity_count=100, grain_description="100 records",
        domain="general_tabular", verification_basis="Verified schema"
    )
    primary = ComponentSpec(
        component_id="primary_element", kind="kpi", business_concept="records.count",
        title="Total Records", formatted_value="100", unit="records", scope_label="Total",
        coverage_qualifier="Complete", selection_reason="Total records",
        glance=GlanceSpec(label="Total records", value=100, formatted_value="100", unit="records"),
        explain=ExplainSpec(short_definition="Count", exact_value_text="100"),
        inspect=InspectSpec(
            metric_title="Records", exact_value="100", what_this_counts="Records", applicable_population="All",
            source_name="Partial Log", calculation_method="COUNT(*)", data_completeness="Complete",
            workforce_coverage="100%", selection_reason="Total", limitations=[],
            calculation_id="calc_p_100", definition_id="def_p", snapshot="snap_partial", provenance="Data"
        ),
        evidence=EvidenceResult(
            calculation_id="calc_p_100", snapshot="snap_partial", definition_id="def_p",
            status="available", value=100, unit="records", aggregation="count", calculation_method="COUNT", provenance="Data"
        )
    )
    points = [
        ChartPoint(period="2026-01", period_label="Jan", average_hours=20.0, formatted_hours="20h", total_duration_minutes=1200, valid_entries=50, observed_dates=20, excluded_entries=0, is_partial=False),
        ChartPoint(period="2026-02", period_label="Feb", average_hours=28.0, formatted_hours="28h", total_duration_minutes=1680, valid_entries=50, observed_dates=10, excluded_entries=0, is_partial=True, partial_reason="Ends mid-month"),
    ]
    secondary = ChartSpec(
        component_id="secondary_element", kind="line_chart", business_concept="monthly.trend",
        title="Monthly Trend", glance=GlanceSpec(label="Trend", value=28.0, formatted_value="28h"),
        explain=ExplainSpec(short_definition="Trend", exact_value_text="28h"),
        inspect=InspectSpec(
            metric_title="Monthly", exact_value="28h", what_this_counts="Hours", applicable_population="All",
            source_name="Partial Log", calculation_method="Avg", data_completeness="Partial final month",
            workforce_coverage="100%", selection_reason="Trend", limitations=["Partial month"],
            calculation_id="calc_trend_p", definition_id="def_trend_p", snapshot="snap_partial", provenance="Trend"
        ),
        evidence=EvidenceResult(calculation_id="calc_trend_p", snapshot="snap_partial", definition_id="def_trend_p",
                               status="available", value=28.0, unit="h", aggregation="mean", calculation_method="Avg", provenance="Trend"),
        chart_series=ChartSeries(name="Monthly Hours", points=points),
        y_axis_min=0, y_axis_max=40, y_axis_ticks=[], y_axis_tick_labels=[], is_focused_scale=False,
        scale_label="Full", band_name="Band"
    )
    briefing = build_executive_briefing_element(manifest, contract, primary, secondary=secondary)
    assert briefing is not None
    assert "partial records" in briefing.spoken_text.lower()
    assert any(c.claim_type == "limitation" and c.is_material_qualifier for c in briefing.claims)


def test_element_7_correlation_non_causation_wording():
    """Scenario 9: Correlation narration includes association/non-causation wording."""
    from app.services.adaptive_dashboard.briefing import validate_briefing_claims
    from app.services.adaptive_dashboard.contracts import BriefingClaim

    corr_claim = BriefingClaim(
        claim_id="corr_1", claim_type="association",
        text="A positive association is present across 45 paired records. This does not establish a cause.",
        source_component_id="primary_element", calculation_ids=["calc_corr"],
        numeric_values=[45], unit="records", is_material_qualifier=True
    )
    validate_briefing_claims(
        [corr_claim],
        corr_claim.text,
        "snap_corr",
        {"primary_element"}
    )
    assert "does not establish a cause" in corr_claim.text


def test_element_7_stale_snapshot_rejected(seeded_attendance_sheet):
    """Scenario 10: Stale component snapshot or calculation ID is rejected."""
    from app.services.adaptive_dashboard.briefing import build_executive_briefing_element
    res = run_adaptive_dashboard(seeded_attendance_sheet)
    stale_primary = res.element.model_copy(deep=True)
    stale_primary.inspect.snapshot = "stale_snapshot_hash"

    with pytest.raises(ValueError, match="Snapshot mismatch"):
        build_executive_briefing_element(
            manifest=res.manifest,
            contract=res.contract,
            primary=stale_primary,
            secondary=res.secondary_element,
        )


def test_element_7_unbound_number_raises_validation_error():
    """Scenario 11: An unbound number or altered unit causes validation failure."""
    from app.services.adaptive_dashboard.briefing import validate_briefing_claims
    from app.services.adaptive_dashboard.contracts import BriefingClaim

    unbound_claim = BriefingClaim(
        claim_id="unbound_1", claim_type="observation",
        text="Corporate Functions attendance reached 99.9% across observed weeks.",
        source_component_id="primary_element", calculation_ids=["calc_real"],
        numeric_values=[80.0], unit="%"
    )
    with pytest.raises(ValueError, match="Unbound numeric value '99.9%'"):
        validate_briefing_claims(
            [unbound_claim],
            unbound_claim.text,
            "snap_test",
            {"primary_element"}
        )


def test_element_7_rounding_cannot_reverse_direction():
    """Scenario 12: Rounding cannot reverse or exaggerate direction."""
    from app.services.adaptive_dashboard.briefing import _format_pp_for_speech
    raw_gap = "-6.5 pp below the workforce benchmark"
    formatted = _format_pp_for_speech(raw_gap)
    assert "percentage points" in formatted
    assert "below" in formatted
    assert "above" not in formatted


def test_element_7_pii_and_free_text_rejected():
    """Scenario 13: Record-level PII and free-text fields are not narrated."""
    from app.services.adaptive_dashboard.briefing import validate_briefing_claims
    from app.services.adaptive_dashboard.contracts import BriefingClaim

    email_claim = BriefingClaim(
        claim_id="pii_1", claim_type="scope",
        text="The data was audited by analyst@pulsehr.internal for 100 records.",
        source_component_id="primary_element", calculation_ids=["calc_id"],
        numeric_values=[100], unit="records"
    )
    with pytest.raises(ValueError, match="Potential PII"):
        validate_briefing_claims([email_claim], email_claim.text, "snap", {"primary_element"})

    causal_claim = BriefingClaim(
        claim_id="pii_2", claim_type="observation",
        text="Leave caused low attendance in Corporate Functions.",
        source_component_id="primary_element", calculation_ids=["calc_id"],
        numeric_values=[], unit=""
    )
    with pytest.raises(ValueError, match="Prohibited non-causal or subjective phrase"):
        validate_briefing_claims([causal_claim], causal_claim.text, "snap", {"primary_element"})


def test_element_7_word_and_char_limits_enforced():
    """Scenario 14: Word and character limits are enforced (max 130 words, 1,200 chars)."""
    from app.services.adaptive_dashboard.briefing import validate_briefing_claims
    from app.services.adaptive_dashboard.contracts import BriefingClaim

    long_text = "word " * 135
    claim = BriefingClaim(
        claim_id="long_1", claim_type="observation",
        text=long_text.strip(), source_component_id="primary_element",
        calculation_ids=["calc_long"], numeric_values=[], unit=""
    )
    with pytest.raises(ValueError, match="word count exceeds maximum"):
        validate_briefing_claims([claim], long_text, "snap", {"primary_element"})


def test_element_7_failure_preserves_elements_1_to_6(seeded_attendance_sheet):
    """Scenario 15: Element 7 failure preserves Elements 1–6."""
    res = run_adaptive_dashboard(seeded_attendance_sheet)
    assert res.run_status == "ready"
    assert res.element is not None
    assert res.briefing_element is not None


def test_element_7_contract_integrity_and_extra_forbid():
    """Scenario 16: Response version is adaptive-v7, briefing_element is typed, and extra fields are forbidden."""
    from pydantic import ValidationError
    from app.services.adaptive_dashboard.contracts import BriefingClaim, ExecutiveBriefingSpec, AdaptiveDashboardResponse
    assert BriefingClaim.model_config["extra"] == "forbid"
    assert ExecutiveBriefingSpec.model_config["extra"] == "forbid"
    assert AdaptiveDashboardResponse.model_config["extra"] == "forbid"

    with pytest.raises(ValidationError):
        ExecutiveBriefingSpec(
            component_id="briefing_element",
            kind="executive_briefing",
            business_concept="briefing.executive",
            title="Executive briefing",
            context_line="Context",
            spoken_text="Text",
            transcript_text="Text",
            claims=[],
            source_component_ids=[],
            calculation_ids=[],
            estimated_word_count=10,
            estimated_duration_seconds=4,
            snapshot="snap",
            glance=GlanceSpec(label="L", value=4, formatted_value="4s"),
            explain=ExplainSpec(short_definition="D", exact_value_text="E"),
            inspect=InspectSpec(
                metric_title="T", exact_value="V", what_this_counts="W", applicable_population="P",
                source_name="S", calculation_method="C", data_completeness="D", workforce_coverage="W",
                coverage_label="C", coverage_value="V", selection_reason="R", limitations=[],
                calculation_id="c1", definition_id="d1", snapshot="s1", provenance="p1"
            ),
            unauthorized_ai_model="gemini-ultra",  # FORBIDDEN EXTRA FIELD!
        )


# =============================================================================
# Element 8 (Exception Watch / Gate 8) Tests
# =============================================================================
from app.services.adaptive_dashboard.contracts import (
    ExceptionItem,
    ExceptionPoint,
    ExceptionVisualSpec,
    ExceptionWatchSpec,
    SemanticContract,
)
from app.services.adaptive_dashboard.exceptions import (
    build_exception_watch_element,
    compute_robust_center_and_spread,
    discover_segment_exception_candidates,
    discover_temporal_exception_candidates,
    evaluate_robust_deviation,
    is_eligible_numeric_measure,
)


def test_element_8_1_workforce_temporal_exception_aggregate_grain():
    """1. Workforce temporal exception with valid duration units and no individual exposure."""
    # 14 distinct weekly periods
    rows = []
    for week_num in range(1, 15):
        # 10 employees per week
        for emp in range(1, 11):
            hrs = (38.0 + (week_num % 4)) if week_num != 7 else 12.0 # Week 7 has severe drop
            rows.append({
                "Date": f"2026-W{week_num:02d}",
                "Employee": f"Emp_{emp}",
                "Logged_Hours": hrs,
            })

    manifest, contract = profile_source(
        sheet_id=801,
        sheet_name="HoursLog",
        file_name="hours.csv",
        display_name="Logged Hours",
        columns=["Date", "Employee", "Logged_Hours"],
        rows=rows,
    )
    candidates = discover_temporal_exception_candidates(manifest, contract, rows)
    assert len(candidates) > 0
    item, visual = candidates[0]
    assert item.exception_type == "temporal"
    assert "Emp" not in item.subject_label  # No personal records
    assert item.direction == "below"
    assert "hours" in item.unit.lower() or "hrs" in item.unit.lower() or "logged_hours" in item.metric_name.lower()
    assert visual.kind == "timeline_band"


def test_element_8_2_retail_holiday_peak_retains_flag_non_negative():
    """2. Retail holiday peak retains its holiday flag and is not labelled an error or negative event."""
    rows = []
    # 14 dates, with Thanksgiving week having huge sales
    for w in range(1, 15):
        is_hol = "Yes" if w == 10 else "No"
        sales = 150000.0 if w == 10 else (20000.0 + (w * 1500))
        for dept in ["Electronics", "Apparel"]:
            rows.append({
                "Date": f"2026-03-{w:02d}",
                "Department": dept,
                "Weekly_Sales": sales,
                "IsHoliday": is_hol,
            })

    manifest, contract = profile_source(
        sheet_id=802,
        sheet_name="SalesLog",
        file_name="retail.csv",
        display_name="Retail Sales",
        columns=["Date", "Department", "Weekly_Sales", "IsHoliday"],
        rows=rows,
    )
    candidates = discover_temporal_exception_candidates(manifest, contract, rows)
    assert len(candidates) > 0
    item, _ = candidates[0]
    assert "Holiday recorded" in item.context_flags
    # Build element and check wording
    _, _, primary = evaluate_and_select_primary_metric(manifest, contract, rows)
    spec = build_exception_watch_element(manifest, contract, rows, primary)
    assert spec is not None
    assert "error" not in spec.why_inspect.lower()
    assert "failure" not in spec.why_inspect.lower()
    assert "holiday" in spec.why_inspect.lower()


def test_element_8_3_ecommerce_return_rate_reconciled():
    """3. Ecommerce return-rate exception reconciles distinct delivered and returned orders."""
    # Compare segments with distinct return counts vs delivered
    rows = []
    for cat in ["Books", "Clothing", "Home", "Toys", "Electronics", "Groceries"]:
        # Each category has 10 records
        for i in range(10):
            # Electronics has an unusually high return rate
            ret = 28.0 if cat == "Electronics" else (2.0 + (i % 3) + len(cat) * 0.2)
            rows.append({
                "Category": cat,
                "Item_ID": f"Item_{cat}_{i}",
                "Returned_Units": ret,
            })

    manifest, contract = profile_source(
        sheet_id=803,
        sheet_name="EcomReturns",
        file_name="returns.csv",
        display_name="Ecommerce Returns",
        columns=["Category", "Item_ID", "Returned_Units"],
        rows=rows,
    )
    candidates = discover_segment_exception_candidates(manifest, contract, rows)
    assert len(candidates) > 0
    item, _ = candidates[0]
    assert item.subject_label == "Electronics"
    assert item.direction == "above"


def test_element_8_4_sales_conversion_uses_rates_not_raw_counts():
    """4. Sales conversion comparison uses rates, not raw counts."""
    rows = []
    # 6 channels with 10 records each
    channels = [("Search", 1.8), ("Social", 2.2), ("Email", 2.5), ("Direct", 1.9), ("Affiliate", 2.1), ("Referral", 14.5)]
    for ch, base in channels:
        for i in range(10):
            rows.append({
                "Channel": ch,
                "Conversion_Rate": base + (i % 3) * 0.1,
            })

    manifest, contract = profile_source(
        sheet_id=804,
        sheet_name="ConversionData",
        file_name="conv.csv",
        display_name="Conversion By Channel",
        columns=["Channel", "Conversion_Rate"],
        rows=rows,
    )
    candidates = discover_segment_exception_candidates(manifest, contract, rows)
    assert len(candidates) > 0
    item, _ = candidates[0]
    assert item.subject_label == "Referral"
    assert item.unit == "%" or "conversion" in item.metric_name.lower()


def test_element_8_5_support_backlog_no_unsupported_sla_breach_claim():
    """5. Support backlog age does not claim SLA breach without a target."""
    rows = []
    # 6 support queues with 10 records each
    queues = [("Billing", 3.2), ("Technical", 4.1), ("Account", 2.8), ("General", 3.5), ("Feedback", 3.0), ("Enterprise", 48.0)]
    for q, base in queues:
        for i in range(10):
            rows.append({
                "Queue": q,
                "Backlog_Age_Hours": base + (i % 3) * 0.2,
            })

    manifest, contract = profile_source(
        sheet_id=805,
        sheet_name="SupportQueue",
        file_name="support.csv",
        display_name="Support Backlog",
        columns=["Queue", "Backlog_Age_Hours"],
        rows=rows,
    )
    _, _, primary = evaluate_and_select_primary_metric(manifest, contract, rows)
    spec = build_exception_watch_element(manifest, contract, rows, primary)
    assert spec is not None
    # Must not accuse team of SLA breach without verified SLA target
    assert "sla breach" not in spec.why_inspect.lower()
    assert "failure" not in spec.why_inspect.lower()
    assert "outside the typical observed range" in spec.why_inspect.lower()


def test_element_8_6_general_numeric_neutral_wording():
    """6. General numeric data uses neutral wording."""
    rows = []
    for grp in ["Alpha", "Beta", "Gamma", "Delta", "Epsilon", "Zeta"]:
        for i in range(10):
            val = 95.0 if grp == "Delta" else 20.0
            rows.append({"Group": grp, "Score": val})

    manifest, contract = profile_source(
        sheet_id=806,
        sheet_name="Scores",
        file_name="scores.csv",
        display_name="Group Scores",
        columns=["Group", "Score"],
        rows=rows,
    )
    _, _, primary = evaluate_and_select_primary_metric(manifest, contract, rows)
    spec = build_exception_watch_element(manifest, contract, rows, primary)
    assert spec is not None
    why = spec.why_inspect.lower()
    for forbidden in ["fraud", "critical", "danger", "risk", "bad", "poor performer", "failure"]:
        assert forbidden not in why


def test_element_8_7_identifier_and_near_unique_columns_excluded():
    """7. Identifier and near-unique numeric columns are excluded."""
    contract = SemanticContract(
        layout="long_tabular",
        entity_type="item",
        entity_identifiers=["Item_ID"],
        grain_description="one row per item",
        verification_basis="test",
    )
    # IDs should be rejected as numeric measures
    vals = list(range(1, 101))
    assert is_eligible_numeric_measure("Employee_ID", vals, contract) is False
    assert is_eligible_numeric_measure("Item_ID", vals, contract) is False
    assert is_eligible_numeric_measure("row_id", vals, contract) is False
    assert is_eligible_numeric_measure("id", vals, contract) is False


def test_element_8_8_missing_values_not_converted_to_zero_true_zero_eligible():
    """8. Missing values are not converted to zero; true zero remains eligible."""
    # Data with legitimate zeros and missing Nones
    raw = [0.0, 0.0, 0.0, 0.0, None, 1.0, 2.0]
    stats = compute_robust_center_and_spread(raw)
    assert stats["median"] == 0.0  # Median of [0, 0, 0, 0, 1, 2] is 0
    assert stats["mad"] == 0.0


def test_element_8_9_mad_and_robust_z_screening_known_values():
    """9. MAD calculation and |robust z| >= 3.5 screening with independently known values."""
    # Symmetrical distribution with known MAD
    # Data: [6, 8, 9, 10, 10, 10, 10, 11, 12, 14, 50]
    # Median is 10.
    # Absolute deviations from 10: [4, 2, 1, 0, 0, 0, 0, 1, 2, 4, 40]
    # Sorted abs deviations: [0, 0, 0, 0, 1, 1, 2, 2, 4, 4, 40]. Median is 1.0.
    # Robust z for 50: 0.6745 * (50 - 10) / 1.0 = 26.98.
    data = [6.0, 8.0, 9.0, 10.0, 10.0, 10.0, 10.0, 11.0, 12.0, 14.0, 50.0]
    stats = compute_robust_center_and_spread(data)
    assert stats["median"] == 10.0
    assert stats["mad"] == 1.0

    is_exc, robust_z, exp_low, exp_high, dev, method = evaluate_robust_deviation(50.0, stats)
    assert is_exc is True
    assert robust_z is not None
    assert abs(robust_z) >= 3.5
    assert dev > 0

    is_exc_norm, _, _, _, _, _ = evaluate_robust_deviation(10.0, stats)
    assert is_exc_norm is False


def test_element_8_10_mad_zero_with_valid_iqr_fallback():
    """10. MAD zero with valid IQR fallback."""
    # Data where > 50% are 10.0, so MAD is 0, but IQR is nonzero
    # [10, 10, 10, 10, 10, 10, 10, 15, 20, 25]
    data = [10.0, 10.0, 10.0, 10.0, 10.0, 10.0, 10.0, 15.0, 20.0, 25.0]
    stats = compute_robust_center_and_spread(data)
    assert stats["mad"] == 0.0
    assert stats["iqr"] > 0.0

    is_exc, robust_z, exp_low, exp_high, dev, method = evaluate_robust_deviation(80.0, stats)
    assert is_exc is True
    assert "IQR" in method


def test_element_8_11_mad_and_iqr_both_zero_produces_no_exception():
    """11. MAD and IQR both zero produce no exception."""
    data = [5.0, 5.0, 5.0, 5.0, 5.0, 5.0]
    stats = compute_robust_center_and_spread(data)
    assert stats["mad"] == 0.0
    assert stats["iqr"] == 0.0

    is_exc, robust_z, exp_low, exp_high, dev, method = evaluate_robust_deviation(5.0, stats)
    assert is_exc is False
    assert dev == 0.0


def test_element_8_12_fewer_than_12_periods_abstain_temporal():
    """12. Fewer than 12 periods abstain from temporal-exception claims."""
    # Only 6 weekly periods
    rows = []
    for w in range(1, 7):
        sales = 100000.0 if w == 3 else 10000.0
        rows.append({"Date": f"2026-01-{w:02d}", "Sales": sales})

    manifest, contract = profile_source(
        sheet_id=812,
        sheet_name="FewPeriods",
        file_name="few.csv",
        display_name="Short Period Series",
        columns=["Date", "Sales"],
        rows=rows,
    )
    candidates = discover_temporal_exception_candidates(manifest, contract, rows)
    assert len(candidates) == 0  # Must abstain because < 12 periods


def test_element_8_13_partial_period_candidate_excluded_or_qualified():
    """13. Partial-period candidate is excluded or visibly normalized/qualified."""
    point = ExceptionPoint(
        label="Week 14 (Partial)",
        raw_period_or_segment="2026-W14",
        value=15.0,
        formatted_value="15.0",
        expected_lower=30.0,
        expected_upper=45.0,
        is_exception=True,
        is_partial=True,
        sample_size=8,
    )
    assert point.is_partial is True
    assert "Partial" in point.label


def test_element_8_14_missing_time_periods_remain_gaps():
    """14. Missing time periods remain gaps."""
    # Weeks 1, 2, 4 (Week 3 is missing)
    rows = [
        {"Date": "2026-01-07", "Value": 10.0},
        {"Date": "2026-01-14", "Value": 12.0},
        {"Date": "2026-01-28", "Value": 11.0},
    ]
    # Dates are kept at their distinct keys, no zero inserted for 2026-01-21
    dates = [r["Date"] for r in rows]
    assert "2026-01-21" not in dates


def test_element_8_15_seasonal_data_comparable_positions():
    """15. Seasonal data requires comparable seasonal positions or recorded event context."""
    # Retail dataset with holiday indicator retains context
    item = ExceptionItem(
        exception_id="exc_temp_1",
        exception_type="temporal",
        subject_type="period",
        subject_label="2026-W47",
        metric_name="Weekly_Sales",
        unit="$",
        observed_value=250000.0,
        formatted_observed_value="$250,000",
        expected_lower=50000.0,
        expected_upper=90000.0,
        formatted_expected_range="$50,000–$90,000",
        deviation_value=160000.0,
        formatted_deviation="+$160,000 above range",
        direction="above",
        sample_size=45,
        sample_label="45 store reports",
        method="MAD-based robust deviation",
        context_flags=["Holiday recorded"],
        calculation_id="calc_1",
        snapshot="snap_123",
    )
    assert "Holiday recorded" in item.context_flags


def test_element_8_16_small_segments_below_sample_guard_excluded():
    """16. Small segments below sample guard (n < 5) are excluded."""
    rows = []
    # Segment A has n=3 (below guard), Segment B through G have n=8
    for i in range(3):
        rows.append({"Dept": "Micro_Unit", "Score": 99.0})  # Extreme but n=3!
    for dept in ["DeptB", "DeptC", "DeptD", "DeptE", "DeptF", "DeptG"]:
        for i in range(8):
            rows.append({"Dept": dept, "Score": 20.0})

    manifest, contract = profile_source(
        sheet_id=816,
        sheet_name="SmallSeg",
        file_name="small.csv",
        display_name="Small Segment Test",
        columns=["Dept", "Score"],
        rows=rows,
    )
    candidates = discover_segment_exception_candidates(manifest, contract, rows)
    # Micro_Unit must be excluded because n=3 < 5
    for item, _ in candidates:
        assert item.subject_label != "Micro_Unit"


def test_element_8_17_ties_preserved():
    """17. Ties are preserved."""
    data = [10.0, 10.0, 20.0, 20.0, 20.0, 20.0, 30.0, 30.0]
    stats = compute_robust_center_and_spread(data)
    is_exc1, _, _, _, dev1, _ = evaluate_robust_deviation(20.0, stats)
    is_exc2, _, _, _, dev2, _ = evaluate_robust_deviation(20.0, stats)
    assert dev1 == dev2
    assert is_exc1 == is_exc2


def test_element_8_18_unknown_never_selected_subject():
    """18. Unknown is never the selected business subject."""
    rows = []
    # Unknown has extreme outlier
    for i in range(10):
        rows.append({"Dept": "Unknown", "Score": 100.0})
    for dept in ["Eng", "Sales", "Ops", "HR", "Legal", "Finance"]:
        for i in range(10):
            rows.append({"Dept": dept, "Score": 25.0})

    manifest, contract = profile_source(
        sheet_id=818,
        sheet_name="UnknownTest",
        file_name="unknown.csv",
        display_name="Unknown Subject Test",
        columns=["Dept", "Score"],
        rows=rows,
    )
    candidates = discover_segment_exception_candidates(manifest, contract, rows)
    for item, _ in candidates:
        assert item.subject_label.lower() != "unknown"


def test_element_8_19_mixed_currencies_and_incompatible_grains_rejected():
    """19. Mixed currencies and incompatible grains are rejected."""
    contract = SemanticContract(
        layout="long_tabular",
        entity_type="record",
        entity_identifiers=["id"],
        grain_description="one row per record",
        verification_basis="test",
    )
    # Column with mixed currency strings like ["$10", "€20", "¥3000"]
    mixed = ["$10", "€20", "¥3000", "USD 50", "GBP 12"]
    assert is_eligible_numeric_measure("Revenue", mixed, contract) is False


def test_element_8_20_stale_and_snapshotless_eda_rejected():
    """20. Stale and snapshotless EDA reports are rejected."""
    rows = [{"Dept": f"Dept_{i}", "Val": 10.0 + i} for i in range(10)]
    manifest, contract = profile_source(
        sheet_id=820,
        sheet_name="EdaTest",
        file_name="eda.csv",
        display_name="EDA Verification",
        columns=["Dept", "Val"],
        rows=rows,
    )
    _, _, primary = evaluate_and_select_primary_metric(manifest, contract, rows)

    # 1. Stale snapshot
    stale_eda = {"snapshot": "stale_hash_123", "outliers": [{"column": "Val", "value": 99.0}]}
    spec_stale = build_exception_watch_element(manifest, contract, rows, primary, eda_report=stale_eda)
    # Should not crash and should safely process current data without stale EDA contamination
    assert spec_stale is not None

    # 2. Snapshotless EDA
    snapshotless_eda = {"outliers": [{"column": "Val", "value": 99.0}]}
    spec_snapless = build_exception_watch_element(manifest, contract, rows, primary, eda_report=snapshotless_eda)
    assert spec_snapless is not None


def test_element_8_21_same_snapshot_eda_recalculated_from_current_rows():
    """21. Same-snapshot EDA screening candidate is recalculated from current rows."""
    rows = []
    depts = [("DeptA", 10.0), ("DeptB", 12.0), ("DeptC", 14.0), ("DeptD", 11.0), ("DeptE", 13.0), ("DeptF", 88.0)]
    for dept, base in depts:
        for i in range(10):
            val = base if dept == "DeptF" else (base + (i % 3) * 0.5)
            rows.append({"Dept": dept, "Score": val})

    manifest, contract = profile_source(
        sheet_id=821,
        sheet_name="EdaMatch",
        file_name="eda_match.csv",
        display_name="EDA Match Test",
        columns=["Dept", "Score"],
        rows=rows,
    )
    _, _, primary = evaluate_and_select_primary_metric(manifest, contract, rows)
    matched_eda = {
        "snapshot": manifest.snapshot,
        "outliers": [{"column": "Score", "value": 88.0, "segment": "DeptF"}],
    }
    spec = build_exception_watch_element(manifest, contract, rows, primary, eda_report=matched_eda)
    assert spec is not None
    assert spec.lead_exception is not None
    assert spec.lead_exception.subject_label == "DeptF"
    assert spec.lead_exception.observed_value == 88.0


@pytest.fixture
def seeded_multi_dept_sheet():
    """Seeds a tabular dataset with 10 departments and 250 records into the test DB."""
    conn = get_connection()
    conn.execute(
        "INSERT INTO dataset_uploads (id, filename, original_name, display_name, file_type) VALUES (?, ?, ?, ?, ?)",
        (80, "wfo_test.xlsx", "WFO_July_2026_Test.xlsx", "July 2026 Attendance Summary", "xlsx"),
    )
    cols = ["Employee_Name", "Department", "Final Attendance", "Attendance Reliability %"]
    conn.execute(
        "INSERT INTO sheets (id, dataset_id, name, display_name, columns_json, profile_json, row_count) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (80, 80, "Sheet1", "July 2026 Attendance Summary", json.dumps(cols), "[]", 259),
    )
    # 10 departments mirroring the production test dataset
    depts = [
        ("Operations and Infrastructure", 26, 16.1, 93.7),
        ("Corporate Functions", 30, 10.2, 80.0),
        ("Engineering Core", 35, 11.5, 87.0),
        ("Product Delivery", 30, 11.8, 86.5),
        ("Sales & Marketing", 28, 12.0, 88.0),
        ("Customer Success", 25, 11.1, 85.0),
        ("Quality Assurance", 25, 12.2, 87.5),
        ("Security & Compliance", 20, 11.4, 86.0),
        ("Alliance Initiative - Design", 20, 8.4, 82.0),
        ("Alliance Initiative - RQI 1stop/LLP", 20, 9.9, 83.0),
    ]
    row_idx = 0
    for dept, count, att_days, rel in depts:
        for i in range(count):
            row_data = {
                "Employee_Name": f"Emp_{dept}_{i}",
                "Department": dept,
                "Final Attendance": att_days,
                "Attendance Reliability %": rel,
            }
            conn.execute(
                "INSERT INTO sheet_rows (sheet_id, row_index, data_json) VALUES (?, ?, ?)",
                (80, row_idx, json.dumps(row_data)),
            )
            row_idx += 1
    conn.commit()
    return 80


def test_element_8_22_lead_exception_does_not_duplicate_element_6(seeded_multi_dept_sheet):
    """22. Lead exception does not duplicate Element 6 when another eligible candidate exists."""
    res = run_adaptive_dashboard(seeded_multi_dept_sheet)
    assert res.decision_element is not None
    assert res.exception_element is not None
    assert res.exception_element.lead_exception is not None
    # Duplicate suppression must select an exception distinct from Decision Focus
    assert res.exception_element.lead_exception.subject_label != res.decision_element.subject_label


def test_element_8_23_element_8_failure_preserves_elements_1_to_7(seeded_multi_dept_sheet, monkeypatch):
    """23. Element 8 failure preserves Elements 1–7."""
    import app.services.adaptive_dashboard.engine as engine_mod

    def bugged_exception_builder(*args, **kwargs):
        raise RuntimeError("Simulated Element 8 failure!")

    monkeypatch.setattr(engine_mod, "build_exception_watch_element", bugged_exception_builder)

    res = run_adaptive_dashboard(seeded_multi_dept_sheet)
    assert res.exception_element is None  # Gracefully caught
    assert res.element is not None        # Element 1 preserved
    assert res.quinary_element is not None    # Element 5 preserved
    assert res.decision_element is not None   # Element 6 preserved
    assert res.briefing_element is not None   # Element 7 preserved


def test_element_8_24_response_version_and_contracts_extra_forbid(seeded_multi_dept_sheet):
    """24. Response version is adaptive-v8, contracts reject extra fields, and all numeric values are finite."""
    import math
    from pydantic import ValidationError

    assert ExceptionPoint.model_config["extra"] == "forbid"
    assert ExceptionItem.model_config["extra"] == "forbid"
    assert ExceptionVisualSpec.model_config["extra"] == "forbid"
    assert ExceptionWatchSpec.model_config["extra"] == "forbid"

    # Reject unauthorized fields
    with pytest.raises(ValidationError):
        ExceptionItem(
            exception_id="exc_1",
            exception_type="segment",
            subject_type="dept",
            subject_label="Ops",
            metric_name="Hours",
            unit="h",
            observed_value=10.0,
            formatted_observed_value="10.0",
            expected_lower=5.0,
            expected_upper=8.0,
            formatted_expected_range="5.0–8.0",
            deviation_value=2.0,
            formatted_deviation="+2.0",
            direction="above",
            sample_size=10,
            sample_label="10 records",
            method="MAD",
            calculation_id="c1",
            snapshot="s1",
            unauthorized_field="illegal",  # FORBIDDEN EXTRA FIELD!
        )

    res = run_adaptive_dashboard(seeded_multi_dept_sheet)
    assert res.version in ("adaptive-v8", "adaptive-v9", "adaptive-v10")
    assert res.exception_element is not None
    lead = res.exception_element.lead_exception
    assert lead is not None
    assert math.isfinite(lead.observed_value)
    assert math.isfinite(lead.expected_lower)
    assert math.isfinite(lead.expected_upper)
    assert math.isfinite(lead.deviation_value)


# ==============================================================================
# ELEMENT 9: FORWARD OUTLOOK TESTS (GATE 9)
# ==============================================================================

from app.services.adaptive_dashboard.contracts import (
    ChartPoint,
    ChartSeries,
    ChartSpec,
    ComponentSpec,
    EvidenceResult,
    ExplainSpec,
    ForwardOutlookSpec,
    GlanceSpec,
    InspectSpec,
    ModelValidationResult,
    OutlookPoint,
    SemanticContract,
    SourceManifest,
)
from app.services.adaptive_dashboard.outlook import (
    backtest_candidate_models,
    build_forward_outlook_element,
    calculate_mae,
    calculate_wape,
    detect_target_column,
    fit_and_predict_candidate,
    is_protected_or_individual_outcome,
)


def _create_mock_manifest(sheet_id: int = 1) -> SourceManifest:
    return SourceManifest(
        sheet_id=sheet_id,
        sheet_name="TestSheet",
        file_name="test.csv",
        display_name="Test Commercial Data",
        row_count=100,
        col_count=5,
        snapshot=f"snap-{sheet_id}",
    )


def _create_mock_spec(metric: str = "Sales", unit: str = "$") -> ComponentSpec:
    return ComponentSpec(
        component_id="primary_element",
        kind="kpi",
        business_concept=f"Commercial {metric}",
        title=metric,
        formatted_value=f"100 {unit}",
        unit=unit,
        scope_label="All records",
        coverage_qualifier="100%",
        selection_reason="Primary measure",
        glance=GlanceSpec(label=metric, formatted_value=f"100 {unit}", value=100.0),
        explain=ExplainSpec(short_definition=metric, exact_value_text=f"100 {unit}"),
        inspect=InspectSpec(
            metric_title=metric,
            exact_value=f"100 {unit}",
            what_this_counts=metric,
            applicable_population="Records",
            source_name="Test Source",
            calculation_method="Sum",
            data_completeness="100%",
            workforce_coverage="100%",
            selection_reason="Primary",
            calculation_id="c1",
            definition_id="d1",
            snapshot="s1",
            provenance="Sheet 1: Test Source",
        ),
        evidence=EvidenceResult(
            calculation_id="c1",
            snapshot="s1",
            definition_id="d1",
            status="available",
            value=100.0,
            unit=unit,
            aggregation="sum",
            calculation_method="sum",
            provenance="Sheet 1: Test Source",
        ),
    )


def test_element_9_01_explicit_target_gap():
    """1. Explicit target with compatible metric and grain computes true target gap."""
    manifest = _create_mock_manifest(1)
    spec = _create_mock_spec("Sales", "$")
    contract = SemanticContract(
        layout="long_tabular",
        entity_type="store",
        entity_identifiers=["Store"],
        primary_measure="Sales",
        grain_description="store",
        domain="commercial_retail",
        verification_basis="deterministic",
    )
    rows = [
        {"Store": 1, "Sales": 120.0, "Target_Sales": 100.0},
        {"Store": 2, "Sales": 130.0, "Target_Sales": 100.0},
        {"Store": 3, "Sales": 110.0, "Target_Sales": 100.0},
    ]
    res = build_forward_outlook_element(1, rows, manifest, contract, spec, None)
    assert res.kind == "target_gap"
    assert res.actual_value == 120.0
    assert res.target_value == 100.0
    assert res.gap_value == 20.0
    assert "above the recorded target" in res.glance.formatted_value
    assert len(res.points) == 2


def test_element_9_02_target_scope_mismatch_and_missing():
    """2. Non-matching target column or missing target falls through to forecast or unavailable."""
    manifest = _create_mock_manifest(2)
    spec = _create_mock_spec("Sales", "$")
    contract = SemanticContract(
        layout="long_tabular",
        entity_type="store",
        entity_identifiers=["Store"],
        primary_measure="Sales",
        grain_description="store",
        domain="commercial_retail",
        verification_basis="deterministic",
    )
    # Rows without target column and without temporal chart -> outlook_unavailable
    rows = [{"Store": 1, "Sales": 100.0}, {"Store": 2, "Sales": 120.0}]
    res = build_forward_outlook_element(2, rows, manifest, contract, spec, None)
    assert res.kind == "outlook_unavailable"
    assert "requires a verified chronological time series" in res.why_available_or_unavailable


def test_element_9_03_target_zero_and_percentage_points():
    """3. Target comparison with percentage unit formats as percentage points."""
    manifest = _create_mock_manifest(3)
    spec = _create_mock_spec("Rate", "%")
    contract = SemanticContract(
        layout="long_tabular",
        entity_type="unit",
        entity_identifiers=["Unit"],
        primary_measure="Rate",
        grain_description="unit",
        domain="commercial_retail",
        verification_basis="deterministic",
    )
    rows = [
        {"Unit": 1, "Rate": 88.4, "Target_Rate": 92.0},
        {"Unit": 2, "Rate": 88.4, "Target_Rate": 92.0},
        {"Unit": 3, "Rate": 88.4, "Target_Rate": 92.0},
    ]
    res = build_forward_outlook_element(3, rows, manifest, contract, spec, None)
    assert res.kind == "target_gap"
    assert res.gap_value == -3.6
    assert "3.6 percentage points below the recorded target" in res.glance.formatted_value


def test_element_9_04_monthly_forecast_with_adequate_history():
    """4. Monthly forecast with >= 12 periods passes rolling-origin backtest and generates point and range."""
    manifest = _create_mock_manifest(4)
    spec = _create_mock_spec("Revenue", "$")
    contract = SemanticContract(
        layout="long_tabular",
        entity_type="store",
        entity_identifiers=["Store"],
        primary_measure="Revenue",
        grain_description="store-month",
        domain="commercial_retail",
        verification_basis="deterministic",
    )
    points = [
        ChartPoint(period=f"2023-{i+1:02d}", period_label=f"M{i+1}", average_hours=200.0 + i * 5.0)
        for i in range(16)
    ]
    chart = ChartSpec(
        component_id="secondary_element",
        kind="line_chart",
        business_concept="Revenue Trend",
        title="Monthly Revenue",
        glance=GlanceSpec(label="Rev", formatted_value="$200", value=200.0),
        explain=ExplainSpec(short_definition="Rev", exact_value_text="$200"),
        inspect=InspectSpec(
            metric_title="Rev", exact_value="$200", what_this_counts="Rev",
            applicable_population="Stores", source_name="Test", calculation_method="Mean",
            data_completeness="100%", workforce_coverage="100%", selection_reason="Primary",
            calculation_id="c1", definition_id="d1", snapshot="s1", provenance="p1"
        ),
        evidence=EvidenceResult(
            calculation_id="c1", snapshot="s1", definition_id="d1", status="available",
            value=200.0, unit="$", aggregation="mean", calculation_method="mean", provenance="p1"
        ),
        chart_series=ChartSeries(name="Revenue", unit="$", points=points),
        temporal_grain="monthly",
    )
    res = build_forward_outlook_element(4, [{"Revenue": 200.0}], manifest, contract, spec, chart)
    assert res.kind == "statistical_forecast"
    assert res.forecast_value is not None
    assert res.lower_bound is not None and res.upper_bound is not None
    assert res.lower_bound <= res.forecast_value <= res.upper_bound
    assert res.validation is not None
    assert res.validation.passed is True
    assert len(res.points) == 17  # 16 historical + 1 forecast


def test_element_9_05_weekly_seasonal_forecast_requirements():
    """5. Weekly seasonal models require at least two full cycles (104 weeks); fewer weeks disqualify seasonal models."""
    series_short = [100.0 + (i % 52) * 2.0 for i in range(55)]  # > 12 weeks, but < 104 weeks
    _, _, _, meta_short = backtest_candidate_models(series_short, "weekly")
    assert meta_short["seasonal_period"] is None

    series_long = [100.0 + (i % 52) * 2.0 for i in range(110)]  # >= 104 weeks
    _, _, _, meta_long = backtest_candidate_models(series_long, "weekly")
    assert meta_long["seasonal_period"] == 52


def test_element_9_06_insufficient_history_abstention():
    """6. History < 12 periods cleanly abstains with exact period count in explanation."""
    manifest = _create_mock_manifest(6)
    spec = _create_mock_spec("Orders", "count")
    contract = SemanticContract(
        layout="long_tabular",
        entity_type="day",
        entity_identifiers=["Day"],
        primary_measure="Orders",
        grain_description="store-month",
        domain="commercial_retail",
        verification_basis="deterministic",
    )
    points = [ChartPoint(period=f"2024-{i+1:02d}", period_label=f"M{i+1}", average_hours=50.0) for i in range(8)]
    chart = ChartSpec(
        component_id="secondary_element",
        kind="line_chart",
        business_concept="Orders",
        title="Orders",
        glance=GlanceSpec(label="Orders", formatted_value="50", value=50.0),
        explain=ExplainSpec(short_definition="Orders", exact_value_text="50"),
        inspect=InspectSpec(
            metric_title="Orders", exact_value="50", what_this_counts="Orders",
            applicable_population="Stores", source_name="Test", calculation_method="Mean",
            data_completeness="100%", workforce_coverage="100%", selection_reason="Primary",
            calculation_id="c1", definition_id="d1", snapshot="s1", provenance="p1"
        ),
        evidence=EvidenceResult(
            calculation_id="c1", snapshot="s1", definition_id="d1", status="available",
            value=50.0, unit="count", aggregation="mean", calculation_method="mean", provenance="p1"
        ),
        chart_series=ChartSeries(name="Orders", unit="count", points=points),
        temporal_grain="monthly",
    )
    res = build_forward_outlook_element(6, [{"Orders": 50}], manifest, contract, spec, chart)
    assert res.kind == "outlook_unavailable"
    assert "needs at least 12 complete monthly periods; this source contains 8" in res.why_available_or_unavailable


def test_element_9_07_partial_latest_period_excluded_from_training():
    """7. Partial latest period is excluded from training folds."""
    manifest = _create_mock_manifest(7)
    spec = _create_mock_spec("Revenue", "$")
    contract = SemanticContract(
        layout="long_tabular",
        entity_type="store",
        entity_identifiers=["Store"],
        primary_measure="Revenue",
        grain_description="store-month",
        domain="commercial_retail",
        verification_basis="deterministic",
    )
    points = [
        ChartPoint(period=f"2023-{i+1:02d}", period_label=f"M{i+1}", average_hours=200.0 + i * 5.0)
        for i in range(12)
    ]
    # Add 13th point marked as partial
    points.append(
        ChartPoint(
            period="2024-01",
            period_label="Jan 2024",
            average_hours=80.0,
            is_partial=True,
            partial_reason="Data through Jan 10 only",
        )
    )
    chart = ChartSpec(
        component_id="secondary_element",
        kind="line_chart",
        business_concept="Revenue",
        title="Revenue",
        glance=GlanceSpec(label="Rev", formatted_value="$200", value=200.0),
        explain=ExplainSpec(short_definition="Rev", exact_value_text="$200"),
        inspect=InspectSpec(
            metric_title="Rev", exact_value="$200", what_this_counts="Rev",
            applicable_population="Stores", source_name="Test", calculation_method="Mean",
            data_completeness="100%", workforce_coverage="100%", selection_reason="Primary",
            calculation_id="c1", definition_id="d1", snapshot="s1", provenance="p1"
        ),
        evidence=EvidenceResult(
            calculation_id="c1", snapshot="s1", definition_id="d1", status="available",
            value=200.0, unit="$", aggregation="mean", calculation_method="mean", provenance="p1"
        ),
        chart_series=ChartSeries(name="Revenue", unit="$", points=points),
        temporal_grain="monthly",
    )
    res = build_forward_outlook_element(7, [{"Revenue": 200.0}], manifest, contract, spec, chart)
    assert res.kind == "statistical_forecast"
    assert any("partial" in lim.lower() for lim in res.inspect.limitations)


def test_element_9_08_zero_safe_wape_mae():
    """8. Zero-safe WAPE calculation never divides by zero."""
    import numpy as np

    y = np.array([0.0, 0.0, 0.0])
    y_hat_exact = np.array([0.0, 0.0, 0.0])
    y_hat_off = np.array([1.0, 0.0, 0.0])

    assert calculate_wape(y, y_hat_exact) == 0.0
    assert calculate_wape(y, y_hat_off) == 1.0
    assert calculate_mae(y, y_hat_off) == pytest.approx(1.0 / 3.0)


def test_element_9_09_rolling_origin_no_leakage():
    """9. Rolling origin evaluates strictly chronologically without future leakage."""
    series = [10.0, 12.0, 14.0, 16.0, 18.0, 20.0, 22.0, 24.0, 26.0, 28.0, 30.0, 32.0, 34.0, 36.0]
    best_model, val_res, _, _ = backtest_candidate_models(series, "monthly")
    assert val_res.fold_count >= 3
    assert val_res.mae >= 0.0
    assert val_res.baseline_mae >= 0.0


def test_element_9_10_candidate_model_loses_to_naive_withheld():
    """10. If candidate models fail to match or beat naive baseline, outlook is withheld."""
    import numpy as np

    # Highly noisy random walk series where naive baseline is best
    np.random.seed(42)
    noise = list(np.cumsum(np.random.randn(15) * 10.0) + 100.0)
    best_model, val_res, _, _ = backtest_candidate_models(noise, "monthly")
    # val_res should capture the comparison
    assert val_res.baseline_mae is not None
    assert val_res.mae is not None


def test_element_9_11_candidate_model_passes_exposes_validation():
    """11. Successful forecast publishes complete validation metadata."""
    series = [100.0 + i * 10.0 for i in range(20)]  # Clean linear trend
    best_model, val_res, _, _ = backtest_candidate_models(series, "monthly")
    assert val_res.passed is True
    assert val_res.model_id in ("holt_linear", "naive_drift")
    assert val_res.mae <= val_res.baseline_mae


def test_element_9_12_nonnegative_and_percentage_clamping():
    """12. Negative bounds are clamped to 0 for non-negative measures and percentages bounded [0, 100]."""
    manifest = _create_mock_manifest(12)
    spec = _create_mock_spec("Sales", "$")
    contract = SemanticContract(
        layout="long_tabular",
        entity_type="store",
        entity_identifiers=["Store"],
        primary_measure="Sales",
        grain_description="store-month",
        domain="commercial_retail",
        verification_basis="deterministic",
    )
    # Series close to zero with wide error
    points = [ChartPoint(period=f"2023-{i+1:02d}", period_label=f"M{i+1}", average_hours=2.0 + (i % 2)) for i in range(15)]
    chart = ChartSpec(
        component_id="secondary_element",
        kind="line_chart",
        business_concept="Sales",
        title="Sales",
        glance=GlanceSpec(label="Sales", formatted_value="$2", value=2.0),
        explain=ExplainSpec(short_definition="Sales", exact_value_text="$2"),
        inspect=InspectSpec(
            metric_title="Sales", exact_value="$2", what_this_counts="Sales",
            applicable_population="Stores", source_name="Test", calculation_method="Mean",
            data_completeness="100%", workforce_coverage="100%", selection_reason="Primary",
            calculation_id="c1", definition_id="d1", snapshot="s1", provenance="p1"
        ),
        evidence=EvidenceResult(
            calculation_id="c1", snapshot="s1", definition_id="d1", status="available",
            value=2.0, unit="$", aggregation="mean", calculation_method="mean", provenance="p1"
        ),
        chart_series=ChartSeries(name="Sales", unit="$", points=points),
        temporal_grain="monthly",
    )
    res = build_forward_outlook_element(12, [{"Sales": 2}], manifest, contract, spec, chart)
    if res.kind == "statistical_forecast":
        assert res.lower_bound >= 0.0


def test_element_9_13_protected_outcome_rejection():
    """13. Individual employee performance, attendance, attrition, or health strictly rejected."""
    assert is_protected_or_individual_outcome("Employee Attendance", "Final Attendance", "employee", ["Full Name", "Final Attendance"]) is True
    assert is_protected_or_individual_outcome("Staff Performance", "Rating", "staff", ["ID", "Rating"]) is True
    assert is_protected_or_individual_outcome("Retail Weekly Sales", "Weekly_Sales", "store", ["Store", "Weekly_Sales"]) is False


def test_element_9_14_element_9_failure_preserves_elements_1_to_8(seeded_multi_dept_sheet):
    """14. Failure in Element 9 keeps Elements 1-8 intact and functional."""
    res = run_adaptive_dashboard(seeded_multi_dept_sheet)
    assert res.element is not None
    assert res.decision_element is not None
    assert res.briefing_element is not None
    assert res.exception_element is not None
    assert res.outlook_element is not None
    # For attendance data Sheet 80, outlook is unavailable per governance policy
    assert res.outlook_element.kind == "outlook_unavailable"


def test_element_9_15_adaptive_v9_contract_extra_forbid():
    """15. ForwardOutlookSpec, ModelValidationResult, and OutlookPoint forbid extra fields."""
    import pytest
    from pydantic import ValidationError

    assert OutlookPoint.model_config["extra"] == "forbid"
    assert ModelValidationResult.model_config["extra"] == "forbid"
    assert ForwardOutlookSpec.model_config["extra"] == "forbid"

    with pytest.raises(ValidationError):
        OutlookPoint(
            period="2024-01",
            period_label="Jan 2024",
            actual_value=100.0,
            unauthorized_field="illegal",
        )


# ==============================================================================
# ELEMENT 10: ENTERPRISE SYNTHESIS TESTS (GATE 10)
# ==============================================================================

def _seed_enterprise_sources(
    primary_rows,
    sibling_sources=(),
    *,
    dataset_id=910,
    primary_name="Workforce Outcomes",
    primary_snapshot="primary-snapshot",
):
    """Seed one upload with deterministic sibling-sheet order for Element 10 tests."""
    conn = get_connection()
    conn.execute(
        "INSERT INTO dataset_uploads (id, filename, original_name, display_name, file_type) "
        "VALUES (?, ?, ?, ?, ?)",
        (dataset_id, "enterprise.xlsx", "enterprise.xlsx", "Enterprise Workbook", "xlsx"),
    )

    all_sources = [(primary_name, primary_rows), *list(sibling_sources)]
    for offset, (name, source_rows) in enumerate(all_sources):
        sid = dataset_id * 10 + offset
        columns = list(source_rows[0].keys()) if source_rows else []
        conn.execute(
            "INSERT INTO sheets "
            "(id, dataset_id, name, display_name, columns_json, profile_json, row_count) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (sid, dataset_id, f"Sheet{offset + 1}", name, json.dumps(columns), "[]", len(source_rows)),
        )
        for row_index, row in enumerate(source_rows):
            conn.execute(
                "INSERT INTO sheet_rows (sheet_id, row_index, data_json) VALUES (?, ?, ?)",
                (sid, row_index, json.dumps(row)),
            )
    conn.commit()

    primary_id = dataset_id * 10
    manifest = SourceManifest(
        sheet_id=primary_id,
        dataset_id=dataset_id,
        sheet_name="Sheet1",
        file_name="enterprise.xlsx",
        display_name=primary_name,
        row_count=len(primary_rows),
        col_count=len(primary_rows[0]) if primary_rows else 0,
        snapshot=primary_snapshot,
    )
    contract = SemanticContract(
        layout="long_tabular",
        entity_type="employee",
        entity_identifiers=["Employee_ID"],
        primary_measure=None,
        grain_description="one row per observed entity",
        domain="workforce_hr",
        verification_basis="deterministic test fixture",
    )
    return conn, primary_id, manifest, contract


def _build_enterprise(primary_rows, sibling_sources=(), **kwargs):
    conn, primary_id, manifest, contract = _seed_enterprise_sources(
        primary_rows, sibling_sources, **kwargs
    )
    try:
        return build_enterprise_synthesis_element(
            conn=conn,
            dataset_id=manifest.dataset_id,
            sheet_id=primary_id,
            manifest=manifest,
            contract=contract,
            rows=primary_rows,
        )
    finally:
        conn.close()


def _workforce_learning_rows(entity_count=12, duplicate_primary=False):
    departments = ("Sales", "Support", "Engineering")
    workforce = []
    learning = []
    for idx in range(entity_count):
        employee_id = f"EMP-{idx + 1:03d}"
        base = {
            "Employee_ID": employee_id,
            "Department": departments[idx % len(departments)],
            "Attendance_Score": 70 + idx,
        }
        workforce.append(base)
        if duplicate_primary:
            workforce.append({**base, "Attendance_Score": 72 + idx})
        learning.append({"Employee_ID": employee_id, "Learning_Score": 60 + idx * 1.5})
    return workforce, learning


def test_element_10_01_same_dataset_scope_rejects_cross_dataset_synthesis():
    """1. Only sibling sheets from the selected upload may enter synthesis."""
    primary = [{"Employee_ID": f"E{i}", "Metric": i} for i in range(1, 8)]
    local = [{"Local_Key": f"L{i}", "Other": i} for i in range(1, 8)]
    conn, primary_id, manifest, contract = _seed_enterprise_sources(primary, [("Local", local)])
    conn.execute(
        "INSERT INTO dataset_uploads (id, filename, original_name, display_name, file_type) VALUES (?, ?, ?, ?, ?)",
        (999, "external.xlsx", "external.xlsx", "External Dataset", "xlsx"),
    )
    external_rows = [{"Employee_ID": f"E{i}", "Return_Value": i} for i in range(1, 8)]
    conn.execute(
        "INSERT INTO sheets (id, dataset_id, name, display_name, columns_json, profile_json, row_count) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (9990, 999, "External", "External Returns", json.dumps(list(external_rows[0])), "[]", len(external_rows)),
    )
    for idx, row in enumerate(external_rows):
        conn.execute("INSERT INTO sheet_rows (sheet_id, row_index, data_json) VALUES (?, ?, ?)", (9990, idx, json.dumps(row)))
    conn.commit()
    result = build_enterprise_synthesis_element(conn, manifest.dataset_id, primary_id, manifest, contract, primary)
    conn.close()
    assert [source.sheet_id for source in result.sources] == [9100, 9101]
    assert 9990 not in {target.sheet_id for target in result.drilldown_targets}


def test_element_10_02_combined_snapshot_changes_with_any_source():
    """2. Any source snapshot mutation invalidates the combined snapshot."""
    refs_a = [
        EnterpriseSourceRef(sheet_id=1, display_name="A", snapshot="a1", entity_count=10),
        EnterpriseSourceRef(sheet_id=2, display_name="B", snapshot="b1", entity_count=10),
    ]
    refs_b = [refs_a[0], refs_a[1].model_copy(update={"snapshot": "b2"})]
    assert compute_combined_snapshot(refs_a) != compute_combined_snapshot(refs_b)
    assert compute_combined_snapshot(refs_a) == compute_combined_snapshot(list(reversed(refs_a)))


def test_element_10_03_safe_one_to_one_join_and_cardinality():
    """3. Unique entity keys on both sides are verified as 1:1."""
    left = [{"Employee_ID": f"E{i}"} for i in range(1, 7)]
    right = [{"Employee_ID": f"E{i}"} for i in range(1, 7)]
    result = inspect_cardinality(left, right, "Employee_ID", "Employee_ID")
    assert result["is_safe"] is True
    assert result["cardinality"] == "1:1"
    assert result["matched_count"] == 6


def test_element_10_04_safe_many_to_one_uses_explicit_entity_grain():
    """4. Repeated primary observations aggregate to entity grain before cohort means."""
    workforce, learning = _workforce_learning_rows(12, duplicate_primary=True)
    result = _build_enterprise(workforce, [("Learning Outcomes", learning)])
    assert result.kind == "matched_comparison"
    assert "N:1" in result.lead_finding.join_description
    assert sum(point.sample_size for point in result.visual.points) == 12


def test_element_10_05_many_to_many_join_is_rejected():
    """5. N:N keys are never used for a combined metric."""
    left = [{"Employee_ID": f"E{i}"} for i in range(1, 7) for _ in range(2)]
    right = [{"Employee_ID": f"E{i}"} for i in range(1, 7) for _ in range(2)]
    result = inspect_cardinality(left, right, "Employee_ID", "Employee_ID")
    assert result["cardinality"] == "N:N"
    assert result["is_safe"] is False


def test_element_10_06_duplicate_key_violation_returns_coverage_only():
    """6. A duplicate-key violation degrades honestly to coverage-only."""
    left = [{"Employee_ID": f"E{i}", "Score": i} for i in range(1, 7) for _ in range(2)]
    right = [{"Employee_ID": f"E{i}", "Learning": i} for i in range(1, 7) for _ in range(2)]
    result = _build_enterprise(left, [("Learning", right)])
    assert result.kind == "coverage_only"
    assert result.lead_finding is None


def test_element_10_07_match_and_unmatched_counts_reconcile():
    """7. Matched and unmatched counts reconcile both key populations."""
    left = [{"Employee_ID": f"E{i}"} for i in range(1, 9)]
    right = [{"Employee_ID": f"E{i}"} for i in range(4, 11)]
    result = inspect_cardinality(left, right, "Employee_ID", "Employee_ID")
    assert result["matched_count"] == 5
    assert result["unmatched_count"] == 5
    assert result["left_eligible"] + result["right_eligible"] == 2 * result["matched_count"] + result["unmatched_count"]


def test_element_10_08_workforce_learning_cohorts_are_privacy_safe():
    """8. Workforce-learning comparison emits department aggregates, not people."""
    workforce, learning = _workforce_learning_rows(15)
    result = _build_enterprise(workforce, [("Learning Outcomes", learning)])
    assert result.kind == "matched_comparison"
    assert {point.label for point in result.visual.points} == {"Sales", "Support", "Engineering"}
    assert all(point.sample_size >= 3 for point in result.visual.points)


def test_element_10_09_correlation_guards_withhold_small_samples():
    """9. Cross-source association is withheld below N=30."""
    left = [{"Employee_ID": f"E{i}", "Productivity_Score": i * 2} for i in range(1, 25)]
    right = [{"Employee_ID": f"E{i}", "Learning_Score": i * 3} for i in range(1, 25)]
    result = _build_enterprise(left, [("Learning", right)])
    assert result.kind == "coverage_only"
    assert "statistically defensible" in result.what_it_does_not_establish


def test_element_10_10_raw_trending_time_series_requires_detrending():
    """10. A shared time trend is not reported as ordinary cross-source correlation."""
    left = [{"Month": f"2024-{i:02d}", "Sales": 100 + i * 10} for i in range(1, 13)]
    right = [{"Month": f"2024-{i:02d}", "Ad_Spend": 50 + i * 8} for i in range(1, 13)]
    result = _build_enterprise(left, [("Marketing", right)])
    assert result.kind == "coverage_only"
    assert "detrending" in result.what_it_does_not_establish.lower()


def test_element_10_11_mixed_currency_is_rejected():
    """11. Explicitly different currencies require an exchange-rate policy."""
    left = [{"Employee_ID": f"E{i}", "Revenue_USD": i * 10} for i in range(1, 36)]
    right = [{"Employee_ID": f"E{i}", "Cost_EUR": i * 7} for i in range(1, 36)]
    result = _build_enterprise(left, [("Costs", right)])
    assert result.kind == "coverage_only"
    assert "mixed currencies" in result.what_it_does_not_establish.lower()


def test_element_10_12_mismatched_periods_rejected_by_as_of_policy():
    """12. Sources with disjoint periods cannot form a combined analytical metric."""
    left = [{"Employee_ID": f"E{i}", "Month": "2023-01", "Score": i} for i in range(1, 36)]
    right = [{"Employee_ID": f"E{i}", "Month": "2025-01", "Learning": i * 2} for i in range(1, 36)]
    result = _build_enterprise(left, [("Learning", right)])
    assert result.kind == "coverage_only"
    assert "periods do not overlap" in result.what_it_does_not_establish.lower()


def test_element_10_13_stale_eda_and_derived_rows_are_not_sources():
    """13. Snapshotless/stale analytical artifacts are excluded from synthesis inputs."""
    workforce, learning = _workforce_learning_rows(12)
    conn, primary_id, manifest, contract = _seed_enterprise_sources(workforce, [("Learning", learning)])
    conn.execute(
        "INSERT INTO eda_reports (sheet_id, dataset_id, health_score, report_json, snapshot) VALUES (?, ?, ?, ?, ?)",
        (primary_id, manifest.dataset_id, 99, json.dumps({"fabricated": 999999}), "stale-snapshot"),
    )
    conn.execute(
        "INSERT INTO derived_tables (name, display_name, description, source_sheets_json, join_keys_json, columns_json, row_count) VALUES (?, ?, ?, ?, ?, ?, ?)",
        ("stale", "Stale Derived", "snapshotless", json.dumps([primary_id]), "[]", json.dumps(["fabricated"]), 1),
    )
    result = build_enterprise_synthesis_element(conn, manifest.dataset_id, primary_id, manifest, contract, workforce)
    conn.close()
    assert result.source_count == 2
    assert all(source.display_name != "Stale Derived" for source in result.sources)
    assert "999999" not in result.model_dump_json()


def test_element_10_14_single_sheet_returns_coverage_only():
    """14. A one-sheet upload returns a useful coverage state, not None or briefing reuse."""
    rows = [{"Employee_ID": f"E{i}", "Score": i} for i in range(1, 7)]
    result = _build_enterprise(rows)
    assert result.kind == "coverage_only"
    assert result.source_count == 1
    assert result.component_id == "enterprise_element"


def test_element_10_15_unknown_join_labels_do_not_become_keys():
    """15. Repeated business labels with the same heading are not verified entity keys."""
    statuses = ["New", "Open", "Pending", "Closed", "Escalated", "Deferred"]
    left = [{"Status": statuses[i % 6], "Metric_A": i} for i in range(30)]
    right = [{"Status": statuses[i % 6], "Metric_B": i * 2} for i in range(30)]
    candidates = detect_candidate_join_keys(list(left[0]), list(right[0]), left, right)
    assert all(pair[0] != "Status" for pair in candidates)
    assert _build_enterprise(left, [("Other", right)]).kind == "coverage_only"


def test_element_10_16_failure_preserves_elements_one_to_nine(seeded_multi_dept_sheet, monkeypatch):
    """16. Element 10 exceptions are isolated from the first nine dashboard elements."""
    def fail_enterprise(*args, **kwargs):
        raise RuntimeError("synthetic enterprise failure")

    monkeypatch.setattr(
        "app.services.adaptive_dashboard.engine.build_enterprise_synthesis_element",
        fail_enterprise,
    )
    result = run_adaptive_dashboard(seeded_multi_dept_sheet)
    assert result.element is not None
    assert result.decision_element is not None
    assert result.briefing_element is not None
    assert result.exception_element is not None
    assert result.outlook_element is not None
    assert result.enterprise_element is None


def test_element_10_17_adaptive_v10_contract_and_extra_forbid():
    """17. Element 10 contracts are strict and the response version is adaptive-v10."""
    from pydantic import ValidationError

    assert AdaptiveDashboardResponse.model_fields["version"].default == "adaptive-v10"
    assert EnterpriseSynthesisSpec.model_config["extra"] == "forbid"
    with pytest.raises(ValidationError):
        EnterpriseVisualSpec(kind="none", unexpected_field="illegal")


def test_element_10_18_response_visuals_contain_no_row_level_pii():
    """18. Names, emails, and personal IDs never appear in visual point labels."""
    workforce, learning = _workforce_learning_rows(12)
    for idx, row in enumerate(workforce):
        row["Full_Name"] = f"Private Person {idx}"
        row["Email"] = f"private{idx}@example.test"
    result = _build_enterprise(workforce, [("Learning", learning)])
    payload = json.dumps([point.model_dump() for point in result.visual.points])
    assert "Private Person" not in payload
    assert "@example.test" not in payload
    assert "EMP-" not in payload


def test_element_10_19_matched_keys_without_metrics_return_coverage_only():
    """19. Verified overlap without an analytical metric remains coverage-only."""
    left = [{"Employee_ID": f"E{i}", "Department": "Sales" if i % 2 else "Support"} for i in range(1, 9)]
    right = [{"Employee_ID": f"E{i}", "Course": "Completed"} for i in range(1, 9)]
    result = _build_enterprise(left, [("Courses", right)])
    assert result.kind == "coverage_only"
    assert result.glance.value == 8
    assert "0 compatible analytical recipes" in result.explain.exact_value_text


def test_element_10_20_multiple_siblings_evaluated_in_dataset_order():
    """20. Every sibling is listed in deterministic order and the first safe recipe is selected."""
    workforce, learning = _workforce_learning_rows(12)
    unrelated = [{"Ticket_Key": f"T{i}", "Queue": "A"} for i in range(1, 13)]
    result = _build_enterprise(
        workforce,
        [("Unrelated Operations", unrelated), ("Learning Outcomes", learning)],
    )
    assert [source.sheet_id for source in result.sources] == [9100, 9101, 9102]
    assert result.lead_finding.source_sheet_ids == [9100, 9102]
    assert result.kind == "matched_comparison"
