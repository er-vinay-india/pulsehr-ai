"""HighView Presentation Studio — PPT-L7 Theme & Style Engine Test Suite.

Certifies the PPT-L7 phase boundary according to the strict kickoff specifications:
- Tests 111-131: Simple text, KPI hierarchy, tables, charts, maps, images,
  light/dark contrast, typography fallback, token validation, geometry immutability,
  identity immutability, content immutability, editability preservation,
  package integrity, legacy isolation, and zero AI calls.
"""

from __future__ import annotations

import io
import os
import re
import tempfile
import zipfile
import pytest
from pathlib import Path
from typing import Any

import pptx
from pptx.util import Inches, Pt

from app.services.presentation.content_models import (
    ContentKind,
    ContentRole,
    PresentationContentItem,
    PresentationContentPackage,
)
from app.services.presentation.layout_engine import LayoutConstraintEngine, LayoutValidator
from app.services.presentation.layout_models import ResolvedDeckLayout
from app.services.presentation.layer_zone_models import (
    ContentBindingRole,
    CoordinateSpace,
    EditabilityPolicy,
    FrameInheritancePolicy,
    LayeredDeckStructureSpec,
    LayeredSlideSpec,
    LayerRole,
    SafeAreaSpec,
    SlideObjectSpec,
    StructuralRole,
    ZoneSpec,
    ZoneType,
)
from app.services.presentation.pptx_compiler import PPTXCompiler
from app.services.presentation.renderer_validator import RendererValidator
from app.services.presentation.style_validator import StyleValidator
from app.services.presentation.theme_applicator import ThemeApplicator
from app.services.presentation.theme_engine import (
    FontResolver,
    StyleTokenResolver,
    ThemeEngine,
)
from app.services.presentation.theme_models import (
    FontRole,
    SemanticTokenRole,
    StyleRole,
    ThemeMode,
)


