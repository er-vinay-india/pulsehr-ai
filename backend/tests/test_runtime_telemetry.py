"""Unit tests for Highview OpenTelemetry-compatible Runtime Telemetry and Governance."""
from __future__ import annotations

import json
import pytest

from app.db.database import get_connection
from app.services.adaptive_dashboard.engine import run_adaptive_dashboard
from app.services.adaptive_dashboard.telemetry import (
    ATTR_BUDGET_LATENCY_MAX,
    ATTR_BUDGET_STATUS,
    ATTR_CALLER_ROLE,
    ATTR_TRACE_ID,
    HighviewSpan,
    HighviewTrace,
    RuntimeBudget,
    SpanEvent,
    TraceCollector,
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


def test_trace_collector_span_hierarchy_and_attributes():
    """Verify TraceCollector builds nested spans with GenAI attributes."""
    collector = TraceCollector(
        request_id="req_test_01",
        sheet_id=42,
        caller_role="council_critic",
        latency_budget_ms=1500.0,
    )

    with collector.span("semantic.resolve", {"entity_type": "employee"}) as s1:
        s1.attributes["source_columns"] = 12
        collector.record_event("schema_validated", {"columns_checked": 12})

    with collector.span("evidence.build", {"snapshot": "snap_abc"}) as s2:
        with collector.span("mcp.tool_dispatch", {"mcp.tool.name": "query_metric"}):
            collector.record_event("evidence_node_created", {"evidence_id": "EVID-001"})

    trace = collector.finalize()

    assert trace.trace_id.startswith("tr_")
    assert trace.caller_role == "council_critic"
    assert trace.root_span.name == "HIGHVIEW_REQUEST"
    assert len(trace.root_span.children) == 2

    # Check child 1 (semantic.resolve)
    c1 = trace.root_span.children[0]
    assert c1.name == "semantic.resolve"
    assert c1.attributes["entity_type"] == "employee"
    assert len(c1.events) == 1
    assert c1.events[0].name == "schema_validated"

    # Check child 2 nested hierarchy
    c2 = trace.root_span.children[1]
    assert c2.name == "evidence.build"
    assert len(c2.children) == 1
    assert c2.children[0].name == "mcp.tool_dispatch"
    assert c2.children[0].attributes["mcp.tool.name"] == "query_metric"


def test_runtime_budget_enforcement_and_event():
    """Verify runtime budget detects exceeded limits and emits event."""
    # Budget set to 50ms (simulating tight threshold)
    collector = TraceCollector(
        latency_budget_ms=50.0,
    )
    collector.budget.record_tool_call()
    collector.budget.record_tool_call()

    # Simulate delay exceeding 50ms
    import time
    time.sleep(0.06)

    trace = collector.finalize()
    assert trace.root_span.attributes[ATTR_BUDGET_STATUS] == "EXCEEDED"

    # Check that budget_exceeded event was attached
    events = trace.root_span.events
    assert any(e.name == "budget_exceeded" for e in events)


def test_dual_view_governance_export():
    """Verify clean separation between executive integrity badge and developer trace."""
    collector = TraceCollector(
        sheet_id=10,
        caller_role="executive_dashboard",
    )

    with collector.span("claim.validate"):
        collector.record_event("unsupported_claim_blocked", {"claim_id": "CLM-999"})

    trace = collector.finalize()

    # 1. Executive View (Boardroom-ready, no technical trace trees)
    exec_view = collector.export_executive_integrity(
        unsupported_claims=0,
        coverage_pct=100.0,
        numeric_valid=True,
    )
    assert exec_view["grounding"] == "Passed"
    assert exec_view["evidence_coverage"] == "100%"
    assert exec_view["numeric_validation"] == "Passed"
    assert exec_view["unsupported_claims"] == 0
    assert exec_view["budget_status"] == "WITHIN_BUDGET"

    # 2. Developer View (Full OpenTelemetry hierarchical tree)
    dev_view = collector.export_developer_trace(trace)
    assert "root_span" in dev_view
    assert "children" in dev_view["root_span"]
    assert dev_view["trace_id"].startswith("tr_")


def test_live_engine_governance_telemetry_integration(seeded_attendance_sheet):
    """Verify run_adaptive_dashboard attaches executive integrity and governance telemetry."""
    res = run_adaptive_dashboard(sheet_id=seeded_attendance_sheet)
    assert res.run_status == "ready"

    # Executive Integrity
    assert res.executive_integrity is not None
    assert res.executive_integrity["grounding"] == "Passed"
    assert res.executive_integrity["unsupported_claims"] == 0
    assert res.executive_integrity["evidence_coverage"] == "100%"

    # Developer Telemetry
    assert res.governance_telemetry is not None
    assert "root_span" in res.governance_telemetry
    children = res.governance_telemetry["root_span"]["children"]
    span_names = [c["name"] for c in children]
    assert "semantic.resolve" in span_names
    assert "evidence.build" in span_names
    assert "insight.rank" in span_names
    assert "story_plan.generate" in span_names
