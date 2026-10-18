"""
HighView Ingestion V2 — Shadow Orchestration & Public Milestone Contract
Stages: 12 Internal Intelligence Stages & 10 Public Visible Progress Groups
Boundary: Shadow execution harness and milestone mapping.
CRITICAL SAFETY RULE:
consumer_cutover_allowed is HARDCODED to False in Phase I1.
V1 remains 100% authoritative for production consumers.
"""

from enum import Enum
from typing import Any
from pydantic import BaseModel, ConfigDict, Field
from app.services.ingestion_v2.contracts.base import IngestionContractBase


class InternalStage(str, Enum):
    RAW_INGESTION = "RAW_INGESTION"                                     # Stage 1
    ADAPTIVE_RECONSTRUCTION = "ADAPTIVE_RECONSTRUCTION"                 # Stage 2
    SANITIZATION_NORMALIZATION = "SANITIZATION_NORMALIZATION"           # Stage 3
    STRUCTURAL_PROFILING_EDA_A = "STRUCTURAL_PROFILING_EDA_A"           # Stage 4
    SEMANTIC_MODELING_GRAIN = "SEMANTIC_MODELING_GRAIN"                 # Stage 5
    RELATIONSHIP_DISCOVERY = "RELATIONSHIP_DISCOVERY"                   # Stage 6
    RELATIONSHIP_VALIDATION_JOIN_PLAN = "RELATIONSHIP_VALIDATION_JOIN_PLAN"  # Stage 7
    ANALYTICAL_EDA_B = "ANALYTICAL_EDA_B"                               # Stage 8
    CONTROLLED_ENRICHMENT = "CONTROLLED_ENRICHMENT"                     # Stage 9
    SEMANTIC_GRAPH = "SEMANTIC_GRAPH"                                   # Stage 10
    VECTORIZATION_INDEXING = "VECTORIZATION_INDEXING"                   # Stage 11
    CONTEXT_RECONCILIATION_PREWARM = "CONTEXT_RECONCILIATION_PREWARM"   # Stage 12


class PublicProgressGroup(str, Enum):
    STAGE_1_FILE_RECEIVED = "FILE_RECEIVED"
    STAGE_2_STRUCTURE_DETECTED = "STRUCTURE_DETECTED"
    STAGE_3_TYPES_NORMALIZED = "TYPES_NORMALIZED"
    STAGE_4_DATA_PROFILED = "DATA_PROFILED"
    STAGE_5_ENTITIES_RESOLVED = "ENTITIES_RESOLVED"
    STAGE_6_RELATIONSHIPS_DISCOVERED = "RELATIONSHIPS_DISCOVERED"
    STAGE_7_RELATIONSHIPS_VERIFIED = "RELATIONSHIPS_VERIFIED"
    STAGE_8_STATISTICS_COMPUTED = "STATISTICS_COMPUTED"
    STAGE_9_KNOWLEDGE_GRAPH_BUILT = "KNOWLEDGE_GRAPH_BUILT"
    STAGE_10_READY = "READY"


# Mapping from 12 internal epistemic stages to 10 public SSE milestones
INTERNAL_TO_PUBLIC_STAGE_MAP: dict[InternalStage, PublicProgressGroup] = {
    InternalStage.RAW_INGESTION: PublicProgressGroup.STAGE_1_FILE_RECEIVED,
    InternalStage.ADAPTIVE_RECONSTRUCTION: PublicProgressGroup.STAGE_2_STRUCTURE_DETECTED,
    InternalStage.SANITIZATION_NORMALIZATION: PublicProgressGroup.STAGE_3_TYPES_NORMALIZED,
    InternalStage.STRUCTURAL_PROFILING_EDA_A: PublicProgressGroup.STAGE_4_DATA_PROFILED,
    InternalStage.SEMANTIC_MODELING_GRAIN: PublicProgressGroup.STAGE_5_ENTITIES_RESOLVED,
    InternalStage.RELATIONSHIP_DISCOVERY: PublicProgressGroup.STAGE_6_RELATIONSHIPS_DISCOVERED,
    InternalStage.RELATIONSHIP_VALIDATION_JOIN_PLAN: PublicProgressGroup.STAGE_7_RELATIONSHIPS_VERIFIED,
    InternalStage.ANALYTICAL_EDA_B: PublicProgressGroup.STAGE_8_STATISTICS_COMPUTED,
    InternalStage.CONTROLLED_ENRICHMENT: PublicProgressGroup.STAGE_8_STATISTICS_COMPUTED,
    InternalStage.SEMANTIC_GRAPH: PublicProgressGroup.STAGE_9_KNOWLEDGE_GRAPH_BUILT,
    InternalStage.VECTORIZATION_INDEXING: PublicProgressGroup.STAGE_9_KNOWLEDGE_GRAPH_BUILT,
    InternalStage.CONTEXT_RECONCILIATION_PREWARM: PublicProgressGroup.STAGE_10_READY,
}


class WorkspaceIntelligenceContext(IngestionContractBase):
    """
    Stage 12 Contract: Context Reconciliation + Pre-Warm.
    Reconciles all stages into pre-warmed context for Dashboards / HRIDAY / Presentation.
    """
    stage_name: str = "context_reconciliation_prewarm"

    summary_stats: dict[str, Any] = Field(default_factory=dict)
    active_tables: list[str] = Field(default_factory=list)
    top_metrics: list[str] = Field(default_factory=list)
    is_prewarmed: bool = True


class ShadowExecutionStatus(str, Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    DISAGREEMENT_DETECTED = "DISAGREEMENT_DETECTED"


class ShadowPipelineRun(BaseModel):
    """
    Metadata for a shadow pipeline execution.
    Maintains complete isolation from production V1 state.
    """
    model_config = ConfigDict(extra="forbid", frozen=True)

    shadow_run_id: str
    v1_dataset_id: str
    v1_run_id: str
    status: ShadowExecutionStatus = ShadowExecutionStatus.PENDING

    current_internal_stage: InternalStage | None = None
    completed_internal_stages: list[InternalStage] = Field(default_factory=list)

    # SAFETY FIREWALL: Hardcoded to False. Absolutely no production cutover allowed in Phase I1.
    consumer_cutover_allowed: bool = False

    stage_fingerprints: dict[str, str] = Field(default_factory=dict)
    execution_start_utc: str
    execution_end_utc: str | None = None
    total_duration_ms: float | None = None
    error_message: str | None = None
