"""GovernedOptimizer: High-level orchestration facade for Governed Adaptive Optimization (Phase E).

Unites:
- Recommendation generation from Phase D telemetry
- Candidate policy derivation and immutable registration
- Offline benchmark execution and strict safety gate comparison
- Human approval / promotion workflows
- Shadow policy execution without user exposure or mutations
- Anomaly-driven rollbacks
"""
from __future__ import annotations

import copy
import logging
import threading
import time
from typing import Any
from uuid import uuid4

from app.agent.state import HighviewAgentState
from app.observability.benchmark.runner import BenchmarkReport, BenchmarkRunner
from app.observability.contracts import AITrace
from app.observability.trace_store import TraceStore, trace_store
from .contracts import (
    HighviewPolicy,
    OptimizationRecommendation,
    PolicyComparisonResult,
    PolicyStatus,
    ShadowEvaluation,
)
from .policy_registry import PolicyRegistry, policy_registry
from .recommendation_engine import OptimizationRecommendationEngine, recommendation_engine
from .benchmark.candidate_runner import CandidateBenchmarkRunner
from .comparison import PolicyComparator
from .promotion_gate import PromotionGate
from .shadow_evaluator import ShadowPolicyEvaluator
from .rollback import RollbackManager, rollback_manager

logger = logging.getLogger(__name__)


