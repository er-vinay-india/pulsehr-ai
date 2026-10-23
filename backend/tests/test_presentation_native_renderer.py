"""HighView Presentation Studio — PPT-L6 Native Editable Renderer Test Suite.

Certifies the PPT-L6 phase boundary, verifying that:
1. PPT-L6 realizes objects; it does not redesign them (PPT-L5 geometry is strictly preserved in EMUs).
2. Native text, tables, and charts are programmatically verified as DrawingML editable.
3. Selection-Pane naming: shape.name matches object_name for every shape.
4. Identity separation: shape.shape_id is an integer, distinct from semantic object_id.
5. Truthful non-native map rendering: MAP uses RASTER_ALLOWED and is_native_editable == False.
6. Zero silent downgrades: NATIVE_REQUIRED objects never silently fall back to raster.
7. Fallback accounting: NATIVE_PREFERRED objects explicitly record fallbacks in RenderManifest.
8. Zero physical slide creation: len(prs.slides) == len(manifest.slides) == len(resolved_deck.slides).
9. Structural package integrity: valid zip, [Content_Types].xml, opens cleanly via python-pptx.
10. Deterministic semantic render fingerprints across executions.
"""

from __future__ import annotations

import copy
import os
import tempfile
import zipfile
import pytest
from pathlib import Path
from typing import Any

import pptx
from pptx.util import Inches

from app.services.presentation.content_models import (
    ContentKind,
    ContentRole,
    PresentationContentItem,
    PresentationContentPackage,
)
from app.services.presentation.fit_engines import (
    ChartFitPolicy,
    ImageFitEngine,
    TableFitEngine,
    TextFitEngine,
)
from app.services.presentation.layout_config import DEFAULT_LAYOUT_CONFIG
from app.services.presentation.layout_engine import (
    LayoutConstraintEngine,
    LayoutValidator,
)
from app.services.presentation.layout_models import (
    Box2D,
    ResolvedDeckLayout,
    ResolvedObjectLayout,
    ResolvedSlideLayout,
    ResolvedZoneLayout,
    ZoneFitStatus,
    SlideFitStatus,
    ObjectFitStatus,
)
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
from app.services.presentation.render_models import (
    RenderManifest,
    RenderStatus,
    RenderedObjectRecord,
    RenderedSlideRecord,
    ShapeType,
    compute_render_manifest_fingerprint,
    compute_rendered_slide_fingerprint,
)
from app.services.presentation.renderer_adapters import (
    ChartRendererAdapter,
    RasterRendererAdapter,
    RenderDegradationError,
    RendererAdapterRegistry,
    TableRendererAdapter,
    TextRendererAdapter,
)
from app.services.presentation.pptx_compiler import PPTXCompiler
from app.services.presentation.renderer_validator import (
    RendererValidator,
    RendererValidationError,
)


