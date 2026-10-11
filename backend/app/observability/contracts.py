"""Pydantic contracts and schemas for AI Observability, Evaluation & Runtime Intelligence (Phase D).

Unifies:
- AITrace: Unified correlated trace container across LangGraph, MCP, and ModelGateway.
- NodeExecutionMetric: Granular step-level execution metrics.
- WorkflowLatencyBudget: Latency target thresholds and SLA compliance.
- Evaluation contracts:
  - IntentAlignmentEvaluation
  - ToolSelectionQuality
  - GroundingEvaluation
  - ClaimAttribution
  - CausalLanguageEvaluation
  - EvidenceQualityEvaluation
  - ModelRoutingEvaluation
  - ComputeCostMetric
  - GovernanceHealthSummary
  - WorkflowOutcomeEvaluation
  - RuntimeQualityScore
  - RuntimeAnomaly
"""
from __future__ import annotations

import enum
import time
from uuid import uuid4
from typing import Any, Literal
from pydantic import BaseModel, ConfigDict, Field


class NodeExecutionMetric(BaseModel):
    """Detailed step-level execution metrics for a single LangGraph node."""
    model_config = ConfigDict(extra="ignore")

    node_name: str
    started_at: float = Field(default_factory=time.time)
    duration_ms: float = 0.0

    input_pointer_count: int = 0
    output_pointer_count: int = 0

    tool_calls: list[str] = Field(default_factory=list)
    model_calls: list[str] = Field(default_factory=list)

    retries: int = 0
    status: str = "SUCCESS"  # SUCCESS, RETRIED, PAUSED, FAILED


class ClaimType(str, enum.Enum):
    """Epistemological claim categories."""
    OBSERVED = "OBSERVED"
    ASSOCIATED = "ASSOCIATED"
    INFERRED = "INFERRED"
    SCENARIO = "SCENARIO"
    CAUSAL = "CAUSAL"


class ClaimAttribution(BaseModel):
    """Sentence-level factual attribution and provenance grounding."""
    model_config = ConfigDict(extra="ignore")

    claim_id: str = Field(default_factory=lambda: f"clm-{uuid4().hex[:8]}")
    text: str
    claim_type: ClaimType = ClaimType.OBSERVED
    evidence_ids: list[str] = Field(default_factory=list)
    scenario_ids: list[str] = Field(default_factory=list)
    verification_status: Literal["VERIFIED", "UNVERIFIED", "REJECTED", "REWRITTEN"] = "VERIFIED"


class IntentAlignmentEvaluation(BaseModel):
    """Evaluates whether agent intent and tool sequence matched user inquiry."""
    model_config = ConfigDict(extra="ignore")

    detected_intent: str
    expected_intent: str | None = None
    workflow_selected: str
    expected_workflow: str | None = None
    tools_selected: list[str] = Field(default_factory=list)
    expected_tools: list[str] = Field(default_factory=list)

    alignment_score: float = 1.0  # 0.0 to 1.0
    unnecessary_tools: list[str] = Field(default_factory=list)
    missing_tools: list[str] = Field(default_factory=list)


class ToolSelectionQuality(BaseModel):
    """Evaluates tool selection precision, redundancy, and efficiency."""
    model_config = ConfigDict(extra="ignore")

    workflow_name: str
    total_tool_calls: int = 0
    useful_tool_calls: int = 0
    tool_precision: float = 1.0
    tool_recall: float = 1.0
    unnecessary_tool_rate: float = 0.0
    duplicate_tool_rate: float = 0.0
    same_tool_retry_rate: float = 0.0


class GroundingEvaluation(BaseModel):
    """Evaluates whether all analytical assertions map strictly to verified evidence."""
    model_config = ConfigDict(extra="ignore")

    factual_claim_count: int = 0
    evid_grounded_claims: int = 0
    scen_grounded_claims: int = 0
    ungrounded_claims: int = 0
    conflicting_claims: int = 0

    grounding_rate: float = 1.0  # Target: 1.0 (100%)
    is_fully_grounded: bool = True


class CausalLanguageEvaluation(BaseModel):
    """Tracks causal verb assertions and enforcement of associational rewrites."""
    model_config = ConfigDict(extra="ignore")

    causal_claims_attempted: int = 0
    causal_claims_allowed: int = 0
    causal_claims_rewritten: int = 0
    causal_claims_blocked: int = 0
    causal_overclaim_rate: float = 0.0


class EvidenceQualityEvaluation(BaseModel):
    """Evaluates sufficiency and diversity of gathered evidence."""
    model_config = ConfigDict(extra="ignore")

    evidence_count: int = 0
    evidence_types: list[str] = Field(default_factory=list)
    evidence_sufficiency_score: float = 1.0
    missing_evidence_types: list[str] = Field(default_factory=list)
    is_sufficient: bool = True


class ModelRoutingEvaluation(BaseModel):
    """Evaluates model selection efficiency, token economics, and fallback usage."""
    model_config = ConfigDict(extra="ignore")

    task_type: str
    primary_model: str
    actual_model: str
    fallback_used: bool = False
    latency_ms: float = 0.0
    token_count: int = 0
    structured_output_valid: bool = True
    routing_efficiency_score: float = 1.0


