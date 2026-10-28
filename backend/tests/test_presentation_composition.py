"""Targeted unit tests for Slide Composition Intelligence (PPT-L2.5).

Tests:
1. DeterministicCompositionProvider archetype selection, grouping, density, and label simplification.
2. CompositionDecisionValidator invariants (grounded IDs, purity, slide ID matching, confidence).
3. AICompositionProvider seamless fallback to deterministic provider on model failure.
4. SlideCompositionEngine deck-level composition orchestration and logical slide enrichment.
"""

from unittest.mock import MagicMock, patch
import pytest

from app.services.presentation.composition import (
    COMPOSITION_TO_LAYOUT_FAMILY,
    COMPOSITION_TO_PREFERRED_ARCHETYPE,
    AICompositionProvider,
    CompositionArchetype,
    CompositionContentGroup,
    CompositionContentRole,
    CompositionDecision,
    CompositionDecisionSource,
    CompositionDecisionValidator,
    CompositionValidationError,
    DeckCompositionPlan,
    DensityIntent,
    DeterministicCompositionProvider,
    NarrativePlacementIntent,
    SlideCompositionEngine,
    SplitIntent,
    VisualPriority,
)
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
    LogicalSlidePlan,
    StructuralRole,
)


def _make_sample_content_pkg() -> PresentationContentPackage:
    items = [
        PresentationContentItem(
            content_id="item-cover-01",
            kind=ContentKind.NARRATIVE_INSIGHT,
            role=ContentRole.PRIMARY_HERO,
            topic_category="District Overview",
            title="District Overview",
            takeaway="Educational performance metrics.",
        ),
        PresentationContentItem(
            content_id="item-kpi-01",
            kind=ContentKind.KPI_METRIC,
            role=ContentRole.STRATEGIC_KPI,
            topic_category="Graduation",
            title="92% Graduation Rate",
            takeaway="High school graduation benchmark.",
        ),
        PresentationContentItem(
            content_id="item-chart-01",
            kind=ContentKind.CHART,
            role=ContentRole.PRIMARY_HERO,
            topic_category="Cohort",
            title="Performance by Cohort",
            takeaway="Distribution across schools.",
        ),
        PresentationContentItem(
            content_id="item-table-01",
            kind=ContentKind.TABLE,
            role=ContentRole.EXPLORATORY_TABLE,
            topic_category="Data Explorer",
            title="School District Breakdown",
            takeaway="Tabular district scores.",
        ),
    ]
    return PresentationContentPackage(
        package_id="pkg-test-01",
        deck_title="District Performance Brief",
        dataset_name="district_db",
        domain="education",
        items=items,
    )


def test_deterministic_provider_title_cover():
    provider = DeterministicCompositionProvider()
    slide = LogicalSlidePlan(
        logical_slide_id="TITLE_COVER",
        structural_role=StructuralRole.TITLE,
        semantic_topic="DISTRICT_PERFORMANCE",
        section_name="Overview",
        purpose="Set context and title for the executive presentation",
        headline="District Academic Performance 2024-2025",
        content_bindings=[ContentBinding(content_id="item-cover-01")],
    )

    decision = provider.compose_slide(slide)

    assert decision.logical_slide_id == "TITLE_COVER"
    assert decision.composition_archetype == CompositionArchetype.TITLE_COVER
    assert decision.density_intent == DensityIntent.SPARSE
    assert decision.visual_priority == VisualPriority.REFERENCE
    assert decision.narrative_placement == NarrativePlacementIntent.BELOW_VISUAL
    assert decision.split_intent == SplitIntent.NO_SPLIT
    assert decision.confidence == 1.0
    assert decision.decision_source == CompositionDecisionSource.DETERMINISTIC_FALLBACK


def test_deterministic_provider_kpi_grid():
    provider = DeterministicCompositionProvider()
    slide = LogicalSlidePlan(
        logical_slide_id="KPI_OVERVIEW",
        structural_role=StructuralRole.STRATEGIC_KPIS,
        semantic_topic="PERFORMANCE_OVERVIEW",
        section_name="Metrics",
        purpose="Summary of top-level performance indicators",
        headline="Key Academic Benchmarks",
        content_bindings=[ContentBinding(content_id="item-kpi-01")],
    )

    decision = provider.compose_slide(slide)

    assert decision.composition_archetype == CompositionArchetype.KPI_GRID
    assert decision.density_intent == DensityIntent.BALANCED
    assert decision.visual_priority == VisualPriority.PRIMARY
    assert decision.narrative_placement == NarrativePlacementIntent.BELOW_VISUAL