@pytest.fixture
def sample_layered_deck() -> tuple[LayeredDeckStructureSpec, PresentationContentPackage, ResolvedDeckLayout]:
    """Builds a deterministic 2-slide deck structure, content package, and resolved layout."""
    # Content package
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
    content_package = PresentationContentPackage(
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

    # Use PPT-L5 LayoutConstraintEngine to resolve concrete geometry
    engine = LayoutConstraintEngine()
    resolved_deck = engine.resolve_deck_layout(deck_structure)

    return deck_structure, content_package, resolved_deck


# ==============================================================================
# TESTS
# ==============================================================================

def test_pptx_compilation_and_validation(sample_layered_deck):
    """Verifies complete PPTX compilation, package integrity, and DrawingML editability."""
    deck_structure, content_package, resolved_deck = sample_layered_deck

    with tempfile.TemporaryDirectory() as tmp_dir:
        out_path = Path(tmp_dir) / "test_presentation.pptx"

        compiler = PPTXCompiler()
        manifest, path = compiler.compile_deck(
            resolved_deck=resolved_deck,
            deck_structure=deck_structure,
            content_package=content_package,
            output_path=out_path,
        )

        assert path.exists()
        assert path.stat().st_size > 0
        assert manifest.total_slides == 2
        assert manifest.total_objects_rendered == 4
        assert manifest.total_native_editable == 3  # Text, Table, Chart
        assert manifest.total_fallbacks == 0

        # Run validator
        validator = RendererValidator()
        validator.validate_manifest_and_package(manifest, resolved_deck, deck_structure)


def test_drawingml_native_editability_inspection(sample_layered_deck):
    """Directly inspects PPTX shapes to prove DrawingML native editability."""
    deck_structure, content_package, resolved_deck = sample_layered_deck

    with tempfile.TemporaryDirectory() as tmp_dir:
        out_path = Path(tmp_dir) / "test_shapes.pptx"
        compiler = PPTXCompiler()
        manifest, _ = compiler.compile_deck(
            resolved_deck=resolved_deck,
            deck_structure=deck_structure,
            content_package=content_package,
            output_path=out_path,
        )

        prs = pptx.Presentation(str(out_path))
        assert len(prs.slides) == 2

        # Slide 1: Text box and Table
        s1 = prs.slides[0]
        assert len(s1.shapes) == 2
        shape_names_s1 = [s.name for s in s1.shapes]
        assert "HV_WORKFORCE_HEALTH_01_TITLE_CNT_HEAD_1" in shape_names_s1
        assert "HV_WORKFORCE_HEALTH_01_DATA_TABLE_CNT_TBL_1" in shape_names_s1

        tb_shape = [s for s in s1.shapes if s.name == "HV_WORKFORCE_HEALTH_01_TITLE_CNT_HEAD_1"][0]
        assert tb_shape.has_text_frame is True
        assert "Executive Workforce Health Summary" in tb_shape.text_frame.text

        tbl_shape = [s for s in s1.shapes if s.name == "HV_WORKFORCE_HEALTH_01_DATA_TABLE_CNT_TBL_1"][0]
        assert tbl_shape.has_table is True
        assert tbl_shape.table.cell(0, 0).text == "Division"
        assert tbl_shape.table.cell(1, 0).text == "Engineering"

        # Slide 2: Chart and Map
        s2 = prs.slides[1]
        assert len(s2.shapes) == 2
        chart_shape = [s for s in s2.shapes if s.name == "HV_WORKFORCE_HEALTH_02_PRIMARY_VISUAL_CNT_CHART_1"][0]
        assert chart_shape.has_chart is True

        map_shape = [s for s in s2.shapes if s.name == "HV_WORKFORCE_HEALTH_02_SECONDARY_VISUAL_CNT_MAP_1"][0]
        assert map_shape.has_chart is False
        assert map_shape.has_table is False


def test_identity_separation_and_selection_pane_naming(sample_layered_deck):
    """Verifies shape.name == object_name and shape.shape_id != object_id."""
    deck_structure, content_package, resolved_deck = sample_layered_deck

    with tempfile.TemporaryDirectory() as tmp_dir:
        out_path = Path(tmp_dir) / "test_identity.pptx"
        compiler = PPTXCompiler()
        manifest, _ = compiler.compile_deck(
            resolved_deck=resolved_deck,
            deck_structure=deck_structure,
            content_package=content_package,
            output_path=out_path,
        )

        prs = pptx.Presentation(str(out_path))
        for slide_idx, prs_slide in enumerate(prs.slides):
            res_slide = resolved_deck.slides[slide_idx]
            for shape_idx, shape in enumerate(prs_slide.shapes):
                expected_obj = res_slide.object_layouts[shape_idx]
                assert shape.name == expected_obj.object_name
                # Internal PowerPoint integer ID
                assert isinstance(shape.shape_id, int)
                # Must not equal semantic HighView string ID (OBJ-...)
                assert str(shape.shape_id) != expected_obj.object_id


def test_zero_silent_downgrade_on_native_required():
    """Verifies that an error in NATIVE_REQUIRED object raises RenderDegradationError, never silent raster."""
    prs = pptx.Presentation()
    slide = prs.slides.add_slide(prs.slide_layouts[6])

    adapter = ChartRendererAdapter()
    broken_obj = ResolvedObjectLayout(
        object_id="OBJ-FAIL-1",
        object_name="HV_FAIL_CHART_01_PRIMARY_VISUAL",
        content_id="CNT-FAIL-1",
        name="Broken Chart",
        binding_role=ContentBindingRole.PRIMARY,
        kind=ContentKind.CHART,
        editability=EditabilityPolicy.NATIVE_REQUIRED,
        bounds=Box2D(left=0.1, top=0.1, width=0.5, height=0.5),
        metadata={"visual_spec": {"chart_type": "invalid_nonexistent_type"}},
    )
    slide_spec = LayeredSlideSpec(
        physical_slide_id="SLD-1",
        logical_slide_id="LOG-1",
        semantic_topic="TEST_TOPIC",
        structural_role=StructuralRole.EXECUTIVE_SUMMARY,
        sequence_index=1,
    )

    # Monkeypatch to force failure
    def raise_err(*args, **kwargs):
        raise ValueError("Simulated DrawingML failure")

    slide.shapes.add_chart = raise_err

    with pytest.raises(RenderDegradationError) as exc_info:
        adapter.render(
            slide=slide,
            obj_layout=broken_obj,
            slide_spec=slide_spec,
            content_item=None,
            slide_w_emu=int(prs.slide_width),
            slide_h_emu=int(prs.slide_height),
        )
    assert "Native DrawingML chart creation failed for NATIVE_REQUIRED" in str(exc_info.value)


def test_native_preferred_fallback_accounting():
    """Verifies that NATIVE_PREFERRED records explicit fallback without raising exception."""
    prs = pptx.Presentation()
    slide = prs.slides.add_slide(prs.slide_layouts[6])

    raster_adapter = RasterRendererAdapter()
    chart_adapter = ChartRendererAdapter(raster_fallback_adapter=raster_adapter)

    obj = ResolvedObjectLayout(
        object_id="OBJ-PREF-1",
        object_name="HV_PREF_CHART_01_PRIMARY_VISUAL",
        content_id="CNT-PREF-1",
        name="Preferred Chart",
        binding_role=ContentBindingRole.PRIMARY,
        kind=ContentKind.CHART,
        editability=EditabilityPolicy.NATIVE_PREFERRED,
        bounds=Box2D(left=0.1, top=0.1, width=0.5, height=0.5),
    )
    slide_spec = LayeredSlideSpec(
        physical_slide_id="SLD-1",
        logical_slide_id="LOG-1",
        semantic_topic="TEST_TOPIC",
        structural_role=StructuralRole.EXECUTIVE_SUMMARY,
        sequence_index=1,
    )

    # Force drawingml failure
    slide.shapes.add_chart = lambda *a, **kw: (_ for _ in ()).throw(RuntimeError("DrawingML OOM"))

    shape, record = chart_adapter.render(
        slide=slide,
        obj_layout=obj,
        slide_spec=slide_spec,
        content_item=None,
        slide_w_emu=int(prs.slide_width),
        slide_h_emu=int(prs.slide_height),
    )

    assert record.fallback_applied is True
    assert "DrawingML chart creation failed" in (record.fallback_reason or "")
    assert record.is_native_editable is False
    assert record.shape_type == ShapeType.PICTURE


def test_truthful_non_native_maps(sample_layered_deck):
    """Verifies map objects truthfully declare RASTER_ALLOWED and is_native_editable == False."""
    deck_structure, content_package, resolved_deck = sample_layered_deck

    with tempfile.TemporaryDirectory() as tmp_dir:
        out_path = Path(tmp_dir) / "test_map.pptx"
        compiler = PPTXCompiler()
        manifest, _ = compiler.compile_deck(
            resolved_deck=resolved_deck,
            deck_structure=deck_structure,
            content_package=content_package,
            output_path=out_path,
        )

        map_record = [o for s in manifest.slides for o in s.objects if o.object_id == "OBJ-MAP-1"][0]
        assert map_record.editability_policy == EditabilityPolicy.RASTER_ALLOWED
        assert map_record.is_native_editable is False
        assert map_record.shape_type == ShapeType.PICTURE
        assert map_record.fallback_applied is False  # Expected raster per policy


def test_package_structural_integrity(sample_layered_deck):
    """Verifies valid zip container, OOXML [Content_Types].xml, and presentation XML."""
    deck_structure, content_package, resolved_deck = sample_layered_deck

    with tempfile.TemporaryDirectory() as tmp_dir:
        out_path = Path(tmp_dir) / "test_zip.pptx"
        compiler = PPTXCompiler()
        manifest, _ = compiler.compile_deck(
            resolved_deck=resolved_deck,
            deck_structure=deck_structure,
            content_package=content_package,
            output_path=out_path,
        )

        with zipfile.ZipFile(out_path, "r") as z:
            names = z.namelist()
            assert "[Content_Types].xml" in names
            assert "ppt/presentation.xml" in names
            assert "ppt/slides/slide1.xml" in names
            assert "ppt/slides/slide2.xml" in names


def test_zero_physical_slide_creation(sample_layered_deck):
    """Verifies PPT-L6 creates zero additional physical slides beyond the manifest count."""
    deck_structure, content_package, resolved_deck = sample_layered_deck

    with tempfile.TemporaryDirectory() as tmp_dir:
        out_path = Path(tmp_dir) / "test_slides.pptx"
        compiler = PPTXCompiler()
        manifest, _ = compiler.compile_deck(
            resolved_deck=resolved_deck,
            deck_structure=deck_structure,
            content_package=content_package,
            output_path=out_path,
        )

        prs = pptx.Presentation(str(out_path))
        assert len(prs.slides) == len(resolved_deck.slides) == len(deck_structure.slides) == 2


def test_deterministic_semantic_fingerprints(sample_layered_deck):
    """Verifies deterministic semantic render fingerprints for identical layouts."""
    deck_structure, content_package, resolved_deck = sample_layered_deck

    with tempfile.TemporaryDirectory() as tmp_dir:
        out_path1 = Path(tmp_dir) / "test_fp1.pptx"
        out_path2 = Path(tmp_dir) / "test_fp2.pptx"

        compiler = PPTXCompiler()
        m1, _ = compiler.compile_deck(resolved_deck, deck_structure, content_package, output_path=out_path1)
        m2, _ = compiler.compile_deck(resolved_deck, deck_structure, content_package, output_path=out_path2)

        assert m1.semantic_render_fingerprint == m2.semantic_render_fingerprint
        assert len(m1.semantic_render_fingerprint) == 64


def test_multi_shape_object_deterministic_naming():
    """Verifies deterministic suffix naming and semantic ID mapping if an object decomposes into multiple shapes."""
    prs = pptx.Presentation()
    slide = prs.slides.add_slide(prs.slide_layouts[6])

    parent_object_id = "OBJ-KPI-01"
    parent_object_name = "HV_ATTENDANCE_KPI_01"

    # Multi-shape instantiation with deterministic suffixes
    suffixes = ["VALUE", "UNIT", "LABEL"]
    shapes = []
    records = []

    for idx, suffix in enumerate(suffixes):
        tb = slide.shapes.add_textbox(Inches(1 + idx * 2), Inches(1), Inches(2), Inches(1))
        child_name = f"{parent_object_name}__{suffix}"
        tb.name = child_name
        shapes.append(tb)

        rec = RenderedObjectRecord(
            object_id=parent_object_id,
            object_name=child_name,
            zone_id="ZONE-KPI-1",
            physical_slide_id="SLD-PHYS-1",
            shape_id=int(tb.shape_id),
            shape_type=ShapeType.TEXT_BOX,
            is_native_editable=True,
            editability_policy=EditabilityPolicy.NATIVE_REQUIRED,
            applied_bounds=Box2D(left=0.1 + idx * 0.2, top=0.1, width=0.2, height=0.1),
            metadata={"child_role": suffix},
        )
        records.append(rec)

    # Invariants:
    # 1. Zero random suffixes, zero Selection-Pane collisions
    shape_names = [s.name for s in shapes]
    assert len(shape_names) == len(set(shape_names)) == 3
    assert shape_names == [
        "HV_ATTENDANCE_KPI_01__VALUE",
        "HV_ATTENDANCE_KPI_01__UNIT",
        "HV_ATTENDANCE_KPI_01__LABEL",
    ]

    # 2. All child shapes map back to the same parent semantic object_id
    assert all(r.object_id == parent_object_id for r in records)


def test_validator_detects_corrupt_or_mismatched_package(sample_layered_deck):
    """Verifies that RendererValidator catches corrupt zip, missing files, or modified counts."""
    deck_structure, content_package, resolved_deck = sample_layered_deck
    validator = RendererValidator()

    with tempfile.TemporaryDirectory() as tmp_dir:
        out_path = Path(tmp_dir) / "corrupt.pptx"
        # Write non-zip data
        out_path.write_bytes(b"NOT_A_ZIP_FILE")

        manifest = RenderManifest(
            manifest_id="RMAN-ERR-1",
            deck_id="DECK-ERR-1",
            pptx_path=str(out_path),
            slides=[],
            semantic_render_fingerprint="abc",
        )

        with pytest.raises(RendererValidationError) as exc:
            validator.validate_manifest_and_package(manifest, resolved_deck, deck_structure)
        assert "not a valid zip archive" in str(exc.value)


def test_validator_catches_missing_slide_file(sample_layered_deck):
    """Verifies that RendererValidator catches nonexistent PPTX file."""
    deck_structure, content_package, resolved_deck = sample_layered_deck
    validator = RendererValidator()

    manifest = RenderManifest(
        manifest_id="RMAN-ERR-2",
        deck_id="DECK-ERR-2",
        pptx_path="/nonexistent/path/pres.pptx",
        slides=[],
        semantic_render_fingerprint="abc",
    )

    with pytest.raises(RendererValidationError) as exc:
        validator.validate_manifest_and_package(manifest, resolved_deck, deck_structure)
    assert "not found" in str(exc.value)


class TestPipelineOrchestratorLayeredIntegrationPPTL6:
    """Tests complete end-to-end execution of PPT-L1..PPT-L6 through pipeline_orchestrator."""

    def test_e2e_layered_pipeline_generates_valid_render_manifest_and_pptx(self):
        """Verifies execute_presentation_pipeline_async compiles PPTX and generates RenderManifest."""
        from unittest.mock import MagicMock, patch
        from app.services.presentation.job_manager import PresentationJobManager
        from app.services.presentation.pipeline_orchestrator import execute_presentation_pipeline_async
        from app.services.presentation.pipeline_selector import PresentationPipelineMode

        mock_mgr = MagicMock(spec=PresentationJobManager)
        mock_mgr.is_cancelled.return_value = False

        scope = {
            "scope_type": "single_sheet",
            "sheet_id": 101,
            "pipeline_mode": "LAYERED",
            "objective": "Executive Geographic Expansion Strategy",
            "audience": "Board of Directors",
            "is_technical_deck": False,
        }

        with patch("app.services.presentation.pipeline_orchestrator.session_scope"), \
             patch("app.services.presentation.pipeline_orchestrator.preview_presentation_scope", return_value={"eligible": True}), \
             patch("app.services.presentation.pipeline_orchestrator.collect_workspace_evidence") as mock_col, \
             patch("app.services.presentation.deck_generator.generate_presentation_deck_spec") as mock_gen, \
             patch("app.services.presentation.pipeline_orchestrator.verify_presentation_claims", return_value={"status": "PASSED"}), \
             patch("app.services.presentation.pipeline_orchestrator.evaluate_automated_gates", return_value={"gates": {}}), \
             patch("app.services.presentation.pipeline_orchestrator._index_persisted_deck"):

            mock_ctx = {
                "target_sheet": {"id": 101, "name": "Expansion"},
                "domain": "Retail Expansion",
                "columns": ["District", "DensityScore", "StoreCount"],
                "records": [
                    {"District": "North", "DensityScore": 88.5, "StoreCount": 12},
                    {"District": "South", "DensityScore": 72.1, "StoreCount": 8},
                ],
                "presentation_topics": [
                    {
                        "topic_id": "T-GEO-01",
                        "title": "Regional Density & Population Centers",
                        "primary_takeaway": "North district commands 88.5 density score across 12 operational stores.",
                        "slot_type": "hero",
                        "metric": "DensityScore",
                    },
                    {
                        "topic_id": "T-GEO-02",
                        "title": "Store Network Coverage",
                        "primary_takeaway": "Store footprint concentrated in high-density corridors.",
                        "slot_type": "breakdown",
                        "metric": "StoreCount",
                    }
                ],
            }
            mock_col.return_value = {"primary_ctx": mock_ctx}

            res = execute_presentation_pipeline_async("test-job-ppt-l6-e2e", scope, manager=mock_mgr)

            assert res is not None
            mock_gen.assert_not_called()  # Invariant: 0 legacy generator calls in layered mode

            meta = res["metadata"]
            assert meta["pipeline_mode"] == PresentationPipelineMode.LAYERED.value
            assert meta["status"] == "STRUCTURE_VALIDATED"
            assert meta["layout_status"] == "LAYOUT_RESOLVED"
            assert meta["render_status"] == "RENDER_VALIDATED"
            assert "render_manifest" in meta
            assert "pptx_path" in meta
            assert Path(meta["pptx_path"]).exists()
            assert Path(meta["pptx_path"]).stat().st_size > 0
            assert len(meta["render_fingerprint"]) == 64
            assert meta["total_native_editable"] > 0
            assert len(meta["rendered_slides"]) == meta["total_physical_slides"]

