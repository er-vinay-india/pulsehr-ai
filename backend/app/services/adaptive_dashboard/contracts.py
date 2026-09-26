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


class DecisionFocusSpec(BaseModel):
    """Specification for the Element 6 Decision Focus component (Gate 6)."""
    model_config = ConfigDict(extra="forbid")

    component_id: str = "decision_element"
    kind: Literal["decision_focus", "investigation_focus", "unavailable_card"] = "decision_focus"
    business_concept: str
    title: str
    subject_type: str
    subject_label: str
    metric_name: str
    unit: str
    observed_value: float | int
    formatted_observed_value: str
    comparator_label: str
    comparator_value: float | int
    formatted_comparator_value: str
    gap_value: float | int
    formatted_gap_value: str
    sample_size: int
    sample_label: str
    why_it_matters: str
    next_step: str
    monitor_metric: str | None = None
    supporting_component_id: str | None = None
    supporting_calculation_ids: list[str] = Field(default_factory=list)
    priority_basis: str
    glance: GlanceSpec
    explain: ExplainSpec
    inspect: InspectSpec
    evidence: EvidenceResult
    caption: str | None = None


class BriefingClaim(BaseModel):
    """Structured, evidence-bound claim segment within an executive briefing."""
    model_config = ConfigDict(extra="forbid")

    claim_id: str
    claim_type: Literal[
        "scope",
        "observation",
        "comparison",
        "association",
        "decision_focus",
        "next_check",
        "limitation",
    ]
    text: str
    source_component_id: str
    calculation_ids: list[str] = Field(default_factory=list)
    numeric_values: list[float | int] = Field(default_factory=list)
    unit: str = ""
    is_material_qualifier: bool = False


class ExecutiveBriefingSpec(BaseModel):
    """Specification for the Element 7 Executive Briefing component (Gate 7)."""
    model_config = ConfigDict(extra="forbid")

    component_id: str = "briefing_element"
    kind: Literal["executive_briefing", "briefing_unavailable"] = "executive_briefing"
    business_concept: str
    title: str = "Executive briefing"
    context_line: str
    spoken_text: str
    transcript_text: str
    claims: list[BriefingClaim]
    source_component_ids: list[str] = Field(default_factory=list)
    calculation_ids: list[str] = Field(default_factory=list)
    estimated_word_count: int
    estimated_duration_seconds: int
    snapshot: str
    glance: GlanceSpec
    explain: ExplainSpec
    inspect: InspectSpec
    caption: str | None = None


class AdaptiveDashboardResponse(BaseModel):
    """Top-level response delivering primary tile, secondary chart, tertiary breakdown, quaternary comparator, quinary disparity matrix, decision focus, executive briefing, exception watch, forward outlook, and enterprise synthesis."""
    model_config = ConfigDict(extra="forbid")

    version: str = "adaptive-v10"
    snapshot: str
    sheet_id: int
    manifest: SourceManifest
    contract: SemanticContract
    element: ComponentSpec
    secondary_element: ChartSpec | None = None
    tertiary_element: BreakdownSpec | None = None
    quaternary_element: ComparatorSpec | None = None
    quinary_element: DisparitySpec | None = None
    decision_element: DecisionFocusSpec | None = None
    briefing_element: ExecutiveBriefingSpec | None = None
    exception_element: "ExceptionWatchSpec | None" = None
    outlook_element: "ForwardOutlookSpec | None" = None
    enterprise_element: "EnterpriseSynthesisSpec | None" = None
    priority_insight: "PriorityInsightSpec | None" = None
    analysis_coverage: "AnalysisCoverageSummary | None" = None
    orchestrator_findings: list["UnifiedFinding"] = Field(default_factory=list)
    run_status: Literal["ready", "needs_definition", "failed"] = "ready"


class UnifiedFinding(BaseModel):
    """Immutable finding representation shared across Dashboard, Copilot, Narration, and Presentation."""
    model_config = ConfigDict(extra="forbid")

    finding_id: str
    recipe_id: str
    calculation_id: str
    definition_id: str
    source_sheet_ids: list[int]
    source_scope: list[str]
    snapshot: str
    status: Literal["available", "needs_definition", "withheld", "abstain"] = "available"

    short_business_title: str
    typed_value: float | None = None
    formatted_value: str
    unit: str

    population_or_exposure: str
    comparison_and_effect: str | None = None
    evidence_bound_observation: str
    possible_operational_implication: str | None = None
    one_next_check_or_action: str
    allowed_claim_level: Literal[
        "descriptive_fact",
        "reconciled_ledger",
        "statistical_association",
        "non_causal_forecast",
        "exploratory_pattern",
        "policy_exposure",
    ] = "descriptive_fact"

    visual_kind: str = "none"
    visual_points_summary: list[dict[str, Any]] = Field(default_factory=list)
    drilldown_route: str | None = None
    privacy_state: Literal["cohort_safe", "aggregate_safe", "pii_suppressed"] = "aggregate_safe"
    limitations: list[str] = Field(default_factory=list)

    # Ranking & deduplication keys
    analytical_subject: str
    decision_category: str
    rank_score: float = 0.0
    score_breakdown: dict[str, float] = Field(default_factory=dict)


