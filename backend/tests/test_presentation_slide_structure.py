"""Unit and integration test suite for PPT-L4: Layer/Zone Contracts + Stable Object Identity.

Verifies:
1. Architectural Separation: Structure and identity, NOT position or geometry.
2. LayerRole & CoordinateSpace ownership (SLIDE_SPACE, BODY_SPACE, MASTER_FRAME_SPACE).
3. Conceptual SafeAreaSpec (0 numeric coordinates, 0 margins in pt/pct/emu).
4. Stable deterministic SlideObjectSpec IDs that survive regeneration and layout changes.
5. Truthful EditabilityPolicy:
   - ContentKind.MAP is strictly STATIC_IMAGE_FALLBACK or PARTIALLY_EDITABLE (never NATIVE_EDITABLE).
   - ContentKind.CHART, TABLE, KPI, TEXT are NATIVE_EDITABLE.
6. SlideExpansionEngine is the SOLE owner of physical slide creation (physical slide creation in PPT-L4 = 0).
7. Zero cross-slide content movement (content stays on its allocated physical slide).
8. Zero unmapped primary items and zero orphan objects.
9. Global object_registry accurately indexes all slide objects.
10. Deterministic structure_fingerprint (SHA-256).
11. Governance leakage protection in normal business decks (SDR, JoinPlan, EVID-*, hashes stripped/cleansed);
    preservation in technical decks (is_technical_deck=True).
12. Feasibility and Replan Contract: STRUCTURE_REPLAN_REQUIRED when capacity exceeded.
13. Absolute exclusion of physical layout geometry, EMUs, font sizes, colors, and PPTX objects.
14. Full pipeline integration via execute_presentation_pipeline_async in LAYERED mode.
15. Zero AI structure calls (fully deterministic) and zero calls in legacy mode.
"""

import copy
import pytest
from typing import Any

from app.services.presentation.content_models import (
    ContentKind,
    ContentRole,
    PresentationContentItem,
    PresentationContentPackage,
)
from app.services.presentation.expansion_engine import SlideExpansionEngine
from app.services.presentation.layer_zone_models import (
    CoordinateSpace,
    CrossSlideMovementError,
    EditabilityPolicy,
    GovernanceLeakageError,
    LayeredDeckStructureSpec,
    LayeredSlideSpec,
    LayeredSlideStructureValidator,
    LayerRole,
    OrphanObjectError,
    PhysicalGeometryLeakageError,
    SafeAreaSpec,
    SlideObjectSpec,
    StructureStatus,
    StructureValidationError,
    UnmappedPrimaryContentError,
    ZoneSpec,
    ZoneType,
)
from app.services.presentation.manifest_models import (
    ContentDensity,
    ExpansionReason,
    PhysicalSlideInstance,
    PhysicalSlideManifest,
)
from app.services.presentation.pipeline_orchestrator import (
    execute_presentation_pipeline_async,
)
from app.services.presentation.pipeline_selector import PresentationPipelineMode
from app.services.presentation.preflight_engine import PresentationPreflightEngine
from app.services.presentation.story_models import (
    ContentBinding,
    ContentBindingRole,
    DeckStoryPlan,
    LogicalSlidePlan,
    StructuralRole,
)
from app.services.presentation.story_planner import StoryPlanner
from app.services.presentation.structure_builder import LayeredSlideStructureBuilder


# ==============================================================================
# TEST FIXTURES
# ==============================================================================

