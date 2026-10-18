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


class AnalyticalFinding(BaseModel):
    """
    Governed finding produced by EDA-B.
    """
    model_config = ConfigDict(extra="forbid", frozen=True)

    finding_id: str
    finding_type: str  # e.g., "OUTLIER_DETECTED", "CORRELATION_DISCOVERED", "TEMPORAL_TREND"
    affected_tables: list[str] = Field(default_factory=list)
    affected_columns: list[str] = Field(default_factory=list)
    evidence_ref: str | None = None
    description: str
    tukey_outlier_evidence: TukeyIqrEvidence | None = None
    hypothesis_test_evidence: HypothesisTestEvidence | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class AnalyticalProfile(IngestionContractBase):
    """
    Stage 8 Contract: Analytical EDA-B.
    """
    stage_name: str = "analytical_eda_b"

    findings: list[AnalyticalFinding] = Field(default_factory=list)
    reliability: AnalyticalReliability
