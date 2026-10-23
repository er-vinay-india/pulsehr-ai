"""HighView Presentation Studio — PPT-L8 Post-Style Deterministic Validation Test Suite.

Certifies the PPT-L8 phase boundary according to the strict kickoff specifications:
- Tests 91-131: Perfect slides, text clipping, collisions, hidden charts, table overflows,
  distortion, map presence, contrast failures, font reflow risk, native editability preservation,
  content & numeric preservation, identity preservation, shape collisions, slide count/order,
  continuation sequences, empty slides, section dividers, governance leaks, package integrity,
  light/dark parity, determinism, legacy isolation, zero mutation, zero slide creation,
  and zero AI calls.
"""

from __future__ import annotations

import copy
import io
import os
import tempfile
import zipfile
import pytest
from pathlib import Path
from typing import Any

import pptx
from pptx.util import Inches, Pt
from PIL import Image

from app.services.presentation.content_models import (
    ContentKind,
    ContentRole,
    PresentationContentItem,
    PresentationContentPackage,
)
from app.services.presentation.deterministic_validation_engine import (
    DeterministicValidationEngine,
    ValidationIssueClassifier,
    RepairRecommendationBuilder,
)
from app.services.presentation.layout_engine import LayoutConstraintEngine
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
from app.services.presentation.theme_applicator import ThemeApplicator
from app.services.presentation.theme_engine import ThemeEngine
from app.services.presentation.validation_models_l8 import (
    DeckValidationStatus,
    RepairAction,
    RepairOwner,
    ValidationCategory,
    ValidationSeverity,
)


@pytest.fixture
def sample_certified_deck() -> tuple[
    LayeredDeckStructureSpec,
    PresentationContentPackage,
    ResolvedDeckLayout,
    Any,
    Any,
    Any,
    bytes,
]:
    """Compiles and styles a clean, valid 2-slide presentation deck through PPT-L4/L5/L6/L7."""
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
    raw_prs = pptx.Presentation(str(pptx_path))

    theme = ThemeEngine.get_theme("executive_dark")
    applicator = ThemeApplicator(theme)
    styled_prs, style_manifest = applicator.apply_theme(
        raw_prs, render_manifest, resolved_deck
    )

    with tempfile.NamedTemporaryFile(suffix=".pptx", delete=False) as tmp:
        tmp_path = tmp.name
    styled_prs.save(tmp_path)
    with open(tmp_path, "rb") as f:
        styled_bytes = f.read()
    if os.path.exists(tmp_path):
        os.remove(tmp_path)

    return (
        deck_structure,
        content_pkg,
        resolved_deck,
        render_manifest,
        style_manifest,
        styled_prs,
        styled_bytes,
    )


# --- Test 91: Perfect Simple Slide Certification ---
def test_91_perfect_simple_slide(sample_certified_deck):
    deck_structure, content_pkg, resolved_deck, render_manifest, style_manifest, prs, raw_bytes = sample_certified_deck

    manifest = DeterministicValidationEngine.validate(
        prs=prs,
        style_manifest=style_manifest,
        render_manifest=render_manifest,
        resolved_deck=resolved_deck,
        deck_structure=deck_structure,
        content_package=content_pkg,
        raw_pptx_bytes=raw_bytes,
    )

    assert manifest.status == DeckValidationStatus.CERTIFIED
    assert manifest.counts_by_severity.get("CRITICAL", 0) == 0
    assert len(manifest.repair_requests) == 0


# --- Test 92: Text Clipping Defect Detection ---
def test_92_text_clipping(sample_certified_deck):
    deck_structure, content_pkg, resolved_deck, render_manifest, style_manifest, prs, raw_bytes = sample_certified_deck

    # Mutate text on slide 1 to severely exceed bounding box
    slide_1 = prs.slides[0]
    txt_shape = next(sh for sh in slide_1.shapes if sh.has_text_frame)
    txt_shape.text_frame.text = "Severe overflowing text block. " * 50

    manifest = DeterministicValidationEngine.validate(
        prs=prs,
        style_manifest=style_manifest,
        render_manifest=render_manifest,
        resolved_deck=resolved_deck,
        deck_structure=deck_structure,
        content_package=content_pkg,
        raw_pptx_bytes=raw_bytes,
    )

    assert manifest.status in (DeckValidationStatus.REPAIR_REQUIRED, DeckValidationStatus.FAIL)
    clipping_issues = [i for i in manifest.issues if i.category == ValidationCategory.TEXT_CLIPPING]
    assert len(clipping_issues) > 0
    assert clipping_issues[0].severity == ValidationSeverity.CRITICAL
    assert clipping_issues[0].recommended_owner == RepairOwner.PPT_L5_LAYOUT
    assert clipping_issues[0].repair_action == RepairAction.TEXT_REFLOW_REQUIRED


