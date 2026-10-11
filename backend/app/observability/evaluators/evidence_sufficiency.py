"""EvidenceQualityEvaluator: Evaluates multi-dimensional evidence sufficiency (Phase D)."""
from __future__ import annotations

import logging
from typing import Any
from ..contracts import EvidenceQualityEvaluation

logger = logging.getLogger(__name__)


class EvidenceQualityEvaluator:
    """Evaluates whether gathered evidence count and dimensions satisfy the analytical goal."""

    @classmethod
    def evaluate(
        cls,
        intent: str,
        evidence_ids: list[str],
        tools_called: list[str],
    ) -> EvidenceQualityEvaluation:
        evid_count = len(evidence_ids)
        evid_types: list[str] = []
        missing: list[str] = []

        if any("rank" in t for t in tools_called):
            evid_types.append("RANKING")
        if any("compare" in t for t in tools_called):
            evid_types.append("COMPARISON")
        if any("relationship" in t or "correlat" in t for t in tools_called):
            evid_types.append("CORRELATION")
        if any("trend" in t for t in tools_called):
            evid_types.append("TEMPORAL")
        if any("counterfactual" in t or "scenario" in t for t in tools_called):
            evid_types.append("SCENARIO")

        score = 1.0

        if intent == "MULTI_STEP_ANALYSIS":
            if "CORRELATION" not in evid_types:
                missing.append("CORRELATION")
                score -= 0.4
            if "COMPARISON" not in evid_types and "RANKING" not in evid_types:
                missing.append("COMPARISON")
                score -= 0.4
            if evid_count < 1:
                score -= 0.2

        elif intent in ("RANKING", "COMPARISON", "TREND", "RELATIONSHIP"):
            if evid_count < 1:
                missing.append("PRIMARY_EVIDENCE")
                score -= 0.5

        sufficiency_score = max(0.0, min(1.0, round(score, 3)))
        is_sufficient = (len(missing) == 0) and (evid_count >= 1 or intent == "DATA_LOOKUP")

        return EvidenceQualityEvaluation(
            evidence_count=evid_count,
            evidence_types=evid_types,
            evidence_sufficiency_score=sufficiency_score,
            missing_evidence_types=missing,
            is_sufficient=is_sufficient,
        )
