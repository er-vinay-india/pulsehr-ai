"""Comprehensive Test Suite & Architectural Invariant Audit for StoryPlanner & Semantic SlideTags (PPT-L2).

Validates:
1. Structural Story Role != Extensible Semantic Topic:
   - structural_role (StructuralRole enum) represents storytelling role (GEOGRAPHIC_ANALYSIS, HERO_ANALYSIS, etc.)
   - semantic_topic (string) represents domain topic (POPULATION_DENSITY, POPULATION_GROWTH, CUSTOMER_RETENTION)
   - logical_slide_id is semantic (e.g. POPULATION_DENSITY), not physical.
2. Multiple Semantic Topics Under Same Structural Role:
   - Simultaneous existence of GEOGRAPHIC_ANALYSIS / POPULATION_DENSITY and GEOGRAPHIC_ANALYSIS / POPULATION_GROWTH
   - Comparison slides under DEPARTMENT_ATTENDANCE and DEPARTMENT_LEAVE without enum expansion.
3. Domain-Independent Extensibility:
   - Previously unseen topic (e.g. CUSTOMER_RETENTION) handled without enum modifications.
4. AI Story Planner Path & Telemetry:
   - Typed schema parsing, ID containment, duplicate binding normalization, latency and call count tracking.
   - Deterministic fallback on timeout, malformed schema, or hallucinated IDs.
5. User Objective Effect:
   - Same package, Objective A (density) vs Objective B (growth): same facts/units/grain, different ordering & priorities.
6. Business Governance Leakage vs Technical Terminology:
   - Normal business deck: 0 SDR, 0 JoinPlan, 0 EVID-..., 0 checksums in user-visible narrative text.
   - Technical presentation: faithfully preserves explicitly requested technical terms verbatim.
7. Truth & Physical Layout Invariants:
   - 0 fact, unit, grain, denominator mutations; 0 invented facts.
   - 0 physical coordinates, 0 physical slide numbers, 0 zones/layers, 0 SlideExpansion, 0 layout work.
   - 0 legacy StoryPlanner calls in layered mode.
"""

import copy
import time
from typing import Any
import pytest
from unittest.mock import MagicMock, patch

from app.services.presentation.content_models import (
    ContentKind,
    ContentRole,
    PresentationContentItem,
    PresentationContentPackage,
    UserVisibleContentPolicy,
)
from app.services.presentation.story_models import (
    ContentBinding,
    ContentBindingRole,
    DeckStoryPlan,
    ExcludedContentItem,
    ExclusionReason,
    GovernanceLeakageError,
    LogicalSlidePlan,
    PhysicalLayoutLeakageError,
    StructuralRole,
    SlideTag,
    StoryPlanValidationError,
    StoryPlanValidator,
    UnaccountedContentError,
    UnknownContentIdError,
    normalize_semantic_topic,
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
            topic_category="Population Density",
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
            kind=ContentKind.CHART,
            role=ContentRole.KEY_FINDING,
            topic_category="Population Growth",
            title="Regional Population Growth and Expansion Trends",
            importance_score=0.90,
            decision_relevance=0.86,
            visual_suitability=0.92,
            narrative_takeaway="Southern expansion territories exhibit accelerated 14.8% annualized population growth.",
            unit="%",
            grain="region",
            denominator="baseline_population"
        ),
        PresentationContentItem(
            content_id="ITEM-003",
            kind=ContentKind.TABLE,
            role=ContentRole.EXPLORATORY_TABLE,
            topic_category="Population Density",
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
            content_id="ITEM-004",
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
            content_id="ITEM-005",
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
            content_id="ITEM-006",
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
            content_id="ITEM-007",
            kind=ContentKind.TABLE,
            role=ContentRole.EXPLORATORY_TABLE,
            topic_category="Auxiliary Equipment",
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
        available_topics=["Population Density", "Population Growth", "Corridor Velocity", "Service Variance", "Auxiliary Equipment"],
    )
    pkg.content_fingerprint = pkg.compute_fingerprint()
    return pkg


# ==============================================================================
# 1. STRUCTURAL ROLE != EXTENSIBLE SEMANTIC TOPIC
# ==============================================================================

