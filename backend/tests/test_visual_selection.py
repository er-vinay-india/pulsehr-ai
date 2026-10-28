"""Targeted unit tests for Visual Selection Intelligence.

Tests the boundary:
Evidence / Content -> DataShapeProfile -> VisualCandidateGenerator -> VisualSelectionDecision
-> VisualSelectionValidator -> Canonical PresentationVisualSpec -> StoryPlanner -> Granite Composition (Read-Only) -> Renderer.
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
from app.services.presentation.presentation_visual_spec import (
    PresentationVisualSpec,
    VisualFamily,
)
from app.services.presentation.story_models import (
    ContentBindingRole,
    DeckStoryPlan,
    LogicalSlidePlan,
    StructuralRole,
)
from app.services.presentation.visual_selection import (
    AIVisualSelectionProvider,
    DataShapeProfile,
    DeterministicVisualSelectionProvider,
    PresentationVisualSpecBuilder,
    VisualCandidateGenerator,
    VisualSelectionDecision,
    VisualSelectionIntelligence,
    VisualSelectionSource,
    VisualSelectionValidator,
)
from app.services.presentation.visual_selection.normalization import normalize_to_visual_family


def test_normalization_adapter():
    """Verifies that legacy ChartFamily and raw strings normalize cleanly to canonical VisualFamily.
    Unknown strings return None rather than making premature semantic decisions.
    """
    assert normalize_to_visual_family("line_chart") == VisualFamily.LINE
    assert normalize_to_visual_family("bar") == VisualFamily.BAR
    assert normalize_to_visual_family("ranked_bar") == VisualFamily.RANKED_BAR
    assert normalize_to_visual_family("column") == VisualFamily.BAR
    assert normalize_to_visual_family("doughnut") == VisualFamily.DONUT
    assert normalize_to_visual_family("map") == VisualFamily.MAP
    assert normalize_to_visual_family("bubble_map") == VisualFamily.MAP
    assert normalize_to_visual_family("choropleth") == VisualFamily.CHOROPLETH
    assert normalize_to_visual_family("scatter") == VisualFamily.SCATTER
    assert normalize_to_visual_family("scenario_card") == VisualFamily.SCENARIO_CARD
    # Neutral unresolved: unknown string must NOT prematurely become BAR or DATA_TABLE
    assert normalize_to_visual_family("unknown_random_chart") is None
    assert normalize_to_visual_family(None) is None


def test_capability_registry_completeness():
    """Verifies every canonical VisualFamily member has a corresponding entry in CHART_CAPABILITY_REGISTRY."""
    from app.services.presentation.presentation_visual_spec import CHART_CAPABILITY_REGISTRY

    all_families = set(VisualFamily)
    registry_families = set(CHART_CAPABILITY_REGISTRY.keys())

    unbound = all_families - registry_families
    extra = registry_families - all_families

    assert len(unbound) == 0, f"Unbound visual families detected: {unbound}"
    assert len(extra) == 0, f"Extra registry entries detected: {extra}"
    assert len(all_families) == 22, f"Expected exactly 22 VisualFamily members, found {len(all_families)}"


def test_candidate_generator_emits_only_canonical_families():
    """Verifies that every candidate emitted across various profiles is in VisualFamily & CHART_CAPABILITY_REGISTRY."""
    from app.services.presentation.presentation_visual_spec import CHART_CAPABILITY_REGISTRY

    gen = VisualCandidateGenerator()
    test_profiles = [
        DataShapeProfile(content_id="P1", is_scenario=True),
        DataShapeProfile(content_id="P2", is_geographic=True),
        DataShapeProfile(content_id="P3", continuous_dimension_count=2),
        DataShapeProfile(content_id="P4", is_distribution=True),
        DataShapeProfile(content_id="P5", is_temporal=True, category_count=8),
        DataShapeProfile(content_id="P6", is_ranked=True, category_count=3),
        DataShapeProfile(content_id="P7", is_record_detail=True, row_count=25),
        DataShapeProfile(content_id="P8", metric_count=1, category_count=1),
        DataShapeProfile(content_id="P9", max_label_length=20, category_count=10),
    ]

    for prof in test_profiles:
        candidates = gen.generate_candidates(prof)
        assert len(candidates) > 0, f"Profile {prof.content_id} returned empty candidates"
        for cand in candidates:
            assert isinstance(cand, VisualFamily), f"Candidate {cand} is not a VisualFamily instance"
            assert cand in CHART_CAPABILITY_REGISTRY, f"Candidate {cand} is not in CHART_CAPABILITY_REGISTRY"


def test_unknown_visual_delegates_to_data_shape_selection():
    """Verifies that an existing visual with an unknown type is not blindly reused, but delegates to data shape."""
    provider = DeterministicVisualSelectionProvider()

    # Temporal profile with completely unknown existing visual type
    profile = DataShapeProfile(
        content_id="ITEM-TEMP-UNKNOWN",
        is_temporal=True,
        category_count=6,
        has_existing_visual=True,
        existing_visual_type="some_unsupported_3d_mesh_chart",
        existing_visual_id="UNKNOWN-V1",
        source_surface="dashboard",
    )
    cands = VisualCandidateGenerator().generate_candidates(profile)
    decision = provider.select_visual("ITEM-TEMP-UNKNOWN", profile, cands)

    # Must NOT blindly reuse as BAR or claim SOURCE_VISUAL_REUSED
    assert decision.selected_visual_family == VisualFamily.LINE
    assert decision.reuse_strategy == VisualStrategy.PRESENTATION_RECOMMENDATION
    assert "TIME_SERIES_PRIMARY" in decision.reason_codes
    assert "SOURCE_VISUAL_REUSED" not in decision.reason_codes


def test_data_shape_profiler():
    """Verifies deterministic profiling across temporal, geographic, scenario, distribution, and ranked items."""
    service = VisualSelectionIntelligence()

    # 1. Temporal Item
    temporal_item = PresentationContentItem(
        content_id="ITEM-TEMP-01",
        role=ContentRole.KEY_FINDING,
        kind=ContentKind.CHART,
        topic_category="Attrition Trends",
        title="Quarterly Attrition Trend 2023-2024",
        metric_name="Attrition Rate",
        metric_value="14.2%",
        visual_type="line",
        visual_spec={
            "chart_type": "line",
            "categories": ["Q1 2023", "Q2 2023", "Q3 2023", "Q4 2023"],
            "series": [{"name": "Attrition Rate", "values": [12.1, 13.5, 13.9, 14.2]}],
        },
    )
    profile_temp = service.profile_content_item(temporal_item)
    assert profile_temp.is_temporal is True
    assert profile_temp.category_count == 4
    assert profile_temp.metric_count == 1
    assert profile_temp.is_scenario is False

    # 2. Geographic Map Item
    geo_item = PresentationContentItem(
        content_id="ITEM-GEO-01",
        role=ContentRole.KEY_FINDING,
        kind=ContentKind.MAP,
        topic_category="Regional Density",
        title="Employee Distribution by State Territory",
        visual_type="choropleth",
        source_surface="dashboard",
        visual_id="GEO-MAP-01",
    )
    profile_geo = service.profile_content_item(geo_item)
    assert profile_geo.is_geographic is True
    assert profile_geo.has_existing_visual is True

    # 3. Scenario Card Item (Safety Guarantee)
    scen_item = PresentationContentItem(
        content_id="ITEM-SCEN-01",
        role=ContentRole.KEY_FINDING,
        kind=ContentKind.CHART,
        topic_category="Policy Simulation",
        title="Compensation Adjustment Counterfactual Scenario",
        visual_id="SCEN-COMP-01",
        visual_type="scenario_card",
        visual_spec={"scenario_name": "Tier 1 Base Bump", "impact": "-2.4% attrition"},
    )
    profile_scen = service.profile_content_item(scen_item)
    assert profile_scen.is_scenario is True

    # 4. Distribution Item
    dist_item = PresentationContentItem(
        content_id="ITEM-DIST-01",
        role=ContentRole.KEY_FINDING,
        kind=ContentKind.CHART,
        topic_category="Salary Dispersion",
        title="Salary Dispersion and Outlier Spread across Bands",
        visual_type="box_plot",
    )
    profile_dist = service.profile_content_item(dist_item)
    assert profile_dist.is_distribution is True


def test_candidate_generator():
    """Verifies that VisualCandidateGenerator returns prioritized, constrained candidate sets."""
    gen = VisualCandidateGenerator()

    # Scenario profile must strictly suggest SCENARIO_CARD
    scen_profile = DataShapeProfile(content_id="SCEN-01", is_scenario=True)
    cands_scen = gen.generate_candidates(scen_profile)
    assert len(cands_scen) >= 1
    assert cands_scen[0] == VisualFamily.SCENARIO_CARD

    # Geographic profile must strictly prioritize CHOROPLETH / BUBBLE_MAP
    geo_profile = DataShapeProfile(content_id="GEO-01", is_geographic=True)
    cands_geo = gen.generate_candidates(geo_profile)
    assert cands_geo[0] == VisualFamily.CHOROPLETH

    # Temporal profile with multiple points must prioritize LINE
    temp_profile = DataShapeProfile(content_id="TEMP-01", is_temporal=True, category_count=6)
    cands_temp = gen.generate_candidates(temp_profile)
    assert cands_temp[0] == VisualFamily.LINE


def test_deterministic_provider_reuse_first():
    """Verifies 'same visual first, editability second' policy."""
    provider = DeterministicVisualSelectionProvider()

    # Existing choropleth map from dashboard must be reused
    profile = DataShapeProfile(
        content_id="ITEM-MAP-01",
        is_geographic=True,
        has_existing_visual=True,
        existing_visual_type="choropleth",
        existing_visual_id="MAP-V1",
        source_surface="dashboard",
    )
    cands = VisualCandidateGenerator().generate_candidates(profile)
    decision = provider.select_visual("ITEM-MAP-01", profile, cands)
    assert decision.selected_visual_family == VisualFamily.CHOROPLETH
    assert decision.reuse_strategy == VisualStrategy.REUSE_EXISTING
    assert "SOURCE_VISUAL_REUSED" in decision.reason_codes
    assert "SAME_VISUAL_PRIORITY" in decision.reason_codes


def test_validator_and_grounded_fallback():
    """Verifies VisualSelectionValidator rejects unsupported/incompatible selections and flags errors."""
    validator = VisualSelectionValidator()
    profile = DataShapeProfile(content_id="ITEM-01", is_temporal=True, category_count=5)
    candidates = VisualCandidateGenerator().generate_candidates(profile)

    # Valid candidate passes with 0 errors
    valid_dec = VisualSelectionDecision(
        content_id="ITEM-01",
        selected_visual_family=VisualFamily.LINE,
        confidence=1.0,
        reason_codes=["TEST_VALID"],
    )
    errors = validator.validate(valid_dec, profile, candidates)
    assert len(errors) == 0

    # Incompatible selection (e.g. SCENARIO_CARD on non-scenario temporal data) flags validation errors
    invalid_dec = VisualSelectionDecision(
        content_id="ITEM-01",
        selected_visual_family=VisualFamily.SCENARIO_CARD,
        confidence=0.8,
        reason_codes=["BAD_CHOICE"],
    )
    errors_invalid = validator.validate(invalid_dec, profile, candidates)
    assert len(errors_invalid) > 0

    # Non-canonical family value is caught by validator
    non_canonical_dec = VisualSelectionDecision.model_construct(
        content_id="ITEM-01",
        selected_visual_family="NON_CANONICAL_BUBBLE_MAP",
        confidence=0.5,
        reason_codes=["BAD_FAMILY"],
    )
    errors_fam = validator.validate(non_canonical_dec, profile, candidates)
    assert any("not a canonical VisualFamily enum member" in e for e in errors_fam)


def test_spec_builder_creates_canonical_spec():
    """Verifies PresentationVisualSpecBuilder creates a rich, validated PresentationVisualSpec."""
    builder = PresentationVisualSpecBuilder()
    item = PresentationContentItem(
        content_id="ITEM-ATTR-01",
        role=ContentRole.KEY_FINDING,
        kind=ContentKind.CHART,
        topic_category="Attrition",
        title="Quarterly Attrition 2024",
        metric_name="Attrition %",
        metric_value="14.2%",
        visual_type="line",
        visual_spec={
            "chart_type": "line",
            "categories": ["Q1", "Q2", "Q3", "Q4"],
            "series": [{"name": "Attrition %", "values": [12.0, 13.1, 14.0, 14.2]}],
        },
    )
    profile = VisualSelectionIntelligence().profile_content_item(item)
    decision = VisualSelectionDecision(
        content_id=item.content_id,
        selected_visual_family=VisualFamily.LINE,
        reuse_strategy=VisualStrategy.REUSE_EXISTING,
        visual_completeness=VisualCompleteness.COMPLETE_VISUAL,
        confidence=1.0,
        reason_codes=["REUSE_EXISTING"],
    )
    spec = builder.build_spec(item, decision, profile)

    assert isinstance(spec, PresentationVisualSpec)
    assert spec.family == VisualFamily.LINE
    assert spec.categories == ["Q1", "Q2", "Q3", "Q4"]
    assert len(spec.series) == 1
    assert spec.series[0].values == [12.0, 13.1, 14.0, 14.2]
    assert spec.reuse_strategy == "REUSE_EXISTING"
    assert spec.is_scenario is False
    assert "REUSE_EXISTING" in spec.reason_codes


def test_story_planner_neutralization_and_granite_immutability():
    """Verifies that StoryPlanner does not decide visual archetype and Granite Composition does not mutate visuals."""
    # 1. Package with processed visual specs
    service = VisualSelectionIntelligence()
    item = PresentationContentItem(
        content_id="ITEM-RANK-01",
        role=ContentRole.KEY_FINDING,
        kind=ContentKind.CHART,
        topic_category="Tenure Analysis",
        title="Tenure Distribution by Department",
        visual_type="bar",
        visual_spec={
            "categories": ["Sales", "Eng", "Ops"],
            "series": [{"name": "Avg Tenure", "values": [2.4, 4.1, 3.2]}],
        },
    )
    pkg = PresentationContentPackage(
        package_id="PKG-TEST-01",
        dataset_name="pulsehr_analytics",
        domain="workforce",
        title="Test Package",
        items=[item],
        global_kpis=[],
    )
    enriched_pkg = service.process_content_package(pkg)
    assert enriched_pkg.items[0].presentation_visual_spec is not None
    assert enriched_pkg.items[0].visual_type == "bar"

    # 2. Plan Story
    from app.services.presentation.story_planner import StoryPlanner
    planner = StoryPlanner(use_ai=False)
    deck_plan = planner.plan_story(enriched_pkg, user_objective="Analyze Tenure")

    # Verify findings slide has neutralized preferred_archetype (None) so Composition Intelligence owns it
    findings_slide = next(
        (s for s in deck_plan.logical_slides if s.structural_role not in (StructuralRole.TITLE, StructuralRole.AGENDA, StructuralRole.CLOSING)),
        None
    )
    assert findings_slide is not None
    assert findings_slide.preferred_archetype is None  # StoryPlanner does NOT dictate archetype!
    assert findings_slide.visual_type == "bar"
    assert findings_slide.presentation_visual_spec is not None

    # 3. Slide Composition Intelligence
    from app.services.presentation.composition import SlideCompositionEngine
    composition_engine = SlideCompositionEngine(use_ai=False)

    spec_hash_before = findings_slide.presentation_visual_spec.semantic_hash
    composition_plan = composition_engine.compose_deck(deck_plan, enriched_pkg)

    # Preferred archetype is now assigned by Composition Intelligence
    assert findings_slide.preferred_archetype is not None
    # Visual representation was NOT mutated by Composition Intelligence
    assert findings_slide.visual_type == "bar"
    assert findings_slide.presentation_visual_spec.semantic_hash == spec_hash_before


def test_renderer_adapter_governed_fallback():
    """Verifies that ChartRendererAdapter records governed fallback telemetry when fallback occurs."""
    from unittest.mock import MagicMock
    from app.services.presentation.renderer_adapters import ChartRendererAdapter
    from app.services.presentation.layout_models import Box2D, EditabilityPolicy, ResolvedObjectLayout
    from app.services.presentation.layer_zone_models import LayeredSlideSpec
    from app.services.presentation.render_models import RenderMode, RenderedObjectRecord, ShapeType

    mock_raster = MagicMock()
    mock_raster_record = RenderedObjectRecord(
        object_id="OBJ_CHART_01",
        object_name="HV_CHART_01",
        zone_id="ZONE_01",
        physical_slide_id="SLIDE_01",
        shape_id=99,
        shape_type=ShapeType.PICTURE,
        is_native_editable=False,
        editability_policy=EditabilityPolicy.NATIVE_PREFERRED,
        applied_bounds=Box2D(left=0.1, top=0.1, width=0.8, height=0.8),
        render_mode=RenderMode.PRESERVED_IMAGE,
        metadata={},
    )
    mock_raster.render.return_value = (MagicMock(), mock_raster_record)

    adapter = ChartRendererAdapter(raster_fallback_adapter=mock_raster)

    # Object layout requesting native bar chart
    obj_layout = ResolvedObjectLayout(
        object_id="OBJ_CHART_01",
        object_name="HV_CHART_01",
        name="Chart Object",
        binding_role=ContentBindingRole.PRIMARY,
        content_id="ITEM-01",
        kind=ContentKind.CHART,
        editability=EditabilityPolicy.NATIVE_PREFERRED,
        bounds=Box2D(left=0.1, top=0.1, width=0.8, height=0.8),
        metadata={
            "visual_type": "bar",
            "presentation_visual_spec": {"family": "bar"},
        },
    )
    slide_spec = MagicMock()
    slide_spec.physical_slide_id = "SLIDE_01"

    # Simulate slide that raises on add_chart to force governed fallback
    slide = MagicMock()
    slide.shapes.add_chart.side_effect = RuntimeError("Simulated DrawingML failure")

    shape, record = adapter._render_internal(
        slide=slide,
        obj_layout=obj_layout,
        slide_spec=slide_spec,
        content_item=None,
        slide_w_emu=9144000,
        slide_h_emu=5143500,
    )

    assert record.fallback_applied is True
    assert "DrawingML chart creation failed" in (record.fallback_reason or "")
    assert record.metadata["original_visual"] == "bar"
    assert record.metadata["fallback_visual"] == "raster"
    assert record.metadata["canonical_visual_family"] == "bar"


# ==============================================================================
# AI-ASSISTED VISUAL SELECTION OVER DETERMINISTIC CANDIDATE SET
# ==============================================================================

def test_ai_provider_selects_from_valid_candidates():
    """Verifies that AIVisualSelectionProvider selects cleanly among the valid candidates."""
    provider = AIVisualSelectionProvider(use_ai=True)

    profile = DataShapeProfile(
        content_id="ITEM-TREND-01",
        is_temporal=True,
        category_count=6,
    )
    candidates = [VisualFamily.LINE, VisualFamily.TREND, VisualFamily.BAR, VisualFamily.DATA_TABLE]

    mock_ai = {
        "selected_visual_family": "line",
        "selected_visual_variant": "standard",
        "reason_codes": ["CHRONOLOGICAL_FLOW", "CONTINUOUS_TRAJECTORY"],
        "confidence": 0.95,
        "diagnostic_notes": "Line chart clearly expresses the multi-period attrition trend.",
    }

    item = PresentationContentItem(
        content_id="ITEM-TREND-01",
        role=ContentRole.KEY_FINDING,
        kind=ContentKind.CHART,
        topic_category="Attrition",
        title="Monthly Attrition Trajectory",
    )

    decision = provider.select_visual(
        content_id="ITEM-TREND-01",
        profile=profile,
        candidates=candidates,
        analytical_intent="Attrition",
        content_item=item,
        metadata={"mock_ai_response": mock_ai},
    )

    assert decision.selected_visual_family == VisualFamily.LINE
    assert decision.decision_source == VisualSelectionSource.AI_MODEL
    assert decision.confidence == 0.95
    assert "CHRONOLOGICAL_FLOW" in decision.reason_codes
    assert decision.selected_visual_family in candidates


def test_ai_provider_rejects_hallucinated_family_and_falls_back():
    """Verifies that if AI returns a family outside the valid candidates list, it is rejected and falls back."""
    provider = AIVisualSelectionProvider(use_ai=True)

    profile = DataShapeProfile(
        content_id="ITEM-TREND-02",
        is_temporal=True,
        category_count=6,
    )
    candidates = [VisualFamily.LINE, VisualFamily.TREND, VisualFamily.BAR, VisualFamily.DATA_TABLE]

    # AI attempts to invent or choose an invalid/non-candidate family (e.g. pie)
    mock_ai = {
        "selected_visual_family": "pie",
        "selected_visual_variant": "standard",
        "reason_codes": ["WRONG_CHOICE"],
        "confidence": 0.9,
    }

    decision = provider.select_visual(
        content_id="ITEM-TREND-02",
        profile=profile,
        candidates=candidates,
        analytical_intent="Attrition",
        metadata={"mock_ai_response": mock_ai},
    )

    # Invariant: AI choice outside candidates is strictly rejected, deterministic fallback is invoked
    assert decision.decision_source == VisualSelectionSource.DETERMINISTIC_FALLBACK
    assert decision.selected_visual_family == VisualFamily.LINE  # deterministic derivation chooses LINE
    assert any("AI_FALLBACK" in r for r in decision.reason_codes)


def test_ai_provider_rejects_low_confidence_and_falls_back():
    """Verifies that if AI confidence falls below threshold, deterministic fallback is invoked."""
    provider = AIVisualSelectionProvider(use_ai=True, confidence_threshold=0.8)

    profile = DataShapeProfile(
        content_id="ITEM-RANK-01",
        is_ranked=True,
        category_count=4,
    )
    candidates = [VisualFamily.RANKED_BAR, VisualFamily.HORIZONTAL_BAR, VisualFamily.DATA_TABLE]

    mock_ai = {
        "selected_visual_family": "ranked_bar",
        "confidence": 0.5,  # below 0.8
    }

    decision = provider.select_visual(
        content_id="ITEM-RANK-01",
        profile=profile,
        candidates=candidates,
        analytical_intent="Rankings",
        metadata={"mock_ai_response": mock_ai},
    )

    assert decision.decision_source == VisualSelectionSource.DETERMINISTIC_FALLBACK
    assert any("AI_FALLBACK" in r for r in decision.reason_codes)


def test_ai_provider_rejects_malformed_json_and_falls_back():
    """Verifies that if AI output is malformed, deterministic fallback is cleanly triggered."""
    provider = AIVisualSelectionProvider(use_ai=True)

    profile = DataShapeProfile(
        content_id="ITEM-MALFORMED",
        is_temporal=True,
        category_count=5,
    )
    candidates = [VisualFamily.LINE, VisualFamily.BAR, VisualFamily.DATA_TABLE]

    decision = provider.select_visual(
        content_id="ITEM-MALFORMED",
        profile=profile,
        candidates=candidates,
        metadata={"mock_ai_response": "Broken text without valid JSON {{{{}"},
    )

    assert decision.decision_source == VisualSelectionSource.DETERMINISTIC_FALLBACK
    assert decision.selected_visual_family in candidates


def test_ai_provider_bypasses_ai_for_reusable_source_visual():
    """Verifies 'same visual first' invariant: trustworthy source visual from dashboard bypasses AI entirely."""
    provider = AIVisualSelectionProvider(use_ai=True)

    profile = DataShapeProfile(
        content_id="ITEM-REUSE-01",
        is_geographic=True,
        has_existing_visual=True,
        existing_visual_type="choropleth",
        existing_visual_id="GEO-01",
        source_surface="dashboard",
    )
    candidates = [VisualFamily.CHOROPLETH, VisualFamily.MAP, VisualFamily.RANKED_BAR]

    # Even if mock_ai would choose something else, AI is never invoked for trusted existing visual
    decision = provider.select_visual(
        content_id="ITEM-REUSE-01",
        profile=profile,
        candidates=candidates,
        metadata={"mock_ai_response": {"selected_visual_family": "map"}},
    )

    assert decision.decision_source == VisualSelectionSource.REUSE_EXISTING
    assert decision.selected_visual_family == VisualFamily.CHOROPLETH
    assert decision.reuse_strategy == VisualStrategy.REUSE_EXISTING


def test_ai_provider_bypasses_ai_for_single_candidate():
    """Verifies that when only 1 candidate exists, AI arbitration is bypassed."""
    provider = AIVisualSelectionProvider(use_ai=True)

    profile = DataShapeProfile(
        content_id="ITEM-SINGLE",
        metric_count=1,
        category_count=1,
    )
    candidates = [VisualFamily.KPI_CARD]

    decision = provider.select_visual(
        content_id="ITEM-SINGLE",
        profile=profile,
        candidates=candidates,
        metadata={"mock_ai_response": {"selected_visual_family": "bar"}},
    )

    # Invariant: single candidate does not invoke AI
    assert decision.selected_visual_family == VisualFamily.KPI_CARD
    assert decision.decision_source == VisualSelectionSource.DETERMINISTIC_SELECTION


def test_ai_provider_strictly_rejects_alias_and_does_not_normalize():
    """Verifies invariant: AI output is NEVER normalized or repaired.
    
    If AI returns an alias such as 'area' (which normalizes to LINE in legacy metadata)
    when candidates are [LINE, TREND, BAR], it must be strictly rejected and fall back.
    """
    provider = AIVisualSelectionProvider(use_ai=True)

    profile = DataShapeProfile(
        content_id="ITEM-ALIAS-01",
        is_temporal=True,
        category_count=6,
    )
    candidates = [VisualFamily.LINE, VisualFamily.TREND, VisualFamily.BAR]

    # AI returns alias 'area' which normalize_to_visual_family would have converted to LINE
    mock_ai = {
        "selected_visual_family": "area",
        "selected_visual_variant": "standard",
        "reason_codes": ["AI_ALIAS_TEST"],
        "confidence": 0.95,
    }

    decision = provider.select_visual(
        content_id="ITEM-ALIAS-01",
        profile=profile,
        candidates=candidates,
        analytical_intent="Attrition",
        metadata={"mock_ai_response": mock_ai},
    )

    # Invariant: rejected as non-candidate, falls back to deterministic provider
    assert decision.decision_source == VisualSelectionSource.DETERMINISTIC_FALLBACK
    assert any("AI_FALLBACK:VisualSelectionValidationError" in r for r in decision.reason_codes)
    assert decision.selected_visual_family == VisualFamily.LINE  # deterministic derivation chooses LINE


def test_ai_provider_strictly_rejects_column_alias_and_does_not_normalize():
    """Verifies that 'column' alias (legacy alias of BAR) is strictly rejected from AI output."""
    provider = AIVisualSelectionProvider(use_ai=True)

    profile = DataShapeProfile(
        content_id="ITEM-ALIAS-02",
        category_count=4,
    )
    candidates = [VisualFamily.BAR, VisualFamily.DATA_TABLE]

    mock_ai = {
        "selected_visual_family": "column",
        "selected_visual_variant": "standard",
        "reason_codes": ["AI_COLUMN_TEST"],
        "confidence": 0.95,
    }

    decision = provider.select_visual(
        content_id="ITEM-ALIAS-02",
        profile=profile,
        candidates=candidates,
        metadata={"mock_ai_response": mock_ai},
    )

    assert decision.decision_source == VisualSelectionSource.DETERMINISTIC_FALLBACK
    assert any("AI_FALLBACK:VisualSelectionValidationError" in r for r in decision.reason_codes)


def test_ai_provider_rejects_unknown_family_and_falls_back():
    """Verifies that completely unknown or invented family names are rejected and fall back."""
    provider = AIVisualSelectionProvider(use_ai=True)

    profile = DataShapeProfile(
        content_id="ITEM-UNKNOWN-01",
        category_count=4,
    )
    candidates = [VisualFamily.BAR, VisualFamily.DATA_TABLE]

    mock_ai = {
        "selected_visual_family": "quantum_chart",
        "selected_visual_variant": "standard",
        "reason_codes": ["INVENTED_CHART"],
        "confidence": 0.95,
    }

    decision = provider.select_visual(
        content_id="ITEM-UNKNOWN-01",
        profile=profile,
        candidates=candidates,
        metadata={"mock_ai_response": mock_ai},
    )

    assert decision.decision_source == VisualSelectionSource.DETERMINISTIC_FALLBACK
    assert any("AI_FALLBACK:VisualSelectionValidationError" in r for r in decision.reason_codes)


def test_visual_selection_confidence_threshold_single_source():
    """Verifies that PRESENTATION_VISUAL_SELECTION_CONFIDENCE_THRESHOLD in config.py is the single authoritative source."""
    from app.core import config
    from app.services.presentation.visual_selection import selection_models

    # Authoritative source in config
    assert config.PRESENTATION_VISUAL_SELECTION_CONFIDENCE_THRESHOLD == 0.60

    # selection_models must NOT contain duplicate numeric definitions
    assert not hasattr(selection_models, "DEFAULT_VISUAL_SELECTION_CONFIDENCE_THRESHOLD")
    assert not hasattr(selection_models, "VISUAL_SELECTION_CONFIDENCE_THRESHOLD")

    # AIVisualSelectionProvider directly reads config.PRESENTATION_VISUAL_SELECTION_CONFIDENCE_THRESHOLD
    provider = AIVisualSelectionProvider()
    assert provider.confidence_threshold == config.PRESENTATION_VISUAL_SELECTION_CONFIDENCE_THRESHOLD


def test_model_router_visual_selection_unassigned_and_no_phi():
    """Verifies that Visual Selection model selection is decoupled, unassigned, and does not include Phi."""
    from app.services.gateway.contracts import AITaskType
    from app.services.gateway.model_router import TASK_MODEL_CASCADES

    cascade = TASK_MODEL_CASCADES[AITaskType.PRESENTATION_VISUAL_SELECTION]
    # Phi is strictly Typography specialist; must NOT be assigned to visual selection
    assert not any("phi" in m.lower() for m in cascade)
    # Granite is strictly Composition specialist; must NOT be in visual selection cascade
    assert not any("granite-composition" in m.lower() for m in cascade)


