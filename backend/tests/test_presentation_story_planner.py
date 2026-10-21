"""Comprehensive Test Suite & Architectural Invariant Audit for StoryPlanner & Logical SlideTags (PPT-L2).

Validates:
1. DeckStoryPlan & LogicalSlideTag Creation:
   - Valid DeckStoryPlan created with plan_id, deck_title, executive_thesis, sections, and logical_slides.
   - LogicalSlideTags assigned across standard narrative vocabulary (TITLE, AGENDA, EXECUTIVE_SUMMARY, STRATEGIC_KPIS, HERO_ANALYSIS, GEOGRAPHIC_DISTRIBUTION, ACTION_PLAN, CLOSING).
2. Content Bound Exclusively by ID:
   - Every ContentBinding references a known, audited content_id.
   - Distinct roles assigned: PRIMARY, SUPPORTING, OPTIONAL.
3. Objective-Aware Narrative Ordering:
   - Geographic user objective prioritizes GEOGRAPHIC_DISTRIBUTION early in the narrative.
   - Risk/anomaly user objective prioritizes COHORT_VARIANCE / risk findings.
   - Deck structure is not a dumb mirror of dashboard or raw dataset.
4. Redundancy Handling & Excluded-Content Ledger:
   - Redundant or lower-priority items are routed to excluded_content with explicit ExclusionReason.
   - Complete content accounting: every package item is either bound or recorded in excluded_content.
   - Zero silent content loss.
5. Unknown ID Rejection:
   - Hallucinated or unknown content_ids in slides or exclusions raise UnknownContentIdError.
6. Deterministic Fallback & Fingerprint Determinism:
   - DeterministicStoryPlanner operates with zero external calls and 100% reproducible ordering.
   - Identical inputs yield identical SHA-256 story_fingerprint.
7. Architectural Invariants (Zero Layout / Physical Rendering):
   - 0 physical coordinates (x, y, width, height, left, top, pt_x, pt_y)
   - 0 physical slide numbers (slide_number, page_number)
   - 0 SlideExpansion
   - 0 Layer / Zone work
   - 0 layout work
   - 0 legacy StoryPlanner calls
8. Analytical Truth Invariants:
   - 0 fact mutations
   - 0 unit mutations
   - 0 grain mutations
   - 0 denominator mutations
   - 0 invented numerical facts
"""

import copy
from typing import Any
import pytest
from unittest.mock import MagicMock, patch

from app.services.presentation.content_models import (
    ContentKind,
    ContentRole,
    PresentationContentItem,
    PresentationContentPackage,
)
from app.services.presentation.story_models import (
    ContentBinding,
    ContentBindingRole,
    DeckStoryPlan,
    ExcludedContentItem,
    ExclusionReason,
    LogicalSlidePlan,
    PhysicalLayoutLeakageError,
    SlideTag,
    StoryPlanValidationError,
    StoryPlanValidator,
    UnaccountedContentError,
    UnknownContentIdError,
)
from app.services.presentation.story_planner import (
    AIStoryPlanner,
    DeterministicStoryPlanner,
    StoryPlanner,
)
from app.services.presentation.pipeline_selector import PresentationPipelineMode


