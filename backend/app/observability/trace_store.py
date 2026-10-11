"""Thread-safe in-memory store for unified AITrace objects (Phase D)."""
from __future__ import annotations

import logging
import threading
from typing import Any
from .contracts import AITrace

logger = logging.getLogger(__name__)


class TraceStore:
    """Stores and indexes correlated AITrace objects with thread safety."""

    def __init__(self, max_traces: int = 1000):
        self._traces: list[AITrace] = []
        self._traces_by_id: dict[str, AITrace] = {}
        self._traces_by_request: dict[str, AITrace] = {}
        self._max_traces = max_traces
        self._lock = threading.Lock()

    def store_trace(self, trace: AITrace) -> AITrace:
        """Stores a trace, maintaining bounded memory capacity."""
        with self._lock:
            self._traces.append(trace)
            self._traces_by_id[trace.trace_id] = trace
            self._traces_by_request[trace.request_id] = trace

            if len(self._traces) > self._max_traces:
                evicted = self._traces.pop(0)
                self._traces_by_id.pop(evicted.trace_id, None)
                self._traces_by_request.pop(evicted.request_id, None)

        logger.debug(f"[TraceStore] Stored trace {trace.trace_id} (status: {trace.status}, latency: {trace.total_latency_ms:.1f}ms)")
        return trace

    def get_trace(self, trace_id: str) -> AITrace | None:
        """Retrieves a trace by its trace_id."""
        with self._lock:
            return self._traces_by_id.get(trace_id)

    def get_trace_by_request_id(self, request_id: str) -> AITrace | None:
        """Retrieves a trace by request_id."""
        with self._lock:
            return self._traces_by_request.get(request_id)

    def list_traces(
        self,
        dataset_id: int | str | None = None,
        workflow_type: str | None = None,
        limit: int = 50,
    ) -> list[AITrace]:
        """Lists historical traces with optional filtering."""
        with self._lock:
            traces_copy = self._traces[:]

        if dataset_id is not None:
            traces_copy = [t for t in traces_copy if str(t.dataset_id) == str(dataset_id)]
        if workflow_type is not None:
            traces_copy = [t for t in traces_copy if t.workflow_type == workflow_type]

        return traces_copy[-limit:]

    def clear_for_test(self) -> None:
        """Resets the store for isolated test execution."""
        with self._lock:
            self._traces.clear()
            self._traces_by_id.clear()
            self._traces_by_request.clear()


trace_store = TraceStore()
