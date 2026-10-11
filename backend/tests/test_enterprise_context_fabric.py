"""Acceptance and unit test suite for Enterprise Knowledge & Context Fabric (Phase F).

Verifies:
1. All 6 Context MCP tools registered under capability group 'context' with typed schemas.
2. Authoritative threshold retrieval (workforce, environmental, retail).
3. KPI definition and calculation standard retrieval.
4. Complete policy document retrieval and constituent CTX-* evidence tokens.
5. Hybrid deterministic context search across domains.
6. Cryptographic provenance tracing for CTX-* tokens.
7. Dynamic organizational document ingestion with custom rule extraction.
8. Strict Epistemological Isolation (EVID != CTX != SCEN) and anomaly detection on namespace contamination.
9. Compound claim grounding pairing empirical data [EVID-*] with policy benchmark [CTX-*].
10. GovernedMCPGateway execution envelope and ledger auditing.
11. Technical Explorer REST API endpoints under /api/context/.
12. Zero bypass violations reported by MCPBypassAuditor.
"""
from __future__ import annotations

import time
import pytest
from fastapi.testclient import TestClient

from app.context import (
    ContextArtifactType,
    ContextDocument,
    ContextEvidence,
    context_store,
)
from app.mcp import (
    GovernanceStatus,
    GovernedMCPGateway,
    MCPBypassAuditor,
    MCPToolRequest,
    mcp_execution_ledger,
    mcp_registry,
)
from app.observability.contracts import AITrace, RuntimeAnomaly
from app.observability.evaluators.grounding import GroundingEvaluator
from app.observability.metrics import AnomalyDetector
from app.main import app


@pytest.fixture(autouse=True)
def clean_context_state():
    """Resets context store and execution ledger between tests."""
    context_store.clear_for_test()
    mcp_execution_ledger.clear_for_test()
    yield
    context_store.clear_for_test()
    mcp_execution_ledger.clear_for_test()


def test_01_context_mcp_tools_registered_with_typed_schemas():
    """Scenario 1: All 6 Context MCP tools are registered under 'context' capability group."""
    context_tools = mcp_registry.list_definitions(capability_group="context")
    tool_names = {t.tool_name for t in context_tools}

    expected_tools = {
        "search_context",
        "get_policy",
        "get_business_definition",
        "get_threshold",
        "get_document_evidence",
        "trace_context_provenance",
    }
    assert expected_tools == tool_names, f"Expected Context tools {expected_tools}, got {tool_names}"

    for defn in context_tools:
        assert defn.capability_group == "context"
        assert defn.read_only is True
        assert hasattr(defn.input_schema, "model_validate")
        assert hasattr(defn.output_schema, "model_validate")


def test_02_authoritative_threshold_retrieval_across_domains():
    """Scenario 2: Context MCP retrieves official thresholds for workforce, ESG, and retail."""
    # Workforce: 3.0 days/week WFO attendance
    req_wf = MCPToolRequest(
        tool_name="get_threshold",
        arguments={"metric_name": "office_attendance_days"},
    )
    resp_wf = GovernedMCPGateway.execute(req_wf)
    assert resp_wf.success is True
    assert resp_wf.result["found"] is True
    assert resp_wf.result["threshold_value"] == 3.0
    assert resp_wf.result["operator"] == "MIN"
    assert resp_wf.result["unit"] == "days/week"
    assert "CTX-WF-001" in resp_wf.context_ids

    # Workforce: 15% voluntary attrition cap
    req_att = MCPToolRequest(
        tool_name="get_threshold",
        arguments={"metric_name": "voluntary_attrition_rate"},
    )
    resp_att = GovernedMCPGateway.execute(req_att)
    assert resp_att.success is True
    assert resp_att.result["threshold_value"] == 15.0
    assert resp_att.result["operator"] == "MAX"
    assert "CTX-WF-004" in resp_att.context_ids

    # Environmental: 500 MT CO2e carbon cap
    req_env = MCPToolRequest(
        tool_name="get_threshold",
        arguments={"metric_name": "carbon_emissions_mt"},
    )
    resp_env = GovernedMCPGateway.execute(req_env)
    assert resp_env.success is True
    assert resp_env.result["threshold_value"] == 500.0
    assert "CTX-ENV-001" in resp_env.context_ids

    # Retail: 1.2% shrinkage cap
    req_ret = MCPToolRequest(
        tool_name="get_threshold",
        arguments={"metric_name": "inventory_shrinkage_rate"},
    )
    resp_ret = GovernedMCPGateway.execute(req_ret)
    assert resp_ret.success is True
    assert resp_ret.result["threshold_value"] == 1.2
    assert "CTX-RET-001" in resp_ret.context_ids


