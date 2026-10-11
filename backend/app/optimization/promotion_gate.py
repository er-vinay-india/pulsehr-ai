"""PromotionGate: Enforces safety invariants before human review eligibility (Phase E)."""
from __future__ import annotations

import logging
from typing import Any
from .contracts import PolicyComparisonResult

logger = logging.getLogger(__name__)


class PromotionGate:
    """Evaluates whether a candidate policy satisfies strict eligibility criteria for promotion."""

    INTENT_TOLERANCE = 0.02
    WORKFLOW_TOLERANCE = 0.02

    @classmethod
    def evaluate_eligibility(cls, comparison: PolicyComparisonResult) -> tuple[bool, str]:
        """Validates that candidate passes all hard safety gates and performance baselines.

        Returns (is_eligible_for_promotion, decision_rationale).
        """
        # 1. Hard Safety Gates MUST be 100% PASS
        if not comparison.hard_safety_gates_passed:
            reasons = "; ".join(comparison.regressions)
            logger.warning(f"[PromotionGate] Candidate '{comparison.candidate_policy_id}' rejected by hard safety gate: {reasons}")
            return False, f"Hard safety gate failed: {reasons}"

        # 2. Grounding MUST NOT regress
        if comparison.grounding_delta < 0.0:
            return False, f"Grounding rate regressed by {abs(comparison.grounding_delta) * 100:.1f}%. Grounding must remain >= baseline."

        # 3. Check for disqualifying regressions
        disqualifying = [r for r in comparison.regressions if "HARD SAFETY" in r or "Grounding" in r]
        if disqualifying:
            return False, f"Disqualifying regressions detected: {'; '.join(disqualifying)}"

        if comparison.recommendation == "REJECT":
            return False, comparison.rationale

        logger.info(f"[PromotionGate] Candidate '{comparison.candidate_policy_id}' passed safety gate. Eligible for human review.")
        return True, "Candidate policy passed all safety criteria and is eligible for human review."
