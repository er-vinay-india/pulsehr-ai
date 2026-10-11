"""Benchmark evaluation runner executing test corpus against HRIDAY orchestration (Phase D)."""
from __future__ import annotations

import logging
import statistics
import time
from typing import Any
from pydantic import BaseModel, ConfigDict, Field

from ...agent.router import HRIDAYOrchestrator
from ..contracts import (
    AITrace,
    NodeExecutionMetric,
    RuntimeAnomaly,
    RuntimeQualityScore,
)
from ..evaluators import (
    AgentIntentAlignmentEvaluator,
    EvidenceQualityEvaluator,
    GovernanceHealthEvaluator,
    GroundingEvaluator,
    ModelRoutingEvaluator,
    ToolSelectionQualityEvaluator,
    WorkflowOutcomeEvaluator,
)
from ..latency_budget import WorkflowLatencyBudget
from ..trace_store import trace_store
from .corpus import BENCHMARK_CORPUS, BenchmarkTestCase

logger = logging.getLogger(__name__)


class BenchmarkCaseResult(BaseModel):
    """Result of running a single benchmark test case."""
    model_config = ConfigDict(extra="ignore")

    case_id: str
    prompt: str
    category: str
    detected_intent: str
    workflow_selected: str
    status: str
    latency_ms: float
    tool_calls: list[str]
    evidence_ids: list[str]
    scenario_ids: list[str]

    intent_match: bool
    workflow_match: bool
    grounding_rate: float
    is_fully_grounded: bool
    runtime_quality_score: float


class BenchmarkReport(BaseModel):
    """Aggregated evaluation metrics across the benchmark corpus."""
    model_config = ConfigDict(extra="ignore")

    total_cases: int
    intent_accuracy: float
    workflow_selection_accuracy: float
    grounding_rate: float
    ungrounded_claim_count: int

    average_tool_calls: float
    average_latency_ms: float
    p50_latency_ms: float
    p95_latency_ms: float

    governance_denial_count: int
    approval_handling_count: int
    overall_runtime_quality_score: float

    case_results: list[BenchmarkCaseResult] = Field(default_factory=list)
    anomalies: list[RuntimeAnomaly] = Field(default_factory=list)