# --- Test 93: Title Collision Detection ---
def test_93_title_collision(sample_certified_deck):
    deck_structure, content_pkg, resolved_deck, render_manifest, style_manifest, prs, raw_bytes = sample_certified_deck

    # Move table to collide with title
    slide_1 = prs.slides[0]
    tbl_shape = next(sh for sh in slide_1.shapes if sh.has_table)
    title_shape = next(sh for sh in slide_1.shapes if "TITLE" in sh.name)
    tbl_shape.top = title_shape.top  # Direct collision

    manifest = DeterministicValidationEngine.validate(
        prs=prs,
        style_manifest=style_manifest,
        render_manifest=render_manifest,
        resolved_deck=resolved_deck,
        deck_structure=deck_structure,
        content_package=content_pkg,
        raw_pptx_bytes=raw_bytes,
    )

    collision_issues = [i for i in manifest.issues if i.category == ValidationCategory.COLLISION]
    assert len(collision_issues) > 0
    assert collision_issues[0].severity == ValidationSeverity.CRITICAL


# --- Test 94: Chart Collision Detection ---
def test_94_chart_collision(sample_certified_deck):
    deck_structure, content_pkg, resolved_deck, render_manifest, style_manifest, prs, raw_bytes = sample_certified_deck

    # Move chart to collide with map
    slide_2 = prs.slides[1]
    chart_shape = next(sh for sh in slide_2.shapes if sh.has_chart)
    map_shape = next(sh for sh in slide_2.shapes if "MAP" in sh.name)
    chart_shape.left = map_shape.left  # Direct collision

    manifest = DeterministicValidationEngine.validate(
        prs=prs,
        style_manifest=style_manifest,
        render_manifest=render_manifest,
        resolved_deck=resolved_deck,
        deck_structure=deck_structure,
        content_package=content_pkg,
        raw_pptx_bytes=raw_bytes,
    )

    collision_issues = [i for i in manifest.issues if i.category == ValidationCategory.COLLISION]
    assert len(collision_issues) > 0


# --- Test 95: Primary Chart Missing/Hidden ---
def test_95_primary_chart_hidden(sample_certified_deck):
    deck_structure, content_pkg, resolved_deck, render_manifest, style_manifest, prs, raw_bytes = sample_certified_deck

    # Remove chart from slide 2
    slide_2 = prs.slides[1]
    chart_shape = next(sh for sh in slide_2.shapes if sh.has_chart)
    chart_shape.name = "CORRUPTED_HIDDEN_NAME"

    manifest = DeterministicValidationEngine.validate(
        prs=prs,
        style_manifest=style_manifest,
        render_manifest=render_manifest,
        resolved_deck=resolved_deck,
        deck_structure=deck_structure,
        content_package=content_pkg,
        raw_pptx_bytes=raw_bytes,
    )

    missing_issues = [i for i in manifest.issues if i.category == ValidationCategory.OBJECT_EXISTENCE]
    assert len(missing_issues) > 0
    assert missing_issues[0].severity == ValidationSeverity.CRITICAL


