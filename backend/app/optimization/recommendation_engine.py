"""Recommendation Engine for Governed Adaptive Optimization (Phase E).

Aggregates historical traces from Phase D AITraceStore and coordinates all 6
analyzers to emit structured OptimizationRecommendations.
"""
from __future__ import annotations

import logging
import threading
from typing import Any
from app.observability.contracts import AITrace
from app.observability.trace_store import TraceStore, trace_store
from .contracts import OptimizationRecommendation, RecommendationCategory
from .policy_registry import PolicyRegistry, policy_registry
from .analyzers import (
    OverOrchestrationDetector,
    ModelRoutingAnalyzer,
    ToolEfficiencyAnalyzer,
    EvidencePolicyAnalyzer,
    RetryPolicyAnalyzer,
    LatencyAnalyzer,
)

logger = logging.getLogger(__name__)


class OptimizationRecommendationEngine:
    """Coordinates deterministic trace analysis to generate governed optimization recommendations."""

    def __init__(
        self,
        trace_storage: TraceStore | None = None,
        registry: PolicyRegistry | None = None,
    ):
        self._lock = threading.Lock()
        self._trace_store = trace_storage or trace_store
        self._registry = registry or policy_registry
        self._recommendations: dict[str, OptimizationRecommendation] = {}

    def generate_recommendations(
        self,
        traces: list[AITrace] | None = None,
    ) -> list[OptimizationRecommendation]:
        """Runs all 6 analyzers against current traces and registers recommendations."""
        active_policy = self._registry.get_active_policy()
        target_traces = traces if traces is not None else self._trace_store.list_traces()

        if not target_traces:
            logger.info("[RecommendationEngine] No traces available to analyze.")
            return []

        current_policy_id = active_policy.policy_id
        emitted: list[OptimizationRecommendation] = []

        # 1. Workflow efficiency / over-orchestration
        emitted.extend(OverOrchestrationDetector.analyze_traces(target_traces, current_policy_id))

        # 2. Model routing / fallbacks / slow primaries
        emitted.extend(ModelRoutingAnalyzer.analyze_traces(target_traces, current_policy_id))

        # 3. Tool efficiency / duplicates / parallel execution
        emitted.extend(ToolEfficiencyAnalyzer.analyze_traces(target_traces, current_policy_id))

        # 4. Evidence policy / certified ranking redundancy
        emitted.extend(EvidencePolicyAnalyzer.analyze_traces(target_traces, current_policy_id))

        # 5. Retry policy / early fallback
        emitted.extend(RetryPolicyAnalyzer.analyze_traces(target_traces, current_policy_id))

        # 6. Latency SLA violations
        emitted.extend(LatencyAnalyzer.analyze_traces(target_traces, current_policy_id))

        # Index and deduplicate
        with self._lock:
            for rec in emitted:
                self._recommendations[rec.recommendation_id] = rec

        logger.info(f"[RecommendationEngine] Generated {len(emitted)} optimization recommendations across {len(target_traces)} traces.")
        return emitted

    def get_recommendation(self, recommendation_id: str) -> OptimizationRecommendation | None:
        """Retrieves a recommendation by ID."""
        with self._lock:
            return self._recommendations.get(recommendation_id)

    def list_recommendations(
        self,
        category: RecommendationCategory | str | None = None,
        status: str | None = None,
    ) -> list[OptimizationRecommendation]:
        """Lists recommendations, optionally filtered."""
        with self._lock:
            recs = list(self._recommendations.values())

        if category:
            cat_str = category.value if isinstance(category, RecommendationCategory) else str(category)
            recs = [r for r in recs if r.category == cat_str or r.category.value == cat_str]
        if status:
            recs = [r for r in recs if r.status == status]

        return recs

    def update_status(self, recommendation_id: str, new_status: str) -> bool:
        """Updates the lifecycle status of a recommendation."""
        with self._lock:
            rec = self._recommendations.get(recommendation_id)
            if rec:
                rec.status = new_status  # type: ignore[assignment]
                return True
        return False

    def clear_for_test(self) -> None:
        """Clears recommendations for clean testing."""
        with self._lock:
            self._recommendations.clear()


recommendation_engine = OptimizationRecommendationEngine()
