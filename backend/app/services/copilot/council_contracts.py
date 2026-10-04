"""Pydantic council contracts governing HighView / HRIDAY AI Council communication.

Provides strictly-typed models for:
- CouncilPlan: Structured query intent and parameters (Qwen -> Granite / Executor)
- RetrievalRequest: Dataset-scoped metadata filtering for semantic retrieval (Granite -> RAG / Nomic)
- RetrievedEvidence: Normalized chunk/finding from hybrid search (RAG -> Council)
- CalculationResult: Deterministic mathematical evaluation across full population (Engine -> Council)
- CriticReview: Conflict arbitration and claim auditing (DeepSeek -> Gemma / Granite)
- EvidenceItem: Unified evidence model wrapping calculation, retrieval, facts, and conversation state
- ModelRoutingDecision: Structured capability assignment and fallback routing
"""

from enum import Enum
from typing import Any, Literal
from pydantic import BaseModel, ConfigDict, Field


class TaskType(str, Enum):
    ANALYTICAL_CALCULATION = "ANALYTICAL_CALCULATION"
    FACT_RETRIEVAL = "FACT_RETRIEVAL"
    HYBRID_ANALYSIS = "HYBRID_ANALYSIS"
    FOLLOW_UP_REFINEMENT = "FOLLOW_UP_REFINEMENT"
    CONCEPTUAL_EXPLANATION = "CONCEPTUAL_EXPLANATION"
    AMBIGUITY_CLARIFICATION = "AMBIGUITY_CLARIFICATION"
    GENERAL_CHAT = "GENERAL_CHAT"


class EntityGrain(str, Enum):
    EMPLOYEE = "employee"
    DEPARTMENT = "department"
    STORE = "store"
    GLOBAL = "global"
    STUDENT = "student"
    CUSTOMER = "customer"
    RECORD = "record"
    INDIVIDUAL = "individual"


class OperationType(str, Enum):
    RANK = "rank"
    SUM = "sum"
    MEAN = "mean"
    COUNT = "count"
    FILTER = "filter"
    COMPARE = "compare"
    CORRELATE = "correlate"
    BREAKDOWN = "breakdown"


class EvidenceType(str, Enum):
    CALCULATION = "CALCULATION"
    RETRIEVED_KNOWLEDGE = "RETRIEVED_KNOWLEDGE"
    CONVERSATION_STATE = "CONVERSATION_STATE"
    DOMAIN_GOVERNANCE = "DOMAIN_GOVERNANCE"


class CouncilPlan(BaseModel):
    """Structured plan emitted by Qwen 3.5 and consumed by Granite Orchestrator and Calculation Engine."""
    model_config = ConfigDict(extra="ignore")

    task_type: TaskType = TaskType.ANALYTICAL_CALCULATION
    entity_grain: EntityGrain = EntityGrain.DEPARTMENT
    metric: str | None = Field(default=None, description="Primary column name or metric to evaluate")
    secondary_metric: str | None = Field(default=None, description="Optional secondary metric for comparisons/correlation")
    operation: OperationType = OperationType.RANK
    direction: Literal["lowest", "highest", "all"] = "lowest"
    ranking_limit: int = Field(default=10, ge=1, le=100)
    additional_fields: list[str] = Field(default_factory=list, description="Descriptive columns like Department or Approved Leaves")
    threshold_operator: Literal["<", "<=", ">", ">=", "==", None] = None
    threshold_value: float | None = None
    requires_rag: bool = False
    requires_calculation: bool = True
    retrieval_topics: list[str] = Field(default_factory=list, description="Semantic topics for RAG retrieval")
    explanation: str = Field(default="", description="Rationale for selected plan parameters")


class RetrievalRequest(BaseModel):
    """Scoped query specification passed to Nomic / Hybrid RAG."""
    model_config = ConfigDict(extra="ignore")

    query: str
    dataset_id: int | None = None
    sheet_id: int | None = None
    entity_grain: EntityGrain | None = None
    metric: str | None = None
    source_types: list[str] = Field(
        default_factory=lambda: ["verified_finding", "column_schema", "tabular_chunk"]
    )
    max_results: int = Field(default=5, ge=1, le=20)
    min_relevance_score: float = Field(default=0.50, ge=0.0, le=1.0)


class RetrievedEvidence(BaseModel):
    """Normalized evidence item returned by RAG search."""
    model_config = ConfigDict(extra="ignore")

    evidence_id: str
    content: str
    source_type: str
    dataset_id: int | None = None
    sheet_id: int | None = None
    entity_grain: EntityGrain | None = None
    metric: str | None = None
    relevance_score: float = Field(ge=0.0, le=1.0)
    confidence: float | None = Field(default=1.0, ge=0.0, le=1.0)
    source_reference: str
    is_stale: bool = False


class CalculationResult(BaseModel):
    """Strictly-typed output of the deterministic analytical executor."""
    model_config = ConfigDict(extra="ignore")

    status: Literal["success", "metric_missing", "identifier_missing", "ambiguity_clarification_required"] = "success"
    dataset_id: int | None = None
    sheet_id: int | None = None
    entity_grain: EntityGrain = EntityGrain.DEPARTMENT
    metric: str
    direction: Literal["lowest", "highest", "all"] = "lowest"
    columns: list[str] = Field(default_factory=list)
    rows: list[dict[str, Any]] = Field(default_factory=list)
    row_count: int = 0
    distinct_entities: int = 0
    missing_records_excluded: int = 0
    snapshot_hash: str = "unversioned"
    calculation_method: str = ""
    warnings: list[str] = Field(default_factory=list)


class EvidenceItem(BaseModel):
    """Unified evidence container shared across all AI Council delegates."""
    model_config = ConfigDict(extra="ignore")

    evidence_type: EvidenceType
    source_id: str
    dataset_id: int | None = None
    sheet_id: int | None = None
    entity_grain: EntityGrain | None = None
    metric: str | None = None
    content: Any
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    provenance: dict[str, Any] = Field(default_factory=dict)


class CriticReview(BaseModel):
    """Auditing and conflict evaluation produced by DeepSeek-R1."""
    model_config = ConfigDict(extra="ignore")

    conflict_detected: bool = False
    grain_consistent: bool = True
    calculation_supported: bool = True
    discrepancy_details: str | None = None
    preferred_evidence_source: Literal["calculation", "retrieval", "unresolved"] = "calculation"
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    mandatory_caveats: list[str] = Field(default_factory=list)


class ModelRoutingDecision(BaseModel):
    """Structured routing decision logged by the central ModelRouter."""
    model_config = ConfigDict(extra="ignore")

    capability: str
    primary_model: str
    fallback_models: list[str] = Field(default_factory=list)
    reason: str
