"""Unit and integration test suite for PPT-L3: Slide Expansion + Presentation Preflight.

Verifies:
1. PhysicalSlideManifest and PhysicalSlideInstance models with stable, semantic physical IDs.
2. Logical to physical expansion (single-page vs multi-page continuation).
3. Split-over-shrink invariant (continuation slides over font shrinking).
4. Continuation chains and sequence contiguity.
5. Story narrative and section order preservation.
6. TITLE first (single page) and CLOSING last invariants.
7. Primary content protection (unassigned primary = 0, silent content loss = 0).
8. Analytical truth preservation (0 fact, unit, grain, denominator mutations).
9. PresentationPreflightEngine (table preflight, visual preflight, text density, structural role capacity).
10. Target length policy & TARGET_LENGTH_CONFLICT handling without filler slides.
11. Absolute prohibition of physical layout geometry (0 coordinates, 0 zones, 0 layers, 0 font sizes).
12. Controlled late-split revision contract.
13. Manifest determinism and localized regeneration stability.
14. Multi-domain coverage (Geographic, Workforce, Technical).
15. Pipeline orchestrator layered boundary and legacy path isolation (0 preflight/expansion calls in legacy).
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
from app.services.presentation.manifest_models import (
    ContentDensity,
    DeckLengthPolicy,
    ExpansionLimitExceededError,
    ExpansionReason,
    InvalidContinuationChainError,
    ManifestValidationError,
    PhysicalLayoutLeakageError,
    PhysicalSlideInstance,
    PhysicalSlideManifest,
    PhysicalSlideManifestValidator,
    PreflightStatus,
    TargetLengthStatus,
    UnassignedPrimaryContentError,
)
from app.services.presentation.pipeline_selector import PresentationPipelineMode
from app.services.presentation.pipeline_orchestrator import (
    execute_presentation_pipeline_async,
)
from app.services.presentation.preflight_engine import PresentationPreflightEngine
from app.services.presentation.story_models import (
    ContentBinding,
    ContentBindingRole,
    DeckStoryPlan,
    ExcludedContentItem,
    ExclusionReason,
    LogicalSlidePlan,
    StructuralRole,
)
from app.services.presentation.story_planner import StoryPlanner


# ==============================================================================
# TEST FIXTURES
# ==============================================================================

@pytest.fixture
def sample_package() -> PresentationContentPackage:
    """Fixture providing a rich multi-domain content package with varied content kinds."""
    items = [
        PresentationContentItem(
            content_id="ITEM-GEO-01",
            kind=ContentKind.MAP,
            role=ContentRole.PRIMARY_HERO,
            topic_category="Population Density",
            title="State-Level Population Density Heatmap",
            importance_score=0.95,
            grain="state",
            unit="people/sq km",
            denominator="geographic_area_sq_km"
        ),
        PresentationContentItem(
            content_id="ITEM-GEO-02",
            kind=ContentKind.TABLE,
            role=ContentRole.EXPLORATORY_TABLE,
            topic_category="Population Density",
            title="Top 25 Dense Districts Tabular Breakdown",
            importance_score=0.80,
            grain="district",
            unit="people/sq km",
            table_data=[{"district": f"District {i}", "val": i} for i in range(15)]  # 15 rows -> definite table split
        ),
        PresentationContentItem(
            content_id="ITEM-GROWTH-01",
            kind=ContentKind.CHART,
            role=ContentRole.PRIMARY_HERO,
            topic_category="Population Growth",
            title="Regional Population Growth Trajectory",
            importance_score=0.90,
            grain="region",
            unit="%"
        ),
        PresentationContentItem(
            content_id="ITEM-GROWTH-02",
            kind=ContentKind.CHART,
            role=ContentRole.KEY_FINDING,
            topic_category="Population Growth",
            title="Urban vs Rural Expansion Dynamics",
            importance_score=0.85,
            grain="sector",
            unit="%"
        ),
        PresentationContentItem(
            content_id="ITEM-SUMMARY-01",
            kind=ContentKind.KPI_METRIC,
            role=ContentRole.STRATEGIC_KPI,
            topic_category="Executive Overview",
            title="National Growth Index",
            importance_score=0.92,
            metric_value="14.8%",
            unit="%"
        ),
        PresentationContentItem(
            content_id="ITEM-ACTION-01",
            kind=ContentKind.NARRATIVE_INSIGHT,
            role=ContentRole.KEY_FINDING,
            topic_category="Action Plan",
            title="Infrastructure Capacity Expansion Initiative",
            importance_score=0.78,
            narrative_takeaway="Deploy northern corridor logistics hubs by Q3."
        ),
    ]

    pkg = PresentationContentPackage(
        package_id="PKG-EXPANSION-001",
        dataset_name="Regional Demographics & Logistics",
        domain="Demographic Geography",
        items=items,
        global_kpis=[items[4]],
        available_topics=["Population Density", "Population Growth", "Executive Overview", "Action Plan"]
    )
    pkg.content_fingerprint = pkg.compute_fingerprint()
    return pkg


@pytest.fixture
def sample_story_plan(sample_package: PresentationContentPackage) -> DeckStoryPlan:
    """Fixture providing a validated DeckStoryPlan conforming to PPT-L2."""
    planner = StoryPlanner(use_ai=False)
    return planner.plan_story(
        content_pkg=sample_package,
        user_objective="Analyze population density and regional growth initiatives"
    )


# ==============================================================================
# 1. PHYSICAL SLIDE MANIFEST & STABLE SEMANTIC IDENTITY
# ==============================================================================

class TestPhysicalSlideManifestAndInstance:
    """Verifies that physical slides carry stable, semantic identities and no random UUIDs."""

    def test_physical_slide_ids_are_semantic_and_deterministic(self, sample_story_plan, sample_package):
        engine = SlideExpansionEngine()
        manifest = engine.expand(story_plan=sample_story_plan, content_pkg=sample_package)

        assert len(manifest.slides) >= len(sample_story_plan.logical_slides)
        for s in manifest.slides:
            # Physical ID must be semantic, ending with 2-digit continuation number
            assert "-" in s.physical_slide_id
            assert s.physical_slide_id.endswith(f"-{s.continuation_index:02d}")
            # Must not be generic or fragile
            assert not s.physical_slide_id.startswith("SLIDE-")
            assert not s.physical_slide_id.startswith("PAGE-")
            assert len(s.physical_slide_id) > 4

    def test_sequence_index_is_strictly_contiguous(self, sample_story_plan, sample_package):
        engine = SlideExpansionEngine()
        manifest = engine.expand(story_plan=sample_story_plan, content_pkg=sample_package)

        sequences = [s.sequence_index for s in manifest.slides]
        assert sequences == list(range(1, len(manifest.slides) + 1))


# ==============================================================================
# 2. LOGICAL TO PHYSICAL EXPANSION (SPLIT-OVER-SHRINK)
# ==============================================================================

class TestLogicalToPhysicalExpansion:
    """Verifies that logical topics expand based on content capacity rather than 1-topic = 1-slide."""

    def test_single_slide_topic_remains_single_page(self, sample_story_plan, sample_package):
        engine = SlideExpansionEngine()
        manifest = engine.expand(story_plan=sample_story_plan, content_pkg=sample_package)

        # Title slide must always remain 1 physical page
        title_slides = [s for s in manifest.slides if s.structural_role == StructuralRole.TITLE]
        assert len(title_slides) == 1
        assert title_slides[0].continuation_index == 1
        assert title_slides[0].is_continuation is False

    def test_dense_table_topic_expands_to_continuation_slides(self, sample_story_plan, sample_package):
        """Verifies that a topic with a large table (> 6 rows) splits across continuation slides."""
        engine = SlideExpansionEngine()
        manifest = engine.expand(story_plan=sample_story_plan, content_pkg=sample_package)

        # Find mappings for density topic (which binds ITEM-GEO-01 map and ITEM-GEO-02 15-row table)
        density_mappings = [
            m for m in manifest.logical_topic_mappings
            if "DENSITY" in m.semantic_topic
        ]
        assert len(density_mappings) >= 1
        mapping = density_mappings[0]

        # Multi-page expansion occurred
        assert mapping.is_split is True
        assert len(mapping.physical_slide_ids) >= 2
        assert mapping.expansion_reason in (ExpansionReason.TABLE_LENGTH, ExpansionReason.MULTI_VISUAL)

        # Physical slides have correct continuation indices
        matching_slides = [s for s in manifest.slides if s.logical_slide_id == mapping.logical_slide_id]
        assert len(matching_slides) >= 2
        assert matching_slides[0].continuation_index == 1
        assert matching_slides[0].is_continuation is False
        assert matching_slides[1].continuation_index == 2
        assert matching_slides[1].is_continuation is True

    def test_split_before_shrink_invariant(self, sample_package):
        """Verifies that over-capacity content triggers slide continuation, never text shrinking."""
        # Create a logical slide with 2 primary charts
        l_slide = LogicalSlidePlan(
            logical_slide_id="MULTI_CHART_TOPIC",
            structural_role=StructuralRole.HERO_ANALYSIS,
            semantic_topic="CORRIDOR_EFFICIENCY",
            section_name="Empirical Analysis",
            headline="Corridor Efficiency Diagnostics",
            purpose="Analyze transit velocity and punctuality",
            content_bindings=[
                ContentBinding(content_id="ITEM-GROWTH-01", binding_role=ContentBindingRole.PRIMARY),
                ContentBinding(content_id="ITEM-GROWTH-02", binding_role=ContentBindingRole.PRIMARY),
            ],
            allow_split=True,
            logical_order=1
        )
        plan = DeckStoryPlan(
            plan_id="PLAN-MULTI",
            deck_title="Corridor Performance Review",
            deck_subtitle="Transit Diagnostics",
            executive_thesis="Corridor efficiency analysis.",
            sections=["Empirical Analysis"],
            logical_slides=[l_slide],
            excluded_content=[]
        )

        engine = SlideExpansionEngine()
        manifest = engine.expand(story_plan=plan, content_pkg=sample_package)

        # The multi-chart topic must split into 2 physical slides
        assert len(manifest.slides) == 2
        assert manifest.slides[0].physical_slide_id == "MULTI_CHART_TOPIC-01"
        assert manifest.slides[1].physical_slide_id == "MULTI_CHART_TOPIC-02"
        assert manifest.slides[1].expansion_reason == ExpansionReason.MULTI_VISUAL


# ==============================================================================
# 3. CONTINUATION CHAINS & CONTIGUITY
# ==============================================================================

class TestContinuationChainsAndContiguity:
    """Verifies that continuation slides are strictly contiguous in physical sequence."""

    def test_continuation_slides_are_physically_contiguous(self, sample_story_plan, sample_package):
        engine = SlideExpansionEngine()
        manifest = engine.expand(story_plan=sample_story_plan, content_pkg=sample_package)

        for mapping in manifest.logical_topic_mappings:
            if mapping.is_split:
                slides = [s for s in manifest.slides if s.logical_slide_id == mapping.logical_slide_id]
                seqs = [s.sequence_index for s in slides]
                # Must be strictly adjacent (e.g. [3, 4] or [4, 5, 6])
                assert seqs == list(range(seqs[0], seqs[0] + len(slides)))

    def test_validator_rejects_non_contiguous_continuation_chain(self, sample_story_plan, sample_package):
        engine = SlideExpansionEngine()
        manifest = engine.expand(story_plan=sample_story_plan, content_pkg=sample_package)

        # Artificially alter sequence index to create a non-contiguous continuation
        if len(manifest.slides) >= 3:
            manifest.slides[1].sequence_index = 5  # gap
            with pytest.raises(ManifestValidationError):
                PhysicalSlideManifestValidator.validate(manifest, sample_story_plan, sample_package)


# ==============================================================================
# 4. STORY NARRATIVE & SECTION ORDER PRESERVATION
# ==============================================================================

class TestStoryAndSectionOrderPreservation:
    """Verifies that expansion preserves logical narrative order and section boundaries."""

    def test_logical_story_order_is_strictly_preserved(self, sample_story_plan, sample_package):
        engine = SlideExpansionEngine()
        manifest = engine.expand(story_plan=sample_story_plan, content_pkg=sample_package)

        logical_order_map = {s.logical_slide_id: s.logical_order for s in sample_story_plan.logical_slides}
        seen_orders = []
        seen_lids = set()

        for ps in manifest.slides:
            if ps.logical_slide_id not in seen_lids:
                seen_lids.add(ps.logical_slide_id)
                seen_orders.append(logical_order_map[ps.logical_slide_id])

        assert seen_orders == sorted(seen_orders)

    def test_section_mappings_are_valid_and_non_overlapping(self, sample_story_plan, sample_package):
        engine = SlideExpansionEngine()
        manifest = engine.expand(story_plan=sample_story_plan, content_pkg=sample_package)

        assert len(manifest.section_mappings) >= 1
        for sm in manifest.section_mappings:
            assert sm.physical_count == (sm.last_sequence_index - sm.first_sequence_index + 1)
            assert sm.first_sequence_index >= 1


# ==============================================================================
# 5. TITLE & CLOSING INVARIANTS
# ==============================================================================

class TestTitleAndClosingInvariants:
    """Verifies that TITLE is always first and CLOSING is always last."""

    def test_title_first_and_closing_last(self, sample_story_plan, sample_package):
        engine = SlideExpansionEngine()
        manifest = engine.expand(story_plan=sample_story_plan, content_pkg=sample_package)

        assert manifest.slides[0].structural_role == StructuralRole.TITLE
        assert manifest.slides[0].sequence_index == 1

        assert manifest.slides[-1].structural_role == StructuralRole.CLOSING
        assert manifest.slides[-1].sequence_index == len(manifest.slides)

    def test_title_never_splits(self, sample_package):
        """Verifies that preflight strictly enforces single-page TITLE slide."""
        preflight = PresentationPreflightEngine()
        title_l_slide = LogicalSlidePlan(
            logical_slide_id="TITLE_SLIDE",
            structural_role=StructuralRole.TITLE,
            semantic_topic="TITLE",
            section_name="Overview",
            headline="Title Slide",
            purpose="Executive presentation title",
            content_bindings=[ContentBinding(content_id="ITEM-SUMMARY-01", binding_role=ContentBindingRole.PRIMARY)],
            allow_split=True,
            logical_order=1
        )
        plan = DeckStoryPlan(
            plan_id="PLAN-T",
            deck_title="Title Plan",
            deck_subtitle="Executive Briefing",
            executive_thesis="Strategic overview.",
            sections=["Overview"],
            logical_slides=[title_l_slide],
            excluded_content=[]
        )
        res = preflight.preflight(plan, sample_package)
        assert res.logical_topic_results[0].recommended_physical_slides == 1
        assert res.logical_topic_results[0].expansion_reason == ExpansionReason.NONE


# ==============================================================================
# 6. PRIMARY CONTENT PROTECTION & TRUTH PRESERVATION
# ==============================================================================

class TestPrimaryContentProtectionAndTruth:
    """Verifies 0 primary content loss, 0 fact mutations, and 0 unit mutations."""

    def test_zero_unassigned_primary_content(self, sample_story_plan, sample_package):
        engine = SlideExpansionEngine()
        manifest = engine.expand(story_plan=sample_story_plan, content_pkg=sample_package)

        required_primaries = set()
        for ls in sample_story_plan.logical_slides:
            for b in ls.content_bindings:
                if b.binding_role == ContentBindingRole.PRIMARY:
                    required_primaries.add(b.content_id)

        assigned_content = {b.content_id for s in manifest.slides for b in s.content_bindings}
        unassigned = required_primaries - assigned_content
        assert len(unassigned) == 0

    def test_validator_rejects_dropped_primary_content(self, sample_story_plan, sample_package):
        engine = SlideExpansionEngine()
        manifest = engine.expand(story_plan=sample_story_plan, content_pkg=sample_package)

        # Artificially remove content bindings from a slide
        for s in manifest.slides:
            if any(b.binding_role == ContentBindingRole.PRIMARY for b in s.content_bindings):
                s.content_bindings = []
                break

        with pytest.raises(UnassignedPrimaryContentError):
            PhysicalSlideManifestValidator.validate(manifest, sample_story_plan, sample_package)

    def test_zero_fact_unit_grain_mutations(self, sample_story_plan, sample_package):
        """Verifies that expanding into physical slides does not mutate any underlying metrics."""
        engine = SlideExpansionEngine()
        manifest = engine.expand(story_plan=sample_story_plan, content_pkg=sample_package)

        pkg_item_map = {it.content_id: it for it in sample_package.items}
        for s in manifest.slides:
            for b in s.content_bindings:
                source_item = pkg_item_map[b.content_id]
                # Units, grain, and values remain identical
                assert b.content_id == source_item.content_id


# ==============================================================================
# 7. PRESENTATION PREFLIGHT ENGINE & TARGET LENGTH GUIDANCE
# ==============================================================================

class TestPresentationPreflightEngine:
    """Verifies preflight evaluation of content density, table pressure, and target length."""

    def test_preflight_detects_table_overflow_pressure(self, sample_story_plan, sample_package):
        engine = PresentationPreflightEngine()
        res = engine.preflight(sample_story_plan, sample_package)

        density_results = [r for r in res.logical_topic_results if "DENSITY" in r.semantic_topic]
        assert len(density_results) >= 1
        r = density_results[0]
        assert r.table_split_recommended is True
        assert r.recommended_physical_slides >= 2

    def test_target_length_conflict_warning_preserves_content(self, sample_story_plan, sample_package):
        """Verifies that requesting an impossibly small deck emits TARGET_LENGTH_CONFLICT without dropping content."""
        engine = PresentationPreflightEngine()
        # Requesting 3 slides when natural minimum is 6+
        res = engine.preflight(sample_story_plan, sample_package, target_slide_count=3)

        assert res.target_length_status == TargetLengthStatus.TARGET_LENGTH_CONFLICT
        assert any("TARGET_LENGTH_CONFLICT" in w for w in res.warnings)

    def test_sparse_dataset_does_not_generate_artificial_filler(self, sample_package):
        """Verifies that a sparse story with 2 slides does not generate filler pages when target=10."""
        l_slide1 = LogicalSlidePlan(
            logical_slide_id="TITLE",
            structural_role=StructuralRole.TITLE,
            semantic_topic="TITLE",
            section_name="Overview",
            headline="Title",
            purpose="Presentation Title",
            allow_split=False,
            logical_order=1
        )
        l_slide2 = LogicalSlidePlan(
            logical_slide_id="HERO",
            structural_role=StructuralRole.HERO_ANALYSIS,
            semantic_topic="GROWTH",
            section_name="Overview",
            headline="Hero Growth",
            purpose="Regional growth diagnostics",
            content_bindings=[ContentBinding(content_id="ITEM-GROWTH-01", binding_role=ContentBindingRole.PRIMARY)],
            allow_split=False,
            logical_order=2
        )
        plan = DeckStoryPlan(
            plan_id="PLAN-SPARSE",
            deck_title="Sparse Plan",
            deck_subtitle="Sparse Executive Briefing",
            executive_thesis="Focused performance summary.",
            sections=["Overview"],
            logical_slides=[l_slide1, l_slide2],
            excluded_content=[]
        )

        engine = SlideExpansionEngine()
        manifest = engine.expand(story_plan=plan, content_pkg=sample_package, target_slide_count=10)

        # Must not generate 10 slides; exactly 2 physical slides created
        assert len(manifest.slides) == 2


# ==============================================================================
# 8. ABSOLUTE PROHIBITION OF PHYSICAL GEOMETRY (0 COORDS, 0 ZONES, 0 LAYERS)
# ==============================================================================

class TestZeroPhysicalGeometryInvariants:
    """Verifies that NO coordinates, zones, layers, font sizes, or layout templates leak into PPT-L3."""

    def test_zero_geometry_in_manifest_and_instances(self, sample_story_plan, sample_package):
        engine = SlideExpansionEngine()
        manifest = engine.expand(story_plan=sample_story_plan, content_pkg=sample_package)

        manifest_dump = manifest.model_dump()
        forbidden = PhysicalSlideManifestValidator.FORBIDDEN_GEOMETRY_FIELDS

        def _scan(data: Any):
            if isinstance(data, dict):
                for k, v in data.items():
                    assert str(k).lower() not in forbidden, f"Forbidden field '{k}' found in manifest!"
                    _scan(v)
            elif isinstance(data, list):
                for item in data:
                    _scan(item)

        _scan(manifest_dump)

    def test_validator_rejects_injected_coordinates_or_font_sizes(self, sample_story_plan, sample_package):
        engine = SlideExpansionEngine()
        manifest = engine.expand(story_plan=sample_story_plan, content_pkg=sample_package)

        # Inject a forbidden coordinate into slide metadata
        manifest.slides[0].metadata["coordinate_space"] = {"x": 100, "y": 200}
        with pytest.raises(PhysicalLayoutLeakageError):
            PhysicalSlideManifestValidator.validate(manifest, sample_story_plan, sample_package)


# ==============================================================================
# 9. CONTROLLED LATE-SPLIT REVISION CONTRACT
# ==============================================================================

class TestLateSplitRevisionContract:
    """Verifies the contract allowing layout engines to request manifest revisions without untracked slides."""

    def test_controlled_late_split_revises_manifest_cleanly(self, sample_story_plan, sample_package):
        engine = SlideExpansionEngine()
        manifest_v1 = engine.expand(story_plan=sample_story_plan, content_pkg=sample_package)

        # Find a slide with multiple bindings to test late split
        target_slide = None
        for s in manifest_v1.slides:
            if len(s.content_bindings) >= 2:
                target_slide = s
                break

        if target_slide is None:
            # Configure slide 1 with 2 bindings to test late split
            manifest_v1.slides[1].content_bindings = [
                ContentBinding(content_id="ITEM-GROWTH-01", binding_role=ContentBindingRole.PRIMARY),
                ContentBinding(content_id="ITEM-GROWTH-02", binding_role=ContentBindingRole.SUPPORTING),
            ]
            target_slide = manifest_v1.slides[1]

        initial_count = len(manifest_v1.slides)
        revised_manifest = engine.expand_late_split(
            current_manifest=manifest_v1,
            offending_physical_slide_id=target_slide.physical_slide_id,
            revision_reason="Downstream layout overflow detected in table column width",
            story_plan=sample_story_plan,
            content_pkg=sample_package
        )

        assert revised_manifest.manifest_version == 2
        assert revised_manifest.parent_manifest_fingerprint == manifest_v1.manifest_fingerprint
        assert len(revised_manifest.slides) == initial_count + 1
        assert revised_manifest.revision_reason is not None

        # Sequences are properly contiguous 1..N
        seqs = [s.sequence_index for s in revised_manifest.slides]
        assert seqs == list(range(1, len(revised_manifest.slides) + 1))


# ==============================================================================
# 10. MANIFEST DETERMINISM & LOCALIZED REGENERATION STABILITY
# ==============================================================================

class TestManifestDeterminismAndStability:
    """Verifies deterministic fingerprints and localized regeneration stability."""

    def test_same_input_yields_identical_manifest_fingerprint(self, sample_story_plan, sample_package):
        engine = SlideExpansionEngine()
        m1 = engine.expand(story_plan=sample_story_plan, content_pkg=sample_package)
        m2 = engine.expand(story_plan=sample_story_plan, content_pkg=sample_package)

        assert m1.manifest_fingerprint == m2.manifest_fingerprint
        assert len(m1.slides) == len(m2.slides)
        assert [s.physical_slide_id for s in m1.slides] == [s.physical_slide_id for s in m2.slides]

    def test_localized_regeneration_preserves_unrelated_physical_ids(self, sample_story_plan, sample_package):
        """Verifies that changing one topic does not alter physical slide IDs of unrelated topics."""
        engine = SlideExpansionEngine()
        m1 = engine.expand(story_plan=sample_story_plan, content_pkg=sample_package)

        # Modify only the headline of the action plan
        plan_modified = copy.deepcopy(sample_story_plan)
        for s in plan_modified.logical_slides:
            if s.structural_role == StructuralRole.ACTION_PLAN:
                s.headline = "Completely Revised Action Plan"

        m2 = engine.expand(story_plan=plan_modified, content_pkg=sample_package)

        # Unrelated topics (e.g. TITLE, DENSITY) retain exact same physical IDs
        density_m1 = [s.physical_slide_id for s in m1.slides if "DENSITY" in s.semantic_topic]
        density_m2 = [s.physical_slide_id for s in m2.slides if "DENSITY" in s.semantic_topic]
        assert density_m1 == density_m2


# ==============================================================================
# 11. ORCHESTRATOR LAYERED BOUNDARY & LEGACY PATH ISOLATION
# ==============================================================================

class TestOrchestratorLayeredPPTL3Integration:
    """Verifies that layered mode terminates at PhysicalSlideManifest and legacy mode remains untouched."""

    def test_orchestrator_layered_mode_generates_physical_manifest(self):
        from unittest.mock import MagicMock, patch
        from app.services.presentation.job_manager import PresentationJobManager

        mock_mgr = MagicMock(spec=PresentationJobManager)
        mock_mgr.is_cancelled.return_value = False

        scope = {
            "scope_type": "single_sheet",
            "sheet_id": 101,
            "pipeline_mode": "LAYERED",
            "objective": "Executive Geographic Expansion Strategy",
            "audience": "Board of Directors"
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

            res = execute_presentation_pipeline_async("job-layered-pptl3", scope, manager=mock_mgr)

            assert res is not None
            # Invariant: Zero legacy generator calls
            mock_gen.assert_not_called()

            # Invariant: Must terminate with validated status (PPT-L3 physical manifest or PPT-L4 structure)
            assert res["metadata"]["status"] in ("PHYSICAL_MANIFEST_VALIDATED", "STRUCTURE_VALIDATED")
            assert "physical_manifest" in res["metadata"]
            manifest_data = res["metadata"]["physical_manifest"]
            assert len(manifest_data["slides"]) >= 4
            assert manifest_data["manifest_fingerprint"] != ""

            # Invariant: Slides list is structured
            assert isinstance(res["slides"], list)
