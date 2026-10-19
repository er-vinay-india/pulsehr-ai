"""
HighView Semantic Data Refinery — Phase SDR-6
Governed Analytical Views, Reconstruction Engine & Silver -> Gold Analytical Modeling

Defines typed contracts for:
- SDRAnalyticalViewStatus (VALID, VALID_WITH_PREAGGREGATION, AMBIGUOUS, UNSAFE, STALE)
- MaterializationMode (VIRTUAL, MATERIALIZED)
- MissingValuePolicy (PRESERVE_NULL, ZERO_IMPUTATION_RESTRICTED, DROP_NULL)
- ExpressionOp & ControlledExpression (Controlled Expression Tree DSL, zero raw LLM SQL)
- SDRDerivedMeasureSpec & SDRFilterConstraint
- SDRAnalyticalViewSpec
- SDRAnalyticalFact (reproducible analytical fact identity)
- SDRAnalyticalExecutionResult
- AnalyticalMaterializationPolicy & Materialization Governance
- Complete Invalidation Engine & Fingerprinting across all 10 dependency dimensions
"""

from __future__ import annotations

from enum import Enum
import hashlib
import json
from typing import Any, Union
from pydantic import BaseModel, ConfigDict, Field

from app.services.ingestion_v2.contracts.joins import (
    JoinPlan,
    JoinSafetyStatus,
    MeasureAdditivity,
    PreAggregationSpec,
)


class SDRAnalyticalViewStatus(str, Enum):
    """
    SDR-6 Governed Analytical View Status.
    Only VALID and VALID_WITH_PREAGGREGATION views may be executed.
    AMBIGUOUS, UNSAFE, and STALE views are strictly blocked from execution.
    """
    VALID = "VALID"
    VALID_WITH_PREAGGREGATION = "VALID_WITH_PREAGGREGATION"
    AMBIGUOUS = "AMBIGUOUS"
    UNSAFE = "UNSAFE"
    STALE = "STALE"


class MaterializationMode(str, Enum):
    """
    Analytical View Materialization Policy.
    Default is VIRTUAL (in-memory execution).
    MATERIALIZED is applied only when authorized by policy (reuse, size, compute cost).
    """
    VIRTUAL = "VIRTUAL"
    MATERIALIZED = "MATERIALIZED"


class MissingValuePolicy(str, Enum):
    """
    Missing Value Semantics.
    CRITICAL: NULL/MISSING must be preserved distinct from 0.
    """
    PRESERVE_NULL = "PRESERVE_NULL"  # Default: keep NULL distinct from 0
    ZERO_IMPUTATION_RESTRICTED = "ZERO_IMPUTATION_RESTRICTED"  # Only if explicitly authorized
    DROP_NULL = "DROP_NULL"


class ExpressionOp(str, Enum):
    """
    Governed Expression Tree Operator.
    Typed DSL operations strictly prevent arbitrary/untrusted SQL text generation.
    """
    SUM = "SUM"
    COUNT = "COUNT"
    COUNT_DISTINCT = "COUNT_DISTINCT"
    MIN = "MIN"
    MAX = "MAX"
    AVG = "AVG"  # Only allowed when semantically authorized; blocked for raw ratios without denominators
    DIVIDE = "DIVIDE"
    SUBTRACT = "SUBTRACT"
    ADD = "ADD"
    MULTIPLY = "MULTIPLY"
    COLUMN = "COLUMN"
    LITERAL = "LITERAL"
    CASE = "CASE"


class ControlledExpression(BaseModel):
    """
    Controlled Expression AST Node.
    Zero raw SQL strings allowed from models. All calculations evaluate through typed nodes.
    """
    model_config = ConfigDict(frozen=True)

    op: ExpressionOp
    column: str | None = None
    literal_value: Union[float, int, str, None] = None
    args: list[ControlledExpression] = Field(default_factory=list)
    unit: str | None = None
    when_clauses: list[dict[str, Any]] = Field(default_factory=list)

    @classmethod
    def col(cls, col_name: str, unit: str | None = None) -> ControlledExpression:
        return cls(op=ExpressionOp.COLUMN, column=col_name, unit=unit)

    @classmethod
    def lit(cls, val: Union[float, int, str], unit: str | None = None) -> ControlledExpression:
        return cls(op=ExpressionOp.LITERAL, literal_value=val, unit=unit)

    @classmethod
    def binary(cls, op: ExpressionOp, left: ControlledExpression, right: ControlledExpression, unit: str | None = None) -> ControlledExpression:
        return cls(op=op, args=[left, right], unit=unit)

    @classmethod
    def aggregate(cls, op: ExpressionOp, inner: ControlledExpression, unit: str | None = None) -> ControlledExpression:
        return cls(op=op, args=[inner], unit=unit)


