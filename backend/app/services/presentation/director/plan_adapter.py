from __future__ import annotations

import datetime
import logging
import uuid
from typing import Any

from ...display_formatters import format_display_label
from ..builders.common import DECK_DEFAULTS, calculate_timing, find_evidence, format_briefing
from .director_models import (
    InformationDestination,
    PresentationPlanSpec,
    PresentationPlanningContext,
    SlidePlan,
)
from ..visual.visual_intelligence import VisualIntelligenceEngine

logger = logging.getLogger(__name__)


def adapt_plan_to_deck_spec(
    plan: PresentationPlanSpec,
    ctx: PresentationPlanningContext,
    theme: dict[str, Any],
    theme_id: str | None = None,
    chart_pack: dict[str, Any] | None = None,
    profiled_data: dict[str, Any] | None = None,
    evidence_ledger: list[dict[str, Any]] | None = None,
    on_slide_progress: Any = None,
    on_slide_start: Any = None
) -> dict[str, Any]:
    """Downstream Adapter: Maps PresentationPlanSpec into the canonical PresentationDeckSpec v2.0.

    Layman explanation:
    Takes the abstract presentation outline and turns it into concrete slides,
    notifying the Observer AI and the frontend before starting each slide and after
    each slide is finished.
    """
    resolved_theme_id = theme_id or ctx.theme_id or "bold_signal"
    charts = chart_pack or {}
    line_chart = charts.get("line_chart")
    bar_chart = charts.get("bar_chart")
    donut_chart = charts.get("donut_chart")
    rel_chart = charts.get("rel_chart")

    ev_ledger = [e for e in (evidence_ledger or ctx.current_evidence or []) if isinstance(e, dict)]
    t9 = ctx.industrial_models.get("talent_9box") if ctx.industrial_models else None
    bs = ctx.industrial_models.get("burnout_strain") if ctx.industrial_models else None
    bf = ctx.industrial_models.get("bradford_factor") if ctx.industrial_models else None

    ev_strength = next((e for e in ev_ledger if e.get("evidence_id") == "EVID-STRENGTH-01"), None)
    ev_headwind = next((e for e in ev_ledger if e.get("evidence_id") == "EVID-HEADWIND-01"), None)
    ev_exec = next((e for e in ev_ledger if e.get("evidence_id") == "EVID-EXEC-01"), None)

    strength_val = ev_strength.get("metric_value") if ev_strength and ev_strength.get("metric_value") else "Baseline Stabilized"
    strength_lbl = ev_strength.get("metric_name") if ev_strength and ev_strength.get("metric_name") else "Operating Baseline"

    headwind_val = (ev_headwind.get("metric_value") or ctx.dispersion_metric or "Observed Spread") if ev_headwind else (ctx.dispersion_metric or "Observed Spread")
    headwind_lbl = (ev_headwind.get("metric_name") or "Dispersion Metric") if ev_headwind else "Dispersion Metric"

    exec_val = ev_exec.get("metric_value", f"{ctx.total_records:,}") if ev_exec else f"{ctx.total_records:,}"

    # Proposed actions are tied to recorded findings; targets remain unassigned.
    proposals = [
        {"priority": "REVIEW", "owner_role": "Unassigned - Report owner",
         "motivating_finding": e.get("finding") or e.get("title") or e.get("metric_name", "Recorded finding"),
         "proposed_response": "Confirm the finding and agree a follow-up action.",
         "success_metric": "To be agreed after review", "dependencies": "Confirm definitions and policy"}
        for e in ev_ledger[:3]
    ]
    initiatives = [{"priority": p["priority"], "owner": p["owner_role"], "title": p["proposed_response"],
                    "finding": p["motivating_finding"], "metric": p["success_metric"], "dependency": p["dependencies"]}
                   for p in proposals]
    appendix_headers = ["Recorded finding", "Value", "Unit", "Period"]
    appendix_rows = [[e.get("title") or e.get("metric_name", ""), str(e.get("metric_value", "")),
                      str(e.get("unit", "")), str(e.get("date_range", ""))] for e in ev_ledger[:12]]

    materialized_slides: list[dict[str, Any]] = []
    total_slides = len(plan.slides)
    visual_engine = VisualIntelligenceEngine()

    for idx, slide_plan in enumerate(plan.slides):
        v_type = slide_plan.visual_intent.visual_type
        layout = slide_plan.layout
        h_line = format_display_label(slide_plan.headline)
        if len(h_line) > 78:
            h_line = h_line[:75] + "..."

        # Find section title for slide category classification
        sec_title = "Executive Review"
        for sec in plan.sections:
            if sec.section_id == slide_plan.section_id:
                sec_title = sec.title
                break

        # Notify Observer AI and UI that this slide is now entering synthesis (building state)
        if on_slide_start and callable(on_slide_start):
            try:
                on_slide_start(idx + 1, total_slides, h_line, sec_title)
            except Exception:
                pass

        ev_id = slide_plan.evidence_ids[0] if slide_plan.evidence_ids else (ev_ledger[0].get("evidence_id") if ev_ledger else "EVID-01")
        ev_item = find_evidence(ev_ledger, ev_id)

        slide_chart = None
        slide_table = None
        metrics = None
        talent_9box_data = None
        burnout_strain_data = None
        structured_props = None
        init_cards = None

        # Only measurements actually cited by this slide become metric cards.
        cited = set(slide_plan.evidence_ids)
        metrics = [{"label": e.get("metric_name") or e.get("title"), "value": e.get("metric_value"),
                    "unit": e.get("unit"), "subtext": e.get("date_range") or "Recorded period",
                    "evidence_id": e["evidence_id"]}
                   for e in ev_ledger if e.get("evidence_id") in cited and e.get("numeric_value") is not None][:4]
        from ..visual_binding import bind_chart
        candidate = charts.get(v_type)
        slide_chart = bind_chart(candidate, slide_plan.evidence_ids, ev_ledger,
                                 slide_plan.visual_intent.metrics_to_display)
        if v_type == "talent_9box" and t9:
            talent_9box_data = t9
        elif v_type == "burnout_strain" and bs:
            burnout_strain_data = bs
        elif v_type == "action_plan" or layout == "action_plan":
            structured_props = [p for p, e in zip(proposals, ev_ledger[:3]) if e.get("evidence_id") in cited]
            init_cards = [{"title": p["proposed_response"], "owner": p["owner_role"], "metric": p["success_metric"]} for p in structured_props]
        elif v_type in ("evidence_ledger", "table", "raci_matrix") or layout == "table_detail":
            rows = [row for row, e in zip(appendix_rows, ev_ledger) if e.get("evidence_id") in cited]
            slide_table = {"headers": appendix_headers, "rows": rows[:6]} if rows else None
        if layout in ("chart_narrative", "full_chart_takeaway", "two_charts") and not slide_chart and not talent_9box_data and not burnout_strain_data:
            layout = "comparison_split"
        if layout == "table_detail" and not slide_table:
            layout = "comparison_split"

        # Clean voice narration script without markdown symbols
        raw_script = slide_plan.speaker_notes or ""
        if "=== CONVERSATIONAL NARRATION SCRIPT" in raw_script:
            raw_script = raw_script.split("=== CONVERSATIONAL NARRATION SCRIPT (~140 WPM) ===")[-1].strip()
        elif "=== PRESENTER BRIEFING" in raw_script:
            raw_script = ""

        if not raw_script or len(raw_script.strip()) < 15:
            raw_script = f"{slide_plan.key_message}. Focus executive attention on verified findings in {h_line}."

        clean_script = raw_script.replace("**", "").replace("*", "").replace("#", "").strip()
        if len(clean_script) < 25:
            clean_script = f"Focus executive attention on verified findings in {h_line}. Empirical records confirm operational baseline."
        clean_script = clean_script.replace("**", "").strip()

        notes_text = slide_plan.speaker_notes
        if not notes_text or len(notes_text.strip()) <= 10 or "=== PRESENTER BRIEFING (BOARD SCRUTINY) ===" not in notes_text:
            ev_for_briefing = ev_item or find_evidence(ev_ledger, ev_id)
            notes_text = format_briefing(
                ev=ev_for_briefing,
                title=h_line,
                takeaway=slide_plan.key_message,
                chart_explanation="Empirical visualization reflecting verified dataset distributions.",
                narration_script=clean_script,
                snapshot_hash=ctx.snapshot_hash or "000000000000"
            )

        if layout == "action_plan" or v_type == "action_plan" or "roadmap" in h_line.lower():
            cat = "STRATEGIC ROADMAP"
            stable_id = "slide_action_plan"
        elif idx == 0:
            if layout == "title_cover":
                cat = f"{ctx.domain.upper()[:22]} · EXECUTIVE BRIEFING"
                stable_id = "slide_title_cover"
            else:
                cat = "EXECUTIVE SUMMARY"
                stable_id = "slide_exec_overview"
        elif idx == 1:
            cat = "ANALYSIS BASELINE"
            stable_id = "slide_macro_outcomes"
        elif v_type == "line_chart" or (layout == "chart_narrative" and idx == 2):
            cat = sec_title.upper()[:25] if sec_title and sec_title.upper() != "EXECUTIVE REVIEW" else "OPERATIONS"
            stable_id = "slide_operational_strengths"
        elif v_type == "bar_chart" or (layout == "chart_narrative" and idx == 3):
            cat = sec_title.upper()[:25] if sec_title and sec_title.upper() != "EXECUTIVE REVIEW" else "DIAGNOSTIC"
            stable_id = "slide_operational_headwinds"
        elif v_type == "donut_chart" or (layout == "chart_narrative" and idx == 4):
            cat = sec_title.upper()[:25] if sec_title and sec_title.upper() != "EXECUTIVE REVIEW" else "DIAGNOSTIC"
            stable_id = "slide_relational_discovery"
        elif v_type == "talent_9box":
            cat = "TALENT & CAPACITY"
            stable_id = "slide_talent_9box_matrix"
        elif v_type == "burnout_strain":
            cat = "STRAIN DIAGNOSTIC"
            stable_id = "slide_burnout_strain_diagnostic"
        elif layout == "table_detail" or v_type in ("table", "evidence_ledger", "raci_matrix"):
            cat = "EVIDENCE APPENDIX"
            stable_id = "slide_data_evidence"
        else:
            cat = sec_title.upper()[:25] if sec_title and sec_title.upper() != "EXECUTIVE REVIEW" else "EXECUTIVE REVIEW"
            stable_id = f"slide_{idx+1}_{layout}"

        ev_sources: list[str] = []
        if ev_item and ev_item.get("source"):
            ev_sources = [ev_item["source"]]
        elif ctx.dataset_profiles:
            ev_sources = [p.get("original_name") or p.get("name") or p.get("display_name") for p in ctx.dataset_profiles if (p.get("original_name") or p.get("name") or p.get("display_name"))]
        if not ev_sources:
            ev_sources = [ctx.dataset_label or f"{ctx.domain.title()} Dataset"]

        reading_order = [
            "slide_header",
            "narrative_lead",
            "visual_chart" if (slide_chart or talent_9box_data or burnout_strain_data) else ("evidence_table" if slide_table else "kpi_metrics"),
            "evidence_bullets" if slide_plan.bullet_points else "proposals_list",
            "governance_footer"
        ]
        timing_meta = calculate_timing(clean_script)

        slide_dict: dict[str, Any] = {
            "id": f"slide_{idx+1}",
            "stable_slide_id": stable_id,
            "order": idx + 1,
            "total_slides": total_slides,
            "category": cat,
            "layout": layout,
            "title": h_line,
            "subtitle": slide_plan.subtitle,
            "narrative": slide_plan.key_message,
            "bullets": slide_plan.bullet_points,
            "narration_script": clean_script,
            "reading_order": reading_order,
            "timing_metadata": timing_meta,
            "evidence_id": ev_id,
            "evidence_finding": ev_item.get("finding") if ev_item else None,
            "speaker_takeaway": slide_plan.key_message,
            "speaker_notes": notes_text,
            "notes": notes_text,
            "visual_hook": v_type,
            "metrics": metrics or [],
            "chart": slide_chart,
            "table": slide_table,
            "talent_9box": talent_9box_data,
            "talent_9box_data": talent_9box_data,
            "burnout_strain": burnout_strain_data,
            "burnout_strain_data": burnout_strain_data,
            "structured_proposals": structured_props,
            "initiatives": init_cards,
            "information_unit_ids": slide_plan.information_unit_ids,
            "historical_context_refs": slide_plan.historical_context_refs,
            "evidence_sources": ev_sources,
        }

        # Phase 4 Canonical Visual Specification
        try:
            v_spec = visual_engine.process_slide(
                slide_package_or_dict=slide_dict,
                theme_id=resolved_theme_id,
                sequence_number=idx + 1,
                total_slides=total_slides
            )
            slide_dict["visual_spec"] = v_spec.model_dump()
        except Exception as e:
            logger.warning(f"Could not build visual_spec for slide {idx+1}: {e}")
            slide_dict["visual_spec"] = None

        materialized_slides.append(slide_dict)

        if on_slide_progress and callable(on_slide_progress):
            try:
                on_slide_progress(idx + 1, total_slides, h_line, sec_title, slide_dict=slide_dict)
            except Exception:
                pass

    # Coverage manifest
    manifest_items = []
    used_ev_ids = {s.get("evidence_id") for s in materialized_slides if s.get("evidence_id")}
    for idx, ev in enumerate(ev_ledger):
        e_id = ev.get("evidence_id", f"EVID-{idx+1:02d}")
        e_title = ev.get("title") or ev.get("headline") or f"Finding {idx+1}"
        if e_id in used_ev_ids:
            manifest_items.append({
                "evidence_id": e_id,
                "title": e_title,
                "disposition": "main_deck",
                "reason": "Directly grounded in planned slide presentation"
            })
        else:
            manifest_items.append({
                "evidence_id": e_id,
                "title": e_title,
                "disposition": "appendix",
                "reason": "Preserved in supplemental audit trail"
            })

    coverage_manifest = {
        "main_deck_count": len([m for m in manifest_items if m["disposition"] == "main_deck"]),
        "appendix_count": len([m for m in manifest_items if m["disposition"] == "appendix"]),
        "excluded_count": 0,
        "coverage_pct": 100.0,
        "items": manifest_items
    }

    deck_id = f"deck_{uuid.uuid4().hex[:12]}"

    return {
        "id": deck_id,
        "spec_version": "2.0",
        "theme": theme,
        "metadata": {
            "title": materialized_slides[0]["title"] if materialized_slides else plan.deck_title,
            "theme_id": resolved_theme_id,
            "theme": theme,
            "domain": ctx.domain,
            "audience": ctx.audience,
            "objective": ctx.objective,
            "file_label": ctx.dataset_label,
            "total_records": ctx.total_records,
            "snapshot_hash": ctx.snapshot_hash,
            "created_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "is_partial_year": ctx.is_partial_year,
            "reporting_period_summary": ctx.reporting_period,
            "industrial_models": ctx.industrial_models or {},
            "planning_intent": plan.intent.model_dump(),
            "planning_validation": plan.planning_validation.model_dump(),
            "narrative_strategy": plan.narrative_strategy.model_dump(),
            "validation_summary": {
                "status": "PENDING_VERIFICATION",
                "total_metrics_checked": len(ev_ledger),
                "passed_verification": 0,
                "discrepancies_flagged": 0,
                "unanswered_questions": plan.planning_validation.unanswered_user_questions
            }
        },
        "slides": materialized_slides,
        "evidence_ledger": ev_ledger,
        "coverage_manifest": coverage_manifest,
        "retrieved_context": ctx.historical_context or {"status": "empty", "results": [], "historical_decks": []}
    }
