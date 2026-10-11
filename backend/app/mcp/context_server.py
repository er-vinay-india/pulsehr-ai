"""Context MCP Capability Server (Phase F).

Exposes governed organizational knowledge, policy retrieval, KPI definitions, and threshold benchmarks:
- search_context
- get_policy
- get_business_definition
- get_threshold
- get_document_evidence
- trace_context_provenance

Deterministic execution. Integrates directly with Enterprise Knowledge & Context Fabric (context_store).
Strict epistemological isolation: Returns CTX-* tokens, completely distinct from empirical EVID-* or counterfactual SCEN-*.
"""
from __future__ import annotations

import logging
from typing import Any

from ..context.store import context_store
from ..context.contracts import ContextEvidence
from .contracts import (
    ContextEvidenceItem,
    ContextProvenanceRecord,
    GetBusinessDefinitionInput,
    GetBusinessDefinitionOutput,
    GetDocumentEvidenceInput,
    GetDocumentEvidenceOutput,
    GetPolicyInput,
    GetPolicyOutput,
    GetThresholdInput,
    GetThresholdOutput,
    MCPToolDefinition,
    SearchContextInput,
    SearchContextOutput,
    ToolRiskLevel,
    TraceContextProvenanceInput,
    TraceContextProvenanceOutput,
)
from .registry import mcp_registry

logger = logging.getLogger(__name__)


def _to_evidence_item(ev: ContextEvidence) -> ContextEvidenceItem:
    return ContextEvidenceItem(
        context_id=ev.context_id,
        document_id=ev.document_id,
        artifact_type=ev.artifact_type.value,
        domain=ev.domain,
        title=ev.title,
        section=ev.section,
        verbatim_excerpt=ev.verbatim_excerpt,
        rule_summary=ev.rule_summary,
        metric_name=ev.metric_name,
        operator=ev.operator,
        threshold_value=ev.threshold_value,
        unit=ev.unit,
        department=ev.department,
        provenance_hash=ev.provenance_hash,
    )


# -----------------------------------------------------------------------------
# Handlers
# -----------------------------------------------------------------------------

def handle_search_context(args: dict[str, Any], context: Any = None) -> SearchContextOutput:
    inp = SearchContextInput.model_validate(args)
    res = context_store.search_context(
        query=inp.query,
        domain=inp.domain,
        artifact_type=inp.artifact_type,
        department=inp.department,
        limit=inp.limit,
    )
    items = [_to_evidence_item(ev) for ev in res.evidence_matches]
    cids = [ev.context_id for ev in res.evidence_matches]
    return SearchContextOutput(
        query=inp.query,
        total_matched=len(items),
        matches=items,
        context_ids=cids,
    )


def handle_get_policy(args: dict[str, Any], context: Any = None) -> GetPolicyOutput:
    inp = GetPolicyInput.model_validate(args)
    doc = context_store.get_policy(inp.policy_name_or_id)
    if not doc:
        return GetPolicyOutput(
            document_id=f"UNKNOWN-{inp.policy_name_or_id}",
            title=f"Policy '{inp.policy_name_or_id}' not found",
            artifact_type="POLICY",
            domain="general",
            version="unknown",
            effective_date="unknown",
            content_summary="No matching policy found in Context Fabric.",
            context_ids=[],
            extracted_evidence=[],
        )

    ev_items = [_to_evidence_item(ev) for ev in doc.extracted_evidence]
    cids = [ev.context_id for ev in doc.extracted_evidence]
    return GetPolicyOutput(
        document_id=doc.document_id,
        title=doc.title,
        artifact_type=doc.artifact_type.value,
        domain=doc.domain,
        version=doc.version,
        effective_date=doc.effective_date,
        content_summary=doc.raw_content[:300] + ("..." if len(doc.raw_content) > 300 else ""),
        context_ids=cids,
        extracted_evidence=ev_items,
    )


def handle_get_business_definition(args: dict[str, Any], context: Any = None) -> GetBusinessDefinitionOutput:
    inp = GetBusinessDefinitionInput.model_validate(args)
    ev = context_store.get_business_definition(inp.term)
    if not ev:
        return GetBusinessDefinitionOutput(
            term=inp.term,
            found=False,
        )

    return GetBusinessDefinitionOutput(
        term=inp.term,
        found=True,
        context_id=ev.context_id,
        definition=ev.verbatim_excerpt,
        metric_name=ev.metric_name,
        calculation_standard=ev.rule_summary,
        document_id=ev.document_id,
    )


