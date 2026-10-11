"""Workflow and tool latency budget specifications and SLA enforcement (Phase D)."""
from __future__ import annotations

import logging
from typing import Any
from pydantic import BaseModel, ConfigDict, Field

logger = logging.getLogger(__name__)


class WorkflowLatencySpec(BaseModel):
    """SLA targets for a workflow type."""
    model_config = ConfigDict(extra="ignore")

    workflow_name: str
    p50_target_ms: float
    p95_target_ms: float


class ToolLatencySpec(BaseModel):
    """SLA target for an individual MCP tool or capability group."""
    model_config = ConfigDict(extra="ignore")

    tool_group_or_name: str
    max_budget_ms: float


class WorkflowLatencyBudget:
    """Central registry of latency targets and SLA violation detector."""

    WORKFLOW_BUDGETS: dict[str, WorkflowLatencySpec] = {
        "quick_answer": WorkflowLatencySpec(
            workflow_name="quick_answer",
            p50_target_ms=500.0,
            p95_target_ms=1500.0,
        ),
        "analytical_investigation": WorkflowLatencySpec(
            workflow_name="analytical_investigation",
            p50_target_ms=2500.0,
            p95_target_ms=6000.0,
        ),
        "scenario_analysis": WorkflowLatencySpec(
            workflow_name="scenario_analysis",
            p50_target_ms=3000.0,
            p95_target_ms=8000.0,
        ),
        "presentation_creation": WorkflowLatencySpec(
            workflow_name="presentation_creation",
            p50_target_ms=8000.0,
            p95_target_ms=20000.0,
        ),
    }

    TOOL_BUDGETS: dict[str, float] = {
        "dataset": 100.0,
        "analytics": 300.0,
        "evidence": 300.0,
        "governance": 100.0,
        "scenario": 500.0,
        "presentation": 2500.0,
    }

    @classmethod
    def check_workflow_latency(
        cls,
        workflow_name: str,
        latency_ms: float,
    ) -> tuple[bool, str | None]:
        """Validates workflow latency against P95 SLA target.

        Returns (is_compliant, violation_message).
        """
        spec = cls.WORKFLOW_BUDGETS.get(workflow_name.lower())
        if not spec:
            # Fallback default budget
            if latency_ms > 10000.0:
                return False, f"Workflow '{workflow_name}' exceeded fallback SLA threshold (latency: {latency_ms:.1f}ms > 10000ms)"
            return True, None

        if latency_ms > spec.p95_target_ms:
            return False, (
                f"SLA violation: Workflow '{workflow_name}' latency {latency_ms:.1f}ms "
                f"exceeded P95 target {spec.p95_target_ms:.1f}ms"
            )
        return True, None

    @classmethod
    def check_tool_latency(
        cls,
        tool_name: str,
        capability_group: str,
        latency_ms: float,
    ) -> tuple[bool, str | None]:
        """Validates tool latency against capability group budget."""
        target = cls.TOOL_BUDGETS.get(capability_group.lower(), 500.0)
        if latency_ms > target:
            return False, (
                f"Tool SLA violation: Tool '{tool_name}' in group '{capability_group}' "
                f"took {latency_ms:.1f}ms (target <= {target:.1f}ms)"
            )
        return True, None
