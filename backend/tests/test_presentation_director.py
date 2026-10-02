import json
import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch

from app.core import config

pytestmark = [pytest.mark.presentation]
from app.services.gateway.model_gateway import GatewayResult
from app.services.presentation.director import (
    AudienceSeniority,
    DeliveryMode,
    InformationDestination,
    InformationSourceType,
    InformationUnit,
    NarrativeArcType,
    NarrativeStrategy,
    PlanningValidationResult,
    PresentationIntent,
    PresentationPlanningContext,
    PresentationPlanSpec,
    PresentationSection,
    SlideCountConstraint,
    SlideCountMode,
    SlidePlan,
    VisualIntent,
    PresentationDirector,
    presentation_director,
    adapt_plan_to_deck_spec,
    plan_intent,
    extract_and_triage_information,
    plan_narrative,
    plan_slides,
    validate_plan,
)
from app.services.presentation.claim_verifier import verify_presentation_claims
from app.services.presentation_quality_auditor import PresentationQualityAuditor
from app.services.report_generator import export_spec_to_pptx
from app.services.presentation.builders.common import build_default_evidence_ledger


def make_sample_context(
    domain: str = "Workforce Operations",
    objective: str = "Quarterly Operational Review",
    audience: str = "C-Suite & Board",
    instructions: str = "Highlight variance and recommend stabilizing initiatives.",
    slide_count_constraint: SlideCountConstraint | None = None,
    current_evidence_count: int = 6,
    has_historical: bool = True
) -> PresentationPlanningContext:
    evidence = build_default_evidence_ledger(
        file_label="Operations_Q3.xlsx",
        total_records=14500,
        mean_val_str="92.4 pts",
        dispersion_metric_str="1.84x",
        snapshot_hash="sha256:7f83b1657ff1",
        reporting_period_summary="Q1 2026 - Q3 2026",
        is_partial_year=False,
        mean_sales=92.4
    )[:current_evidence_count]


    hist_ctx = {}
    if has_historical:
        hist_ctx = {
            "status": "success",
            "results": [
                {
                    "memory_id": "MEM-HIST-01",
                    "memory_type": "BUSINESS_FINDING",
                    "text": "Prior quarter operational baseline recorded 4.2% turnover.",
                    "score": 0.85,
                    "evidence_status": "historical"
                },
                {
                    "memory_id": "MEM-HIST-02",
                    "memory_type": "DOMAIN_KNOWLEDGE",
                    "text": "Historical industrial threshold targets under 5% absenteeism.",
                    "score": 0.78,
                    "evidence_status": "historical"
                }
            ],
            "historical_decks": []
        }

    return PresentationPlanningContext(
        domain=domain,
        objective=objective,
        audience=audience,
        instructions=instructions,
        dataset_label="Operations_Q3.xlsx",
        total_records=14500,
        completeness_pct=100.0,
        baseline_benchmark="92.4 pts",
        dispersion_metric="1.84x",
        reporting_period="Q1 2026 - Q3 2026",
        is_partial_year=False,
        dataset_profiles=[{"ranked_categorical": [{"dimension": "Region", "top_categories": [{"category": "North", "count": 6200, "percentage": 42.8}]}]}],
        current_evidence=evidence,
        historical_context=hist_ctx,
        available_charts={"line_chart": True, "bar_chart": True, "donut_chart": True},
        industrial_models={"talent_9box": {"available": True, "total_evaluated": 14500, "high_performers_count": 2800}},
        slide_count_constraint=slide_count_constraint or SlideCountConstraint(mode=SlideCountMode.ADAPTIVE),
        workspace_id="ws_ops_01",
        theme_id="executive_dark",
        snapshot_hash="sha256:7f83b1657ff1"
    )


