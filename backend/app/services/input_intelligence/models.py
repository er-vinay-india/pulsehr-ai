"""Canonical Input, Context & Ingestion Intelligence Data Contracts.

Defines the complete schemas for:
- WorkspaceContext (canonical entry contract)
- UserIntentContext (first-class user intent, questions, constraints)
- SourceItem & SourceRole (source abstraction and role classification)
- DatasetProfile & ColumnProfile (deterministic structured profiling)
- SemanticColumnRole & SemanticUnit (semantic type classification)
- InferredDomain & DomainInferenceResult (multi-signal cautious domain detection)
- WorkbookContext & RelationshipCandidate (multi-sheet and join intelligence)
- DataQualityProfile & AnalysisReadiness (data hygiene and analysis readiness)
- QuestionDataMapping (intent + data alignment)
- IngestionSnapshot (immutable provenance and version tracking)
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Literal
from pydantic import BaseModel, Field


# =============================================================================
# ENUMS
# =============================================================================

class SourceType(str, Enum):
    """Supported input source formats."""
    CSV = "csv"
    EXCEL = "excel"
    MULTI_SHEET_EXCEL = "multi_sheet_excel"
    JSON = "json"
    PDF = "pdf"
    DOCX = "docx"
    PPTX = "pptx"
    TEXT = "text"
    MARKDOWN = "markdown"
    IMAGE = "image"
    DATASET = "dataset"
    ARTIFACT = "artifact"
    UNKNOWN = "unknown"


class SourceRole(str, Enum):
    """Analytical role assigned to an input source."""
    PRIMARY_DATA = "PRIMARY_DATA"
    SUPPORTING_DATA = "SUPPORTING_DATA"
    REFERENCE_DOCUMENT = "REFERENCE_DOCUMENT"
    POLICY_DOCUMENT = "POLICY_DOCUMENT"
    HISTORICAL_REPORT = "HISTORICAL_REPORT"
    PREVIOUS_PRESENTATION = "PREVIOUS_PRESENTATION"
    BRAND_GUIDELINE = "BRAND_GUIDELINE"
    USER_NOTES = "USER_NOTES"
    UNKNOWN = "UNKNOWN"


class SemanticColumnRole(str, Enum):
    """Semantic role of a data column determined through name, type, and distribution."""
    IDENTIFIER = "IDENTIFIER"
    DATE = "DATE"
    TIME = "TIME"
    CATEGORY = "CATEGORY"
    METRIC = "METRIC"
    PERCENTAGE = "PERCENTAGE"
    CURRENCY = "CURRENCY"
    BOOLEAN = "BOOLEAN"
    TEXT = "TEXT"
    STATUS = "STATUS"
    LOCATION = "LOCATION"
    PERSON = "PERSON"
    ORGANIZATION = "ORGANIZATION"
    TARGET = "TARGET"
    ACTUAL = "ACTUAL"
    BENCHMARK = "BENCHMARK"
    UNKNOWN = "UNKNOWN"


class SemanticUnit(str, Enum):
    """Detected numerical or measurement unit."""
    CURRENCY = "currency"
    PERCENTAGE = "percentage"
    COUNT = "count"
    DURATION = "duration"
    RATE = "rate"
    RATIO = "ratio"
    DISTANCE = "distance"
    STORAGE = "storage"
    DATE = "date"
    UNKNOWN = "unknown"


class InferredDomain(str, Enum):
    """Inferred domain context."""
    HR_WORKFORCE = "Workforce Operations"
    SALES = "Commercial Sales"
    FINANCE = "Corporate Finance"
    OPERATIONS = "Business Operations"
    SUPPLY_CHAIN = "Supply Chain & Logistics"
    SOFTWARE_ENGINEERING = "Software Engineering"
    INFRASTRUCTURE = "Cloud Infrastructure & SRE"
    RESEARCH = "Academic & Clinical Research"
    EDUCATION = "Education & Training"
    ENVIRONMENTAL = "Environmental & Public Health"
    GENERIC_ANALYTICS = "Generic Analytics"


class OutputIntent(str, Enum):
    """User's requested or intended output medium."""
    ANALYSIS = "ANALYSIS"
    DASHBOARD = "DASHBOARD"
    PRESENTATION = "PRESENTATION"
    REPORT = "REPORT"
    SUMMARY = "SUMMARY"
    TABLE = "TABLE"
    CHART = "CHART"
    UNKNOWN = "UNKNOWN"


class IntentStatus(str, Enum):
    """Status of user intent capture."""
    EXPLICIT = "EXPLICIT"
    INFERRED = "INFERRED"
    UNSPECIFIED = "UNSPECIFIED"


class ReadinessStatus(str, Enum):
    """Overall dataset readiness for business analysis."""
    READY = "READY"
    READY_WITH_WARNINGS = "READY_WITH_WARNINGS"
    NEEDS_MAPPING = "NEEDS_MAPPING"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"
    UNSUPPORTED = "UNSUPPORTED"


