"""Visual Specification Contracts (Phase G5.4).

Defines:
- VisualInput: Typed, verified input for visual specification (zero raw dataframes, zero DB connections).
- VisualSpec: Theme-agnostic visual specification carrying topic identity, axes, series, and morphology.
- VisualSeries, VisualAxis, VisualReferenceLine: Typed visual building blocks.
- VisualMorphology, VisualIntent, ChartFamily: Governed visual taxonomy enums.
"""
from __future__ import annotations

from enum import Enum
from typing import Any, Literal
from pydantic import BaseModel, ConfigDict, Field

from ..evidence.contracts import BoundFact


class VisualMorphology(str, Enum):
    """Geometric and perceptual visual morphology."""
    LENGTH = "LENGTH"                # ranked_bar, horizontal_bar, column, bullet, variance_bar
    POINT = "POINT"                  # dot_plot, lollipop, scatter, bubble
    RANGE = "RANGE"                  # dumbbell, range_chart
    AREA = "AREA"                    # 100_percent_stacked_bar, stacked_bar, donut, pie
    TEMPORAL_PATH = "TEMPORAL_PATH"  # line, spline, slope
    MATRIX = "MATRIX"                # heatmap, correlation_matrix


class ChartFamily(str, Enum):
    """Governed visual family taxonomy."""
    COMPARISON = "COMPARISON"
    CORRELATION = "CORRELATION"
    PART_TO_WHOLE = "PART_TO_WHOLE"
    HIERARCHY = "HIERARCHY"
    TEMPORAL = "TEMPORAL"
    DISTRIBUTION = "DISTRIBUTION"
    FLOW = "FLOW"
    SPECIALTY = "SPECIALTY"


class VisualSeries(BaseModel):
    """Named quantitative data series within a visual specification."""
    model_config = ConfigDict(extra="ignore")

    name: str
    values: list[float | int] = Field(default_factory=list)
    unit: str = ""
    evidence_id: str | None = None
    semantic_role: str = "PRIMARY"  # PRIMARY, COMPARISON, BENCHMARK, CONTEXT


class VisualReferenceLine(BaseModel):
    """Governed benchmark or threshold reference line."""
    model_config = ConfigDict(extra="ignore")

    value: float
    label: str
    axis: Literal["x", "y"] = "y"
    line_style: Literal["dashed", "solid", "dotted"] = "dashed"


class VisualAxis(BaseModel):
    """Visual axis specification derived from underlying bound measures."""
    model_config = ConfigDict(extra="ignore")

    name: str
    label: str
    data_type: Literal["categorical", "quantitative", "temporal"] = "categorical"
    unit: str = ""
    min_value: float | None = None
    max_value: float | None = None


class VisualInput(BaseModel):
    """Strictly typed input to the VisualSpecFactory.
    
    Receives only verified analytical meaning and bound facts.
    Strictly isolated from raw rows, DataFrames, SQLite, DuckDB, React state, and theme tokens.
    """
    model_config = ConfigDict(extra="ignore")

    topic_id: str
    dataset_id: int | None = None
    dataset_version: int | None = None
    domain: str = "general"
    analytical_intent: str = "RANKING"
    entity_grain: str = "aggregate"  # PERSON, DEPARTMENT, STORE, LOCATION, aggregate
    bound_facts: list[BoundFact] = Field(default_factory=list)
    narrative_title: str = ""
    full_title: str = ""
    display_title: str = ""
    evidence_ids: list[str] = Field(default_factory=list)
    chart_type: str | None = None
    categories: list[str] = Field(default_factory=list)
    values: list[float] = Field(default_factory=list)
    series: list[dict[str, Any]] = Field(default_factory=list)
    benchmark: float | None = None
    benchmark_label: str | None = None
    unit: str = ""
    x_label: str = ""
    y_label: str = ""
    layout_hint: str = "MEDIUM"
    tokens: dict[str, Any] = Field(default_factory=dict)


class VisualSpec(BaseModel):
    """Theme-agnostic semantic visualization specification.
    
    Carries topic identity and analytical visual parameters.
    Contains zero theme styling (no hex codes, no light/dark color definitions).
    """
    model_config = ConfigDict(extra="ignore")

    topic_id: str
    dataset_id: int | None = None
    dataset_version: int | None = None
    domain: str = "general"
    entity_grain: str = "aggregate"
    chart_type: str
    full_title: str
    display_title: str
    analytical_intent: str
    visual_morphology: str
    categories: list[str] = Field(default_factory=list)
    values: list[float] = Field(default_factory=list)
    series: list[dict[str, Any]] = Field(default_factory=list)
    x_label: str = ""
    y_label: str = ""
    benchmark: float | None = None
    benchmark_label: str | None = None
    unit: str = ""
    key_metric: str = ""
    evidence_ids: list[str] = Field(default_factory=list)
    layout_hint: str = "MEDIUM"
    properties: dict[str, Any] = Field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Converts to dictionary representation compatible with ExecutiveTopic.visual_spec."""
        d: dict[str, Any] = {
            "topic_id": self.topic_id,
            "dataset_id": self.dataset_id,
            "domain": self.domain,
            "entity_grain": self.entity_grain,
            "chart_type": self.chart_type,
            "full_title": self.full_title,
            "display_title": self.display_title,
            "analytical_intent": self.analytical_intent,
            "visual_morphology": self.visual_morphology,
            "categories": self.categories,
            "values": self.values,
            "series": self.series,
            "x_label": self.x_label,
            "y_label": self.y_label,
            "unit": self.unit,
            "evidence_ids": self.evidence_ids,
            "layout_hint": self.layout_hint,
        }
        if self.benchmark is not None:
            d["benchmark"] = self.benchmark
        if self.benchmark_label:
            d["benchmark_label"] = self.benchmark_label
        if self.key_metric:
            d["key_metric"] = self.key_metric
        if self.properties:
            d.update(self.properties)
        return d


__all__ = [
    "ChartFamily",
    "VisualAxis",
    "VisualInput",
    "VisualMorphology",
    "VisualReferenceLine",
    "VisualSeries",
    "VisualSpec",
]