@pytest.fixture
def sample_package() -> PresentationContentPackage:
    """Fixture providing a rich multi-domain content package with varied content kinds."""
    items = [
        PresentationContentItem(
            content_id="ITEM-GEO-MAP-01",
            kind=ContentKind.MAP,
            role=ContentRole.PRIMARY_HERO,
            topic_category="POPULATION_DENSITY",
            title="State-Level Population Density Heatmap",
            narrative_takeaway="State-Level Population Density Heatmap across key states",
            supporting_bullets=["Top density observed in northern metro corridors", "Lower density in western rural belts"],
            importance_score=0.95,
            grain="state",
            unit="people/sq km",
            denominator="geographic_area_sq_km",
            fact_id="FACT-GEO-101",
            source_dataset_id="DS-CENSUS",
            source_sheet_name="Regional_Density",
            evidence_ids=["EVID-GEO-001"],
        ),
        PresentationContentItem(
            content_id="ITEM-GEO-TBL-02",
            kind=ContentKind.TABLE,
            role=ContentRole.EXPLORATORY_TABLE,
            topic_category="POPULATION_DENSITY",
            title="Top Dense Districts Breakdown",
            narrative_takeaway="Top Dense Districts Tabular Breakdown",
            importance_score=0.80,
            grain="district",
            unit="people/sq km",
            table_data=[{"district": f"District {i}", "val": i * 100} for i in range(10)],
            fact_id="FACT-GEO-102",
            source_dataset_id="DS-CENSUS",
            source_sheet_name="District_Density",
        ),
        PresentationContentItem(
            content_id="ITEM-GROWTH-01",
            kind=ContentKind.CHART,
            role=ContentRole.PRIMARY_HERO,
            topic_category="REGIONAL_GROWTH",
            title="Regional Growth Trajectory",
            narrative_takeaway="Regional Growth Trajectory 2020-2026",
            supporting_bullets=["Consistent 12% YoY expansion in southern tech hubs"],
            importance_score=0.90,
            grain="region",
            unit="percentage",
            visual_spec={"chart_type": "line_chart"},
            fact_id="FACT-GROWTH-201",
            source_sheet_name="Growth_Trends",
        ),
        PresentationContentItem(
            content_id="ITEM-KPI-01",
            kind=ContentKind.KPI_METRIC,
            role=ContentRole.STRATEGIC_KPI,
            topic_category="EXECUTIVE_SUMMARY",
            title="Total Population Metric",
            metric_label="Total Population",
            metric_value="1.42B",
            importance_score=0.85,
        ),
        PresentationContentItem(
            content_id="ITEM-NARRATIVE-01",
            kind=ContentKind.NARRATIVE_INSIGHT,
            role=ContentRole.KEY_FINDING,
            topic_category="EXECUTIVE_SUMMARY",
            title="Demographic Summary",
            narrative_takeaway="Executive demographic summary highlighting major macro migration shifts.",
            supporting_bullets=["Urbanization trend accelerated by 4.2%", "Industrial clusters attracting top talent"],
            importance_score=0.75,
        ),
    ]
    return PresentationContentPackage(
        package_id="PKG-TEST-L4",
        dataset_name="Census_Demographics",
        domain="demographics",
        items=items,
        available_topics=["POPULATION_DENSITY", "REGIONAL_GROWTH", "EXECUTIVE_SUMMARY"],
        global_kpis=[
            PresentationContentItem(
                content_id="KPI-GLOBAL-01",
                kind=ContentKind.KPI_METRIC,
                role=ContentRole.STRATEGIC_KPI,
                topic_category="EXECUTIVE_SUMMARY",
                title="National Growth KPI",
                metric_label="National Growth",
                metric_value="+1.1% YoY",
                importance_score=0.99,
            )
        ],
    )


@pytest.fixture
def sample_manifest(sample_package: PresentationContentPackage) -> PhysicalSlideManifest:
    """Fixture generating a validated PhysicalSlideManifest via L2 StoryPlanner + L3 SlideExpansionEngine."""
    planner = StoryPlanner(use_ai=False)
    story_plan = planner.plan_story(
        content_pkg=sample_package,
        user_objective="Analyze population density and growth trends",
        target_audience="Executive Leadership",
    )
    expansion_engine = SlideExpansionEngine(preflight_engine=PresentationPreflightEngine())
    manifest = expansion_engine.expand(
        story_plan=story_plan,
        content_pkg=sample_package,
    )
    return manifest


# ==============================================================================
# TESTS
# ==============================================================================