class AlignmentStatus(str, Enum):
    """Question or intent alignment against data capabilities."""
    SUPPORTED = "SUPPORTED"
    PARTIALLY_SUPPORTED = "PARTIALLY_SUPPORTED"
    UNSUPPORTED = "UNSUPPORTED"


class JoinCardinality(str, Enum):
    """Cardinality of detected cross-dataset or cross-sheet relationships."""
    ONE_TO_ONE = "ONE_TO_ONE"
    ONE_TO_MANY = "ONE_TO_MANY"
    MANY_TO_ONE = "MANY_TO_ONE"
    MANY_TO_MANY = "MANY_TO_MANY"


class IssueSeverity(str, Enum):
    """Severity level of data quality or readiness issues."""
    ERROR = "ERROR"
    WARNING = "WARNING"
    INFO = "INFO"


class ProvenanceOrigin(str, Enum):
    """Origin of a metadata or semantic property."""
    USER_EXPLICIT = "USER_EXPLICIT"
    USER_OVERRIDE = "USER_OVERRIDE"
    DATASET_DERIVED = "DATASET_DERIVED"
    INFERRED = "INFERRED"
    SYSTEM_DEFAULT = "SYSTEM_DEFAULT"


# =============================================================================
# DATA CONTRACTS
# =============================================================================

class SourceItem(BaseModel):
    """Canonical representation of an ingested file, dataset, or document."""
    source_id: str
    source_type: SourceType
    filename: str
    original_name: str
    role: SourceRole = SourceRole.UNKNOWN
    status: str = "ready"  # ready, processing, error
    file_hash: str = ""
    size_bytes: int = 0
    sheet_count: int = 1
    metadata: dict[str, Any] = Field(default_factory=dict)


class ColumnProfile(BaseModel):
    """Deterministic profile and semantic classification of a single data column."""
    name: str
    original_name: str
    data_type: str  # numeric, string, date, boolean
    semantic_role: SemanticColumnRole = SemanticColumnRole.UNKNOWN
    semantic_unit: SemanticUnit = SemanticUnit.UNKNOWN
    null_count: int = 0
    null_pct: float = 0.0
    unique_count: int = 0
    sample_values: list[Any] = Field(default_factory=list)
    min_val: Any = None
    max_val: Any = None
    mean_val: float | None = None
    cardinality: int = 0
    is_identifier_candidate: bool = False
    is_metric_candidate: bool = False
    is_dimension_candidate: bool = False
    is_time_candidate: bool = False
    is_sensitive: bool = False
    sensitivity_reason: str | None = None
    confidence: float = 1.0
    provenance: ProvenanceOrigin = ProvenanceOrigin.DATASET_DERIVED


class DatasetProfile(BaseModel):
    """Comprehensive deterministic profile of a structured dataset or sheet."""
    dataset_id: str
    name: str
    original_name: str
    row_count: int
    col_count: int
    columns: list[ColumnProfile] = Field(default_factory=list)
    duplicate_row_count: int = 0
    duplicate_rate: float = 0.0
    date_range: dict[str, Any] | None = None
    numeric_ranges: dict[str, dict[str, Any]] = Field(default_factory=dict)
    categorical_cardinality: dict[str, int] = Field(default_factory=dict)
    primary_keys: list[str] = Field(default_factory=list)
    metric_candidates: list[str] = Field(default_factory=list)
    dimension_candidates: list[str] = Field(default_factory=list)
    time_candidates: list[str] = Field(default_factory=list)
    sensitive_columns: list[str] = Field(default_factory=list)
    representative_samples: list[dict[str, Any]] = Field(default_factory=list)

    @property
    def sample_rows(self) -> list[dict[str, Any]]:
        return self.representative_samples


class RelationshipCandidate(BaseModel):
    """Candidate relationship or join path between two datasets/sheets."""
    relationship_id: str
    left_dataset_id: str
    left_column: str
    right_dataset_id: str
    right_column: str
    cardinality: JoinCardinality = JoinCardinality.MANY_TO_ONE
    confidence: float = 0.0
    is_safe: bool = True
    evidence: str = ""


class WorkbookContext(BaseModel):
    """Multi-sheet Excel workbook intelligence."""
    workbook_name: str
    source_id: str
    sheet_profiles: list[DatasetProfile] = Field(default_factory=list)
    relationship_candidates: list[RelationshipCandidate] = Field(default_factory=list)
    primary_sheet_candidates: list[str] = Field(default_factory=list)
    reference_sheet_candidates: list[str] = Field(default_factory=list)


class DataQualityIssue(BaseModel):
    """Specific data quality defect identified during deterministic profiling."""
    issue_type: str
    severity: IssueSeverity = IssueSeverity.INFO
    column_name: str | None = None
    message: str
    count_affected: int = 0


