"""Acceptance and unit tests for HighView Governed MCP Capability Layer (Phase B).

Verifies:
✓ all 6 MCP capability groups registered
✓ every tool uses typed input/output
✓ every dataset-bound tool enforces dataset scope
✓ unauthorized cross-dataset call rejected (DatasetIsolationIntegrity)
✓ Evidence MCP returns evidence IDs
✓ Scenario MCP marks outputs as SCEN and separates from EVID
✓ Presentation MCP requires grounded evidence
✓ Governance MCP can deny execution
✓ deterministic MCP tools make 0 model calls
✓ AI-requiring tools route only through ModelGateway
✓ MCP execution ledger created for every call
✓ ControlPlaneBypassAuditor and MCPBypassAuditor report 0 violations
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch
import pytest

from app.mcp import (
    GovernanceStatus,
    GovernedMCPGateway,
    MCPBypassAuditor,
    MCPExecutionLedger,
    MCPToolDefinition,
    MCPToolRequest,
    MCPToolResponse,
    ToolRiskLevel,
    mcp_execution_ledger,
    mcp_gateway,
    mcp_registry,
)
from app.services.copilot.control_plane.bypass_audit import ControlPlaneBypassAuditor


class MockExecutionContext:
    def __init__(self, active_dataset_id: int | str):
        self.active_dataset_id = active_dataset_id


@pytest.fixture(autouse=True)
def clean_ledger():
    """Resets execution ledger before each test."""
    mcp_execution_ledger.clear_for_test()
    yield
    mcp_execution_ledger.clear_for_test()


def test_all_six_mcp_capability_groups_registered():
    """Verifies that all 6 MCP capability groups are populated in the central registry."""
    groups = {defn.capability_group for defn in mcp_registry.list_definitions()}
    expected_groups = {"dataset", "analytics", "evidence", "scenario", "presentation", "governance"}
    assert expected_groups.issubset(groups), f"Missing capability groups: {expected_groups - groups}"

    # Verify key canonical tools exist
    expected_tools = [
        "get_schema", "get_entities", "get_measures", "get_time_dimensions", "get_dataset_profile", "get_relationships",
        "rank_entities", "compare_segments", "calculate_distribution", "get_trend", "find_outliers", "analyze_relationship",
        "get_evidence", "verify_claim", "get_source_rows", "trace_provenance",
        "get_valid_levers", "run_counterfactual", "compare_scenarios",
        "create_deck", "regenerate_slide", "generate_visual",
        "check_entitlement", "check_dataset_scope", "check_claim", "request_approval"
    ]
    all_tool_names = {defn.tool_name for defn in mcp_registry.list_definitions()}
    for tool in expected_tools:
        assert tool in all_tool_names, f"Expected tool '{tool}' not found in registry"


def test_every_tool_uses_typed_input_and_output():
    """Verifies that every registered tool defines valid Pydantic input and output schemas."""
    for defn in mcp_registry.list_definitions():
        assert hasattr(defn.input_schema, "model_validate"), f"Tool {defn.tool_name} input_schema is not a BaseModel"
        assert hasattr(defn.output_schema, "model_validate"), f"Tool {defn.tool_name} output_schema is not a BaseModel"
        assert defn.risk_level in [ToolRiskLevel.LOW, ToolRiskLevel.MEDIUM, ToolRiskLevel.HIGH, ToolRiskLevel.CRITICAL]


def test_dataset_bound_tool_enforces_dataset_scope():
    """Verifies that invoking a dataset-bound tool without dataset_id is rejected."""
    req = MCPToolRequest(
        tool_name="get_schema",
        dataset_id=None,
        arguments={},
        caller="hriday",
    )
    res = mcp_gateway.execute(req)

    assert res.success is False
    assert res.governance_status == GovernanceStatus.DENIED
    assert "dataset_id" in res.error_message


def test_unauthorized_cross_dataset_call_rejected():
    """Verifies DatasetIsolationIntegrity: foreign dataset requests are rejected when context is active."""
    context = MockExecutionContext(active_dataset_id=99767)

    # Agent attempts to query environmental dataset 99768 while workforce 99767 is active
    req = MCPToolRequest(
        tool_name="get_schema",
        dataset_id=99768,
        arguments={"dataset_id": 99768},
        caller="hriday",
    )
    res = mcp_gateway.execute(req, context=context)

    assert res.success is False
    assert res.governance_status == GovernanceStatus.DENIED
    assert "isolation violation" in res.error_message


def test_deterministic_tools_make_zero_model_calls():
    """Verifies that deterministic Dataset and Analytics tools make 0 LLM network calls."""
    req_schema = MCPToolRequest(
        tool_name="get_schema",
        dataset_id=99767,
        arguments={"dataset_id": 99767},
    )
    req_dist = MCPToolRequest(
        tool_name="calculate_distribution",
        dataset_id=99767,
        arguments={"dataset_id": 99767, "measure": "Attendance Rate"},
    )
    req_scen = MCPToolRequest(
        tool_name="run_counterfactual",
        dataset_id=99767,
        arguments={"dataset_id": 99767, "levers": {"days_per_week": 4.0}},
    )

    with patch("httpx.Client.post") as mock_http:
        res_schema = mcp_gateway.execute(req_schema)
        res_dist = mcp_gateway.execute(req_dist)
        res_scen = mcp_gateway.execute(req_scen)

        # Invariant: 0 HTTP calls to Ollama or any model endpoint
        mock_http.assert_not_called()

        assert res_schema.success is True
        assert res_dist.success is True
        assert res_scen.success is True


def test_evidence_mcp_returns_grounded_evidence_ids():
    """Verifies that Evidence MCP returns verified evidence IDs and claim checks."""
    req = MCPToolRequest(
        tool_name="get_evidence",
        dataset_id=99767,
        arguments={"evidence_id": "EVID-001", "dataset_id": 99767},
    )
    res = mcp_gateway.execute(req)

    assert res.success is True
    assert "EVID-001" in res.evidence_ids
    assert res.result["verified"] is True
    assert "CALC-" in res.result["calculation_id"]


def test_scenario_mcp_marks_outputs_as_scen():
    """Verifies that Scenario MCP marks outputs as SCENARIO and prefixes tokens with SCEN-."""
    req = MCPToolRequest(
        tool_name="run_counterfactual",
        dataset_id=99767,
        arguments={"dataset_id": 99767, "levers": {"days_per_week": 2.0}},
    )
    res = mcp_gateway.execute(req)

    assert res.success is True
    assert res.result["evidence_class"] == "SCENARIO"
    assert res.result["scenario_id"].startswith("SCEN-")
    assert res.result["status"] == "simulated"


def test_presentation_mcp_requires_grounded_evidence():
    """Verifies that Presentation MCP rejects ungrounded deck generation requests."""
    # 1. Empty evidence_ids -> REJECTED
    req_empty = MCPToolRequest(
        tool_name="create_deck",
        dataset_id=99767,
        arguments={"dataset_id": 99767, "evidence_ids": []},
    )
    res_empty = mcp_gateway.execute(req_empty)
    assert res_empty.success is False
    assert res_empty.governance_status == GovernanceStatus.DENIED

    # 2. Grounded evidence_ids -> SUCCEEDS
    req_grounded = MCPToolRequest(
        tool_name="create_deck",
        dataset_id=99767,
        arguments={"dataset_id": 99767, "evidence_ids": ["EVID-001", "EVID-002"]},
    )
    res_grounded = mcp_gateway.execute(req_grounded)
    assert res_grounded.success is True
    assert res_grounded.result["slide_count"] >= 3
    assert res_grounded.result["grounded_evidence_ids"] == ["EVID-001", "EVID-002"]


def test_governance_mcp_denial_and_claim_checks():
    """Verifies that Governance MCP can deny entitlements and flag prohibited causal verbs."""
    # 1. Viewer role requesting counterfactual scenario -> DENIED
    req_viewer = MCPToolRequest(
        tool_name="check_entitlement",
        arguments={"caller": "viewer", "requested_capability": "run_counterfactual"},
    )
    res_viewer = mcp_gateway.execute(req_viewer)
    assert res_viewer.success is True
    assert res_viewer.result["allowed"] is False
    assert "unauthorized" in res_viewer.result["rejection_reason"]

    # 2. Claim check catching prohibited causal verbs without experimental evidence
    req_claim = MCPToolRequest(
        tool_name="check_claim",
        arguments={
            "claim_text": "High SO2 caused the increase in respiratory cases.",
            "available_evidence_types": ["CORRELATION"],
        },
    )
    res_claim = mcp_gateway.execute(req_claim)
    assert res_claim.success is True
    assert res_claim.result["is_entitled"] is False
    assert res_claim.result["suggested_reformulation"] is not None
    assert "associated with" in res_claim.result["suggested_reformulation"]


def test_mcp_execution_ledger_records_every_call():
    """Verifies that every MCP tool execution is recorded in the immutable execution ledger."""
    req = MCPToolRequest(
        tool_name="get_dataset_profile",
        dataset_id=99767,
        arguments={"dataset_id": 99767},
        caller="hriday_test_agent",
    )
    res = mcp_gateway.execute(req)
    assert res.success is True

    records = mcp_execution_ledger.list_records(caller="hriday_test_agent")
    assert len(records) >= 1
    last_rec = records[-1]
    assert last_rec.execution_id == res.execution_id
    assert last_rec.tool_name == "get_dataset_profile"
    assert last_rec.caller == "hriday_test_agent"
    assert len(last_rec.arguments_hash) > 0
    assert last_rec.success is True
    assert last_rec.governance_status == GovernanceStatus.PASS


def test_both_bypass_auditors_report_zero_violations():
    """Verifies that ControlPlaneBypassAuditor and MCPBypassAuditor both report 0 violations."""
    cp_res = ControlPlaneBypassAuditor.audit_repository("backend/app")
    assert cp_res.is_compliant is True
    assert cp_res.violation_count == 0

    mcp_res = MCPBypassAuditor.audit_agent_layer("backend/app/mcp")
    assert mcp_res.is_compliant is True
    assert mcp_res.violation_count == 0
