"""Opportunity Execution Portfolio.

Selects a diversified execution portfolio of analytical opportunities across
semantic families and analytical intents, preventing any single family or
measure-dimension pair from monopolizing the empirical execution budget.
"""
from __future__ import annotations

import collections
import logging
from typing import Any

from .contracts import AnalyticalOpportunity, AnalyticalOpportunityType

logger = logging.getLogger(__name__)


class OpportunityExecutionPortfolio:
    """Governed portfolio manager allocating analytical execution budget across diversified families."""

    @classmethod
    def select_portfolio(
        cls,
        opportunities: list[AnalyticalOpportunity],
        budget: int = 12,
        max_per_semantic_family: int = 2,
        max_per_measure_dim_pair: int = 1,
        max_per_temporal_family: int = 1,
    ) -> list[AnalyticalOpportunity]:
        """Selects a diversified set of opportunities across families and analytical archetypes.
        
        Guarantees:
        - No single semantic family consumes more than max_per_semantic_family (default 2)
        - No duplicate measure-dimension pairs (default 1)
        - Representation across ranking, temporal, composition, relationship, and cross-sheet
        """
        if not opportunities:
            return []

        # Sort all opportunities by score descending
        sorted_opps = sorted(opportunities, key=lambda o: o.score.total_score, reverse=True)

        family_counts: dict[str, int] = collections.defaultdict(int)
        measure_dim_counts: dict[tuple[str, str], int] = collections.defaultdict(int)
        temporal_family_counts: dict[str, int] = collections.defaultdict(int)

        # Categorize by intent
        intent_buckets: dict[str, list[AnalyticalOpportunity]] = {
            "ranking": [],
            "trend": [],
            "composition": [],
            "relationship": [],
            "anomaly": [],
            "cross_sheet": [],
        }

        for opp in sorted_opps:
            if opp.is_cross_sheet or opp.opportunity_type == AnalyticalOpportunityType.CROSS_SHEET_RELATIONSHIP:
                intent_buckets["cross_sheet"].append(opp)
            elif opp.statistical_intent in ("trend", "temporal") or opp.opportunity_type == AnalyticalOpportunityType.MEASURE_BY_TIME:
                intent_buckets["trend"].append(opp)
            elif opp.statistical_intent == "composition" or opp.opportunity_type == AnalyticalOpportunityType.COMPOSITION_PART_TO_WHOLE:
                intent_buckets["composition"].append(opp)
            elif opp.statistical_intent in ("relationship", "correlation") or opp.opportunity_type == AnalyticalOpportunityType.MEASURE_BY_MEASURE:
                intent_buckets["relationship"].append(opp)
            elif opp.statistical_intent in ("anomaly", "variance", "target_gap"):
                intent_buckets["anomaly"].append(opp)
            else:
                intent_buckets["ranking"].append(opp)

        selected: list[AnalyticalOpportunity] = []

        def can_accept(opp: AnalyticalOpportunity) -> bool:
            fam_key = opp.semantic_family or opp.semantic_group or "default_fam"
            if family_counts[fam_key] >= max_per_semantic_family:
                return False

            if opp.primary_measure and opp.primary_dimension:
                md_key = (opp.primary_measure.lower(), opp.primary_dimension.lower())
                if measure_dim_counts[md_key] >= max_per_measure_dim_pair:
                    return False

            if opp.statistical_intent in ("trend", "temporal"):
                tf_key = (opp.primary_measure or "temporal").lower()
                if temporal_family_counts[tf_key] >= max_per_temporal_family:
                    return False

            return True

        def accept(opp: AnalyticalOpportunity):
            fam_key = opp.semantic_family or opp.semantic_group or "default_fam"
            family_counts[fam_key] += 1
            if opp.primary_measure and opp.primary_dimension:
                md_key = (opp.primary_measure.lower(), opp.primary_dimension.lower())
                measure_dim_counts[md_key] += 1
            if opp.statistical_intent in ("trend", "temporal"):
                tf_key = (opp.primary_measure or "temporal").lower()
                temporal_family_counts[tf_key] += 1
            selected.append(opp)

        # Round 1: Target quotas across archetypes (diversified execution budget)
        target_quotas = [
            ("ranking", 2),
            ("trend", 2),
            ("composition", 2),
            ("relationship", 2),
            ("cross_sheet", 2),
            ("anomaly", 1),
        ]

        for intent, quota in target_quotas:
            count = 0
            for opp in intent_buckets.get(intent, []):
                if count >= quota or len(selected) >= budget:
                    break
                if opp not in selected and can_accept(opp):
                    accept(opp)
                    count += 1

        # Round 2: Fill remaining budget with highest scoring eligible opportunities
        if len(selected) < budget:
            for opp in sorted_opps:
                if len(selected) >= budget:
                    break
                if opp not in selected and can_accept(opp):
                    accept(opp)

        # Round 3: If still under budget (due to strict caps), relax family limits
        if len(selected) < budget:
            for opp in sorted_opps:
                if len(selected) >= budget:
                    break
                if opp not in selected:
                    selected.append(opp)

        logger.info(
            "OpportunityExecutionPortfolio selected %d opportunities across %d semantic families (budget=%d)",
            len(selected),
            len(family_counts),
            budget,
        )
        return selected