class SDRDerivedMeasureSpec(BaseModel):
    """
    Governed Derived Measure Specification.
    Binds a metric name to a typed expression AST, unit, and measure classification.
    """
    model_config = ConfigDict(frozen=True)

    measure_name: str
    expression: ControlledExpression
    unit: str | None = None
    measure_class: str = "ADDITIVE"
    denominator_measure: str | None = None
    formula_repr: str = ""


class SDRFilterConstraint(BaseModel):
    """
    Governed Filter Predicate Constraint.
    Typed filter to eliminate arbitrary raw SQL injection.
    """
    model_config = ConfigDict(frozen=True)

    column: str
    operator: str = "="  # "=", "!=", ">", "<", ">=", "<=", "IN", "NOT IN", "IS NULL", "IS NOT NULL"
    value: Any = None


class SDRAnalyticalViewSpec(BaseModel):
    """
    SDR-6 Governed Analytical View Specification Contract.
    Captures multi-sheet or single-sheet analytical view configurations with full
    grain, unit, denominator, JoinPlan, and provenance tracking across all 10 dependency dimensions.
    """
    model_config = ConfigDict(frozen=True)

    analytical_view_id: str
    dataset_id: str
    dataset_version: str = "v1"
    name: str

    source_sheet_ids: list[str]
    source_artifact_fingerprints: list[str] = Field(default_factory=list)

    join_plan_ids: list[str] = Field(default_factory=list)

    base_grain: str
    result_grain: str

    dimension_columns: list[str] = Field(default_factory=list)
    measure_columns: list[str] = Field(default_factory=list)

    filter_constraints: list[SDRFilterConstraint] = Field(default_factory=list)
    preaggregation_specs: list[PreAggregationSpec] = Field(default_factory=list)
    derived_measure_specs: list[SDRDerivedMeasureSpec] = Field(default_factory=list)

    missing_value_policy: MissingValuePolicy = MissingValuePolicy.PRESERVE_NULL
    unit_metadata: dict[str, str] = Field(default_factory=dict)
    denominator_metadata: dict[str, str] = Field(default_factory=dict)

    materialization_mode: MaterializationMode = MaterializationMode.VIRTUAL
    status: SDRAnalyticalViewStatus = SDRAnalyticalViewStatus.VALID
    rejection_reason: str | None = None

    # Complete 10-dimension dependency fingerprints
    semantic_profile_fingerprints: list[str] = Field(default_factory=list)
    grain_fingerprints: list[str] = Field(default_factory=list)
    key_fingerprints: list[str] = Field(default_factory=list)
    enrichment_fingerprints: list[str] = Field(default_factory=list)
    relationship_edge_fingerprints: list[str] = Field(default_factory=list)
    join_plan_fingerprints: list[str] = Field(default_factory=list)
    formula_fingerprint: str = ""

    provenance: dict[str, Any] = Field(default_factory=dict)
    policy_fingerprint: str = ""
    artifact_fingerprint: str = ""


class SDRAnalyticalFact(BaseModel):
    """
    SDR-6 Governed Analytical Fact Contract.
    Represents an immutable, reproducible analytical statement derived from a validated view.
    """
    model_config = ConfigDict(frozen=True)

    fact_id: str
    metric: str
    value: float | int | None = None
    formatted_value: str = ""
    unit: str | None = None
    grain: str
    denominator_value: float | int | None = None
    dataset_id: str
    dataset_version: str = "v1"
    source_evidence_ids: list[str] = Field(default_factory=list)
    analytical_view_id: str
    join_plan_ids: list[str] = Field(default_factory=list)
    provenance_type: str = "OBSERVED"  # "OBSERVED", "DERIVED_LOCAL", "DERIVED_RELATIONAL", "DERIVED_ENRICHMENT"
    tokens: dict[str, Any] = Field(default_factory=dict)
    artifact_fingerprint: str = ""


