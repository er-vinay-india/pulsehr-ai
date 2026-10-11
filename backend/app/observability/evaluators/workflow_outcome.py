"""WorkflowOutcomeEvaluator: Calculates outcome quality and weighted RuntimeQualityScore (Phase D)."""
from __future__ import annotations

import logging
from typing import Any
from ..contracts import RuntimeQualityScore, WorkflowOutcomeEvaluation

logger = logging.getLogger(__name__)


class WorkflowOutcomeEvaluator:
    """Evaluates final workflow completion status, satisfaction, and composite runtime score."""

    @classmethod
    def evaluate(
        cls,
        workflow_status: str,
        grounding_rate: float,
        intent_alignment_score: float,
        tool_precision: float,
        is_latency_compliant: bool,
        unnecessary_steps: int = 0,
    ) -> tuple[WorkflowOutcomeEvaluation, RuntimeQualityScore]:
        completed = (workflow_status == "COMPLETED")
        partial = (workflow_status == "PARTIAL")
        denied = (workflow_status == "DENIED")
        review_required = (workflow_status == "REVIEW_REQUIRED")
        failed_safe = (workflow_status == "FAILED_SAFE")

        evidence_grounded = (grounding_rate >= 0.99)
        satisfied = completed and evidence_grounded

        # Overall workflow completion score
        if completed:
            wf_score = 1.0
        elif review_required or denied:
            wf_score = 0.8  # Correctly halted by policy
        elif partial:
            wf_score = 0.5
        elif failed_safe:
            wf_score = 0.4
        else:
            wf_score = 0.0

        if unnecessary_steps > 0:
            wf_score = max(0.1, wf_score - (unnecessary_steps * 0.1))

        outcome_eval = WorkflowOutcomeEvaluation(
            status=workflow_status,
            completed=completed,
            partial=partial,
            denied=denied,
            review_required=review_required,
            failed_safe=failed_safe,
            evidence_grounded=evidence_grounded,
            user_request_satisfied=satisfied,
            unnecessary_steps=unnecessary_steps,
            overall_score=round(wf_score, 3),
        )

        # Governance score: 1.0 if completed or properly denied/reviewed
        gov_score = 1.0 if (completed or denied or review_required) else 0.7
        lat_score = 1.0 if is_latency_compliant else 0.6
        model_score = 1.0

        quality_score = RuntimeQualityScore.calculate(
            grounding=grounding_rate,
            intent_alignment=intent_alignment_score,
            tool_efficiency=tool_precision,
            workflow_completion=wf_score,
            governance_correctness=gov_score,
            latency_efficiency=lat_score,
            model_routing_efficiency=model_score,
        )

        return outcome_eval, quality_score
