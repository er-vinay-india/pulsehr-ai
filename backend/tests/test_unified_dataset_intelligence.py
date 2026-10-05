"""Unit tests for Phase 8: Unified Dataset Intelligence, Cross-Sheet Orchestration & Global Ranking."""
from __future__ import annotations

import json
import pytest

from app.db.database import get_connection
from app.services.adaptive_dashboard.dataset_orchestrator import (
    DatasetIntelligenceResponse,
    DatasetRelationship,
    DatasetRelationshipEngine,
    DatasetRelationshipGraph,
    SheetContext,
    run_dataset_intelligence,
)
from app.services.adaptive_dashboard.evidence_graph import EvidenceGraph, EvidenceItem
from app.services.adaptive_dashboard.global_ranker import (
    DashboardSlotBudget,
    GlobalCandidatePoolEngine,
    GlobalInsightScorer,
    InsightCandidate,
    InsightRedundancyResolver,
)
from app.services.adaptive_dashboard.mcp_gateway import AgentRole, GovernedMCPGateway


@pytest.fixture
def multi_sheet_dataset():
    """Seeds a multi-sheet dataset (Employees, Attendance, Leave) into isolated SQLite."""
    conn = get_connection()
    # 1. Dataset Upload
    conn.execute(
        "INSERT INTO dataset_uploads (id, filename, original_name, display_name, file_type, sheet_count) VALUES (?, ?, ?, ?, ?, ?)",
        (99, "workforce_multisheet.xlsx", "Workforce Enterprise 2026.xlsx", "Enterprise Workforce", "xlsx", 3),
    )
    # 2. Sheets
    emp_cols = ["employee_id", "department", "tenure_years"]
    att_cols = ["employee_id", "date", "attendance_hours"]
    leave_cols = ["employee_id", "leave_type", "leave_days"]

    conn.execute(
        "INSERT INTO sheets (id, dataset_id, name, display_name, columns_json, profile_json, row_count) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (101, 99, "Employees", "Employee Directory", json.dumps(emp_cols), "[]", 50),
    )
    conn.execute(
        "INSERT INTO sheets (id, dataset_id, name, display_name, columns_json, profile_json, row_count) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (102, 99, "Attendance", "July Attendance Logs", json.dumps(att_cols), "[]", 500),
    )
    conn.execute(
        "INSERT INTO sheets (id, dataset_id, name, display_name, columns_json, profile_json, row_count) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (103, 99, "Leave", "Leave Records", json.dumps(leave_cols), "[]", 120),
    )

    # 3. Seed Relationships
    conn.execute(
        """
        INSERT INTO sheet_relationships (left_sheet, right_sheet, left_column, right_column, method, status, cardinality, matching_keys, matching_pairs, similarity, reason)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (101, 102, "employee_id", "employee_id", "exact_key", "verified", "one-to-many", 50, 500, 1.0, "Employee ID primary join"),
    )
    conn.execute(
        """
        INSERT INTO sheet_relationships (left_sheet, right_sheet, left_column, right_column, method, status, cardinality, matching_keys, matching_pairs, similarity, reason)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (101, 103, "employee_id", "employee_id", "exact_key", "verified", "one-to-many", 45, 120, 0.95, "Leave records link"),
    )

    conn.commit()
    conn.close()
    return 99


def test_dataset_relationship_engine_discovery(multi_sheet_dataset):
    """Verify relationship engine discovers cross-sheet joins with confidence and cardinality."""
    sheets = [
        SheetContext(sheet_id=101, sheet_name="Employees", row_count=50, col_count=3, entity_type="employee", columns=["employee_id", "department"]),
        SheetContext(sheet_id=102, sheet_name="Attendance", row_count=500, col_count=3, entity_type="attendance", columns=["employee_id", "date"]),
        SheetContext(sheet_id=103, sheet_name="Leave", row_count=120, col_count=3, entity_type="leave", columns=["employee_id", "leave_days"]),
    ]

    rel_graph = DatasetRelationshipEngine.discover_relationships(multi_sheet_dataset, sheets)
    assert len(rel_graph.relationships) >= 2

    r1 = rel_graph.relationships[0]
    assert r1.left_column == "employee_id"
    assert r1.right_column == "employee_id"
    assert r1.join_confidence >= 0.95
    assert r1.cardinality in ("one-to-many", "many-to-one")


