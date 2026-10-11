"""Pydantic contracts and schemas for Highview Governed MCP Capability Layer (Phase B).

Defines:
- ToolRiskLevel (LOW, MEDIUM, HIGH, CRITICAL)
- GovernanceStatus (PASS, DENIED, FLAGGED)
- MCPToolRequest & MCPToolResponse common envelopes
- MCPToolDefinition metadata & entitlement constraints
- Typed Input & Output schemas for the 6 MCP capability groups:
    1. Dataset MCP
    2. Analytics MCP
    3. Evidence MCP
    4. Scenario MCP
    5. Presentation MCP
    6. Governance MCP
"""
from __future__ import annotations

import enum
import hashlib
import json
import time
from uuid import uuid4
from typing import Any, Generic, Literal, TypeVar
from pydantic import BaseModel, ConfigDict, Field


class ToolRiskLevel(str, enum.Enum):
    """Operational and decision impact risk classification for MCP tools."""
    LOW = "LOW"            # Read schema, metadata, descriptive metrics
    MEDIUM = "MEDIUM"      # Rankings, distributions, bivariate relationships
    HIGH = "HIGH"          # Counterfactual scenario simulations, deck generation
    CRITICAL = "CRITICAL"  # Cross-dataset linkage, approval actions, external mutations


class GovernanceStatus(str, enum.Enum):
    """Governance pre-flight evaluation status."""
    PASS = "PASS"
    DENIED = "DENIED"
    FLAGGED = "FLAGGED"


def compute_arguments_hash(args: dict[str, Any]) -> str:
    """Computes deterministic SHA-256 hash of arguments for execution ledger."""
    serialized = json.dumps(args, sort_keys=True, default=str)
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()[:16]


class MCPToolRequest(BaseModel):
    """Standardized envelope for every MCP tool invocation."""
    model_config = ConfigDict(extra="ignore")

    tool_name: str
    dataset_id: int | str | None = None
    workspace_id: str | None = None
    arguments: dict[str, Any] = Field(default_factory=dict)
    caller: str = "hriday"
    correlation_id: str = Field(default_factory=lambda: f"corr-{uuid4().hex[:10]}")
    requested_evidence_scope: list[str] | None = None


class MCPToolResponse(BaseModel):
    """Standardized audited outcome envelope returned by GovernedMCPGateway."""
    model_config = ConfigDict(extra="ignore")

    success: bool
    tool_name: str
    result: dict[str, Any] = Field(default_factory=dict)
    evidence_ids: list[str] = Field(default_factory=list)
    provenance_ids: list[str] = Field(default_factory=list)
    dataset_id: int | str | None = None
    execution_id: str
    governance_status: GovernanceStatus = GovernanceStatus.PASS
    warnings: list[str] = Field(default_factory=list)
    error_message: str | None = None


class MCPToolDefinition(BaseModel):
    """Static registration metadata and governance constraints for an MCP tool."""
    model_config = ConfigDict(arbitrary_types_allowed=True, extra="ignore")

    tool_name: str
    capability_group: Literal["dataset", "analytics", "evidence", "scenario", "presentation", "governance"]
    description: str
    input_schema: type[BaseModel]
    output_schema: type[BaseModel]
    risk_level: ToolRiskLevel = ToolRiskLevel.LOW
    requires_dataset_scope: bool = True
    requires_evidence: bool = False
    requires_human_approval: bool = False
    allows_cross_dataset: bool = False
    allows_scenario: bool = False
    read_only: bool = True


# =============================================================================
# 1. Dataset MCP Schemas
# =============================================================================

class GetSchemaInput(BaseModel):
    dataset_id: int | str

class SchemaColumnItem(BaseModel):
    name: str
    data_type: str
    semantic_role: str
    is_nullable: bool = True

class GetSchemaOutput(BaseModel):
    dataset_id: int | str
    sheet_name: str
    row_count: int
    column_count: int
    columns: list[SchemaColumnItem]


class GetEntitiesInput(BaseModel):
    dataset_id: int | str
    limit: int = 50

class EntityCohortItem(BaseModel):
    entity_name: str
    entity_type: str
    record_count: int