class DataQualityProfile(BaseModel):
    """Data hygiene, missingness, and health audit."""
    dataset_id: str
    total_records: int = 0
    overall_health_score: float = 1.0  # 0.0 to 1.0
    missingness_rate: float = 0.0
    duplicate_rate: float = 0.0
    issues: list[DataQualityIssue] = Field(default_factory=list)


class AnalysisReadiness(BaseModel):
    """Assessment of whether dataset is ready for downstream analytical workflows."""
    status: ReadinessStatus = ReadinessStatus.READY
    is_ready: bool = True
    issues: list[str] = Field(default_factory=list)
    missing_prerequisites: list[str] = Field(default_factory=list)


class QuestionDataMapping(BaseModel):
    """Mapping of an explicit user question to required dataset concepts and availability."""
    question: str
    required_concepts: list[str] = Field(default_factory=list)
    mapped_fields: dict[str, str] = Field(default_factory=dict)
    unmapped_concepts: list[str] = Field(default_factory=list)
    alignment_status: AlignmentStatus = AlignmentStatus.SUPPORTED
    explanation: str = ""


class UserIntentContext(BaseModel):
    """First-class representation of user instructions, goals, and constraints."""
    raw_instruction: str = ""
    normalized_objective: str = ""
    explicit_questions: list[str] = Field(default_factory=list)
    expected_output: OutputIntent = OutputIntent.UNKNOWN
    audience: str | None = None
    decision_context: str | None = None
    analysis_focus: list[str] = Field(default_factory=list)
    excluded_topics: list[str] = Field(default_factory=list)
    time_period: str | None = None
    comparison_request: str | None = None
    output_constraints: list[str] = Field(default_factory=list)
    presentation_constraints: list[str] = Field(default_factory=list)
    intent_status: IntentStatus = IntentStatus.UNSPECIFIED
    possible_analysis_capabilities: list[str] = Field(default_factory=list)
    confidence: float = 1.0
    provenance: ProvenanceOrigin = ProvenanceOrigin.USER_EXPLICIT


class TimeIntelligence(BaseModel):
    """Time-series, periodicity, and date coverage metadata."""
    reporting_period: str = "Current Period"
    granularity: str = "unspecified"  # daily, weekly, monthly, quarterly, yearly
    min_date: str | None = None
    max_date: str | None = None
    is_partial_year: bool = False
    missing_periods: list[str] = Field(default_factory=list)
    comparable_periods: list[str] = Field(default_factory=list)


class ContextSummary(BaseModel):
    """Compact contextual overview suitable for logging and prompt injection."""
    domain: str = "Generic Analytics"
    primary_dataset: str = ""
    record_count: int = 0
    reporting_period: str = "Current Period"
    key_dimensions: list[str] = Field(default_factory=list)
    key_metrics: list[str] = Field(default_factory=list)
    user_goal: str = ""
    readiness_summary: str = "Ready"


class IngestionSnapshot(BaseModel):
    """Immutable snapshot metadata guaranteeing provenance across pipeline runs."""
    workspace_id: str
    snapshot_hash: str
    ingested_at: str
    source_hashes: dict[str, str] = Field(default_factory=dict)
    dataset_versions: dict[str, str] = Field(default_factory=dict)
    profile_version: str = "1.0"


class OverrideAuditRecord(BaseModel):
    """Audit record capturing changes made via user overrides."""
    field: str
    old_value: Any
    new_value: Any
    origin: ProvenanceOrigin = ProvenanceOrigin.USER_OVERRIDE
    timestamp: str
    notes: str | None = None


class WorkspaceContext(BaseModel):
    """Canonical top-level Input & Context Intelligence contract.
    
    Serves as the authoritative source of truth for downstream modules:
    EDA, Copilot, Analysis Briefs, Dashboards, and Presentation Planning.
    """
    workspace_id: str
    workspace_context_version: int = 1
    user_request: UserIntentContext = Field(default_factory=UserIntentContext)
    sources: list[SourceItem] = Field(default_factory=list)
    datasets: list[DatasetProfile] = Field(default_factory=list)
    documents: list[dict[str, Any]] = Field(default_factory=list)
    workbook_contexts: list[WorkbookContext] = Field(default_factory=list)
    relationships: list[RelationshipCandidate] = Field(default_factory=list)
    primary_dataset_id: str | None = None
    time_intelligence: TimeIntelligence = Field(default_factory=TimeIntelligence)
    context_summary: ContextSummary = Field(default_factory=ContextSummary)
    quality: DataQualityProfile | None = None
    readiness: AnalysisReadiness = Field(default_factory=AnalysisReadiness)
    question_mappings: list[QuestionDataMapping] = Field(default_factory=list)
    user_overrides: dict[str, Any] = Field(default_factory=dict)
    override_history: list[OverrideAuditRecord] = Field(default_factory=list)
    provenance: IngestionSnapshot | None = None
