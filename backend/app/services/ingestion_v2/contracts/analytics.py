"""
HighView Ingestion V2 — Analytical EDA-B Contract
Stage 8: Analytical EDA-B
Boundary: Exploration of statistical distributions, correlations, and anomalies across validated tables and safe joins.
Rule 1: Tukey IQR outlier detection is rule-based (1.5x IQR multiplier); it NEVER produces a p-value.
Rule 2: AnalyticalReliability is strictly decoupled from StructuralDataQuality.
Rule 3: EDA-B never invents or validates foreign key relationships.
"""

from enum import Enum
from typing import Any
from pydantic import BaseModel, ConfigDict, Field
from app.services.ingestion_v2.contracts.base import IngestionContractBase


class OutlierMethod(str, Enum):
    TUKEY_IQR = "TUKEY_IQR"
    Z_SCORE = "Z_SCORE"
    MODIFIED_Z_SCORE = "MODIFIED_Z_SCORE"


class FindingType(str, Enum):
    DISTRIBUTION = "DISTRIBUTION"
    GROUP_COMPARISON = "GROUP_COMPARISON"
    RANKING = "RANKING"
    TREND = "TREND"
    CHANGE = "CHANGE"
    CONCENTRATION = "CONCENTRATION"
    OUTLIER = "OUTLIER"
    CORRELATION = "CORRELATION"
    VARIANCE = "VARIANCE"
    PROPORTION = "PROPORTION"
    RATE = "RATE"
    COUNT = "COUNT"
    DISTINCT_COUNT = "DISTINCT_COUNT"
    CROSS_TABLE_COMPARISON = "CROSS_TABLE_COMPARISON"


class TukeyIqrEvidence(BaseModel):
    """
    Evidence for rule-based Tukey IQR outlier detection.
    Zero p-values: Tukey IQR is a non-parametric rule-based threshold.
    """
    model_config = ConfigDict(extra="forbid", frozen=True)

    outlier_method: OutlierMethod = OutlierMethod.TUKEY_IQR
    iqr_multiplier: float = 1.5
    q1: float
    q3: float
    iqr: float
    lower_bound: float
    upper_bound: float
    outlier_count: int
    outlier_percentage: float = Field(ge=0.0, le=100.0)


class HypothesisTestEvidence(BaseModel):
    """
    Evidence for formal inferential hypothesis tests (e.g., Pearson, Spearman, ANOVA, t-test).
    This is where p-values and test statistics legitimately belong.
    """
    model_config = ConfigDict(extra="forbid", frozen=True)

    test_name: str  # e.g., "PEARSON_CORRELATION", "SPEARMAN_RANK", "WELCH_T_TEST"
    test_statistic: float
    p_value: float = Field(ge=0.0, le=1.0)
    alpha: float = 0.05
    degrees_of_freedom: float | None = None
    is_statistically_significant: bool


class StatisticalTestEvidence(BaseModel):
    """
    Evidence for formal statistical tests in Phase I5.
    Includes effect sizes, sample size, assumptions, and warnings.
    """
    model_config = ConfigDict(extra="forbid", frozen=True)

    test_name: str
    test_statistic: float
    p_value: float = Field(ge=0.0, le=1.0)
    effect_size: float | None = None
    sample_size: int | None = None
    alpha: float = 0.05
    degrees_of_freedom: float | None = None
    is_statistically_significant: bool = False
    assumptions: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class NullPolicy(str, Enum):
    EXCLUDE_NULL = "EXCLUDE_NULL"
    INCLUDE_AS_CATEGORY = "INCLUDE_AS_CATEGORY"
    IMPUTE = "IMPUTE"


class AnalyticalReliability(BaseModel):
    """
    Measures analytical confidence, join coverage, grain safety, and evidence sufficiency.
    Strictly distinct from StructuralDataQuality.
    """
    model_config = ConfigDict(extra="forbid", frozen=True)

    grain_confidence_score: float = Field(ge=0.0, le=1.0)
    join_coverage_score: float = Field(ge=0.0, le=1.0)
    metric_definition_confidence: float = Field(ge=0.0, le=1.0)
    evidence_sufficiency_score: float = Field(ge=0.0, le=1.0)
    overall_analytical_reliability: float = Field(ge=0.0, le=1.0)
    reliability_level: str = "HIGH"
    sample_sufficiency_score: float = 1.0
    statistical_support_score: float = 1.0
    rationale: str = ""

    # Fine-grained component scores for certification
    relationship_confidence_score: float = Field(default=1.0, ge=0.0, le=1.0)
    join_plan_confidence_score: float = Field(default=1.0, ge=0.0, le=1.0)
    source_coverage_score: float = Field(default=1.0, ge=0.0, le=1.0)
    missingness_support_score: float = Field(default=1.0, ge=0.0, le=1.0)


class AnalyticalFinding(BaseModel):
    """
    Governed finding produced by EDA-B.
    """
    model_config = ConfigDict(extra="forbid", frozen=True)

    finding_id: str
    finding_type: str  # FindingType or string
    affected_tables: list[str] = Field(default_factory=list)
    affected_columns: list[str] = Field(default_factory=list)
    evidence_ref: str | None = None
    description: str
    tukey_outlier_evidence: TukeyIqrEvidence | None = None
    hypothesis_test_evidence: HypothesisTestEvidence | None = None
    statistical_test_evidence: StatisticalTestEvidence | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    # I5 Governance & Precision extensions
    dataset_id: str = ""
    source_table_ids: list[str] = Field(default_factory=list)
    source_column_ids: list[str] = Field(default_factory=list)
    target_grain: str | None = None
    join_plan_ids: list[str] = Field(default_factory=list)
    metric_definition: str | None = None
    dimension_definition: str | None = None
    population_definition: str | None = None
    numerator_definition: str | None = None
    denominator_definition: str | None = None
    result: Any = None
    effect_size: float | None = None
    confidence: float = 1.0
    evidence_refs: list[str] = Field(default_factory=list)
    provenance_refs: list[str] = Field(default_factory=list)
    analytical_reliability: AnalyticalReliability | None = None
    limitations: list[str] = Field(default_factory=list)
    finding_fingerprint: str | None = None
    filter_provenance: dict[str, Any] = Field(default_factory=dict)
    null_policy: NullPolicy = NullPolicy.EXCLUDE_NULL
    time_range: str | None = None
    eligible_population: str | None = None
    imputation_method: str | None = None


class AnalyticalProfile(IngestionContractBase):
    """
    Stage 8 Contract: Analytical EDA-B.
    """
    stage_name: str = "analytical_eda_b"

    findings: list[AnalyticalFinding] = Field(default_factory=list)
    reliability: AnalyticalReliability