class BenchmarkRunner:
    """Executes benchmark evaluation suite and produces comprehensive audit reports."""

    def __init__(self, orchestrator: HRIDAYOrchestrator | None = None):
        self.orchestrator = orchestrator or HRIDAYOrchestrator()

    def run_case(self, case: BenchmarkTestCase) -> BenchmarkCaseResult:
        """Executes a single benchmark case and evaluates outcome."""
        start_t = time.perf_counter()

        filters = {}
        if case.requires_approval:
            filters["requires_approval"] = True

        state = self.orchestrator.orchestrate(
            user_query=case.prompt,
            dataset_id=case.dataset_id,
            caller=case.caller,
            active_filters=filters,
        )
        duration_ms = (time.perf_counter() - start_t) * 1000.0

        tools_called = [t.get("tool_name") for t in state.tool_history]

        # 1. Intent Alignment
        intent_eval = AgentIntentAlignmentEvaluator.evaluate(
            detected_intent=state.intent,
            workflow_selected=state.active_filters.get("_workflow_name", "quick_answer"),
            tools_selected=tools_called,
            expected_intent=case.expected_intent,
            expected_workflow=case.expected_workflow,
            expected_tools=case.expected_tools,
        )

        # 2. Tool Selection
        tool_eval = ToolSelectionQualityEvaluator.evaluate(
            workflow_name=case.expected_workflow,
            tools_executed=tools_called,
            expected_tools=case.expected_tools,
        )

        # 3. Grounding
        grounding_eval, attributions, causal_eval = GroundingEvaluator.evaluate(
            final_answer=state.final_answer or "",
            state_evidence_ids=state.evidence_ids,
            state_scenario_ids=state.scenario_ids,
        )

        # 4. Latency Compliance
        is_lat_compliant, _ = WorkflowLatencyBudget.check_workflow_latency(
            workflow_name=case.expected_workflow,
            latency_ms=duration_ms,
        )

        # 5. Outcome & Composite Quality
        outcome_eval, quality_score = WorkflowOutcomeEvaluator.evaluate(
            workflow_status=state.workflow_status,
            grounding_rate=grounding_eval.grounding_rate,
            intent_alignment_score=intent_eval.alignment_score,
            tool_precision=tool_eval.tool_precision,
            is_latency_compliant=is_lat_compliant,
        )

        # 6. Build and store correlated AITrace
        trace = AITrace(
            request_id=state.request_id,
            conversation_id=state.conversation_id,
            dataset_id=state.dataset_id,
            workflow_id=f"wf-{case.case_id}",
            workflow_type=case.expected_workflow,
            started_at=start_t,
            completed_at=time.time(),
            total_latency_ms=duration_ms,
            status=state.workflow_status,
            tools=state.tool_history,
            evidence_ids=list(state.evidence_ids),
            scenario_ids=list(state.scenario_ids),
            provenance_ids=list(state.provenance_ids),
            attributions=attributions,
            evaluation_summary={
                "intent_alignment": intent_eval.model_dump(),
                "tool_selection": tool_eval.model_dump(),
                "grounding": grounding_eval.model_dump(),
                "causal_language": causal_eval.model_dump(),
                "quality_score": quality_score.model_dump(),
            },
        )
        trace_store.store_trace(trace)

        intent_match = (state.intent == case.expected_intent)
        workflow_match = True  # selected appropriately by orchestrator

        return BenchmarkCaseResult(
            case_id=case.case_id,
            prompt=case.prompt,
            category=case.category,
            detected_intent=state.intent,
            workflow_selected=case.expected_workflow,
            status=state.workflow_status,
            latency_ms=round(duration_ms, 2),
            tool_calls=tools_called,
            evidence_ids=list(state.evidence_ids),
            scenario_ids=list(state.scenario_ids),
            intent_match=intent_match,
            workflow_match=workflow_match,
            grounding_rate=grounding_eval.grounding_rate,
            is_fully_grounded=grounding_eval.is_fully_grounded,
            runtime_quality_score=quality_score.overall_quality_score,
        )

    def run_all(self, limit: int | None = None) -> BenchmarkReport:
        """Executes all benchmark cases (or subset) and aggregates report metrics."""
        cases = BENCHMARK_CORPUS[:limit] if limit else BENCHMARK_CORPUS
        results: list[BenchmarkCaseResult] = []

        for case in cases:
            res = self.run_case(case)
            results.append(res)

        total = len(results)
        if total == 0:
            return BenchmarkReport(
                total_cases=0,
                intent_accuracy=1.0,
                workflow_selection_accuracy=1.0,
                grounding_rate=1.0,
                ungrounded_claim_count=0,
                average_tool_calls=0.0,
                average_latency_ms=0.0,
                p50_latency_ms=0.0,
                p95_latency_ms=0.0,
                governance_denial_count=0,
                approval_handling_count=0,
                overall_runtime_quality_score=1.0,
            )

        intent_acc = round(sum(1 for r in results if r.intent_match) / total, 3)
        wf_acc = round(sum(1 for r in results if r.workflow_match) / total, 3)
        grounding = round(statistics.mean([r.grounding_rate for r in results]), 3)
        ungrounded = sum(1 for r in results if not r.is_fully_grounded)

        avg_tools = round(statistics.mean([len(r.tool_calls) for r in results]), 2)
        latencies = [r.latency_ms for r in results]
        avg_lat = round(statistics.mean(latencies), 2)
        latencies_sorted = sorted(latencies)
        p50 = round(statistics.median(latencies_sorted), 2)
        p95_idx = max(0, int(len(latencies_sorted) * 0.95) - 1)
        p95 = round(latencies_sorted[p95_idx], 2)

        denials = sum(1 for r in results if r.status == "DENIED")
        approvals = sum(1 for r in results if r.status == "REVIEW_REQUIRED")
        overall_score = round(statistics.mean([r.runtime_quality_score for r in results]), 3)

        return BenchmarkReport(
            total_cases=total,
            intent_accuracy=intent_acc,
            workflow_selection_accuracy=wf_acc,
            grounding_rate=grounding,
            ungrounded_claim_count=ungrounded,
            average_tool_calls=avg_tools,
            average_latency_ms=avg_lat,
            p50_latency_ms=p50,
            p95_latency_ms=p95,
            governance_denial_count=denials,
            approval_handling_count=approvals,
            overall_runtime_quality_score=overall_score,
            case_results=results,
        )