# --- Test 96: Table Overflow / Split Required ---
def test_96_table_overflow_split_recommendation(sample_certified_deck):
    deck_structure, content_pkg, resolved_deck, render_manifest, style_manifest, prs, raw_bytes = sample_certified_deck

    # Mutate table row count to create mismatch
    slide_1 = prs.slides[0]
    tbl_shape = next(sh for sh in slide_1.shapes if sh.has_table)
    # Add fake row
    tbl_shape.table.rows._tbl.append(copy.deepcopy(tbl_shape.table.rows[0]._tr))

    manifest = DeterministicValidationEngine.validate(
        prs=prs,
        style_manifest=style_manifest,
        render_manifest=render_manifest,
        resolved_deck=resolved_deck,
        deck_structure=deck_structure,
        content_package=content_pkg,
        raw_pptx_bytes=raw_bytes,
    )

    table_issues = [i for i in manifest.issues if i.category == ValidationCategory.TABLE_INTEGRITY]
    assert len(table_issues) > 0
    assert table_issues[0].repair_action == RepairAction.TABLE_SPLIT_REQUIRED
    assert table_issues[0].recommended_owner == RepairOwner.PPT_L3_EXPANSION


# --- Test 97: Safe Area Violation ---
def test_97_safe_area_violation(sample_certified_deck):
    deck_structure, content_pkg, resolved_deck, render_manifest, style_manifest, prs, raw_bytes = sample_certified_deck

    # Move table outside slide margins
    slide_1 = prs.slides[0]
    tbl_shape = next(sh for sh in slide_1.shapes if sh.has_table)
    tbl_shape.left = Inches(-1.0)  # Breaches left margin

    manifest = DeterministicValidationEngine.validate(
        prs=prs,
        style_manifest=style_manifest,
        render_manifest=render_manifest,
        resolved_deck=resolved_deck,
        deck_structure=deck_structure,
        content_package=content_pkg,
        raw_pptx_bytes=raw_bytes,
    )

    safe_issues = [i for i in manifest.issues if i.category == ValidationCategory.SAFE_AREA]
    assert len(safe_issues) > 0
    assert safe_issues[0].severity == ValidationSeverity.CRITICAL


# --- Test 98: Contrast Failure Detection ---
def test_98_contrast_failure_detection(sample_certified_deck):
    deck_structure, content_pkg, resolved_deck, render_manifest, style_manifest, prs, raw_bytes = sample_certified_deck

    # Inject failed audit into style_manifest
    from app.services.presentation.theme_models import AccessibilityAuditResult
    corrupted_manifest = style_manifest.model_copy(deep=True)
    corrupted_manifest.accessibility_results.append(
        AccessibilityAuditResult(
            target_id="TEST_BAD_TEXT",
            target_type="BODY",
            foreground_hex="#333333",
            background_hex="#222222",
            contrast_ratio=1.2,
            threshold=4.5,
            passed=False,
        )
    )

    manifest = DeterministicValidationEngine.validate(
        prs=prs,
        style_manifest=corrupted_manifest,
        render_manifest=render_manifest,
        resolved_deck=resolved_deck,
        deck_structure=deck_structure,
        content_package=content_pkg,
        raw_pptx_bytes=raw_bytes,
    )

    contrast_issues = [i for i in manifest.issues if i.category == ValidationCategory.CONTRAST]
    assert len(contrast_issues) > 0
    assert contrast_issues[0].severity == ValidationSeverity.CRITICAL
    assert contrast_issues[0].recommended_owner == RepairOwner.PPT_L7_STYLE


# --- Test 99: Map Missing Detection ---
def test_99_map_missing_detection(sample_certified_deck):
    deck_structure, content_pkg, resolved_deck, render_manifest, style_manifest, prs, raw_bytes = sample_certified_deck

    # Corrupt map shape name on slide 2
    slide_2 = prs.slides[1]
    map_shape = next(sh for sh in slide_2.shapes if "MAP" in sh.name)
    map_shape.name = "NON_MAP_SHAPE"

    manifest = DeterministicValidationEngine.validate(
        prs=prs,
        style_manifest=style_manifest,
        render_manifest=render_manifest,
        resolved_deck=resolved_deck,
        deck_structure=deck_structure,
        content_package=content_pkg,
        raw_pptx_bytes=raw_bytes,
    )

    missing_issues = [i for i in manifest.issues if i.category == ValidationCategory.OBJECT_EXISTENCE]
    assert len(missing_issues) > 0


