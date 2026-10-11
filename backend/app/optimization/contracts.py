"""Pydantic contracts and schemas for Governed Adaptive Optimization (Phase E).

Enforces:
1. Immutable policy versions and clear separation of ACTIVE from CANDIDATE.
2. Structured optimization recommendations grounded in Phase D telemetry.
3. Offline policy benchmarking and safety regression gates.
4. Shadow evaluation without duplicate external mutations.
"""
from __future__ import annotations

import enum
import time
from uuid import uuid4
from typing import Any, Literal
from pydantic import BaseModel, ConfigDict, Field


class PolicyStatus(str, enum.Enum):
    """Lifecycle status of an immutable optimization policy."""
    ACTIVE = "ACTIVE"
    CANDIDATE = "CANDIDATE"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    RETIRED = "RETIRED"


class RecommendationCategory(str, enum.Enum):
    """Classification of optimization recommendations."""
    WORKFLOW = "WORKFLOW"
    TOOL_SELECTION = "TOOL_SELECTION"
    MODEL_ROUTING = "MODEL_ROUTING"
    LATENCY = "LATENCY"
    EVIDENCE_POLICY = "EVIDENCE_POLICY"
    RETRY_POLICY = "RETRY_POLICY"
    FALLBACK_POLICY = "FALLBACK_POLICY"


class RiskLevel(str, enum.Enum):
    """Risk tiers for candidate modifications."""
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class WorkflowPolicy(BaseModel):
    """Configures intent-to-workflow mapping and node traversal bounds."""
    model_config = ConfigDict(extra="ignore")

    intent_workflow_map: dict[str, str] = Field(default_factory=lambda: {
        "DATA_LOOKUP": "quick_answer",
        "RANKING": "quick_answer",
        "COMPARISON": "quick_answer",
        "TREND": "quick_answer",
        "RELATIONSHIP": "quick_answer",
        "SCENARIO_ANALYSIS": "scenario_analysis",
        "PRESENTATION_CREATION": "presentation_creation",
        "MULTI_STEP_ANALYSIS": "analytical_investigation",
    })
    max_workflow_steps: int = 16
    enable_early_exit_on_sufficiency: bool = True


class ToolSelectionPolicy(BaseModel):
    """Defines default planned tools and pruning rules per intent."""
    model_config = ConfigDict(extra="ignore")

    default_tools_by_intent: dict[str, list[str]] = Field(default_factory=lambda: {
        "DATA_LOOKUP": ["calculate_distribution"],
        "RANKING": ["rank_entities"],
        "COMPARISON": ["compare_segments"],
        "TREND": ["get_trend"],
        "RELATIONSHIP": ["analyze_relationship"],
        "SCENARIO_ANALYSIS": ["get_valid_levers", "run_counterfactual"],
        "PRESENTATION_CREATION": ["rank_entities", "create_deck"],
        "MULTI_STEP_ANALYSIS": ["compare_segments", "analyze_relationship", "verify_claim"],
    })
    max_tool_calls_per_query: int = 10
    parallel_execution_candidates: list[list[str]] = Field(default_factory=lambda: [
        ["calculate_distribution", "get_trend"],
        ["compare_segments", "analyze_relationship"],
    ])


class ModelRoutingPolicy(BaseModel):
    """Governed model cascade priorities per AI task type."""
    model_config = ConfigDict(extra="ignore")

    cascades: dict[str, list[str]] = Field(default_factory=lambda: {
        "STRUCTURAL_AI": ["phi4-mini:latest", "qwen3.5:2b", "llama3.1:8b"],
        "SEMANTIC_AI": ["qwen3.5:2b", "phi4-mini:latest", "qwen3.5:9b"],
        "NARRATIVE_AI": ["gemma4:12b", "qwen3.5:9b", "phi4-mini:latest"],
        "AGENTIC_AI": ["qwen3.5:9b", "gemma4:12b", "phi4-mini:latest"],
        "PRESENTATION_AI": ["gemma4:12b", "qwen3.5:9b", "phi4-mini:latest"],
        "DETERMINISTIC_CALCULATION": [],
    })


class EvidencePolicy(BaseModel):
    """Rules governing evidence grounding and verification deduplication."""
    model_config = ConfigDict(extra="ignore")

    mandatory_grounding_rate: float = 1.0
    deduplicate_certified_determinations: bool = True
    prohibit_causal_verbs: bool = True


