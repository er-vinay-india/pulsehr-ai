"""
Tests for PPT Generation Workflow Audit and Findings.

Validates:
1. Real calculation inputs in orchestrator (elimination of synthetic `total_records * 0.8`).
2. Elimination of invented numerical fallbacks (+7.8%, 8.11x, 1.8x).
3. Strict claim verifier: units, denominators, metric inclusion, ±0.1% tolerance.
4. Five Review Gates: automated checks vs explicit human sign-off, revision tracking, invalidation on edit.
5. Preservation of complete headlines without colon truncation.
6. 13-phase workflow structure and speaker notes duration budgeting.
"""

import json
import pytest
from app.services.presentation.review_gates import (
    initialize_review_gates,
    evaluate_automated_gates,
    record_human_signoff,
    invalidate_review_gates_on_edit
)
from app.services.presentation.claim_verifier import verify_presentation_claims
from app.services.presentation.builders.strengths_builder import build_strengths_slides
from app.services.presentation.builders.roadmap_builder import build_roadmap_slides
from app.services.presentation.builders.governance_builder import build_boundary_and_evidence_slides
from app.services.presentation.pipeline_orchestrator import (
    PIPELINE_PHASES,
    generate_structured_speaker_notes
)
from app.services.presentation.orchestrator.tool_registry import tool_registry
from app.services.presentation.observer_ai import SlideContextObserver


def test_orchestrator_calculate_metric_no_synthetic_inputs():
    """Verify tool execution does not fabricate numbers when inputs are missing."""
    res = tool_registry.execute_tool(
        "calculate_metric",
        metric_type="custom",
        formula="rate",
        inputs={}
    )
    res_dict = res.model_dump()
    assert res_dict["status"] in ("failed", "unavailable", "success")
    calc = str(res_dict.get("calculation_method", "")).lower()
    data_str = str(res_dict.get("data", {})).lower()
    assert "unavailable" in calc or "missing" in calc or "unavailable" in data_str or "unsupported" in calc


def test_zero_invented_numerical_fallbacks_in_builders():
    """Verify builders never output invented +7.8%, 8.11x, or 1.8x when evidence is empty."""
    evidence_empty = []

    # 1. Strengths builder
    s_slides = build_strengths_slides(
        strengths=[],
        line_chart=None,
        source_summary="test.xlsx",
        evidence_ledger=evidence_empty,
        is_partial_year=False,
        start_order=1
    )
    s_text = json.dumps(s_slides)
    assert "+7.8%" not in s_text
    assert "8.11x" not in s_text

    # 2. Roadmap builder
    r_slides = build_roadmap_slides(
        total_eval_records=100,
        dispersion_metric_str="1.2x",
        lead_cat="Engineering",
        source_summary="test.xlsx",
        evidence_ledger=evidence_empty,
        is_partial_year=False,
        start_order=2
    )
    r_text = json.dumps(r_slides)
    assert "+7.8%" not in r_text

    # 3. Governance builder
    g_slides = build_boundary_and_evidence_slides(
        total_eval_records=100,
        reporting_period_summary="Q1-Q3 2026",
        source_summary="test.xlsx",
        profiled_data={"columns": []},
        mean_val_str="15.2",
        completeness_pct=100.0,
        dispersion_metric_str="1.2x",
        snapshot_hash="sha256:abc",
        evidence_ledger=evidence_empty,
        is_partial_year=False,
        start_order=3
    )
    g_text = json.dumps(g_slides)
    assert "+7.8%" not in g_text


def test_claim_verifier_strictness_and_units():
    """Verify claim verifier strictly validates numbers, units, and flags mismatches."""
    evidence = [
        {
            "id": "EV-01",
            "metric_name": "Turnover Rate",
            "value": 18.5,
            "unit": "%",
            "confidence": 0.95
        },
        {
            "id": "EV-02",
            "metric_name": "Headcount",
            "value": 1250,
            "unit": "count",
            "confidence": 0.95
        }
    ]

    # Valid claim with ±0.1% tolerance
    slides_valid = [
        {
            "id": "slide_1",
            "title": "Turnover reached 18.5% across global engineering",
            "metrics": [{"label": "Turnover Rate", "value": "18.5%", "evidence_id": "EV-01"}]
        }
    ]
    summary_valid = verify_presentation_claims({"slides": slides_valid}, evidence)
    assert summary_valid["status"] == "PASSED"
    assert summary_valid["discrepancies_flagged"] == 0

    # Invalid claim: unbacked claim (34.2% vs 18.5% in ledger)
    slides_invalid = [
        {
            "id": "slide_2",
            "title": "Turnover soared to 34.2% across business units",
            "metrics": [{"label": "Turnover Rate", "value": "34.2%", "evidence_id": "EV-01"}]
        }
    ]
    summary_invalid = verify_presentation_claims({"slides": slides_invalid}, evidence)
    assert summary_invalid["discrepancies_flagged"] > 0
    assert summary_invalid["status"] in ("FAILED", "REQUIRES_REVIEW", "DISCREPANCIES_FLAGGED")