def test_deterministic_provider_table_deep_dive():
    provider = DeterministicCompositionProvider()
    slide = LogicalSlidePlan(
        logical_slide_id="DATA_EXPLORER_TABLE",
        structural_role=StructuralRole.DEEP_DIVE,
        semantic_topic="SCHOOL_LEVEL_DATA",
        section_name="Data Deep Dive",
        purpose="Provide exhaustive school-level score records",
        headline="School Level Data Explorer Records",
        content_bindings=[ContentBinding(content_id="item-table-01")],
        visual_type="table",
    )

    decision = provider.compose_slide(slide)

    assert decision.composition_archetype == CompositionArchetype.TABLE_DEEP_DIVE
    assert decision.density_intent == DensityIntent.DENSE
    assert decision.narrative_placement == NarrativePlacementIntent.ABOVE_VISUAL
    assert decision.split_intent == SplitIntent.PREFER_SPLIT


def test_deterministic_provider_label_simplification():
    provider = DeterministicCompositionProvider()
    slide = LogicalSlidePlan(
        logical_slide_id="ACADEMIC_GROWTH",
        structural_role=StructuralRole.CORRELATION_ANALYSIS,
        semantic_topic="pct_proficient_math_score",
        section_name="Correlations",
        purpose="Analyze math score correlation",
        headline="Math Scores vs Growth Index",
        content_bindings=[ContentBinding(content_id="item-chart-01")],
        visual_spec={"metric": "district_growth_index", "x_axis": "avg_attendance_pct"},
    )

    decision = provider.compose_slide(slide)

    assert len(decision.label_intents) > 0
    source_labels = [li.source_label for li in decision.label_intents]
    assert "pct_proficient_math_score" in source_labels or "district_growth_index" in source_labels
    suggested = [li.suggested_display_text for li in decision.label_intents]
    assert any("Growth Index" in s or "Math Score" in s or "Attendance" in s for s in suggested if s)


def test_validator_rejects_mismatched_slide_id():
    slide = LogicalSlidePlan(
        logical_slide_id="SLIDE_A",
        structural_role=StructuralRole.HERO_ANALYSIS,
        semantic_topic="TOPIC_A",
        section_name="Section",
        purpose="Purpose",
        headline="Headline",
        content_bindings=[ContentBinding(content_id="item-kpi-01")],
    )
    decision = CompositionDecision(
        logical_slide_id="WRONG_SLIDE_ID",
        composition_archetype=CompositionArchetype.VISUAL_WITH_INSIGHT,
        primary_content_id="item-kpi-01",
    )

    with pytest.raises(CompositionValidationError, match="Mismatched logical_slide_id"):
        CompositionDecisionValidator.validate(decision, slide)


def test_validator_rejects_ungrounded_content_id():
    pkg = _make_sample_content_pkg()
    slide = LogicalSlidePlan(
        logical_slide_id="SLIDE_B",
        structural_role=StructuralRole.HERO_ANALYSIS,
        semantic_topic="TOPIC_B",
        section_name="Section",
        purpose="Purpose",
        headline="Headline",
        content_bindings=[ContentBinding(content_id="item-kpi-01")],
    )
    decision = CompositionDecision(
        logical_slide_id="SLIDE_B",
        composition_archetype=CompositionArchetype.VISUAL_WITH_INSIGHT,
        primary_content_id="hallucinated-content-999",
    )

    with pytest.raises(CompositionValidationError, match="ungrounded content IDs"):
        CompositionDecisionValidator.validate(decision, slide, pkg)


def test_validator_rejects_render_markup_in_metadata():
    slide = LogicalSlidePlan(
        logical_slide_id="SLIDE_C",
        structural_role=StructuralRole.HERO_ANALYSIS,
        semantic_topic="TOPIC_C",
        section_name="Section",
        purpose="Purpose",
        headline="Headline",
        content_bindings=[ContentBinding(content_id="item-kpi-01")],
    )
    decision = CompositionDecision(
        logical_slide_id="SLIDE_C",
        composition_archetype=CompositionArchetype.VISUAL_WITH_INSIGHT,
        primary_content_id="item-kpi-01",
        metadata={"font_size": "14pt"},  # Prohibited layout key
    )

    with pytest.raises(CompositionValidationError, match="prohibited rendering/layout key"):
        CompositionDecisionValidator.validate(decision, slide)