class GetEntitiesOutput(BaseModel):
    dataset_id: int | str
    total_entities: int
    entities: list[EntityCohortItem]


class GetMeasuresInput(BaseModel):
    dataset_id: int | str

class MeasureDescriptor(BaseModel):
    name: str
    semantic_role: str = "MEASURE"
    unit: str
    aggregation: str = "SUM"
    grain: str
    polarity: str = "NEUTRAL"

class GetMeasuresOutput(BaseModel):
    dataset_id: int | str
    measures: list[MeasureDescriptor]


class GetTimeDimensionsInput(BaseModel):
    dataset_id: int | str

class TimeDimensionItem(BaseModel):
    name: str
    has_temporal_points: bool
    cadence: str | None = None
    min_date: str | None = None
    max_date: str | None = None

class GetTimeDimensionsOutput(BaseModel):
    dataset_id: int | str
    has_temporal_data: bool
    time_dimensions: list[TimeDimensionItem]


class GetDatasetProfileInput(BaseModel):
    dataset_id: int | str

class GetDatasetProfileOutput(BaseModel):
    dataset_id: int | str
    domain: str
    governed_scenario_domain: str | None = None
    sheet_names: list[str]
    total_records: int
    hygiene_score: float


class GetRelationshipsInput(BaseModel):
    dataset_id: int | str

class SheetRelationshipItem(BaseModel):
    source_sheet: str
    target_sheet: str
    source_key: str
    target_key: str
    match_ratio: float
    relationship_type: str

class GetRelationshipsOutput(BaseModel):
    dataset_id: int | str
    relationship_count: int
    relationships: list[SheetRelationshipItem]


# =============================================================================
# 2. Analytics MCP Schemas
# =============================================================================

class RankEntitiesInput(BaseModel):
    dataset_id: int | str
    entity_dimension: str
    measure: str
    direction: Literal["desc", "asc"] = "desc"
    limit: int = 10

class RankedEntityItem(BaseModel):
    rank: int
    entity: str
    value: float
    formatted_value: str
    share_of_total_pct: float | None = None

class RankEntitiesOutput(BaseModel):
    dataset_id: int | str
    measure: str
    total_evaluated: int
    ranked_items: list[RankedEntityItem]
    evidence_id: str | None = None


class CompareSegmentsInput(BaseModel):
    dataset_id: int | str
    dimension: str
    measure: str
    segment_a: str
    segment_b: str

class CompareSegmentsOutput(BaseModel):
    dataset_id: int | str
    measure: str
    segment_a_name: str
    segment_a_value: float
    segment_b_name: str
    segment_b_value: float
    delta: float
    delta_pct: float
    evidence_id: str | None = None


class CalculateDistributionInput(BaseModel):
    dataset_id: int | str
    measure: str

class CalculateDistributionOutput(BaseModel):
    dataset_id: int | str
    measure: str
    count: int
    min: float
    p25: float
    median: float
    p75: float
    max: float
    iqr: float
    distribution_id: str
    evidence_id: str | None = None


class GetTrendInput(BaseModel):
    dataset_id: int | str
    time_dimension: str
    measure: str

class TrendPoint(BaseModel):
    period: str
    value: float

class GetTrendOutput(BaseModel):
    dataset_id: int | str
    measure: str
    is_temporal: bool
    direction: Literal["UPWARD", "DOWNWARD", "FLAT", "NON_TEMPORAL"]
    points: list[TrendPoint]
    evidence_id: str | None = None


class FindOutliersInput(BaseModel):
    dataset_id: int | str
    measure: str
    threshold_sigma: float = 2.0

class OutlierEntity(BaseModel):
    entity: str
    value: float
    z_score: float
    severity: Literal["MODERATE", "SEVERE", "EXTREME"]

class FindOutliersOutput(BaseModel):
    dataset_id: int | str
    measure: str
    outlier_count: int
    outliers: list[OutlierEntity]
    evidence_id: str | None = None


class AnalyzeRelationshipInput(BaseModel):
    dataset_id: int | str
    measure_x: str
    measure_y: str

