"""
HighView Ingestion V2 — Pipeline Disagreement Ledger Contract
Stage: Cross-Cutting Shadow Validation & Disagreement Auditing
Boundary: Captures and classifies behavioral differences between V1 and V2.

Encodes BOTH:
1. ComparisonClass (Macro Evaluation Layer):
   - UNCHANGED: Must match V1 (row fidelity, source provenance, frontend contracts, evidence bindings)
   - EXPECTED_IMPROVEMENT: Measurable V2 superiority (relationship precision, join safety, semantic role accuracy)
   - EXPECTED_DIFFERENCE: Intentional divergence (V1 unsafe joins rejected by V2, low confidence yielding AMBIGUOUS)

2. DisagreementType (Micro Governance & Cutover Layer):
   - EXPECTED_FIX: Defect in V1 corrected by V2 (e.g., rejecting invalid self-referential or Cartesian joins)
   - EXPECTED_REFACTOR: Architectural or structural representation change with identical analytical truth
   - REGRESSION: Loss of valid capability, loss of valid relationship, or erroneous calculation
   - UNRESOLVED: Unclassified or unknown divergence (defaults to UNRESOLVED, blocks cutover if critical)
"""

from enum import Enum
from typing import Any
from pydantic import BaseModel, ConfigDict, Field
from app.services.ingestion_v2.contracts.base import IngestionContractBase


class ComparisonClass(str, Enum):
    UNCHANGED = "UNCHANGED"
    EXPECTED_IMPROVEMENT = "EXPECTED_IMPROVEMENT"
    EXPECTED_DIFFERENCE = "EXPECTED_DIFFERENCE"


class DisagreementType(str, Enum):
    EXPECTED_FIX = "EXPECTED_FIX"
    EXPECTED_REFACTOR = "EXPECTED_REFACTOR"
    REGRESSION = "REGRESSION"
    UNRESOLVED = "UNRESOLVED"


class Severity(str, Enum):
    INFO = "INFO"
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"
    BLOCKER = "BLOCKER"


class ReviewStatus(str, Enum):
    OPEN = "OPEN"
    RESOLVED = "RESOLVED"
    ACCEPTED_DIFFERENCE = "ACCEPTED_DIFFERENCE"
    IGNORED = "IGNORED"


class PipelineDisagreementRecord(BaseModel):
    """
    Individual disagreement record documenting a divergence between V1 and V2 outputs.
    Combines ComparisonClass and DisagreementType to provide full cutover governance.
    """
    model_config = ConfigDict(extra="forbid", frozen=True)

    disagreement_id: str
    shadow_run_id: str
    dataset_id: str
    comparison_class: ComparisonClass
    disagreement_type: DisagreementType = DisagreementType.UNRESOLVED
    severity: Severity = Severity.WARNING

    category: str | None = None  # e.g., "RELATIONSHIP", "SCHEMA", "GRAIN", "METRIC", "OUTLIER"
    target_table_id: str | None = None
    target_column_id: str | None = None
    target_metric_id: str | None = None

    v1_value: Any | None = None
    v2_value: Any | None = None
    difference_summary: str
    architectural_rationale: str

    review_status: ReviewStatus = ReviewStatus.OPEN
    reviewed_by: str | None = None
    review_notes: str | None = None


class PipelineDisagreementLedger(IngestionContractBase):
    """
    Contract for the Disagreement Ledger capturing all divergences in a shadow run.
    Critical REGRESSION or critical UNRESOLVED records explicitly block cutover.
    """
    stage_name: str = "pipeline_disagreement_ledger"

    shadow_run_id: str
    records: list[PipelineDisagreementRecord] = Field(default_factory=list)

    # Class counts
    total_unchanged_violations: int = 0
    total_expected_improvements: int = 0
    total_expected_differences: int = 0

    # Type counts
    total_expected_fixes: int = 0
    total_expected_refactors: int = 0
    total_regressions: int = 0
    total_unresolved: int = 0

    # Cutover governance
    blocks_cutover: bool = False
    requires_human_review: bool = False
