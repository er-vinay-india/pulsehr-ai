"""Execution Budget Manager (Phase 11.5).

Enforces ModelBudgetIntegrity:
1. Defines runtime ceilings (LLM calls, tool calls, critic passes, latency targets) per (Risk, Complexity) tier.
2. Audits resource consumption and logs compliance in the ControlPlaneAuditRecord.
"""
from __future__ import annotations

from typing import Any
from .contracts import (
    ComplexityTier,
    ExecutionBudget,
    RiskTier,
)


class ExecutionBudgetManager:
    """Calculates and validates runtime resource budgets."""

    @classmethod
    def get_budget(cls, risk: RiskTier, complexity: ComplexityTier) -> ExecutionBudget:
        """Returns the policy-mandated execution budget for a (Risk, Complexity) combination."""
        # 1. R0: Deterministic lookup (<250ms, zero LLMs)
        if risk == RiskTier.R0:
            return ExecutionBudget(
                risk_tier=risk,
                complexity_tier=complexity,
                max_llm_calls=0,
                max_tool_calls=2,
                critic_required=False,
                council_required=False,
                target_latency_ms=100.0,
                max_latency_ms=250.0,
            )

        # 2. R1: Descriptive analytics (<1.5s)
        if risk == RiskTier.R1:
            return ExecutionBudget(
                risk_tier=risk,
                complexity_tier=complexity,
                max_llm_calls=1,
                max_tool_calls=4,
                critic_required=False,
                council_required=False,
                target_latency_ms=800.0,
                max_latency_ms=1500.0,
            )

        # 3. R2: Interpretation (<3.0s, optional critic if C3)
        if risk == RiskTier.R2:
            is_c3 = complexity == ComplexityTier.C3
            return ExecutionBudget(
                risk_tier=risk,
                complexity_tier=complexity,
                max_llm_calls=2,
                max_tool_calls=8 if is_c3 else 6,
                critic_required=is_c3,
                council_required=False,
                target_latency_ms=2500.0,
                max_latency_ms=4500.0 if is_c3 else 3000.0,
            )

        # 4. R3: Operational Recommendation (<5.0s)
        if risk == RiskTier.R3:
            return ExecutionBudget(
                risk_tier=risk,
                complexity_tier=complexity,
                max_llm_calls=2,
                max_tool_calls=10,
                critic_required=False,
                council_required=False,
                target_latency_ms=3500.0,
                max_latency_ms=5000.0,
            )

        # 5. R4: High-Impact Decision Support (<8.0s, Council + Critic mandatory)
        return ExecutionBudget(
            risk_tier=risk,
            complexity_tier=complexity,
            max_llm_calls=4,
            max_tool_calls=12,
            critic_required=True,
            council_required=True,
            target_latency_ms=6000.0,
            max_latency_ms=8000.0,
        )

    @classmethod
    def evaluate_consumption(
        cls,
        budget: ExecutionBudget,
        actual_llm_calls: int,
        actual_tool_calls: int,
        actual_latency_ms: float,
    ) -> tuple[str, str]:
        """Evaluates actual consumption against budget. Returns (status, reason)."""
        if actual_llm_calls > budget.max_llm_calls:
            return (
                "EXCEEDED",
                f"LLM call ceiling violated: used {actual_llm_calls}, budget allows {budget.max_llm_calls}.",
            )

        if actual_tool_calls > budget.max_tool_calls:
            return (
                "EXCEEDED",
                f"Tool call ceiling violated: executed {actual_tool_calls}, budget allows {budget.max_tool_calls}.",
            )

        if actual_latency_ms > budget.max_latency_ms:
            return (
                "EXCEEDED",
                f"SLA latency threshold exceeded: took {actual_latency_ms:.1f}ms, budget limit {budget.max_latency_ms:.1f}ms.",
            )

        return "PASS", "Resource consumption strictly within budget ceiling."