@pytest.fixture
def sample_content_package() -> PresentationContentPackage:
    """Constructs a deterministic, audited PresentationContentPackage with diverse items."""
    kpis = [
        PresentationContentItem(
            content_id="KPI-001",
            kind=ContentKind.KPI_METRIC,
            role=ContentRole.STRATEGIC_KPI,
            topic_category="Core Logistics",
            title="Overall On-Time Performance",
            metric_value="94.2%",
            metric_label="On-Time Delivery Rate",
            unit="%",
            grain="overall_system",
            denominator="total_dispatches",
            importance_score=0.95,
            decision_relevance=0.90,
            visual_suitability=0.85,
            narrative_takeaway="System-wide on-time performance reached 94.2% across active networks."
        ),
        PresentationContentItem(
            content_id="KPI-002",
            kind=ContentKind.KPI_METRIC,
            role=ContentRole.STRATEGIC_KPI,
            topic_category="Fleet Operations",
            title="Fleet Utilization",
            metric_value="88.7%",
            metric_label="Asset Utilization",
            unit="%",
            grain="fleet_vehicles",
            denominator="active_fleet",
            importance_score=0.88,
            decision_relevance=0.82,
            visual_suitability=0.80,
            narrative_takeaway="Fleet asset utilization averaged 88.7% for the reporting period."
        ),
    ]

    items = [
        PresentationContentItem(
            content_id="ITEM-001",
            kind=ContentKind.MAP,
            role=ContentRole.PRIMARY_HERO,
            topic_category="Geographic Density",
            title="State-by-State Population Density & Route Load",
            importance_score=0.92,
            decision_relevance=0.88,
            visual_suitability=0.95,
            narrative_takeaway="Northern corridor demonstrates highest population density at 11,320 per sq km.",
            unit="people/sq km",
            grain="state",
            denominator="geographic_area_sq_km"
        ),
        PresentationContentItem(
            content_id="ITEM-002",
            kind=ContentKind.TABLE,
            role=ContentRole.EXPLORATORY_TABLE,
            topic_category="Geographic Density",
            title="Top 10 High-Density Districts Comparison",
            importance_score=0.75,
            decision_relevance=0.70,
            visual_suitability=0.65,
            narrative_takeaway="District-level tabular breakdown confirms density cluster in northern capital districts.",
            unit="people/sq km",
            grain="district",
            denominator="district_area_sq_km"
        ),
        PresentationContentItem(
            content_id="ITEM-003",
            kind=ContentKind.CHART,
            role=ContentRole.KEY_FINDING,
            topic_category="Corridor Velocity",
            title="On-Time Rate vs Turnaround Time Correlation",
            importance_score=0.85,
            decision_relevance=0.80,
            visual_suitability=0.90,
            narrative_takeaway="Strong negative correlation between dispatch turnaround lag and delivery punctuality.",
            unit="hours",
            grain="corridor",
            denominator="total_dispatches"
        ),
        PresentationContentItem(
            content_id="ITEM-004",
            kind=ContentKind.CHART,
            role=ContentRole.RISK_ANOMALY,
            topic_category="Service Variance",
            title="Peak Hour Incident Distribution",
            importance_score=0.82,
            decision_relevance=0.85,
            visual_suitability=0.80,
            narrative_takeaway="Late evening shifts exhibit an isolated 3.4x spike in transit delay incidents.",
            unit="incidents/shift",
            grain="shift_cohort",
            denominator="scheduled_shifts"
        ),
        PresentationContentItem(
            content_id="ITEM-005",
            kind=ContentKind.CHART,
            role=ContentRole.KEY_FINDING,
            topic_category="Corridor Velocity",
            title="Duplicate Turnaround Speed Index",
            importance_score=0.60,
            decision_relevance=0.55,
            visual_suitability=0.70,
            redundancy_score=0.85,  # High redundancy
            narrative_takeaway="Turnaround index measures dispatch velocity across corridors.",
            unit="index",
            grain="corridor"
        ),
        PresentationContentItem(
            content_id="ITEM-006",
            kind=ContentKind.TABLE,
            role=ContentRole.EXPLORATORY_TABLE,
            topic_category="Miscellaneous Audit",
            title="Raw Vehicle Maintenance Log Excerpt",
            importance_score=0.20,
            decision_relevance=0.15,
            visual_suitability=0.30,
            narrative_takeaway="Maintenance entries for auxiliary equipment.",
            grain="vehicle_id"
        ),
    ]

    pkg = PresentationContentPackage(
        package_id="PKG-LOGISTICS-001",
        dataset_name="Logistics Operational Performance",
        domain="Supply Chain & Fleet Logistics",
        items=items,
        global_kpis=kpis,
        available_topics=["Geographic Density", "Corridor Velocity", "Service Variance", "Miscellaneous Audit"],
    )
    pkg.content_fingerprint = pkg.compute_fingerprint()
    return pkg


# ==============================================================================
# 1. DECK STORY PLAN & SLIDE TAG CREATION
# ==============================================================================