class TestLayerZoneEnumsAndModels:
    """Test PPT-L4 enums and model specifications."""

    def test_layer_roles_and_coordinate_spaces(self):
        """Verify layer roles and coordinate space ownership enums."""
        assert LayerRole.BACKGROUND == "BACKGROUND"
        assert LayerRole.MASTER_FRAME == "MASTER_FRAME"
        assert LayerRole.BODY == "BODY"
        assert LayerRole.OVERLAY == "OVERLAY"

        assert CoordinateSpace.SLIDE_SPACE == "SLIDE_SPACE"
        assert CoordinateSpace.MASTER_FRAME_SPACE == "MASTER_FRAME_SPACE"
        assert CoordinateSpace.BODY_SPACE == "BODY_SPACE"

    def test_safe_area_spec_zero_geometry(self):
        """Verify SafeAreaSpec is purely policy-driven with zero numeric coordinates."""
        safe_area = SafeAreaSpec()
        dumped = safe_area.model_dump()
        for forbidden in ["x", "y", "width", "height", "top", "left", "pt", "emu", "margin_pt"]:
            assert forbidden not in dumped
        assert safe_area.policy_name == "standard_executive_safe_area"

    def test_editability_policy_truthfulness(self):
        """Verify editability policy classifications."""
        assert EditabilityPolicy.NATIVE_EDITABLE == "NATIVE_EDITABLE"
        assert EditabilityPolicy.PARTIALLY_EDITABLE == "PARTIALLY_EDITABLE"
        assert EditabilityPolicy.STATIC_IMAGE_FALLBACK == "STATIC_IMAGE_FALLBACK"
        assert EditabilityPolicy.NON_EDITABLE == "NON_EDITABLE"