class LatencyPolicy(BaseModel):
    """Per-workflow latency SLA targets in milliseconds."""
    model_config = ConfigDict(extra="ignore")

    quick_answer_p95_ms: float = 1500.0
    investigation_p95_ms: float = 6000.0
    scenario_p95_ms: float = 8000.0
    presentation_p95_ms: float = 20000.0


class RetryPolicy(BaseModel):
    """Defines retry limits and early fallback behavior."""
    model_config = ConfigDict(extra="ignore")

    max_same_tool_calls: int = 3
    max_node_retries: int = 2
    early_fallback_on_model_timeout: bool = True


class HighviewPolicy(BaseModel):
    """Immutable policy snapshot defining Highview runtime execution rules."""
    model_config = ConfigDict(extra="ignore")

    policy_id: str = Field(default_factory=lambda: f"POLICY-{time.strftime('%Y-%m')}-{uuid4().hex[:6].upper()}")
    version_number: int = 1
    name: str = "Standard Governed Highview Policy"
    description: str = "Default production baseline policy"

    status: PolicyStatus = PolicyStatus.ACTIVE
    created_at: float = Field(default_factory=time.time)
    created_by: str = "system"
    parent_policy_id: str | None = None

    approval_status: str = "APPROVED"
    approved_by: str | None = "system_init"
    approved_at: float | None = Field(default_factory=time.time)
    benchmark_result_id: str | None = None

    workflow_policy: WorkflowPolicy = Field(default_factory=WorkflowPolicy)
    tool_policy: ToolSelectionPolicy = Field(default_factory=ToolSelectionPolicy)
    model_routing_policy: ModelRoutingPolicy = Field(default_factory=ModelRoutingPolicy)
    evidence_policy: EvidencePolicy = Field(default_factory=EvidencePolicy)
    latency_policy: LatencyPolicy = Field(default_factory=LatencyPolicy)
    retry_policy: RetryPolicy = Field(default_factory=RetryPolicy)


class OptimizationRecommendation(BaseModel):
    """Structured candidate modification proposal derived from Phase D telemetry."""
    model_config = ConfigDict(extra="ignore")

    recommendation_id: str = Field(default_factory=lambda: f"rec-{uuid4().hex[:8]}")
    category: RecommendationCategory
    current_policy_id: str
    proposed_policy_delta: dict[str, Any] = Field(default_factory=dict)

    evidence_trace_ids: list[str] = Field(default_factory=list)
    reason: str
    expected_improvement: str
    risk_level: RiskLevel = RiskLevel.LOW

    benchmark_required: bool = True
    human_approval_required: bool = True
    status: Literal["PENDING", "BENCHMARKED", "APPROVED", "REJECTED", "PROMOTED"] = "PENDING"
    created_at: float = Field(default_factory=time.time)


class PolicyComparisonResult(BaseModel):
    """Outcome of offline benchmark comparison between active and candidate policies."""
    model_config = ConfigDict(extra="ignore")

    baseline_policy_id: str
    candidate_policy_id: str

    quality_delta: float = 0.0
    latency_delta_ms: float = 0.0
    compute_delta: float = 0.0
    tool_efficiency_delta: float = 0.0
    grounding_delta: float = 0.0
    governance_delta: float = 0.0

    hard_safety_gates_passed: bool = True
    regressions: list[str] = Field(default_factory=list)
    improvements: list[str] = Field(default_factory=list)

    recommendation: Literal["PROMOTE", "REJECT", "REVIEW"] = "REVIEW"
    rationale: str = ""


class ShadowEvaluation(BaseModel):
    """Comparison of candidate policy execution in shadow mode alongside production."""
    model_config = ConfigDict(extra="ignore")

    evaluation_id: str = Field(default_factory=lambda: f"shd-{uuid4().hex[:8]}")
    trace_id: str
    active_policy_id: str
    candidate_policy_id: str

    active_workflow_decision: str
    candidate_workflow_decision: str

    active_tools: list[str] = Field(default_factory=list)
    candidate_tools: list[str] = Field(default_factory=list)

    active_model: str
    candidate_model: str

    active_latency_ms: float
    candidate_latency_ms: float

    active_quality_score: float
    candidate_quality_score: float

    differences: list[str] = Field(default_factory=list)
    side_effects_skipped: bool = True
    evaluated_at: float = Field(default_factory=time.time)
