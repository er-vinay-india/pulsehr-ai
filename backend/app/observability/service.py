"""AIObservabilityService: Central runtime intelligence and evaluation service (Phase D)."""
from __future__ import annotations

import logging
import time
from typing import Any
from uuid import uuid4

from ..agent.execution_record import WorkflowExecutionRecord
from ..agent.state import HighviewAgentState
from .benchmark.runner import BenchmarkReport, BenchmarkRunner
from .contracts import (
    AITrace,
    NodeExecutionMetric,
    RuntimeAnomaly,
    RuntimeQualityScore,
)
from .evaluators import (
    AgentIntentAlignmentEvaluator,
    EvidenceQualityEvaluator,
    GovernanceHealthEvaluator,
    GroundingEvaluator,
    ModelRoutingEvaluator,
    ToolSelectionQualityEvaluator,
    WorkflowOutcomeEvaluator,
)
from .latency_budget import WorkflowLatencyBudget
from .metrics import AnomalyDetector, MetricsAggregator, RuntimeHealthKPIs
from .trace_store import TraceStore, trace_store

logger = logging.getLogger(__name__)


class AIObservabilityService:
    """Master facade for telemetry ingestion, continuous evaluation, and explorer telemetry."""

    def __init__(self, store: TraceStore = trace_store):
        self.store = store
        self.benchmark_runner = BenchmarkRunner()

    def record_workflow_execution(
        self,
        state: HighviewAgentState,
        wf_record: WorkflowExecutionRecord | None = None,
        workflow_type: str = "quick_answer",
    ) -> AITrace:
        """Constructs an evaluated AITrace from an executed LangGraph state."""
        start_time = wf_record.started_at if wf_record else (time.time() - 0.1)
        completed_time = wf_record.completed_at if wf_record else time.time()
        latency_ms = wf_record.total_latency_ms if wf_record else (completed_time - start_time) * 1000.0

        tools_called = [t.get("tool_name") for t in state.tool_history]

        # 1. Intent Alignment
        intent_eval = AgentIntentAlignmentEvaluator.evaluate(
            detected_intent=state.intent,
            workflow_selected=workflow_type,
            tools_selected=tools_called,
        )

        # 2. Tool Selection Quality
        tool_eval = ToolSelectionQualityEvaluator.evaluate(
            workflow_name=workflow_type,
            tools_executed=tools_called,
        )

        # 3. Grounding & Provenance
        grounding_eval, attributions, causal_eval = GroundingEvaluator.evaluate(
            final_answer=state.final_answer or "",
            state_evidence_ids=state.evidence_ids,
            state_scenario_ids=state.scenario_ids,
        )

        # 4. Evidence Quality
        evid_eval = EvidenceQualityEvaluator.evaluate(
            intent=state.intent,
            evidence_ids=state.evidence_ids,
            tools_called=tools_called,
        )

        # 5. Governance Health
        approvals = [state.pending_approval] if state.pending_approval else []
        gov_eval = GovernanceHealthEvaluator.evaluate(
            tool_history=state.tool_history,
            approvals=approvals,
            workflow_status=state.workflow_status,
        )

        # 6. Model Routing (if models called)
        models_used = wf_record.models_used if wf_record else ["gateway-fallback-deterministic"]
        model_eval, cost_metric = ModelRoutingEvaluator.evaluate(
            task_type="AGENTIC_AI",
            primary_model="qwen3.5:9b",
            actual_model=models_used[0] if models_used else "qwen3.5:9b",
            latency_ms=latency_ms,
        )

        # 7. SLA Compliance
        is_compliant, sla_msg = WorkflowLatencyBudget.check_workflow_latency(
            workflow_name=workflow_type,
            latency_ms=latency_ms,
        )

        # 8. Outcome & Composite Runtime Quality
        outcome_eval, quality_score = WorkflowOutcomeEvaluator.evaluate(
            workflow_status=state.workflow_status,
            grounding_rate=grounding_eval.grounding_rate,
            intent_alignment_score=intent_eval.alignment_score,
            tool_precision=tool_eval.tool_precision,
            is_latency_compliant=is_compliant,
        )

        # Construct AITrace
        trace = AITrace(
            request_id=state.request_id,
            conversation_id=state.conversation_id,
            dataset_id=state.dataset_id,
            workspace_id=state.workspace_id,
            workflow_id=wf_record.workflow_id if wf_record else f"wf-{uuid4().hex[:8]}",
            workflow_type=workflow_type,
            started_at=start_time,
            completed_at=completed_time,
            total_latency_ms=round(latency_ms, 2),
            status=state.workflow_status,
            tools=state.tool_history,
            evidence_ids=list(state.evidence_ids),
            scenario_ids=list(state.scenario_ids),
            provenance_ids=list(state.provenance_ids),
            approvals=approvals,
            attributions=attributions,
            evaluation_summary={
                "intent_alignment": intent_eval.model_dump(),
                "tool_selection": tool_eval.model_dump(),
                "grounding": grounding_eval.model_dump(),
                "causal_language": causal_eval.model_dump(),
                "evidence_quality": evid_eval.model_dump(),
                "governance_health": gov_eval.model_dump(),
                "model_routing": model_eval.model_dump(),
                "compute_cost": cost_metric.model_dump(),
                "outcome": outcome_eval.model_dump(),
                "quality_score": quality_score.model_dump(),
                "sla_compliant": is_compliant,
                "sla_message": sla_msg,
            },
        )

        # Scan for anomalies
        trace.anomalies = AnomalyDetector.scan_trace_for_anomalies(trace)

        # Store in ledger
        self.store.store_trace(trace)
        return trace

    def get_runtime_kpis(self, dataset_id: int | str | None = None) -> RuntimeHealthKPIs:
        """Computes aggregate KPIs across historical traces."""
        traces = self.store.list_traces(dataset_id=dataset_id, limit=200)
        return MetricsAggregator.compute_kpis(traces)

    def get_trace_details(self, trace_id: str) -> dict[str, Any] | None:
        """Retrieves complete trace drill-down for Technical Explorer."""
        trace = self.store.get_trace(trace_id)
        if not trace:
            return None
        return trace.model_dump()

    def run_benchmark_evaluations(self, limit: int | None = None) -> BenchmarkReport:
        """Executes the benchmark corpus and aggregates evaluation report."""
        return self.benchmark_runner.run_all(limit=limit)

    def get_technical_explorer_summary(self, dataset_id: int | str | None = None) -> dict[str, Any]:
        """Returns structured payload for Technical Explorer AI Runtime Intelligence tab."""
        kpis = self.get_runtime_kpis(dataset_id=dataset_id)
        recent_traces = self.store.list_traces(dataset_id=dataset_id, limit=10)

        all_anomalies = []
        for t in recent_traces:
            all_anomalies.extend([a.model_dump() for a in t.anomalies])

        return {
            "kpis": kpis.model_dump(),
            "recent_traces": [
                {
                    "trace_id": t.trace_id,
                    "workflow_type": t.workflow_type,
                    "status": t.status,
                    "latency_ms": t.total_latency_ms,
                    "evidence_count": len(t.evidence_ids),
                    "scenario_count": len(t.scenario_ids),
                    "tool_count": len(t.tools),
                    "grounding_rate": t.evaluation_summary.get("grounding", {}).get("grounding_rate", 1.0),
                    "completed_at": t.completed_at,
                }
                for t in recent_traces
            ],
            "anomalies": all_anomalies[-5:],
        }


ai_observability_service = AIObservabilityService()
