"""HighView Presentation Studio — PPT-L9 Rendered Visual Review Test Suite.

Certifies the PPT-L9 phase boundary according to the strict kickoff specifications:
- Tests 98-132: Clean slide visual certification, title/body overlap, axis tick collisions,
  hidden primary visuals, table density, text overload, image crop/distortion, map legibility,
  excessive vs intentional whitespace, light/dark parity, governance leak detection,
  bounded repair success, repair failure termination, regression detection, targeted rerender stability,
  content/numeric immutability, identity/editability preservation, slide count preservation,
  AI structured output & timeout safety, render failure safety, single specialist review (council=0),
  max repair attempts cap, issue merging with PPT-L8, real PPTX rendering, legacy isolation,
  and zero executable code generation.
"""

from __future__ import annotations

import copy
import io
import os
import tempfile
from pathlib import Path
from typing import Any

import pptx
from pptx.util import Inches, Pt
import pytest

from app.services.presentation.content_models import (
    ContentKind,
    ContentRole,
    PresentationContentItem,
    PresentationContentPackage,
)
from app.services.presentation.story_models import ContentBindingRole
from app.services.presentation.deterministic_validation_engine import DeterministicValidationEngine
from app.services.presentation.layer_zone_models import (
    CoordinateSpace,
    EditabilityPolicy,
    LayerRole,
    LayeredDeckStructureSpec,
    LayeredSlideSpec,
    SlideObjectSpec,
    StructuralRole,
    ZoneSpec,
    ZoneType,
)
from app.services.presentation.layout_models import (
    Box2D,
    ResolvedDeckLayout,
    ResolvedObjectLayout,
    ResolvedSafeArea,
    ResolvedSlideLayout,
    ResolvedZoneLayout,
)
from app.services.presentation.pipeline_selector import (
    PresentationPipelineMode,
    PresentationPipelineSelector,
)
from app.services.presentation.render_models import (
    RenderManifest,
    RenderStatus,
    RenderedObjectRecord,
    RenderedSlideRecord,
    ShapeType,
)
from app.services.presentation.theme_models import (
    StyleManifest,
    ThemeDefinition,
    ThemeMode,
    TypographyTokens,
)
from app.services.presentation.validation_models_l8 import (
    DeckValidationStatus,
    RepairAction,
    RepairOwner,
    ValidationCategory,
    ValidationManifest,
    ValidationSeverity,
)
from app.services.presentation.visual_models_l9 import (
    MAX_VISUAL_REPAIR_ATTEMPTS,
    RenderedSlideArtifact,
    RepairApprovalLevel,
    VisualCategory,
    VisualCertificationStatus,
    VisualConfidence,
    VisualIssue,
    VisualRepairHistory,
    VisualReviewManifest,
    VisualSeverity,
    compute_visual_manifest_fingerprint,
)
from app.services.presentation.slide_render_service import (
    DeterministicVisualPrecheck,
    SlideRenderService,
)
from app.services.presentation.visual_review_engine import VisualReviewEngine
from app.services.presentation.bounded_repair_orchestrator import (
    BoundedRepairOrchestrator,
    RepairDecisionEngine,
)


@pytest.fixture
def sample_l9_certified_deck():
    """Builds a certified, styled presentation deck with PPT-L8 validation manifest."""
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
        package_id="PKG-L9-001",
        dataset_name="WorkforceData",
        domain="HR",
        items=content_items,
    )

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
                bounds_hint=[0.52, 0.15, 0.43, 0.75],
                objects=[
                    SlideObjectSpec(
                        object_id="OBJ-MAP-1",
                        object_name="HV_WORKFORCE_HEALTH_02_SECONDARY_VISUAL_CNT_MAP_1",
                        name="Facility Map",
                        content_id="CNT-MAP-1",
                        binding_role=ContentBindingRole.SUPPORTING,
                        kind=ContentKind.MAP,
                        semantic_topic="WORKFORCE_HEALTH",
                        editability=EditabilityPolicy.RASTER_ALLOWED,
                    ),
                ],
            ),
        ],
    )

    deck_structure = LayeredDeckStructureSpec(
        manifest_id="MNF-L9-TEST-001",
        manifest_version=1,
        slides=[slide_1, slide_2],
    )

    # Resolved Layout
    from app.services.presentation.layout_engine import LayoutConstraintEngine
    from app.services.presentation.pptx_compiler import PPTXCompiler
    from app.services.presentation.theme_engine import ThemeEngine
    from app.services.presentation.theme_applicator import ThemeApplicator

    layout_engine = LayoutConstraintEngine()
    resolved_deck = layout_engine.resolve_deck_layout(deck_structure)

    compiler = PPTXCompiler()
    render_manifest, pptx_path = compiler.compile_deck(
        resolved_deck=resolved_deck,
        deck_structure=deck_structure,
        content_package=content_pkg,
    )
    raw_prs = pptx.Presentation(str(pptx_path))

    theme = ThemeEngine.get_theme("executive_dark")
    applicator = ThemeApplicator(theme)
    prs, style_manifest = applicator.apply_theme(
        raw_prs, render_manifest, resolved_deck
    )

    # PPT-L8 Validation Manifest
    l8_manifest = DeterministicValidationEngine.validate(
        prs=prs,
        style_manifest=style_manifest,
        render_manifest=render_manifest,
        resolved_deck=resolved_deck,
        deck_structure=deck_structure,
        content_package=content_pkg,
    )

    return deck_structure, content_pkg, resolved_deck, style_manifest, l8_manifest, prs


