"""Insight Ranking Engine for Prioritizing Governed Evidence.

Ranks evidence nodes deterministically using multi-factor scoring:
- Business Impact (0.30)
- Statistical Strength (0.25)
- Magnitude / Effect Size (0.20)
- Actionability (0.15)
- Confidence (0.10)
"""
from __future__ import annotations

import math
from typing import Any
from pydantic import BaseModel, ConfigDict, Field

from .evidence_graph import EvidenceGraph, EvidenceItem


class RankedInsight(BaseModel):
    """Prioritized insight bound to an authoritative EvidenceItem."""
    model_config = ConfigDict(extra="forbid")

    rank: int
    evidence: EvidenceItem
    composite_score: float
    score_breakdown: dict[str, float]
    suggested_role: str = "supporting"  # "hero", "primary_comparator", "supporting", "context"


class InsightRankingEngine:
    """Deterministic ranking engine evaluating evidence importance for leadership reporting."""

    def __init__(
        self,
        w_impact: float = 0.30,
        w_stat: float = 0.25,
        w_magnitude: float = 0.20,
        w_action: float = 0.15,
        w_confidence: float = 0.10,
    ):
        self.w_impact = w_impact
        self.w_stat = w_stat
        self.w_magnitude = w_magnitude
        self.w_action = w_action
        self.w_confidence = w_confidence

    def score_evidence(self, item: EvidenceItem) -> tuple[float, dict[str, float]]:
        """Calculates multi-factor score for an individual EvidenceItem."""
        # 1. Business Impact (0.0 to 1.0)
        impact = 0.50
        claim = item.claim_type
        if claim in ("capacity_gap", "backlog_aging", "target_gap"):
            impact = 0.95
        elif claim == "segment_difference":
            impact = 0.85
        elif claim == "trend_change":
            impact = 0.80
        elif claim in ("concentration", "distribution_skew"):
            impact = 0.70
        elif claim == "retention_decay":
            impact = 0.75

        # 2. Statistical Strength (0.0 to 1.0)
        stat = 0.50
        if item.population >= 50:
            stat = 1.0
        elif item.population >= 25:
            stat = 0.85
        elif item.population >= 10:
            stat = 0.65
        elif item.population > 0:
            stat = 0.40
        else:
            stat = 0.60  # Aggregate ledger with unstated discrete pop

        # 3. Magnitude / Effect Size (0.0 to 1.0)
        magnitude = 0.40
        if item.difference_pct is not None:
            abs_diff = abs(item.difference_pct)
            if abs_diff >= 40.0:
                magnitude = 1.0
            elif abs_diff >= 20.0:
                magnitude = 0.80
            elif abs_diff >= 10.0:
                magnitude = 0.60
            elif abs_diff > 0.0:
                magnitude = 0.40
        elif item.value is not None and item.comparison_value is not None and item.comparison_value != 0:
            ratio = abs(float(item.value) - float(item.comparison_value)) / abs(float(item.comparison_value))
            magnitude = min(1.0, max(0.3, ratio))

        # 4. Actionability (0.0 to 1.0)
        action = 0.60
        if item.limitations:
            action -= 0.15 * min(2, len(item.limitations))
        if claim in ("capacity_gap", "target_gap", "segment_difference"):
            action += 0.30
        action = max(0.1, min(1.0, action))

        # 5. Confidence (0.0 to 1.0)
        conf = 0.50
        if item.confidence == "HIGH":
            conf = 1.0
        elif item.confidence == "MEDIUM":
            conf = 0.70
        elif item.confidence == "LOW":
            conf = 0.35

        composite = (
            self.w_impact * impact
            + self.w_stat * stat
            + self.w_magnitude * magnitude
            + self.w_action * action
            + self.w_confidence * conf
        )
        composite = round(composite, 4)

        breakdown = {
            "business_impact": round(impact, 2),
            "statistical_strength": round(stat, 2),
            "magnitude": round(magnitude, 2),
            "actionability": round(action, 2),
            "confidence": round(conf, 2),
        }
        return composite, breakdown

    def rank_graph(self, graph: EvidenceGraph, top_n: int = 12) -> list[RankedInsight]:
        """Ranks all evidence nodes in an EvidenceGraph and returns top_n ranked insights."""
        scored: list[tuple[float, dict[str, float], EvidenceItem]] = []

        for item in graph.nodes:
            score, breakdown = self.score_evidence(item)
            scored.append((score, breakdown, item))

        # Sort descending by composite score, secondary sort by population
        scored.sort(key=lambda x: (x[0], x[2].population), reverse=True)

        ranked: list[RankedInsight] = []
        for rank_idx, (score, breakdown, item) in enumerate(scored[:top_n], start=1):
            suggested_role = "supporting"
            if rank_idx == 1:
                suggested_role = "hero"
            elif rank_idx == 2:
                suggested_role = "primary_comparator"
            elif rank_idx <= 4:
                suggested_role = "supporting"
            else:
                suggested_role = "context"

            ranked.append(
                RankedInsight(
                    rank=rank_idx,
                    evidence=item,
                    composite_score=score,
                    score_breakdown=breakdown,
                    suggested_role=suggested_role,
                )
            )

        return ranked
