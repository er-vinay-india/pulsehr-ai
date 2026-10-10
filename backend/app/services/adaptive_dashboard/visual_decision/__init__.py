"""Visual Decision Intelligence Package.

Analytical Intent -> Visual Decision layer for Highview Adaptive Dashboard.
"""
from .contracts import (
    AnalyticalIntent,
    AudienceType,
    ChartSuitabilityScore,
    ChartType,
    MetricSemantics,
    VisualDecisionAudit,
    VisualQuestion,
)
from .intent_classifier import AnalyticalIntentClassifier
from .question_builder import VisualQuestionBuilder
from .suitability_matrix import CHART_SUITABILITY_MATRIX
from .suitability_ranker import ChartSuitabilityRanker
from .semantic_validator import VisualSemanticValidator
from .archetypes import ARCHETYPE_LIBRARY, VisualArchetype
from .engine import VisualDecisionEngine

__all__ = [
    "AnalyticalIntent",
    "AudienceType",
    "ChartSuitabilityScore",
    "ChartType",
    "MetricSemantics",
    "VisualDecisionAudit",
    "VisualQuestion",
    "AnalyticalIntentClassifier",
    "VisualQuestionBuilder",
    "CHART_SUITABILITY_MATRIX",
    "ChartSuitabilityRanker",
    "VisualSemanticValidator",
    "ARCHETYPE_LIBRARY",
    "VisualArchetype",
    "VisualDecisionEngine",
]