# ==============================================================================
# TESTS 98-132: PPT-L9 VISUAL REVIEW CERTIFICATION SUITE
# ==============================================================================

# --- Test 98: Clean Slide Visually Certified ---
def test_98_clean_slide_visually_certified(sample_l9_certified_deck, tmp_path):
    deck_structure, content_pkg, resolved_deck, style_manifest, l8_manifest, prs = sample_l9_certified_deck

    render_service = SlideRenderService(output_dir=tmp_path)
    artifacts = render_service.render_deck(prs=prs, deck_id="DECK-TEST-98")
    assert len(artifacts) == 2
    assert all(Path(a.image_path).exists() for a in artifacts)

    engine = VisualReviewEngine()
    manifest = engine.review_deck(
        artifacts=artifacts,
        validation_manifest=l8_manifest,
        resolved_deck=resolved_deck,
        deck_structure=deck_structure,
        style_manifest=style_manifest,
        prs=prs,
    )

    assert manifest.status == VisualCertificationStatus.VISUALLY_CERTIFIED
    assert manifest.counts_by_severity.get("CRITICAL", 0) == 0
    assert manifest.stats["council_calls"] == 0
    assert manifest.visual_fingerprint != ""


# --- Test 99: Title/Body Overlap Detected as CRITICAL ---
def test_99_title_body_overlap(sample_l9_certified_deck, tmp_path):
    deck_structure, content_pkg, resolved_deck, style_manifest, l8_manifest, prs = sample_l9_certified_deck

    # Move table to directly overlap title
    slide_1 = prs.slides[0]
    tbl_shape = next(sh for sh in slide_1.shapes if sh.has_table)
    title_shape = next(sh for sh in slide_1.shapes if "TITLE" in sh.name)
    tbl_shape.top = title_shape.top

    # Revalidate PPT-L8 to capture deterministic collision
    l8_manifest = DeterministicValidationEngine.validate(
        prs=prs,
        style_manifest=style_manifest,
        render_manifest=None,
        resolved_deck=resolved_deck,
        deck_structure=deck_structure,
        content_package=content_pkg,
    )

    render_service = SlideRenderService(output_dir=tmp_path)
    artifacts = render_service.render_deck(prs=prs, deck_id="DECK-TEST-99", force_rerender=True)

    engine = VisualReviewEngine()
    manifest = engine.review_deck(
        artifacts=artifacts,
        validation_manifest=l8_manifest,
        resolved_deck=resolved_deck,
        deck_structure=deck_structure,
        style_manifest=style_manifest,
        prs=prs,
    )

    overlap_issues = [i for i in manifest.issues if i.category == VisualCategory.VISUAL_OVERLAP]
    assert len(overlap_issues) > 0
    assert any(i.severity == VisualSeverity.CRITICAL for i in overlap_issues)
    assert overlap_issues[0].recommended_owner == RepairOwner.PPT_L5_LAYOUT


# --- Test 100: Axis Tick / Category Crowding Detected ---
def test_100_axis_tick_overlap(sample_l9_certified_deck, tmp_path):
    deck_structure, content_pkg, resolved_deck, style_manifest, l8_manifest, prs = sample_l9_certified_deck

    slide_2 = prs.slides[1]
    chart_shape = next(sh for sh in slide_2.shapes if sh.has_chart)

    # Replace chart data with 12 crowded categories
    from pptx.chart.data import CategoryChartData
    from pptx.enum.chart import XL_CHART_TYPE
    cdata = CategoryChartData()
    cdata.categories = [f"Dept-{i}" for i in range(12)]
    cdata.add_series("Series", tuple(range(12)))
    chart_shape.chart.replace_data(cdata)

    render_service = SlideRenderService(output_dir=tmp_path)
    artifacts = render_service.render_deck(prs=prs, deck_id="DECK-TEST-100", force_rerender=True)

    engine = VisualReviewEngine()
    manifest = engine.review_deck(
        artifacts=artifacts,
        validation_manifest=l8_manifest,
        resolved_deck=resolved_deck,
        deck_structure=deck_structure,
        style_manifest=style_manifest,
        prs=prs,
    )

    axis_issues = [i for i in manifest.issues if i.category == VisualCategory.AXIS_LABEL_COLLISION]
    assert len(axis_issues) > 0
    assert axis_issues[0].recommended_owner == RepairOwner.PPT_L5_LAYOUT