def test_redundancy_suppression_and_slot_budget():
    """Verify redundant findings are suppressed and slot budgets are hard-governed."""
    # 4 repetitive findings about Sales attendance
    candidates = [
        InsightCandidate(
            candidate_id="INS-01",
            title="Sales presence is 10.2 days",
            scope="SINGLE_SHEET",
            slot_type="strategic",
            metric_name="attendance_days",
            dimension_name="Sales",
            business_impact=0.70,
            composite_score=0.72,
            redundancy_group="attendance_sales",
        ),
        InsightCandidate(
            candidate_id="INS-02",
            title="Sales attendance is 25% below company benchmark",
            scope="SINGLE_SHEET",
            slot_type="strategic",
            metric_name="attendance_days",
            dimension_name="Sales",
            business_impact=0.85,
            composite_score=0.88,  # Higher score -> should win
            redundancy_group="attendance_sales",
        ),
        InsightCandidate(
            candidate_id="INS-03",
            title="Sales office presence ranks lowest",
            scope="SINGLE_SHEET",
            slot_type="strategic",
            metric_name="attendance_days",
            dimension_name="Sales",
            business_impact=0.65,
            composite_score=0.69,
            redundancy_group="attendance_sales",
        ),
        # Distinct cross-sheet candidate
        InsightCandidate(
            candidate_id="INS-04",
            title="Teams with high overtime record 3x leave rate in following cycle",
            scope="CROSS_SHEET",
            slot_type="risk_foresight",
            metric_name="overtime_leave_interaction",
            dimension_name="Cross-Sheet",
            business_impact=0.95,
            cross_sheet_value=0.85,
            composite_score=0.94,
            redundancy_group="overtime_leave",
        ),
    ]

    selected, warnings = GlobalCandidatePoolEngine.select_dashboard_insights(candidates, DashboardSlotBudget())

    # Only 2 distinct groups should be selected (INS-02 won attendance_sales, INS-04 won overtime_leave)
    assert len(selected) == 2
    selected_ids = [s.candidate_id for s in selected]
    assert "INS-04" in selected_ids  # Cross-sheet hero
    assert "INS-02" in selected_ids  # Winning sales insight
    assert "INS-01" not in selected_ids  # Suppressed
    assert "INS-03" not in selected_ids  # Suppressed


def test_cross_sheet_boost_and_domain_coverage_warning():
    """Verify cross-sheet insights receive boost and single-domain dominance emits warning."""
    candidates = [
        InsightCandidate(
            candidate_id=f"INS-{i:02d}",
            title=f"Workforce Metric {i}",
            scope="SINGLE_SHEET",
            slot_type="strategic",
            domain="workforce_hr",
            metric_name=f"metric_{i}",
            dimension_name=f"dim_{i}",
            composite_score=0.80,
            redundancy_group=f"group_{i}",
        )
        for i in range(1, 6)
    ]

    selected, warnings = GlobalCandidatePoolEngine.select_dashboard_insights(candidates, DashboardSlotBudget())
    assert len(selected) >= 4
    # All 5 came from workforce_hr -> should trigger CoverageWarning
    assert len(warnings) == 1
    assert "CoverageWarning" in warnings[0]
    assert "workforce_hr" in warnings[0]


def test_end_to_end_dataset_intelligence_and_mcp_tools(multi_sheet_dataset):
    """Verify run_dataset_intelligence executes across sheets and MCP tools respond."""
    res = run_dataset_intelligence(multi_sheet_dataset)
    assert isinstance(res, DatasetIntelligenceResponse)
    assert res.dataset_id == multi_sheet_dataset
    assert res.sheet_count == 3
    assert res.relationship_count >= 2
    assert res.cross_sheet_evidence_count >= 2
    assert len(res.selected_dashboard_insights) <= 9  # Hard budget respected

    # Test MCP tool: query_dataset_insights
    mcp_res = GovernedMCPGateway.execute_tool(
        tool_name="query_dataset_insights",
        params={"dataset_id": multi_sheet_dataset},
        caller_role=AgentRole.HRIDAY_COPILOT,
    )
    assert mcp_res.status == "success"
    assert "selected_dashboard_insights" in mcp_res.data

    # Test MCP tool: query_cross_sheet_insights
    mcp_cross = GovernedMCPGateway.execute_tool(
        tool_name="query_cross_sheet_insights",
        params={"dataset_id": multi_sheet_dataset},
        caller_role=AgentRole.COUNCIL_CRITIC,
    )
    assert mcp_cross.status == "success"
    assert "cross_sheet_insights" in mcp_cross.data
    assert len(mcp_cross.data["cross_sheet_insights"]) >= 1