# 1. Intent extraction extracts correct domain, purpose, audience, goals, and key questions
def test_intent_extraction_domain_and_audience():
    ctx = make_sample_context(
        domain="Sales",
        objective="Drive Q4 revenue acceleration",
        audience="VP of Sales & Regional Managers",
        instructions="Why did the Western region underperform in August?"
    )
    with patch("app.services.gateway.model_gateway.ModelGateway.generate") as mock_gen:
        mock_gen.return_value = GatewayResult(
            raw_text=json.dumps({
                "domain": "Sales",
                "purpose": "Revenue acceleration",
                "primary_goal": "Optimize pipeline throughput",
                "target_audience": "VP of Sales & Regional Managers",
                "audience_seniority": "VP_DIRECTOR",
                "technical_depth": "balanced",
                "delivery_mode": "LIVE_EXECUTIVE_PITCH",
                "key_takeaways": ["North is surging", "West is lagging"],
                "key_questions_to_answer": ["Why did the Western region underperform in August?"]
            }),
            success=True
        )
        intent = plan_intent(ctx, max_retries=1)
        assert intent.domain == "Sales"
        assert intent.audience_seniority == AudienceSeniority.VP_DIRECTOR
        assert "Western region" in intent.key_questions_to_answer[0]


# 2. Audience adaptation modifies narrative tone and density
def test_audience_adaptation_seniority():
    ctx_csuite = make_sample_context(audience="C-Suite & Board of Directors")
    intent_csuite = PresentationIntent(
        domain="Finance",
        purpose="Budget Review",
        primary_goal="Approve Allocations",
        target_audience="C-Suite & Board",
        audience_seniority=AudienceSeniority.C_SUITE
    )
    narrative_csuite = plan_narrative(ctx_csuite, intent_csuite, [], max_retries=-1)
    assert narrative_csuite.tone == "executive_decisive"
    assert narrative_csuite.pacing == "brisk_high_signal"

    ctx_tech = make_sample_context(audience="Principal Software Engineers & System Architects")
    intent_tech = PresentationIntent(
        domain="Tech Architecture",
        purpose="Refactor Core Services",
        primary_goal="Reduce Latency",
        target_audience="Engineers",
        audience_seniority=AudienceSeniority.TECHNICAL_OPERATIONAL
    )
    narrative_tech = plan_narrative(ctx_tech, intent_tech, [], max_retries=-1)
    assert narrative_tech.tone == "empirically_rigorous_analytical"
    assert narrative_tech.pacing == "thorough_deep_dive"


# 3. Non-HR domains: Sales
def test_non_hr_domains_sales():
    ctx = make_sample_context(domain="Sales & Commercial", objective="Revenue expansion")
    intent = PresentationIntent(domain="Sales & Commercial", purpose="Revenue review", primary_goal="Scale quota", target_audience="Sales Leadership")
    narrative = plan_narrative(ctx, intent, [], max_retries=-1)
    sec_titles = " ".join([s.title.lower() for s in narrative.sections])
    assert "revenue" in sec_titles or "commercial" in sec_titles or "sales" in sec_titles


# 4. Non-HR domains: Finance
def test_non_hr_domains_finance():
    ctx = make_sample_context(domain="Corporate Finance", objective="Cost containment and EBITDA margin review")
    intent = PresentationIntent(domain="Corporate Finance", purpose="Fiscal analysis", primary_goal="Margin expansion", target_audience="Finance Committee")
    narrative = plan_narrative(ctx, intent, [], max_retries=-1)
    sec_titles = " ".join([s.title.lower() for s in narrative.sections])
    assert "fiscal" in sec_titles or "p&l" in sec_titles or "cost" in sec_titles or "finance" in sec_titles


# 5. Non-HR domains: Tech Architecture
def test_non_hr_domains_tech_architecture():
    ctx = make_sample_context(domain="Cloud Infrastructure Architecture", objective="System reliability & latency optimization")
    intent = PresentationIntent(domain="Cloud Infrastructure Architecture", purpose="System review", primary_goal="Improve SLAs", target_audience="Engineering")
    narrative = plan_narrative(ctx, intent, [], max_retries=-1)
    assert narrative.arc_type == NarrativeArcType.TECHNICAL_ARCHITECTURE
    sec_titles = " ".join([s.title.lower() for s in narrative.sections])
    assert "architecture" in sec_titles or "throughput" in sec_titles or "latency" in sec_titles or "system" in sec_titles



# 6. Adaptive slide count mode
def test_slide_count_adaptive_mode():
    ctx = make_sample_context(
        slide_count_constraint=SlideCountConstraint(mode=SlideCountMode.ADAPTIVE),
        current_evidence_count=8
    )
    director = PresentationDirector(enabled=False, max_retries=0)
    plan = director.plan_presentation(ctx)
    assert plan.slide_count >= 5
    assert plan.metadata["slide_count_mode"] == "ADAPTIVE"