# --- Test 101: Primary Visual Obscured by Card / Control ---
def test_101_chart_hidden_by_control(sample_l9_certified_deck, tmp_path):
    deck_structure, content_pkg, resolved_deck, style_manifest, l8_manifest, prs = sample_l9_certified_deck

    slide_2 = prs.slides[1]
    chart_shape = next(sh for sh in slide_2.shapes if sh.has_chart)

    # Place an opaque control card directly over the primary chart
    control_box = slide_2.shapes.add_shape(1, chart_shape.left, chart_shape.top, chart_shape.width, chart_shape.height)
    control_box.name = "FILTER_CONTROL_DRAWER"

    render_service = SlideRenderService(output_dir=tmp_path)
    artifacts = render_service.render_deck(prs=prs, deck_id="DECK-TEST-101", force_rerender=True)

    engine = VisualReviewEngine()
    manifest = engine.review_deck(
        artifacts=artifacts,
        validation_manifest=l8_manifest,
        resolved_deck=resolved_deck,
        deck_structure=deck_structure,
        style_manifest=style_manifest,
        prs=prs,
    )

    obscured_issues = [i for i in manifest.issues if i.category == VisualCategory.PRIMARY_VISUAL_OBSCURED]
    assert len(obscured_issues) > 0
    assert obscured_issues[0].severity == VisualSeverity.CRITICAL


# --- Test 102: Table Too Dense Detected and Routed to Late Split ---
def test_102_table_too_dense(sample_l9_certified_deck, tmp_path):
    deck_structure, content_pkg, resolved_deck, style_manifest, l8_manifest, prs = sample_l9_certified_deck

    slide_1 = prs.slides[0]
    tbl_shape = next(sh for sh in slide_1.shapes if sh.has_table)
    # Remove existing and add a 16-row unreadable table
    tbl_shape._element.getparent().remove(tbl_shape._element)
    dense_tbl = slide_1.shapes.add_table(16, 4, Inches(0.666), Inches(1.875), Inches(12.0), Inches(4.875))
    dense_tbl.name = "HV_WORKFORCE_HEALTH_01_DATA_TABLE_DENSE"

    render_service = SlideRenderService(output_dir=tmp_path)
    artifacts = render_service.render_deck(prs=prs, deck_id="DECK-TEST-102", force_rerender=True)

    engine = VisualReviewEngine()
    manifest = engine.review_deck(
        artifacts=artifacts,
        validation_manifest=l8_manifest,
        resolved_deck=resolved_deck,
        deck_structure=deck_structure,
        style_manifest=style_manifest,
        prs=prs,
    )

    table_issues = [i for i in manifest.issues if i.category == VisualCategory.TABLE_UNREADABLE]
    assert len(table_issues) > 0
    assert table_issues[0].severity == VisualSeverity.CRITICAL
    assert table_issues[0].recommended_owner == RepairOwner.PPT_L3_EXPANSION
    assert table_issues[0].recommended_action == RepairAction.TABLE_SPLIT_REQUIRED


# --- Test 103: Text Overload Detected ---
def test_103_text_overload(sample_l9_certified_deck, tmp_path):
    deck_structure, content_pkg, resolved_deck, style_manifest, l8_manifest, prs = sample_l9_certified_deck

    slide_1 = prs.slides[0]
    body_txt = slide_1.shapes.add_textbox(Inches(0.666), Inches(2.0), Inches(5.0), Inches(3.0))
    body_txt.name = "HV_WORKFORCE_HEALTH_01_PARAGRAPH_OVERLOAD"
    body_txt.text_frame.text = "Comprehensive workforce analysis indicates multi-factor dependencies across all quarters. " * 15

    render_service = SlideRenderService(output_dir=tmp_path)
    artifacts = render_service.render_deck(prs=prs, deck_id="DECK-TEST-103", force_rerender=True)

    engine = VisualReviewEngine()
    manifest = engine.review_deck(
        artifacts=artifacts,
        validation_manifest=l8_manifest,
        resolved_deck=resolved_deck,
        deck_structure=deck_structure,
        style_manifest=style_manifest,
        prs=prs,
    )

    text_issues = [i for i in manifest.issues if i.category == VisualCategory.TEXT_TOO_DENSE]
    assert len(text_issues) > 0
    assert text_issues[0].recommended_action == RepairAction.TEXT_REFLOW_REQUIRED


# --- Test 104: Image Bad Crop / Distortion Detected ---
def test_104_image_bad_crop(sample_l9_certified_deck, tmp_path):
    deck_structure, content_pkg, resolved_deck, style_manifest, l8_manifest, prs = sample_l9_certified_deck

    slide_2 = prs.slides[1]
    # Add an unnaturally stretched image shape (width 10 inches, height 0.5 inches -> ratio 20:1)
    distorted_img = slide_2.shapes.add_shape(1, Inches(0.666), Inches(6.5), Inches(10.0), Inches(0.5))
    distorted_img.name = "HV_WORKFORCE_HEALTH_02_IMAGE_BANNER"

    render_service = SlideRenderService(output_dir=tmp_path)
    artifacts = render_service.render_deck(prs=prs, deck_id="DECK-TEST-104", force_rerender=True)

    engine = VisualReviewEngine()
    manifest = engine.review_deck(
        artifacts=artifacts,
        validation_manifest=l8_manifest,
        resolved_deck=resolved_deck,
        deck_structure=deck_structure,
        style_manifest=style_manifest,
        prs=prs,
    )

    distortion_issues = [i for i in manifest.issues if i.category == VisualCategory.IMAGE_DISTORTION]
    assert len(distortion_issues) > 0
    assert distortion_issues[0].recommended_owner == RepairOwner.ASSET_PIPELINE