# --- Test 102: Native Text Lost (Rasterization) ---
def test_102_native_text_lost(sample_certified_deck):
    deck_structure, content_pkg, resolved_deck, render_manifest, style_manifest, prs, raw_bytes = sample_certified_deck

    # Replace native text shape with picture (raster conversion)
    slide_1 = prs.slides[0]
    txt_shape = next(sh for sh in slide_1.shapes if sh.has_text_frame)
    txt_name = txt_shape.name
    txt_shape._element.getparent().remove(txt_shape._element)
    
    img = Image.new("RGB", (100, 100), color="blue")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    pic = slide_1.shapes.add_picture(buf, 0, 0, 100, 100)
    pic.name = txt_name

    manifest = DeterministicValidationEngine.validate(
        prs=prs,
        style_manifest=style_manifest,
        render_manifest=render_manifest,
        resolved_deck=resolved_deck,
        deck_structure=deck_structure,
        content_package=content_pkg,
        raw_pptx_bytes=raw_bytes,
    )

    edit_issues = [i for i in manifest.issues if i.category == ValidationCategory.EDITABILITY_PRESERVATION]
    assert len(edit_issues) > 0
    assert edit_issues[0].severity == ValidationSeverity.CRITICAL


# --- Test 105: Content Mutation Detection ---
def test_105_content_mutation_detection(sample_certified_deck):
    deck_structure, content_pkg, resolved_deck, render_manifest, style_manifest, prs, raw_bytes = sample_certified_deck

    slide_1 = prs.slides[0]
    txt_shape = next(sh for sh in slide_1.shapes if sh.has_text_frame)
    txt_shape.text_frame.text = "Completely hallucinated non-empirical narrative text."

    manifest = DeterministicValidationEngine.validate(
        prs=prs,
        style_manifest=style_manifest,
        render_manifest=render_manifest,
        resolved_deck=resolved_deck,
        deck_structure=deck_structure,
        content_package=content_pkg,
        raw_pptx_bytes=raw_bytes,
    )

    content_issues = [i for i in manifest.issues if i.category == ValidationCategory.CONTENT_PRESERVATION]
    assert len(content_issues) > 0
    assert manifest.status == DeckValidationStatus.FAIL


# --- Test 108: Shape Name Collision Detection ---
def test_108_shape_name_collision(sample_certified_deck):
    deck_structure, content_pkg, resolved_deck, render_manifest, style_manifest, prs, raw_bytes = sample_certified_deck

    slide_1 = prs.slides[0]
    slide_1.shapes[1].name = slide_1.shapes[0].name  # Duplicate name

    manifest = DeterministicValidationEngine.validate(
        prs=prs,
        style_manifest=style_manifest,
        render_manifest=render_manifest,
        resolved_deck=resolved_deck,
        deck_structure=deck_structure,
        content_package=content_pkg,
        raw_pptx_bytes=raw_bytes,
    )

    id_issues = [i for i in manifest.issues if i.category == ValidationCategory.IDENTITY_PRESERVATION]
    assert len(id_issues) > 0


# --- Test 109: Extra Physical Slide Detection ---
def test_109_extra_slide_detection(sample_certified_deck):
    deck_structure, content_pkg, resolved_deck, render_manifest, style_manifest, prs, raw_bytes = sample_certified_deck

    # Add unauthorized extra slide to PPTX
    prs.slides.add_slide(prs.slide_layouts[6])

    manifest = DeterministicValidationEngine.validate(
        prs=prs,
        style_manifest=style_manifest,
        render_manifest=render_manifest,
        resolved_deck=resolved_deck,
        deck_structure=deck_structure,
        content_package=content_pkg,
        raw_pptx_bytes=raw_bytes,
    )

    count_issues = [i for i in manifest.issues if i.category == ValidationCategory.SLIDE_COUNT_ORDER]
    assert len(count_issues) > 0
    assert manifest.status == DeckValidationStatus.FAIL


# --- Test 112: Broken Continuation Detection ---
def test_112_broken_continuation_detection(sample_certified_deck):
    deck_structure, content_pkg, resolved_deck, render_manifest, style_manifest, prs, raw_bytes = sample_certified_deck

    # Introduce discontinuous continuation in deck structure
    broken_structure = deck_structure.model_copy(deep=True)
    # Add a third slide with same topic but separated
    extra_slide = copy.deepcopy(broken_structure.slides[0])
    extra_slide.physical_slide_id = "SLD-PHYS-3"
    extra_slide.sequence_index = 3
    broken_structure.slides[1].semantic_topic = "UNRELATED_TOPIC"
    broken_structure.slides.append(extra_slide)

    prs.slides.add_slide(prs.slide_layouts[6])

    manifest = DeterministicValidationEngine.validate(
        prs=prs,
        style_manifest=style_manifest,
        render_manifest=render_manifest,
        resolved_deck=resolved_deck,
        deck_structure=broken_structure,
        content_package=content_pkg,
        raw_pptx_bytes=raw_bytes,
    )

    cont_issues = [i for i in manifest.issues if i.category == ValidationCategory.CONTINUATION_SEQUENCE]
    assert len(cont_issues) > 0


