"""Highview Observability & Runtime Governance Engine.

Implements OpenTelemetry-compatible tracing, GenAI semantic conventions,
runtime budget enforcement, and dual-layer governance reporting:
1. Executive View: Measurable integrity indicators (grounding, coverage, validation).
2. Developer View: Complete hierarchical span tree, model attributes, MCP tool calls,
   budget utilization, and discrete runtime events.
"""
from __future__ import annotations

import time
import uuid
from contextlib import contextmanager
from typing import Any, Generator, Literal
from pydantic import BaseModel, ConfigDict, Field


# -----------------------------------------------------------------------------
# Semantic Attribute Constants (OpenTelemetry GenAI & Highview Conventions)
# -----------------------------------------------------------------------------

ATTR_TRACE_ID = "highview.trace_id"
ATTR_REQUEST_ID = "highview.request_id"
ATTR_SHEET_ID = "highview.sheet_id"
ATTR_DATASET_ID = "highview.dataset_id"
ATTR_CALLER_ROLE = "highview.caller_role"
ATTR_AGENT_NAME = "highview.agent_name"

ATTR_GENAI_SYSTEM = "gen_ai.system"
ATTR_GENAI_MODEL = "gen_ai.request.model"
ATTR_GENAI_TOKENS_IN = "gen_ai.usage.input_tokens"
ATTR_GENAI_TOKENS_OUT = "gen_ai.usage.output_tokens"

ATTR_MCP_TOOL_NAME = "mcp.tool.name"
ATTR_MCP_PERMISSION = "mcp.permission_result"
ATTR_MCP_EVID_COUNT = "mcp.evidence_count"
ATTR_MCP_SCEN_COUNT = "mcp.scenario_count"

ATTR_GROUNDING_STATUS = "grounding.status"
ATTR_GROUNDING_COVERAGE = "grounding.coverage_pct"
ATTR_UNSUPPORTED_CLAIMS = "grounding.unsupported_claims_count"
ATTR_CAUSAL_VIOLATIONS = "grounding.causal_violations_count"

ATTR_VISUAL_TYPE = "visual.type"
ATTR_VISUAL_QA_PASSED = "visual.qa_passed"
ATTR_VISUAL_THEME_INTEGRITY_PASSED = "visual.theme_integrity_passed"
ATTR_VISUAL_THEME_MODE = "visual.theme_mode"
ATTR_VISUAL_THEME_VIOLATION_COUNT = "visual.theme_violation_count"
ATTR_VISUAL_CONTRAST_VIOLATION_COUNT = "visual.contrast_violation_count"
EVENT_THEME_INTEGRITY_VIOLATION = "theme_integrity_violation"

ATTR_BUDGET_LATENCY_MAX = "budget.latency_budget_ms"
ATTR_BUDGET_STATUS = "budget.status"


class SpanEvent(BaseModel):
    """Noteworthy runtime transition event attached to an execution span."""
    model_config = ConfigDict(extra="forbid")

    name: str  # e.g., "model_fallback_triggered", "unsupported_claim_blocked", "forecast_rejected"
    timestamp_ms: float
    attributes: dict[str, Any] = Field(default_factory=dict)


class HighviewSpan(BaseModel):
    """Hierarchical OpenTelemetry-compatible span with GenAI attributes and events."""
    model_config = ConfigDict(extra="forbid")

    span_id: str
    parent_span_id: str | None = None
    name: str
    start_time_ms: float
    end_time_ms: float | None = None
    duration_ms: float = 0.0
    status: Literal["OK", "ERROR", "WARNING"] = "OK"
    attributes: dict[str, Any] = Field(default_factory=dict)
    events: list[SpanEvent] = Field(default_factory=list)
    children: list[HighviewSpan] = Field(default_factory=list)


class RuntimeBudget(BaseModel):
    """Enforceable computational and latency envelope."""
    model_config = ConfigDict(extra="forbid")

    latency_budget_ms: float = 1500.0
    llm_call_budget: int = 1
    tool_call_budget: int = 8
    retry_budget: int = 1

    llm_calls_made: int = 0
    tool_calls_made: int = 0
    retries_made: int = 0

    def record_llm_call(self) -> None:
        self.llm_calls_made += 1

    def record_tool_call(self) -> None:
        self.tool_calls_made += 1

    def record_retry(self) -> None:
        self.retries_made += 1

    def is_exceeded(self, elapsed_ms: float) -> bool:
        return (
            elapsed_ms > self.latency_budget_ms
            or self.llm_calls_made > self.llm_call_budget
            or self.tool_calls_made > self.tool_call_budget
            or self.retries_made > self.retry_budget
        )


class HighviewTrace(BaseModel):
    """Authoritative trace instance wrapping request lifecycle."""
    model_config = ConfigDict(extra="forbid")

    trace_id: str
    request_id: str
    sheet_id: int | None = None
    dataset_id: int | None = None
    caller_role: str = "anonymous"
    agent_name: str = "highview_engine"
    start_time_ms: float
    end_time_ms: float | None = None
    total_duration_ms: float = 0.0
    budget: RuntimeBudget = Field(default_factory=RuntimeBudget)
    root_span: HighviewSpan