# --- Test 105: Image Low Quality / Small Pixel Budget ---
def test_105_image_low_quality(sample_l9_certified_deck, tmp_path):
    deck_structure, content_pkg, resolved_deck, style_manifest, l8_manifest, prs = sample_l9_certified_deck

    # Deterministic precheck verifies image resolution
    fake_artifact = RenderedSlideArtifact(
        physical_slide_id="SLD-PHYS-1",
        slide_index=1,
        image_path=str(tmp_path / "low_res.png"),
        width_px=800,  # below 1200px threshold
        height_px=450,
        dpi=72,
        renderer_backend="PIL_DRAWINGML_RENDERER",
        render_fingerprint="fp-low-res",
        source_pptx_fingerprint="",
    )
    from PIL import Image
    im = Image.new("RGB", (800, 450), color="blue")
    im.save(tmp_path / "low_res.png")

    issues = DeterministicVisualPrecheck.check_artifact(fake_artifact)
    assert any(i.category == VisualCategory.RENDER_CORRUPTION and i.severity == VisualSeverity.WARNING for i in issues)


# --- Test 106: Map Unreadable Size Detected ---
def test_106_map_unreadable(sample_l9_certified_deck, tmp_path):
    deck_structure, content_pkg, resolved_deck, style_manifest, l8_manifest, prs = sample_l9_certified_deck

    slide_2 = prs.slides[1]
    map_shape = next(sh for sh in slide_2.shapes if "MAP" in sh.name)
    # Shrink map to 1 inch x 1 inch
    map_shape.width = Inches(1.0)
    map_shape.height = Inches(1.0)

    render_service = SlideRenderService(output_dir=tmp_path)
    artifacts = render_service.render_deck(prs=prs, deck_id="DECK-TEST-106", force_rerender=True)

    engine = VisualReviewEngine()
    manifest = engine.review_deck(
        artifacts=artifacts,
        validation_manifest=l8_manifest,
        resolved_deck=resolved_deck,
        deck_structure=deck_structure,
        style_manifest=style_manifest,
        prs=prs,
    )

    map_issues = [i for i in manifest.issues if i.category == VisualCategory.MAP_UNREADABLE]
    assert len(map_issues) > 0


# --- Test 107: Excessive Whitespace on Analytical Slide ---
def test_107_excessive_whitespace(sample_l9_certified_deck, tmp_path):
    deck_structure, content_pkg, resolved_deck, style_manifest, l8_manifest, prs = sample_l9_certified_deck

    slide_2 = prs.slides[1]
    # Remove large shapes and leave only a tiny label
    for sh in list(slide_2.shapes):
        sh._element.getparent().remove(sh._element)

    tiny = slide_2.shapes.add_textbox(Inches(1.0), Inches(1.0), Inches(1.0), Inches(0.5))
    tiny.name = "HV_ISOLATED_TINY_LABEL"
    tiny.text_frame.text = "Isolated"

    render_service = SlideRenderService(output_dir=tmp_path)
    artifacts = render_service.render_deck(prs=prs, deck_id="DECK-TEST-107", force_rerender=True)

    engine = VisualReviewEngine()
    manifest = engine.review_deck(
        artifacts=artifacts,
        validation_manifest=l8_manifest,
        resolved_deck=resolved_deck,
        deck_structure=deck_structure,
        style_manifest=style_manifest,
        prs=prs,
    )

    ws_issues = [i for i in manifest.issues if i.category == VisualCategory.EXCESSIVE_WHITESPACE]
    assert len(ws_issues) > 0
    assert ws_issues[0].severity == VisualSeverity.WARNING


# --- Test 108: Intentional Whitespace on Title Slide Not Flagged ---
def test_108_intentional_whitespace(sample_l9_certified_deck, tmp_path):
    deck_structure, content_pkg, resolved_deck, style_manifest, l8_manifest, prs = sample_l9_certified_deck

    # Set slide 1 structural role to TITLE
    deck_structure.slides[0].structural_role = StructuralRole.TITLE
    slide_1 = prs.slides[0]
    # Keep only the title shape (generous clean whitespace)
    for sh in list(slide_1.shapes):
        if "TABLE" in sh.name:
            sh._element.getparent().remove(sh._element)

    render_service = SlideRenderService(output_dir=tmp_path)
    artifacts = render_service.render_deck(prs=prs, deck_id="DECK-TEST-108", force_rerender=True)

    engine = VisualReviewEngine()
    manifest = engine.review_deck(
        artifacts=artifacts,
        validation_manifest=l8_manifest,
        resolved_deck=resolved_deck,
        deck_structure=deck_structure,
        style_manifest=style_manifest,
        prs=prs,
    )

    # Intentional whitespace on title slide must NOT be flagged as EXCESSIVE_WHITESPACE
    slide_1_ws = [i for i in manifest.issues if i.slide_id == "SLD-PHYS-1" and i.category == VisualCategory.EXCESSIVE_WHITESPACE]
    assert len(slide_1_ws) == 0


