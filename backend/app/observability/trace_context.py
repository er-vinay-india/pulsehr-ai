"""Context propagation utilities for unified trace_id tracking across execution layers (Phase D)."""
from __future__ import annotations

import contextvars
from typing import Any
from uuid import uuid4

# Context variables for distributed in-process tracing
_current_trace_id: contextvars.ContextVar[str] = contextvars.ContextVar("current_trace_id", default="")
_current_request_id: contextvars.ContextVar[str] = contextvars.ContextVar("current_request_id", default="")
_current_dataset_id: contextvars.ContextVar[int | str | None] = contextvars.ContextVar("current_dataset_id", default=None)
_current_workflow_id: contextvars.ContextVar[str | None] = contextvars.ContextVar("current_workflow_id", default=None)


class TraceContext:
    """Provides accessor methods to get and set active trace context."""

    @classmethod
    def get_trace_id(cls) -> str:
        tid = _current_trace_id.get()
        if not tid:
            tid = f"trace-{uuid4().hex[:12]}"
            _current_trace_id.set(tid)
        return tid

    @classmethod
    def set_trace_id(cls, trace_id: str) -> None:
        _current_trace_id.set(trace_id)

    @classmethod
    def get_request_id(cls) -> str:
        return _current_request_id.get()

    @classmethod
    def set_request_id(cls, request_id: str) -> None:
        _current_request_id.set(request_id)

    @classmethod
    def get_dataset_id(cls) -> int | str | None:
        return _current_dataset_id.get()

    @classmethod
    def set_dataset_id(cls, dataset_id: int | str | None) -> None:
        _current_dataset_id.set(dataset_id)

    @classmethod
    def get_workflow_id(cls) -> str | None:
        return _current_workflow_id.get()

    @classmethod
    def set_workflow_id(cls, workflow_id: str | None) -> None:
        _current_workflow_id.set(workflow_id)

    @classmethod
    def reset(cls) -> None:
        """Resets all context variables."""
        _current_trace_id.set("")
        _current_request_id.set("")
        _current_dataset_id.set(None)
        _current_workflow_id.set(None)