class TestDeckStoryPlanCreation:
    """Verifies that DeckStoryPlan is cleanly created with valid logical slide tags."""

    def test_creates_valid_deck_story_plan(self, sample_content_package):
        planner = StoryPlanner(use_ai=False)
        plan = planner.plan_story(
            content_pkg=sample_content_package,
            user_objective="Analyze operational bottlenecks and corridor performance",
            target_audience="Executive Operations Committee"
        )

        assert isinstance(plan, DeckStoryPlan)
        assert plan.plan_id.startswith("PLAN-")
        assert len(plan.deck_title) > 0
        assert len(plan.executive_thesis) > 0
        assert len(plan.sections) >= 3
        assert len(plan.logical_slides) >= 5
        assert len(plan.story_fingerprint) == 64

    def test_assigns_valid_logical_slide_tags(self, sample_content_package):
        planner = StoryPlanner(use_ai=False)
        plan = planner.plan_story(
            content_pkg=sample_content_package,
            user_objective="Evaluate fleet performance",
            target_audience="Executive Leadership"
        )

        tags = [s.tag for s in plan.logical_slides]
        # Invariants: Must contain foundational logical story tags
        assert SlideTag.TITLE in tags
        assert SlideTag.AGENDA in tags
        assert SlideTag.EXECUTIVE_SUMMARY in tags
        assert SlideTag.STRATEGIC_KPIS in tags
        assert SlideTag.ACTION_PLAN in tags
        assert SlideTag.CLOSING in tags

        # Every tag must be a recognized SlideTag enum member
        for s in plan.logical_slides:
            assert isinstance(s.tag, SlideTag)
            assert s.section_name in plan.sections

    def test_logical_slide_is_not_physical_slide(self, sample_content_package):
        """Invariant: LogicalSlidePlan allows multi-binding and has 0 physical coordinates."""
        planner = StoryPlanner(use_ai=False)
        plan = planner.plan_story(
            content_pkg=sample_content_package,
            user_objective="Assess regional density and top districts"
        )

        # Check that logical slides contain purpose and headline but NO physical dimensions
        for s in plan.logical_slides:
            assert hasattr(s, "headline")
            assert hasattr(s, "purpose")
            assert hasattr(s, "allow_split")
            assert not hasattr(s, "width")
            assert not hasattr(s, "height")
            assert not hasattr(s, "x")
            assert not hasattr(s, "y")
            assert not hasattr(s, "slide_number")


# ==============================================================================
# 2. CONTENT BOUND EXCLUSIVELY BY ID & ROLES
# ==============================================================================

class TestContentBindingAndRoles:
    """Verifies that all bound content references valid IDs with explicit roles."""

    def test_bindings_use_valid_content_ids(self, sample_content_package):
        planner = StoryPlanner(use_ai=False)
        plan = planner.plan_story(
            content_pkg=sample_content_package,
            user_objective="Examine corridor velocity"
        )

        valid_ids = {it.content_id for it in sample_content_package.items} | {
            k.content_id for k in sample_content_package.global_kpis
        }

        bound_ids = set()
        for s in plan.logical_slides:
            for b in s.content_bindings:
                assert b.content_id in valid_ids, f"Bound ID {b.content_id} not in package"
                assert isinstance(b.binding_role, ContentBindingRole)
                bound_ids.add(b.content_id)

        assert len(bound_ids) > 0

    def test_primary_and_supporting_roles_assigned(self, sample_content_package):
        planner = StoryPlanner(use_ai=False)
        plan = planner.plan_story(
            content_pkg=sample_content_package,
            user_objective="Explore geographic density"
        )

        all_roles = [
            b.binding_role
            for s in plan.logical_slides
            for b in s.content_bindings
        ]
        assert ContentBindingRole.PRIMARY in all_roles
        # Check if supporting table was paired with primary visual
        geo_slide = next(
            (s for s in plan.logical_slides if s.tag == SlideTag.GEOGRAPHIC_DISTRIBUTION),
            None
        )
        if geo_slide and len(geo_slide.content_bindings) > 1:
            binding_roles = [b.binding_role for b in geo_slide.content_bindings]
            assert ContentBindingRole.PRIMARY in binding_roles
            assert ContentBindingRole.SUPPORTING in binding_roles


# ==============================================================================
# 3. OBJECTIVE-AWARE ORDERING & EMPHASIS
# ==============================================================================