# 7. Fixed slide count mode
def test_slide_count_fixed_mode():
    ctx = make_sample_context(
        slide_count_constraint=SlideCountConstraint(mode=SlideCountMode.FIXED, target=5, min_slides=5, max_slides=5)
    )
    director = PresentationDirector(enabled=False, max_retries=0)
    plan = director.plan_presentation(ctx)
    assert plan.slide_count == 5
    assert len(plan.slides) == 5


# 8. Minimum slide count mode
def test_slide_count_minimum_mode():
    ctx = make_sample_context(
        slide_count_constraint=SlideCountConstraint(mode=SlideCountMode.MINIMUM, min_slides=10)
    )
    director = PresentationDirector(enabled=False, max_retries=0)
    plan = director.plan_presentation(ctx)
    assert plan.slide_count >= 10


# 9. Maximum slide count mode
def test_slide_count_maximum_mode():
    ctx = make_sample_context(
        slide_count_constraint=SlideCountConstraint(mode=SlideCountMode.MAXIMUM, max_slides=6)
    )
    director = PresentationDirector(enabled=False, max_retries=0)
    plan = director.plan_presentation(ctx)
    assert plan.slide_count <= 6


# 10. Range slide count mode
def test_slide_count_range_mode():
    ctx = make_sample_context(
        slide_count_constraint=SlideCountConstraint(mode=SlideCountMode.RANGE, min_slides=7, max_slides=9)
    )
    director = PresentationDirector(enabled=False, max_retries=0)
    plan = director.plan_presentation(ctx)
    assert 7 <= plan.slide_count <= 9


# 11. Instruction parser for slide constraints
def test_slide_count_instruction_parser():
    c1 = SlideCountConstraint.from_inputs("Please deliver exactly 5 slides.")
    assert c1.mode == SlideCountMode.FIXED
    assert c1.target == 5

    c2 = SlideCountConstraint.from_inputs("Create between 8 and 12 slides for the board.")
    assert c2.mode == SlideCountMode.RANGE
    assert c2.min_slides == 8
    assert c2.max_slides == 12

    c3 = SlideCountConstraint.from_inputs("Provide at least 9 slides.")
    assert c3.mode == SlideCountMode.MINIMUM
    assert c3.min_slides == 9

    c4 = SlideCountConstraint.from_inputs("Keep it under 6 slides.")
    assert c4.mode == SlideCountMode.MAXIMUM
    assert c4.max_slides == 6

    c5 = SlideCountConstraint.from_inputs("", target_length=7, default_mode="FIXED")
    assert c5.mode == SlideCountMode.FIXED
    assert c5.target == 7


# 12. Information unit extraction and destination triage
def test_information_unit_extraction_triage():
    ctx = make_sample_context(current_evidence_count=10)
    intent = PresentationIntent(domain="Operations", purpose="Review", primary_goal="Goal", target_audience="Board")
    units = extract_and_triage_information(ctx, intent, max_retries=-1)
    assert len(units) >= 10
    destinations = {u.destination for u in units}
    assert InformationDestination.MAIN_DECK in destinations
    assert InformationDestination.APPENDIX in destinations or InformationDestination.SPEAKER_NOTES in destinations


# 13. Strict truth precedence: Current evidence always wins
def test_strict_truth_precedence_current_wins():
    ctx = make_sample_context(has_historical=True)
    intent = PresentationIntent(domain="Operations", purpose="Review", primary_goal="Goal", target_audience="Board")
    units = extract_and_triage_information(ctx, intent, max_retries=-1)

    current_units = [u for u in units if u.source_type == InformationSourceType.CURRENT_EVIDENCE]
    hist_units = [u for u in units if u.source_type == InformationSourceType.HISTORICAL_MEMORY]

    assert len(current_units) > 0
    assert len(hist_units) > 0

    # Current verified evidence must have confidence 1.0 and high/medium priority
    for cu in current_units:
        assert cu.confidence == 1.0

    # Historical units must NOT override current evidence to MAIN_DECK with HIGH priority
    for hu in hist_units:
        assert hu.confidence < 1.0
        assert hu.destination in (InformationDestination.SPEAKER_NOTES, InformationDestination.APPENDIX)


