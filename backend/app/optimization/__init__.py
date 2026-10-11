"""Governed Adaptive Optimization & Policy Recommendation Engine (Phase E).

Enforces the core invariant:
OBSERVE -> EVALUATE -> RECOMMEND -> BENCHMARK -> HUMAN APPROVAL -> ACTIVATE
Never: OBSERVE -> SELF-MODIFY PRODUCTION
"""
from __future__ import annotations

from .contracts import (
    HighviewPolicy,
    OptimizationRecommendation,
    PolicyComparisonResult,
    PolicyStatus,
    RecommendationCategory,
    RiskLevel,
    ShadowEvaluation,
    WorkflowPolicy,
    ToolSelectionPolicy,
    ModelRoutingPolicy,
    EvidencePolicy,
    LatencyPolicy,
    RetryPolicy,
)
from .policy_registry import PolicyRegistry, policy_registry
from .recommendation_engine import OptimizationRecommendationEngine, recommendation_engine
from .comparison import PolicyComparator
from .promotion_gate import PromotionGate
from .shadow_evaluator import ShadowPolicyEvaluator
from .rollback import RollbackManager, RollbackAdvisory, rollback_manager
from .optimizer import GovernedOptimizer, governed_optimizer

__all__ = [
    "HighviewPolicy",
    "OptimizationRecommendation",
    "PolicyComparisonResult",
    "PolicyStatus",
    "RecommendationCategory",
    "RiskLevel",
    "ShadowEvaluation",
    "WorkflowPolicy",
    "ToolSelectionPolicy",
    "ModelRoutingPolicy",
    "EvidencePolicy",
    "LatencyPolicy",
    "RetryPolicy",
    "PolicyRegistry",
    "policy_registry",
    "OptimizationRecommendationEngine",
    "recommendation_engine",
    "PolicyComparator",
    "PromotionGate",
    "ShadowPolicyEvaluator",
    "RollbackManager",
    "RollbackAdvisory",
    "rollback_manager",
    "GovernedOptimizer",
    "governed_optimizer",
]