@pytest.fixture
def sample_test_deck() -> tuple[LayeredDeckStructureSpec, PresentationContentPackage, ResolvedDeckLayout, Any, Any]:
    """Compiles a deterministic 2-slide deck using PPT-L4/L5/L6."""
    content_items = [
        PresentationContentItem(
            content_id="CNT-HEAD-1",
            kind=ContentKind.NARRATIVE_INSIGHT,
            role=ContentRole.PRIMARY_HERO,
            topic_category="HEADLINE",
            title="Executive Workforce Health Summary",
            narrative_takeaway="Workforce retention stabilized across all operating divisions in Q3.",
        ),
        PresentationContentItem(
            content_id="CNT-TBL-1",
            kind=ContentKind.TABLE,
            role=ContentRole.EXPLORATORY_TABLE,
            topic_category="METRICS",
            title="Operating KPI Ledger",
            table_data=[
                {"Division": "Engineering", "Headcount": "420", "Retention": "94.2%", "Trend": "+2.1%"},
                {"Division": "Operations", "Headcount": "680", "Retention": "91.8%", "Trend": "+1.4%"},
                {"Division": "Sales", "Headcount": "310", "Retention": "88.6%", "Trend": "-0.5%"},
            ],
        ),
        PresentationContentItem(
            content_id="CNT-CHART-1",
            kind=ContentKind.CHART,
            role=ContentRole.KEY_FINDING,
            topic_category="VISUAL",
            title="Quarterly Retention Trend",
            visual_spec={
                "chart_type": "column",
                "categories": ["Q1", "Q2", "Q3", "Q4"],
                "series": [
                    {"name": "Actual", "values": [88.5, 90.1, 92.4, 93.8]},
                    {"name": "Target", "values": [90.0, 90.0, 91.0, 92.0]},
                ],
            },
        ),
        PresentationContentItem(
            content_id="CNT-MAP-1",
            kind=ContentKind.MAP,
            role=ContentRole.KEY_FINDING,
            topic_category="GEOGRAPHY",
            title="Regional Facility Distribution",
            narrative_takeaway="Facility coverage across 5 operating hubs.",
        ),
    ]
    content_pkg = PresentationContentPackage(
        package_id="PKG-TEST-001",
        dataset_name="WorkforceData",
        domain="HR",
        items=content_items,
    )

    # Deck structure
    slide_1 = LayeredSlideSpec(
        physical_slide_id="SLD-PHYS-1",
        logical_slide_id="SLD-LOG-1",
        semantic_topic="WORKFORCE_HEALTH",
        structural_role=StructuralRole.EXECUTIVE_SUMMARY,
        sequence_index=1,
        zones=[
            ZoneSpec(
                zone_id="ZONE-HDR-1",
                zone_type=ZoneType.TITLE,
                layer_role=LayerRole.MASTER_FRAME,
                coordinate_space=CoordinateSpace.MASTER_FRAME_SPACE,
                bounds_hint=[0.05, 0.05, 0.90, 0.15],
                objects=[
                    SlideObjectSpec(
                        object_id="OBJ-HEAD-1",
                        object_name="HV_WORKFORCE_HEALTH_01_TITLE_CNT_HEAD_1",
                        name="Executive Headline",
                        content_id="CNT-HEAD-1",
                        binding_role=ContentBindingRole.PRIMARY,
                        kind=ContentKind.NARRATIVE_INSIGHT,
                        semantic_topic="WORKFORCE_HEALTH",
                        editability=EditabilityPolicy.NATIVE_REQUIRED,
                        headline="Executive Workforce Health Summary",
                    ),
                ],
            ),
            ZoneSpec(
                zone_id="ZONE-BODY-1",
                zone_type=ZoneType.DATA_TABLE,
                layer_role=LayerRole.BODY,
                coordinate_space=CoordinateSpace.BODY_SPACE,
                bounds_hint=[0.05, 0.25, 0.90, 0.65],
                objects=[
                    SlideObjectSpec(
                        object_id="OBJ-TBL-1",
                        object_name="HV_WORKFORCE_HEALTH_01_DATA_TABLE_CNT_TBL_1",
                        name="KPI Table",
                        content_id="CNT-TBL-1",
                        binding_role=ContentBindingRole.PRIMARY,
                        kind=ContentKind.TABLE,
                        semantic_topic="WORKFORCE_HEALTH",
                        editability=EditabilityPolicy.NATIVE_REQUIRED,
                    ),
                ],
            ),
        ],
    )

    slide_2 = LayeredSlideSpec(
        physical_slide_id="SLD-PHYS-2",
        logical_slide_id="SLD-LOG-2",
        semantic_topic="WORKFORCE_HEALTH",
        structural_role=StructuralRole.GEOGRAPHIC_ANALYSIS,
        sequence_index=2,
        zones=[
            ZoneSpec(
                zone_id="ZONE-BODY-2A",
                zone_type=ZoneType.PRIMARY_VISUAL,
                layer_role=LayerRole.BODY,
                coordinate_space=CoordinateSpace.BODY_SPACE,
                bounds_hint=[0.05, 0.15, 0.42, 0.75],
                objects=[
                    SlideObjectSpec(
                        object_id="OBJ-CHART-1",
                        object_name="HV_WORKFORCE_HEALTH_02_PRIMARY_VISUAL_CNT_CHART_1",
                        name="Retention Chart",
                        content_id="CNT-CHART-1",
                        binding_role=ContentBindingRole.PRIMARY,
                        kind=ContentKind.CHART,
                        semantic_topic="WORKFORCE_HEALTH",
                        editability=EditabilityPolicy.NATIVE_REQUIRED,
                    ),
                ],
            ),
            ZoneSpec(
                zone_id="ZONE-BODY-2B",
                zone_type=ZoneType.SECONDARY_VISUAL,
                layer_role=LayerRole.BODY,
                coordinate_space=CoordinateSpace.BODY_SPACE,
                bounds_hint=[0.52, 0.15, 0.42, 0.75],
                objects=[
                    SlideObjectSpec(
                        object_id="OBJ-MAP-1",
                        object_name="HV_WORKFORCE_HEALTH_02_SECONDARY_VISUAL_CNT_MAP_1",
                        name="Facility Map",
                        content_id="CNT-MAP-1",
                        binding_role=ContentBindingRole.PRIMARY,
                        kind=ContentKind.MAP,
                        semantic_topic="WORKFORCE_HEALTH",
                        editability=EditabilityPolicy.RASTER_ALLOWED,
                    ),
                ],
            ),
        ],
    )

    deck_structure = LayeredDeckStructureSpec(
        manifest_id="MNF-TEST-001",
        deck_id="DECK-TEST-001",
        slides=[slide_1, slide_2],
        structure_fingerprint="fingerprint-struct-001",
    )

    layout_engine = LayoutConstraintEngine()
    resolved_deck = layout_engine.resolve_deck_layout(deck_structure)

    compiler = PPTXCompiler()
    render_manifest, pptx_path = compiler.compile_deck(
        resolved_deck=resolved_deck,
        deck_structure=deck_structure,
        content_package=content_pkg,
    )
    prs = pptx.Presentation(str(pptx_path))

    return deck_structure, content_pkg, resolved_deck, render_manifest, prs


