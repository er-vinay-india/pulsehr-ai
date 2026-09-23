"""Pluggable Decision Engine package for PulseHR AI Copilot."""

from .base import DecisionEngine, DecisionResult
from .rule_engine import RuleDecisionEngine
from .embedding_engine import EmbeddingDecisionEngine
from .factory import get_decision_engine

__all__ = [
    "DecisionEngine",
    "DecisionResult",
    "RuleDecisionEngine",
    "EmbeddingDecisionEngine",
    "get_decision_engine",
]