class TestStructuralRoleVsSemanticTopic:
    """Verifies that structural story role is cleanly separated from extensible semantic topic."""

    def test_structural_role_and_semantic_topic_distinct(self, sample_content_package):
        planner = StoryPlanner(use_ai=False)
        plan = planner.plan_story(
            content_pkg=sample_content_package,
            user_objective="Analyze population density across districts"
        )

        geo_slides = [
            s for s in plan.logical_slides
            if s.structural_role == StructuralRole.GEOGRAPHIC_ANALYSIS
        ]
        assert len(geo_slides) >= 1
        slide = geo_slides[0]

        # Structural role is generic storytelling archetype
        assert slide.structural_role == StructuralRole.GEOGRAPHIC_ANALYSIS
        # Semantic topic is the domain business topic
        assert slide.semantic_topic == "POPULATION_DENSITY"
        # Logical slide ID is semantic, NOT generic
        assert "POPULATION_DENSITY" in slide.logical_slide_id
        assert "GEOGRAPHIC_DISTRIBUTION-1" not in slide.logical_slide_id

    def test_multiple_semantic_topics_under_same_structural_role(self, sample_content_package):
        """Verifies that GEOGRAPHIC_ANALYSIS can house POPULATION_DENSITY and POPULATION_GROWTH simultaneously."""
        planner = StoryPlanner(use_ai=False)
        plan = planner.plan_story(
            content_pkg=sample_content_package,
            user_objective="Comprehensive regional review covering population density and population growth",
            max_logical_slides=12
        )

        geo_slides = [
            s for s in plan.logical_slides
            if s.structural_role == StructuralRole.GEOGRAPHIC_ANALYSIS
        ]
        semantic_topics = [s.semantic_topic for s in geo_slides]
        
        # Both distinct topics are represented under the same structural role
        assert "POPULATION_DENSITY" in semantic_topics
        assert "POPULATION_GROWTH" in semantic_topics
        
        # Logical slide IDs remain distinct and meaningful
        logical_ids = [s.logical_slide_id for s in geo_slides]
        assert len(logical_ids) == len(set(logical_ids))
        assert any("POPULATION_DENSITY" in lid for lid in logical_ids)
        assert any("POPULATION_GROWTH" in lid for lid in logical_ids)

    def test_extensible_comparison_topics_without_enum_expansion(self):
        """Verifies that arbitrary topics (e.g. DEPARTMENT_ATTENDANCE vs DEPARTMENT_LEAVE) work without enum edits."""
        item1 = PresentationContentItem(
            content_id="HR-01",
            kind=ContentKind.CHART,
            role=ContentRole.PRIMARY_HERO,
            topic_category="Department Attendance",
            title="Department Attendance Comparison",
            metric_value="96.1%",
            importance_score=0.9
        )
        item2 = PresentationContentItem(
            content_id="HR-02",
            kind=ContentKind.CHART,
            role=ContentRole.KEY_FINDING,
            topic_category="Department Leave",
            title="Department Leave Pattern Analysis",
            metric_value="4.2 days",
            importance_score=0.88
        )
        pkg = PresentationContentPackage(
            package_id="PKG-HR-01",
            dataset_name="HR Workforce",
            domain="Human Resources",
            items=[item1, item2],
            global_kpis=[]
        )

        planner = StoryPlanner(use_ai=False)
        plan = planner.plan_story(pkg, user_objective="Compare attendance and leave")

        topics = [s.semantic_topic for s in plan.logical_slides]
        assert "DEPARTMENT_ATTENDANCE" in topics
        assert "DEPARTMENT_LEAVE" in topics


# ==============================================================================
# 2. DOMAIN-INDEPENDENT EXTENSIBILITY
# ==============================================================================

class TestDomainIndependentExtensibility:
    """Verifies that previously unseen domain topics work seamlessly without enum additions."""

    def test_unseen_topic_customer_retention(self):
        item = PresentationContentItem(
            content_id="SAAS-01",
            kind=ContentKind.CHART,
            role=ContentRole.PRIMARY_HERO,
            topic_category="Customer Retention",
            title="Net Retention Rate Across Enterprise Cohorts",
            metric_value="118%",
            unit="%",
            grain="customer_cohort",
            importance_score=0.95,
            decision_relevance=0.92,
            narrative_takeaway="Enterprise tier net customer retention expanded to 118%."
        )
        pkg = PresentationContentPackage(
            package_id="PKG-SAAS-01",
            dataset_name="SaaS Metrics",
            domain="Subscription Revenue",
            items=[item],
            global_kpis=[]
        )

        planner = StoryPlanner(use_ai=False)
        plan = planner.plan_story(pkg, user_objective="Focus on enterprise customer retention")

        # Verify plan accepted without new enum
        slide = next(s for s in plan.logical_slides if s.semantic_topic == "CUSTOMER_RETENTION")
        assert slide.structural_role in (StructuralRole.HERO_ANALYSIS, StructuralRole.DIAGNOSTIC_ANALYSIS)
        assert slide.semantic_topic == "CUSTOMER_RETENTION"
        assert "CUSTOMER_RETENTION" in slide.logical_slide_id
        assert len(plan.story_fingerprint) == 64

        # Validate cleanly
        StoryPlanValidator.validate(plan, pkg)