def test_03_kpi_definition_and_formula_lookup():
    """Scenario 3: Retrieves authoritative KPI definition formula from Context Fabric."""
    req = MCPToolRequest(
        tool_name="get_business_definition",
        arguments={"term": "voluntary attrition"},
    )
    resp = GovernedMCPGateway.execute(req)
    assert resp.success is True
    assert resp.result["found"] is True
    assert "Voluntary Terminations / Average Monthly Active Headcount" in resp.result["definition"]
    assert "CTX-WF-003" in resp.context_ids


def test_04_policy_document_retrieval_and_constituent_evidence():
    """Scenario 4: Retrieves full policy document with constituent CTX-* tokens."""
    req = MCPToolRequest(
        tool_name="get_policy",
        arguments={"policy_name_or_id": "Global Workplace Policy"},
    )
    resp = GovernedMCPGateway.execute(req)
    assert resp.success is True
    assert resp.result["document_id"] == "DOC-WF-001"
    assert "CTX-WF-001" in resp.result["context_ids"]
    assert "CTX-WF-002" in resp.result["context_ids"]
    assert len(resp.result["extracted_evidence"]) == 2


def test_05_hybrid_context_search_with_domain_filtering():
    """Scenario 5: Search Context Fabric by keywords and verify relevance scoring."""
    req = MCPToolRequest(
        tool_name="search_context",
        arguments={"query": "minimum office attendance requirement", "domain": "workforce"},
    )
    resp = GovernedMCPGateway.execute(req)
    assert resp.success is True
    assert resp.result["total_matched"] >= 1
    top_match = resp.result["matches"][0]
    assert top_match["context_id"] == "CTX-WF-001"
    assert "3 days per week" in top_match["verbatim_excerpt"]


def test_06_cryptographic_provenance_tracing_for_context_tokens():
    """Scenario 6: Traces cryptographic SHA-256 hash and document provenance for CTX-* tokens."""
    req = MCPToolRequest(
        tool_name="trace_context_provenance",
        arguments={"context_ids": ["CTX-WF-001", "CTX-ENV-001"]},
    )
    resp = GovernedMCPGateway.execute(req)
    assert resp.success is True
    assert resp.result["total_records"] == 2

    rec_wf = resp.result["records"][0]
    assert rec_wf["context_id"] == "CTX-WF-001"
    assert len(rec_wf["provenance_hash"]) == 64  # SHA-256 hex length
    assert "global_workplace_policy" in rec_wf["source_uri"]


def test_07_dynamic_document_ingestion_and_custom_rule_extraction():
    """Scenario 7: Dynamic ingestion of a new SOP document creates new verified CTX-* tokens."""
    doc = ContextDocument(
        document_id="DOC-OPS-099",
        title="Manufacturing Shift Safety SOP v1.0",
        artifact_type=ContextArtifactType.SOP,
        domain="workforce",
        department="Operations",
        raw_content="Section 4.1: Maximum Continuous Shift Hours.\nOperators must not exceed 8.0 continuous hours without a mandatory 45-minute rest interval.",
        source_uri="file:///policies/ops/safety_sop_v1.0.pdf",
    )
    ev = ContextEvidence.create(
        document_id=doc.document_id,
        artifact_type=ContextArtifactType.THRESHOLD,
        domain="workforce",
        title="Maximum Continuous Shift Hours",
        section="Section 4.1",
        verbatim_excerpt="Operators must not exceed 8.0 continuous hours without a mandatory 45-minute rest interval.",
        rule_summary="Maximum continuous shift is 8.0 hours.",
        metric_name="continuous_shift_hours",
        operator="MAX",
        threshold_value=8.0,
        unit="hours",
        department="Operations",
        source_uri=doc.source_uri,
        context_id="CTX-OPS-099",
    )
    doc.extracted_evidence = [ev]
    context_store.ingest_document(doc)

    # Verify retrieval through MCP
    req = MCPToolRequest(
        tool_name="get_document_evidence",
        arguments={"context_id": "CTX-OPS-099"},
    )
    resp = GovernedMCPGateway.execute(req)
    assert resp.success is True
    assert resp.result["found"] is True
    assert resp.result["evidence"]["threshold_value"] == 8.0
    assert resp.result["evidence"]["department"] == "Operations"