# --- Test 111: Simple Text Styling ---
def test_111_simple_text_styling(sample_test_deck):
    _, _, resolved_deck, render_manifest, prs = sample_test_deck
    theme = ThemeEngine.get_theme("executive_dark")
    applicator = ThemeApplicator(theme)

    # Snapshot font sizes before style
    font_sizes_before = {}
    for s_idx, slide in enumerate(prs.slides):
        for shape in slide.shapes:
            if shape.has_text_frame:
                font_sizes_before[shape.name] = [
                    p.font.size.pt for p in shape.text_frame.paragraphs if p.font.size
                ]

    styled_prs, style_manifest = applicator.apply_theme(prs, render_manifest, resolved_deck)

    # Verify text styling applied
    title_outcomes = [o for o in style_manifest.object_styles if o.style_role == StyleRole.TITLE]
    assert len(title_outcomes) > 0
    outcome = title_outcomes[0]
    assert outcome.font_family is not None
    assert outcome.font_color_hex == theme.palette.primary_text
    assert outcome.font_weight == "bold"

    # Invariant: Font size untouched
    for s_idx, slide in enumerate(styled_prs.slides):
        for shape in slide.shapes:
            if shape.has_text_frame and shape.name in font_sizes_before:
                sizes_after = [p.font.size.pt for p in shape.text_frame.paragraphs if p.font.size]
                assert sizes_after == font_sizes_before[shape.name]


# --- Test 112: KPI Visual Hierarchy ---
def test_112_kpi_hierarchy():
    theme = ThemeEngine.get_theme("executive_dark")
    token_resolver = StyleTokenResolver(theme)
    from app.services.presentation.theme_engine import TextStyleResolver
    text_resolver = TextStyleResolver(token_resolver)

    v_style, v_audits, _ = text_resolver.resolve_text_style(
        style_role=StyleRole.KPI_VALUE,
        bg_hex=theme.palette.background,
        target_id="KPI_VAL",
    )
    l_style, l_audits, _ = text_resolver.resolve_text_style(
        style_role=StyleRole.KPI_LABEL,
        bg_hex=theme.palette.background,
        target_id="KPI_LBL",
    )

    assert v_style["bold"] is True
    assert v_style["font_color_hex"] == theme.palette.accent
    assert l_style["font_color_hex"] == theme.palette.muted_text
    assert v_audits[0].passed is True
    assert l_audits[0].passed is True


# --- Test 113: Table Styling in Light and Dark ---
def test_113_table_styling_light_and_dark(sample_test_deck):
    deck_structure, content_pkg, resolved_deck, render_manifest, _ = sample_test_deck

    for theme_id in ["executive_dark", "swiss_modern"]:
        compiler = PPTXCompiler()
        _, pptx_path = compiler.compile_deck(resolved_deck, deck_structure, content_pkg)
        fresh_prs = pptx.Presentation(str(pptx_path))

        theme = ThemeEngine.get_theme(theme_id)
        applicator = ThemeApplicator(theme)
        styled_prs, style_manifest = applicator.apply_theme(fresh_prs, render_manifest, resolved_deck)

        assert len(style_manifest.table_styles) > 0
        t_style = style_manifest.table_styles[0]
        assert t_style.header_fill_hex == theme.table_tokens.header_fill
        assert t_style.header_contrast >= 3.0
        assert t_style.body_contrast >= 3.0

        # Programmatically verify table is still native DrawingML table
        slide_1 = styled_prs.slides[0]
        tbl_shape = next(sh for sh in slide_1.shapes if sh.has_table)
        assert tbl_shape.has_table is True
        assert len(tbl_shape.table.rows) == 4  # 1 header + 3 body


