"""Unit tests for Governed MCP Gateway, Agent RBAC, and Claim Validator."""
from __future__ import annotations

import json
import pytest

from app.db.database import get_connection
from app.services.adaptive_dashboard.claim_validator import (
    ClaimValidator,
    GovernedAgentResponse,
    GovernedAuditReport,
    StructuredClaim,
)
from app.services.adaptive_dashboard.contracts import AdaptiveDashboardResponse, UnifiedFinding
from app.services.adaptive_dashboard.engine import run_adaptive_dashboard
from app.services.adaptive_dashboard.evidence_graph import EvidenceGraph, EvidenceItem, findings_to_evidence_graph
from app.services.adaptive_dashboard.mcp_gateway import (
    AgentRole,
    GovernedMCPGateway,
    MCPToolResult,
    ScenarioEvidence,
)


@pytest.fixture
def test_dashboard_response():
    """Builds a test AdaptiveDashboardResponse with populated catalog and evidence graph."""
    findings = [
        UnifiedFinding(
            finding_id="f1",
            recipe_id="recipe_s09_segment_disparity",
            calculation_id="calc_s09_01",
            definition_id="def_s09",
            source_sheet_ids=[1],
            source_scope=["Attendance Sheet"],
            snapshot="snap_test_123",
            status="available",
            short_business_title="Operations and Infrastructure",
            typed_value=17.23,
            formatted_value="17.23 days",
            unit="days",
            population_or_exposure="26 employees",
            comparison_and_effect="+42.4% vs company baseline",
            evidence_bound_observation="Operations recorded highest presence.",
            one_next_check_or_action="Audit shift schedule.",
            allowed_claim_level="descriptive_fact",
            analytical_subject="workforce",
            decision_category="segment_disparity",
            rank_score=95.0,
        ),
        UnifiedFinding(
            finding_id="f2",
            recipe_id="recipe_s10_composition_reversal",
            calculation_id="calc_s10_01",
            definition_id="def_s10",
            source_sheet_ids=[1],
            source_scope=["Attendance Sheet"],
            snapshot="snap_test_123",
            status="available",
            short_business_title="Leave vs Attendance Correlation",
            typed_value=0.68,
            formatted_value="0.68 r",
            unit="r",
            population_or_exposure="100 employees",
            comparison_and_effect="Moderate correlation",
            evidence_bound_observation="Leave days coincided with remote shifts.",
            one_next_check_or_action="Evaluate policy impact.",
            allowed_claim_level="statistical_association",
            analytical_subject="workforce",
            decision_category="correlation",
            rank_score=85.0,
        ),
    ]

    graph = findings_to_evidence_graph(findings, sheet_id=1, snapshot="snap_test_123")
    
    # Minimal dummy contracts for response context
    from app.services.adaptive_dashboard.contracts import (
        ComponentSpec,
        EvidenceResult,
        ExplainSpec,
        GlanceSpec,
        InspectSpec,
        SemanticContract,
        SourceManifest,
    )

    manifest = SourceManifest(
        sheet_id=1,
        sheet_name="Sheet1",
        file_name="test.csv",
        display_name="Test Attendance",
        row_count=100,
        col_count=5,
        snapshot="snap_test_123",
    )
    contract = SemanticContract(
        layout="wide_entity_matrix",
        entity_type="employee",
        entity_identifiers=["Person_0"],
        grain_description="daily employee attendance",
        verification_basis="verified header",
    )
    elem = ComponentSpec(
        component_id="primary_element",
        kind="kpi",
        business_concept="office_attendance",
        glance=GlanceSpec(label="Employee count", formatted_value="100"),
        explain=ExplainSpec(short_definition="Test count", exact_value_text="100 employees"),
        inspect=InspectSpec(
            metric_title="Count",
            exact_value="100",
            what_this_counts="Employees",
            applicable_population="100",
            source_name="Sheet1",
            calculation_method="COUNT(*)",
            data_completeness="complete",
            workforce_coverage="100%",
            selection_reason="primary",
            calculation_id="calc_1",
            definition_id="def_1",
            snapshot="snap_test_123",
            provenance="test",
        ),
        evidence=EvidenceResult(
            calculation_id="calc_1",
            snapshot="snap_test_123",
            definition_id="def_1",
            status="available",
            value=100,
            unit="employees",
            aggregation="count",
            calculation_method="COUNT(*)",
            provenance="test",
        ),
        title="Employee count",
        verified_value=100.0,
        formatted_value="100",
        unit="employees",
        scope_label="Company",
        coverage_qualifier="In data",
        selection_reason="primary",
    )

    return AdaptiveDashboardResponse(
        version="adaptive-v10",
        snapshot="snap_test_123",
        sheet_id=1,
        manifest=manifest,
        contract=contract,
        element=elem,
        evidence_graph=graph.model_dump(),
        semantic_catalog={
            "sheet_id": 1,
            "sheet_name": "Sheet1",
            "entity_type": "employee",
            "metrics": [{"name": "attendance_days", "unit": "days", "direction": "higher_is_better"}],
            "dimensions": [{"name": "department", "data_type": "categorical"}],
        },
        run_status="ready",
    )


