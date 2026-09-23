"""Observability, execution tracing, and factual lineage tracker for AI reporting."""

import logging
import time
from typing import Any
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class ExecutionTrace(BaseModel):
    """Detailed telemetry record for a single LLM or deterministic stage invocation."""
    trace_id: str
    report_id: str
    workflow_step: str
    role: str
    model_requested: str
    model_used: str
    duration_ms: float
    success: bool
    fallback_triggered: bool = False
    retry_count: int = 0
    prompt_tokens_approx: int = 0
    completion_tokens_approx: int = 0
    finding_ids_referenced: list[str] = Field(default_factory=list)
    critic_verdict: str | None = None
    error: str | None = None


class LineageRecord(BaseModel):
    """Lineage link connecting a generated statement back to evidence and source columns."""
    report_id: str
    section_id: str
    sentence_text: str
    finding_id: str
    metric_name: str
    source_sheet: str
    source_columns: list[str] = Field(default_factory=list)
    verified_by_critic: bool = False


class TraceRegistry:
    """In-memory trace registry storing execution logs and lineage traces."""

    def __init__(self):
        self._traces: list[ExecutionTrace] = []
        self._lineage: list[LineageRecord] = []

    def record_trace(self, trace: ExecutionTrace):
        self._traces.append(trace)
        logger.info(
            f"[AI Gateway Trace] step={trace.workflow_step} role={trace.role} "
            f"model={trace.model_used} latency={trace.duration_ms:.1f}ms "
            f"success={trace.success} fallback={trace.fallback_triggered}"
        )

    def record_lineage(self, lineage: LineageRecord):
        self._lineage.append(lineage)

    def get_traces_for_report(self, report_id: str) -> list[ExecutionTrace]:
        return [t for t in self._traces if t.report_id == report_id]

    def get_lineage_for_report(self, report_id: str) -> list[LineageRecord]:
        return [l for l in self._lineage if l.report_id == report_id]

    def clear(self):
        self._traces.clear()
        self._lineage.clear()


# Global trace registry singleton
trace_registry = TraceRegistry()