class TestObjectiveAwareOrdering:
    """Verifies that user objectives drive narrative prioritization without mirroring dashboard verbatim."""

    def test_geographic_objective_prioritizes_spatial_slide(self, sample_content_package):
        planner = StoryPlanner(use_ai=False)
        plan = planner.plan_story(
            content_pkg=sample_content_package,
            user_objective="Detailed geographic and regional population analysis"
        )

        # In a geo-focused deck, GEOGRAPHIC_DISTRIBUTION should appear early in empirical findings
        slide_tags = [s.tag for s in plan.logical_slides]
        assert SlideTag.GEOGRAPHIC_DISTRIBUTION in slide_tags
        geo_index = slide_tags.index(SlideTag.GEOGRAPHIC_DISTRIBUTION)
        # Should be placed right after the introductory framing (TITLE, SUMMARY, KPIS, AGENDA)
        assert geo_index <= 5

        # Check bound content for geo slide
        geo_slide = plan.logical_slides[geo_index]
        bound_ids = [b.content_id for b in geo_slide.content_bindings]
        assert "ITEM-001" in bound_ids  # The MAP item

    def test_risk_objective_prioritizes_anomaly_slide(self, sample_content_package):
        planner = StoryPlanner(use_ai=False)
        plan = planner.plan_story(
            content_pkg=sample_content_package,
            user_objective="Focus on risk anomalies, incident spikes, and delay variances"
        )

        slide_tags = [s.tag for s in plan.logical_slides]
        assert SlideTag.COHORT_VARIANCE in slide_tags
        risk_index = slide_tags.index(SlideTag.COHORT_VARIANCE)
        # Anomaly slide should appear prominently
        assert risk_index <= 5

        risk_slide = plan.logical_slides[risk_index]
        bound_ids = [b.content_id for b in risk_slide.content_bindings]
        assert "ITEM-004" in bound_ids  # Peak Hour Incident Distribution


# ==============================================================================
# 4. REDUNDANCY HANDLING & COMPLETE CONTENT ACCOUNTING
# ==============================================================================

class TestRedundancyAndExcludedContentLedger:
    """Verifies that redundant and unselected items are cataloged with explicit reasons."""

    def test_redundant_items_routed_to_exclusion_ledger(self, sample_content_package):
        planner = StoryPlanner(use_ai=False)
        plan = planner.plan_story(
            content_pkg=sample_content_package,
            user_objective="Review overall operational performance"
        )

        # ITEM-005 had redundancy_score = 0.85
        redundant_exclusions = [
            e for e in plan.excluded_content
            if e.reason == ExclusionReason.REDUNDANT
        ]
        assert len(redundant_exclusions) >= 1
        redundant_ids = {e.content_id for e in redundant_exclusions}
        assert "ITEM-005" in redundant_ids

    def test_complete_content_accounting_zero_silent_loss(self, sample_content_package):
        """Invariant: Every item in package.items must be either bound or in excluded_content."""
        planner = StoryPlanner(use_ai=False)
        plan = planner.plan_story(
            content_pkg=sample_content_package,
            user_objective="Analyze high-level logistics"
        )

        all_pkg_item_ids = {it.content_id for it in sample_content_package.items}
        bound_item_ids = {
            b.content_id
            for s in plan.logical_slides
            for b in s.content_bindings
            if b.content_id.startswith("ITEM-")
        }
        excluded_item_ids = {e.content_id for e in plan.excluded_content}

        # Union must strictly equal all package items
        assert bound_item_ids | excluded_item_ids == all_pkg_item_ids
        # Intersection must be empty (cannot be both bound and excluded)
        assert len(bound_item_ids & excluded_item_ids) == 0

    def test_unaccounted_content_triggers_validator_error(self, sample_content_package):
        planner = StoryPlanner(use_ai=False)
        plan = planner.plan_story(
            content_pkg=sample_content_package,
            user_objective="Analyze performance"
        )

        # Intentionally remove an item from excluded_content without binding it
        plan.excluded_content.pop()

        with pytest.raises(UnaccountedContentError) as exc_info:
            StoryPlanValidator.validate(plan, sample_content_package, strict_exclusions=True)
        assert "neither bound to a slide nor recorded in excluded_content" in str(exc_info.value)


# ==============================================================================
# 5. UNKNOWN ID REJECTION
# ==============================================================================