class SDRAnalyticalExecutionResult(BaseModel):
    """
    SDR-6 Governed Analytical Execution Result.
    Emitted after deterministic DuckDB execution and post-execution invariant verification.
    """
    model_config = ConfigDict(frozen=True)

    view_id: str
    status: SDRAnalyticalViewStatus
    row_count: int
    result_grain: str

    measure_results: dict[str, Any] = Field(default_factory=dict)
    grain_validation: dict[str, Any] = Field(default_factory=dict)
    unit_validation: dict[str, Any] = Field(default_factory=dict)
    denominator_validation: dict[str, Any] = Field(default_factory=dict)
    missing_value_summary: dict[str, Any] = Field(default_factory=dict)

    provenance: dict[str, Any] = Field(default_factory=dict)
    execution_fingerprint: str = ""
    materialized_parquet_path: str | None = None
    rows: list[dict[str, Any]] = Field(default_factory=list)
    error_message: str | None = None


# =====================================================================
# MATERIALIZATION GOVERNANCE
# =====================================================================

class AnalyticalMaterializationPolicy(BaseModel):
    """
    SDR-6 Governed Materialization Policy.
    Separates analytical utility / importance from physical materialization authority.
    VIRTUAL is the strict default.
    """
    model_config = ConfigDict(frozen=True)

    storage_budget_bytes: int = 50 * 1024 * 1024  # 50 MB default storage budget
    max_materialized_views: int = 10
    min_recomputation_cost_ms: float = 50.0  # Min compute time to justify caching
    min_expected_reuse: int = 2  # Must expect at least 2 reuses to justify disk persistence
    allow_explicit_materialization: bool = True


def evaluate_view_materialization_authorization(
    view_spec: SDRAnalyticalViewSpec,
    estimated_size_bytes: int,
    current_storage_used_bytes: int,
    expected_reuse_count: int = 1,
    recomputation_cost_ms: float = 5.0,
    policy: AnalyticalMaterializationPolicy | None = None,
    explicit_materialization_request: bool = False,
    utility_score: float = 1.0,  # e.g., 1.0 for high utility / Gold views
) -> tuple[MaterializationMode, str]:
    """
    Evaluates whether an analytical view is authorized for physical materialization (Parquet).

    CORE GOVERNANCE RULE:
    Analytical utility != physical materialization authority.
    High utility alone CANNOT authorize materialization without reuse/cost justification.
    """
    pol = policy or AnalyticalMaterializationPolicy()

    # Hard Gate 1: Explicit request or economic justification required
    has_justification = explicit_materialization_request or (
        expected_reuse_count >= pol.min_expected_reuse and recomputation_cost_ms >= pol.min_recomputation_cost_ms
    )

    if not has_justification:
        return (
            MaterializationMode.VIRTUAL,
            "VIRTUAL_BY_DEFAULT: High analytical utility alone does not authorize persistence without reuse or compute cost justification",
        )

    # Hard Gate 2: Storage budget firewall
    if current_storage_used_bytes + estimated_size_bytes > pol.storage_budget_bytes:
        return (
            MaterializationMode.VIRTUAL,
            f"MATERIALIZATION_BLOCKED: Storage budget exceeded ({current_storage_used_bytes + estimated_size_bytes} > {pol.storage_budget_bytes})",
        )

    return (MaterializationMode.MATERIALIZED, "MATERIALIZATION_AUTHORIZED")


def serve_materialized_gold_view(
    view: SDRAnalyticalViewSpec,
    current_dependencies: dict[str, Any],
) -> tuple[str | None, str]:
    """
    Serves a materialized Gold view artifact ONLY if it is 100% current.
    If any dependency has drifted, returns (None, 'STALE_MATERIALIZED_VIEW_BLOCKED').
    Guarantees that stale materialized views are NEVER served as current truth.
    """
    is_stale, reason = check_analytical_view_invalidation(
        view=view,
        **current_dependencies,
    )

    if is_stale:
        return None, f"STALE_MATERIALIZED_VIEW_BLOCKED: {reason}"

    parquet_path = view.provenance.get("materialized_parquet_path")
    if not parquet_path:
        return None, "NO_MATERIALIZED_PATH_FOUND"

    return parquet_path, "MATERIALIZED_VIEW_SERVED"


