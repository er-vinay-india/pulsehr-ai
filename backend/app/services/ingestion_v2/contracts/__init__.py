"""
HighView Ingestion V2 — Contracts Package
Exports all typed, frozen contracts for Ingestion Intelligence V2.
"""

from app.services.ingestion_v2.contracts.provenance import SourceCoordinateRef
from app.services.ingestion_v2.contracts.base import (
    IngestionContractBase,
    compute_stage_fingerprint,
)
from app.services.ingestion_v2.contracts.raw import (
    PhysicalSheet,
    RawIngestionResult,
)
from app.services.ingestion_v2.contracts.reconstruction import (
    ReconstructionStatus,
    PhysicalCellCoord,
    LogicalColumnHeader,
    LogicalTable,
    ReconstructedDataset,
)
from app.services.ingestion_v2.contracts.normalization import (
    CanonicalPhysicalType,
    NormalizationRule,
    NormalizedFieldLineage,
    NormalizedColumn,
    NormalizedTable,
    NormalizedDataset,
)
from app.services.ingestion_v2.contracts.profiling import (
    StructuralDataQuality,
    ColumnStructuralProfile,
    TableStructuralProfile,
    StructuralProfile,
)
from app.services.ingestion_v2.contracts.semantics import (
    SemanticColumnRole,
    SemanticEntityType,
    ClassificationSource,
    SemanticColumnAssignment,
    TableSemanticModel,
    SemanticModel,
)
from app.services.ingestion_v2.contracts.grain import (
    CanonicalGrain,
    TemporalGrain,
    TableGrainProfile,
    GrainProfile,
)
from app.services.ingestion_v2.contracts.relationships import (
    CandidateKeyType,
    RelationshipCardinality,
    RelationshipStatus,
    RelationshipCandidate,
    RelationshipCandidateSet,
    ValidatedRelationshipEdge,
    ValidatedRelationshipGraph,
)
from app.services.ingestion_v2.contracts.joins import (
    JoinSafetyStatus,
    MeasureAdditivity,
    PreAggregationSpec,
    JoinSafetyAssessment,
    JoinPlan,
    GovernedJoinPlanSet,
)
from app.services.ingestion_v2.contracts.analytics import (
    OutlierMethod,
    FindingType,
    NullPolicy,
    TukeyIqrEvidence,
    HypothesisTestEvidence,
    StatisticalTestEvidence,
    AnalyticalReliability,
    AnalyticalFinding,
    AnalyticalProfile,
)
from app.services.ingestion_v2.contracts.enrichment import (
    MetricScope,
    LocalDerivedMetric,
    RelationalDerivedMetric,
    EnrichedDataset,
)
from app.services.ingestion_v2.contracts.semantic_graph import (
    GraphNodeType,
    GraphEdgeType,
    SemanticGraphNode,
    SemanticGraphEdge,
    SemanticGraph,
)
from app.services.ingestion_v2.contracts.retrieval import (
    RetrievalNamespace,
    IndexedDocumentRef,
    MultiNamespaceRetrievalManifest,
)
from app.services.ingestion_v2.contracts.intent import (
    IntentFocusDomain,
    TargetPersona,
    AnalysisIntent,
)
from app.services.ingestion_v2.contracts.shadow import (
    InternalStage,
    PublicProgressGroup,
    INTERNAL_TO_PUBLIC_STAGE_MAP,
    WorkspaceIntelligenceContext,
    ShadowExecutionStatus,
    ShadowPipelineRun,
)
from app.services.ingestion_v2.contracts.disagreement import (
    ComparisonClass,
    DisagreementType,
    Severity,
    ReviewStatus,
    PipelineDisagreementRecord,
    PipelineDisagreementLedger,
)

__all__ = [
    # Provenance & Base
    "SourceCoordinateRef",
    "IngestionContractBase",
    "compute_stage_fingerprint",
    # Stage 1: Raw
    "PhysicalSheet",
    "RawIngestionResult",
    # Stage 2: Reconstruction
    "ReconstructionStatus",
    "PhysicalCellCoord",
    "LogicalColumnHeader",
    "LogicalTable",
    "ReconstructedDataset",
    # Stage 3: Normalization
    "CanonicalPhysicalType",
    "NormalizationRule",
    "NormalizedFieldLineage",
    "NormalizedColumn",
    "NormalizedTable",
    "NormalizedDataset",
    # Stage 4: Profiling (EDA-A)
    "StructuralDataQuality",
    "ColumnStructuralProfile",
    "TableStructuralProfile",
    "StructuralProfile",
    # Stage 5: Semantics & Grain
    "SemanticColumnRole",
    "SemanticEntityType",
    "ClassificationSource",
    "SemanticColumnAssignment",
    "TableSemanticModel",
    "SemanticModel",
    "CanonicalGrain",
    "TemporalGrain",
    "TableGrainProfile",
    "GrainProfile",
    # Stage 6 & 7: Relationships & Joins
    "CandidateKeyType",
    "RelationshipCardinality",
    "RelationshipStatus",
    "RelationshipCandidate",
    "RelationshipCandidateSet",
    "ValidatedRelationshipEdge",
    "ValidatedRelationshipGraph",
    "JoinSafetyStatus",
    "MeasureAdditivity",
    "PreAggregationSpec",
    "JoinSafetyAssessment",
    "JoinPlan",
    "GovernedJoinPlanSet",
    # Stage 8: Analytics (EDA-B)
    "OutlierMethod",
    "FindingType",
    "NullPolicy",
    "TukeyIqrEvidence",
    "HypothesisTestEvidence",
    "StatisticalTestEvidence",
    "AnalyticalReliability",
    "AnalyticalFinding",
    "AnalyticalProfile",
    # Stage 9: Enrichment
    "MetricScope",
    "LocalDerivedMetric",
    "RelationalDerivedMetric",
    "EnrichedDataset",
    # Stage 10: Semantic Graph
    "GraphNodeType",
    "GraphEdgeType",
    "SemanticGraphNode",
    "SemanticGraphEdge",
    "SemanticGraph",
    # Stage 11: Retrieval
    "RetrievalNamespace",
    "IndexedDocumentRef",
    "MultiNamespaceRetrievalManifest",
    # Intent
    "IntentFocusDomain",
    "TargetPersona",
    "AnalysisIntent",
    # Shadow & Public Milestones
    "InternalStage",
    "PublicProgressGroup",
    "INTERNAL_TO_PUBLIC_STAGE_MAP",
    "WorkspaceIntelligenceContext",
    "ShadowExecutionStatus",
    "ShadowPipelineRun",
    # Disagreement Ledger
    "ComparisonClass",
    "DisagreementType",
    "Severity",
    "ReviewStatus",
    "PipelineDisagreementRecord",
    "PipelineDisagreementLedger",
]
