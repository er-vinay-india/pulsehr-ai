from __future__ import annotations

from typing import Any
from pydantic import BaseModel, Field


class ToolExecutionResult(BaseModel):
    """Standardized deterministic execution result returned by all registered tools."""
    tool_name: str
    status: str = "success"  # success | error
    data: dict[str, Any] = Field(default_factory=dict)
    source_ids: list[str] = Field(default_factory=list)
    evidence_ids: list[str] = Field(default_factory=list)
    dataset_ids: list[str] = Field(default_factory=list)
    memory_ids: list[str] = Field(default_factory=list)
    calculation_method: str = ""
    error: str | None = None
    execution_time_ms: float = 0.0


class RetrieveMemoryArgs(BaseModel):
    query: str
    workspace_id: str | None = None
    domain: str | None = None
    limit: int = 5


class FetchEvidenceArgs(BaseModel):
    evidence_ids: list[str]


class CalculateMetricArgs(BaseModel):
    metric_type: str  # percentage_share | dispersion_ratio | surge_delta | growth_rate | mean
    values: list[float] = Field(default_factory=list)
    baseline: float | None = None
    comparison_value: float | None = None
    calculation_status: str | None = None


class AggregateDataArgs(BaseModel):
    records: list[dict[str, Any]]
    group_by: str
    metric_col: str | None = None
    agg_fn: str = "count"  # count | sum | mean


class RankCategoriesArgs(BaseModel):
    records: list[dict[str, Any]]
    dimension_col: str
    top_n: int = 6


class DetectOutliersArgs(BaseModel):
    values: list[float]
    threshold_iqr: float = 1.5


class DetectTrendArgs(BaseModel):
    time_series: list[float]
    labels: list[str] | None = None


class PrepareChartDataArgs(BaseModel):
    chart_type: str  # line | bar | donut | column
    title: str
    categories: list[str]
    series: list[dict[str, Any]]
    subtitle: str = ""


class PrepareTableDataArgs(BaseModel):
    headers: list[str]
    rows: list[list[str]]
    max_rows: int = 8


class VerifyClaimArgs(BaseModel):
    claimed_value: float
    expected_value: float
    tolerance_pct: float = 0.1
