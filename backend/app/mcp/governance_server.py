"""Governance MCP Capability Server (Phase B).

Exposes governance gates, dataset isolation checks, and human approval nodes:
- check_entitlement
- check_dataset_scope (DatasetIsolationIntegrity)
- check_claim (ClaimEntitlementIntegrity)
- check_scenario_permission
- request_approval
- get_decision_provenance

Acts as pre-flight validation layer for all sensitive or high-risk tool operations.
"""
from __future__ import annotations

import logging
from uuid import uuid4
from typing import Any

from ..services.copilot.control_plane.claim_governor import ClaimEntitlementGovernor
from .contracts import (
    CheckClaimInput,
    CheckClaimOutput,
    CheckDatasetScopeInput,
    CheckDatasetScopeOutput,
    CheckEntitlementInput,
    CheckEntitlementOutput,
    CheckScenarioPermissionInput,
    CheckScenarioPermissionOutput,
    GetDecisionProvenanceInput,
    GetDecisionProvenanceOutput,
    MCPToolDefinition,
    RequestApprovalInput,
    RequestApprovalOutput,
    ToolRiskLevel,
)
from .execution_ledger import mcp_execution_ledger
from .registry import mcp_registry

logger = logging.getLogger(__name__)


# -----------------------------------------------------------------------------
# Handlers
# -----------------------------------------------------------------------------

def handle_check_entitlement(args: dict[str, Any], context: Any = None) -> CheckEntitlementOutput:
    inp = CheckEntitlementInput.model_validate(args)
    caller = inp.caller
    cap = inp.requested_capability.lower()

    # Viewers restricted from compensation or scenario mutation
    if caller.lower() == "viewer" and any(k in cap for k in ("scenario", "counterfactual", "salary")):
        return CheckEntitlementOutput(
            caller=caller,
            capability=inp.requested_capability,
            allowed=False,
            rejection_reason=f"Role '{caller}' is unauthorized for sensitive capability '{inp.requested_capability}'.",
        )

    return CheckEntitlementOutput(
        caller=caller,
        capability=inp.requested_capability,
        allowed=True,
    )


def handle_check_dataset_scope(args: dict[str, Any], context: Any = None) -> CheckDatasetScopeOutput:
    inp = CheckDatasetScopeInput.model_validate(args)
    active_id = str(inp.active_dataset_id)
    req_id = str(inp.requested_dataset_id)
    allow_cross = inp.allow_cross_dataset

    # Enforce DatasetIsolationIntegrity: foreign dataset IDs strictly rejected
    if active_id != req_id and not allow_cross:
        return CheckDatasetScopeOutput(
            in_scope=False,
            violation_detected=True,
            reason=(
                f"Dataset isolation violation: requested dataset '{req_id}' "
                f"does not match active authorized dataset '{active_id}'."
            ),
        )

    return CheckDatasetScopeOutput(
        in_scope=True,
        violation_detected=False,
    )


def handle_check_claim(args: dict[str, Any], context: Any = None) -> CheckClaimOutput:
    inp = CheckClaimInput.model_validate(args)
    claim = inp.claim_text
    evid_types = inp.available_evidence_types

    audit_res = ClaimEntitlementGovernor.audit_claim(claim, evid_types)

    return CheckClaimOutput(
        claim_text=claim,
        is_entitled=audit_res.is_entitled,
        detected_claim_type=audit_res.detected_claim_type.value,
        linguistic_conformance=audit_res.linguistic_conformance,
        rejection_reason=audit_res.rejection_reason,
        suggested_reformulation=audit_res.suggested_reformulation,
    )


def handle_check_scenario_permission(args: dict[str, Any], context: Any = None) -> CheckScenarioPermissionOutput:
    inp = CheckScenarioPermissionInput.model_validate(args)
    dataset_id = str(inp.dataset_id)

    # Domain entitlement
    domain = "workforce" if dataset_id == "99767" or "workforce" in dataset_id.lower() else "environmental"
    permitted = (domain == "workforce")
    reason = None if permitted else "Scenario counterfactual re-evaluations are strictly gated to workforce domains."

    return CheckScenarioPermissionOutput(
        dataset_id=dataset_id,
        domain=domain,
        permitted=permitted,
        reason=reason,
    )


