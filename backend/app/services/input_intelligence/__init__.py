"""Input, Context & Ingestion Intelligence Package.

Provides:
- WorkspaceContext & UserIntentContext canonical contracts
- DataProfiler (deterministic profiling, hygiene scoring, PII scanning)
- SemanticClassifier (semantic column roles, units, domain inference, time intelligence)
- MultiSheetIntelligence (workbook intelligence, candidate join detection)
- UserIntentEngine (intent precedence, question-to-data mapping, readiness)
- SnapshotManager (immutable snapshots, cache invalidation, incremental updates)
- MemoryIntegrationBridge (Phase 1 Semantic Memory indexing without raw PII)
- WorkspaceToPresentationAdapter (WorkspaceContext -> PresentationPlanningContext)
- InputIntelligenceService (unified master entry point)
"""

from .models import (
    AlignmentStatus,
    AnalysisReadiness,
    ColumnProfile,
    ContextSummary,
    DataQualityIssue,
    DataQualityProfile,
    DatasetProfile,
    IngestionSnapshot,
    InferredDomain,
    IntentStatus,
    IssueSeverity,
    JoinCardinality,
    OutputIntent,
    OverrideAuditRecord,
    ProvenanceOrigin,
    QuestionDataMapping,
    ReadinessStatus,
    RelationshipCandidate,
    SemanticColumnRole,
    SemanticUnit,
    SourceItem,
    SourceRole,
    SourceType,
    TimeIntelligence,
    UserIntentContext,
    WorkbookContext,
    WorkspaceContext,
)
from .profiler import DataProfiler
from .classifier import SemanticClassifier
from .multi_sheet import MultiSheetIntelligence
from .intent_engine import UserIntentEngine
from .snapshot_manager import SnapshotManager
from .memory_bridge import MemoryIntegrationBridge
from .presentation_bridge import WorkspaceToPresentationAdapter
from .eda_bridge import EDAContextAdapter, EDAAnalysisContext
from .dashboard_bridge import DashboardContextAdapter, DashboardPlanningContext
from .service import InputIntelligenceService

__all__ = [
    "AlignmentStatus",
    "AnalysisReadiness",
    "ColumnProfile",
    "ContextSummary",
    "DataQualityIssue",
    "DataQualityProfile",
    "DatasetProfile",
    "IngestionSnapshot",
    "InferredDomain",
    "IntentStatus",
    "IssueSeverity",
    "JoinCardinality",
    "OutputIntent",
    "OverrideAuditRecord",
    "ProvenanceOrigin",
    "QuestionDataMapping",
    "ReadinessStatus",
    "RelationshipCandidate",
    "SemanticColumnRole",
    "SemanticUnit",
    "SourceItem",
    "SourceRole",
    "SourceType",
    "TimeIntelligence",
    "UserIntentContext",
    "WorkbookContext",
    "WorkspaceContext",
    "DataProfiler",
    "SemanticClassifier",
    "MultiSheetIntelligence",
    "UserIntentEngine",
    "SnapshotManager",
    "MemoryIntegrationBridge",
    "WorkspaceToPresentationAdapter",
    "EDAContextAdapter",
    "EDAAnalysisContext",
    "DashboardContextAdapter",
    "DashboardPlanningContext",
    "InputIntelligenceService",
]
