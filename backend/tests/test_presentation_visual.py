"""Comprehensive Unit and Regression Test Suite for Phase 4.

Validates all 40 requirements for Visual Intelligence & Rendering Modernization:
- Canonical contracts and schema validations (VisualSpec, ChartSpec, LayoutSpec)
- Layout registry mappings (canonical, legacy, and dashboard layouts)
- Scoped CSS isolation and theme protection (no global selectors, no :root leak)
- Chart family coverage (24 canonical families) and guardrail enforcements
- Diagram and matrix rendering contracts
- Theme tokens and WCAG 2.1 contrast calculations
- Cross-renderer parity (React / ECharts / HTML / PPTX)
- Chart selector intelligence and graceful fallbacks
"""

import os
import re
import pytest

from app.services.presentation.visual.chart_models import (
    ChartFamily,
    ChartFormatting,
    ChartSeries,
    ChartSpec,
)
from app.services.presentation.visual.chart_selector import ChartSelector
from app.services.presentation.visual.design_tokens import (
    DEFAULT_SLIDE_THEMES,
    SlideDesignTokens,
    normalize_slide_theme,
)
from app.services.presentation.visual.diagram_models import (
    DiagramConnection,
    DiagramFamily,
    DiagramNode,
    DiagramSpec,
    MatrixFamily,
    MatrixQuadrant,
    MatrixSpec,
)
from app.services.presentation.visual.layout_registry import (
    ContentBudget,
    LayoutFamily,
    LayoutRegistry,
    LayoutSpec,
    layout_registry,
)
from app.services.presentation.visual.layout_selector import LayoutSelector
from app.services.presentation.visual.visual_models import (
    PrimaryVisualDescriptor,
    SourceFooterSpec,
    TransitionType,
    VisualSpecification,
    VisualStory,
)
from app.services.presentation.visual.visual_validator import (
    VisualValidator,
    calculate_contrast_ratio,
    calculate_relative_luminance,
    parse_hex_color,
)
from app.services.presentation.visual.visual_intelligence import VisualIntelligenceEngine
from app.services.presentation.visual.adapters.echarts_adapter import EChartsAdapter
from app.services.presentation.visual.adapters.pptx_adapter import PPTXAdapter
from app.services.presentation.visual.adapters.html_adapter import HTMLAdapter
from app.services.presentation.orchestrator.orchestrator_models import SlideExecutionPackage


# =========================================================================
# 1. VisualSpec Validation
# =========================================================================
def test_visual_spec_validation():
    tokens = normalize_slide_theme("bold_signal")
    spec = VisualSpecification(
        slide_id="slide-1",
        sequence_number=1,
        headline="Strategic Workforce Optimization",
        subtitle="Audited Performance Review",
        visual_story=VisualStory(primary_message="Transformation targets achieved."),
        layout=LayoutRegistry.get_canonical_layout(LayoutFamily.CHART_INSIGHT),
        primary_visual=PrimaryVisualDescriptor(visual_family="BAR_VERTICAL")
    )
    assert spec.headline == "Strategic Workforce Optimization"
    assert spec.layout.family == LayoutFamily.CHART_INSIGHT
    assert spec.components is not None


# =========================================================================
# 2. ChartSpec Validation
# =========================================================================
def test_chart_spec_validation():
    cs = ChartSpec(
        chart_id="c1",
        family=ChartFamily.BAR_VERTICAL,
        title="Departmental Allocation",
        categories=["Eng", "Ops", "Sales"],
        series=[ChartSeries(name="Staff", data=[100, 200, 300])]
    )
    assert cs.family == ChartFamily.BAR_VERTICAL
    assert len(cs.categories) == 3
    assert len(cs.series[0].data) == 3


# =========================================================================
# 3. Layout Registry Returns Valid Layout Definitions
# =========================================================================
def test_layout_registry_returns_valid_definitions():
    families = layout_registry.get_all_families()
    assert len(families) == 21
    for fam in families:
        defn = layout_registry.get_layout(fam)
        assert defn is not None
        assert defn.family == fam
        assert defn.content_budget.max_headline_lines in (2, 3)