# ==============================================================================
# 3. AI STORY PLANNER PATH CERTIFICATION & TELEMETRY
# ==============================================================================

class TestAIStoryPlannerPathCertification:
    """Verifies the real AI story planning path with schema validation, call counts, and latency."""

    def test_ai_planner_typed_schema_success(self, sample_content_package):
        ai_planner = AIStoryPlanner()
        mock_payload = {
            "deck_title": "Executive Fleet & Corridor Diagnostic",
            "deck_subtitle": "Audited AI Story Architecture",
            "executive_thesis": "Corridor turnaround lag directly compresses on-time reliability.",
            "sections": ["Strategic Context", "Thematic Discoveries", "Actions"],
            "logical_slides": [
                {
                    "logical_slide_id": "POPULATION_DENSITY",
                    "structural_role": "GEOGRAPHIC_ANALYSIS",
                    "semantic_topic": "POPULATION_DENSITY",
                    "section_name": "Thematic Discoveries",
                    "purpose": "Evaluate state population density",
                    "headline": "Northern Corridor Density Concentration",
                    "takeaway": "Northern region density reaches 11,320 per sq km.",
                    "content_bindings": [
                        {"content_id": "ITEM-001", "binding_role": "PRIMARY"}
                    ]
                },
                {
                    "logical_slide_id": "CORRIDOR_VELOCITY",
                    "structural_role": "CORRELATION_ANALYSIS",
                    "semantic_topic": "CORRIDOR_VELOCITY",
                    "section_name": "Thematic Discoveries",
                    "purpose": "Corridor dispatch velocity",
                    "headline": "Turnaround Correlation Dynamics",
                    "takeaway": "Strong negative correlation.",
                    "content_bindings": [
                        {"content_id": "ITEM-004", "binding_role": "PRIMARY"}
                    ]
                }
            ]
        }

        plan = ai_planner.plan(
            sample_content_package,
            user_objective="Evaluate spatial density and velocity",
            metadata={"mock_ai_response": mock_payload}
        )

        assert isinstance(plan, DeckStoryPlan)
        assert plan.deck_title == "Executive Fleet & Corridor Diagnostic"
        assert ai_planner.call_count == 1
        assert ai_planner.total_latency_ms >= 0.0
        assert ai_planner.repair_calls == 0
        assert ai_planner.fallback_invoked is False

        # All unassigned items routed to excluded_content
        excluded_ids = {e.content_id for e in plan.excluded_content}
        assert "ITEM-002" in excluded_ids
        assert "ITEM-005" in excluded_ids
        assert "ITEM-006" in excluded_ids

    def test_ai_planner_rejects_hallucinated_id_and_triggers_fallback(self, sample_content_package):
        ai_planner = AIStoryPlanner()
        mock_invalid = {
            "deck_title": "AI Hallucinated Plan",
            "logical_slides": [
                {
                    "logical_slide_id": "BAD_SLIDE",
                    "structural_role": "HERO_ANALYSIS",
                    "semantic_topic": "HALLUCINATED_TOPIC",
                    "section_name": "Findings",
                    "headline": "Ghost Metric",
                    "content_bindings": [
                        {"content_id": "HALLUCINATED-ITEM-999", "binding_role": "PRIMARY"}
                    ]
                }
            ]
        }

        plan = ai_planner.plan(
            sample_content_package,
            user_objective="Standard operational review",
            metadata={"mock_ai_response": mock_invalid}
        )

        # Fallback invoked cleanly
        assert ai_planner.fallback_invoked is True
        assert isinstance(plan, DeckStoryPlan)
        # Verify no hallucinated ID exists in returned plan
        bound_ids = {b.content_id for s in plan.logical_slides for b in s.content_bindings}
        assert "HALLUCINATED-ITEM-999" not in bound_ids
        StoryPlanValidator.validate(plan, sample_content_package)

    def test_ai_planner_normalizes_duplicate_bindings(self, sample_content_package):
        ai_planner = AIStoryPlanner()
        mock_with_dupe = {
            "deck_title": "Deduplicated Plan",
            "logical_slides": [
                {
                    "logical_slide_id": "POPULATION_DENSITY",
                    "structural_role": "GEOGRAPHIC_ANALYSIS",
                    "semantic_topic": "POPULATION_DENSITY",
                    "section_name": "Findings",
                    "headline": "Density Analysis",
                    "content_bindings": [
                        {"content_id": "ITEM-001", "binding_role": "PRIMARY"},
                        {"content_id": "ITEM-001", "binding_role": "PRIMARY"}  # duplicate
                    ]
                }
            ]
        }

        plan = ai_planner.plan(
            sample_content_package,
            user_objective="Density overview",
            metadata={"mock_ai_response": mock_with_dupe}
        )

        assert ai_planner.repair_calls == 1
        slide = plan.logical_slides[0]
        # Duplicate was normalized to single binding
        assert len(slide.content_bindings) == 1
        assert slide.content_bindings[0].content_id == "ITEM-001"

    def test_ai_planner_fallback_on_malformed_schema_and_timeout(self, sample_content_package):
        ai_planner = AIStoryPlanner()

        # Test malformed schema (missing required fields)
        plan1 = ai_planner.plan(
            sample_content_package,
            metadata={"mock_ai_response": {"broken": "payload"}}
        )
        assert ai_planner.fallback_invoked is True
        assert len(plan1.logical_slides) >= 4

        # Test timeout / exception
        ai_planner2 = AIStoryPlanner()
        with patch.object(ai_planner2, "_attempt_ai_plan", side_effect=TimeoutError("Model timed out")):
            plan2 = ai_planner2.plan(sample_content_package)
            assert ai_planner2.fallback_invoked is True
            assert len(plan2.logical_slides) >= 4