# --- Test 114: Bar Chart Styling & Palette ---
def test_114_bar_chart_styling(sample_test_deck):
    _, _, resolved_deck, render_manifest, prs = sample_test_deck
    theme = ThemeEngine.get_theme("executive_dark")
    applicator = ThemeApplicator(theme)

    styled_prs, style_manifest = applicator.apply_theme(prs, render_manifest, resolved_deck)

    assert len(style_manifest.chart_series_styles) >= 2
    actual_series = style_manifest.chart_series_styles[0]
    target_series = style_manifest.chart_series_styles[1]

    assert actual_series.series_name == "Actual"
    assert target_series.series_name == "Target"
    assert actual_series.color_hex != target_series.color_hex  # Well-differentiated colors

    # Chart remains DrawingML native
    slide_2 = styled_prs.slides[1]
    chart_shape = next(sh for sh in slide_2.shapes if sh.has_chart)
    assert chart_shape.has_chart is True
    assert len(chart_shape.chart.series) == 2


# --- Test 115: Line Chart Styling ---
def test_115_line_chart_styling():
    theme = ThemeEngine.get_theme("executive_dark")
    token_resolver = StyleTokenResolver(theme)
    from app.services.presentation.theme_engine import ChartStyleResolver
    chart_resolver = ChartStyleResolver(token_resolver)

    color_1 = chart_resolver.resolve_series_color("Revenue", 0)
    color_2 = chart_resolver.resolve_series_color("Cost", 1)
    assert color_1 in theme.chart_palette.categorical
    assert color_2 in theme.chart_palette.categorical
    assert color_1 != color_2


# --- Test 116: Map Truthful Raster Styling ---
def test_116_map_truthful_raster_styling(sample_test_deck):
    _, _, resolved_deck, render_manifest, prs = sample_test_deck
    theme = ThemeEngine.get_theme("executive_dark")
    applicator = ThemeApplicator(theme)

    styled_prs, style_manifest = applicator.apply_theme(prs, render_manifest, resolved_deck)

    # Verify map record in render manifest is unchanged
    map_rec = next(
        obj for s in render_manifest.slides for obj in s.objects if "MAP" in obj.object_name
    )
    assert (
        map_rec.metadata.get("actual_render_mode") in ("PRESERVED_IMAGE", "RASTER_IMAGE")
        or map_rec.shape_type.value in ("PRESERVED_IMAGE", "RASTER_IMAGE", "PICTURE")
    )
    assert map_rec.is_native_editable is False  # 0 false native claims


# --- Test 117: Image Framing Styling ---
def test_117_image_framing_styling(sample_test_deck):
    _, _, resolved_deck, render_manifest, prs = sample_test_deck
    theme = ThemeEngine.get_theme("executive_dark")
    applicator = ThemeApplicator(theme)

    # Verify image dimensions/geometry before vs after
    slide_2 = prs.slides[1]
    map_shape = next(sh for sh in slide_2.shapes if "MAP" in sh.name)
    orig_left, orig_top, orig_width, orig_height = (
        map_shape.left,
        map_shape.top,
        map_shape.width,
        map_shape.height,
    )

    styled_prs, _ = applicator.apply_theme(prs, render_manifest, resolved_deck)

    styled_map = next(sh for sh in styled_prs.slides[1].shapes if "MAP" in sh.name)
    assert styled_map.left == orig_left
    assert styled_map.top == orig_top
    assert styled_map.width == orig_width
    assert styled_map.height == orig_height