def test_ai_provider_fallback_on_exception():
    pkg = _make_sample_content_pkg()
    slide = LogicalSlidePlan(
        logical_slide_id="SLIDE_AI_TEST",
        structural_role=StructuralRole.HERO_ANALYSIS,
        semantic_topic="DISTRICT_BENCHMARK",
        section_name="Benchmark",
        purpose="Compare state vs district benchmarks",
        headline="District Outperforms State Benchmark",
        content_bindings=[ContentBinding(content_id="item-kpi-01")],
    )

    provider = AICompositionProvider(use_ai=True)

    with patch("app.services.gateway.model_gateway.ModelGateway.execute") as mock_exec:
        mock_exec.side_effect = RuntimeError("Ollama connection refused")
        decision = provider.compose_slide(slide, pkg)

    assert decision.decision_source == CompositionDecisionSource.DETERMINISTIC_FALLBACK
    assert decision.fallback_reason is not None
    assert "Ollama connection refused" in decision.fallback_reason
    assert decision.composition_archetype == CompositionArchetype.VISUAL_WITH_INSIGHT


def test_slide_composition_engine_compose_deck():
    pkg = _make_sample_content_pkg()
    slides = [
        LogicalSlidePlan(
            logical_slide_id="COVER",
            structural_role=StructuralRole.TITLE,
            semantic_topic="COVER_TOPIC",
            section_name="Overview",
            purpose="Deck Cover",
            headline="Executive Briefing",
            content_bindings=[ContentBinding(content_id="item-cover-01")],
        ),
        LogicalSlidePlan(
            logical_slide_id="KPIS",
            structural_role=StructuralRole.STRATEGIC_KPIS,
            semantic_topic="METRICS_TOPIC",
            section_name="Metrics",
            purpose="Performance KPIs",
            headline="Key Results",
            content_bindings=[ContentBinding(content_id="item-kpi-01")],
        ),
        LogicalSlidePlan(
            logical_slide_id="TABLE",
            structural_role=StructuralRole.DEEP_DIVE,
            semantic_topic="TABLE_TOPIC",
            section_name="Details",
            purpose="Detailed Breakdown",
            headline="District Records",
            content_bindings=[ContentBinding(content_id="item-table-01")],
            visual_type="table",
        ),
    ]
    story_plan = DeckStoryPlan(
        plan_id="PLAN-TEST-100",
        deck_title="District Analysis",
        deck_subtitle="Q3 Review",
        executive_thesis="Performance remains strong across cohorts.",
        logical_slides=slides,
    )

    engine = SlideCompositionEngine(use_ai=False)
    composition_plan = engine.compose_deck(story_plan, pkg)

    assert isinstance(composition_plan, DeckCompositionPlan)
    assert len(composition_plan.slide_decisions) == 3
    assert composition_plan.fallback_decisions_count == 3
    assert composition_plan.ai_decisions_count == 0

    # Verify logical slides were properly enriched
    cover_slide = story_plan.logical_slides[0]
    assert cover_slide.preferred_archetype == "TITLE_HERO"
    assert cover_slide.metadata["planned_layout_family"] == "title_cover"
    assert cover_slide.metadata["density_intent"] == "SPARSE"

    kpi_slide = story_plan.logical_slides[1]
    assert kpi_slide.preferred_archetype == "KPI_GRID"
    assert kpi_slide.metadata["planned_layout_family"] == "kpi_summary"

    table_slide = story_plan.logical_slides[2]
    assert table_slide.preferred_archetype == "DATA_TABLE_DETAIL"
    assert table_slide.metadata["planned_layout_family"] == "table_detail"
    assert table_slide.metadata["density_intent"] == "DENSE"

    # Verify deck-level telemetry
    assert "composition_telemetry" in story_plan.metadata
    assert story_plan.metadata["composition_telemetry"]["total_slides"] == 3
    assert "composition_consumption" in cover_slide.metadata


