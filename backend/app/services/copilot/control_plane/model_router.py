"""Model Router & Escalation Policy (Phase 11.3).

Guarantees:
1. RoutingIntegrity: LLM is invoked ONLY after deterministic tools complete.
2. The AI Council is exceptional, never routine:
   - R0/R1 -> Deterministic / Fast model only (refuses council escalation).
   - R2/R3 -> Single Synthesizer model (Coordinator), with Critic only if conflicting evidence.
   - R4 -> Full Council Deliberation with mandatory Critic audit.
"""
from __future__ import annotations

from typing import Any
from .contracts import (
    ComplexityTier,
    RiskTier,
)


class EscalationPolicy:
    """Governs whether a query qualifies for Critic or AI Council deliberation."""

    @classmethod
    def evaluate_escalation(
        cls,
        risk: RiskTier,
        complexity: ComplexityTier,
        evidence_conflict: bool = False,
        force_council_requested: bool = False,
    ) -> tuple[bool, bool, str]:
        """Returns (critic_required, council_required, rationale)."""
        # Rule 1: R0 and R1 queries NEVER qualify for AI Council even if requested
        if risk in [RiskTier.R0, RiskTier.R1]:
            if force_council_requested:
                return (
                    False,
                    False,
                    f"Council escalation refused: query risk ({risk.value}) is deterministic/descriptive. Handled by tool execution.",
                )
            return False, False, "Deterministic or fast-path tool execution; no council required."

        # Rule 2: R4 queries ALWAYS mandate Council + Critic review
        if risk == RiskTier.R4:
            return (
                True,
                True,
                "Mandatory AI Council deliberation and DeepSeek critic review for high-impact decision support (R4).",
            )

        # Rule 3: R2/R3 with conflicting evidence requires Critic, but not full Council
        if evidence_conflict:
            return (
                True,
                False,
                "Conflicting evidence detected across historical sources; engaging critic audit.",
            )

        # Rule 4: R3 with high complexity (C3) and user council request may escalate
        if risk == RiskTier.R3 and complexity == ComplexityTier.C3 and force_council_requested:
            return (
                True,
                True,
                "High complexity (C3) operational recommendation with user council request approved.",
            )

        # Standard R2 / R3 single-synthesizer path
        return False, False, "Standard coordinator synthesis; council escalation unnecessary."


class ModelRouter:
    """Assigns the exact execution model based on risk, complexity, and capability."""

    @classmethod
    def select_route(
        cls,
        risk: RiskTier,
        complexity: ComplexityTier,
        needs_llm: bool,
        evidence_conflict: bool = False,
        force_council: bool = False,
    ) -> tuple[str, bool, bool, str]:
        """Returns (model_route, critic_required, council_required, rationale).

        model_route options:
        - "deterministic"
        - "fast_model"
        - "coordinator"
        - "council_war_room"
        """
        # 1. Deterministic path
        if not needs_llm:
            return "deterministic", False, False, "100% deterministic mathematical execution. No LLM used."

        # 2. Evaluate escalation policy
        critic_req, council_req, rationale = EscalationPolicy.evaluate_escalation(
            risk=risk,
            complexity=complexity,
            evidence_conflict=evidence_conflict,
            force_council_requested=force_council,
        )

        if council_req:
            return "council_war_room", critic_req, True, rationale

        # 3. Simple descriptive text formatting -> Fast model
        if risk == RiskTier.R1 or (risk == RiskTier.R2 and complexity == ComplexityTier.C0):
            msg = f"{rationale} " if force_council else ""
            return "fast_model", critic_req, False, f"{msg}Assigned to fast model (Qwen 3.5 2B / Phi) for rapid response synthesis."

        # 4. Standard Coordinator model
        return "coordinator", critic_req, False, rationale