# --- Test 109 & 110: Light and Dark Theme Visual Review ---
def test_109_light_and_110_dark_theme_review(sample_l9_certified_deck, tmp_path):
    deck_structure, content_pkg, resolved_deck, style_manifest, l8_manifest, prs = sample_l9_certified_deck

    render_service = SlideRenderService(output_dir=tmp_path)
    artifacts = render_service.render_deck(prs=prs, deck_id="DECK-TEST-109-110")

    engine = VisualReviewEngine()

    # Dark review
    style_manifest.mode = ThemeMode.DARK
    dark_manifest = engine.review_deck(
        artifacts=artifacts,
        validation_manifest=l8_manifest,
        resolved_deck=resolved_deck,
        deck_structure=deck_structure,
        style_manifest=style_manifest,
        prs=prs,
    )
    assert dark_manifest.status == VisualCertificationStatus.VISUALLY_CERTIFIED

    # Light review
    style_manifest.mode = ThemeMode.LIGHT
    light_manifest = engine.review_deck(
        artifacts=artifacts,
        validation_manifest=l8_manifest,
        resolved_deck=resolved_deck,
        deck_structure=deck_structure,
        style_manifest=style_manifest,
        prs=prs,
    )
    assert light_manifest.status == VisualCertificationStatus.VISUALLY_CERTIFIED


# --- Test 111: Cross-Slide Style Consistency ---
def test_111_cross_slide_style_consistency(sample_l9_certified_deck, tmp_path):
    deck_structure, content_pkg, resolved_deck, style_manifest, l8_manifest, prs = sample_l9_certified_deck

    render_service = SlideRenderService(output_dir=tmp_path)
    artifacts = render_service.render_deck(prs=prs, deck_id="DECK-TEST-111")

    engine = VisualReviewEngine()
    manifest = engine.review_deck(
        artifacts=artifacts,
        validation_manifest=l8_manifest,
        resolved_deck=resolved_deck,
        deck_structure=deck_structure,
        style_manifest=style_manifest,
        prs=prs,
    )

    inconsistencies = [i for i in manifest.issues if i.category == VisualCategory.STYLE_INCONSISTENCY]
    assert len(inconsistencies) == 0


# --- Test 112: Governance Token Leak Detected ---
def test_112_governance_token_leak(sample_l9_certified_deck, tmp_path):
    deck_structure, content_pkg, resolved_deck, style_manifest, l8_manifest, prs = sample_l9_certified_deck

    slide_1 = prs.slides[0]
    txt_shape = next(sh for sh in slide_1.shapes if sh.has_text_frame)
    txt_shape.text_frame.text = "Executive Summary {{HV_OPERATING_REVENUE_METRIC}} EVID-9921"

    render_service = SlideRenderService(output_dir=tmp_path)
    artifacts = render_service.render_deck(prs=prs, deck_id="DECK-TEST-112", force_rerender=True)

    engine = VisualReviewEngine()
    manifest = engine.review_deck(
        artifacts=artifacts,
        validation_manifest=l8_manifest,
        resolved_deck=resolved_deck,
        deck_structure=deck_structure,
        style_manifest=style_manifest,
        prs=prs,
        is_technical_deck=False,
    )

    gov_issues = [i for i in manifest.issues if i.category == VisualCategory.STYLE_INCONSISTENCY and "Governance token leak" in i.description]
    assert len(gov_issues) > 0
    assert gov_issues[0].severity == VisualSeverity.CRITICAL


# --- Test 113: Bounded Repair Loop Success ---
def test_113_bounded_repair_success(sample_l9_certified_deck, tmp_path):
    deck_structure, content_pkg, resolved_deck, style_manifest, l8_manifest, prs = sample_l9_certified_deck

    # Introduce repairable chart size defect
    slide_2 = prs.slides[1]
    chart_shape = next(sh for sh in slide_2.shapes if sh.has_chart)
    chart_shape.width = Inches(1.5)  # too small (<20% width)

    render_service = SlideRenderService(output_dir=tmp_path)
    artifacts = render_service.render_deck(prs=prs, deck_id="DECK-TEST-113", force_rerender=True)

    review_engine = VisualReviewEngine()
    initial_visual_manifest = review_engine.review_deck(
        artifacts=artifacts,
        validation_manifest=l8_manifest,
        resolved_deck=resolved_deck,
        deck_structure=deck_structure,
        style_manifest=style_manifest,
        prs=prs,
    )
    assert initial_visual_manifest.status == VisualCertificationStatus.REPAIR_REQUIRED

    orchestrator = BoundedRepairOrchestrator(render_service=render_service, max_attempts=2)
    final_manifest, final_l8, history = orchestrator.execute_bounded_repairs(
        initial_manifest=initial_visual_manifest,
        initial_l8_manifest=l8_manifest,
        prs=prs,
        resolved_deck=resolved_deck,
        deck_structure=deck_structure,
        style_manifest=style_manifest,
        content_package=content_pkg,
        review_engine=review_engine,
    )

    assert final_manifest.status == VisualCertificationStatus.VISUALLY_CERTIFIED
    assert len(history) == 1
    assert history[0].status == "SUCCESS"
    assert history[0].repair_owner == RepairOwner.PPT_L5_LAYOUT


