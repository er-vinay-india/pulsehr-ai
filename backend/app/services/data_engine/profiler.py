"""Deterministic dataset profiling engine categorizing measures, dimensions, and timeline context.

Integrates with the generic SemanticClassifier and OpportunityMapGenerator:
- Provides universal multi-signal semantic column classification
- Dynamic dataset row grain discovery
- Conservative metric polarity tracking with confidence and detection rationale
- Admissible Analysis Opportunity Mapping
- Full backward-compatibility with downstream analytical workflows
"""

import re
from typing import Any
import pandas as pd
from pydantic import BaseModel, Field

from ..display_formatters import format_display_label
from .semantic_classifier import (
    SemanticClassifier,
    SemanticDatasetProfile,
    ColumnSemanticProfile,
    SemanticRole,
    MetricPolarity
)
from .opportunity_map import (
    OpportunityMapGenerator,
    AnalysisOpportunityMap,
    AnalysisOpportunity,
    OpportunityType
)


class ColumnProfile(BaseModel):
    """Detailed profile of an individual column."""
    name: str
    display_name: str
    inferred_type: str  # "numeric_measure", "categorical_dimension", "datetime", "identifier"
    null_percentage: float
    distinct_count: int
    unit: str = ""
    summary: dict[str, Any] = Field(default_factory=dict)
    semantic_role: SemanticRole = SemanticRole.CATEGORICAL_DIMENSION
    metric_polarity: MetricPolarity = MetricPolarity.UNKNOWN
    polarity_confidence: float = 0.0
    polarity_reason: str = ""
    detection_reasons: list[str] = Field(default_factory=list)


class DatasetProfile(BaseModel):
    """Holistic profile of the dataset consumed by analyst and writer models."""
    dataset_name: str
    business_domain: str
    row_count: int
    column_count: int
    numeric_measures: list[str] = Field(default_factory=list)
    categorical_dimensions: list[str] = Field(default_factory=list)
    timeline_columns: list[str] = Field(default_factory=list)
    identifier_columns: list[str] = Field(default_factory=list)
    profiles: list[ColumnProfile] = Field(default_factory=list)
    observation_window: str = "Cross-sectional snapshot"
    
    # Generic Phase 1 enhancements
    inferred_grain: str = "record"
    grain_confidence: float = 0.5
    grain_key_columns: list[str] = Field(default_factory=list)
    semantic_profile: SemanticDatasetProfile | None = None
    opportunity_map: AnalysisOpportunityMap | None = None


def is_id_column(col_name: str) -> bool:
    c = col_name.lower().replace("_", "").replace("-", "").strip()
    return c.endswith("id") or c == "id" or "uuid" in c or c.endswith("code") or c == "key"


def is_date_column(col_name: str, series: pd.Series) -> bool:
    c = col_name.lower()
    if any(k in c for k in ("date", "time", "timestamp", "month", "year", "quarter", "period", "week")):
        return True
    sample = series.dropna().astype(str).head(10)
    if len(sample) >= 3:
        try:
            pd.to_datetime(sample, errors='raise')
            return True
        except Exception:
            pass
    return False


def infer_domain(columns: list[str], dataset_name: str = "") -> str:
    combined = " ".join([c.lower() for c in columns] + [dataset_name.lower()])
    if any(k in combined for k in ("sales", "revenue", "store", "product", "retail", "price", "order", "inventory", "discount", "margin")):
        return "Commercial Sales & Retail"
    if any(k in combined for k in ("employee", "attendance", "performance", "rating", "salary", "turnover", "attrition", "department", "hr", "leave", "staff")):
        return "Workforce Health & Talent Analytics"
    if any(k in combined for k in ("shipment", "warehouse", "logistics", "freight", "carrier", "route", "transit")):
        return "Logistics & Supply Chain"
    if any(k in combined for k in ("patient", "clinical", "hospital", "diagnosis", "health", "doctor")):
        return "Clinical Operations & Healthcare"
    if any(k in combined for k in ("cost", "budget", "pnl", "ebitda", "financial", "expenditure", "accounting", "ledger")):
        return "Financial Planning & Analysis"
    if any(k in combined for k in ("machine", "defect", "scrap", "cycle_time", "batch", "operator", "factory", "plant", "manufacturing")):
        return "Industrial Manufacturing & Operations"
    if any(k in combined for k in ("session", "page", "bounce", "event", "user", "web", "browser", "traffic", "visitor")):
        return "Web & Product Analytics"
    return "Enterprise Operations"