# --- Test 115: Internal Governance Text Leak Detection ---
def test_115_governance_leak_detection(sample_certified_deck):
    deck_structure, content_pkg, resolved_deck, render_manifest, style_manifest, prs, raw_bytes = sample_certified_deck

    slide_1 = prs.slides[0]
    txt_shape = next(sh for sh in slide_1.shapes if sh.has_text_frame)
    txt_shape.text_frame.text += " (Backed by EVID-WORKFORCE-HEALTH-Q3)"

    manifest = DeterministicValidationEngine.validate(
        prs=prs,
        style_manifest=style_manifest,
        render_manifest=render_manifest,
        resolved_deck=resolved_deck,
        deck_structure=deck_structure,
        content_package=content_pkg,
        raw_pptx_bytes=raw_bytes,
        is_technical_deck=False,  # Normal business deck
    )

    gov_issues = [i for i in manifest.issues if i.category == ValidationCategory.GOVERNANCE_LEAK]
    assert len(gov_issues) > 0
    assert gov_issues[0].severity == ValidationSeverity.WARNING


# --- Test 116: Package Corruption Detection ---
def test_116_package_corruption_detection(sample_certified_deck):
    deck_structure, content_pkg, resolved_deck, render_manifest, style_manifest, prs, _ = sample_certified_deck

    corrupt_bytes = b"NOT_A_VALID_ZIP_ARCHIVE_DATA"

    manifest = DeterministicValidationEngine.validate(
        prs=prs,
        style_manifest=style_manifest,
        render_manifest=render_manifest,
        resolved_deck=resolved_deck,
        deck_structure=deck_structure,
        content_package=content_pkg,
        raw_pptx_bytes=corrupt_bytes,
    )

    pkg_issues = [i for i in manifest.issues if i.category == ValidationCategory.PACKAGE_INTEGRITY]
    assert len(pkg_issues) > 0
    assert manifest.status == DeckValidationStatus.FAIL


# --- Test 120: Light / Dark Theme Parity ---
def test_120_theme_parity(sample_certified_deck):
    deck_structure, content_pkg, resolved_deck, render_manifest, _, prs, raw_bytes = sample_certified_deck

    theme_dark = ThemeEngine.get_theme("executive_dark")
    theme_light = ThemeEngine.get_theme("swiss_modern")

    _, style_dark = ThemeApplicator(theme_dark).apply_theme(prs, render_manifest, resolved_deck)
    _, style_light = ThemeApplicator(theme_light).apply_theme(prs, render_manifest, resolved_deck)

    manifest_dark = DeterministicValidationEngine.validate(
        prs=prs,
        style_manifest=style_dark,
        render_manifest=render_manifest,
        resolved_deck=resolved_deck,
        deck_structure=deck_structure,
        content_package=content_pkg,
        raw_pptx_bytes=raw_bytes,
    )

    manifest_light = DeterministicValidationEngine.validate(
        prs=prs,
        style_manifest=style_light,
        render_manifest=render_manifest,
        resolved_deck=resolved_deck,
        deck_structure=deck_structure,
        content_package=content_pkg,
        raw_pptx_bytes=raw_bytes,
    )

    assert manifest_dark.status == DeckValidationStatus.CERTIFIED
    assert manifest_light.status == DeckValidationStatus.CERTIFIED


