"""VerifyClaimNode: Validates factual claims against Evidence and Governance MCP."""
from __future__ import annotations

import logging
from typing import Any
from ...mcp import MCPToolRequest, mcp_gateway
from ..guards import CausalLanguageGuard
from ..state import HighviewAgentState

logger = logging.getLogger(__name__)


def verify_claim_node(state: HighviewAgentState) -> HighviewAgentState:
    """Verifies candidate claims using Evidence MCP and sanitizes causal overreach."""
    dataset_id = state.dataset_id or 99767
    caller = state.active_filters.get("caller", "hriday")

    # Generate or extract candidate claim if none present
    entity = state.selected_entities[0] if state.selected_entities else "segment"
    measure = state.selected_measures[0] if state.selected_measures else "metric"

    candidate_claim = f"Significant variance in {measure} is observed across {entity}s."
    if state.intent == "MULTI_STEP_ANALYSIS":
        candidate_claim = f"Attendance variation across {entity}s is associated with leave patterns."

    # 1. Sanitize causal language (e.g. 'caused' -> 'was associated with')
    sanitized_claim, was_modified = CausalLanguageGuard.sanitize_claim(
        candidate_claim,
        is_counterfactual_verified=False,
    )
    if was_modified:
        logger.info(f"[VerifyClaimNode] Sanitized causal language in claim: '{sanitized_claim}'")

    # 2. Verify against Evidence MCP
    evid_req = MCPToolRequest(
        tool_name="verify_claim",
        dataset_id=dataset_id,
        arguments={
            "dataset_id": dataset_id,
            "claim_text": sanitized_claim,
        },
        caller=caller,
    )
    evid_res = mcp_gateway.execute(evid_req)

    # 3. Check governance entitlement against Governance MCP
    gov_req = MCPToolRequest(
        tool_name="check_claim",
        dataset_id=dataset_id,
        arguments={
            "claim_text": sanitized_claim,
            "available_evidence_types": ["CORRELATION", "AGGREGATION", "RAW_RECORD"],
        },
        caller=caller,
    )
    gov_res = mcp_gateway.execute(gov_req)

    is_verified = (
        evid_res.success
        and evid_res.result.get("verified", True)
        and gov_res.success
        and gov_res.result.get("is_entitled", True)
    )

    if is_verified:
        if sanitized_claim not in state.verified_claims:
            state.verified_claims.append(sanitized_claim)
        logger.debug(f"[VerifyClaimNode] Claim verified: '{sanitized_claim}'")
    else:
        if sanitized_claim not in state.rejected_claims:
            state.rejected_claims.append(sanitized_claim)
        logger.warning(f"[VerifyClaimNode] Claim rejected or refuted: '{sanitized_claim}'")

    return state
