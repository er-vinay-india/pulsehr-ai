"""Audit ledger tracking every MCP tool invocation across Highview AI.

Enforces complete traceability:
- execution_id
- tool_name & caller
- dataset_id & workspace_id
- arguments_hash (SHA-256)
- evidence_ids & provenance_ids
- governance_status (PASS, DENIED, FLAGGED)
- duration_ms, success, error_code
"""
from __future__ import annotations

import logging
import threading
import time
from uuid import uuid4
from typing import Any
from pydantic import BaseModel, ConfigDict, Field

from .contracts import GovernanceStatus

logger = logging.getLogger(__name__)


class MCPExecutionRecord(BaseModel):
    """Immutable audit record for a single MCP tool execution."""
    model_config = ConfigDict(extra="ignore")

    execution_id: str = Field(default_factory=lambda: f"mcp-exec-{uuid4().hex[:12]}")
    tool_name: str
    caller: str
    dataset_id: int | str | None = None
    workspace_id: str | None = None
    arguments_hash: str
    evidence_ids: list[str] = Field(default_factory=list)
    provenance_ids: list[str] = Field(default_factory=list)
    governance_status: GovernanceStatus = GovernanceStatus.PASS
    started_at: float = Field(default_factory=time.time)
    duration_ms: float = 0.0
    success: bool = True
    error_code: str | None = None


class MCPExecutionLedger:
    """Thread-safe in-memory ledger storing MCP execution records."""

    def __init__(self, max_records: int = 2000):
        self._records: list[MCPExecutionRecord] = []
        self._records_by_id: dict[str, MCPExecutionRecord] = {}
        self._max_records = max_records
        self._lock = threading.Lock()

    def record_execution(
        self,
        tool_name: str,
        caller: str,
        arguments_hash: str,
        duration_ms: float,
        success: bool,
        dataset_id: int | str | None = None,
        workspace_id: str | None = None,
        evidence_ids: list[str] | None = None,
        provenance_ids: list[str] | None = None,
        governance_status: GovernanceStatus = GovernanceStatus.PASS,
        error_code: str | None = None,
        execution_id: str | None = None,
    ) -> MCPExecutionRecord:
        """Records an execution into the ledger."""
        rec = MCPExecutionRecord(
            execution_id=execution_id or f"mcp-exec-{uuid4().hex[:12]}",
            tool_name=tool_name,
            caller=caller,
            dataset_id=dataset_id,
            workspace_id=workspace_id,
            arguments_hash=arguments_hash,
            evidence_ids=evidence_ids or [],
            provenance_ids=provenance_ids or [],
            governance_status=governance_status,
            started_at=time.time(),
            duration_ms=duration_ms,
            success=success,
            error_code=error_code,
        )

        with self._lock:
            self._records.append(rec)
            self._records_by_id[rec.execution_id] = rec
            if len(self._records) > self._max_records:
                oldest = self._records.pop(0)
                self._records_by_id.pop(oldest.execution_id, None)

        return rec

    def get_record(self, execution_id: str) -> MCPExecutionRecord | None:
        """Fetches a specific execution record by ID."""
        with self._lock:
            return self._records_by_id.get(execution_id)

    def list_records(
        self,
        dataset_id: int | str | None = None,
        tool_name: str | None = None,
        caller: str | None = None,
        limit: int = 50,
    ) -> list[MCPExecutionRecord]:
        """Queries historical execution records with optional filtering."""
        with self._lock:
            filtered = self._records[:]

        if dataset_id is not None:
            filtered = [r for r in filtered if str(r.dataset_id) == str(dataset_id)]
        if tool_name is not None:
            filtered = [r for r in filtered if r.tool_name == tool_name]
        if caller is not None:
            filtered = [r for r in filtered if r.caller == caller]

        return filtered[-limit:]

    def clear_for_test(self) -> None:
        """Resets the ledger state for isolated test execution."""
        with self._lock:
            self._records.clear()
            self._records_by_id.clear()


mcp_execution_ledger = MCPExecutionLedger()