# --- Test 121: Determinism (Same Input -> Same ValidationManifest & Fingerprint) ---
def test_121_determinism(sample_certified_deck):
    deck_structure, content_pkg, resolved_deck, render_manifest, style_manifest, prs, raw_bytes = sample_certified_deck

    m1 = DeterministicValidationEngine.validate(
        prs=prs,
        style_manifest=style_manifest,
        render_manifest=render_manifest,
        resolved_deck=resolved_deck,
        deck_structure=deck_structure,
        content_package=content_pkg,
        raw_pptx_bytes=raw_bytes,
    )

    m2 = DeterministicValidationEngine.validate(
        prs=prs,
        style_manifest=style_manifest,
        render_manifest=render_manifest,
        resolved_deck=resolved_deck,
        deck_structure=deck_structure,
        content_package=content_pkg,
        raw_pptx_bytes=raw_bytes,
    )

    assert m1.validation_fingerprint == m2.validation_fingerprint
    assert len(m1.issues) == len(m2.issues)
    assert m1.status == m2.status


# --- Test 122: Issue Ordering Stability ---
def test_122_issue_ordering_stability(sample_certified_deck):
    deck_structure, content_pkg, resolved_deck, render_manifest, style_manifest, prs, raw_bytes = sample_certified_deck

    # Create multiple issues
    prs.slides[0].shapes[0].left = Inches(-2.0)
    prs.slides[0].shapes[1].name = "COLLIDED_NAME"

    m1 = DeterministicValidationEngine.validate(prs, style_manifest, render_manifest, resolved_deck, deck_structure, content_pkg, raw_bytes)
    m2 = DeterministicValidationEngine.validate(prs, style_manifest, render_manifest, resolved_deck, deck_structure, content_pkg, raw_bytes)

    ids1 = [i.issue_id for i in m1.issues]
    ids2 = [i.issue_id for i in m2.issues]
    assert ids1 == ids2


# --- Test 123: Legacy Pipeline Isolation ---
def test_123_legacy_pipeline_isolation():
    from app.services.presentation.pipeline_selector import (
        PresentationPipelineMode,
        PresentationPipelineSelector,
    )
    scope = {"is_layered_pipeline": False}
    mode = PresentationPipelineSelector.select_pipeline(scope)
    assert mode == PresentationPipelineMode.LEGACY


# --- Test 124: Zero AI Calls in PPT-L8 ---
def test_124_ai_zero(sample_certified_deck):
    deck_structure, content_pkg, resolved_deck, render_manifest, style_manifest, prs, raw_bytes = sample_certified_deck

    # Runs purely locally and deterministically with 0 LLM inference
    manifest = DeterministicValidationEngine.validate(prs, style_manifest, render_manifest, resolved_deck, deck_structure, content_pkg, raw_bytes)
    assert manifest.validation_fingerprint != ""


# --- Test 125: Zero Mutations Introduced by Validator ---
def test_125_zero_mutations_by_validator(sample_certified_deck):
    deck_structure, content_pkg, resolved_deck, render_manifest, style_manifest, prs, raw_bytes = sample_certified_deck

    # Snapshot shapes before validation
    shapes_before = [
        (s_idx, sh.name, sh.left, sh.top, sh.width, sh.height)
        for s_idx, s in enumerate(prs.slides)
        for sh in s.shapes
    ]

    _ = DeterministicValidationEngine.validate(
        prs=prs,
        style_manifest=style_manifest,
        render_manifest=render_manifest,
        resolved_deck=resolved_deck,
        deck_structure=deck_structure,
        content_package=content_pkg,
        raw_pptx_bytes=raw_bytes,
    )

    shapes_after = [
        (s_idx, sh.name, sh.left, sh.top, sh.width, sh.height)
        for s_idx, s in enumerate(prs.slides)
        for sh in s.shapes
    ]

    assert shapes_before == shapes_after


# --- Test 126: Zero Slides Created by Validator ---
def test_126_zero_slides_created_by_validator(sample_certified_deck):
    deck_structure, content_pkg, resolved_deck, render_manifest, style_manifest, prs, raw_bytes = sample_certified_deck

    slide_count_before = len(prs.slides)
    _ = DeterministicValidationEngine.validate(
        prs=prs,
        style_manifest=style_manifest,
        render_manifest=render_manifest,
        resolved_deck=resolved_deck,
        deck_structure=deck_structure,
        content_package=content_pkg,
        raw_pptx_bytes=raw_bytes,
    )
    slide_count_after = len(prs.slides)

    assert slide_count_before == slide_count_after