class DatasetProfiler:
    """Profiles tabular datasets using multi-signal generic semantic detection."""

    @classmethod
    def profile(cls, df: pd.DataFrame, dataset_name: str = "Dataset") -> DatasetProfile:
        # 1. Execute deep semantic classification
        sem_profile = SemanticClassifier.profile_dataset(df, dataset_name=dataset_name)

        # 2. Generate analysis opportunity map
        opp_map = OpportunityMapGenerator.generate(sem_profile)

        # 3. Domain context
        domain = infer_domain(list(df.columns), dataset_name)

        # 4. Construct legacy-compatible column profiles while attaching semantic details
        legacy_profiles: list[ColumnProfile] = []
        for col_name in df.columns:
            sp = sem_profile.columns.get(str(col_name))
            if not sp:
                continue

            # Map semantic role to legacy inferred type
            if sp.semantic_role == SemanticRole.IDENTIFIER:
                inf_type = "identifier"
            elif sp.semantic_role == SemanticRole.DATETIME:
                inf_type = "datetime"
            elif sp.semantic_role in (SemanticRole.NUMERIC_MEASURE, SemanticRole.CURRENCY_MONETARY, SemanticRole.PERCENTAGE_RATE):
                inf_type = "numeric_measure"
            elif sp.semantic_role in (SemanticRole.CATEGORICAL_DIMENSION, SemanticRole.GEOGRAPHIC, SemanticRole.BOOLEAN, SemanticRole.POSSIBLE_TARGET):
                inf_type = "categorical_dimension"
            else:
                inf_type = "text_or_sparse"

            summary: dict[str, Any] = {}
            if sp.semantic_role in (SemanticRole.NUMERIC_MEASURE, SemanticRole.CURRENCY_MONETARY, SemanticRole.PERCENTAGE_RATE, SemanticRole.ORDINAL):
                if sp.min_value is not None:
                    summary["min"] = sp.min_value
                if sp.max_value is not None:
                    summary["max"] = sp.max_value
                if sp.mean is not None:
                    summary["mean"] = sp.mean
                if sp.median is not None:
                    summary["median"] = sp.median
            elif sp.top_categories:
                summary["top_categories"] = {k: v for k, v in sp.top_categories}

            legacy_profiles.append(ColumnProfile(
                name=sp.name,
                display_name=sp.display_name,
                inferred_type=inf_type,
                null_percentage=sp.null_percentage,
                distinct_count=sp.unique_count,
                unit=sp.unit or "",
                summary=summary,
                semantic_role=sp.semantic_role,
                metric_polarity=sp.metric_polarity,
                polarity_confidence=sp.polarity_confidence,
                polarity_reason=sp.polarity_reason,
                detection_reasons=sp.detection_reasons
            ))

        return DatasetProfile(
            dataset_name=dataset_name,
            business_domain=domain,
            row_count=sem_profile.row_count,
            column_count=sem_profile.column_count,
            numeric_measures=sem_profile.numeric_measures,
            categorical_dimensions=sem_profile.categorical_dimensions,
            timeline_columns=sem_profile.temporal_dimensions,
            identifier_columns=sem_profile.identifiers,
            profiles=legacy_profiles,
            observation_window=sem_profile.observation_window or "Cross-sectional snapshot",
            inferred_grain=sem_profile.inferred_grain,
            grain_confidence=sem_profile.grain_confidence,
            grain_key_columns=sem_profile.grain_key_columns,
            semantic_profile=sem_profile,
            opportunity_map=opp_map
        )