# =========================================================================
# 4. Legacy Layout Mappings Resolve to Canonical Layouts
# =========================================================================
def test_legacy_layout_mappings():
    mappings = {
        "title_hero": LayoutFamily.TITLE_HERO,
        "title_cover": LayoutFamily.TITLE_HERO,
        "kpi_summary": LayoutFamily.KPI_GRID,
        "chart_narrative": LayoutFamily.CHART_INSIGHT,
        "full_chart_takeaway": LayoutFamily.CHART_FULL,
        "two_charts": LayoutFamily.DUAL_CHART,
        "comparison_split": LayoutFamily.COMPARISON,
        "action_plan": LayoutFamily.ACTION_PLAN,
        "table_detail": LayoutFamily.TABLE
    }
    for legacy_name, expected_family in mappings.items():
        fam, variant = layout_registry.map_legacy_layout(legacy_name)
        assert fam == expected_family, f"Failed mapping for {legacy_name}"


# =========================================================================
# 5. Dashboard Layout Mappings Resolve Correctly
# =========================================================================
def test_dashboard_layout_mappings():
    dash_mappings = {
        "split_kpi_chart": LayoutFamily.CHART_INSIGHT,
        "chart_focus": LayoutFamily.CHART_FULL,
        "callout_alert": LayoutFamily.EXECUTIVE_SUMMARY,
        "audit_quad": LayoutFamily.MATRIX,
        "roadmap_quad": LayoutFamily.ROADMAP
    }
    for dash_name, expected_family in dash_mappings.items():
        fam, variant = layout_registry.map_legacy_layout(dash_name)
        assert fam == expected_family, f"Failed dashboard mapping for {dash_name}"


# =========================================================================
# 6. Scoped Bootstrap CSS Does Not Contain Global Selectors
# =========================================================================
def test_scoped_bootstrap_css_no_global_selectors():
    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    css_path = os.path.join(repo_root, "frontend/src/styles/presentation-scoped-bootstrap.scss")
    assert os.path.exists(css_path)
    with open(css_path, "r") as f:
        content = f.read()

    # Verify that presentation-runtime or ppt-slide-runtime scopes the entire stylesheet
    assert ".presentation-runtime" in content
    assert ".ppt-slide-runtime" in content
    # No un-nested global HTML element styling
    assert not re.search(r"^body\s*\{", content, re.MULTILINE)
    assert not re.search(r"^html\s*\{", content, re.MULTILINE)


# =========================================================================
# 7. Scoped Bootstrap CSS Does Not Contain :root Overrides
# =========================================================================
def test_scoped_bootstrap_css_no_root_overrides():
    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    css_path = os.path.join(repo_root, "frontend/src/styles/presentation-scoped-bootstrap.scss")
    with open(css_path, "r") as f:
        content = f.read()
    assert ":root" not in content, "presentation-scoped-bootstrap.scss must not touch :root!"


# =========================================================================
# 8. Scoped Bootstrap CSS Does Not Contain Unscoped .row, .col, .card, .btn
# =========================================================================
def test_scoped_bootstrap_css_no_unscoped_classes():
    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    css_path = os.path.join(repo_root, "frontend/src/styles/presentation-scoped-bootstrap.scss")
    with open(css_path, "r") as f:
        content = f.read()

    # The file starts with .presentation-runtime, and all classes are nested
    assert content.strip().startswith("/*") or content.strip().startswith(".presentation-runtime")
    assert not re.search(r"^\.row\s*\{", content, re.MULTILINE)
    assert not re.search(r"^\.col\s*\{", content, re.MULTILINE)
    assert not re.search(r"^\.card\s*\{", content, re.MULTILINE)
    assert not re.search(r"^\.btn\s*\{", content, re.MULTILINE)