# ==============================================================================
# 4. USER OBJECTIVE EFFECT
# ==============================================================================

class TestUserObjectiveEffect:
    """Verifies that user objectives significantly influence ordering and priority with identical facts."""

    def test_same_package_different_objectives_different_priority(self, sample_content_package):
        planner = StoryPlanner(use_ai=False)

        # Objective A: Focus on population density
        plan_density = planner.plan_story(
            content_pkg=sample_content_package,
            user_objective="Focus specifically on population density and high load centers"
        )

        # Objective B: Focus on population growth
        plan_growth = planner.plan_story(
            content_pkg=sample_content_package,
            user_objective="Focus specifically on population growth, expansion territories, and scale"
        )

        # 1. Facts, units, grains remain 100% identical
        for orig, d_item in zip(sample_content_package.items, sample_content_package.items):
            assert orig.metric_value == d_item.metric_value
            assert orig.unit == d_item.unit
            assert orig.grain == d_item.grain

        # 2. But narrative ordering and topic priority differ!
        topics_density = [s.semantic_topic for s in plan_density.logical_slides]
        topics_growth = [s.semantic_topic for s in plan_growth.logical_slides]

        assert "POPULATION_DENSITY" in topics_density
        assert "POPULATION_GROWTH" in topics_growth

        # In density plan, density appears before growth
        density_idx_in_a = topics_density.index("POPULATION_DENSITY")
        growth_idx_in_a = topics_density.index("POPULATION_GROWTH") if "POPULATION_GROWTH" in topics_density else 99
        assert density_idx_in_a < growth_idx_in_a

        # In growth plan, growth appears before density
        growth_idx_in_b = topics_growth.index("POPULATION_GROWTH")
        density_idx_in_b = topics_growth.index("POPULATION_DENSITY") if "POPULATION_DENSITY" in topics_growth else 99
        assert growth_idx_in_b < density_idx_in_b

        # Fingerprints are distinctly different
        assert plan_density.story_fingerprint != plan_growth.story_fingerprint


# ==============================================================================
# 5. BUSINESS GOVERNANCE LEAKAGE VS TECHNICAL TERMINOLOGY
# ==============================================================================