def test_governed_label_resolver_preserves_truth():
    from app.services.presentation.composition.label_resolver import GovernedLabelResolver
    from app.services.presentation.composition.composition_models import LabelSimplificationIntent

    intents = [
        LabelSimplificationIntent(
            source_label="pct_grad_rate_2024",
            suggested_display_text="Graduation Rate 2024",
        ),
        LabelSimplificationIntent(
            source_label="corrupt_intent_year",
            suggested_display_text="Year 2025",  # Source has no digits, candidate invents 2025
        ),
    ]

    # Valid simplification with preserved digits
    display, simplified = GovernedLabelResolver.resolve_label("pct_grad_rate_2024", intents)
    assert simplified is True
    assert display == "Graduation Rate 2024"

    # Mismatched digits / hallucinated numbers rejected
    display_rejected, simplified_rejected = GovernedLabelResolver.resolve_label("corrupt_intent_year", intents)
    assert simplified_rejected is False
    assert display_rejected == "corrupt_intent_year"


def test_preflight_split_intent_and_overflow_safety():
    from app.services.presentation.preflight_engine import PresentationPreflightEngine

    pkg = _make_sample_content_pkg()
    preflight = PresentationPreflightEngine()

    # Slide with PREFER_SPLIT and multiple items -> expands to 2 slides
    slide_prefer_split = LogicalSlidePlan(
        logical_slide_id="SPLIT_TEST",
        structural_role=StructuralRole.HERO_ANALYSIS,
        semantic_topic="PERFORMANCE",
        section_name="Analysis",
        purpose="Analyze performance",
        headline="Performance Across Schools",
        content_bindings=[
            ContentBinding(content_id="item-chart-01"),
            ContentBinding(content_id="item-table-01"),
        ],
        metadata={"split_intent": "PREFER_SPLIT"},
    )
    res_split = preflight.preflight(
        story_plan=DeckStoryPlan(
            plan_id="PLAN-SPLIT",
            deck_title="Split Test",
            deck_subtitle="",
            executive_thesis="",
            logical_slides=[slide_prefer_split],
        ),
        content_pkg=pkg,
    )
    assert res_split.logical_topic_results[0].recommended_physical_slides == 2

    # Slide with NO_SPLIT -> stays 1 slide
    slide_no_split = LogicalSlidePlan(
        logical_slide_id="NO_SPLIT_TEST",
        structural_role=StructuralRole.HERO_ANALYSIS,
        semantic_topic="PERFORMANCE",
        section_name="Analysis",
        purpose="Analyze performance",
        headline="Performance Summary",
        content_bindings=[
            ContentBinding(content_id="item-chart-01"),
            ContentBinding(content_id="item-kpi-01"),
        ],
        metadata={"split_intent": "NO_SPLIT"},
    )
    res_no_split = preflight.preflight(
        story_plan=DeckStoryPlan(
            plan_id="PLAN-NOSPLIT",
            deck_title="No Split Test",
            deck_subtitle="",
            executive_thesis="",
            logical_slides=[slide_no_split],
        ),
        content_pkg=pkg,
    )
    assert res_no_split.logical_topic_results[0].recommended_physical_slides == 1


