"""Lightweight HighviewAgentState for HRIDAY LangGraph Orchestration (Phase C).

Enforces:
1. Pointer-based state: Stores IDs (dataset_id, evidence_ids, scenario_ids, provenance_ids).
   Never contains raw DataFrames, SQL query results, or bulk tables.
2. Complete serializability for interrupt, pause, resume, and audit ledgers.
3. Strict separation of empirical observations (evidence_ids) from simulated
   counterfactuals (scenario_ids).
"""
from __future__ import annotations

from uuid import uuid4
from typing import Any
from pydantic import BaseModel, ConfigDict, Field


class HighviewAgentState(BaseModel):
    """Universal state container passed between LangGraph nodes."""
    model_config = ConfigDict(extra="ignore")

    conversation_id: str = Field(default_factory=lambda: f"conv-{uuid4().hex[:10]}")
    request_id: str = Field(default_factory=lambda: f"req-{uuid4().hex[:10]}")

    dataset_id: int | str | None = None
    workspace_id: str | None = None

    user_query: str = ""
    intent: str = "UNKNOWN"

    active_filters: dict[str, Any] = Field(default_factory=dict)
    selected_entities: list[str] = Field(default_factory=list)
    selected_measures: list[str] = Field(default_factory=list)

    # Invariant: absolute separation of observed truth from counterfactual projections
    evidence_ids: list[str] = Field(default_factory=list)   # Empirical facts (EVID-xxx)
    scenario_ids: list[str] = Field(default_factory=list)   # Counterfactual simulations (SCEN-xxx)
    provenance_ids: list[str] = Field(default_factory=list) # Snapshot / calculation audit tokens

    verified_claims: list[str] = Field(default_factory=list)
    rejected_claims: list[str] = Field(default_factory=list)

    tool_history: list[dict[str, Any]] = Field(default_factory=list)

    pending_approval: dict[str, Any] | None = None
    final_answer: str | None = None
    workflow_status: str = "IN_PROGRESS"  # COMPLETED, PARTIAL, DENIED, REVIEW_REQUIRED, FAILED_SAFE

    step_count: int = 0
    error: str | None = None