class PriorityInsightSpec(BaseModel):
    """Specification for the top verified priority insight component."""
    model_config = ConfigDict(extra="forbid")

    finding_id: str
    recipe_id: str
    strategy_code: str
    strategy_name: str
    short_business_title: str
    prominent_number: str
    numeric_value: float | None = None
    unit: str
    comparison_label: str
    comparison_value: str
    implication: str
    next_check: str
    evidence_details: dict[str, Any]
    visual_type: Literal["category_comparison", "time_trend", "composition", "distribution", "none"] = "none"
    echarts_option: dict[str, Any] | None = None
    population_summary: str
    allowed_claim_level: str


class StrategyCoverageItem(BaseModel):
    """Status and missing prerequisites for one evaluated strategy (S01-S20)."""
    model_config = ConfigDict(extra="forbid")

    recipe_id: str
    strategy_code: str
    strategy_name: str
    status: Literal["completed", "needs_inputs", "incompatible", "execution_failure", "not_implemented"]
    status_label: str
    summary_reason: str
    missing_prerequisites: list[str] = Field(default_factory=list)
    generated_finding_ids: list[str] = Field(default_factory=list)


class AnalysisCoverageSummary(BaseModel):
    """Summary of strategy coverage and evaluated prerequisites across S01-S20."""
    model_config = ConfigDict(extra="forbid")

    total_strategies: int = 20
    completed_count: int
    needs_inputs_count: int
    incompatible_count: int
    execution_failure_count: int
    not_implemented_count: int
    # Optional legacy aliases for non-breaking API consumption
    supported_count: int | None = None
    descriptive_only_count: int | None = None
    strategies: list[StrategyCoverageItem]


class ExceptionPoint(BaseModel):
    """Single point in an exception timeline or segment dotplot."""
    model_config = ConfigDict(extra="forbid")

    label: str
    raw_period_or_segment: str
    value: float | None = None
    formatted_value: str
    expected_lower: float | None = None
    expected_upper: float | None = None
    is_exception: bool = False
    is_partial: bool = False
    sample_size: int | None = None


class ExceptionItem(BaseModel):
    """Structured representation of one statistically defensible unusual period or segment."""
    model_config = ConfigDict(extra="forbid")

    exception_id: str
    exception_type: Literal["temporal", "segment", "reconciled_rate", "distribution"]
    subject_type: str
    subject_label: str
    metric_name: str
    unit: str
    observed_value: float
    formatted_observed_value: str
    expected_lower: float
    expected_upper: float
    formatted_expected_range: str
    deviation_value: float
    formatted_deviation: str
    direction: Literal["above", "below", "outside", "neutral"]
    sample_size: int
    sample_label: str
    method: str
    context_flags: list[str] = Field(default_factory=list)
    calculation_id: str
    snapshot: str


class ExceptionVisualSpec(BaseModel):
    """Specification for the visual representation of an exception."""
    model_config = ConfigDict(extra="forbid")

    kind: Literal["timeline_band", "segment_dotplot", "none"] = "none"
    x_axis_title: str | None = None
    y_axis_title: str | None = None
    points: list[ExceptionPoint] = Field(default_factory=list)


class ExceptionWatchSpec(BaseModel):
    """Specification for the Element 8 Exception Watch component (Gate 8)."""
    model_config = ConfigDict(extra="forbid")

    component_id: str = "exception_element"
    kind: Literal["exception_watch", "exception_unavailable"] = "exception_watch"
    business_concept: str
    title: str = "Exception watch"
    lead_exception: ExceptionItem | None = None
    additional_exceptions: list[ExceptionItem] = Field(default_factory=list)
    total_eligible_exceptions: int = 0
    why_inspect: str
    next_check: str
    visual: ExceptionVisualSpec | None = None
    glance: GlanceSpec
    explain: ExplainSpec
    inspect: InspectSpec
    evidence: EvidenceResult | None = None
    caption: str | None = None


