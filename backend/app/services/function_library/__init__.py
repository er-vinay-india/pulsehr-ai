"""Analytical Function & Business Jargon Library.

Permanent, token-optimized catalog of mathematical functions, persona jargon translations,
deterministic business impact rules, and visualization recommendations.
"""

from .base import (
    BaseAnalyticalFunction,
    AnalyticalFunctionMetadata,
    FunctionCategory,
    ImpactType,
    ImpactSeverity,
    JargonMapping,
    BusinessImpactRule,
    BusinessImpactAssessment,
    FunctionPreconditions,
    VisualGrammarRecommendation,
)
from .registry import AnalyticalFunctionRegistry, register_function
from .storage import FunctionLibraryStorage

__all__ = [
    "BaseAnalyticalFunction",
    "AnalyticalFunctionMetadata",
    "FunctionCategory",
    "ImpactType",
    "ImpactSeverity",
    "JargonMapping",
    "BusinessImpactRule",
    "BusinessImpactAssessment",
    "FunctionPreconditions",
    "VisualGrammarRecommendation",
    "AnalyticalFunctionRegistry",
    "register_function",
    "FunctionLibraryStorage",
]