def test_mcp_gateway_rbac_enforcement(test_dashboard_response):
    """Verify role permissions are strictly enforced across tools."""
    # HRIDAY_COPILOT is authorized for query_insights
    res_copilot = GovernedMCPGateway.execute_tool(
        tool_name="query_insights",
        params={"top_n": 2},
        caller_role=AgentRole.HRIDAY_COPILOT,
        dashboard_response=test_dashboard_response,
    )
    assert res_copilot.status == "success"
    assert len(res_copilot.evidence_ids_accessed) > 0

    # STORY_PLANNER is unauthorized for run_counterfactual
    res_planner = GovernedMCPGateway.execute_tool(
        tool_name="run_counterfactual",
        params={"delta_pct": 10.0},
        caller_role=AgentRole.STORY_PLANNER,
        dashboard_response=test_dashboard_response,
    )
    assert res_planner.status == "permission_denied"
    assert "unauthorized" in res_planner.error_message


def test_mcp_gateway_counterfactual_isolates_scenario(test_dashboard_response):
    """Verify run_counterfactual produces SCEN-xxx tokens without mutating EVID-xxx nodes."""
    res = GovernedMCPGateway.execute_tool(
        tool_name="run_counterfactual",
        params={"delta_pct": 15.0},
        caller_role=AgentRole.HRIDAY_COPILOT,
        dashboard_response=test_dashboard_response,
    )

    assert res.status == "success"
    assert len(res.scenario_ids_generated) == 1
    scen_id = res.scenario_ids_generated[0]
    assert scen_id.startswith("SCEN-")
    assert res.data["scenario_result"]["projected_outcome"] == 115.0

    # Check that evidence graph nodes remain purely EVID-xxx
    graph_nodes = test_dashboard_response.evidence_graph["nodes"]
    for node in graph_nodes:
        assert node["evidence_id"].startswith("EVID-")
        assert not node["evidence_id"].startswith("SCEN-")


def test_mcp_gateway_evidence_lineage(test_dashboard_response):
    """Verify get_evidence_lineage returns cryptographic snapshot and row lineage."""
    res = GovernedMCPGateway.execute_tool(
        tool_name="get_evidence_lineage",
        params={"evidence_id": "EVID-001"},
        caller_role=AgentRole.COUNCIL_CRITIC,
        dashboard_response=test_dashboard_response,
    )

    assert res.status == "success"
    lineage = res.data["lineage"]
    assert lineage["evidence_id"] == "EVID-001"
    assert lineage["snapshot_hash"] == "snap_test_123"
    assert lineage["total_rows"] == 100


def test_claim_validator_passes_valid_claims(test_dashboard_response):
    """Verify ClaimValidator passes grounded claims with 0 unsupported claims."""
    graph = EvidenceGraph(**test_dashboard_response.evidence_graph)
    claims = [
        StructuredClaim(
            claim_id="CLM-001",
            claim_text="Operations recorded 17.23 days in July.",
            evidence_ids=["EVID-001"],
            causal_type="OBSERVED",
        )
    ]

    gov_resp = ClaimValidator.audit_response(
        answer="Operations recorded 17.23 days in July.",
        claims=claims,
        graph=graph,
    )

    assert gov_resp.audit.grounding_validation == "PASSED"
    assert gov_resp.audit.unsupported_claims_count == 0
    assert gov_resp.audit.evidence_coverage_pct == 100.0
    assert gov_resp.audit.numeric_reconciliation == "PASSED"
    assert len(gov_resp.audit.causal_violations) == 0


def test_claim_validator_catches_unauthorized_causality(test_dashboard_response):
    """Verify ClaimValidator flags causal upgrade violations on associative evidence."""
    graph = EvidenceGraph(**test_dashboard_response.evidence_graph)
    # EVID-002 has causal_classification == "ASSOCIATED"
    claims = [
        StructuredClaim(
            claim_id="CLM-002",
            claim_text="Lower office attendance was caused by remote shift policies.",
            evidence_ids=["EVID-002"],
            causal_type="ASSOCIATED",
        )
    ]

    gov_resp = ClaimValidator.audit_response(
        answer="Lower office attendance was caused by remote shift policies.",
        claims=claims,
        graph=graph,
    )

    assert gov_resp.audit.grounding_validation == "WARNING"
    assert len(gov_resp.audit.causal_violations) == 1
    assert "caused by" in gov_resp.audit.causal_violations[0]