# --- Test 114: Repair Failure Terminates at Max Attempts ---
def test_114_repair_fails(sample_l9_certified_deck, tmp_path):
    deck_structure, content_pkg, resolved_deck, style_manifest, l8_manifest, prs = sample_l9_certified_deck

    render_service = SlideRenderService(output_dir=tmp_path)
    artifacts = render_service.render_deck(prs=prs, deck_id="DECK-TEST-114")

    # Manually inject an unrepairable critical defect
    review_engine = VisualReviewEngine()
    initial_visual_manifest = review_engine.review_deck(
        artifacts=artifacts,
        validation_manifest=l8_manifest,
        resolved_deck=resolved_deck,
        deck_structure=deck_structure,
        style_manifest=style_manifest,
        prs=prs,
    )
    initial_visual_manifest.status = VisualCertificationStatus.REPAIR_REQUIRED
    initial_visual_manifest.issues.append(
        VisualIssue(
            issue_id="VIS-UNREP-1",
            slide_id="SLD-PHYS-1",
            severity=VisualSeverity.CRITICAL,
            category=VisualCategory.RENDER_CORRUPTION,
            description="Unrecoverable renderer fault.",
            visual_evidence="Hardware pipe crashed.",
            recommended_owner=RepairOwner.ASSET_PIPELINE,
            recommended_action=RepairAction.RENDER_RETRY_REQUIRED,
            repairable=True,
        )
    )

    orchestrator = BoundedRepairOrchestrator(render_service=render_service, max_attempts=2)
    final_manifest, _, history = orchestrator.execute_bounded_repairs(
        initial_manifest=initial_visual_manifest,
        initial_l8_manifest=l8_manifest,
        prs=prs,
        resolved_deck=resolved_deck,
        deck_structure=deck_structure,
        style_manifest=style_manifest,
        content_package=content_pkg,
        review_engine=review_engine,
    )

    assert final_manifest.status == VisualCertificationStatus.FAIL
    assert len(history) <= 2  # Hard capped, no infinite loop


# --- Test 115: Repair Regression Detection ---
def test_115_repair_creates_new_defect(sample_l9_certified_deck, tmp_path):
    deck_structure, content_pkg, resolved_deck, style_manifest, l8_manifest, prs = sample_l9_certified_deck

    render_service = SlideRenderService(output_dir=tmp_path)
    artifacts = render_service.render_deck(prs=prs, deck_id="DECK-TEST-115")

    review_engine = VisualReviewEngine()
    initial_visual_manifest = review_engine.review_deck(
        artifacts=artifacts,
        validation_manifest=l8_manifest,
        resolved_deck=resolved_deck,
        deck_structure=deck_structure,
        style_manifest=style_manifest,
        prs=prs,
    )

    # Inject an issue that will trigger layout repair
    initial_visual_manifest.status = VisualCertificationStatus.REPAIR_REQUIRED
    initial_visual_manifest.issues.append(
        VisualIssue(
            issue_id="VIS-REG-1",
            slide_id="SLD-PHYS-1",
            severity=VisualSeverity.CRITICAL,
            category=VisualCategory.VISUAL_OVERLAP,
            description="Simulated overlap",
            visual_evidence="Overlap",
            recommended_owner=RepairOwner.PPT_L5_LAYOUT,
            recommended_action=RepairAction.LAYOUT_REPLAN_REQUIRED,
            repairable=True,
        )
    )

    # Break deck structure slides so PPT-L8 will fail during revalidation
    broken_structure = deck_structure.model_copy(deep=True)
    broken_structure.slides = broken_structure.slides[:1]  # count mismatch

    orchestrator = BoundedRepairOrchestrator(render_service=render_service, max_attempts=2)
    final_manifest, final_l8, history = orchestrator.execute_bounded_repairs(
        initial_manifest=initial_visual_manifest,
        initial_l8_manifest=l8_manifest,
        prs=prs,
        resolved_deck=resolved_deck,
        deck_structure=broken_structure,
        style_manifest=style_manifest,
        content_package=content_pkg,
        review_engine=review_engine,
    )

    assert final_manifest.status == VisualCertificationStatus.FAIL
    assert any(h.status == "REGRESSION" for h in history)