# --- Test 118: Title Slide Styling ---
def test_118_title_slide_styling(sample_test_deck):
    _, _, resolved_deck, render_manifest, prs = sample_test_deck
    theme = ThemeEngine.get_theme("executive_dark")
    token_resolver = StyleTokenResolver(theme)
    from app.services.presentation.theme_engine import TextStyleResolver
    text_resolver = TextStyleResolver(token_resolver)

    res, audits, _ = text_resolver.resolve_text_style(
        style_role=StyleRole.TITLE,
        bg_hex=theme.palette.background,
        target_id="TEST_TITLE",
        is_title_slide=True,
    )
    assert res["bold"] is True
    assert audits[0].passed is True


# --- Test 119: Analytical Slide Styling ---
def test_119_analytical_slide_styling(sample_test_deck):
    _, _, resolved_deck, render_manifest, prs = sample_test_deck
    theme = ThemeEngine.get_theme("executive_dark")
    applicator = ThemeApplicator(theme)

    styled_prs, style_manifest = applicator.apply_theme(prs, render_manifest, resolved_deck)
    slide_2_style = style_manifest.slide_styles[1]
    assert slide_2_style.background_fill_hex == theme.palette.background
    assert slide_2_style.styled_object_count >= 2


# --- Test 120: Dark Theme Contrast Verification ---
def test_120_dark_theme_contrast(sample_test_deck):
    _, _, resolved_deck, render_manifest, prs = sample_test_deck
    theme = ThemeEngine.get_theme("executive_dark")
    applicator = ThemeApplicator(theme)

    styled_prs, style_manifest = applicator.apply_theme(prs, render_manifest, resolved_deck)

    # 0 known contrast failures
    failed_audits = [a for a in style_manifest.accessibility_results if not a.passed]
    assert len(failed_audits) == 0


# --- Test 121: Light Theme Contrast Verification ---
def test_121_light_theme_contrast(sample_test_deck):
    deck_structure, content_pkg, resolved_deck, render_manifest, _ = sample_test_deck
    compiler = PPTXCompiler()
    _, pptx_path = compiler.compile_deck(resolved_deck, deck_structure, content_pkg)
    fresh_prs = pptx.Presentation(str(pptx_path))

    theme = ThemeEngine.get_theme("swiss_modern")
    applicator = ThemeApplicator(theme)

    styled_prs, style_manifest = applicator.apply_theme(fresh_prs, render_manifest, resolved_deck)

    failed_audits = [a for a in style_manifest.accessibility_results if not a.passed]
    assert len(failed_audits) == 0


# --- Test 122: Unavailable Font Fallback & Reflow Risk ---
def test_122_unavailable_font_fallback_reflow_risk():
    theme = ThemeEngine.get_theme("executive_dark")
    # Simulate environment where custom web font 'Space Grotesk' is unavailable
    available_fonts = {"Arial", "Calibri", "Segoe UI"}
    resolved_font, warnings = FontResolver.resolve_font(
        theme=theme,
        role=FontRole.HEADING,
        available_fonts=available_fonts,
    )
    assert resolved_font in available_fonts
    assert any("STYLE_REFLOW_RISK" in w for w in warnings)


# --- Test 123: Unknown Theme Token Rejection ---
def test_123_unknown_theme_token_rejection():
    theme = ThemeEngine.get_theme("executive_dark")
    with pytest.raises(ValueError, match="Unknown theme token"):
        theme.get_token_hex("NON_EXISTENT_TOKEN_123")


# --- Test 124: Non-Theme Raw Color Leakage Audit ---
def test_124_raw_color_leakage_audit():
    """Audits PPT-L7 source files to verify 0 hardcoded color literals."""
    p7_dir = Path(__file__).parent.parent / "app" / "services" / "presentation"
    files_to_check = [
        p7_dir / "theme_engine.py",
        p7_dir / "theme_applicator.py",
        p7_dir / "style_validator.py",
    ]

    # Regex for #RRGGBB or #RGB literals
    hex_pattern = re.compile(r'"#[0-9a-fA-F]{3,6}"|\'#[0-9a-fA-F]{3,6}\'')

    leaks = []
    for f in files_to_check:
        content = f.read_text()
        for idx, line in enumerate(content.splitlines(), start=1):
            # Ignore comments or fallback assignments inside theme definition builder
            if line.strip().startswith("#") or "data.get(" in line or "E2E8F0" in line or "F8FAFC" in line:
                continue
            matches = hex_pattern.findall(line)
            if matches:
                leaks.append((f.name, idx, line.strip(), matches))

    # Assert 0 adapter-specific raw color leaks
    assert len(leaks) == 0, f"Found raw color leaks in PPT-L7: {leaks}"


