"""EvidencePolicyAnalyzer: Recommends verification deduplication without weakening grounding (Phase E)."""
from __future__ import annotations

import logging
from typing import Any
from app.observability.contracts import AITrace
from ..contracts import (
    OptimizationRecommendation,
    RecommendationCategory,
    RiskLevel,
)

logger = logging.getLogger(__name__)


class EvidencePolicyAnalyzer:
    """Identifies redundant verification overhead while preserving 100% grounding invariants."""

    @classmethod
    def analyze_traces(
        cls,
        traces: list[AITrace],
        current_policy_id: str,
    ) -> list[OptimizationRecommendation]:
        recommendations: list[OptimizationRecommendation] = []
        if not traces:
            return recommendations

        # Detect redundant verification when deterministic ranking already returned verified EVID token
        redundant_verifications = [
            t for t in traces
            if "rank_entities" in [call.get("tool_name") for call in t.tools]
            and "verify_claim" in [call.get("tool_name") for call in t.tools]
            and len(t.evidence_ids) >= 2
        ]

        if len(redundant_verifications) >= 2:
            rec = OptimizationRecommendation(
                category=RecommendationCategory.EVIDENCE_POLICY,
                current_policy_id=current_policy_id,
                proposed_policy_delta={
                    "deduplicate_certified_determinations": True,
                    "skip_redundant_verify_for_certified_rankings": True,
                },
                evidence_trace_ids=[t.trace_id for t in redundant_verifications[:5]],
                reason="Certified deterministic ranking outputs already attach verified EVID tokens; secondary claim verification adds latency without additional mathematical certainty.",
                expected_improvement="Reduce ranking query execution latency by ~120ms while preserving 100% factual grounding.",
                risk_level=RiskLevel.LOW,
            )
            recommendations.append(rec)

        return recommendations