class GovernedOptimizer:
    """Central controller coordinating governed optimization workflows."""

    def __init__(
        self,
        registry: PolicyRegistry | None = None,
        rec_engine: OptimizationRecommendationEngine | None = None,
        rb_manager: RollbackManager | None = None,
        trace_storage: TraceStore | None = None,
    ):
        self._lock = threading.Lock()
        self._registry = registry or policy_registry
        self._rec_engine = rec_engine or recommendation_engine
        self._rollback_mgr = rb_manager or rollback_manager
        self._trace_store = trace_storage or trace_store

        self._comparison_results: dict[str, PolicyComparisonResult] = {}
        self._shadow_evaluations: list[ShadowEvaluation] = []

    # 1. Policy Registry access
    def get_active_policy(self) -> HighviewPolicy:
        """Retrieves active immutable production policy."""
        return self._registry.get_active_policy()

    def list_policies(self, status: PolicyStatus | None = None) -> list[HighviewPolicy]:
        """Lists registered policies."""
        return self._registry.list_policies(status=status)

    def get_policy(self, policy_id: str) -> HighviewPolicy | None:
        """Retrieves a policy by ID."""
        return self._registry.get_policy(policy_id)

    # 2. Recommendations
    def analyze_traces_and_recommend(
        self,
        traces: list[AITrace] | None = None,
    ) -> list[OptimizationRecommendation]:
        """Runs all 6 analyzers to produce candidate recommendations from telemetry."""
        return self._rec_engine.generate_recommendations(traces=traces)

    def list_recommendations(self, category: str | None = None, status: str | None = None) -> list[OptimizationRecommendation]:
        """Lists active and historical recommendations."""
        return self._rec_engine.list_recommendations(category=category, status=status)

    # 3. Candidate Policy Derivation
    def create_candidate_from_recommendation(
        self,
        recommendation: OptimizationRecommendation,
        author: str = "human_governance",
    ) -> HighviewPolicy:
        """Derives a new immutable candidate HighviewPolicy incorporating recommendation delta."""
        active = self.get_active_policy()

        new_policy_dict = active.model_dump()
        new_policy_dict["policy_id"] = f"POLICY-CANDIDATE-{uuid4().hex[:6].upper()}"
        new_policy_dict["version_number"] = active.version_number + 1
        new_policy_dict["name"] = f"Candidate from {recommendation.category.value} recommendation"
        new_policy_dict["description"] = recommendation.reason
        new_policy_dict["status"] = PolicyStatus.CANDIDATE
        new_policy_dict["created_by"] = author
        new_policy_dict["created_at"] = time.time()
        new_policy_dict["parent_policy_id"] = active.policy_id
        new_policy_dict["approval_status"] = "PENDING_BENCHMARK"
        new_policy_dict["approved_by"] = None
        new_policy_dict["approved_at"] = None

        delta = recommendation.proposed_policy_delta

        # Apply delta safely according to category
        if "workflow" in delta and "prune_unnecessary_preflights" in delta:
            # Workflow adjustment
            new_policy_dict["workflow_policy"]["enable_early_exit_on_sufficiency"] = True
        if "cascade" in delta:
            # Model routing cascade adjustment
            for task_type, cascade_models in delta["cascade"].items():
                new_policy_dict["model_routing_policy"]["cascades"][task_type] = cascade_models
        if "parallel_candidates" in delta:
            # Parallel tool candidate adjustment
            new_policy_dict["tool_policy"]["parallel_execution_candidates"] = delta["parallel_candidates"]
        if "max_tool_calls_per_query" in delta:
            new_policy_dict["tool_policy"]["max_tool_calls_per_query"] = delta["max_tool_calls_per_query"]
        if "deduplicate_certified_determinations" in delta:
            new_policy_dict["evidence_policy"]["deduplicate_certified_determinations"] = delta["deduplicate_certified_determinations"]
        if "max_node_retries" in delta:
            new_policy_dict["retry_policy"]["max_node_retries"] = delta["max_node_retries"]

        candidate = HighviewPolicy(**new_policy_dict)
        self._registry.register_candidate(candidate)
        self._rec_engine.update_status(recommendation.recommendation_id, "BENCHMARKED")
        return candidate

    # 4. Benchmark Comparison and Promotion Gate
    def benchmark_and_compare(
        self,
        candidate_policy: HighviewPolicy,
        limit: int = 10,
        safety_override_flags: dict[str, Any] | None = None,
    ) -> PolicyComparisonResult:
        """Benchmarks candidate offline against active baseline under hard safety gates."""
        active = self.get_active_policy()

        # Run baseline report
        baseline_report = BenchmarkRunner().run_all(limit=limit)

        # Run candidate report
        candidate_report = CandidateBenchmarkRunner.run_candidate_benchmark(
            candidate_policy=candidate_policy,
            limit=limit,
        )

        comparison = PolicyComparator.compare_policies(
            baseline_policy=active,
            candidate_policy=candidate_policy,
            baseline_report=baseline_report,
            candidate_report=candidate_report,
            safety_override_flags=safety_override_flags,
        )

        with self._lock:
            self._comparison_results[candidate_policy.policy_id] = comparison

        # Update candidate approval status accordingly
        eligible, reason = PromotionGate.evaluate_eligibility(comparison)
        if not eligible:
            candidate_policy.approval_status = f"INELIGIBLE: {reason}"
        else:
            candidate_policy.approval_status = "ELIGIBLE_FOR_HUMAN_REVIEW"

        return comparison

    def get_comparison_result(self, candidate_policy_id: str) -> PolicyComparisonResult | None:
        """Retrieves comparison result for candidate policy."""
        with self._lock:
            return self._comparison_results.get(candidate_policy_id)

    # 5. Human Promotion & Rejection
    def approve_and_activate(
        self,
        candidate_policy_id: str,
        comparison: PolicyComparisonResult | None = None,
        approved_by: str = "human_governance",
    ) -> tuple[bool, str]:
        """Enforces human approval governance invariant before promoting candidate to ACTIVE."""
        candidate = self.get_policy(candidate_policy_id)
        if not candidate:
            return False, f"Candidate policy '{candidate_policy_id}' not found."

        if candidate.status != PolicyStatus.CANDIDATE:
            return False, f"Policy '{candidate_policy_id}' is not in CANDIDATE state (status: {candidate.status})."

        comp = comparison or self.get_comparison_result(candidate_policy_id)
        if comp:
            eligible, reason = PromotionGate.evaluate_eligibility(comp)
            if not eligible:
                logger.warning(f"[GovernedOptimizer] Promotion refused by safety gate: {reason}")
                return False, f"Safety gate refused promotion: {reason}"

        # Promote
        success, msg = self._registry.activate_policy(candidate_policy_id, approved_by=approved_by)
        return success, msg

    def reject_candidate(
        self,
        candidate_policy_id: str,
        reason: str = "Rejected by governance board",
    ) -> None:
        """Explicit human rejection of candidate policy."""
        self._registry.reject_policy(candidate_policy_id, reason=reason)

    # 6. Safe Rollback
    def execute_rollback(
        self,
        to_policy_id: str | None = None,
        operator: str = "governance_safety",
    ) -> tuple[bool, str]:
        """Rolls back active policy to previous immutable baseline."""
        return self._rollback_mgr.execute_rollback(to_policy_id=to_policy_id, operator=operator)

    # 7. Shadow Policy Evaluation
    def run_shadow_evaluation(
        self,
        active_state: HighviewAgentState,
        candidate_policy_id: str,
        active_latency_ms: float = 120.0,
    ) -> ShadowEvaluation | None:
        """Runs shadow evaluation without user exposure or side effects."""
        candidate = self.get_policy(candidate_policy_id)
        if not candidate:
            logger.error(f"[GovernedOptimizer] Cannot run shadow evaluation: candidate '{candidate_policy_id}' not found.")
            return None

        shadow_eval = ShadowPolicyEvaluator.evaluate_shadow(
            active_state=active_state,
            candidate_policy=candidate,
            active_latency_ms=active_latency_ms,
        )

        with self._lock:
            self._shadow_evaluations.append(shadow_eval)

        return shadow_eval

    def list_shadow_evaluations(self) -> list[ShadowEvaluation]:
        """Lists recorded shadow evaluations."""
        with self._lock:
            return list(self._shadow_evaluations)

    def clear_for_test(self) -> None:
        """Resets state for clean unit and integration testing."""
        self._registry.clear_for_test()
        self._rec_engine.clear_for_test()
        with self._lock:
            self._comparison_results.clear()
            self._shadow_evaluations.clear()


governed_optimizer = GovernedOptimizer()