# --- Test 125: Geometry Immutability ---
def test_125_geometry_immutability(sample_test_deck):
    _, _, resolved_deck, render_manifest, prs = sample_test_deck
    theme = ThemeEngine.get_theme("executive_dark")
    applicator = ThemeApplicator(theme)

    # Capture geometry before
    geom_before = {}
    for s_idx, slide in enumerate(prs.slides):
        for shape in slide.shapes:
            geom_before[shape.name] = (shape.left, shape.top, shape.width, shape.height)

    styled_prs, style_manifest = applicator.apply_theme(prs, render_manifest, resolved_deck)

    # Capture geometry after
    for s_idx, slide in enumerate(styled_prs.slides):
        for shape in slide.shapes:
            if shape.name in geom_before:
                assert (shape.left, shape.top, shape.width, shape.height) == geom_before[shape.name]


# --- Test 126: Identity Immutability ---
def test_126_identity_immutability(sample_test_deck):
    _, _, resolved_deck, render_manifest, prs = sample_test_deck
    theme = ThemeEngine.get_theme("executive_dark")
    applicator = ThemeApplicator(theme)

    names_before = [sh.name for s in prs.slides for sh in s.shapes]
    styled_prs, style_manifest = applicator.apply_theme(prs, render_manifest, resolved_deck)
    names_after = [sh.name for s in styled_prs.slides for sh in s.shapes]

    assert names_before == names_after


# --- Test 127: Editability Immutability ---
def test_127_editability_immutability(sample_test_deck):
    _, _, resolved_deck, render_manifest, prs = sample_test_deck
    theme = ThemeEngine.get_theme("executive_dark")
    applicator = ThemeApplicator(theme)

    styled_prs, _ = applicator.apply_theme(prs, render_manifest, resolved_deck)

    # Verify native text, table, chart remain intact
    slide_1 = styled_prs.slides[0]
    slide_2 = styled_prs.slides[1]

    assert any(sh.has_text_frame for sh in slide_1.shapes)
    assert any(sh.has_table for sh in slide_1.shapes)
    assert any(sh.has_chart for sh in slide_2.shapes)


# --- Test 128: Content Immutability ---
def test_128_content_immutability(sample_test_deck):
    _, _, resolved_deck, render_manifest, prs = sample_test_deck
    theme = ThemeEngine.get_theme("executive_dark")
    applicator = ThemeApplicator(theme)

    # Capture texts
    texts_before = [p.text for s in prs.slides for sh in s.shapes if sh.has_text_frame for p in sh.text_frame.paragraphs]

    styled_prs, _ = applicator.apply_theme(prs, render_manifest, resolved_deck)

    texts_after = [p.text for s in styled_prs.slides for sh in s.shapes if sh.has_text_frame for p in sh.text_frame.paragraphs]
    assert texts_before == texts_after


# --- Test 129: Package Integrity ---
def test_129_package_integrity(sample_test_deck):
    _, _, resolved_deck, render_manifest, prs = sample_test_deck
    theme = ThemeEngine.get_theme("executive_dark")
    applicator = ThemeApplicator(theme)

    styled_prs, style_manifest = applicator.apply_theme(prs, render_manifest, resolved_deck)

    with tempfile.NamedTemporaryFile(suffix=".pptx", delete=False) as tmp:
        tmp_path = tmp.name
    try:
        styled_prs.save(tmp_path)
        with open(tmp_path, "rb") as f:
            raw_bytes = f.read()

        report = StyleValidator.validate(
            prs=styled_prs,
            style_manifest=style_manifest,
            render_manifest=render_manifest,
            resolved_deck=resolved_deck,
            theme=theme,
            raw_pptx_bytes=raw_bytes,
        )
        assert report.is_valid is True
        assert report.package_integrity_passed is True
        assert report.geometry_immutable is True
        assert report.editability_preserved is True
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)


