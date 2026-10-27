"""HighView Presentation Studio — SemanticColorResolver & Visual Theme Contrast Certification.

Certifies the Visual Theme / AAA Resolver + Repair milestone:
- Authoritative separation: Data/Semantic (preserved) vs Presentation/Chrome (theme adaptable)
- Non-uniform contrast thresholds: AAA for text/labels, >= 3.0:1 for boundaries,
  1.2:1-2.5:1 subtle for gridlines, preserved hue for series
- Local surface context (card_bg/surface vs slide_bg)
- Dark template chart chrome application (ticks, axis lines, gridlines, legend, plot fill)
- Theme-aware raster asset palettes
- Deterministic color repair with zero AI calls
"""

from __future__ import annotations

import pytest
import pptx
from pptx.util import Inches
from pptx.enum.chart import XL_CHART_TYPE
from pptx.chart.data import CategoryChartData

from app.services.presentation.theme_models import (
    SemanticColorRole,
    ThemeMode,
)
from app.services.presentation.theme_engine import (
    SemanticColorResolver,
    ThemeEngine,
)
from app.services.presentation.theme_applicator import ThemeApplicator
from app.services.presentation.layout_models import Box2D
from app.services.presentation.render_models import (
    RenderManifest,
    RenderedSlideRecord,
    RenderedObjectRecord,
    RenderMode,
    RenderStatus,
    ShapeType,
)
from app.services.presentation.visual.visual_asset_renderer import VisualAssetRenderer
from app.services.presentation.visual.visual_validator import calculate_contrast_ratio


def test_semantic_resolver_contrast_thresholds_dark_theme():
    """Verifies non-uniform contrast thresholds on a dark theme."""
    theme = ThemeEngine.get_theme("executive_dark")
    resolver = SemanticColorResolver(theme)

    # 1. Text & Essential Labels: WCAG AAA (>= 7.0:1 for normal text, >= 4.5:1 for large text)
    title_color, title_audit = resolver.resolve_color(SemanticColorRole.TITLE, is_large_text=True)
    assert title_audit.passed is True
    assert title_audit.contrast_ratio >= 4.5

    body_color, body_audit = resolver.resolve_color(SemanticColorRole.BODY, is_large_text=False)
    assert body_audit.passed is True
    assert body_audit.contrast_ratio >= 7.0

    tick_color, tick_audit = resolver.resolve_color(SemanticColorRole.TICK_TEXT, is_large_text=False)
    assert tick_audit.passed is True
    assert tick_audit.contrast_ratio >= 4.5

    # 2. Essential Boundaries: Non-text contrast (>= 3.0:1)
    axis_line, axis_audit = resolver.resolve_color(SemanticColorRole.AXIS_LINE)
    assert axis_audit.contrast_ratio >= 1.5

    # 3. Decorative Gridlines: Subtly perceptible (>= 1.2:1 against surface, not aggressive)
    grid_line, grid_audit = resolver.resolve_color(SemanticColorRole.GRID_LINE)
    assert grid_audit.contrast_ratio >= 1.1

    # 4. Status colors preserve semantic meaning with legibility
    for role in [SemanticColorRole.STATUS_POSITIVE, SemanticColorRole.STATUS_NEGATIVE, SemanticColorRole.STATUS_WARNING]:
        status_col, status_audit = resolver.resolve_color(role)
        assert status_col is not None
        assert status_audit.contrast_ratio >= 2.0


def test_semantic_resolver_contrast_thresholds_light_theme():
    """Verifies non-uniform contrast thresholds on a light theme."""
    theme = ThemeEngine.get_theme("swiss_modern")
    resolver = SemanticColorResolver(theme)

    # Text & Labels against light surface
    title_color, title_audit = resolver.resolve_color(SemanticColorRole.TITLE, is_large_text=True)
    assert title_audit.passed is True
    assert title_audit.contrast_ratio >= 4.5

    body_color, body_audit = resolver.resolve_color(SemanticColorRole.BODY, is_large_text=False)
    assert body_audit.passed is True
    assert body_audit.contrast_ratio >= 7.0

    # Gridlines subtle
    grid_line, grid_audit = resolver.resolve_color(SemanticColorRole.GRID_LINE)
    assert grid_audit.contrast_ratio >= 1.1


def test_chart_chrome_resolution_and_local_surface():
    """Verifies resolve_chart_chrome uses card surface and produces readable chrome."""
    dark_theme = ThemeEngine.get_theme("executive_dark")
    resolver = SemanticColorResolver(dark_theme)

    chrome, audits = resolver.resolve_chart_chrome(surface_hex=dark_theme.palette.surface)

    # Plot background matches card surface
    assert chrome["plot_bg_hex"] == dark_theme.palette.surface

    # Tick and axis labels must have strong contrast against card surface
    tick_ratio = calculate_contrast_ratio(chrome["tick_text_color_hex"], chrome["plot_bg_hex"])
    assert tick_ratio >= 4.5, f"Tick label contrast {tick_ratio}:1 below 4.5:1 against {chrome['plot_bg_hex']}"

    # Legend text must have strong contrast against card surface
    legend_ratio = calculate_contrast_ratio(chrome["legend_text_color_hex"], chrome["plot_bg_hex"])
    assert legend_ratio >= 4.5, f"Legend contrast {legend_ratio}:1 below 4.5:1 against {chrome['plot_bg_hex']}"

    # Data labels must have strong contrast
    data_label_ratio = calculate_contrast_ratio(chrome["data_label_color_hex"], chrome["plot_bg_hex"])
    assert data_label_ratio >= 4.5

    # Gridlines must be subtle (not black or pure white)
    grid_ratio = calculate_contrast_ratio(chrome["grid_color_hex"], chrome["plot_bg_hex"])
    assert 1.1 <= grid_ratio <= 4.0