class TraceCollector:
    """Manages active span nesting, budget monitoring, and OTLP-compatible export."""

    def __init__(
        self,
        request_id: str | None = None,
        sheet_id: int | None = None,
        dataset_id: int | None = None,
        caller_role: str = "executive_dashboard",
        latency_budget_ms: float = 1500.0,
    ):
        self.trace_id = f"tr_{uuid.uuid4().hex[:12]}"
        self.request_id = request_id or f"req_{uuid.uuid4().hex[:8]}"
        self.sheet_id = sheet_id
        self.dataset_id = dataset_id
        self.caller_role = caller_role
        self.start_time = time.time()
        self.budget = RuntimeBudget(latency_budget_ms=latency_budget_ms)

        # Initialize root span
        self.root_span = HighviewSpan(
            span_id=f"sp_{uuid.uuid4().hex[:8]}",
            parent_span_id=None,
            name="HIGHVIEW_REQUEST",
            start_time_ms=self.start_time * 1000.0,
            attributes={
                ATTR_TRACE_ID: self.trace_id,
                ATTR_REQUEST_ID: self.request_id,
                ATTR_SHEET_ID: self.sheet_id,
                ATTR_DATASET_ID: self.dataset_id,
                ATTR_CALLER_ROLE: self.caller_role,
                ATTR_BUDGET_LATENCY_MAX: latency_budget_ms,
            },
        )
        self._current_span: HighviewSpan = self.root_span
        self._span_stack: list[HighviewSpan] = [self.root_span]

    @contextmanager
    def span(self, name: str, attributes: dict[str, Any] | None = None) -> Generator[HighviewSpan, None, None]:
        """Context manager creating a nested OpenTelemetry span."""
        now_ms = time.time() * 1000.0
        new_span = HighviewSpan(
            span_id=f"sp_{uuid.uuid4().hex[:8]}",
            parent_span_id=self._current_span.span_id,
            name=name,
            start_time_ms=now_ms,
            attributes=attributes or {},
        )
        self._current_span.children.append(new_span)
        self._span_stack.append(new_span)
        parent = self._current_span
        self._current_span = new_span

        try:
            yield new_span
        except Exception as exc:
            new_span.status = "ERROR"
            new_span.attributes["error.type"] = exc.__class__.__name__
            new_span.attributes["error.message"] = str(exc)
            self.record_event("exception_caught", {"error": str(exc), "span": name})
            raise
        finally:
            end_ms = time.time() * 1000.0
            new_span.end_time_ms = end_ms
            new_span.duration_ms = round(end_ms - new_span.start_time_ms, 2)
            self._span_stack.pop()
            self._current_span = parent

    def record_event(self, name: str, attributes: dict[str, Any] | None = None) -> None:
        """Records an event onto the currently active span."""
        now_ms = time.time() * 1000.0
        event = SpanEvent(name=name, timestamp_ms=now_ms, attributes=attributes or {})
        self._current_span.events.append(event)

    def finalize(self) -> HighviewTrace:
        """Finalizes the trace, computes total duration, and evaluates budget status."""
        end_time = time.time()
        end_ms = end_time * 1000.0
        self.root_span.end_time_ms = end_ms
        self.root_span.duration_ms = round(end_ms - self.root_span.start_time_ms, 2)

        is_exceeded = self.budget.is_exceeded(self.root_span.duration_ms)
        budget_status = "EXCEEDED" if is_exceeded else "WITHIN_BUDGET"
        self.root_span.attributes[ATTR_BUDGET_STATUS] = budget_status

        if is_exceeded:
            self.record_event(
                "budget_exceeded",
                {
                    "elapsed_ms": self.root_span.duration_ms,
                    "budget_ms": self.budget.latency_budget_ms,
                    "llm_calls": self.budget.llm_calls_made,
                    "tool_calls": self.budget.tool_calls_made,
                },
            )

        return HighviewTrace(
            trace_id=self.trace_id,
            request_id=self.request_id,
            sheet_id=self.sheet_id,
            dataset_id=self.dataset_id,
            caller_role=self.caller_role,
            start_time_ms=self.root_span.start_time_ms,
            end_time_ms=end_ms,
            total_duration_ms=self.root_span.duration_ms,
            budget=self.budget,
            root_span=self.root_span,
        )

    def export_executive_integrity(
        self,
        unsupported_claims: int = 0,
        coverage_pct: float = 100.0,
        numeric_valid: bool = True,
        causal_violations: int = 0,
    ) -> dict[str, Any]:
        """Returns clean, boardroom-ready engineering integrity metrics."""
        elapsed_ms = round((time.time() - self.start_time) * 1000.0, 1)
        budget_status = "EXCEEDED" if self.budget.is_exceeded(elapsed_ms) else "WITHIN_BUDGET"

        return {
            "grounding": "Passed" if unsupported_claims == 0 and causal_violations == 0 else "Warning",
            "evidence_coverage": f"{coverage_pct:.0f}%",
            "numeric_validation": "Passed" if numeric_valid else "Failed",
            "unsupported_claims": unsupported_claims,
            "scenario_isolation": "Strict (SCEN isolated from EVID)",
            "budget_status": budget_status,
            "total_latency_ms": elapsed_ms,
        }

    def export_developer_trace(self, trace: HighviewTrace) -> dict[str, Any]:
        """Returns complete OpenTelemetry-compliant hierarchical trace for diagnostics."""
        return trace.model_dump()