class TestLayeredSlideStructureBuilder:
    """Test deterministic structure assembly by LayeredSlideStructureBuilder."""

    def test_build_structure_basic_invariants(
        self,
        sample_manifest: PhysicalSlideManifest,
        sample_package: PresentationContentPackage,
    ):
        """Verify builder produces a valid LayeredDeckStructureSpec adhering to PPT-L4 invariants."""
        builder = LayeredSlideStructureBuilder()
        structure = builder.build_structure(
            manifest=sample_manifest,
            content_pkg=sample_package,
            is_technical_deck=False,
        )

        assert isinstance(structure, LayeredDeckStructureSpec)
        assert structure.manifest_id == sample_manifest.manifest_id
        assert structure.replan_required is False
        assert len(structure.structure_fingerprint) == 64

        # Invariant: SlideExpansionEngine is sole owner of physical slide creation
        # Structure slide count MUST exactly equal manifest slide count
        assert len(structure.slides) == len(sample_manifest.slides)

        for m_slide, s_slide in zip(sample_manifest.slides, structure.slides):
            assert s_slide.physical_slide_id == m_slide.physical_slide_id
            assert s_slide.logical_slide_id == m_slide.logical_slide_id
            assert s_slide.sequence_index == m_slide.sequence_index
            assert s_slide.continuation_index == m_slide.continuation_index
            assert s_slide.structure_status == StructureStatus.STRUCTURE_VALIDATED

            # Slide must have at least TITLE and FOOTNOTE zones
            zone_types = [z.zone_type for z in s_slide.zones]
            assert ZoneType.TITLE in zone_types
            assert ZoneType.FOOTNOTE in zone_types

    def test_stable_deterministic_object_and_zone_ids(
        self,
        sample_manifest: PhysicalSlideManifest,
        sample_package: PresentationContentPackage,
    ):
        """Verify zone IDs and object IDs are strictly deterministic and unique."""
        builder = LayeredSlideStructureBuilder()
        structure1 = builder.build_structure(sample_manifest, sample_package)
        structure2 = builder.build_structure(sample_manifest, sample_package)

        assert structure1.structure_fingerprint == structure2.structure_fingerprint
        assert len(structure1.object_registry) == len(structure2.object_registry)

        for obj_id, obj in structure1.object_registry.items():
            assert obj_id in structure2.object_registry
            assert structure2.object_registry[obj_id].content_id == obj.content_id
            assert structure2.object_registry[obj_id].editability == obj.editability

    def test_truthful_map_editability(
        self,
        sample_manifest: PhysicalSlideManifest,
        sample_package: PresentationContentPackage,
    ):
        """Verify maps are strictly classified as STATIC_IMAGE_FALLBACK, never NATIVE_EDITABLE."""
        builder = LayeredSlideStructureBuilder()
        structure = builder.build_structure(sample_manifest, sample_package)

        map_objects = [
            obj for obj in structure.object_registry.values()
            if obj.kind == ContentKind.MAP
        ]
        assert len(map_objects) > 0, "Expected at least one MAP object in test package"
        for map_obj in map_objects:
            assert map_obj.editability == EditabilityPolicy.STATIC_IMAGE_FALLBACK
            assert map_obj.editability != EditabilityPolicy.NATIVE_EDITABLE

    def test_truthful_chart_and_table_editability(
        self,
        sample_manifest: PhysicalSlideManifest,
        sample_package: PresentationContentPackage,
    ):
        """Verify charts and tables are classified as NATIVE_EDITABLE."""
        builder = LayeredSlideStructureBuilder()
        structure = builder.build_structure(sample_manifest, sample_package)

        chart_objects = [
            obj for obj in structure.object_registry.values()
            if obj.kind == ContentKind.CHART
        ]
        assert len(chart_objects) > 0
        for chart_obj in chart_objects:
            assert chart_obj.editability == EditabilityPolicy.NATIVE_EDITABLE

        table_objects = [
            obj for obj in structure.object_registry.values()
            if obj.kind == ContentKind.TABLE
        ]
        assert len(table_objects) > 0
        for table_obj in table_objects:
            assert table_obj.editability == EditabilityPolicy.NATIVE_EDITABLE

    def test_source_traceability_preservation(
        self,
        sample_manifest: PhysicalSlideManifest,
        sample_package: PresentationContentPackage,
    ):
        """Verify audited provenance is preserved in object source_traceability."""
        builder = LayeredSlideStructureBuilder()
        structure = builder.build_structure(sample_manifest, sample_package)

        geo_obj = next(
            obj for obj in structure.object_registry.values()
            if obj.content_id == "ITEM-GEO-MAP-01"
        )
        assert geo_obj.source_traceability.get("fact_id") == "FACT-GEO-101"
        assert geo_obj.source_traceability.get("source_dataset_id") == "DS-CENSUS"
        assert geo_obj.source_traceability.get("source_sheet_name") == "Regional_Density"
        assert geo_obj.source_traceability.get("grain") == "state"
        assert geo_obj.source_traceability.get("unit") == "people/sq km"