class AnalyzeRelationshipOutput(BaseModel):
    dataset_id: int | str
    measure_x: str
    measure_y: str
    correlation_coefficient: float
    association_strength: str
    sample_size: int
    is_causal: bool = False  # Hard invariant: NEVER causal from correlation!
    evidence_id: str | None = None


class GetBenchmarkComparisonInput(BaseModel):
    dataset_id: int | str
    measure: str
    benchmark_value: float

class GetBenchmarkComparisonOutput(BaseModel):
    dataset_id: int | str
    measure: str
    benchmark_value: float
    actual_mean: float
    gap: float
    gap_pct: float
    compliant_ratio_pct: float
    evidence_id: str | None = None


# =============================================================================
# 3. Evidence MCP Schemas
# =============================================================================

class GetEvidenceInput(BaseModel):
    evidence_id: str  # e.g. "EVID-001"
    dataset_id: int | str | None = None

class GetEvidenceOutput(BaseModel):
    evidence_id: str
    dataset_id: int | str
    claim: str
    verified: bool
    calculation_id: str
    formula: str
    observed_value: float
    formatted_value: str
    unit: str
    sample_size: int
    source_cells: list[str] = Field(default_factory=list)


class VerifyClaimInput(BaseModel):
    dataset_id: int | str
    claim_text: str

class VerifyClaimOutput(BaseModel):
    dataset_id: int | str
    claim_text: str
    verified: bool
    confidence: Literal["HIGH", "MEDIUM", "LOW", "UNVERIFIED"]
    evidence_ids: list[str] = Field(default_factory=list)
    calculation_id: str | None = None
    detected_claim_type: str
    linguistic_conformance: bool
    rejection_reason: str | None = None
    suggested_reformulation: str | None = None


class GetSourceRowsInput(BaseModel):
    dataset_id: int | str
    evidence_id: str
    limit: int = 10
    offset: int = 0

class GetSourceRowsOutput(BaseModel):
    dataset_id: int | str
    evidence_id: str
    total_matching_rows: int
    rows: list[dict[str, Any]]
    pagination_token: str | None = None


class TraceProvenanceInput(BaseModel):
    dataset_id: int | str
    evidence_id: str

class TraceProvenanceOutput(BaseModel):
    dataset_id: int | str
    evidence_id: str
    snapshot_id: str
    transform_sequence: list[str]
    cryptographic_hash: str
    provenance_chain: list[dict[str, Any]]


class GetCalculationInput(BaseModel):
    calculation_id: str  # e.g. "CALC-001"

class GetCalculationOutput(BaseModel):
    calculation_id: str
    recipe_id: str
    definition: str
    math_operator: str
    inputs: list[str]
    output_unit: str


class GetRelatedEvidenceInput(BaseModel):
    dataset_id: int | str
    evidence_id: str

class GetRelatedEvidenceOutput(BaseModel):
    primary_evidence_id: str
    related_evidence_ids: list[str]
    relationship_types: list[str]


# =============================================================================
# 4. Scenario MCP Schemas
# =============================================================================

class GetValidLeversInput(BaseModel):
    dataset_id: int | str

class GovernedLeverDescriptor(BaseModel):
    lever_id: str
    name: str
    domain: str
    min_value: float
    max_value: float
    default_value: float
    discrete_steps: list[float] = Field(default_factory=list)

class GetValidLeversOutput(BaseModel):
    dataset_id: int | str
    domain: str
    is_entitled: bool
    valid_levers: list[GovernedLeverDescriptor]


class RunCounterfactualInput(BaseModel):
    dataset_id: int | str
    levers: dict[str, float]  # e.g. {"days_per_week": 4.0}

class RunCounterfactualOutput(BaseModel):
    dataset_id: int | str
    scenario_id: str  # Strictly prefixed with "SCEN-"
    evidence_class: Literal["SCENARIO"] = "SCENARIO"  # Invariant: EVID != SCEN
    baseline_evidence_id: str
    baseline_value: float
    simulated_value: float
    projected_delta: float
    projected_delta_pct: float
    affected_population: int
    business_consequence: str
    status: Literal["simulated", "invalid_bounds", "domain_unentitled"]


