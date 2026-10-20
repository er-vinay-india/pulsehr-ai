"""
HighView Semantic Data Refinery — Phase SDR-8
Shadow Consumer Integration Contracts

Defines strongly-typed models for:
- ComparisonClass (UNCHANGED, EXPECTED_IMPROVEMENT, EXPECTED_DIFFERENCE)
- DisagreementType (EXPECTED_FIX, EXPECTED_REFACTOR, REGRESSION, UNRESOLVED)
- Severity (INFO, WARNING, CRITICAL)
- ShadowConsumerType (HRIDAY, DASHBOARD, PRESENTATION)
- FactIdentity (Governed Fact Identity across consumers)
- FactComparison (Fact-level parity assessment)
- SemanticComparison (Macro semantic dimensions assessment)
- SDRShadowEvaluation (Complete shadow evaluation record)
- ShadowTelemetrySummary (Aggregated shadow metrics per consumer)
"""

from __future__ import annotations

from enum import Enum
import hashlib
import json
from typing import Any, Union
from pydantic import BaseModel, ConfigDict, Field


class ComparisonClass(str, Enum):
    """
    Macro evaluation layer comparison classes.
    Strictly aligns with the frozen comparison model.
    """
    UNCHANGED = "UNCHANGED"
    EXPECTED_IMPROVEMENT = "EXPECTED_IMPROVEMENT"
    EXPECTED_DIFFERENCE = "EXPECTED_DIFFERENCE"


class DisagreementType(str, Enum):
    """
    Micro governance and cutover classification.
    """
    EXPECTED_FIX = "EXPECTED_FIX"
    EXPECTED_REFACTOR = "EXPECTED_REFACTOR"
    REGRESSION = "REGRESSION"
    UNRESOLVED = "UNRESOLVED"


class Severity(str, Enum):
    """
    Disagreement severity rating.
    """
    INFO = "INFO"
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"


class ShadowConsumerType(str, Enum):
    """
    Governed consumers in scope for shadow integration.
    """
    HRIDAY = "HRIDAY"
    DASHBOARD = "DASHBOARD"
    PRESENTATION = "PRESENTATION"


class FactIdentity(BaseModel):
    """
    Governed fact identity model for cross-consumer parity.
    A fact is identical across consumers if and only if it shares:
    metric_id, value, unit, grain, denominator, dataset_version, and evidence identity.
    """
    model_config = ConfigDict(frozen=True)

    metric_id: str
    value: Union[float, int, str, None] = None
    formatted_value: str = ""
    unit: str | None = None
    grain: str
    denominator: Union[str, float, int, None] = None
    dataset_id: str
    dataset_version: str = "v1"
    evidence_id: str | None = None
    source_evidence_ids: list[str] = Field(default_factory=list)
    provenance_type: str = "OBSERVED"  # "OBSERVED", "DERIVED_LOCAL", "DERIVED_RELATIONAL", "DERIVED_ENRICHMENT"
    join_plan_id: str | None = None
    analytical_view_id: str | None = None

    def compute_identity_fingerprint(self) -> str:
        """
        Computes deterministic SHA-256 fingerprint of the governed fact identity.
        Normalizes numeric values to prevent presentation compacting differences.
        """
        norm_val = ""
        if isinstance(self.value, (int, float)):
            norm_val = f"{float(self.value):.6f}"
        elif self.value is not None:
            norm_val = str(self.value).strip().lower()

        sorted_evids = sorted(self.source_evidence_ids) if self.source_evidence_ids else ([self.evidence_id] if self.evidence_id else [])
        norm_unit = str(self.unit).strip().lower() if self.unit else "none"
        norm_grain = str(self.grain).strip().upper() if self.grain else "none"
        raw = (
            f"{self.metric_id}|{norm_val}|{norm_unit}|{norm_grain}|"
            f"{self.denominator or 'none'}|{self.dataset_id}|{self.dataset_version}|"
            f"{','.join(filter(None, sorted_evids))}"
        )
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()


class FactComparison(BaseModel):
    """
    Fact-level comparison between V2 authoritative fact and SDR shadow fact.
    """
    model_config = ConfigDict(frozen=True)

    fact_id: str
    metric_id: str
    v2_fact: FactIdentity | None = None
    sdr_fact: FactIdentity | None = None

    comparison_class: ComparisonClass
    difference_type: DisagreementType
    severity: Severity

    numeric_match: bool = True
    unit_match: bool = True
    grain_match: bool = True
    denominator_match: bool = True
    provenance_match: bool = True

    rationale: str = ""


class SemanticComparison(BaseModel):
    """
    Macro-level semantic comparison (e.g., topic selection, card ranking, refusal, cross-sheet answerability).
    """
    model_config = ConfigDict(frozen=True)

    dimension: str  # "RETRIEVAL_COVERAGE", "TOPIC_SELECTION", "CROSS_SHEET_ANSWERABILITY", "CARD_RANKING", "REFUSAL_BEHAVIOR"
    v2_value: Any = None
    sdr_value: Any = None

    comparison_class: ComparisonClass
    difference_type: DisagreementType
    severity: Severity

    rationale: str = ""


class SDRShadowEvaluation(BaseModel):
    """
    Complete typed SDR Shadow Evaluation record.
    Captures the exact comparison between V2 authoritative output and SDR shadow output.
    """
    model_config = ConfigDict(frozen=True)

    shadow_evaluation_id: str
    dataset_id: str
    dataset_version: str = "v1"
    consumer: ShadowConsumerType
    request_fingerprint: str

    v2_result_fingerprint: str
    sdr_result_fingerprint: str

    comparison_class: ComparisonClass
    difference_type: DisagreementType
    severity: Severity

    fact_comparisons: list[FactComparison] = Field(default_factory=list)
    semantic_comparisons: list[SemanticComparison] = Field(default_factory=list)

    latency: dict[str, float] = Field(default_factory=dict)  # {"v2_ms": ..., "sdr_ms": ..., "comparison_ms": ...}
    fallback_state: dict[str, Any] = Field(default_factory=dict)
    provenance: dict[str, Any] = Field(default_factory=dict)
    artifact_fingerprint: str = ""

    sdr_status: str = "AVAILABLE"  # "AVAILABLE", "UNAVAILABLE", "STALE", "UNSAFE_BLOCKED", "AMBIGUOUS_BLOCKED"
    is_refusal: bool = False
    refusal_reason: str | None = None


class ShadowTelemetrySummary(BaseModel):
    """
    Aggregated shadow telemetry for a consumer.
    """
    model_config = ConfigDict(frozen=False)

    consumer: ShadowConsumerType
    total_requests: int = 0
    sdr_available_count: int = 0
    sdr_unavailable_count: int = 0
    sdr_stale_count: int = 0
    unsafe_blocked_count: int = 0
    ambiguous_blocked_count: int = 0

    unchanged_count: int = 0
    expected_improvement_count: int = 0
    expected_difference_count: int = 0
    regression_count: int = 0
    unresolved_count: int = 0

    v2_latency_samples: list[float] = Field(default_factory=list)
    sdr_latency_samples: list[float] = Field(default_factory=list)
    comparison_latency_samples: list[float] = Field(default_factory=list)

    v2_failures_caused_by_sdr: int = 0
    user_visible_substitutions: int = 0