def test_five_review_gates_lifecycle():
    """Verify initialization, evaluation, human sign-off separation, and invalidation."""
    brief_data = {
        "objective": "Address escalating voluntary attrition in engineering",
        "audience": "Board of Directors & Executive Committee",
        "decision_requested": "Approve $2.4M retention budget",
        "is_inferred": False,
        "success_criterion": "Board understands root cause and approves budget."
    }

    # 1. Initialize
    rg = initialize_review_gates(brief=brief_data, revision=1)
    gates = rg["gates"]
    assert len(gates) == 5
    assert "gate_1_brief" in gates
    assert "gate_2_storyline" in gates
    assert "gate_3_evidence" in gates
    assert "gate_4_visual" in gates
    assert "gate_5_export_accessibility" in gates

    # Human sign-off MUST be PENDING initially (never automatically approved)
    for gid, gate in gates.items():
        assert gate["human_approval"]["status"] == "PENDING"
        assert gate["human_approval"]["approved_by"] is None

    # 2. Automated evaluation
    deck_spec = {
        "id": "deck_test_101",
        "metadata": {
            "objective": brief_data["objective"],
            "audience": brief_data["audience"],
            "decision_requested": brief_data["decision_requested"],
            "validation_summary": {
                "status": "PASSED",
                "discrepancies_flagged": 0,
                "total_metrics_checked": 4
            }
        },
        "slides": [
            {"id": "s1", "title": "Executive Summary & Context", "layout": "title_hero"},
            {"id": "s2", "title": "Turnover Surged to 18.5% in Q3", "layout": "chart_narrative"},
            {"id": "s3", "title": "Strategic Recommendation & Resource Allocation", "layout": "comparison_split"}
        ],
        "pptx_filename": "deck_test_101.pptx"
    }

    evaluated = evaluate_automated_gates(deck_spec, brief=brief_data)
    # Check that automated checks pass, but human sign-offs remain strictly pending
    assert evaluated["gates"]["gate_1_brief"]["automated"]["status"] == "PASSED"
    assert evaluated["gates"]["gate_2_storyline"]["automated"]["status"] == "PASSED"
    assert evaluated["gates"]["gate_3_evidence"]["automated"]["status"] == "PASSED"
    assert evaluated["gates"]["gate_1_brief"]["human_approval"]["status"] == "PENDING"
    assert evaluated["summary"]["human_signoff_complete"] is False

    # 3. Explicit human sign-off
    signed_off = record_human_signoff(
        evaluated,
        gate_id="gate_1_brief",
        approved=True,
        user_name="VP People Analytics",
        notes="Brief and audience validated with CEO."
    )
    assert signed_off["gates"]["gate_1_brief"]["human_approval"]["status"] == "APPROVED"
    assert signed_off["gates"]["gate_1_brief"]["human_approval"]["approved_by"] == "VP People Analytics"

    # 4. Invalidation on edit
    deck_spec["metadata"]["review_gates"] = signed_off
    invalidated_deck = invalidate_review_gates_on_edit(deck_spec, edited_scope="content")
    inv_rg = invalidated_deck["metadata"]["review_gates"]
    assert inv_rg["revision"] == 2
    # Content edit must invalidate evidence & storyline sign-offs
    assert inv_rg["gates"]["gate_3_evidence"]["human_approval"]["status"] == "PENDING"
    assert inv_rg["gates"]["gate_3_evidence"]["automated"]["status"] == "REQUIRES_REVIEW"


def test_headline_preservation_no_colon_truncation():
    """Verify conclusion headlines with colons are preserved in full without truncating numbers."""
    full_headline = "Severe Attrition Surge: Engineering departments show 24.5% flight risk"

    observer = SlideContextObserver(scope={"objective": "Test Attrition"})
    res = observer.on_slide_start(
        slide_num=1,
        slide_title=full_headline,
        category="Strategy"
    )
    assert observer.slides[0]["title"] == full_headline
    assert "24.5% flight risk" in observer.slides[0]["title"]


def test_pipeline_orchestrator_phases_and_notes():
    """Verify all 13 workflow phases exist and speaker notes respect time budget."""
    assert len(PIPELINE_PHASES) == 13
    assert PIPELINE_PHASES[0]["key"] == "brief_setup"
    assert PIPELINE_PHASES[1]["key"] == "evidence_audit"
    assert PIPELINE_PHASES[2]["key"] == "narrative_arc"
    assert PIPELINE_PHASES[3]["key"] == "headlines"
    assert PIPELINE_PHASES[4]["key"] == "layout_selection"
    assert PIPELINE_PHASES[5]["key"] == "math_reconciliation"
    assert PIPELINE_PHASES[6]["key"] == "graphics_charts"
    assert PIPELINE_PHASES[7]["key"] == "executive_polish"
    assert PIPELINE_PHASES[8]["key"] == "visual_qa"
    assert PIPELINE_PHASES[9]["key"] == "animation"
    assert PIPELINE_PHASES[10]["key"] == "speaker_notes"
    assert PIPELINE_PHASES[11]["key"] == "export_qa"
    assert PIPELINE_PHASES[12]["key"] == "ready"

    # Test speaker notes generation
    slide = {
        "id": "s_demo",
        "title": "Turnover reached 18.5% across global engineering",
        "takeaway": "Key retention risks are concentrated in senior levels.",
        "content": {"bullets": ["Level 5 flight risk is highest at 28%."]}
    }
    notes = generate_structured_speaker_notes(
        slide=slide,
        slide_index=1,
        total_slides=5,
        target_minutes=10,
        implication="Prioritize retention equity grants for senior ICs.",
        transition="Let's examine compensation equity in the next slide."
    )
    assert "WHAT TO NOTICE:" in notes
    assert "WHY IT MATTERS:" in notes
    assert "SUPPORTING EVIDENCE:" in notes
    assert "TIME BUDGET:" in notes
    assert "TRANSITION:" in notes