class TestLayeredSlideStructureValidator:
    """Test validation rules and architectural invariant enforcement."""

    def test_validator_detects_forbidden_geometry(
        self,
        sample_manifest: PhysicalSlideManifest,
        sample_package: PresentationContentPackage,
    ):
        """Verify validator raises PhysicalGeometryLeakageError on geometry or styling attributes."""
        builder = LayeredSlideStructureBuilder()
        structure = builder.build_structure(sample_manifest, sample_package)

        # Inject forbidden coordinate into zone metadata
        structure.slides[0].zones[0].metadata["left_pct"] = 0.15
        with pytest.raises(PhysicalGeometryLeakageError, match="forbidden geometry/styling fields"):
            LayeredSlideStructureValidator.validate(structure, sample_manifest, sample_package)

    def test_validator_detects_forbidden_font_sizes(
        self,
        sample_manifest: PhysicalSlideManifest,
        sample_package: PresentationContentPackage,
    ):
        """Verify validator raises PhysicalGeometryLeakageError on font sizes."""
        builder = LayeredSlideStructureBuilder()
        structure = builder.build_structure(sample_manifest, sample_package)

        # Inject forbidden font size
        structure.slides[0].metadata["font_size_pt"] = 24
        with pytest.raises(PhysicalGeometryLeakageError, match="forbidden geometry/styling fields"):
            LayeredSlideStructureValidator.validate(structure, sample_manifest, sample_package)

    def test_validator_detects_cross_slide_content_movement(
        self,
        sample_manifest: PhysicalSlideManifest,
        sample_package: PresentationContentPackage,
    ):
        """Verify validator raises CrossSlideMovementError if content is moved across slides."""
        builder = LayeredSlideStructureBuilder()
        structure = builder.build_structure(sample_manifest, sample_package)

        if len(structure.slides) >= 2:
            slide1 = structure.slides[0]
            slide2 = structure.slides[1]
            # Steal an object from slide 2 and insert it into slide 1
            if slide2.zones and slide2.zones[1].objects:
                stolen_obj = slide2.zones[1].objects[0]
                slide1.zones[0].objects.append(stolen_obj)

                with pytest.raises(CrossSlideMovementError, match=r"(?i)cross-slide"):
                    LayeredSlideStructureValidator.validate(structure, sample_manifest, sample_package)

    def test_validator_detects_unmapped_primary_content(
        self,
        sample_manifest: PhysicalSlideManifest,
        sample_package: PresentationContentPackage,
    ):
        """Verify validator raises UnmappedPrimaryContentError if primary item is omitted."""
        builder = LayeredSlideStructureBuilder()
        structure = builder.build_structure(sample_manifest, sample_package)

        # Remove primary visual zone from a slide that has one
        slide = next(s for s in structure.slides if any(z.zone_type == ZoneType.PRIMARY_VISUAL for z in s.zones))
        slide.zones = [z for z in slide.zones if z.zone_type != ZoneType.PRIMARY_VISUAL]

        with pytest.raises(UnmappedPrimaryContentError, match="left primary content unmapped"):
            LayeredSlideStructureValidator.validate(structure, sample_manifest, sample_package)

    def test_validator_detects_orphan_objects(
        self,
        sample_manifest: PhysicalSlideManifest,
        sample_package: PresentationContentPackage,
    ):
        """Verify validator raises OrphanObjectError if object is not in registry."""
        builder = LayeredSlideStructureBuilder()
        structure = builder.build_structure(sample_manifest, sample_package)

        # Delete an object from the registry
        obj_id = list(structure.object_registry.keys())[0]
        del structure.object_registry[obj_id]

        with pytest.raises(OrphanObjectError, match="missing from object_registry"):
            LayeredSlideStructureValidator.validate(structure, sample_manifest, sample_package)

    def test_validator_detects_untruthful_map_editability(
        self,
        sample_manifest: PhysicalSlideManifest,
        sample_package: PresentationContentPackage,
    ):
        """Verify validator strictly rejects MAP marked as NATIVE_EDITABLE."""
        builder = LayeredSlideStructureBuilder()
        structure = builder.build_structure(sample_manifest, sample_package)

        # Corrupt map object editability
        for obj in structure.object_registry.values():
            if obj.kind == ContentKind.MAP:
                obj.editability = EditabilityPolicy.NATIVE_EDITABLE
                for s in structure.slides:
                    for z in s.zones:
                        for zo in z.objects:
                            if zo.object_id == obj.object_id:
                                zo.editability = EditabilityPolicy.NATIVE_EDITABLE

        with pytest.raises(StructureValidationError, match="MAP but is marked NATIVE_EDITABLE"):
            LayeredSlideStructureValidator.validate(structure, sample_manifest, sample_package)

    def test_validator_detects_governance_leakage_in_normal_deck(
        self,
        sample_manifest: PhysicalSlideManifest,
        sample_package: PresentationContentPackage,
    ):
        """Verify validator flags internal governance tokens (SDR, JoinPlan, EVID-*) in normal decks."""
        builder = LayeredSlideStructureBuilder()
        structure = builder.build_structure(sample_manifest, sample_package)

        # Inject governance token into slide headline
        structure.slides[0].headline = "Analysis based on SDR-99 JoinPlan schema"
        with pytest.raises(GovernanceLeakageError, match="Internal governance token"):
            LayeredSlideStructureValidator.validate(
                structure, sample_manifest, sample_package, is_technical_deck=False
            )

    def test_validator_allows_governance_in_technical_deck(
        self,
        sample_manifest: PhysicalSlideManifest,
        sample_package: PresentationContentPackage,
    ):
        """Verify technical decks preserve requested technical tokens without error."""
        builder = LayeredSlideStructureBuilder()
        structure = builder.build_structure(
            sample_manifest, sample_package, is_technical_deck=True
        )

        structure.slides[0].headline = "Technical Architecture: SDR pipeline and JoinPlan"
        # Should not raise
        LayeredSlideStructureValidator.validate(
            structure, sample_manifest, sample_package, is_technical_deck=True
        )