def handle_request_approval(args: dict[str, Any], context: Any = None) -> RequestApprovalOutput:
    inp = RequestApprovalInput.model_validate(args)
    app_id = f"APP-{uuid4().hex[:8].upper()}"

    return RequestApprovalOutput(
        approval_id=app_id,
        status="PENDING",
        approver=None,
        audit_token=f"TOKEN-{abs(hash((inp.caller, inp.action_type))) % 1000000:06d}",
    )


def handle_get_decision_provenance(args: dict[str, Any], context: Any = None) -> GetDecisionProvenanceOutput:
    inp = GetDecisionProvenanceInput.model_validate(args)
    exec_id = inp.execution_id

    rec = mcp_execution_ledger.get_record(exec_id)
    if rec:
        return GetDecisionProvenanceOutput(
            execution_id=rec.execution_id,
            tool_name=rec.tool_name,
            caller=rec.caller,
            dataset_id=rec.dataset_id,
            governance_status=rec.governance_status.value,
            evidence_ids=rec.evidence_ids,
            duration_ms=rec.duration_ms,
            timestamp=rec.started_at,
        )

    return GetDecisionProvenanceOutput(
        execution_id=exec_id,
        tool_name="unknown",
        caller="unknown",
        dataset_id=None,
        governance_status="NOT_FOUND",
        evidence_ids=[],
        duration_ms=0.0,
        timestamp=0.0,
    )


# -----------------------------------------------------------------------------
# Registration
# -----------------------------------------------------------------------------

def register_governance_tools() -> None:
    """Registers all Governance MCP tools into the central registry."""
    tools = [
        (
            MCPToolDefinition(
                tool_name="check_entitlement",
                capability_group="governance",
                description="Verify caller authorization before executing a sensitive capability.",
                input_schema=CheckEntitlementInput,
                output_schema=CheckEntitlementOutput,
                risk_level=ToolRiskLevel.LOW,
                requires_dataset_scope=False,
            ),
            handle_check_entitlement,
        ),
        (
            MCPToolDefinition(
                tool_name="check_dataset_scope",
                capability_group="governance",
                description="Enforce DatasetIsolationIntegrity: block unauthorized cross-dataset data leakage.",
                input_schema=CheckDatasetScopeInput,
                output_schema=CheckDatasetScopeOutput,
                risk_level=ToolRiskLevel.LOW,
                requires_dataset_scope=False,
            ),
            handle_check_dataset_scope,
        ),
        (
            MCPToolDefinition(
                tool_name="check_claim",
                capability_group="governance",
                description="Audit analytical claim for required supporting evidence types and prohibited causal verbs.",
                input_schema=CheckClaimInput,
                output_schema=CheckClaimOutput,
                risk_level=ToolRiskLevel.LOW,
                requires_dataset_scope=False,
            ),
            handle_check_claim,
        ),
        (
            MCPToolDefinition(
                tool_name="check_scenario_permission",
                capability_group="governance",
                description="Verify if dataset domain is entitled to run counterfactual scenario simulations.",
                input_schema=CheckScenarioPermissionInput,
                output_schema=CheckScenarioPermissionOutput,
                risk_level=ToolRiskLevel.LOW,
            ),
            handle_check_scenario_permission,
        ),
        (
            MCPToolDefinition(
                tool_name="request_approval",
                capability_group="governance",
                description="Request human approval node before high-impact or destructive actions.",
                input_schema=RequestApprovalInput,
                output_schema=RequestApprovalOutput,
                risk_level=ToolRiskLevel.CRITICAL,
                requires_human_approval=True,
            ),
            handle_request_approval,
        ),
        (
            MCPToolDefinition(
                tool_name="get_decision_provenance",
                capability_group="governance",
                description="Retrieve cryptographic audit record and governance trace for an execution ID.",
                input_schema=GetDecisionProvenanceInput,
                output_schema=GetDecisionProvenanceOutput,
                risk_level=ToolRiskLevel.LOW,
                requires_dataset_scope=False,
            ),
            handle_get_decision_provenance,
        ),
    ]

    for defn, handler in tools:
        mcp_registry.register(defn, handler)