# =====================================================================
# FINGERPRINTING & INVALIDATION
# =====================================================================

def compute_formula_fingerprint(derived_measure_specs: list[SDRDerivedMeasureSpec]) -> str:
    """Computes a deterministic SHA-256 fingerprint of derived measure expressions."""
    trees = [
        {
            "name": d.measure_name,
            "formula": d.formula_repr or str(d.expression),
            "unit": d.unit,
            "class": d.measure_class,
            "denominator": d.denominator_measure,
        }
        for d in sorted(derived_measure_specs, key=lambda m: m.measure_name)
    ]
    raw = json.dumps(trees, sort_keys=True)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def compute_analytical_view_fingerprint(
    dataset_version: str,
    source_artifact_fingerprints: list[str],
    join_plan_fingerprints: list[str],
    base_grain: str,
    result_grain: str,
    dimension_columns: list[str],
    measure_columns: list[str],
    derived_measure_specs: list[SDRDerivedMeasureSpec],
    unit_metadata: dict[str, str],
    denominator_metadata: dict[str, str],
    missing_value_policy: MissingValuePolicy,
    policy_fingerprint: str,
) -> str:
    """
    Computes a deterministic SHA-256 fingerprint for an SDRAnalyticalViewSpec.
    Excludes runtime paths, timestamps, and UUIDs.
    """
    formula_fp = compute_formula_fingerprint(derived_measure_specs)

    payload = {
        "dataset_version": dataset_version,
        "source_artifact_fingerprints": sorted(source_artifact_fingerprints),
        "join_plan_fingerprints": sorted(join_plan_fingerprints),
        "base_grain": base_grain,
        "result_grain": result_grain,
        "dimension_columns": sorted(dimension_columns),
        "measure_columns": sorted(measure_columns),
        "formula_fingerprint": formula_fp,
        "unit_metadata": sorted(unit_metadata.items()),
        "denominator_metadata": sorted(denominator_metadata.items()),
        "missing_value_policy": missing_value_policy.value,
        "policy_fingerprint": policy_fingerprint,
    }
    raw = json.dumps(payload, sort_keys=True)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def compute_analytical_fact_fingerprint(
    dataset_id: str,
    dataset_version: str,
    analytical_view_id: str,
    metric: str,
    value: float | int | None,
    unit: str | None,
    grain: str,
    denominator_value: float | int | None,
    source_evidence_ids: list[str],
    join_plan_ids: list[str],
    provenance_type: str,
) -> str:
    """
    Computes a deterministic SHA-256 fingerprint for an SDRAnalyticalFact.
    """
    payload = {
        "dataset_id": dataset_id,
        "dataset_version": dataset_version,
        "analytical_view_id": analytical_view_id,
        "metric": metric,
        "value": round(float(value), 6) if isinstance(value, (int, float)) else str(value),
        "unit": unit,
        "grain": grain,
        "denominator_value": round(float(denominator_value), 6) if isinstance(denominator_value, (int, float)) else str(denominator_value),
        "source_evidence_ids": sorted(source_evidence_ids),
        "join_plan_ids": sorted(join_plan_ids),
        "provenance_type": provenance_type,
    }
    raw = json.dumps(payload, sort_keys=True)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def check_analytical_view_invalidation(
    view: SDRAnalyticalViewSpec,
    current_dataset_version: str | None = None,
    current_source_fingerprints: list[str] | None = None,
    current_semantic_profile_fingerprints: list[str] | None = None,
    current_grain_fingerprints: list[str] | None = None,
    current_key_fingerprints: list[str] | None = None,
    current_enrichment_fingerprints: list[str] | None = None,
    current_relationship_edge_fingerprints: list[str] | None = None,
    current_join_plan_fingerprints: list[str] | None = None,
    current_policy_fingerprint: str | None = None,
    current_formula_fingerprint: str | None = None,
    **kwargs: Any,
) -> tuple[bool, str | None]:
    """
    Evaluates whether an SDRAnalyticalViewSpec has become stale due to upstream drift across
    all 10 dependency dimensions (A through J).
    Returns (is_invalidated, reason).
    """
    dataset_version = (
        current_dataset_version
        if current_dataset_version is not None
        else kwargs.get("current_dataset_version", kwargs.get("dataset_version"))
    )
    source_fingerprints = (
        current_source_fingerprints
        if current_source_fingerprints is not None
        else kwargs.get("current_source_fingerprints", kwargs.get("source_artifact_fingerprints"))
    )
    semantic_profile_fingerprints = (
        current_semantic_profile_fingerprints
        if current_semantic_profile_fingerprints is not None
        else kwargs.get("current_semantic_profile_fingerprints", kwargs.get("semantic_profile_fingerprints"))
    )
    grain_fingerprints = (
        current_grain_fingerprints
        if current_grain_fingerprints is not None
        else kwargs.get("current_grain_fingerprints", kwargs.get("grain_fingerprints"))
    )
    key_fingerprints = (
        current_key_fingerprints
        if current_key_fingerprints is not None
        else kwargs.get("current_key_fingerprints", kwargs.get("key_fingerprints"))
    )
    enrichment_fingerprints = (
        current_enrichment_fingerprints
        if current_enrichment_fingerprints is not None
        else kwargs.get("current_enrichment_fingerprints", kwargs.get("enrichment_fingerprints"))
    )
    relationship_edge_fingerprints = (
        current_relationship_edge_fingerprints
        if current_relationship_edge_fingerprints is not None
        else kwargs.get("current_relationship_edge_fingerprints", kwargs.get("relationship_edge_fingerprints"))
    )
    join_plan_fingerprints = (
        current_join_plan_fingerprints
        if current_join_plan_fingerprints is not None
        else kwargs.get("current_join_plan_fingerprints", kwargs.get("join_plan_fingerprints"))
    )
    policy_fingerprint = (
        current_policy_fingerprint
        if current_policy_fingerprint is not None
        else kwargs.get("current_policy_fingerprint", kwargs.get("policy_fingerprint"))
    )
    formula_fingerprint = (
        current_formula_fingerprint
        if current_formula_fingerprint is not None
        else kwargs.get("current_formula_fingerprint", kwargs.get("formula_fingerprint"))
    )

    # A. Dataset / source version drift
    if dataset_version is not None and view.dataset_version != dataset_version:
        return True, "INVALIDATED_DATASET_VERSION_DRIFT"

    # B. Source artifact fingerprint drift
    if source_fingerprints is not None and sorted(view.source_artifact_fingerprints) != sorted(source_fingerprints):
        return True, "INVALIDATED_SOURCE_FINGERPRINT_DRIFT"

    # C. SDR-1 Semantic profile drift
    if semantic_profile_fingerprints is not None and sorted(view.semantic_profile_fingerprints) != sorted(semantic_profile_fingerprints):
        return True, "INVALIDATED_SEMANTIC_DRIFT"

    # D. SDR-2 Grain drift
    if grain_fingerprints is not None and sorted(view.grain_fingerprints) != sorted(grain_fingerprints):
        return True, "INVALIDATED_GRAIN_DRIFT"

    # E. SDR-3 Key drift
    if key_fingerprints is not None and sorted(view.key_fingerprints) != sorted(key_fingerprints):
        return True, "INVALIDATED_KEY_DRIFT"

    # F. SDR-4 Enrichment drift
    if enrichment_fingerprints is not None and sorted(view.enrichment_fingerprints) != sorted(enrichment_fingerprints):
        return True, "INVALIDATED_ENRICHMENT_DRIFT"

    # G. SDR-5 ValidatedRelationshipEdge drift
    if relationship_edge_fingerprints is not None and sorted(view.relationship_edge_fingerprints) != sorted(relationship_edge_fingerprints):
        return True, "INVALIDATED_RELATIONSHIP_EDGE_DRIFT"

    # H. SDR-5 JoinPlan drift
    if join_plan_fingerprints is not None and sorted(view.join_plan_fingerprints) != sorted(join_plan_fingerprints):
        return True, "INVALIDATED_JOIN_PLAN_DRIFT"

    # I. Analytical policy drift
    if policy_fingerprint is not None and view.policy_fingerprint and policy_fingerprint != view.policy_fingerprint:
        return True, "INVALIDATED_POLICY_DRIFT"

    # J. Formula / ControlledExpression drift
    if formula_fingerprint is not None and view.formula_fingerprint and formula_fingerprint != view.formula_fingerprint:
        return True, "INVALIDATED_FORMULA_DRIFT"

    return False, None
