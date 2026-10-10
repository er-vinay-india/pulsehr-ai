"""Analytical Opportunity Planner Package.

Translates ingestion semantic catalog into prioritized, domain-isolated
analytical opportunities and empirical evidence nodes.
"""
from .contracts import (
    AnalyticalOpportunity,
    AnalyticalOpportunityScore,
    AnalyticalOpportunityType,
    RelationshipReductionTracker,
)
from .executor import AnalyticalOpportunityExecutor
from .planner import AnalyticalOpportunityPlanner

__all__ = [
    "AnalyticalOpportunity",
    "AnalyticalOpportunityScore",
    "AnalyticalOpportunityType",
    "AnalyticalOpportunityPlanner",
    "AnalyticalOpportunityExecutor",
    "RelationshipReductionTracker",
]
