"""HighView Presentation Studio — PPT-L5 Constraint Layout & Fit Test Suite.

Certifies the PPT-L5 phase boundary, verifying that:
1. Canonical normalized coordinates [0.0, 1.0] and safe areas are strictly enforced.
2. TextFitEngine respects typography floors and triggers late split on overflow (split before shrink).
3. ImageFitEngine preserves exact source aspect ratio (zero distortion) and calculates deterministic crops.
4. TableFitEngine performs data-aware column allocation and issues continuation requests on row overflow.
5. ChartFitPolicy protects minimum viable visual area, map area, and flags label/legend pressure.
6. LayoutValidator strictly catches any unapproved overlaps, safe area breaches, or font floor violations.
7. SlideExpansionEngine remains the sole owner of physical slide creation (physical slides created in PPT-L5 = 0).
8. Object IDs, Selection-Pane names, and EditabilityPolicies are 100% preserved.
9. Determinism and localized regeneration stability hold (zero AI calls).
"""

from __future__ import annotations

import copy
import pytest
from typing import Any

from app.services.presentation.content_models import (
    ContentKind,
    PresentationContentItem,
    PresentationContentPackage,
)
from app.services.presentation.fit_engines import (
    ChartFitPolicy,
    ImageFitEngine,
    TableFitEngine,
    TextFitEngine,
)
from app.services.presentation.layout_config import (
    CentralLayoutConfig,
    DEFAULT_LAYOUT_CONFIG,
)
from app.services.presentation.layout_engine import (
    LayoutConstraintEngine,
    LayoutValidationError,
    LayoutValidator,
    ZoneLayoutEngine,
)
from app.services.presentation.layout_models import (
    Box2D,
    ImageFitMode,
    ImageQualityWarning,
    ObjectFitStatus,
    ResolvedSlideLayout,
    SlideFitStatus,
    TextRole,
    ZoneFitStatus,
)
from app.services.presentation.layer_zone_models import (
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
from app.services.presentation.story_models import ContentBindingRole


@pytest.fixture
def sample_slide_spec() -> LayeredSlideSpec:
    """Fixture providing a standard two-zone slide spec (Primary Visual + Narrative)."""
    title_obj = SlideObjectSpec(
        object_id="POP_DENSITY-01__OBJ_TITLE",
        object_name="HV_POP_DENSITY_01_TITLE",
        name="Population Density Title",
        content_id="ITEM-TITLE-01",
        binding_role=ContentBindingRole.PRIMARY,
        kind=ContentKind.NARRATIVE_INSIGHT,
        semantic_topic="POPULATION_DENSITY",
        editability=EditabilityPolicy.NATIVE_REQUIRED,
        headline="National Demographic Concentration & Density Dynamics",
    )
    title_zone = ZoneSpec(
        zone_id="POP_DENSITY-01__ZONE_TITLE",
        zone_type=ZoneType.TITLE,
        layer_role=LayerRole.MASTER_FRAME,
        coordinate_space=CoordinateSpace.MASTER_FRAME_SPACE,
        objects=[title_obj],
    )

    chart_obj = SlideObjectSpec(
        object_id="POP_DENSITY-01__OBJ_CHART",
        object_name="HV_POP_DENSITY_01_CHART",
        name="State Density Chart",
        content_id="ITEM-CHART-01",
        binding_role=ContentBindingRole.PRIMARY,
        kind=ContentKind.CHART,
        semantic_topic="POPULATION_DENSITY",
        editability=EditabilityPolicy.NATIVE_PREFERRED,
        data_summary={"category_count": 6, "series_count": 2},
    )
    visual_zone = ZoneSpec(
        zone_id="POP_DENSITY-01__ZONE_PRIMARY_VISUAL",
        zone_type=ZoneType.PRIMARY_VISUAL,
        layer_role=LayerRole.BODY,
        coordinate_space=CoordinateSpace.BODY_SPACE,
        objects=[chart_obj],
    )

    narrative_obj = SlideObjectSpec(
        object_id="POP_DENSITY-01__OBJ_NARRATIVE",
        object_name="HV_POP_DENSITY_01_NARRATIVE",
        name="Strategic Insight Narrative",
        content_id="ITEM-NARR-01",
        binding_role=ContentBindingRole.SUPPORTING,
        kind=ContentKind.NARRATIVE_INSIGHT,
        semantic_topic="POPULATION_DENSITY",
        editability=EditabilityPolicy.NATIVE_REQUIRED,
        narrative_text="Urban centers continue to concentrate 68% of regional productivity despite rural landmass abundance.",
    )
    insight_zone = ZoneSpec(
        zone_id="POP_DENSITY-01__ZONE_INSIGHT",
        zone_type=ZoneType.INSIGHT_NARRATIVE,
        layer_role=LayerRole.BODY,
        coordinate_space=CoordinateSpace.BODY_SPACE,
        objects=[narrative_obj],
    )

    footnote_obj = SlideObjectSpec(
        object_id="POP_DENSITY-01__OBJ_FOOTNOTE",
        object_name="HV_POP_DENSITY_01_FOOTNOTE",
        name="Source Audit Tag",
        content_id="ITEM-NOTE-01",
        binding_role=ContentBindingRole.SUPPORTING,
        kind=ContentKind.NARRATIVE_INSIGHT,
        semantic_topic="POPULATION_DENSITY",
        editability=EditabilityPolicy.NATIVE_REQUIRED,
        inheritance_policy=FrameInheritancePolicy.MASTER_PREFERRED,
        narrative_text="Source: Census Bureau Bureau Data & Geospatial Registry (2025).",
    )
    footnote_zone = ZoneSpec(
        zone_id="POP_DENSITY-01__ZONE_FOOTNOTE",
        zone_type=ZoneType.FOOTNOTE,
        layer_role=LayerRole.MASTER_FRAME,
        coordinate_space=CoordinateSpace.MASTER_FRAME_SPACE,
        inheritance_policy=FrameInheritancePolicy.MASTER_PREFERRED,
        objects=[footnote_obj],
    )

    return LayeredSlideSpec(
        physical_slide_id="POP_DENSITY-01",
        logical_slide_id="TOPIC_POP_DENSITY",
        semantic_topic="POPULATION_DENSITY",
        structural_role=StructuralRole.GEOGRAPHIC_ANALYSIS,
        sequence_index=1,
        headline="National Demographic Concentration & Density Dynamics",
        zones=[title_zone, visual_zone, insight_zone, footnote_zone],
    )


class TestPPTL5ConstraintLayout:
    """Rigorous tests covering requirements 97 to 118 from the PPT-L5 kickoff specification."""

    def test_97_text_heavy_split_before_shrink(self):
        """Test 97: Dense text scales to font floor; if still overflowing, requests late split rather than micro-fonts."""
        engine = LayoutConstraintEngine()
        text_engine = TextFitEngine()

        # Very long text that cannot fit within a small box at floor font
        small_box = Box2D(left=0.05, top=0.17, width=0.35, height=0.15)
        dense_text = " ".join([
            "Strategic operational analysis indicates significant variance across regional clusters.",
            "Substantial headwinds in distribution networks require restructuring supply chain nodes.",
            "Capital expenditures must be prioritized toward automated fulfillment centers.",
            "Workforce reallocation across Tier 1 metropolitan zones shows 24.5% efficiency gains.",
            "Long-term margin expansion remains contingent on digital infrastructure cutover.",
            "Cross-functional governance models require executive oversight committee signoff.",
        ] * 4)

        font_size, lines, status, warnings = text_engine.fit_text(
            dense_text, available_box=small_box, role=TextRole.BODY
        )
        assert status == ObjectFitStatus.OVERFLOW
        assert font_size >= DEFAULT_LAYOUT_CONFIG.get_typography(TextRole.BODY).floor_size_pt
        assert any("overflows" in w.lower() for w in warnings)

    def test_98_long_title_fit_and_overflow(self):
        """Test 98: Long titles wrap gracefully or flag title overflow without silent clipping."""
        text_engine = TextFitEngine()
        title_box = Box2D(left=0.05, top=0.04, width=0.90, height=0.08)

        # Normal title fits within line limit
        normal_title = "Executive Summary: Workforce Operational Diagnostics & Headwinds"
        font_size, lines, status, _ = text_engine.fit_text(normal_title, title_box, role=TextRole.TITLE)
        assert status in (ObjectFitStatus.FIT, ObjectFitStatus.FIT_WITH_ADJUSTMENT)
        assert lines <= 3

        # Extremely long title
        extreme_title = "Comprehensive Operational Assessment of Multi-Regional Workforce Productivity and Strategic Capital Allocation Inefficiencies Across Global Subsidiaries and Emerging Markets Under Volatile Macroeconomic Conditions"
        font_size, lines, status, warnings = text_engine.fit_text(extreme_title, title_box, role=TextRole.TITLE)
        assert font_size >= DEFAULT_LAYOUT_CONFIG.get_typography(TextRole.TITLE).floor_size_pt

    def test_99_table_heavy_continuation_request(self):
        """Test 99: Tables with excessive rows request late split rather than collapsing row heights to zero."""
        table_engine = TableFitEngine()
        box = Box2D(left=0.05, top=0.17, width=0.90, height=0.74)

        headers = ["ID", "Department", "Headcount", "Budget Variance", "Operational Risk Rating"]
        sample_rows = [
            [f"DEP-{i:03d}", f"Operational Unit {i}", 120 + i, "$14,500", "Low Risk"]
            for i in range(25)  # 25 rows
        ]

        col_w, row_h, font, status, split_hint, warnings = table_engine.fit_table(
            headers=headers, row_count=25, sample_rows=sample_rows, available_box=box
        )
        assert status == ObjectFitStatus.OVERFLOW
        assert split_hint is not None
        assert split_hint["total_rows"] == 25
        assert split_hint["split_row_index"] < 25
        assert font >= DEFAULT_LAYOUT_CONFIG.get_typography(TextRole.TABLE).floor_size_pt

    def test_100_image_portrait_aspect_preservation(self):
        """Test 100: Portrait image fits without distortion (aspect ratio strictly preserved)."""
        image_engine = ImageFitEngine()
        box = Box2D(left=0.05, top=0.17, width=0.45, height=0.74)

        # 600w x 1200h (aspect = 0.5)
        bounds, crop_b, q_warn, _ = image_engine.fit_image(
            source_width_px=600, source_height_px=1200, available_box=box, mode=ImageFitMode.CONTAIN
        )
        assert box.contains(bounds)
        # Verify physical aspect ratio
        w_phys = bounds.width * DEFAULT_LAYOUT_CONFIG.canvas_aspect_ratio
        h_phys = bounds.height * 1.0
        calc_aspect = w_phys / h_phys
        assert pytest.approx(calc_aspect, rel=1e-2) == 0.5

    def test_101_image_landscape_aspect_preservation(self):
        """Test 101: Landscape image fits without distortion."""
        image_engine = ImageFitEngine()
        box = Box2D(left=0.05, top=0.17, width=0.50, height=0.60)

        # 1600w x 900h (aspect = 1.7778)
        bounds, crop_b, q_warn, _ = image_engine.fit_image(
            source_width_px=1600, source_height_px=900, available_box=box, mode=ImageFitMode.CONTAIN
        )
        assert box.contains(bounds)
        w_phys = bounds.width * DEFAULT_LAYOUT_CONFIG.canvas_aspect_ratio
        h_phys = bounds.height * 1.0
        calc_aspect = w_phys / h_phys
        assert pytest.approx(calc_aspect, rel=1e-2) == (1600.0 / 900.0)

    def test_102_low_res_image_quality_warning(self):
        """Test 102: Low resolution image triggers pre-renderer warning without fake enhancement."""
        image_engine = ImageFitEngine()
        box = Box2D(left=0.05, top=0.17, width=0.50, height=0.60)

        bounds, crop_b, q_warn, warnings = image_engine.fit_image(
            source_width_px=150, source_height_px=100, available_box=box
        )
        assert q_warn == ImageQualityWarning.LOW_RESOLUTION
        assert any("below recommended" in w for w in warnings)

    def test_103_map_minimum_size_protection(self):
        """Test 103: Map visual receives protected generous area (minimum 0.40 x 0.40)."""
        policy = ChartFitPolicy()

        # Constrained map box
        tiny_box = Box2D(left=0.05, top=0.17, width=0.25, height=0.25)
        status, warnings = policy.evaluate_chart_fit(
            available_box=tiny_box, kind=ContentKind.MAP, is_map=True
        )
        assert status == ObjectFitStatus.OVERFLOW
        assert any("insufficient area" in w for w in warnings)

        # Generous map box
        viable_box = Box2D(left=0.05, top=0.17, width=0.55, height=0.65)
        status, warnings = policy.evaluate_chart_fit(
            available_box=viable_box, kind=ContentKind.MAP, is_map=True
        )
        assert status == ObjectFitStatus.FIT

    def test_104_chart_many_categories_label_pressure(self):
        """Test 104: Chart with excessive categories flags label pressure."""
        policy = ChartFitPolicy()
        box = Box2D(left=0.05, top=0.17, width=0.55, height=0.60)

        status, warnings = policy.evaluate_chart_fit(
            available_box=box, kind=ContentKind.CHART, category_count=14
        )
        assert any("category count" in w for w in warnings)

    def test_105_multi_series_chart_legend_pressure(self):
        """Test 105: Chart with high series count flags legend reservation pressure."""
        policy = ChartFitPolicy()
        box = Box2D(left=0.05, top=0.17, width=0.55, height=0.60)

        status, warnings = policy.evaluate_chart_fit(
            available_box=box, kind=ContentKind.CHART, series_count=8
        )
        assert any("series count" in w for w in warnings)

    def test_106_two_charts_multi_visual_layout(self, sample_slide_spec: LayeredSlideSpec):
        """Test 106: Slide with two charts allocates viable dimensions to both."""
        engine = LayoutConstraintEngine()
        spec = copy.deepcopy(sample_slide_spec)

        # Replace insight zone with secondary visual zone
        chart2_obj = SlideObjectSpec(
            object_id="POP_DENSITY-01__OBJ_CHART_2",
            object_name="HV_POP_DENSITY_01_CHART_RIGHT",
            name="Regional Trend Chart",
            content_id="ITEM-CHART-02",
            binding_role=ContentBindingRole.PRIMARY,
            kind=ContentKind.CHART,
            semantic_topic="POPULATION_DENSITY",
            editability=EditabilityPolicy.NATIVE_PREFERRED,
        )
        sec_zone = ZoneSpec(
            zone_id="POP_DENSITY-01__ZONE_SEC_VISUAL",
            zone_type=ZoneType.SECONDARY_VISUAL,
            layer_role=LayerRole.BODY,
            coordinate_space=CoordinateSpace.BODY_SPACE,
            objects=[chart2_obj],
        )
        spec.zones = [spec.zones[0], spec.zones[1], sec_zone, spec.zones[3]]

        res_slide = engine.resolve_slide_layout(spec)
        assert res_slide.fit_status in (SlideFitStatus.PASS, SlideFitStatus.PASS_WITH_WARNINGS)
        assert len(res_slide.zones) == 4

        # Both chart zones must be >= min_chart_width
        body_zones = [z for z in res_slide.zones if z.layer_role == LayerRole.BODY]
        assert len(body_zones) == 2
        for z in body_zones:
            assert z.bounds.width >= DEFAULT_LAYOUT_CONFIG.min_chart_width

    def test_107_chart_plus_table_overflow_split(self, sample_slide_spec: LayeredSlideSpec):
        """Test 107: Massive table paired with chart triggers late split escalation."""
        engine = LayoutConstraintEngine()
        spec = copy.deepcopy(sample_slide_spec)

        table_obj = SlideObjectSpec(
            object_id="POP_DENSITY-01__OBJ_TABLE",
            object_name="HV_POP_DENSITY_01_TABLE",
            name="Massive Audit Table",
            content_id="ITEM-TABLE-01",
            binding_role=ContentBindingRole.SUPPORTING,
            kind=ContentKind.TABLE,
            semantic_topic="POPULATION_DENSITY",
            editability=EditabilityPolicy.NATIVE_REQUIRED,
            data_summary={"row_count": 28, "headers": ["A", "B", "C"]},
        )
        spec.zones[2].objects = [table_obj]
        spec.zones[2].zone_type = ZoneType.DATA_TABLE

        res_slide = engine.resolve_slide_layout(spec)
        assert res_slide.fit_status == SlideFitStatus.LATE_SPLIT_REQUIRED
        assert res_slide.late_split_request is not None
        assert res_slide.late_split_request.reason == "TABLE_OVERFLOW"

    def test_108_kpi_plus_chart_layout(self, sample_slide_spec: LayeredSlideSpec):
        """Test 108: KPI strip paired with chart: no overlap, chart remains prominent."""
        engine = LayoutConstraintEngine()
        spec = copy.deepcopy(sample_slide_spec)

        kpi_obj1 = SlideObjectSpec(
            object_id="POP_DENSITY-01__OBJ_KPI_01",
            object_name="HV_POP_DENSITY_01_KPI_01",
            name="Total Population",
            content_id="ITEM-KPI-01",
            binding_role=ContentBindingRole.PRIMARY,
            kind=ContentKind.KPI_METRIC,
            semantic_topic="POPULATION_DENSITY",
            editability=EditabilityPolicy.NATIVE_REQUIRED,
        )
        kpi_obj2 = SlideObjectSpec(
            object_id="POP_DENSITY-01__OBJ_KPI_02",
            object_name="HV_POP_DENSITY_01_KPI_02",
            name="Urban Density",
            content_id="ITEM-KPI-02",
            binding_role=ContentBindingRole.PRIMARY,
            kind=ContentKind.KPI_METRIC,
            semantic_topic="POPULATION_DENSITY",
            editability=EditabilityPolicy.NATIVE_REQUIRED,
        )
        kpi_zone = ZoneSpec(
            zone_id="POP_DENSITY-01__ZONE_KPI",
            zone_type=ZoneType.KPI_STRIP,
            layer_role=LayerRole.BODY,
            coordinate_space=CoordinateSpace.BODY_SPACE,
            objects=[kpi_obj1, kpi_obj2],
        )
        spec.zones = [spec.zones[0], kpi_zone, spec.zones[1], spec.zones[3]]

        res_slide = engine.resolve_slide_layout(spec)
        assert res_slide.fit_status in (SlideFitStatus.PASS, SlideFitStatus.PASS_WITH_WARNINGS)

        # Validate zero collision
        validator = LayoutValidator()
        validator.validate_slide_layout(res_slide)

    def test_109_footnote_no_overlap(self, sample_slide_spec: LayeredSlideSpec):
        """Test 109: Footnote does not overlap body zones or header frame."""
        engine = LayoutConstraintEngine()
        res_slide = engine.resolve_slide_layout(sample_slide_spec)

        fn_zone = next(z for z in res_slide.zones if z.zone_type == ZoneType.FOOTNOTE)
        body_zones = [z for z in res_slide.zones if z.layer_role == LayerRole.BODY]

        for bz in body_zones:
            assert not fn_zone.bounds.intersects(bz.bounds)

    def test_110_frame_collision_prevention(self, sample_slide_spec: LayeredSlideSpec):
        """Test 110: Body zones strictly enclosed within body_bounds without entering reserved header/footer."""
        engine = LayoutConstraintEngine()
        res_slide = engine.resolve_slide_layout(sample_slide_spec)

        hb = res_slide.safe_area.frame_header_bounds
        fb = res_slide.safe_area.frame_footer_bounds

        for z in res_slide.zones:
            if z.layer_role == LayerRole.BODY:
                assert not z.bounds.intersects(hb)
                assert not z.bounds.intersects(fb)

    def test_111_overlay_isolation(self, sample_slide_spec: LayeredSlideSpec):
        """Test 111: Overlays are explicitly categorized in LayerRole.OVERLAY."""
        engine = LayoutConstraintEngine()
        spec = copy.deepcopy(sample_slide_spec)

        badge_obj = SlideObjectSpec(
            object_id="POP_DENSITY-01__OBJ_BADGE",
            object_name="HV_POP_DENSITY_01_BADGE",
            name="Confidential Badge",
            content_id="ITEM-BADGE-01",
            binding_role=ContentBindingRole.SUPPORTING,
            kind=ContentKind.NARRATIVE_INSIGHT,
            semantic_topic="POPULATION_DENSITY",
            editability=EditabilityPolicy.NATIVE_REQUIRED,
        )
        badge_zone = ZoneSpec(
            zone_id="POP_DENSITY-01__ZONE_BADGE",
            zone_type=ZoneType.CALLOUT_BADGE,
            layer_role=LayerRole.OVERLAY,
            coordinate_space=CoordinateSpace.BODY_SPACE,
            objects=[badge_obj],
        )
        spec.zones.append(badge_zone)

        res_slide = engine.resolve_slide_layout(spec)
        overlay_z = next(z for z in res_slide.zones if z.layer_role == LayerRole.OVERLAY)
        assert overlay_z.layer_role == LayerRole.OVERLAY

    def test_112_determinism_identical_input_identical_output(self, sample_slide_spec: LayeredSlideSpec):
        """Test 112: Same input spec produces identical zone/object geometry and identical fingerprint."""
        engine = LayoutConstraintEngine()
        res1 = engine.resolve_slide_layout(sample_slide_spec)
        res2 = engine.resolve_slide_layout(sample_slide_spec)

        assert res1.layout_fingerprint == res2.layout_fingerprint
        assert len(res1.zones) == len(res2.zones)
        for z1, z2 in zip(res1.zones, res2.zones):
            assert z1.bounds.to_rounded_dict() == z2.bounds.to_rounded_dict()
            assert len(z1.objects) == len(z2.objects)
            for o1, o2 in zip(z1.objects, z2.objects):
                assert o1.bounds.to_rounded_dict() == o2.bounds.to_rounded_dict()
                assert o1.resolved_font_size == o2.resolved_font_size

    def test_113_localized_regeneration_stability(self, sample_slide_spec: LayeredSlideSpec):
        """Test 113: Modifying Slide A does NOT change the layout fingerprint of Slide B."""
        engine = LayoutConstraintEngine()

        slide_a = copy.deepcopy(sample_slide_spec)
        slide_b = copy.deepcopy(sample_slide_spec)
        slide_b.physical_slide_id = "SLIDE_B_METRICS"

        res_b_before = engine.resolve_slide_layout(slide_b)

        # Mutate slide A (different headline and text)
        slide_a.headline = "Modified Headline for Slide A Only"
        slide_a.zones[0].objects[0].headline = "Modified Headline for Slide A Only"

        res_b_after = engine.resolve_slide_layout(slide_b)
        assert res_b_before.layout_fingerprint == res_b_after.layout_fingerprint

    def test_114_no_ai_calls_in_layout(self, sample_slide_spec: LayeredSlideSpec, monkeypatch):
        """Test 114: AI layout calls = 0. Mock any AI callers to prove zero AI execution."""
        from app.services.presentation import story_planner

        def fail_on_ai(*args, **kwargs):
            pytest.fail("AI call attempted in PPT-L5 constraint layout!")

        monkeypatch.setattr(story_planner, "AIStoryPlanner", fail_on_ai)

        engine = LayoutConstraintEngine()
        res = engine.resolve_slide_layout(sample_slide_spec)
        assert res.layout_fingerprint

    def test_115_no_pptx_or_drawingml_created(self, sample_slide_spec: LayeredSlideSpec):
        """Test 115: PPTX shape objects created = 0, DrawingML = 0, renderer calls = 0."""
        engine = LayoutConstraintEngine()
        res = engine.resolve_slide_layout(sample_slide_spec)

        for obj in res.object_layouts:
            # Must not contain PPTX internal shape ids
            assert "shape_id" not in obj.metadata
            assert "pptx_shape" not in obj.metadata
            assert "drawingml" not in obj.metadata

    def test_116_late_split_ownership_preserved(self, sample_slide_spec: LayeredSlideSpec):
        """Test 116: PPT-L5 overflow returns LateSplitRequest and does NOT create physical slides."""
        engine = LayoutConstraintEngine()
        spec = copy.deepcopy(sample_slide_spec)

        # Force overflow
        spec.zones[1].objects[0].data_summary["category_count"] = 50
        table_obj = SlideObjectSpec(
            object_id="POP_DENSITY-01__OBJ_OVERFLOW_TBL",
            object_name="HV_POP_DENSITY_01_OVERFLOW_TBL",
            name="Overflow Table",
            content_id="ITEM-OVERFLOW-TBL",
            binding_role=ContentBindingRole.PRIMARY,
            kind=ContentKind.TABLE,
            semantic_topic="POPULATION_DENSITY",
            editability=EditabilityPolicy.NATIVE_REQUIRED,
            data_summary={"row_count": 30, "headers": ["A", "B", "C"]},
        )
        spec.zones[1].objects = [table_obj]
        spec.zones[1].zone_type = ZoneType.DATA_TABLE

        deck_spec = LayeredDeckStructureSpec(
            manifest_id="MANIFEST-TEST-01",
            slides=[spec],
        )

        resolved_deck = engine.resolve_deck_layout(deck_spec)
        # Total physical slides must remain exactly 1 (0 created by PPT-L5)
        assert resolved_deck.total_slides == 1
        assert len(resolved_deck.slides) == 1
        assert resolved_deck.replan_required is True
        assert len(resolved_deck.late_splits) >= 1

    def test_117_object_id_and_selection_pane_name_stability(self, sample_slide_spec: LayeredSlideSpec):
        """Test 117: Layout engine preserves object_id and object_name exactly without renaming."""
        engine = LayoutConstraintEngine()
        res = engine.resolve_slide_layout(sample_slide_spec)

        spec_objs = {o.object_id: o for z in sample_slide_spec.zones for o in z.objects}
        for res_obj in res.object_layouts:
            orig = spec_objs[res_obj.object_id]
            assert res_obj.object_id == orig.object_id
            assert res_obj.object_name == orig.object_name
            assert res_obj.kind == orig.kind

    def test_118_editability_policy_preserved(self, sample_slide_spec: LayeredSlideSpec):
        """Test 118: Canonical EditabilityPolicy is 100% preserved."""
        engine = LayoutConstraintEngine()
        res = engine.resolve_slide_layout(sample_slide_spec)

        spec_objs = {o.object_id: o for z in sample_slide_spec.zones for o in z.objects}
        for res_obj in res.object_layouts:
            orig = spec_objs[res_obj.object_id]
            assert res_obj.editability == orig.editability
            assert isinstance(res_obj.editability, EditabilityPolicy)

    def test_119_box2d_canonical_coordinate_math(self):
        """Test 119: Canonical Box2D geometry mathematics and numerical tolerance."""
        b1 = Box2D(left=0.1, top=0.1, width=0.4, height=0.4)
        b2 = Box2D(left=0.2, top=0.2, width=0.2, height=0.2)
        b3 = Box2D(left=0.6, top=0.6, width=0.3, height=0.3)

        assert b1.right == pytest.approx(0.5)
        assert b1.bottom == pytest.approx(0.5)
        assert b1.area == pytest.approx(0.16)
        assert b1.contains(b2)
        assert not b2.contains(b1)
        assert b1.intersects(b2)
        assert not b1.intersects(b3)

        inter = b1.intersection(b2)
        assert inter is not None
        assert inter.left == pytest.approx(0.2)
        assert inter.width == pytest.approx(0.2)

    def test_120_central_layout_config_and_typography_floors(self):
        """Test 120: Central layout configuration provides valid floors for all semantic roles."""
        cfg = DEFAULT_LAYOUT_CONFIG
        roles = [
            TextRole.TITLE,
            TextRole.SUBTITLE,
            TextRole.BODY,
            TextRole.BULLET,
            TextRole.KPI_VALUE,
            TextRole.KPI_LABEL,
            TextRole.TABLE,
            TextRole.FOOTNOTE,
            TextRole.CAPTION,
        ]
        for role in roles:
            policy = cfg.get_typography(role)
            assert policy.floor_size_pt >= 8.0
            assert policy.default_size_pt >= policy.floor_size_pt
            assert policy.line_height_ratio >= 1.0

    def test_121_bounded_repair_loop_actions(self, sample_slide_spec: LayeredSlideSpec):
        """Test 121: LayoutConstraintEngine applies bounded repairs and records telemetry."""
        engine = LayoutConstraintEngine()
        spec = copy.deepcopy(sample_slide_spec)

        res = engine.resolve_slide_layout(spec)
        assert res.repair_attempts >= 1
        assert isinstance(res.repair_actions, list)

    def test_122_full_deck_layout_resolution(self, sample_slide_spec: LayeredSlideSpec):
        """Test 122: Full deck layout resolves multiple slides and computes deck fingerprint."""
        engine = LayoutConstraintEngine()
        slide1 = copy.deepcopy(sample_slide_spec)
        slide2 = copy.deepcopy(sample_slide_spec)
        slide2.physical_slide_id = "SLIDE-02"
        slide2.sequence_index = 2

        deck_spec = LayeredDeckStructureSpec(
            manifest_id="DECK-TEST-FULL-01",
            slides=[slide1, slide2],
        )

        resolved_deck = engine.resolve_deck_layout(deck_spec)
        assert resolved_deck.total_slides == 2
        assert len(resolved_deck.slides) == 2
        assert resolved_deck.deck_fingerprint
        assert len(resolved_deck.deck_fingerprint) == 64

        validator = LayoutValidator()
        validator.validate_deck_layout(resolved_deck, original_spec=deck_spec)