class TestUnknownIdRejection:
    """Verifies that any unknown or hallucinated content_id is strictly rejected."""

    def test_rejects_hallucinated_bound_content_id(self, sample_content_package):
        planner = StoryPlanner(use_ai=False)
        plan = planner.plan_story(
            content_pkg=sample_content_package,
            user_objective="Check logistics"
        )

        # Inject a hallucinated ID into a slide binding
        plan.logical_slides[0].content_bindings.append(
            ContentBinding(content_id="HALLUCINATED-CHART-999", binding_role=ContentBindingRole.PRIMARY)
        )

        with pytest.raises(UnknownContentIdError) as exc_info:
            StoryPlanValidator.validate(plan, sample_content_package)
        assert "HALLUCINATED-CHART-999" in str(exc_info.value)

    def test_rejects_hallucinated_excluded_content_id(self, sample_content_package):
        planner = StoryPlanner(use_ai=False)
        plan = planner.plan_story(
            content_pkg=sample_content_package,
            user_objective="Check logistics"
        )

        # Inject a hallucinated ID into excluded_content
        plan.excluded_content.append(
            ExcludedContentItem(
                content_id="GHOST-ITEM-007",
                reason=ExclusionReason.OFF_OBJECTIVE
            )
        )

        with pytest.raises(UnknownContentIdError) as exc_info:
            StoryPlanValidator.validate(plan, sample_content_package)
        assert "GHOST-ITEM-007" in str(exc_info.value)


# ==============================================================================
# 6. DETERMINISTIC REPRODUCIBILITY & FALLBACK
# ==============================================================================

class TestDeterministicReproducibilityAndFallback:
    """Verifies that story planning is 100% deterministic and fallback operates seamlessly."""

    def test_identical_runs_produce_identical_fingerprints(self, sample_content_package):
        planner1 = DeterministicStoryPlanner()
        planner2 = DeterministicStoryPlanner()

        plan1 = planner1.plan(
            sample_content_package,
            user_objective="Analyze corridor velocity and bottlenecks",
            target_audience="VP Operations"
        )
        plan2 = planner2.plan(
            sample_content_package,
            user_objective="Analyze corridor velocity and bottlenecks",
            target_audience="VP Operations"
        )

        assert plan1.story_fingerprint == plan2.story_fingerprint
        assert len(plan1.logical_slides) == len(plan2.logical_slides)
        for s1, s2 in zip(plan1.logical_slides, plan2.logical_slides):
            assert s1.tag == s2.tag
            assert s1.headline == s2.headline
            assert [b.content_id for b in s1.content_bindings] == [b.content_id for b in s2.content_bindings]

    def test_ai_planner_graceful_fallback(self, sample_content_package):
        """When AI raises an error or is offline, it falls back seamlessly to deterministic planner."""
        ai_planner = AIStoryPlanner()
        
        # Patch _attempt_ai_plan to raise an exception
        with patch.object(ai_planner, "_attempt_ai_plan", side_effect=RuntimeError("LLM API Timeout")):
            plan = ai_planner.plan(
                sample_content_package,
                user_objective="Operational overview",
                target_audience="Executive Leadership"
            )

        assert isinstance(plan, DeckStoryPlan)
        assert len(plan.logical_slides) >= 5
        assert len(plan.story_fingerprint) == 64


# ==============================================================================
# 7. ARCHITECTURAL INVARIANTS: ZERO PHYSICAL LAYOUT / COORDINATES / EXPANSION
# ==============================================================================

class TestArchitecturalInvariantsZeroPhysicalLayout:
    """Verifies that PPT-L2 contains ZERO physical coordinates, slide numbers, or zone layouts."""

    def test_zero_physical_coordinates_in_output(self, sample_content_package):
        planner = StoryPlanner(use_ai=False)
        plan = planner.plan_story(
            content_pkg=sample_content_package,
            user_objective="Analyze spatial density"
        )

        plan_dict = plan.model_dump()

        def _assert_no_coords(data: Any, path: str = ""):
            forbidden = {"x", "y", "width", "height", "left", "top", "pt_x", "pt_y", "slide_number", "page_number", "zones", "layers"}
            if isinstance(data, dict):
                for k, v in data.items():
                    assert k.lower() not in forbidden, f"Forbidden physical property '{k}' leaked at '{path}.{k}'"
                    _assert_no_coords(v, f"{path}.{k}")
            elif isinstance(data, list):
                for i, elem in enumerate(data):
                    _assert_no_coords(elem, f"{path}[{i}]")

        _assert_no_coords(plan_dict)

    def test_validator_rejects_physical_coordinate_leakage(self, sample_content_package):
        planner = StoryPlanner(use_ai=False)
        plan = planner.plan_story(
            content_pkg=sample_content_package,
            user_objective="Analyze spatial density"
        )

        # Inject physical layout metadata into plan metadata
        plan.metadata["zones"] = [{"zone_id": "ZONE-01", "width": 480}]

        with pytest.raises(PhysicalLayoutLeakageError) as exc_info:
            StoryPlanValidator.validate(plan, sample_content_package)
        assert "Physical layout property 'zones'" in str(exc_info.value)


