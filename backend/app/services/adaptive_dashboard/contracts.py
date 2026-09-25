"""Typed semantic, measurement, and disclosure contracts for the Adaptive Decision Dashboard.

Follows Revision 4 of docs/adaptive-dashboard-design.md.
Implements the 3 disclosure layers:
- GLANCE: concise familiar business label, dominant number, optional short context qualifier, info trigger.
- EXPLAIN: noninteractive preview on hover/focus with plain-language definition and exact value.
- INSPECT: persistent accessible modal details with full definition, coverage, calculation, and provenance.
"""
from typing import Any, Literal
from pydantic import BaseModel, ConfigDict, Field


class SourceManifest(BaseModel):
    """Source-preserving metadata, row lineage, and cryptographic content hash."""
    model_config = ConfigDict(extra="forbid")

    sheet_id: int
    dataset_id: int | None = None
    sheet_name: str
    file_name: str
    display_name: str
    row_count: int
    col_count: int
    snapshot: str
    date_range: dict[str, Any] | None = None


class SemanticContract(BaseModel):
    """Derived semantic mappings, observed grain, and verification basis."""
    model_config = ConfigDict(extra="forbid")

    layout: Literal["wide_entity_matrix", "long_tabular", "unstructured"]
    entity_type: str
    entity_identifiers: list[str]
    distinct_entity_count: int | None = None
    date_column: str | None = None
    primary_measure: str | None = None
    grain_description: str
    domain: Literal[
        "commercial_retail",
        "workforce_hr",
        "demographics_public",
        "household_budget",
        "operations_support",
        "general_tabular",
    ] = "general_tabular"
    analyst_persona: str = "General Data Analyst"
    verified_mappings: dict[str, str] = Field(default_factory=dict)
    unresolved_meanings: list[str] = Field(default_factory=list)
    verification_basis: str


class MetricRequest(BaseModel):
    """Bounded, typed analytical operation request."""
    model_config = ConfigDict(extra="forbid")

    recipe_id: str
    target_construct: str
    operation: Literal["count_distinct_entities", "sum_measure", "average_measure", "honest_definition_card"]
    target_role: str
    grain: str
    rationale: str


class EvidenceResult(BaseModel):
    """Deterministic, validated evidence result bound to immutable source snapshot."""
    model_config = ConfigDict(extra="forbid")

    calculation_id: str
    snapshot: str
    definition_id: str
    status: Literal["available", "needs_definition", "unavailable", "invalid"]
    value: float | int | None
    unit: str
    aggregation: str
    numerator: float | int | None = None
    denominator: float | int | None = None
    is_known_zero: bool = False
    missing_observations: int = 0
    invalid_observations: int = 0
    excluded_observations: int = 0
    coverage_ratio: float = 1.0
    calculation_method: str
    provenance: str
    limitations: list[str] = Field(default_factory=list)


class GlanceSpec(BaseModel):
    """Layer 1: Default glance tile — dominant number with familiar business label."""
    model_config = ConfigDict(extra="forbid")

    label: str
    value: float | int | None = None
    formatted_value: str
    unit: str | None = None
    unit_display: Literal["implicit_in_label", "explicit_suffix", "currency_prefix", "none"] = "implicit_in_label"
    context_qualifier: str | None = None
    has_info_control: bool = True


class ExplainSpec(BaseModel):
    """Layer 2: Hover/focus preview — plain-language definition and exact value."""
    model_config = ConfigDict(extra="forbid")

    short_definition: str
    exact_value_text: str


class InspectSpec(BaseModel):
    """Layer 3: Persistent modal inspection — comprehensive audited evidence."""
    model_config = ConfigDict(extra="forbid")

    metric_title: str
    exact_value: str
    what_this_counts: str
    applicable_population: str
    source_name: str
    reporting_period: str | None = None
    calculation_method: str
    data_completeness: str
    workforce_coverage: str
    coverage_label: str = "Coverage Scope"
    coverage_value: str | None = None
    missing_observations: int = 0
    excluded_observations: int = 0
    selection_reason: str
    limitations: list[str] = Field(default_factory=list)
    calculation_id: str
    definition_id: str
    snapshot: str
    provenance: str