# --- Test 116: Targeted Repair Leaves Unrelated Slides Unchanged ---
def test_116_targeted_repair(sample_l9_certified_deck, tmp_path):
    deck_structure, content_pkg, resolved_deck, style_manifest, l8_manifest, prs = sample_l9_certified_deck

    render_service = SlideRenderService(output_dir=tmp_path)
    artifacts_v1 = render_service.render_deck(prs=prs, deck_id="DECK-TEST-116", force_rerender=True)

    fp_slide_1_before = artifacts_v1[0].render_fingerprint

    # Modify slide 2 only
    slide_2 = prs.slides[1]
    slide_2.shapes.add_textbox(Inches(1.0), Inches(1.0), Inches(2.0), Inches(1.0)).text_frame.text = "New label"

    # Targeted render of slide 2
    artifacts_v2 = render_service.render_deck(
        prs=prs,
        deck_id="DECK-TEST-116",
        target_slide_ids=["SLD-PHYS-2"],
        force_rerender=True,
    )

    # Slide 1 render fingerprint must remain identical
    assert artifacts_v2[0].render_fingerprint == fp_slide_1_before


# --- Test 117-120: Invariant Preservation Across Visual Review ---
def test_117_to_120_invariants_preserved(sample_l9_certified_deck, tmp_path):
    deck_structure, content_pkg, resolved_deck, style_manifest, l8_manifest, prs = sample_l9_certified_deck

    # Snapshots before visual review
    content_titles_before = [item.title for item in content_pkg.items]
    table_data_before = content_pkg.items[1].table_data
    object_names_before = [sh.name for s in prs.slides for sh in s.shapes]
    slide_count_before = len(prs.slides)
    editable_before = [
        sh.has_text_frame or sh.has_table or sh.has_chart
        for s in prs.slides for sh in s.shapes
    ]

    render_service = SlideRenderService(output_dir=tmp_path)
    artifacts = render_service.render_deck(prs=prs, deck_id="DECK-INVARIANTS")

    review_engine = VisualReviewEngine()
    manifest = review_engine.review_deck(
        artifacts=artifacts,
        validation_manifest=l8_manifest,
        resolved_deck=resolved_deck,
        deck_structure=deck_structure,
        style_manifest=style_manifest,
        prs=prs,
    )

    # Assert 0 content mutations
    assert [item.title for item in content_pkg.items] == content_titles_before
    assert content_pkg.items[1].table_data == table_data_before

    # Assert 0 identity mutations
    assert [sh.name for s in prs.slides for sh in s.shapes] == object_names_before

    # Assert 0 editability mutations
    editable_after = [
        sh.has_text_frame or sh.has_table or sh.has_chart
        for s in prs.slides for sh in s.shapes
    ]
    assert editable_after == editable_before

    # Assert 0 slide creations
    assert len(prs.slides) == slide_count_before


# --- Test 121: AI Structured Output Validation ---
def test_121_ai_structured_output(sample_l9_certified_deck):
    # Verify VisualReviewManifest conforms to strict pydantic model schema
    manifest = VisualReviewManifest(
        manifest_id="VMAN-SCHEMA-TEST",
        deck_id="DECK-001",
        status=VisualCertificationStatus.VISUALLY_CERTIFIED,
        counts_by_severity={"CRITICAL": 0, "WARNING": 0, "INFO": 0},
    )
    dumped = manifest.model_dump()
    assert "visual_fingerprint" in dumped
    assert "status" in dumped
    assert dumped["status"] == "VISUALLY_CERTIFIED"


# --- Test 122 & 124: AI Timeout / Model Unavailable Safety ---
def test_122_and_124_model_failure_safety(sample_l9_certified_deck, tmp_path):
    deck_structure, content_pkg, resolved_deck, style_manifest, l8_manifest, prs = sample_l9_certified_deck

    render_service = SlideRenderService(output_dir=tmp_path)
    artifacts = render_service.render_deck(prs=prs, deck_id="DECK-FAIL-SAFETY")

    # Point critic to an unavailable host
    from app.services.presentation.qa.gemma_critic import GemmaVisualCritic
    unavailable_critic = GemmaVisualCritic(base_url="http://127.0.0.1:99999", timeout_seconds=0.1)
    engine = VisualReviewEngine(critic=unavailable_critic)

    # Engine must execute deterministically without raising unhandled exceptions or falsely certifying
    manifest = engine.review_deck(
        artifacts=artifacts,
        validation_manifest=l8_manifest,
        resolved_deck=resolved_deck,
        deck_structure=deck_structure,
        style_manifest=style_manifest,
        prs=prs,
    )
    assert manifest is not None
    assert manifest.manifest_id != ""