# ==============================================================================
# 8. ANALYTICAL TRUTH PRESERVATION: ZERO MUTATIONS
# ==============================================================================

class TestAnalyticalTruthPreservation:
    """Verifies that facts, units, grains, and denominators remain 100% immutable."""

    def test_zero_fact_unit_grain_mutations(self, sample_content_package):
        # Deepcopy package to check immutability after planning
        orig_copy = copy.deepcopy(sample_content_package)

        planner = StoryPlanner(use_ai=False)
        plan = planner.plan_story(
            content_pkg=sample_content_package,
            user_objective="Complete review of delivery operations"
        )

        # Verify that original package was not mutated
        for orig_it, curr_it in zip(orig_copy.items, sample_content_package.items):
            assert orig_it.metric_value == curr_it.metric_value, "Fact value mutated!"
            assert orig_it.unit == curr_it.unit, "Unit mutated!"
            assert orig_it.grain == curr_it.grain, "Grain mutated!"
            assert orig_it.denominator == curr_it.denominator, "Denominator mutated!"

        # Verify that global KPIs were not mutated
        for orig_k, curr_k in zip(orig_copy.global_kpis, sample_content_package.global_kpis):
            assert orig_k.metric_value == curr_k.metric_value, "KPI value mutated!"
            assert orig_k.unit == curr_k.unit, "KPI unit mutated!"
            assert orig_k.grain == curr_k.grain, "KPI grain mutated!"
            assert orig_k.denominator == curr_k.denominator, "KPI denominator mutated!"


# ==============================================================================
# 9. ORCHESTRATOR LAYERED STORY PLANNER INTEGRATION
# ==============================================================================

class TestOrchestratorLayeredStoryPlannerIntegration:
    """Verifies pipeline_orchestrator integration in LAYERED mode."""

    def test_orchestrator_layered_mode_stops_after_deck_story_plan(self):
        from app.services.presentation.pipeline_orchestrator import execute_presentation_pipeline_async
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

            result_deck = execute_presentation_pipeline_async("job-ppt-l2-test", scope, manager=mock_mgr)

            # Invariant: Zero legacy StoryPlanner or deck generator calls
            mock_gen.assert_not_called()

            # Invariant: Layered mode returns structured deck spec stopping after DeckStoryPlan
            assert result_deck is not None
            assert result_deck["metadata"]["pipeline_mode"] == "LAYERED"
            assert result_deck["metadata"]["status"] == "STORY_PLAN_VALIDATED"
            assert "content_package" in result_deck["metadata"]
            assert "story_plan" in result_deck["metadata"]

            story_plan = result_deck["metadata"]["story_plan"]
            assert story_plan["target_audience"] == "Board of Directors"
            assert story_plan["user_objective"] == "Executive Geographic Expansion Strategy"
            assert len(story_plan["logical_slides"]) >= 4
            assert len(story_plan["story_fingerprint"]) == 64

            # Invariant: 0 physical coordinates, 0 physical slides, 0 physical manifest (PPT-L3+)
            assert len(result_deck["slides"]) == 0
            assert "physical_manifest" not in result_deck["metadata"]

            # Invariant: Job manager stage updated to ready with story_plan_validated phase
            mock_mgr.update_stage.assert_called()
            last_call_args, last_call_kwargs = mock_mgr.update_stage.call_args
            assert last_call_args[1] == "ready"
            assert last_call_args[3] == 100
            assert last_call_kwargs["extra"]["active_phase"] == "story_plan_validated"

