"""Typed Pydantic contracts for AdaptiveTableReconstructionEngine.

Enforces strict schemas for all structural decisions, provenance tracking,
sentinel extraction, ambiguity gating, model escalation, and integrity validation gates.
"""

from enum import Enum
from typing import Any, Dict, List, Optional, Union
from pydantic import BaseModel, Field, model_validator


class RowRole(str, Enum):
    DOCUMENT_METADATA = "DOCUMENT_METADATA"      # Document codes, reference IDs, export metadata at top
    TITLE = "TITLE"                              # Sheet or report titles above the table
    HEADER = "HEADER"                            # Primary or multi-row header rows
    HEADER_CONTINUATION = "HEADER_CONTINUATION"  # Sub-headers forming the header hierarchy
    DATA = "DATA"                                # Standard complete data rows
    DATA_CONTINUATION = "DATA_CONTINUATION"      # Wrapped/split physical row belonging to an adjacent record
    PAGE_HEADER = "PAGE_HEADER"                  # Repeated document header/watermark embedded inside data
    FOOTNOTE = "FOOTNOTE"                        # Trailing explanatory notes or disclaimer text
    SENTINEL_DEFINITION = "SENTINEL_DEFINITION"  # Footnotes explicitly defining sentinel missing codes
    BLANK_SEPARATOR = "BLANK_SEPARATOR"          # Completely blank rows
    UNKNOWN = "UNKNOWN"                          # Ambiguous row requiring model resolution or human review


class ContinuationType(str, Enum):
    PREFIX_OF_NEXT_ROW = "PREFIX_OF_NEXT_ROW"          # Continuation fragment prefixes the next data row
    SUFFIX_OF_PREVIOUS_ROW = "SUFFIX_OF_PREVIOUS_ROW"  # Continuation fragment suffixes the preceding row
    INDEPENDENT = "INDEPENDENT"                        # Not a continuation


class AmbiguityType(str, Enum):
    ROW_ROLE = "ROW_ROLE"
    HEADER_BOUNDARY = "HEADER_BOUNDARY"
    HEADER_HIERARCHY = "HEADER_HIERARCHY"
    ROW_CONTINUATION = "ROW_CONTINUATION"
    TABLE_BOUNDARY = "TABLE_BOUNDARY"
    SENTINEL_MEANING = "SENTINEL_MEANING"
    COLUMN_ALIGNMENT = "COLUMN_ALIGNMENT"
    MULTI_TABLE_SPLIT = "MULTI_TABLE_SPLIT"


class DecisionStatus(str, Enum):
    DETERMINISTIC_VALIDATED = "DETERMINISTIC_VALIDATED"
    VALIDATED = "DETERMINISTIC_VALIDATED"  # Backward-compatible alias
    MODEL_ASSISTED_VALIDATED = "MODEL_ASSISTED_VALIDATED"
    MODEL_ASSISTED_PROPOSED = "MODEL_ASSISTED_PROPOSED"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"
    REJECTED = "REJECTED"


class CanonicalMissingState(str, Enum):
    NOT_MONITORED = "NOT_MONITORED"
    NOT_REPORTED = "NOT_REPORTED"
    NOT_EVALUATED = "NOT_EVALUATED"
    NOT_APPLICABLE = "NOT_APPLICABLE"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"
    NOT_AVAILABLE = "NOT_AVAILABLE"
    MISSING = "MISSING"
    UNKNOWN_MISSING_STATE = "UNKNOWN_MISSING_STATE"


class ReconstructionRiskLevel(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class FieldSemanticRole(str, Enum):
    IDENTIFIER = "IDENTIFIER"      # e.g., employee_id, s_no, pk (CRITICAL RISK if altered/merged)
    MEASURE = "MEASURE"            # e.g., salary, revenue, pollution ppm (HIGH RISK)
    DIMENSION = "DIMENSION"        # e.g., department, state, city (MEDIUM RISK)
    TIMESTAMP = "TIMESTAMP"        # e.g., date, year, month (HIGH/CRITICAL RISK)
    FREE_TEXT = "FREE_TEXT"        # e.g., notes, descriptions, remarks (MEDIUM/LOW RISK)


class ReconstructionConfidence(BaseModel):
    structural_confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    semantic_confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    source_fidelity_confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    composite_confidence: float = Field(default=1.0, ge=0.0, le=1.0)


class RowRoleDecision(BaseModel):
    row_index: int
    role: RowRole
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    reason: str = ""
    features: Dict[str, Any] = Field(default_factory=dict)
    requires_review: bool = False


class HeaderNode(BaseModel):
    col_index: int
    row_indices: List[int]
    raw_tokens: List[str]
    normalized_name: str
    display_name: str


class HeaderTree(BaseModel):
    header_row_indices: List[int]
    columns: List[HeaderNode]
    column_names: List[str]
    normalized_columns: List[str]
    col_index_to_name: Dict[int, str] = Field(default_factory=dict)


class ContinuationDecision(BaseModel):
    continuation_row_index: int
    target_row_index: int
    continuation_type: ContinuationType
    affected_col_indices: List[int]
    merge_strategy: str  # e.g. "concat_no_space", "concat_with_space"
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    reason: str = ""
    requires_review: bool = False


class SentinelDefinition(BaseModel):
    token: str
    meaning: str
    source_row_index: int
    canonical_state: CanonicalMissingState = CanonicalMissingState.MISSING
    is_missing_indicator: bool = True
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)