class ComputeCostMetric(BaseModel):
    """Hardware and compute utilization metric for local model execution."""
    model_config = ConfigDict(extra="ignore")

    input_tokens: int = 0
    output_tokens: int = 0
    latency_ms: float = 0.0
    estimated_cpu_seconds: float = 0.0
    estimated_gpu_seconds: float = 0.0


class GovernanceHealthSummary(BaseModel):
    """Summary of governance gates, isolation checks, denials, and approvals."""
    model_config = ConfigDict(extra="ignore")

    governance_checks: int = 0
    governance_denials: int = 0
    governance_flags: int = 0

    dataset_scope_denials: int = 0
    claim_entitlement_denials: int = 0
    scenario_entitlement_denials: int = 0

    approval_requested: int = 0
    approval_granted: int = 0
    approval_rejected: int = 0

    failed_safe_count: int = 0


class WorkflowOutcomeEvaluation(BaseModel):
    """Evaluates terminal execution quality and satisfaction of user inquiry."""
    model_config = ConfigDict(extra="ignore")

    status: str = "COMPLETED"
    completed: bool = True
    partial: bool = False
    denied: bool = False
    review_required: bool = False
    failed_safe: bool = False

    evidence_grounded: bool = True
    user_request_satisfied: bool = True
    unnecessary_steps: int = 0
    overall_score: float = 1.0


class RuntimeQualityScore(BaseModel):
    """Composite weighted score evaluating runtime performance and governance."""
    model_config = ConfigDict(extra="ignore")

    grounding_score: float = 1.0            # 25% weight
    intent_alignment_score: float = 1.0     # 20% weight
    tool_efficiency_score: float = 1.0      # 15% weight
    workflow_completion_score: float = 1.0  # 15% weight
    governance_correctness_score: float = 1.0 # 10% weight
    latency_efficiency_score: float = 1.0   # 10% weight
    model_routing_efficiency_score: float = 1.0 # 5% weight

    overall_quality_score: float = 1.0      # Weighted composite: 0.0 - 1.0

    @classmethod
    def calculate(
        cls,
        grounding: float,
        intent_alignment: float,
        tool_efficiency: float,
        workflow_completion: float,
        governance_correctness: float,
        latency_efficiency: float,
        model_routing_efficiency: float,
    ) -> RuntimeQualityScore:
        overall = (
            0.25 * grounding
            + 0.20 * intent_alignment
            + 0.15 * tool_efficiency
            + 0.15 * workflow_completion
            + 0.10 * governance_correctness
            + 0.10 * latency_efficiency
            + 0.05 * model_routing_efficiency
        )
        return cls(
            grounding_score=round(grounding, 3),
            intent_alignment_score=round(intent_alignment, 3),
            tool_efficiency_score=round(tool_efficiency, 3),
            workflow_completion_score=round(workflow_completion, 3),
            governance_correctness_score=round(governance_correctness, 3),
            latency_efficiency_score=round(latency_efficiency, 3),
            model_routing_efficiency_score=round(model_routing_efficiency, 3),
            overall_quality_score=round(overall, 3),
        )


class RuntimeAnomaly(BaseModel):
    """Deterministic alert for unusual runtime behavior or policy breach."""
    model_config = ConfigDict(extra="ignore")

    anomaly_id: str = Field(default_factory=lambda: f"anom-{uuid4().hex[:8]}")
    anomaly_type: str
    severity: Literal["LOW", "MEDIUM", "HIGH", "CRITICAL"] = "MEDIUM"
    message: str
    trace_id: str | None = None
    detected_at: float = Field(default_factory=time.time)


class AITrace(BaseModel):
    """Unified correlated trace uniting Workflow, MCP, and ModelGateway executions."""
    model_config = ConfigDict(extra="ignore")

    trace_id: str = Field(default_factory=lambda: f"trace-{uuid4().hex[:12]}")
    request_id: str
    conversation_id: str

    dataset_id: int | str | None = None
    workspace_id: str | None = None

    workflow_id: str | None = None
    workflow_type: str | None = None

    started_at: float = Field(default_factory=time.time)
    completed_at: float = Field(default_factory=time.time)
    total_latency_ms: float = 0.0

    status: str = "COMPLETED"  # COMPLETED, PARTIAL, DENIED, REVIEW_REQUIRED, FAILED_SAFE

    nodes: list[NodeExecutionMetric] = Field(default_factory=list)
    tools: list[dict[str, Any]] = Field(default_factory=list)
    model_calls: list[dict[str, Any]] = Field(default_factory=list)

    evidence_ids: list[str] = Field(default_factory=list)
    scenario_ids: list[str] = Field(default_factory=list)
    provenance_ids: list[str] = Field(default_factory=list)

    approvals: list[dict[str, Any]] = Field(default_factory=list)
    attributions: list[ClaimAttribution] = Field(default_factory=list)

    evaluation_summary: dict[str, Any] = Field(default_factory=dict)
    anomalies: list[RuntimeAnomaly] = Field(default_factory=list)
    privacy_sanitized: bool = True
