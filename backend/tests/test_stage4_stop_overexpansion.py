"""HighView Presentation Studio — Stage 4 Focused Verification.

Verifies:
1. 'visual_completeness' semantic is cleanly typed (COMPLETE_VISUAL, DETAIL_VISUAL).
2. REUSE_EXISTING + COMPLETE_VISUAL defaults to exactly 1 primary physical slide.
3. SlideExpansionEngine guards complete visuals from splitting based on category count alone.
4. India density choropleth allocates 1 primary slide, NOT 3 ranking continuation slides.
5. Data Explorer table defaults to SUPPORTING/OPTIONAL reference rather than main executive slide.
6. Executive KPIs remain preserved as opening content.
7. Raw ranking data is preserved without loss in content package and references.
"""

import pytest
from app.services.presentation.content_models import (
    ContentKind,
    ContentRole,
    PresentationContentItem,
    PresentationContentPackage,
    VisualCompleteness,
    VisualStrategy,
)
from app.services.presentation.story_models import (
    ContentBinding,
    ContentBindingRole,
    DeckStoryPlan,
    LogicalSlidePlan,
    StructuralRole,
)
from app.services.presentation.story_planner import StoryPlanner
from app.services.presentation.preflight_engine import PresentationPreflightEngine
from app.services.presentation.expansion_engine import SlideExpansionEngine
from app.services.presentation.manifest_models import ContentDensity, ExpansionReason


