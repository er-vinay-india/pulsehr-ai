"""GovernanceHealthEvaluator: Aggregates governance checks, isolation, and approvals (Phase D)."""
from __future__ import annotations

import logging
from typing import Any
from ..contracts import GovernanceHealthSummary

logger = logging.getLogger(__name__)


class GovernanceHealthEvaluator:
    """Aggregates governance metrics across MCP calls and LangGraph node executions."""

    @classmethod
    def evaluate(
        cls,
        tool_history: list[dict[str, Any]],
        approvals: list[dict[str, Any]],
        workflow_status: str,
    ) -> GovernanceHealthSummary:
        checks = 0
        denials = 0
        flags = 0
        scope_denials = 0
        claim_denials = 0
        scenario_denials = 0

        for t in tool_history:
            t_name = t.get("tool_name", "")
            status = t.get("governance_status", "PASS")

            if "check_" in t_name:
                checks += 1

            if status in ("DENIED", "REJECTED") or not t.get("success", True):
                denials += 1
                if "dataset_scope" in t_name:
                    scope_denials += 1
                elif "claim" in t_name:
                    claim_denials += 1
                elif "scenario" in t_name:
                    scenario_denials += 1

            if status == "FLAGGED":
                flags += 1

        appr_req = len(approvals)
        appr_granted = sum(1 for a in approvals if a.get("granted") is True)
        appr_rejected = sum(1 for a in approvals if a.get("granted") is False)

        failed_safe = 1 if workflow_status == "FAILED_SAFE" else 0
        if workflow_status == "DENIED":
            denials += 1

        return GovernanceHealthSummary(
            governance_checks=checks,
            governance_denials=denials,
            governance_flags=flags,
            dataset_scope_denials=scope_denials,
            claim_entitlement_denials=claim_denials,
            scenario_entitlement_denials=scenario_denials,
            approval_requested=appr_req,
            approval_granted=appr_granted,
            approval_rejected=appr_rejected,
            failed_safe_count=failed_safe,
        )
