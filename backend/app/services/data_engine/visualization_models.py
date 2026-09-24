"""Visualization Data Models for PulseHR AI (Phase 3B).

Provides structured, zero-hallucination chart specifications deterministically
derived from CandidateFacts and SemanticDatasetProfiles.
"""

from typing import Any
from pydantic import BaseModel, Field


class ChartSeries(BaseModel):
    """Single series in a multi-series or single-series chart."""
    name: str
    values: list[float] = Field(default_factory=list)
    color_token: str | None = None


class ChartReferenceLine(BaseModel):
    """Benchmark, target, or baseline reference marker line."""
    label: str
    value: float
    line_style: str = "dashed"  # "dashed", "solid", "dotted"


class VisualChartSpec(BaseModel):
    """Structured, client-ready chart specification."""
    chart_id: str
    chart_type: str  # "line", "column", "bar", "horizontal_bar", "donut", "scatter", "pareto"
    title: str
    subtitle: str
    unit: str = ""
    categories: list[str] = Field(default_factory=list)
    series: list[ChartSeries] = Field(default_factory=list)
    reference_lines: list[ChartReferenceLine] = Field(default_factory=list)
    supporting_fact_id: str | None = None
    metric_col: str | None = None
    dimension_col: str | None = None
    aggregation_disclosure: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