def test_08_strict_epistemological_separation_and_contamination_detection():
    """Scenario 8: Enforces strict separation of EVID, CTX, and SCEN namespaces."""
    # Valid isolated trace
    valid_trace = AITrace(
        request_id="tr-valid-ctx",
        conversation_id="conv-1",
        evidence_ids=["EVID-101", "EVID-102"],
        context_ids=["CTX-WF-001"],
        scenario_ids=[],
        status="COMPLETED",
    )
    anomalies_valid = AnomalyDetector.scan_trace_for_anomalies(valid_trace)
    assert not any("CONTAMINATION" in a.anomaly_type for a in anomalies_valid)

    # Contaminated trace 1: CTX token placed inside empirical evidence_ids
    contaminated_trace_1 = AITrace(
        request_id="tr-contam-1",
        conversation_id="conv-1",
        evidence_ids=["EVID-101", "CTX-WF-001"],  # Violation!
        context_ids=[],
        status="COMPLETED",
    )
    anomalies_1 = AnomalyDetector.scan_trace_for_anomalies(contaminated_trace_1)
    assert any(a.anomaly_type == "CONTEXT_EVIDENCE_CONTAMINATION" for a in anomalies_1)

    # Contaminated trace 2: Counterfactual SCEN token placed inside context_ids
    contaminated_trace_2 = AITrace(
        request_id="tr-contam-2",
        conversation_id="conv-1",
        evidence_ids=["EVID-101"],
        context_ids=["SCEN-COUNTERFACTUAL-01"],  # Violation!
        status="COMPLETED",
    )
    anomalies_2 = AnomalyDetector.scan_trace_for_anomalies(contaminated_trace_2)
    assert any(a.anomaly_type == "SCENARIO_CONTEXT_CONTAMINATION" for a in anomalies_2)


def test_09_compound_claim_grounding_pairs_evid_and_ctx():
    """Scenario 9: Evaluates compound claim combining empirical data [EVID-*] with policy benchmark [CTX-*]."""
    answer = (
        "Operations attendance averages 2.4 days/week [EVID-028], which fails to meet "
        "the mandatory company workplace policy of 3.0 days/week [CTX-WF-001]."
    )

    grounding_eval, attributions, causal_eval = GroundingEvaluator.evaluate(
        final_answer=answer,
        state_evidence_ids=["EVID-028"],
        state_context_ids=["CTX-WF-001"],
    )

    assert grounding_eval.factual_claim_count == 1
    assert grounding_eval.evid_grounded_claims == 1
    assert grounding_eval.ctx_grounded_claims == 1
    assert grounding_eval.ungrounded_claims == 0
    assert grounding_eval.conflicting_claims == 0
    assert grounding_eval.grounding_rate == 1.0
    assert grounding_eval.is_fully_grounded is True

    assert len(attributions) == 1
    attr = attributions[0]
    assert attr.verification_status == "VERIFIED"
    assert "EVID-028" in attr.evidence_ids
    assert "CTX-WF-001" in attr.context_ids


def test_10_mcp_gateway_execution_ledger_records_context_invocations():
    """Scenario 10: GovernedMCPGateway creates audited execution ledger record for Context MCP calls."""
    req = MCPToolRequest(
        tool_name="get_threshold",
        arguments={"metric_name": "office_attendance_days"},
        caller="hriday_orchestrator",
    )
    resp = GovernedMCPGateway.execute(req)
    assert resp.success is True

    record = mcp_execution_ledger.get_record(resp.execution_id)
    assert record is not None
    assert record.tool_name == "get_threshold"
    assert record.caller == "hriday_orchestrator"
    assert record.governance_status == GovernanceStatus.PASS
    assert record.success is True


def test_11_context_fabric_rest_api_endpoints():
    """Scenario 11: Validates FastAPI endpoints under /api/context/."""
    client = TestClient(app)

    # 1. List documents
    res = client.get("/api/context/documents")
    assert res.status_code == 200
    docs = res.json()
    assert len(docs) >= 3

    # 2. Document details
    res = client.get("/api/context/documents/DOC-WF-001")
    assert res.status_code == 200
    doc_wf = res.json()
    assert doc_wf["document_id"] == "DOC-WF-001"
    assert len(doc_wf["extracted_evidence"]) >= 1

    # 3. List evidence items
    res = client.get("/api/context/evidence")
    assert res.status_code == 200
    evidence_list = res.json()
    assert len(evidence_list) >= 4

    # 4. Evidence details with provenance
    res = client.get("/api/context/evidence/CTX-WF-001")
    assert res.status_code == 200
    ev_detail = res.json()
    assert ev_detail["evidence"]["context_id"] == "CTX-WF-001"
    assert "provenance" in ev_detail
    assert len(ev_detail["provenance"]["provenance_hash"]) == 64

    # 5. Threshold endpoint
    res = client.get("/api/context/thresholds/office_attendance_days")
    assert res.status_code == 200
    th_data = res.json()
    assert th_data["threshold_value"] == 3.0

    # 6. Search endpoint
    res = client.post("/api/context/search", json={"query": "carbon emission budget", "domain": "environmental"})
    assert res.status_code == 200
    search_data = res.json()
    assert search_data["total_matched"] >= 1


def test_12_mcp_bypass_auditor_reports_zero_violations():
    """Scenario 12: MCPBypassAuditor confirms zero direct DB or service bypasses in agent layer."""
    res = MCPBypassAuditor.audit_agent_layer("backend/app/agent")
    assert res.is_compliant is True
    assert res.violation_count == 0, f"Detected bypass violations: {[v.line_content for v in res.violations]}"