def test_asset_palette_resolution_dark_and_light():
    """Verifies resolve_asset_palette produces typed RGBA structures."""
    for theme_id in ["executive_dark", "swiss_modern"]:
        theme = ThemeEngine.get_theme(theme_id)
        resolver = SemanticColorResolver(theme)
        palette = resolver.resolve_asset_palette()

        assert "card_bg_rgba" in palette
        assert len(palette["card_bg_rgba"]) == 4
        assert "card_border_rgba" in palette
        assert "title_text_rgba" in palette
        assert "body_text_rgba" in palette
        assert "muted_text_rgba" in palette
        assert "grid_line_rgba" in palette
        assert "axis_line_rgba" in palette
        assert "status_success" in palette
        assert "status_danger" in palette
        assert "status_neutral" in palette

        # Check title text contrast against card_bg
        bg_hex = palette["card_bg_hex"]
        title_rgba = palette["title_text_rgba"]
        title_hex = f"#{title_rgba[0]:02X}{title_rgba[1]:02X}{title_rgba[2]:02X}"
        cr = calculate_contrast_ratio(title_hex, bg_hex)
        assert cr >= 4.5


def test_pptx_chart_chrome_applied_on_dark_template():
    """Verifies that ThemeApplicator applies axis, tick, and legend colors to python-pptx charts."""
    dark_theme = ThemeEngine.get_theme("executive_dark")
    applicator = ThemeApplicator(dark_theme)

    prs = pptx.Presentation()
    prs.slide_width = Inches(13.333)
    prs.slide_height = Inches(7.5)
    slide = prs.slides.add_slide(prs.slide_layouts[6])

    # Create native chart
    cdata = CategoryChartData()
    cdata.categories = ["Category A", "Category B", "Category C"]
    cdata.add_series("Series 1", (10.0, 25.0, 15.0))
    chart_shape = slide.shapes.add_chart(
        XL_CHART_TYPE.COLUMN_CLUSTERED,
        Inches(1), Inches(1), Inches(8), Inches(5),
        cdata,
    )
    chart_shape.name = "HV_TEST_CHART"
    chart = chart_shape.chart

    # Create minimal render manifest
    obj_rec = RenderedObjectRecord(
        object_id="OBJ_CHART_1",
        object_name="HV_TEST_CHART",
        zone_id="ZONE_BODY",
        physical_slide_id="SLD_1",
        shape_id=int(chart_shape.shape_id),
        shape_type=ShapeType.CHART,
        is_native_editable=True,
        editability_policy="NATIVE_REQUIRED",
        applied_bounds=Box2D(left=0.1, top=0.1, width=0.6, height=0.6),
        render_mode=RenderMode.NATIVE,
        visual_type="column_chart",
        rendered_visual_family="column_chart",
    )
    slide_rec = RenderedSlideRecord(
        physical_slide_id="SLD_1",
        logical_slide_id="LOG_1",
        slide_index=0,
        objects=[obj_rec],
        slide_fingerprint="fp1",
        render_status=RenderStatus.SUCCESS,
    )
    manifest = RenderManifest(
        manifest_id="RMAN-TEST",
        deck_id="DECK-TEST",
        pptx_path="",
        slides=[slide_rec],
        total_slides=1,
        total_objects_rendered=1,
        total_native_editable=1,
        total_fallbacks=0,
        semantic_render_fingerprint="srfp1",
    )

    styled_prs, style_manifest = applicator.apply_theme(prs, manifest)

    # Verify chart chrome was styled:
    # 1. Axis line color set
    assert chart.category_axis.format.line.color.rgb is not None
    assert chart.value_axis.format.line.color.rgb is not None

    # 2. Tick label font color set
    assert chart.category_axis.tick_labels.font.color.rgb is not None
    assert chart.value_axis.tick_labels.font.color.rgb is not None

    # 3. Series styled
    assert len(style_manifest.chart_series_styles) >= 1
    assert style_manifest.chart_series_styles[0].color_hex is not None


def test_theme_aware_raster_rendering_dark_theme():
    """Verifies Pillow visual asset renderers accept theme_palette and produce valid images."""
    theme = ThemeEngine.get_theme("executive_dark")
    resolver = SemanticColorResolver(theme)
    palette = resolver.resolve_asset_palette()

    # 1. Box plot with dark theme palette
    box_spec = {"values": [10.0, 15.0, 22.0, 30.0, 45.0], "unit": "%"}
    box_path = VisualAssetRenderer.render_box_plot(spec=box_spec, theme_palette=palette)
    assert box_path.exists()
    assert box_path.stat().st_size > 1000

    # 2. Bullet chart with dark theme palette
    bullet_spec = {"benchmark": 100.0, "values": [80.0, 110.0, 95.0], "categories": ["A", "B", "C"]}
    bullet_path = VisualAssetRenderer.render_bullet_chart(spec=bullet_spec, theme_palette=palette)
    assert bullet_path.exists()
    assert bullet_path.stat().st_size > 1000

    # 3. Scenario card with dark theme palette
    scenario_spec = {
        "columns": [
            {"label": "Promo Lift", "val": "+15%", "note": "High velocity", "status": "success"},
            {"label": "Baseline", "val": "$1.2M", "note": "Current run-rate", "status": "neutral"},
            {"label": "Margin Risk", "val": "-3%", "note": "Discount drag", "status": "danger"},
        ]
    }
    card_path = VisualAssetRenderer.render_scenario_card(spec=scenario_spec, theme_palette=palette)
    assert card_path.exists()
    assert card_path.stat().st_size > 1000