class CompareScenariosInput(BaseModel):
    dataset_id: int | str
    scenario_ids: list[str]

class ScenarioComparisonItem(BaseModel):
    scenario_id: str
    parameters: dict[str, float]
    projected_outcome: float
    delta_vs_baseline: float

class CompareScenariosOutput(BaseModel):
    dataset_id: int | str
    baseline_value: float
    comparisons: list[ScenarioComparisonItem]


class GetScenarioAssumptionsInput(BaseModel):
    dataset_id: int | str
    scenario_id: str

class GetScenarioAssumptionsOutput(BaseModel):
    scenario_id: str
    domain: str
    fixed_assumptions: list[str]
    methodology: str
    disclaimer: str


# =============================================================================
# 5. Presentation MCP Schemas
# =============================================================================

class CreateDeckInput(BaseModel):
    dataset_id: int | str
    evidence_ids: list[str]
    audience: Literal["executive", "operational", "technical"] = "executive"
    title_override: str | None = None

class CreateDeckOutput(BaseModel):
    deck_id: str
    slide_count: int
    title: str
    grounded_evidence_ids: list[str]
    slides_summary: list[dict[str, Any]]


class RegenerateSlideInput(BaseModel):
    deck_id: str
    slide_index: int
    mutation_type: str
    new_evidence_ids: list[str] | None = None

class RegenerateSlideOutput(BaseModel):
    deck_id: str
    slide_index: int
    updated_headline: str
    updated_visual_type: str
    evidence_ids: list[str]


class GenerateVisualInput(BaseModel):
    dataset_id: int | str
    visual_archetype: str
    measure: str
    entity_dimension: str | None = None
    evidence_ids: list[str] = Field(default_factory=list)

class GenerateVisualOutput(BaseModel):
    visual_id: str
    archetype: str
    chart_spec: dict[str, Any]
    grounded_evidence_ids: list[str]


class ExportPdfInput(BaseModel):
    deck_id: str

class ExportPdfOutput(BaseModel):
    deck_id: str
    download_url: str
    page_count: int
    file_size_bytes: int


class GetPresentationStatusInput(BaseModel):
    deck_id: str

class GetPresentationStatusOutput(BaseModel):
    deck_id: str
    status: Literal["ready", "generating", "failed"]
    progress_pct: float
    error_message: str | None = None


# =============================================================================
# 6. Governance MCP Schemas
# =============================================================================

class CheckEntitlementInput(BaseModel):
    caller: str
    requested_capability: str
    dataset_id: int | str | None = None

class CheckEntitlementOutput(BaseModel):
    caller: str
    capability: str
    allowed: bool
    rejection_reason: str | None = None


class CheckDatasetScopeInput(BaseModel):
    active_dataset_id: int | str
    requested_dataset_id: int | str
    allow_cross_dataset: bool = False

class CheckDatasetScopeOutput(BaseModel):
    in_scope: bool
    violation_detected: bool
    reason: str | None = None


class CheckClaimInput(BaseModel):
    claim_text: str
    available_evidence_types: list[str]

class CheckClaimOutput(BaseModel):
    claim_text: str
    is_entitled: bool
    detected_claim_type: str
    linguistic_conformance: bool
    rejection_reason: str | None = None
    suggested_reformulation: str | None = None


class CheckScenarioPermissionInput(BaseModel):
    dataset_id: int | str
    caller: str

class CheckScenarioPermissionOutput(BaseModel):
    dataset_id: int | str
    domain: str
    permitted: bool
    reason: str | None = None


class RequestApprovalInput(BaseModel):
    caller: str
    action_type: str
    impact_description: str
    context: dict[str, Any] = Field(default_factory=dict)

class RequestApprovalOutput(BaseModel):
    approval_id: str
    status: Literal["PENDING", "APPROVED", "REJECTED"]
    approver: str | None = None
    audit_token: str


class GetDecisionProvenanceInput(BaseModel):
    execution_id: str

class GetDecisionProvenanceOutput(BaseModel):
    execution_id: str
    tool_name: str
    caller: str
    dataset_id: int | str | None
    governance_status: str
    evidence_ids: list[str]
    duration_ms: float
    timestamp: float
