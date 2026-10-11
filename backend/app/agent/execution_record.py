"""Provenance and execution ledger for HRIDAY LangGraph workflows (Phase C).

Tracks:
- workflow_id & request_id
- nodes_executed sequence
- tools_called & evidence_ids / scenario_ids gathered
- models_used via ModelGateway
- approvals requested and decisions made
- latencies, step counts, and final workflow status
"""
from __future__ import annotations

import enum
import threading
import time
from uuid import uuid4
from typing import Any
from pydantic import BaseModel, ConfigDict, Field


class WorkflowStatus(str, enum.Enum):
    """Lifecycle status of a LangGraph workflow execution."""
    COMPLETED = "COMPLETED"
    PARTIAL = "PARTIAL"
    DENIED = "DENIED"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"
    FAILED_SAFE = "FAILED_SAFE"


class WorkflowExecutionRecord(BaseModel):
    """Immutable audit record for a single LangGraph workflow execution."""
    model_config = ConfigDict(extra="ignore")

    workflow_id: str = Field(default_factory=lambda: f"wf-{uuid4().hex[:12]}")
    workflow_name: str
    request_id: str
    dataset_id: int | str | None = None

    nodes_executed: list[str] = Field(default_factory=list)
    tools_called: list[str] = Field(default_factory=list)
    evidence_ids: list[str] = Field(default_factory=list)
    scenario_ids: list[str] = Field(default_factory=list)
    models_used: list[str] = Field(default_factory=list)
    approvals: list[dict[str, Any]] = Field(default_factory=list)

    total_latency_ms: float = 0.0
    tool_call_count: int = 0
    model_call_count: int = 0

    final_status: WorkflowStatus = WorkflowStatus.COMPLETED
    started_at: float = Field(default_factory=time.time)
    completed_at: float = Field(default_factory=time.time)


class WorkflowExecutionLedger:
    """Thread-safe in-memory ledger storing LangGraph workflow execution records."""

    def __init__(self, max_records: int = 1000):
        self._records: list[WorkflowExecutionRecord] = []
        self._records_by_id: dict[str, WorkflowExecutionRecord] = {}
        self._max_records = max_records
        self._lock = threading.Lock()

    def record_workflow(self, record: WorkflowExecutionRecord) -> WorkflowExecutionRecord:
        """Stores a workflow execution record into the ledger."""
        with self._lock:
            self._records.append(record)
            self._records_by_id[record.workflow_id] = record
            if len(self._records) > self._max_records:
                oldest = self._records.pop(0)
                self._records_by_id.pop(oldest.workflow_id, None)
        return record

    def get_record(self, workflow_id: str) -> WorkflowExecutionRecord | None:
        """Retrieves a workflow execution record by ID."""
        with self._lock:
            return self._records_by_id.get(workflow_id)

    def list_records(
        self,
        dataset_id: int | str | None = None,
        workflow_name: str | None = None,
        limit: int = 50,
    ) -> list[WorkflowExecutionRecord]:
        """Lists historical records with optional filtering."""
        with self._lock:
            filtered = self._records[:]

        if dataset_id is not None:
            filtered = [r for r in filtered if str(r.dataset_id) == str(dataset_id)]
        if workflow_name is not None:
            filtered = [r for r in filtered if r.workflow_name == workflow_name]

        return filtered[-limit:]

    def clear_for_test(self) -> None:
        """Resets ledger state for isolated test execution."""
        with self._lock:
            self._records.clear()
            self._records_by_id.clear()


workflow_execution_ledger = WorkflowExecutionLedger()