class OutlookPoint(BaseModel):
    """Single point in a historical actual series, target baseline, or forecast horizon."""
    model_config = ConfigDict(extra="forbid")

    period: str
    period_label: str
    actual_value: float | None = None
    forecast_value: float | None = None
    lower_bound: float | None = None
    upper_bound: float | None = None
    is_partial: bool = False


class ModelValidationResult(BaseModel):
    """Chronological backtest results evaluated against a naive baseline."""
    model_config = ConfigDict(extra="forbid")

    model_id: str
    model_label: str
    fold_count: int
    mae: float
    wape: float
    baseline_mae: float
    baseline_wape: float
    passed: bool
    rejection_reason: str | None = None


class ForwardOutlookSpec(BaseModel):
    """Specification for the Element 9 Forward Outlook component (Gate 9)."""
    model_config = ConfigDict(extra="forbid")

    component_id: str = "outlook_element"
    kind: Literal["target_gap", "statistical_forecast", "outlook_unavailable"]
    business_concept: str
    title: str = "Forward outlook"
    metric_name: str
    unit: str
    temporal_grain: str | None = None
    horizon: int | None = None
    actual_value: float | None = None
    target_value: float | None = None
    gap_value: float | None = None
    forecast_value: float | None = None
    lower_bound: float | None = None
    upper_bound: float | None = None
    model_id: str | None = None
    validation: ModelValidationResult | None = None
    points: list[OutlookPoint] = Field(default_factory=list)
    next_review_period: str | None = None
    why_available_or_unavailable: str
    glance: GlanceSpec
    explain: ExplainSpec
    inspect: InspectSpec
    evidence: EvidenceResult | None = None
    caption: str | None = None


class EnterpriseSourceRef(BaseModel):
    """Reference to a verified sibling sheet included in enterprise synthesis."""
    model_config = ConfigDict(extra="forbid")

    sheet_id: int
    display_name: str
    snapshot: str
    entity_count: int
    period: str | None = None
    role: str = "source"


class CrossSourceEvidence(BaseModel):
    """Structured evidence for a cross-source finding connecting two or more sheets."""
    model_config = ConfigDict(extra="forbid")

    finding_id: str
    recipe_id: str
    title: str
    observation: str
    interpretation: str
    metric_names: list[str] = Field(default_factory=list)
    values: list[float] = Field(default_factory=list)
    units: list[str] = Field(default_factory=list)
    paired_or_eligible_count: int
    matched_count: int
    unmatched_count: int
    coverage_ratio: float
    join_description: str
    calculation_id: str
    source_sheet_ids: list[int] = Field(default_factory=list)
    snapshot: str


class EnterpriseVisualPoint(BaseModel):
    """Aggregated, privacy-safe point for cross-source scatter, paired-dot, or flow visual."""
    model_config = ConfigDict(extra="forbid")

    label: str
    x: float
    y: float
    group: str | None = None
    sample_size: int | None = None
    formatted_x: str | None = None
    formatted_y: str | None = None


class EnterpriseVisualSpec(BaseModel):
    """Specification for the visual representation of enterprise synthesis."""
    model_config = ConfigDict(extra="forbid")

    kind: Literal["scatter", "paired_dot", "lifecycle_flow", "none"] = "none"
    x_axis_title: str | None = None
    y_axis_title: str | None = None
    points: list[EnterpriseVisualPoint] = Field(default_factory=list)
    reference_line: str | None = None


class EnterpriseDrilldownTarget(BaseModel):
    """Verified target destination in Data Explorer for cross-source inspection."""
    model_config = ConfigDict(extra="forbid")

    sheet_id: int
    label: str
    target_type: str = "sheet"
    route: str


class EnterpriseSynthesisSpec(BaseModel):
    """Specification for the Element 10 Enterprise Synthesis component (Gate 10)."""
    model_config = ConfigDict(extra="forbid")

    component_id: str = "enterprise_element"
    kind: Literal[
        "reconciled_metric",
        "matched_comparison",
        "cross_source_association",
        "temporal_comovement",
        "coverage_only",
    ]
    business_concept: str
    title: str = "Enterprise synthesis"
    sources: list[EnterpriseSourceRef] = Field(default_factory=list)
    source_count: int
    lead_finding: CrossSourceEvidence | None = None
    visual: EnterpriseVisualSpec | None = None
    what_it_establishes: str
    what_it_does_not_establish: str
    next_check: str
    drilldown_targets: list[EnterpriseDrilldownTarget] = Field(default_factory=list)
    glance: GlanceSpec
    explain: ExplainSpec
    inspect: InspectSpec
    evidence: EvidenceResult | None = None
    caption: str | None = None


AdaptiveDashboardResponse.model_rebuild()