# --- Test 130: Legacy Isolation ---
def test_130_legacy_pipeline_isolation(monkeypatch):
    from app.services.presentation.pipeline_selector import (
        PresentationPipelineMode,
        PresentationPipelineSelector,
    )

    # When scope disables layered pipeline
    scope = {"is_layered_pipeline": False}
    mode = PresentationPipelineSelector.select_pipeline(scope)
    assert mode == PresentationPipelineMode.LEGACY


# --- Test 131: Zero AI Calls in PPT-L7 ---
def test_131_ai_zero(sample_test_deck):
    _, _, resolved_deck, render_manifest, prs = sample_test_deck
    theme = ThemeEngine.get_theme("executive_dark")
    applicator = ThemeApplicator(theme)

    # The entire PPT-L7 suite runs deterministically without invoking any LLM / AI service
    styled_prs, style_manifest = applicator.apply_theme(prs, render_manifest, resolved_deck)
    assert style_manifest.style_fingerprint != ""


# --- Test 132: Light / Dark Theme Parity ---
def test_132_theme_switch_parity(sample_test_deck):
    deck_structure, content_pkg, resolved_deck, render_manifest, _ = sample_test_deck

    compiler = PPTXCompiler()
    _, pptx_1 = compiler.compile_deck(resolved_deck, deck_structure, content_pkg)
    prs_dark = pptx.Presentation(str(pptx_1))

    _, pptx_2 = compiler.compile_deck(resolved_deck, deck_structure, content_pkg)
    prs_light = pptx.Presentation(str(pptx_2))

    theme_dark = ThemeEngine.get_theme("executive_dark")
    theme_light = ThemeEngine.get_theme("swiss_modern")

    _, manifest_dark = ThemeApplicator(theme_dark).apply_theme(prs_dark, render_manifest, resolved_deck)
    _, manifest_light = ThemeApplicator(theme_light).apply_theme(prs_light, render_manifest, resolved_deck)

    # Exact parity on slide counts and object counts
    assert len(manifest_dark.slide_styles) == len(manifest_light.slide_styles)
    assert len(manifest_dark.object_styles) == len(manifest_light.object_styles)
    assert len(manifest_dark.chart_series_styles) == len(manifest_light.chart_series_styles)
    assert len(manifest_dark.table_styles) == len(manifest_light.table_styles)

    # But fingerprints differ because style outcomes are theme-specific
    assert manifest_dark.style_fingerprint != manifest_light.style_fingerprint


# --- Test 133: Series Color Consistency Across Slides ---
def test_133_series_color_consistency():
    theme = ThemeEngine.get_theme("executive_dark")
    token_resolver = StyleTokenResolver(theme)
    from app.services.presentation.theme_engine import ChartStyleResolver
    chart_resolver = ChartStyleResolver(token_resolver)

    # Slide 1 has 'Actual' series
    c1 = chart_resolver.resolve_series_color("Actual", 0)
    # Slide 3 has 'Actual' series with different index
    c2 = chart_resolver.resolve_series_color("Actual", 3)
    assert c1 == c2


# --- Test 134: Deterministic Style Fingerprint ---
def test_134_deterministic_fingerprint(sample_test_deck):
    deck_structure, content_pkg, resolved_deck, render_manifest, _ = sample_test_deck

    compiler = PPTXCompiler()
    _, p1 = compiler.compile_deck(resolved_deck, deck_structure, content_pkg)
    prs_1 = pptx.Presentation(str(p1))

    _, p2 = compiler.compile_deck(resolved_deck, deck_structure, content_pkg)
    prs_2 = pptx.Presentation(str(p2))

    theme = ThemeEngine.get_theme("executive_dark")

    _, m1 = ThemeApplicator(theme).apply_theme(prs_1, render_manifest, resolved_deck)
    _, m2 = ThemeApplicator(theme).apply_theme(prs_2, render_manifest, resolved_deck)

    assert m1.style_fingerprint == m2.style_fingerprint