class NoticeSpec(BaseModel):
    """Classified materiality notice (routine, helpful, material_qualifier, definition_needed)."""
    model_config = ConfigDict(extra="forbid")

    level: Literal["routine", "helpful", "material_qualifier", "definition_needed"]
    message: str


class ComponentSpec(BaseModel):
    """Single visible component specification consumed by the dashboard renderer."""
    model_config = ConfigDict(extra="forbid")

    component_id: str = "primary_element"
    kind: Literal["kpi", "definition_card"]
    business_concept: str
    glance: GlanceSpec
    explain: ExplainSpec
    inspect: InspectSpec
    evidence: EvidenceResult
    material_notice: NoticeSpec | None = None
    # Compatibility fields for legacy consumers
    title: str
    verified_value: float | int | None = None
    formatted_value: str
    unit: str
    scope_label: str
    period_label: str | None = None
    coverage_qualifier: str
    selection_reason: str
    drilldown: str = "calculation_and_source"


class ChartPoint(BaseModel):
    """Single chronological point in a time series with distribution bounds."""
    model_config = ConfigDict(extra="forbid")

    period: str  # "YYYY-MM"
    period_label: str  # e.g. "Jan 2023"
    average_hours: float | None = None  # None for missing month gap
    formatted_hours: str | None = None  # e.g. "8h 00m"
    p10_hours: float | None = None
    p90_hours: float | None = None
    formatted_p10: str | None = None  # e.g. "7h 36m"
    formatted_p90: str | None = None  # e.g. "8h 24m"
    min_hours: float | None = None
    max_hours: float | None = None
    formatted_min: str | None = None
    formatted_max: str | None = None
    has_band: bool = False  # True only if valid_entries >= 20
    total_duration_minutes: int = 0
    valid_entries: int = 0
    observed_dates: int = 0
    excluded_entries: int = 0
    is_partial: bool = False
    partial_reason: str | None = None
    first_observed_date: str | None = None
    last_observed_date: str | None = None


class ChartSeries(BaseModel):
    """Named time series for the line chart."""
    model_config = ConfigDict(extra="forbid")

    name: str
    unit: str = "hours"
    points: list[ChartPoint]


class ChartSpec(BaseModel):
    """Specification for the secondary Apache ECharts line chart component."""
    model_config = ConfigDict(extra="forbid")

    component_id: str = "secondary_element"
    kind: Literal["line_chart", "unavailable_card"]
    business_concept: str
    title: str
    glance: GlanceSpec
    explain: ExplainSpec
    inspect: InspectSpec
    evidence: EvidenceResult
    chart_series: ChartSeries | None = None
    y_axis_min: float = 0.0
    y_axis_max: float = 12.0
    y_axis_ticks: list[float] = Field(default_factory=list)
    y_axis_tick_labels: list[str] = Field(default_factory=list)
    is_focused_scale: bool = False
    scale_label: str = "Focused scale"
    band_name: str = "Middle 80% of recorded entries"
    caption: str | None = None
    terminal_note: str | None = None
    data_through_date: str | None = None
    y_axis_title: str | None = None
    x_axis_title: str | None = None
    temporal_grain: str = "monthly"


class BreakdownItem(BaseModel):
    """Single category bucket in a categorical breakdown."""
    model_config = ConfigDict(extra="forbid")

    category: str
    value: float | int
    formatted_value: str
    share_pct: float
    secondary_value: float | int | None = None
    formatted_secondary: str | None = None
    count: int = 1