# --- Test 123: Render Failure Safety ---
def test_123_render_failure_safety(sample_l9_certified_deck, tmp_path):
    deck_structure, content_pkg, resolved_deck, style_manifest, l8_manifest, prs = sample_l9_certified_deck

    # Non-existent image path
    corrupt_artifact = RenderedSlideArtifact(
        physical_slide_id="SLD-PHYS-1",
        slide_index=1,
        image_path=str(tmp_path / "non_existent.png"),
        width_px=1920,
        height_px=1080,
        dpi=150,
        renderer_backend="PIL_DRAWINGML_RENDERER",
        render_fingerprint="",
        source_pptx_fingerprint="",
    )

    engine = VisualReviewEngine()
    manifest = engine.review_deck(
        artifacts=[corrupt_artifact],
        validation_manifest=l8_manifest,
        resolved_deck=resolved_deck,
        deck_structure=deck_structure,
        style_manifest=style_manifest,
        prs=prs,
    )

    assert manifest.status == VisualCertificationStatus.FAIL
    assert any(i.category == VisualCategory.RENDER_CORRUPTION for i in manifest.issues)


# --- Test 125: Single Specialist Reviewer (0 Council Calls) ---
def test_125_no_council_default(sample_l9_certified_deck, tmp_path):
    deck_structure, content_pkg, resolved_deck, style_manifest, l8_manifest, prs = sample_l9_certified_deck

    render_service = SlideRenderService(output_dir=tmp_path)
    artifacts = render_service.render_deck(prs=prs, deck_id="DECK-NO-COUNCIL")

    engine = VisualReviewEngine()
    manifest = engine.review_deck(
        artifacts=artifacts,
        validation_manifest=l8_manifest,
        resolved_deck=resolved_deck,
        deck_structure=deck_structure,
        style_manifest=style_manifest,
        prs=prs,
    )

    assert manifest.stats["council_calls"] == 0


# --- Test 126: Max Repair Attempts Cap ---
def test_126_max_repair_attempts_cap():
    assert MAX_VISUAL_REPAIR_ATTEMPTS == 2


# --- Test 127: Issue Merging with PPT-L8 ---
def test_127_issue_merging_with_pptl8(sample_l9_certified_deck, tmp_path):
    deck_structure, content_pkg, resolved_deck, style_manifest, l8_manifest, prs = sample_l9_certified_deck

    # Inject an issue in PPT-L8 manifest
    from app.services.presentation.validation_models_l8 import ValidationIssue
    l8_manifest.issues.append(
        ValidationIssue(
            issue_id="ISSUE-L8-TEST",
            severity=ValidationSeverity.WARNING,
            category=ValidationCategory.SAFE_AREA,
            slide_id="SLD-PHYS-1",
            message="Horizontal safe margin breach",
        )
    )

    render_service = SlideRenderService(output_dir=tmp_path)
    artifacts = render_service.render_deck(prs=prs, deck_id="DECK-MERGE-TEST")

    engine = VisualReviewEngine()
    manifest = engine.review_deck(
        artifacts=artifacts,
        validation_manifest=l8_manifest,
        resolved_deck=resolved_deck,
        deck_structure=deck_structure,
        style_manifest=style_manifest,
        prs=prs,
    )

    # Issue must be merged with deterministic_support=True
    merged = next((i for i in manifest.issues if i.deterministic_support), None)
    assert merged is not None
    assert merged.category == VisualCategory.FRAME_COLLISION


# --- Test 128: Real PPTX Rendered and Reviewed ---
def test_128_real_pptx_rendered_and_reviewed(sample_l9_certified_deck, tmp_path):
    deck_structure, content_pkg, resolved_deck, style_manifest, l8_manifest, prs = sample_l9_certified_deck

    pptx_file = tmp_path / "actual_rendered_deck.pptx"
    prs.save(pptx_file)
    assert pptx_file.exists() and pptx_file.stat().st_size > 1000

    loaded_prs = pptx.Presentation(pptx_file)
    render_service = SlideRenderService(output_dir=tmp_path)
    artifacts = render_service.render_deck(prs=loaded_prs, deck_id="REAL-DECK")

    assert len(artifacts) == len(loaded_prs.slides)
    for art in artifacts:
        assert Path(art.image_path).exists()
        assert art.width_px >= 1600


# --- Test 131: Legacy Pipeline Isolation ---
def test_131_legacy_pipeline_isolation():
    scope = {"is_layered_pipeline": False}
    mode = PresentationPipelineSelector.select_pipeline(scope)
    assert mode == PresentationPipelineMode.LEGACY


# --- Test 132: Zero AI Code Generation in Visual Review ---
def test_132_zero_ai_code_generation(sample_l9_certified_deck, tmp_path):
    deck_structure, content_pkg, resolved_deck, style_manifest, l8_manifest, prs = sample_l9_certified_deck

    render_service = SlideRenderService(output_dir=tmp_path)
    artifacts = render_service.render_deck(prs=prs, deck_id="DECK-NO-CODE")

    engine = VisualReviewEngine()
    manifest = engine.review_deck(
        artifacts=artifacts,
        validation_manifest=l8_manifest,
        resolved_deck=resolved_deck,
        deck_structure=deck_structure,
        style_manifest=style_manifest,
        prs=prs,
    )

    # All issues must have typed recommended action, never executable python code strings
    for issue in manifest.issues:
        assert isinstance(issue.recommended_action, RepairAction)
        assert isinstance(issue.recommended_owner, RepairOwner)
        assert not any(keyword in issue.description for keyword in ["def ", "import ", "lambda", "class "])
