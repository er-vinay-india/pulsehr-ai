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
- Fingerprinting and Invalidation helpers
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
    grain, unit, denominator, JoinPlan, and provenance tracking.
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
    formula_trees = [
        {
            "name": d.measure_name,
            "formula": d.formula_repr or str(d.expression),
            "unit": d.unit,
            "class": d.measure_class,
            "denominator": d.denominator_measure,
        }
        for d in sorted(derived_measure_specs, key=lambda m: m.measure_name)
    ]

    payload = {
        "dataset_version": dataset_version,
        "source_artifact_fingerprints": sorted(source_artifact_fingerprints),
        "join_plan_fingerprints": sorted(join_plan_fingerprints),
        "base_grain": base_grain,
        "result_grain": result_grain,
        "dimension_columns": sorted(dimension_columns),
        "measure_columns": sorted(measure_columns),
        "formula_trees": formula_trees,
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
    current_dataset_version: str,
    current_source_fingerprints: list[str],
    current_join_plan_fingerprints: list[str],
    current_policy_fingerprint: str,
) -> tuple[bool, str | None]:
    """
    Evaluates whether an SDRAnalyticalViewSpec has become stale due to upstream drift.
    Returns (is_invalidated, reason).
    """
    if view.dataset_version != current_dataset_version:
        return True, "INVALIDATED_DATASET_VERSION_DRIFT"

    if sorted(view.source_artifact_fingerprints) != sorted(current_source_fingerprints):
        return True, "INVALIDATED_SOURCE_FINGERPRINT_DRIFT"

    if sorted(view.join_plan_ids) and sorted(current_join_plan_fingerprints) != sorted(view.provenance.get("join_plan_fingerprints", [])):
        return True, "INVALIDATED_JOIN_PLAN_DRIFT"

    if view.policy_fingerprint and current_policy_fingerprint != view.policy_fingerprint:
        return True, "INVALIDATED_POLICY_DRIFT"

    return False, None