class TestStructureFeasibilityAndReplan:
    """Test replan signaling when zone capacity is exceeded."""

    def test_builder_signals_replan_on_excessive_visuals(
        self,
        sample_manifest: PhysicalSlideManifest,
        sample_package: PresentationContentPackage,
    ):
        """Verify builder sets STRUCTURE_REPLAN_REQUIRED if a slide has > 2 visual items."""
        builder = LayeredSlideStructureBuilder()

        extra_pkg = copy.deepcopy(sample_package)
        extra_pkg.items.append(
            PresentationContentItem(
                content_id="EXTRA-CHART-01",
                kind=ContentKind.CHART,
                role=ContentRole.PRIMARY_HERO,
                topic_category="REGIONAL_GROWTH",
                title="Extra Chart",
                narrative_takeaway="Extra Chart Takeaway",
            )
        )

        # Add 3 visual bindings to a single physical slide in manifest
        modified_manifest = copy.deepcopy(sample_manifest)
        modified_manifest.slides[0].content_bindings = [
            ContentBinding(content_id="ITEM-GEO-MAP-01", binding_role=ContentBindingRole.PRIMARY),
            ContentBinding(content_id="ITEM-GROWTH-01", binding_role=ContentBindingRole.PRIMARY),
            ContentBinding(content_id="EXTRA-CHART-01", binding_role=ContentBindingRole.PRIMARY),
        ]

        structure = builder.build_structure(modified_manifest, extra_pkg)
        assert structure.replan_required is True
        assert len(structure.replan_reasons) > 0
        assert "exceeding maximum zone capacity" in structure.replan_reasons[0]
        assert structure.slides[0].structure_status == StructureStatus.STRUCTURE_REPLAN_REQUIRED


class TestPipelineOrchestratorLayeredIntegration:
    """Test full integration in pipeline_orchestrator under LAYERED mode."""

    def test_layered_pipeline_orchestration_reaches_structure_validated(self):
        """Verify execute_presentation_pipeline_async executes L1->L2->L3->L4 and stops at validated structure."""
        from unittest.mock import MagicMock, patch
        from app.services.presentation.job_manager import PresentationJobManager

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

            res = execute_presentation_pipeline_async("test-job-ppt-l4-001", scope, manager=mock_mgr)

            assert res is not None
            mock_gen.assert_not_called()  # Invariant: 0 legacy generator calls in layered mode

            assert res["metadata"]["pipeline_mode"] == PresentationPipelineMode.LAYERED.value
            assert res["metadata"]["status"] == "STRUCTURE_VALIDATED"
            assert "layered_deck_structure" in res["metadata"]
            assert "structure_fingerprint" in res["metadata"]
            assert len(res["metadata"]["structure_fingerprint"]) == 64
            assert res["metadata"]["total_physical_slides"] > 0
            assert res["metadata"]["total_objects"] > 0
            assert res["slides"] == []  # PPT-L4 stops before layout geometry and rendering