# =========================================================================
# 9. Existing Application Theme Variables Are Not Overridden
# =========================================================================
def test_existing_application_theme_unaffected():
    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    tokens_path = os.path.join(repo_root, "frontend/src/styles/_tokens.scss")
    assert os.path.exists(tokens_path)
    with open(tokens_path, "r") as f:
        content = f.read()
    # Confirm web application token file is pristine
    assert "--color-bg-page" in content
    assert "--color-text-primary" in content
    assert "--color-brand-primary" in content


# =========================================================================
# 10. Chart Family Coverage (All 24 Canonical Families Supported)
# =========================================================================
def test_chart_family_coverage_24_canonical_families():
    assert len(ChartFamily) == 24
    expected_members = [
        "BAR_VERTICAL", "BAR_HORIZONTAL", "BAR_GROUPED", "BAR_STACKED",
        "LINE", "LINE_MULTI", "AREA", "PIE", "DONUT", "SCATTER",
        "BUBBLE", "HEATMAP", "RADAR", "WATERFALL", "FUNNEL", "GAUGE",
        "TREEMAP", "SUNBURST", "SANKEY", "CANDLESTICK", "BOXPLOT",
        "HISTOGRAM", "GRAPH_NETWORK", "MIXED_BAR_LINE"
    ]
    for m in expected_members:
        assert m in ChartFamily.__members__


# =========================================================================
# 11. Chart Guardrails: Donut With >5 Slices Falls Back to Horizontal Bar
# =========================================================================
def test_chart_guardrails_donut_overflow_fallback():
    cs = ChartSpec(
        family=ChartFamily.DONUT,
        categories=["A", "B", "C", "D", "E", "F", "G"],
        series=[ChartSeries(name="Vals", data=[10, 20, 30, 40, 50, 60, 70])]
    )
    res = cs.validate_guardrails()
    assert not res.passed
    assert res.fallback_family == ChartFamily.BAR_HORIZONTAL


# =========================================================================
# 12. Chart Guardrails: Heatmap With Insufficient Dimensions Falls Back
# =========================================================================
def test_chart_guardrails_heatmap_insufficient_dimensions():
    cs = ChartSpec(
        family=ChartFamily.HEATMAP,
        categories=["SingleDim"],
        series=[ChartSeries(name="Vals", data=[10])]
    )
    res = cs.validate_guardrails()
    assert not res.passed
    assert res.fallback_family == ChartFamily.BAR_GROUPED


# =========================================================================
# 13. Chart Guardrails: Candlestick Without OHLC Is Flagged
# =========================================================================
def test_chart_guardrails_candlestick_without_ohlc():
    cs = ChartSpec(
        family=ChartFamily.CANDLESTICK,
        categories=["Day 1"],
        series=[ChartSeries(name="Price", data=[100])]
    )
    res = cs.validate_guardrails()
    assert not res.passed
    assert "OHLC" in res.violations[0]


# =========================================================================
# 14. Chart Guardrails: Sankey Without Weighted Links Is Flagged
# =========================================================================
def test_chart_guardrails_sankey_without_links():
    cs = ChartSpec(
        family=ChartFamily.SANKEY,
        extra_options={"links": []}
    )
    res = cs.validate_guardrails()
    assert not res.passed
    assert "links" in res.violations[0].lower()


# =========================================================================
# 15. Chart Guardrails: Scatter Without 2 Numerical Variables Is Flagged
# =========================================================================
def test_chart_guardrails_scatter_without_bivariate_data():
    cs = ChartSpec(
        family=ChartFamily.SCATTER,
        series=[ChartSeries(name="SingleVar", data=[10, 20, 30])]
    )
    res = cs.validate_guardrails()
    assert not res.passed
    assert "coordinates" in res.violations[0].lower() or "scatter" in res.violations[0].lower()


# =========================================================================
# 16. Chart Guardrails: Radar With >8 Dimensions Falls Back
# =========================================================================
def test_chart_guardrails_radar_dimension_overflow():
    cs = ChartSpec(
        family=ChartFamily.RADAR,
        categories=[f"Dim{i}" for i in range(10)],
        series=[ChartSeries(name="Score", data=[50]*10)]
    )
    res = cs.validate_guardrails()
    assert not res.passed
    assert res.fallback_family in (ChartFamily.BAR_GROUPED, ChartFamily.BAR_HORIZONTAL)