# 14. Historical context provenance tagging
def test_historical_context_provenance_tagging():
    ctx = make_sample_context(has_historical=True)
    intent = PresentationIntent(domain="Operations", purpose="Review", primary_goal="Goal", target_audience="Board")
    units = extract_and_triage_information(ctx, intent, max_retries=-1)
    hist_units = [u for u in units if u.source_type == InformationSourceType.HISTORICAL_MEMORY]
    assert all("[Historical Context]" in u.statement for u in hist_units)
    assert all(u.source_ref.startswith("MEM-") for u in hist_units)



# 15. Duplicate concept detection
def test_duplicate_concept_detection():
    ctx = make_sample_context()
    intent = PresentationIntent(domain="Operations", purpose="Review", primary_goal="Goal", target_audience="Board")
    duplicate_slides = [
        SlidePlan(
            slide_id="s1",
            section_id="sec1",
            sequence_number=1,
            layout="title_hero",
            headline="Revenue Acceleration in North Region",
            key_message="Identical finding about North region expansion.",
            bullet_points=["Point 1", "Point 2", "Point 3"]
        ),
        SlidePlan(
            slide_id="s2",
            section_id="sec1",
            sequence_number=2,
            layout="chart_narrative",
            headline="Revenue Acceleration in North Region",
            key_message="Identical finding about North region expansion.",
            bullet_points=["Point 1", "Point 2", "Point 3"]
        ),
        SlidePlan(
            slide_id="s3",
            section_id="sec2",
            sequence_number=3,
            layout="action_plan",
            headline="Action Roadmap for Expansion",
            key_message="Roadmap details.",
            bullet_points=["Action 1", "Action 2", "Action 3"]
        )
    ]
    res = validate_plan(ctx, intent, duplicate_slides)
    assert not res.is_valid
    assert len(res.duplicate_concepts_detected) > 0


# 16. Unanswered user question detection
def test_unanswered_user_question_detection():
    ctx = make_sample_context()
    intent = PresentationIntent(
        domain="Operations",
        purpose="Review",
        primary_goal="Goal",
        target_audience="Board",
        key_questions_to_answer=[
            "What is the current operational baseline?",
            "Why did the international logistics pipeline collapse in September?"
        ]
    )
    slides = [
        SlidePlan(
            slide_id="s1",
            section_id="sec1",
            sequence_number=1,
            layout="title_hero",
            headline="Operational Baseline Review",
            key_message="Operational baseline established across audited units.",
            bullet_points=["Point 1", "Point 2", "Point 3"]
        ),
        SlidePlan(
            slide_id="s2",
            section_id="sec1",
            sequence_number=2,
            layout="kpi_summary",
            headline="Key Performance Summary",
            key_message="Baseline metrics summarized.",
            bullet_points=["Point 1", "Point 2", "Point 3"]
        ),
        SlidePlan(
            slide_id="s3",
            section_id="sec1",
            sequence_number=3,
            layout="action_plan",
            headline="Strategic Roadmap",
            key_message="Strategic initiatives.",
            bullet_points=["Point 1", "Point 2", "Point 3"]
        )
    ]
    res = validate_plan(ctx, intent, slides)
    # Second question (international logistics pipeline collapse) is completely unaddressed
    assert any("logistics" in q for q in res.unanswered_user_questions)


# 17. Unsupported claims detection
def test_unsupported_claims_detection():
    ctx = make_sample_context()
    intent = PresentationIntent(domain="Operations", purpose="Review", primary_goal="Goal", target_audience="Board")
    slides = [
        SlidePlan(
            slide_id="s1",
            section_id="sec1",
            sequence_number=1,
            layout="title_hero",
            headline="Hero Slide",
            bullet_points=["Point 1", "Point 2", "Point 3"]
        ),
        SlidePlan(
            slide_id="s2",
            section_id="sec1",
            sequence_number=2,
            layout="chart_narrative",
            headline="Ungrounded Finding Slide",
            evidence_ids=[],
            information_unit_ids=[],
            bullet_points=["Point 1", "Point 2", "Point 3"]
        ),
        SlidePlan(
            slide_id="s3",
            section_id="sec1",
            sequence_number=3,
            layout="action_plan",
            headline="Roadmap",
            evidence_ids=["EVID-01"],
            bullet_points=["Point 1", "Point 2", "Point 3"]
        )
    ]
    res = validate_plan(ctx, intent, slides)
    assert any("Ungrounded Finding Slide" in u for u in res.unsupported_claims)


