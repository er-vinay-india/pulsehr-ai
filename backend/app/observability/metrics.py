"""Runtime metrics aggregation and deterministic anomaly detection (Phase D)."""
from __future__ import annotations

import logging
import statistics
import time
from typing import Any
from pydantic import BaseModel, ConfigDict, Field
from .contracts import AITrace, RuntimeAnomaly

logger = logging.getLogger(__name__)


class RuntimeHealthKPIs(BaseModel):
    """Key performance and reliability indicators surfaced in Technical Explorer."""
    model_config = ConfigDict(extra="ignore")

    total_traces: int = 0
    grounding_rate_pct: float = 100.0
    avg_tools_per_query: float = 0.0
    fallback_rate_pct: float = 0.0
    failed_safe_rate_pct: float = 0.0
    governance_denial_rate_pct: float = 0.0
    approval_rate_pct: float = 0.0

    p50_quick_answer_ms: float = 0.0
    p95_quick_answer_ms: float = 0.0
    p50_investigation_ms: float = 0.0
    p95_investigation_ms: float = 0.0


class AnomalyDetector:
    """Detects deterministic runtime anomalies across traces without relying on LLMs."""

    TOOL_COUNT_THRESHOLD = 8
    LATENCY_SPIKE_THRESHOLD_MS = 12000.0
    GROUNDING_DROP_THRESHOLD = 0.95

    @classmethod
    def scan_trace_for_anomalies(cls, trace: AITrace) -> list[RuntimeAnomaly]:
        anomalies: list[RuntimeAnomaly] = []

        # 1. Tool Call Overuse Anomaly
        tool_count = len(trace.tools)
        if tool_count > cls.TOOL_COUNT_THRESHOLD:
            anomalies.append(RuntimeAnomaly(
                anomaly_type="TOOL_COUNT_SPIKE",
                severity="HIGH",
                message=f"Excessive tool calls detected ({tool_count} > {cls.TOOL_COUNT_THRESHOLD}) in workflow '{trace.workflow_type}'",
                trace_id=trace.trace_id,
            ))

        # 2. Latency Spike Anomaly
        if trace.total_latency_ms > cls.LATENCY_SPIKE_THRESHOLD_MS:
            anomalies.append(RuntimeAnomaly(
                anomaly_type="LATENCY_SPIKE",
                severity="MEDIUM",
                message=f"Latency spike detected ({trace.total_latency_ms:.1f}ms > {cls.LATENCY_SPIKE_THRESHOLD_MS:.1f}ms)",
                trace_id=trace.trace_id,
            ))

        # 3. Grounding Drop Anomaly
        grounding_summary = trace.evaluation_summary.get("grounding", {})
        g_rate = grounding_summary.get("grounding_rate", 1.0)
        if g_rate < cls.GROUNDING_DROP_THRESHOLD:
            anomalies.append(RuntimeAnomaly(
                anomaly_type="GROUNDING_DROP",
                severity="CRITICAL",
                message=f"Factual grounding rate degraded below threshold ({g_rate * 100:.1f}% < 95.0%)",
                trace_id=trace.trace_id,
            ))

        # 4. Failed-Safe Anomaly
        if trace.status == "FAILED_SAFE":
            anomalies.append(RuntimeAnomaly(
                anomaly_type="FAILED_SAFE_HALT",
                severity="HIGH",
                message=f"Execution halted safely due to loop limits or error in trace {trace.trace_id}",
                trace_id=trace.trace_id,
            ))

        # 5. EVID/SCEN Contamination Check
        has_evid = any(eid.startswith("SCEN-") for eid in trace.evidence_ids)
        if has_evid:
            anomalies.append(RuntimeAnomaly(
                anomaly_type="SCENARIO_EVIDENCE_CONTAMINATION",
                severity="CRITICAL",
                message=f"Counterfactual SCEN tokens detected inside evidence_ids ledger in trace {trace.trace_id}",
                trace_id=trace.trace_id,
            ))

        return anomalies


class MetricsAggregator:
    """Aggregates historical traces into executive and technical KPIs."""

    @classmethod
    def compute_kpis(cls, traces: list[AITrace]) -> RuntimeHealthKPIs:
        if not traces:
            return RuntimeHealthKPIs()

        total = len(traces)
        tool_counts = [len(t.tools) for t in traces]
        avg_tools = round(statistics.mean(tool_counts), 2) if tool_counts else 0.0

        # Grounding
        grounding_rates = []
        for t in traces:
            g_eval = t.evaluation_summary.get("grounding", {})
            g_rate = g_eval.get("grounding_rate", 1.0)
            grounding_rates.append(g_rate)
        avg_grounding_pct = round(statistics.mean(grounding_rates) * 100.0, 1) if grounding_rates else 100.0

        # Fallbacks
        fallback_counts = sum(
            1 for t in traces
            if t.evaluation_summary.get("model_routing", {}).get("fallback_used", False)
        )
        fallback_pct = round((fallback_counts / total) * 100.0, 1)

        # Status percentages
        failed_safes = sum(1 for t in traces if t.status == "FAILED_SAFE")
        failed_safe_pct = round((failed_safes / total) * 100.0, 1)

        denials = sum(1 for t in traces if t.status == "DENIED")
        denial_pct = round((denials / total) * 100.0, 1)

        approvals = sum(1 for t in traces if len(t.approvals) > 0 or t.status == "REVIEW_REQUIRED")
        approval_pct = round((approvals / total) * 100.0, 1)

        # Latencies by workflow type
        qa_latencies = [t.total_latency_ms for t in traces if t.workflow_type == "quick_answer"]
        inv_latencies = [t.total_latency_ms for t in traces if t.workflow_type == "analytical_investigation"]

        p50_qa = round(statistics.median(qa_latencies), 1) if qa_latencies else 0.0
        p95_qa = round(sorted(qa_latencies)[max(0, int(len(qa_latencies) * 0.95) - 1)], 1) if qa_latencies else 0.0

        p50_inv = round(statistics.median(inv_latencies), 1) if inv_latencies else 0.0
        p95_inv = round(sorted(inv_latencies)[max(0, int(len(inv_latencies) * 0.95) - 1)], 1) if inv_latencies else 0.0

        return RuntimeHealthKPIs(
            total_traces=total,
            grounding_rate_pct=avg_grounding_pct,
            avg_tools_per_query=avg_tools,
            fallback_rate_pct=fallback_pct,
            failed_safe_rate_pct=failed_safe_pct,
            governance_denial_rate_pct=denial_pct,
            approval_rate_pct=approval_pct,
            p50_quick_answer_ms=p50_qa,
            p95_quick_answer_ms=p95_qa,
            p50_investigation_ms=p50_inv,
            p95_investigation_ms=p95_inv,
        )