def handle_get_threshold(args: dict[str, Any], context: Any = None) -> GetThresholdOutput:
    inp = GetThresholdInput.model_validate(args)
    ev = context_store.get_threshold(metric_name=inp.metric_name, department=inp.department)
    if not ev:
        return GetThresholdOutput(
            metric_name=inp.metric_name,
            found=False,
            department=inp.department,
        )

    return GetThresholdOutput(
        metric_name=inp.metric_name,
        found=True,
        context_id=ev.context_id,
        operator=ev.operator,
        threshold_value=ev.threshold_value,
        unit=ev.unit,
        rule_summary=ev.rule_summary,
        document_id=ev.document_id,
        department=ev.department,
    )


def handle_get_document_evidence(args: dict[str, Any], context: Any = None) -> GetDocumentEvidenceOutput:
    inp = GetDocumentEvidenceInput.model_validate(args)
    ev = context_store.get_evidence(inp.context_id)
    if not ev:
        return GetDocumentEvidenceOutput(
            context_id=inp.context_id,
            found=False,
        )

    return GetDocumentEvidenceOutput(
        context_id=inp.context_id,
        found=True,
        evidence=_to_evidence_item(ev),
    )


def handle_trace_context_provenance(args: dict[str, Any], context: Any = None) -> TraceContextProvenanceOutput:
    inp = TraceContextProvenanceInput.model_validate(args)
    records: list[ContextProvenanceRecord] = []
    for cid in inp.context_ids:
        prov = context_store.trace_provenance(cid)
        if prov:
            records.append(ContextProvenanceRecord(
                context_id=prov["context_id"],
                document_id=prov["document_id"],
                document_title=prov["document_title"],
                version=prov["version"],
                section=prov["section"],
                verbatim_excerpt=prov["verbatim_excerpt"],
                provenance_hash=prov["provenance_hash"],
                source_uri=prov["source_uri"],
                effective_date=prov["effective_date"],
            ))

    return TraceContextProvenanceOutput(
        total_records=len(records),
        records=records,
    )


# -----------------------------------------------------------------------------
# Tool Registration
# -----------------------------------------------------------------------------

def register_context_tools() -> None:
    """Registers all 6 Context MCP tools into the central registry."""
    tools = [
        (
            MCPToolDefinition(
                tool_name="search_context",
                capability_group="context",
                description="Search Context Fabric for organizational policies, rules, and guidelines.",
                input_schema=SearchContextInput,
                output_schema=SearchContextOutput,
                risk_level=ToolRiskLevel.LOW,
                requires_dataset_scope=False,
            ),
            handle_search_context,
        ),
        (
            MCPToolDefinition(
                tool_name="get_policy",
                capability_group="context",
                description="Retrieve complete policy document and extracted CTX-* items by name or ID.",
                input_schema=GetPolicyInput,
                output_schema=GetPolicyOutput,
                risk_level=ToolRiskLevel.LOW,
                requires_dataset_scope=False,
            ),
            handle_get_policy,
        ),
        (
            MCPToolDefinition(
                tool_name="get_business_definition",
                capability_group="context",
                description="Fetch official calculation formula, definition, or metric standard for a term.",
                input_schema=GetBusinessDefinitionInput,
                output_schema=GetBusinessDefinitionOutput,
                risk_level=ToolRiskLevel.LOW,
                requires_dataset_scope=False,
            ),
            handle_get_business_definition,
        ),
        (
            MCPToolDefinition(
                tool_name="get_threshold",
                capability_group="context",
                description="Fetch authoritative target, limit, or threshold benchmark for a metric.",
                input_schema=GetThresholdInput,
                output_schema=GetThresholdOutput,
                risk_level=ToolRiskLevel.LOW,
                requires_dataset_scope=False,
            ),
            handle_get_threshold,
        ),
        (
            MCPToolDefinition(
                tool_name="get_document_evidence",
                capability_group="context",
                description="Fetch verbatim excerpt, title, and section metadata for a CTX-* context evidence token.",
                input_schema=GetDocumentEvidenceInput,
                output_schema=GetDocumentEvidenceOutput,
                risk_level=ToolRiskLevel.LOW,
                requires_dataset_scope=False,
            ),
            handle_get_document_evidence,
        ),
        (
            MCPToolDefinition(
                tool_name="trace_context_provenance",
                capability_group="context",
                description="Trace cryptographic hash, source document, version, and effective date for CTX-* tokens.",
                input_schema=TraceContextProvenanceInput,
                output_schema=TraceContextProvenanceOutput,
                risk_level=ToolRiskLevel.LOW,
                requires_dataset_scope=False,
            ),
            handle_trace_context_provenance,
        ),
    ]

    for defn, handler in tools:
        mcp_registry.register(defn, handler)
    logger.info(f"[MCPRegistry] Registered {len(tools)} Context MCP tools")