# 18. Stage recovery on validation failure
def test_stage_recovery_on_validation_failure():
    ctx = make_sample_context()
    director = PresentationDirector(enabled=False, max_retries=1)
    plan = director.plan_presentation(ctx)
    assert plan.slide_count >= 4
    # A structurally complete fallback is not an evidence-backed answer.
    assert not plan.planning_validation.is_valid
    assert plan.planning_validation.unanswered_user_questions


# 19. Presentation Director fallback
def test_presentation_director_fallback():
    ctx = make_sample_context()
    director = PresentationDirector(enabled=False, max_retries=0)
    plan = director.plan_presentation(ctx)
    assert plan.slide_count >= 5
    assert len(plan.slides) == plan.slide_count
    assert plan.deck_title is not None


# 20. Downstream adapter deck spec contract (spec_version 2.0)
def test_downstream_adapter_deck_spec_contract():
    ctx = make_sample_context()
    director = PresentationDirector(enabled=False, max_retries=0)
    plan = director.plan_presentation(ctx)
    theme = {"id": "executive_dark", "background": "#0F172A"}
    deck_spec = adapt_plan_to_deck_spec(plan, ctx, theme=theme)

    assert deck_spec["spec_version"] == "2.0"
    assert deck_spec["id"].startswith("deck_")
    assert deck_spec["theme"]["id"] == "executive_dark"
    assert "metadata" in deck_spec
    assert "slides" in deck_spec
    assert "evidence_ledger" in deck_spec
    assert "coverage_manifest" in deck_spec
    assert "retrieved_context" in deck_spec


# 21. Downstream adapter chart binding
def test_downstream_adapter_chart_binding():
    ctx = make_sample_context()
    chart_pack = {
        "line_chart": {"chart_type": "line", "title": "Throughput Velocity", "series": [{"name": "Volume", "values": [10, 20, 30]}]},
        "bar_chart": {"chart_type": "bar", "title": "Entity Spread", "series": [{"name": "Spread", "values": [5, 15, 25]}]},
        "donut_chart": {"chart_type": "donut", "title": "Category Share", "series": [{"name": "Share", "values": [40, 60]}]}
    }
    director = PresentationDirector(enabled=False, max_retries=0)
    plan = director.plan_presentation(ctx)
    deck_spec = adapt_plan_to_deck_spec(plan, ctx, theme={"id": "executive_dark"}, chart_pack=chart_pack)

    # Matching a chart family alone does not establish its subject or evidence.
    assert not any(s.get("chart") for s in deck_spec["slides"])
    assert not any(m.get("label") == "System Resilience" for s in deck_spec["slides"] for m in s.get("metrics", []))


# 22. Downstream adapter metric badges and speaker notes
def test_downstream_adapter_metric_and_speaker_notes():
    ctx = make_sample_context()
    director = PresentationDirector(enabled=False, max_retries=0)
    plan = director.plan_presentation(ctx)
    deck_spec = adapt_plan_to_deck_spec(plan, ctx, theme={"id": "executive_dark"})

    for s in deck_spec["slides"]:
        assert len(s.get("bullets", [])) >= 3
        assert s.get("notes") is not None
        assert s.get("narrative") is not None


# 23. Downstream adapter snapshot hash preservation
def test_downstream_adapter_snapshot_hash_preservation():
    ctx = make_sample_context()
    director = PresentationDirector(enabled=False, max_retries=0)
    plan = director.plan_presentation(ctx)
    deck_spec = adapt_plan_to_deck_spec(plan, ctx, theme={"id": "executive_dark"})

    assert deck_spec["metadata"]["snapshot_hash"] == ctx.snapshot_hash
    assert deck_spec["metadata"]["total_records"] == ctx.total_records


# 24. Downstream adapter coverage manifest
def test_downstream_adapter_coverage_manifest():
    ctx = make_sample_context(current_evidence_count=8)
    director = PresentationDirector(enabled=False, max_retries=0)
    plan = director.plan_presentation(ctx)
    deck_spec = adapt_plan_to_deck_spec(plan, ctx, theme={"id": "executive_dark"})

    manifest = deck_spec["coverage_manifest"]
    assert manifest["coverage_pct"] == 100.0
    assert manifest["main_deck_count"] + manifest["appendix_count"] == len(ctx.current_evidence)
    assert len(manifest["items"]) == len(ctx.current_evidence)


