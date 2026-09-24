"""Structured Candidate Fact definitions for PulseHR AI.

Represents mathematically defensible, empirical candidate facts discovered
without LLM computation or business interpretation.
"""

from enum import Enum
from typing import Any
from pydantic import BaseModel, Field, model_validator

from .semantic_classifier import MetricPolarity


class ReliabilityStatus(str, Enum):
    RELIABLE = "reliable"
    UNRELIABLE = "unreliable"
    SKIPPED = "skipped"


class CandidateFact(BaseModel):
    """Deterministic candidate observation surfaced strictly from data engine evidence."""

    fact_id: str
    fact_type: str
    metric: str
    dimensions: dict[str, Any] = Field(default_factory=dict)
    value: float | None = None
    baseline_value: float | None = None
    absolute_difference: float | None = None
    relative_difference: float | None = None
    sample_size: int = 0
    statistical_info: dict[str, Any] = Field(default_factory=dict)
    source_columns: list[str] = Field(default_factory=list)
    filters: dict[str, Any] = Field(default_factory=dict)
    time_window: str | None = None
    polarity: MetricPolarity = MetricPolarity.UNKNOWN
    semantic_confidence: float = 1.0
    calculation_method: str = ""
    evidence_metadata: dict[str, Any] = Field(default_factory=dict)
    statement: str = ""
    reliability_status: ReliabilityStatus = ReliabilityStatus.RELIABLE
    reliability_reason: str | None = None

    @model_validator(mode="before")
    @classmethod
    def _translate_legacy_and_defaults(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data

        d = dict(data)
        # 1. Translate observed_value -> value
        if "observed_value" in d and "value" not in d:
            d["value"] = d.pop("observed_value")

        # 2. Translate difference -> absolute_difference
        if "difference" in d and "absolute_difference" not in d:
            d["absolute_difference"] = d.pop("difference")

        # 3. Translate percentage_gap -> relative_difference
        if "percentage_gap" in d and "relative_difference" not in d:
            d["relative_difference"] = d.pop("percentage_gap")

        # 4. Translate segment -> dimensions
        if "segment" in d and d["segment"] and "dimensions" not in d:
            seg = d.pop("segment")
            if isinstance(seg, str) and ":" in seg:
                k, v = seg.split(":", 1)
                d["dimensions"] = {k.strip(): v.strip()}
            elif isinstance(seg, str):
                d["dimensions"] = {"segment": seg}

        # 5. Translate raw_proof -> evidence_metadata
        if "raw_proof" in d and "evidence_metadata" not in d:
            d["evidence_metadata"] = d.pop("raw_proof")

        # 6. Translate significance_score -> statistical_info
        if "significance_score" in d:
            score = d.pop("significance_score")
            stat_info = d.get("statistical_info", {})
            if isinstance(stat_info, dict) and "significance_score" not in stat_info:
                stat_info["significance_score"] = score
            d["statistical_info"] = stat_info

        return d

    # Backward compatibility properties for existing AnalystAgent and test callers
    @property
    def observed_value(self) -> float:
        return self.value if self.value is not None else 0.0

    @property
    def difference(self) -> float | None:
        return self.absolute_difference

    @property
    def percentage_gap(self) -> float | None:
        return self.relative_difference

    @property
    def segment(self) -> str | None:
        if not self.dimensions:
            return None
        if "segment" in self.dimensions:
            return str(self.dimensions["segment"])
        k, v = next(iter(self.dimensions.items()))
        return f"{k}:{v}"

    @property
    def significance_score(self) -> float:
        if "significance_score" in self.statistical_info:
            return float(self.statistical_info["significance_score"])
        if self.relative_difference is not None:
            return min(1.0, abs(self.relative_difference) / 50.0)
        return 0.5

    @property
    def raw_proof(self) -> dict[str, Any]:
        return self.evidence_metadata