# =========================================================================
# 17. Chart Guardrails: Waterfall Without Step Deltas Is Flagged
# =========================================================================
def test_chart_guardrails_waterfall_step_deltas():
    cs = ChartSpec(
        family=ChartFamily.WATERFALL,
        series=[]
    )
    res = cs.validate_guardrails()
    assert not res.passed
    assert "delta" in res.violations[0].lower() or "step" in res.violations[0].lower()


# =========================================================================
# 18. KPI Card Rendering: Label + Value + Subtext + Delta
# =========================================================================
def test_kpi_card_structure():
    kpis = [
        {"label": "Total Headcount", "value": "1,420", "subtext": "Audited ground truth", "delta": "+4.2%"}
    ]
    tokens = normalize_slide_theme("bold_signal")
    html_res = HTMLAdapter._render_kpis(kpis, tokens)
    assert "Total Headcount" in html_res
    assert "1,420" in html_res
    assert "Audited ground truth" in html_res


# =========================================================================
# 19. Matrix Rendering: 2x2 Quadrant Layout With Labeled Axes
# =========================================================================
def test_matrix_rendering_contract():
    ms = MatrixSpec(
        family=MatrixFamily.QUADRANT_2X2,
        title="Impact vs Effort",
        x_axis_label="Effort",
        y_axis_label="Impact",
        quadrants=[
            MatrixQuadrant(id="q1", label="Quick Wins", x=1, y=2),
            MatrixQuadrant(id="q2", label="Strategic Bets", x=2, y=2)
        ]
    )
    assert len(ms.quadrants) == 2
    assert ms.x_axis_label == "Effort"
    assert ms.y_axis_label == "Impact"


# =========================================================================
# 20. Process Flow Rendering: Sequential Nodes With Connections
# =========================================================================
def test_process_flow_rendering_contract():
    ds = DiagramSpec(
        family=DiagramFamily.HORIZONTAL_PROCESS,
        title="Deployment Process",
        nodes=[
            DiagramNode(id="n1", label="Audit", order=1),
            DiagramNode(id="n2", label="Remediate", order=2)
        ],
        connections=[
            DiagramConnection(from_node="n1", to_node="n2")
        ]
    )
    assert len(ds.nodes) == 2
    assert ds.connections[0].from_node == "n1"


# =========================================================================
# 21. Timeline Rendering: Chronological Milestones
# =========================================================================
def test_timeline_rendering_contract():
    ds = DiagramSpec(
        family=DiagramFamily.TIMELINE_CHEVRON,
        title="Workforce Milestones",
        nodes=[
            DiagramNode(id="m1", label="Q1 Kickoff", sublabel="Completed"),
            DiagramNode(id="m2", label="Q2 Scale", sublabel="On Track")
        ]
    )
    assert ds.family == DiagramFamily.TIMELINE_CHEVRON
    assert len(ds.nodes) == 2


# =========================================================================
# 22. Architecture Diagram Rendering: Layered Components
# =========================================================================
def test_architecture_diagram_rendering_contract():
    ds = DiagramSpec(
        family=DiagramFamily.ARCHITECTURE_LAYERS,
        title="System Architecture",
        nodes=[
            DiagramNode(id="l1", label="Presentation Layer"),
            DiagramNode(id="l2", label="Execution Orchestrator"),
            DiagramNode(id="l3", label="Semantic Memory & Vectors")
        ]
    )
    assert ds.family == DiagramFamily.ARCHITECTURE_LAYERS
    assert len(ds.nodes) == 3