# 25. Variety of narrative arcs supported
def test_narrative_arcs_variety():
    ctx_diag = make_sample_context(objective="Diagnostic deep dive into regional bottlenecks")
    strat_diag = plan_narrative(ctx_diag, plan_intent(ctx_diag, max_retries=-1), [], max_retries=-1)
    assert strat_diag.arc_type == NarrativeArcType.DIAGNOSTIC_DEEP_DIVE

    ctx_strat = make_sample_context(objective="Strategic recommendation for workforce expansion")
    strat_strat = plan_narrative(ctx_strat, plan_intent(ctx_strat, max_retries=-1), [], max_retries=-1)
    assert strat_strat.arc_type == NarrativeArcType.STRATEGIC_RECOMMENDATION

    ctx_arch = make_sample_context(domain="System Architecture", objective="Core microservices refactoring")
    strat_arch = plan_narrative(ctx_arch, plan_intent(ctx_arch, max_retries=-1), [], max_retries=-1)
    assert strat_arch.arc_type == NarrativeArcType.TECHNICAL_ARCHITECTURE



# 26. Visual intent layout mapping
def test_visual_intent_layout_mapping():
    ctx = make_sample_context()
    director = PresentationDirector(enabled=False, max_retries=0)
    plan = director.plan_presentation(ctx)
    layouts = {s.layout for s in plan.slides}
    assert "title_hero" in layouts or "title_cover" in layouts
    assert "kpi_summary" in layouts
    assert "chart_narrative" in layouts or "table_detail" in layouts


# 27. Slide titles are assertive headlines under 80 characters
def test_slide_titles_length_and_assertion():
    ctx = make_sample_context()
    director = PresentationDirector(enabled=False, max_retries=0)
    plan = director.plan_presentation(ctx)
    for s in plan.slides:
        assert len(s.headline) <= 80


# 28. Multi-dataset and aggregated evidence in planning context
def test_multidataset_planning_context():
    ctx = make_sample_context(current_evidence_count=12)
    ctx.dataset_profiles.append({
        "dataset_name": "Secondary_Telemetry.csv",
        "records": 5000,
        "ranked_categorical": [{"dimension": "Facility", "top_categories": [{"category": "Site B", "count": 2500}]}]
    })
    director = PresentationDirector(enabled=False, max_retries=0)
    plan = director.plan_presentation(ctx)
    assert plan.slide_count >= 5
    assert len(plan.information_units) >= 12


# 29. Export compatibility (PPTX export and claim verification and quality audit)
def test_export_pptx_and_quality_audit_compatibility():
    ctx = make_sample_context()
    chart_pack = {
        "line_chart": {
            "chart_type": "line",
            "title": "Weekly Throughput Velocity",
            "categories": ["W1", "W2", "W3", "W4"],
            "series": [{"name": "Throughput", "values": [120.0, 140.0, 135.0, 160.0]}]
        },
        "bar_chart": {
            "chart_type": "bar",
            "title": "Regional Spread",
            "categories": ["North", "South", "East", "West"],
            "series": [{"name": "Score", "values": [90.0, 75.0, 82.0, 68.0]}]
        }
    }
    director = PresentationDirector(enabled=False, max_retries=0)
    deck_spec = director.plan_and_adapt(
        ctx=ctx,
        theme={"id": "executive_dark", "background": "#0F172A", "primary": "#38BDF8", "secondary": "#94A3B8"},
        theme_id="executive_dark",
        chart_pack=chart_pack
    )

    # Verify claims
    claim_res = verify_presentation_claims(deck_spec, deck_spec["evidence_ledger"])
    # Raw fallback planning text is not automatically certified by cited IDs.
    assert claim_res["discrepancies_flagged"] > 0

    # Quality audit
    audit_res = PresentationQualityAuditor.audit_deck_spec(deck_spec, deck_spec["evidence_ledger"])
    assert audit_res.get("critical_count", 0) == 0

    # Native PPTX export
    pptx_path = export_spec_to_pptx(deck_spec)
    assert Path(pptx_path).exists()
    assert Path(pptx_path).stat().st_size > 1000