class StructuralComplexityScore(BaseModel):
    score: float = Field(ge=0.0, le=1.0)
    is_complex: bool
    recommended_pipeline: str  # "FAST_DETERMINISTIC", "VALIDATED_DETERMINISTIC", "MODEL_ASSISTED", "ESCALATED"
    factors: Dict[str, float] = Field(default_factory=dict)


class ReconstructionProvenance(BaseModel):
    provenance_id: str  # e.g. "ATR-0001", "ATR-MDL-0001"
    operation: str      # "PRUNE_PREAMBLE", "MERGE_HEADER_HIERARCHY", "MERGE_WRAPPED_RECORD", "MODEL_ASSISTED_RESOLUTION", etc.
    source_rows: List[int]
    target_row: Optional[int] = None
    affected_columns: List[Union[int, str]] = Field(default_factory=list)
    before_state: Any = None
    after_state: Any = None
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    method: str = "DETERMINISTIC"  # "DETERMINISTIC" or "MODEL_ASSISTED"
    requires_review: bool = False
    status: DecisionStatus = DecisionStatus.VALIDATED
    explanation: str = ""


class IntegrityGateResult(BaseModel):
    gate_name: str
    passed: bool
    metrics: Dict[str, Any] = Field(default_factory=dict)
    warnings: List[str] = Field(default_factory=list)


# --- Phase 2: Model Escalation Contracts ---

class AmbiguityCase(BaseModel):
    case_id: str
    ambiguity_type: AmbiguityType
    current_row_index: int
    current_row: List[str]
    previous_rows: List[List[str]] = Field(default_factory=list)
    next_rows: List[List[str]] = Field(default_factory=list)
    provisional_schema: List[str] = Field(default_factory=list)
    expected_column_types: List[str] = Field(default_factory=list)
    deterministic_candidates: List[str] = Field(default_factory=list)
    deterministic_confidence: float = 0.5
    context_window_text: str = ""


class ModelRowRoleDecision(BaseModel):
    role: RowRole
    confidence: float = Field(ge=0.0, le=1.0)
    reason: str
    evidence: List[str] = Field(default_factory=list)


class ModelContinuationDecision(BaseModel):
    relationship: ContinuationType
    target_row_index: Optional[int] = None
    target_column_index: Optional[int] = None
    reconstructed_value: Optional[str] = None
    confidence: float = Field(ge=0.0, le=1.0)
    evidence: List[str] = Field(default_factory=list)

    @model_validator(mode="before")
    @classmethod
    def normalize_aliases(cls, data: Any) -> Any:
        if isinstance(data, dict):
            if "relationship" not in data:
                if data.get("is_continuation") is False:
                    data["relationship"] = ContinuationType.INDEPENDENT
                elif data.get("is_prefix") or data.get("type") == "prefix":
                    data["relationship"] = ContinuationType.PREFIX_OF_NEXT_ROW
                elif data.get("is_suffix") or data.get("type") == "suffix":
                    data["relationship"] = ContinuationType.SUFFIX_OF_PREVIOUS_ROW
                else:
                    data["relationship"] = ContinuationType.INDEPENDENT
            if "confidence" not in data:
                data["confidence"] = float(data.get("score") or data.get("certainty") or 0.85)
        return data


class ModelHeaderDecision(BaseModel):
    is_header: bool
    header_level: int = 1
    canonical_name: str
    confidence: float = Field(ge=0.0, le=1.0)
    evidence: List[str] = Field(default_factory=list)


class ModelSentinelDecision(BaseModel):
    token: str
    meaning: str
    is_missing_indicator: bool = True
    confidence: float = Field(ge=0.0, le=1.0)
    evidence: List[str] = Field(default_factory=list)


class ModelTableBoundaryDecision(BaseModel):
    is_table_boundary: bool
    boundary_kind: str  # "START", "END", "SECTION_DIVIDER"
    confidence: float = Field(ge=0.0, le=1.0)
    evidence: List[str] = Field(default_factory=list)


class ModelResolutionAudit(BaseModel):
    case_id: str
    ambiguity_type: AmbiguityType
    source_rows: List[int]
    deterministic_confidence: float
    model_name: str
    model_confidence: float
    model_decision: Dict[str, Any]
    post_validation_passed: bool
    final_status: DecisionStatus
    validation_notes: str = ""


class ModelEscalationTelemetry(BaseModel):
    model_calls: int = 0
    model_tokens: int = 0
    model_latency_ms: float = 0.0
    ambiguities_detected: int = 0
    ambiguities_resolved: int = 0
    ambiguities_unresolved: int = 0
    review_required_count: int = 0
    false_merge_prevented: int = 0
    models_used: List[str] = Field(default_factory=list)


class TableReconstructionResult(BaseModel):
    raw_row_count: int
    raw_col_count: int
    reconstructed_row_count: int
    reconstructed_col_count: int
    complexity: StructuralComplexityScore
    header_tree: Optional[HeaderTree] = None
    sentinels: List[SentinelDefinition] = Field(default_factory=list)
    provenance: List[ReconstructionProvenance] = Field(default_factory=list)
    integrity_gates: List[IntegrityGateResult] = Field(default_factory=list)
    metadata_extracted: Dict[str, Any] = Field(default_factory=dict)
    telemetry: ModelEscalationTelemetry = Field(default_factory=ModelEscalationTelemetry)
    audits: List[ModelResolutionAudit] = Field(default_factory=list)
    confidence_vector: Optional[ReconstructionConfidence] = None
    risk_level: ReconstructionRiskLevel = ReconstructionRiskLevel.LOW
    status: DecisionStatus = DecisionStatus.VALIDATED
    reconstructed_df: Optional[Any] = None

    class Config:
        arbitrary_types_allowed = True