def test_structure_builder_content_grouping_and_typography():
    from app.services.presentation.expansion_engine import SlideExpansionEngine
    from app.services.presentation.structure_builder import LayeredSlideStructureBuilder
    from app.services.presentation.layer_zone_models import ZoneType

    pkg = _make_sample_content_pkg()
    slide = LogicalSlidePlan(
        logical_slide_id="STRUCT_TEST",
        structural_role=StructuralRole.HERO_ANALYSIS,
        semantic_topic="DISTRICT_HERO",
        section_name="Analysis",
        purpose="Deep Dive",
        headline="District Academic Performance",
        content_bindings=[
            ContentBinding(content_id="item-kpi-01"),
            ContentBinding(content_id="item-chart-01"),
        ],
        metadata={
            "composition_decision": {
                "logical_slide_id": "STRUCT_TEST",
                "composition_archetype": "VISUAL_WITH_INSIGHT",
                "primary_content_id": "item-chart-01",  # item-chart-01 elevated over kpi
                "visual_priority": "PRIMARY",
                "content_groups": [
                    {"role": "PRIMARY_VISUAL", "content_ids": ["item-chart-01"]},
                    {"role": "PRIMARY_INSIGHT", "content_ids": ["item-kpi-01"]},
                ],
            }
        },
    )

    story_plan = DeckStoryPlan(
        plan_id="PLAN-STRUCT",
        deck_title="Struct Test",
        deck_subtitle="",
        executive_thesis="",
        logical_slides=[slide],
    )
    expansion = SlideExpansionEngine()
    manifest = expansion.expand(story_plan=story_plan, content_pkg=pkg)

    builder = LayeredSlideStructureBuilder()
    spec = builder.build_structure(manifest=manifest, content_pkg=pkg)
    slide_spec = spec.slides[0]

    # Primary visual zone should contain item-chart-01
    primary_vis_zones = [z for z in slide_spec.zones if z.zone_type == ZoneType.PRIMARY_VISUAL]
    assert len(primary_vis_zones) == 1
    assert primary_vis_zones[0].objects[0].content_id == "item-chart-01"

    # item-kpi-01 assigned PRIMARY_INSIGHT should have typography_priority = HIGH
    kpi_objs = [obj for z in slide_spec.zones for obj in z.objects if obj.content_id == "item-kpi-01"]
    assert len(kpi_objs) == 1
    assert kpi_objs[0].metadata.get("typography_priority") == "HIGH"


def test_layout_engine_visual_priority_and_narrative_placement():
    from app.services.presentation.expansion_engine import SlideExpansionEngine
    from app.services.presentation.structure_builder import LayeredSlideStructureBuilder
    from app.services.presentation.layout_engine import LayoutConstraintEngine, ZoneLayoutEngine
    from app.services.presentation.layer_zone_models import ZoneType

    pkg = _make_sample_content_pkg()

    # Case A: Visual Priority PRIMARY vs SECONDARY
    slide_primary = LogicalSlidePlan(
        logical_slide_id="VIS_PRIO_TEST",
        structural_role=StructuralRole.HERO_ANALYSIS,
        semantic_topic="PERFORMANCE",
        section_name="Analysis",
        purpose="Analyze",
        headline="Visual Dominance Check",
        content_bindings=[
            ContentBinding(content_id="item-chart-01"),
            ContentBinding(content_id="item-cover-01"),
        ],
        metadata={
            "visual_priority": "PRIMARY",
            "narrative_placement": "BESIDE_VISUAL",
            "composition_decision": {
                "logical_slide_id": "VIS_PRIO_TEST",
                "composition_archetype": "VISUAL_WITH_INSIGHT",
                "visual_priority": "PRIMARY",
                "narrative_placement": "BESIDE_VISUAL",
            },
        },
    )
    story_a = DeckStoryPlan(plan_id="P-A", deck_title="A", deck_subtitle="", executive_thesis="", logical_slides=[slide_primary])
    man_a = SlideExpansionEngine().expand(story_plan=story_a, content_pkg=pkg)
    spec_a = LayeredSlideStructureBuilder().build_structure(manifest=man_a, content_pkg=pkg)

    zone_engine = ZoneLayoutEngine()
    safe_a = zone_engine.resolve_safe_area()
    bounds_a = zone_engine.resolve_zone_bounds(spec_a.slides[0], safe_a)

    vis_zone_a = next(z for z in spec_a.slides[0].zones if z.zone_type == ZoneType.PRIMARY_VISUAL)
    # Visual zone width should be dominant (>= 0.60 * body_width)
    assert bounds_a[vis_zone_a.zone_id].width >= round(safe_a.body_bounds.width * 0.60, 4)

    # Case B: Narrative Placement ABOVE_VISUAL
    slide_above = LogicalSlidePlan(
        logical_slide_id="ABOVE_TEST",
        structural_role=StructuralRole.HERO_ANALYSIS,
        semantic_topic="PERFORMANCE",
        section_name="Analysis",
        purpose="Analyze",
        headline="Above Placement Check",
        content_bindings=[
            ContentBinding(content_id="item-chart-01"),
            ContentBinding(content_id="item-cover-01"),
        ],
        metadata={
            "narrative_placement": "ABOVE_VISUAL",
            "composition_decision": {
                "logical_slide_id": "ABOVE_TEST",
                "composition_archetype": "VISUAL_WITH_INSIGHT",
                "narrative_placement": "ABOVE_VISUAL",
            },
        },
    )
    story_b = DeckStoryPlan(plan_id="P-B", deck_title="B", deck_subtitle="", executive_thesis="", logical_slides=[slide_above])
    man_b = SlideExpansionEngine().expand(story_plan=story_b, content_pkg=pkg)
    spec_b = LayeredSlideStructureBuilder().build_structure(manifest=man_b, content_pkg=pkg)
    bounds_b = zone_engine.resolve_zone_bounds(spec_b.slides[0], safe_a)

    text_zone_b = next(z for z in spec_b.slides[0].zones if z.zone_type == ZoneType.INSIGHT_NARRATIVE)
    vis_zone_b = next(z for z in spec_b.slides[0].zones if z.zone_type == ZoneType.PRIMARY_VISUAL)

    # Narrative zone is placed above visual zone: text_box.top < vis_box.top
    assert bounds_b[text_zone_b.zone_id].top < bounds_b[vis_zone_b.zone_id].top