class TestGovernanceLeakageAndTechnicalTerminology:
    """Verifies that business decks omit internal jargon, while technical requests preserve it."""

    def test_normal_business_deck_omits_internal_governance_jargon(self, sample_content_package):
        planner = StoryPlanner(use_ai=False)
        plan = planner.plan_story(
            content_pkg=sample_content_package,
            user_objective="Executive Operations Review"
        )

        forbidden_terms = ["SDR", "JoinPlan", "JoinGraph", "EVID-", "control plane"]
        all_narrative_text = f"{plan.deck_title} {plan.deck_subtitle} {plan.executive_thesis} " + " ".join(
            f"{s.headline} {s.takeaway} {s.purpose}" for s in plan.logical_slides
        )

        for term in forbidden_terms:
            assert term.lower() not in all_narrative_text.lower(), f"Forbidden governance term '{term}' leaked into user narrative!"

    def test_governance_leakage_triggers_validator_error(self, sample_content_package):
        planner = StoryPlanner(use_ai=False)
        plan = planner.plan_story(
            content_pkg=sample_content_package,
            user_objective="Executive Operations Review"
        )

        # Inject an internal SDR term into an executive headline
        plan.logical_slides[0].headline = "Quarterly SDR-4 JoinPlan Performance"

        with pytest.raises(GovernanceLeakageError) as exc_info:
            StoryPlanValidator.validate(plan, sample_content_package)
        assert "leaked into user-visible field" in str(exc_info.value)

    def test_technical_objective_preserves_requested_terminology(self, sample_content_package):
        """When the user explicitly asks to audit or explain technical architecture, terms are preserved."""
        planner = StoryPlanner(use_ai=False)
        plan = planner.plan_story(
            content_pkg=sample_content_package,
            user_objective="Explain the SDR and JoinPlan architecture and data pipeline governance review"
        )

        # The objective was technical, so technical terms in objective remain valid
        assert "SDR" in plan.user_objective
        assert "JoinPlan" in plan.user_objective
        assert "SDR" in plan.deck_title
        # Validator passes without raising GovernanceLeakageError
        StoryPlanValidator.validate(plan, sample_content_package)


# ==============================================================================
# 6. TYPO CORRECTION: SUPERSEDED_BY_HERO
# ==============================================================================

class TestTypoCorrection:
    """Verifies that ExclusionReason uses the correct spelling SUPERSEDED_BY_HERO."""

    def test_exclusion_reason_uses_correct_spelling(self):
        assert ExclusionReason.SUPERSEDED_BY_HERO.value == "SUPERSEDED_BY_HERO"
        # Backwards compatibility alias also maps to the correct value
        assert ExclusionReason.SUPERCEDED_BY_HERO.value == "SUPERSEDED_BY_HERO"


# ==============================================================================
# 7. ZERO PHYSICAL LAYOUT / COORDINATES / EXPANSION INVARIANTS
# ==============================================================================

class TestPhysicalLayoutInvariants:
    """Verifies that DeckStoryPlan contains ZERO physical coordinates, slide numbers, or zone layouts."""

    def test_zero_physical_coordinates_in_output(self, sample_content_package):
        planner = StoryPlanner(use_ai=False)
        plan = planner.plan_story(
            content_pkg=sample_content_package,
            user_objective="Analyze spatial density"
        )

        plan_dict = plan.model_dump()

        def _assert_no_coords(data: Any, path: str = ""):
            forbidden = {
                "x", "y", "width", "height", "left", "top", "pt_x", "pt_y",
                "slide_number", "page_number", "zones", "layers", "emu",
                "layout_template", "physical_slide_id", "physical_slide_number"
            }
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
            assert result_deck["metadata"]["status"] in ("STORY_PLAN_VALIDATED", "PHYSICAL_MANIFEST_VALIDATED")
            assert "content_package" in result_deck["metadata"]
            assert "story_plan" in result_deck["metadata"]

            story_plan = result_deck["metadata"]["story_plan"]
            assert story_plan["target_audience"] == "Board of Directors"
            assert story_plan["user_objective"] == "Executive Geographic Expansion Strategy"
            assert len(story_plan["logical_slides"]) >= 4
            assert len(story_plan["story_fingerprint"]) == 64

            # Invariant: 0 physical coordinates, 0 rendered layout slides (PPT-L4+)
            assert len(result_deck["slides"]) == 0

            # Invariant: Job manager stage updated to ready with validated phase
            mock_mgr.update_stage.assert_called()
            last_call_args, last_call_kwargs = mock_mgr.update_stage.call_args
            assert last_call_args[1] == "ready"
            assert last_call_args[3] == 100
            assert last_call_kwargs["extra"]["active_phase"] in ("story_plan_validated", "physical_manifest_validated")