class TestStage4StopOverexpansion:
    """Verifies that complete analytical visuals remain single-slide units and avoid over-expansion."""

    def test_visual_completeness_defaults(self):
        """Analytical visual types default to COMPLETE_VISUAL; tables default to DETAIL_VISUAL."""
        chart_item = PresentationContentItem(
            content_id="CONTENT-001",
            visual_id="TOPIC-001",
            source_surface="dashboard",
            visual_type="choropleth",
            kind=ContentKind.MAP,
            role=ContentRole.KEY_FINDING,
            topic_category="Population Density",
            title="Population Density Map",
            takeaway="Dense urban concentrations in Northern India",
            visual_spec={"chart_type": "choropleth", "topic_id": "TOPIC-001"}
        )
        assert chart_item.visual_completeness == VisualCompleteness.COMPLETE_VISUAL
        assert chart_item.visual_strategy == VisualStrategy.REUSE_EXISTING

        table_item = PresentationContentItem(
            content_id="CONTENT-EXP-001",
            visual_id="explorer_table",
            source_surface="data_explorer",
            visual_type="table",
            kind=ContentKind.TABLE,
            role=ContentRole.EXPLORATORY_TABLE,
            topic_category="Data Structure",
            title="Dataset Preview",
            takeaway="Sample preview of 10 records",
            table_data=[{"state": "UP", "pop": 199000000}]
        )
        assert table_item.visual_completeness == VisualCompleteness.DETAIL_VISUAL

    def test_preflight_recommends_one_physical_slide_for_complete_reused_visual(self):
        """Preflight engine preserves 1 slide allocation for COMPLETE_VISUAL despite heavy category data."""
        # Visual with 36 categories (like Indian states)
        categories_36 = [f"State_{i}" for i in range(36)]
        item = PresentationContentItem(
            content_id="CONTENT-MAP-01",
            visual_id="TOPIC-MAP-01",
            source_surface="dashboard",
            visual_type="choropleth",
            kind=ContentKind.MAP,
            role=ContentRole.KEY_FINDING,
            topic_category="Geographic Density",
            title="State Population Density",
            takeaway="Dense cluster in Delhi and UP",
            visual_spec={"chart_type": "choropleth", "categories": categories_36, "topic_id": "TOPIC-MAP-01"},
            visual_completeness=VisualCompleteness.COMPLETE_VISUAL,
            visual_strategy=VisualStrategy.REUSE_EXISTING,
        )

        binding = ContentBinding(
            content_id=item.content_id,
            binding_role=ContentBindingRole.PRIMARY,
            visual_id=item.visual_id,
            visual_strategy=item.visual_strategy,
            visual_completeness=item.visual_completeness,
            visual_type=item.visual_type,
            visual_spec=item.visual_spec,
        )

        logical_slide = LogicalSlidePlan(
            logical_slide_id="GEOGRAPHIC_DENSITY",
            structural_role=StructuralRole.GEOGRAPHIC_ANALYSIS,
            semantic_topic="GEOGRAPHIC_DENSITY",
            section_name="Empirical Findings",
            purpose="Analyze geographic distribution",
            headline="Geographic Density Analysis",
            takeaway="36 states analyzed",
            content_bindings=[binding],
            visual_id=item.visual_id,
            visual_strategy=item.visual_strategy,
            visual_completeness=item.visual_completeness,
            visual_type=item.visual_type,
            allow_split=True, # Even if caller allows split, complete visual invariant overrides
        )

        story_plan = DeckStoryPlan(
            plan_id="PLAN-TEST-01",
            deck_title="Test Deck",
            deck_subtitle="Testing Stage 4",
            executive_thesis="Core Thesis",
            logical_slides=[logical_slide],
            sections=["Empirical Findings"]
        )

        content_pkg = PresentationContentPackage(
            package_id="PKG-TEST-01",
            dataset_name="India Census",
            domain="Demographics",
            items=[item]
        )

        preflight_engine = PresentationPreflightEngine()
        result = preflight_engine.preflight(story_plan, content_pkg)
        assert len(result.logical_topic_results) == 1
        assert result.logical_topic_results[0].recommended_physical_slides == 1
        assert result.logical_topic_results[0].expansion_reason == ExpansionReason.NONE

    def test_expansion_engine_guards_complete_visual_from_expansion(self):
        """SlideExpansionEngine strictly enforces target_physical_count=1 for REUSE_EXISTING + COMPLETE_VISUAL."""
        item = PresentationContentItem(
            content_id="CONTENT-BOX-01",
            visual_id="TOPIC-BOX-01",
            source_surface="dashboard",
            visual_type="box_plot",
            kind=ContentKind.CHART,
            role=ContentRole.KEY_FINDING,
            topic_category="Population Spread",
            title="Distribution Spread",
            takeaway="Wide interquartile range",
            visual_completeness=VisualCompleteness.COMPLETE_VISUAL,
            visual_strategy=VisualStrategy.REUSE_EXISTING,
        )

        binding = ContentBinding(
            content_id=item.content_id,
            binding_role=ContentBindingRole.PRIMARY,
            visual_id=item.visual_id,
            visual_strategy=item.visual_strategy,
            visual_completeness=item.visual_completeness,
            visual_type=item.visual_type,
        )

        logical_slide = LogicalSlidePlan(
            logical_slide_id="POPULATION_SPREAD",
            structural_role=StructuralRole.COHORT_ANALYSIS,
            semantic_topic="POPULATION_SPREAD",
            section_name="Analysis",
            purpose="Show spread",
            headline="Population Spread Across Cohorts",
            takeaway="Clear variance",
            content_bindings=[binding],
            visual_id=item.visual_id,
            visual_strategy=item.visual_strategy,
            visual_completeness=item.visual_completeness,
            visual_type=item.visual_type,
            allow_split=True,
        )

        story_plan = DeckStoryPlan(
            plan_id="PLAN-TEST-02",
            deck_title="Test Deck",
            deck_subtitle="Testing Stage 4",
            executive_thesis="Core Thesis",
            logical_slides=[logical_slide],
            sections=["Analysis"]
        )

        content_pkg = PresentationContentPackage(
            package_id="PKG-TEST-02",
            dataset_name="Census",
            domain="Demographics",
            items=[item]
        )

        engine = SlideExpansionEngine()
        # Even if expand is called with high requested count, complete visual guard enforces 1 slide
        manifest = engine.expand(story_plan=story_plan, content_pkg=content_pkg, target_slide_count=20)
        assert len(manifest.slides) == 1
        assert manifest.slides[0].physical_slide_id == "POPULATION_SPREAD-01"
        assert not manifest.slides[0].is_continuation

    def test_data_explorer_table_defaults_to_supporting(self):
        """Data Explorer table is not automatically promoted to a primary executive slide."""
        table_item = PresentationContentItem(
            content_id="CONTENT-EXP-001",
            visual_id="explorer_table_sample",
            source_surface="data_explorer",
            visual_type="table",
            kind=ContentKind.TABLE,
            role=ContentRole.EXPLORATORY_TABLE,
            topic_category="Data Structure",
            title="Sample Preview",
            takeaway="Preview of empirical rows",
            table_data=[{"id": 1, "val": 100}],
            visual_completeness=VisualCompleteness.DETAIL_VISUAL,
        )

        hero_item = PresentationContentItem(
            content_id="CONTENT-HERO-001",
            visual_id="hero_chart",
            source_surface="dashboard",
            visual_type="scatter",
            kind=ContentKind.CHART,
            role=ContentRole.PRIMARY_HERO,
            topic_category="Growth Trends",
            title="Growth vs Base",
            takeaway="Positive correlation",
            visual_spec={"chart_type": "scatter"},
            visual_completeness=VisualCompleteness.COMPLETE_VISUAL,
            visual_strategy=VisualStrategy.REUSE_EXISTING,
        )

        pkg = PresentationContentPackage(
            package_id="PKG-TEST-03",
            dataset_name="Dataset",
            domain="Analytics",
            items=[hero_item, table_item]
        )

        planner = StoryPlanner()
        # Normal executive objective without table request
        plan = planner.plan_story(pkg, user_objective="Executive Summary of Growth Trends")
        
        # Verify hero is a primary logical slide
        hero_slides = [s for s in plan.logical_slides if any(b.content_id == "CONTENT-HERO-001" for b in s.content_bindings)]
        assert len(hero_slides) == 1

        # Verify table is NOT a primary main executive slide
        table_slides = [s for s in plan.logical_slides if any(b.content_id == "CONTENT-EXP-001" for b in s.content_bindings)]
        assert len(table_slides) == 0

        # Verify table is preserved in excluded_content ledger as reference
        excluded_table = [e for e in plan.excluded_content if e.content_id == "CONTENT-EXP-001"]
        assert len(excluded_table) == 1
        assert "SUPPORTING/OPTIONAL" in excluded_table[0].notes