def test_end_to_end_composition_to_layout_execution():
    from app.services.presentation.expansion_engine import SlideExpansionEngine
    from app.services.presentation.structure_builder import LayeredSlideStructureBuilder
    from app.services.presentation.layout_engine import LayoutConstraintEngine
    from app.services.presentation.layout_models import SlideFitStatus

    pkg = _make_sample_content_pkg()
    slide = LogicalSlidePlan(
        logical_slide_id="E2E_COMP_SLIDE",
        structural_role=StructuralRole.HERO_ANALYSIS,
        semantic_topic="academic_growth_score",  # snake_case triggers LabelSimplificationIntent
        section_name="Academic Results",
        purpose="Analyze student performance and trends",
        headline="pct_proficient_math_score",  # snake_case triggers label simplification
        takeaway="Schools consistently outperformed regional targets.",
        content_bindings=[
            ContentBinding(content_id="item-chart-01"),
            ContentBinding(content_id="item-kpi-01"),
        ],
        visual_type="bar",
    )
    story_plan = DeckStoryPlan(
        plan_id="PLAN-E2E",
        deck_title="Executive Briefing",
        deck_subtitle="Q3 Review",
        executive_thesis="Performance remains high.",
        logical_slides=[slide],
    )

    # 1. Slide Composition Intelligence (PPT-L2.5)
    engine = SlideCompositionEngine(use_ai=False)
    comp_plan = engine.compose_deck(story_plan=story_plan, content_pkg=pkg)
    assert comp_plan.plan_id.startswith("COMP-PLAN-")
    assert len(comp_plan.slide_decisions) == 1

    # 2. Slide Expansion Engine (PPT-L3)
    expansion = SlideExpansionEngine()
    manifest = expansion.expand(story_plan=story_plan, content_pkg=pkg)
    assert len(manifest.slides) == 1

    # 3. Layered Slide Structure Builder (PPT-L4)
    builder = LayeredSlideStructureBuilder()
    struct_deck = builder.build_structure(manifest=manifest, content_pkg=pkg)
    slide_spec = struct_deck.slides[0]

    # 4. Layout Constraint Engine (PPT-L5)
    layout_engine = LayoutConstraintEngine()
    resolved_layout = layout_engine.resolve_slide_layout(slide_spec)

    assert resolved_layout.fit_status == SlideFitStatus.PASS
    assert len(resolved_layout.zones) >= 2

    # 5. Verify Diagnostic Consumption Tracker (Prevent Phantom Composition)
    consumption = slide_spec.metadata.get("composition_consumption", {})
    assert consumption.get("archetype_consumed") is True
    assert consumption.get("content_grouping_consumed") is True
    assert consumption.get("visual_priority_consumed") is True
    assert consumption.get("density_consumed") is True
    assert consumption.get("narrative_placement_consumed") is True
    assert consumption.get("split_intent_consumed") is True
    assert consumption.get("label_intent_consumed") is True