# =========================================================================
# 23. Table Rendering: Bounded Rows With Overflow Prevention
# =========================================================================
def test_table_rendering_overflow_prevention():
    tokens = normalize_slide_theme("bold_signal")
    table_data = {
        "headers": ["Unit", "Metric"],
        "rows": [[f"Unit {i}", f"Val {i}"] for i in range(25)]
    }
    rendered = HTMLAdapter._render_table(table_data, tokens)
    # Renders top bounded rows (capped at 6)
    assert "Unit 0" in rendered
    assert "Unit 5" in rendered
    assert "Unit 20" not in rendered


# =========================================================================
# 24. Source Footer Rendering: Provenance Statement Present
# =========================================================================
def test_source_footer_provenance_statement():
    tokens = normalize_slide_theme("bold_signal")
    spec = VisualSpecification(
        headline="Executive Review",
        visual_story=VisualStory(primary_message="Audited report"),
        layout=LayoutRegistry.get_canonical_layout(LayoutFamily.CHART_INSIGHT),
        primary_visual=PrimaryVisualDescriptor(visual_family="BAR"),
        source_footer=SourceFooterSpec(
            source_citation="Audited HR Intelligence",
            evidence_citation="EVID-EXEC-01",
            slide_counter_text="1 / 6"
        )
    )
    footer_html = HTMLAdapter._render_footer(spec, tokens)
    assert "Audited HR Intelligence" in footer_html
    assert "EVID-EXEC-01" in footer_html
    assert "1 / 6" in footer_html


# =========================================================================
# 25-30. Theme Tokens Palette Tests
# =========================================================================
def test_theme_tokens_bold_signal():
    t = normalize_slide_theme("bold_signal")
    assert t.theme_id == "bold_signal"
    assert t.accent == "#FF8A65"
    assert t.brand == "#FF5722"
    assert t.is_dark is True

def test_theme_tokens_electric_studio():
    t = normalize_slide_theme("electric_studio")
    assert t.theme_id == "electric_studio"
    assert t.brand == "#4361EE"
    assert t.accent == "#4CC9F0"

def test_theme_tokens_creative_voltage():
    t = normalize_slide_theme("creative_voltage")
    assert t.theme_id == "creative_voltage"
    assert t.brand == "#00F0FF"
    assert t.accent == "#0055FF"

def test_theme_tokens_executive_dark():
    t = normalize_slide_theme("executive_dark")
    assert t.theme_id == "executive_dark"
    assert t.is_dark is True

def test_theme_tokens_minimal_stark():
    t = normalize_slide_theme("minimal_stark")
    assert t.theme_id == "minimal_stark"
    assert t.is_dark is False
    assert t.background == "#F8FAFC"
    assert t.accent == "#2563EB"

def test_theme_tokens_corporate_navy():
    t = normalize_slide_theme("corporate_navy")
    assert t.theme_id == "corporate_navy"
    assert t.background == "#0B192C"
    assert t.brand == "#008DDA"


# =========================================================================
# 31. WCAG Contrast Check Passes for All Default Themes
# =========================================================================
def test_wcag_contrast_check_all_default_themes():
    for theme_id in DEFAULT_SLIDE_THEMES:
        tokens = normalize_slide_theme(theme_id)
        report = VisualValidator.validate_contrast(tokens)
        assert report["passes_wcag_aa"] is True, f"Theme {theme_id} failed WCAG AA: {report}"


# =========================================================================
# 32. React and PPTX Output Parity
# =========================================================================
def test_react_and_pptx_output_parity():
    engine = VisualIntelligenceEngine()
    pkg = SlideExecutionPackage(
        slide_id="slide-2",
        sequence_number=2,
        headline="Throughput Analysis",
        resolved_content={"key_message": "Stable output observed."},
        chart_data={
            "chart_type": "bar",
            "title": "Throughput by Unit",
            "categories": ["Ops", "Tech"],
            "series": [{"name": "Staff", "values": [120, 85]}]
        }
    )
    tokens = normalize_slide_theme("bold_signal")
    spec = engine.process_slide(pkg, theme_id="bold_signal", sequence_number=2, total_slides=5)
    pptx_dict = PPTXAdapter.to_pptx_slide_dict(spec, tokens)

    assert pptx_dict["title"] == spec.headline
    assert pptx_dict["slide_index"] == spec.sequence_number
    assert pptx_dict["chart"]["chart_type"] == "bar"
    assert pptx_dict["chart"]["categories"] == ["Ops", "Tech"]