class ComparatorItem(BaseModel):
    """Single cohort or segment in a comparative analysis (Gate 4)."""
    model_config = ConfigDict(extra="forbid")

    cohort: str
    is_baseline: bool = False
    value: float | int
    formatted_value: str
    sample_size: int
    sample_label: str
    secondary_value: float | int | None = None
    formatted_secondary: str | None = None
    share_pct: float | None = None


class ComparatorSpec(BaseModel):
    """Specification for the quaternary explanatory comparator component (Gate 4)."""
    model_config = ConfigDict(extra="forbid")

    component_id: str = "quaternary_element"
    kind: Literal["cohort_comparator", "impact_ratio", "unavailable_card"] = "cohort_comparator"
    business_concept: str
    title: str
    dimension_name: str
    metric_name: str
    unit: str
    baseline_cohort: str
    comparator_cohort: str
    absolute_lift: float | int | None = None
    formatted_absolute_lift: str | None = None
    relative_lift_pct: float | None = None
    formatted_relative_lift: str | None = None
    items: list[ComparatorItem]
    glance: GlanceSpec
    explain: ExplainSpec
    inspect: InspectSpec
    evidence: EvidenceResult
    caption: str | None = None


class BreakdownSpec(BaseModel):
    """Specification for the tertiary categorical breakdown component (Gate 3)."""
    model_config = ConfigDict(extra="forbid")

    component_id: str = "tertiary_element"
    kind: Literal["ranked_bar", "unavailable_card"] = "ranked_bar"
    business_concept: str
    dimension_name: str
    title: str
    metric_name: str
    unit: str
    items: list[BreakdownItem]
    total_categories: int
    total_value: float | int
    formatted_total_value: str
    glance: GlanceSpec
    explain: ExplainSpec
    inspect: InspectSpec
    evidence: EvidenceResult
    caption: str | None = None


class DisparityItem(BaseModel):
    """Single segment or unit in a disparity / variance distribution matrix."""
    model_config = ConfigDict(extra="forbid")

    segment: str
    primary_value: float | int
    formatted_primary: str
    secondary_value: float | int | None = None
    formatted_secondary: str | None = None
    sample_size: int = 1
    sample_label: str = "observations"
    tier: Literal["top_tier", "benchmark_tier", "friction_tier", "standard_tier"] = "standard_tier"
    relative_index: float | None = None
    formatted_relative_index: str | None = None


class DisparitySpec(BaseModel):
    """Specification for the quinary segment disparity & variance matrix component (Gate 5)."""
    model_config = ConfigDict(extra="forbid")

    component_id: str = "quinary_element"
    kind: Literal["segment_disparity", "variance_matrix", "unavailable_card"] = "segment_disparity"
    business_concept: str
    title: str
    dimension_name: str
    metric_name: str
    secondary_metric_name: str | None = None
    unit: str
    spread_value: float | int
    formatted_spread: str
    spread_type: Literal["percentage_points", "ratio", "absolute_delta"] = "percentage_points"
    top_segment: str
    bottom_segment: str
    benchmark_value: float | int | None = None
    formatted_benchmark: str | None = None
    items: list[DisparityItem]
    glance: GlanceSpec
    explain: ExplainSpec
    inspect: InspectSpec
    evidence: EvidenceResult
    caption: str | None = None


class AdaptiveDashboardResponse(BaseModel):
    """Top-level response delivering primary tile, secondary chart, tertiary breakdown, quaternary comparator, and quinary disparity matrix."""
    model_config = ConfigDict(extra="forbid")

    version: str = "adaptive-v5"
    snapshot: str
    sheet_id: int
    manifest: SourceManifest
    contract: SemanticContract
    element: ComponentSpec
    secondary_element: ChartSpec | None = None
    tertiary_element: BreakdownSpec | None = None
    quaternary_element: ComparatorSpec | None = None
    quinary_element: DisparitySpec | None = None
    run_status: Literal["ready", "needs_definition", "failed"] = "ready"