def test_model_router_granite_composition_routing():
    """Confirms ModelRouter routes PRESENTATION_COMPOSITION to Granite and preserves specialized ownership."""
    from app.services.gateway.contracts import AIRequest, AITaskType, ReasoningLevel
    from app.services.gateway.model_router import ModelRouter, TASK_MODEL_CASCADES

    cascade = TASK_MODEL_CASCADES[AITaskType.PRESENTATION_COMPOSITION]
    assert "granite-composition-v1" in cascade
    assert "granite4:3b" in cascade
    assert cascade[0] == "granite-composition-v1"

    req = AIRequest(
        task_type=AITaskType.PRESENTATION_COMPOSITION,
        prompt="Make a composition decision",
        max_latency_ms=8000.0,
        reasoning_level=ReasoningLevel.LOW,
    )
    candidates = ModelRouter.route_ai_request(req)
    assert candidates[0] == "granite-composition-v1"
    assert not any("phi" in c for c in candidates)


def test_ai_composition_provider_provenance_and_granite_tagging():
    """Verifies AICompositionProvider tags Granite provenance and metadata correctly on success."""
    import json
    pkg = _make_sample_content_pkg()
    slide = LogicalSlidePlan(
        logical_slide_id="GRANITE_PROVENANCE_SLIDE",
        structural_role=StructuralRole.HERO_ANALYSIS,
        semantic_topic="Store Performance",
        section_name="Retail",
        purpose="Analyze stores",
        headline="Store Sales Accelerate",
        content_bindings=[ContentBinding(content_id="item-chart-01")],
        visual_type="bar",
    )

    valid_granite_payload = {
        "logical_slide_id": "GRANITE_PROVENANCE_SLIDE",
        "composition_archetype": "VISUAL_WITH_INSIGHT",
        "primary_content_id": "item-chart-01",
        "visual_priority": "PRIMARY",
        "density_intent": "BALANCED",
        "narrative_placement": "BESIDE_VISUAL",
        "supporting_content_ids": [],
        "content_groups": [
            {"role": "PRIMARY_VISUAL", "content_ids": ["item-chart-01"]}
        ],
        "split_intent": "SPLIT_IF_REQUIRED",
        "label_intents": [],
        "reason_codes": ["GRANITE_COMPOSED"],
        "confidence": 0.94,
    }

    from app.services.gateway.contracts import AIResponse, AIExecutionRecord, AITaskType
    mock_resp = AIResponse(
        raw_text=json.dumps(valid_granite_payload),
        parsed=CompositionDecision.model_validate(valid_granite_payload),
        execution_record=AIExecutionRecord(
            request_id="test",
            task_type=AITaskType.PRESENTATION_COMPOSITION,
            model="granite-composition-v1",
            structured_input_hash="h1",
            structured_output_hash="h2",
            latency_ms=250.0,
            fallback_used=False,
            models_attempted=["granite-composition-v1"],
            entitlement_status="PASS",
            tokens_used=120,
            success=True,
        ),
        success=True,
    )

    with patch("app.services.gateway.model_gateway.ModelGateway.execute", return_value=mock_resp):
        provider = AICompositionProvider(use_ai=True)
        decision = provider.compose_slide(slide, pkg)

        assert decision.decision_source == CompositionDecisionSource.AI_MODEL
        assert decision.metadata.get("model_family") == "GRANITE"
        assert decision.metadata.get("base_model") in ("granite4:3b", "mlx-community/granite-4.0-h-micro-4bit")
        assert "granite" in decision.metadata.get("adapter_name").lower()
        assert decision.metadata.get("adapter_version") == "v1"
        assert decision.metadata.get("fallback_used") is False
        assert decision.confidence == 0.94


