"""AdaptiveTableReconstruction: Document-to-Table Reconstruction Intelligence Layer.

Reconstructs clean, source-faithful logical tables from messy enterprise/government
spreadsheets and CSV reports with multi-row headers, preambles, wrapped physical rows,
and footnote sentinels prior to dataframe creation and semantic profiling.
Features governed model-assisted structural reasoning (ModelEscalator) with strict post-validation.
"""

from .contracts import (
    AmbiguityCase,
    AmbiguityType,
    ContinuationDecision,
    ContinuationType,
    DecisionStatus,
    HeaderNode,
    HeaderTree,
    IntegrityGateResult,
    ModelContinuationDecision,
    ModelEscalationTelemetry,
    ModelHeaderDecision,
    ModelResolutionAudit,
    ModelRowRoleDecision,
    ModelSentinelDecision,
    ModelTableBoundaryDecision,
    ReconstructionProvenance,
    RowRole,
    RowRoleDecision,
    SentinelDefinition,
    StructuralComplexityScore,
    TableReconstructionResult,
)
from .continuation_detector import ContinuationDetector, LogicalRecordReconstructor
from .engine import AdaptiveTableReconstructionEngine
from .grid_capture import GridCapture, RawGrid
from .header_tree_builder import HeaderTreeBuilder
from .model_escalator import ModelEscalator
from .row_role_classifier import RowRoleClassifier
from .sentinel_resolver import SentinelResolver
from .structural_validator import StructuralValidator

__all__ = [
    "AdaptiveTableReconstructionEngine",
    "TableReconstructionResult",
    "StructuralComplexityScore",
    "ReconstructionProvenance",
    "SentinelDefinition",
    "RowRole",
    "RowRoleDecision",
    "HeaderTree",
    "HeaderNode",
    "ContinuationDecision",
    "ContinuationType",
    "AmbiguityCase",
    "AmbiguityType",
    "DecisionStatus",
    "ModelEscalationTelemetry",
    "ModelResolutionAudit",
    "ModelContinuationDecision",
    "ModelSentinelDecision",
    "ModelHeaderDecision",
    "ModelRowRoleDecision",
    "ModelTableBoundaryDecision",
    "ModelEscalator",
    "IntegrityGateResult",
    "GridCapture",
    "RawGrid",
    "HeaderTreeBuilder",
    "RowRoleClassifier",
    "ContinuationDetector",
    "LogicalRecordReconstructor",
    "SentinelResolver",
    "StructuralValidator",
]
