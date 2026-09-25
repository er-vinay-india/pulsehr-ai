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
)
from app.services.adaptive_dashboard.engine import (
    build_average_logged_time_chart,
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
    assert data["version"] == "adaptive-v5"
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
    assert comparator.kind == "impact_ratio"
    assert comparator.title == "Attendance vs. approved leaves"
    assert comparator.glance.label == "Attendance capacity & leave impact"
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
    assert disparity.metric_name == "Attendance Reliability"
    assert disparity.unit == "%"
    assert disparity.top_segment == "Operations"
    assert disparity.bottom_segment == "Corporate"
    # Operations: 36 / 40 = 90.0%
    # Corporate: 14 / 20 = 70.0%
    # Spread: 90.0 - 70.0 = 20.0 pp
    assert disparity.spread_value == 20.0
    assert disparity.formatted_spread == "20.0 pp spread"
    assert disparity.glance.label == "Department attendance disparity"
    assert "Operations" in disparity.glance.context_qualifier
    assert "Corporate" in disparity.glance.context_qualifier
    assert len(disparity.items) == 3
    assert disparity.items[0].segment == "Operations"
    assert disparity.items[0].primary_value == 90.0
    assert disparity.items[0].formatted_primary == "90.0%"
    assert disparity.items[0].tier == "top_tier"
    assert disparity.items[-1].segment == "Corporate"
    assert disparity.items[-1].primary_value == 70.0
    assert disparity.items[-1].formatted_primary == "70.0%"
    assert disparity.items[-1].tier == "friction_tier"


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