def test_ai_composition_provider_confidence_threshold_fallback():
    """Verifies that confidence below threshold (0.65) activates deterministic fallback with telemetry."""
    import json
    pkg = _make_sample_content_pkg()
    slide = LogicalSlidePlan(
        logical_slide_id="LOW_CONF_SLIDE",
        structural_role=StructuralRole.HERO_ANALYSIS,
        semantic_topic="Store Performance",
        section_name="Retail",
        purpose="Analyze stores",
        headline="Store Sales Accelerate",
        content_bindings=[ContentBinding(content_id="item-chart-01")],
        visual_type="bar",
    )

    low_conf_payload = {
        "logical_slide_id": "LOW_CONF_SLIDE",
        "composition_archetype": "VISUAL_WITH_INSIGHT",
        "primary_content_id": "item-chart-01",
        "visual_priority": "PRIMARY",
        "density_intent": "BALANCED",
        "narrative_placement": "BESIDE_VISUAL",
        "supporting_content_ids": [],
        "content_groups": [
            {"role": "PRIMARY_VISUAL", "content_ids": ["item-chart-01"]}
        ],
        "split_intent": "SPLIT_IF_REQUIRED",
        "label_intents": [],
        "reason_codes": ["UNCERTAIN"],
        "confidence": 0.42,
    }

    from app.services.gateway.contracts import AIResponse, AIExecutionRecord, AITaskType
    mock_resp = AIResponse(
        raw_text=json.dumps(low_conf_payload),
        parsed=CompositionDecision.model_validate(low_conf_payload),
        execution_record=AIExecutionRecord(
            request_id="test-low-conf",
            task_type=AITaskType.PRESENTATION_COMPOSITION,
            model="granite-composition-v1",
            structured_input_hash="h1",
            structured_output_hash="h2",
            latency_ms=250.0,
            fallback_used=False,
            models_attempted=["granite-composition-v1"],
            entitlement_status="PASS",
            tokens_used=120,
            success=True,
        ),
        success=True,
    )

    with patch("app.services.gateway.model_gateway.ModelGateway.execute", return_value=mock_resp):
        provider = AICompositionProvider(use_ai=True)
        decision = provider.compose_slide(slide, pkg)

        assert decision.decision_source == CompositionDecisionSource.DETERMINISTIC_FALLBACK
        assert "LOW_CONFIDENCE" in decision.fallback_reason
        assert decision.metadata.get("fallback_used") is True
        assert decision.metadata.get("model_family") == "GRANITE"
        assert decision.metadata["failure_telemetry"]["failure_type"] == "LOW_CONFIDENCE"


def test_ai_composition_provider_ungrounded_id_fallback():
    """Verifies that hallucinated/ungrounded content IDs trigger validation failure and fallback."""
    import json
    pkg = _make_sample_content_pkg()
    slide = LogicalSlidePlan(
        logical_slide_id="UNGROUNDED_SLIDE",
        structural_role=StructuralRole.HERO_ANALYSIS,
        semantic_topic="Store Performance",
        section_name="Retail",
        purpose="Analyze stores",
        headline="Store Sales Accelerate",
        content_bindings=[ContentBinding(content_id="item-chart-01")],
        visual_type="bar",
    )

    hallucinated_payload = {
        "logical_slide_id": "UNGROUNDED_SLIDE",
        "composition_archetype": "VISUAL_WITH_INSIGHT",
        "primary_content_id": "hallucinated_item_999",
        "visual_priority": "PRIMARY",
        "density_intent": "BALANCED",
        "narrative_placement": "BESIDE_VISUAL",
        "supporting_content_ids": [],
        "content_groups": [
            {"role": "PRIMARY_VISUAL", "content_ids": ["hallucinated_item_999"]}
        ],
        "split_intent": "SPLIT_IF_REQUIRED",
        "label_intents": [],
        "reason_codes": ["HALLUCINATION_TEST"],
        "confidence": 0.95,
    }

    from app.services.gateway.contracts import AIResponse, AIExecutionRecord, AITaskType
    mock_resp = AIResponse(
        raw_text=json.dumps(hallucinated_payload),
        parsed=CompositionDecision.model_validate(hallucinated_payload),
        execution_record=AIExecutionRecord(
            request_id="test-hallucinated",
            task_type=AITaskType.PRESENTATION_COMPOSITION,
            model="granite-composition-v1",
            structured_input_hash="h1",
            structured_output_hash="h2",
            latency_ms=250.0,
            fallback_used=False,
            models_attempted=["granite-composition-v1"],
            entitlement_status="PASS",
            tokens_used=120,
            success=True,
        ),
        success=True,
    )

    with patch("app.services.gateway.model_gateway.ModelGateway.execute", return_value=mock_resp):
        provider = AICompositionProvider(use_ai=True)
        decision = provider.compose_slide(slide, pkg)

        assert decision.decision_source == CompositionDecisionSource.DETERMINISTIC_FALLBACK
        assert "UNGROUNDED_ID" in decision.fallback_reason
        assert decision.metadata["failure_telemetry"]["failure_type"] == "UNGROUNDED_ID"