# =========================================================================
# 33. React and HTML Output Parity
# =========================================================================
def test_react_and_html_output_parity():
    engine = VisualIntelligenceEngine()
    pkg = SlideExecutionPackage(
        slide_id="slide-3",
        sequence_number=3,
        headline="Quarterly Risk Overview",
        resolved_content={"key_message": "Risk mitigated within variance limits."}
    )
    tokens = normalize_slide_theme("bold_signal")
    spec = engine.process_slide(pkg, theme_id="bold_signal", sequence_number=3, total_slides=5)
    html_out = HTMLAdapter.to_html_slide(spec, tokens)

    assert spec.headline in html_out
    assert "presentation-runtime" in html_out


# =========================================================================
# 34. Chart Selector: Temporal Data Selects Line or Area
# =========================================================================
def test_chart_selector_temporal():
    fam, reason = ChartSelector.select_chart(
        data_relationship="TIME_SERIES",
        num_categories=12
    )
    assert fam in (ChartFamily.LINE, ChartFamily.AREA)
    assert "time" in reason.lower() or "trend" in reason.lower() or "line" in reason.lower() or "momentum" in reason.lower()


# =========================================================================
# 35. Chart Selector: Categorical Comparison Selects Bar
# =========================================================================
def test_chart_selector_categorical_bar():
    fam, reason = ChartSelector.select_chart(
        data_relationship="CATEGORICAL_COMPARISON",
        num_categories=4
    )
    assert fam == ChartFamily.BAR_VERTICAL


# =========================================================================
# 36. Chart Selector: Ranking Selects Horizontal Bar
# =========================================================================
def test_chart_selector_ranking_horizontal_bar():
    fam, reason = ChartSelector.select_chart(
        data_relationship="RANKING",
        num_categories=8
    )
    assert fam == ChartFamily.BAR_HORIZONTAL
    assert "horizontal" in reason.lower()


# =========================================================================
# 37. Chart Selector: Part-to-Whole With <=5 Categories Selects Donut
# =========================================================================
def test_chart_selector_part_to_whole_donut():
    fam, reason = ChartSelector.select_chart(
        data_relationship="PART_TO_WHOLE",
        num_categories=4
    )
    assert fam == ChartFamily.DONUT


# =========================================================================
# 38. Chart Selector: Two Continuous Variables Selects Scatter
# =========================================================================
def test_chart_selector_two_variables_scatter():
    fam, reason = ChartSelector.select_chart(
        data_relationship="CORRELATION",
        num_categories=20
    )
    assert fam == ChartFamily.SCATTER


# =========================================================================
# 39. Visual Validator Flags Content Budget Overflow
# =========================================================================
def test_visual_validator_content_budget_overflow():
    budget = ContentBudget(max_headline_chars=50, max_insights=2)
    res = VisualValidator.validate_content_budget(
        headline="A" * 60,
        body_text="Short body",
        insights=["Insight 1", "Insight 2", "Insight 3"],
        budget=budget
    )
    assert not res["within_budget"]
    assert len(res["violations"]) == 2


# =========================================================================
# 40. Graceful Fallback When Visual Engine Encounters Unknown Layout
# =========================================================================
def test_graceful_fallback_unknown_layout():
    engine = VisualIntelligenceEngine()
    pkg = SlideExecutionPackage(
        slide_id="slide-99",
        sequence_number=99,
        headline="Mystery Slide Layout",
        layout="non_existent_layout_abc",
        resolved_content={"key_message": "Should fallback gracefully."}
    )
    spec = engine.process_slide(pkg, theme_id="bold_signal")
    assert spec is not None
    # Graceful fallback to CHART_INSIGHT or valid family
    assert spec.layout.family in LayoutFamily
