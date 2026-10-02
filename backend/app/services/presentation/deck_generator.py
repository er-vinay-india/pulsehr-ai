import datetime
import logging
import os
import re
from typing import Any
import uuid

from ..display_formatters import format_display_label
from .ai_enrichment import _call_ai_presentation_enrichment
from .ai_deck_planner import plan_deck_with_ai
from .ai_slide_materializer import materialize_ai_deck
from .chart_synthesizer import synthesize_presentation_charts
from .data_profiler import profile_presentation_dataset
from .scope_detector import detect_sheet_date_range
from .storyline_generator import plan_dynamic_storyline
from .builders import (
    THEMES,
    build_default_evidence_ledger,
    build_executive_title_cover_slide,
    build_executive_summary_slide,
    build_baseline_scope_slide,
    build_strengths_slides,
    build_headwinds_slides,
    build_industrial_slides,
    build_boundary_and_evidence_slides,
    build_roadmap_slides,
    build_evidence_ledger_slides,
)
from .persona_router import detect_dataset_persona
from ...core import config

logger = logging.getLogger(__name__)


def materialize_slide_visuals(slides: list[dict[str, Any]], theme_id: str = "executive_dark") -> list[dict[str, Any]]:
    """Phase 6: Visual Intelligence Engine materialization for slides and chart specifications."""
    total_slide_count = len(slides)
    try:
        from .visual import VisualIntelligenceEngine
        v_engine = VisualIntelligenceEngine()
        for idx, s in enumerate(slides):
            s["total_slides"] = total_slide_count
            v_spec = v_engine.process_slide(
                s,
                theme_id=theme_id,
                sequence_number=idx + 1,
                total_slides=total_slide_count
            )
            s["visual_spec"] = v_spec.model_dump()
            # If slide didn't have chart but visual spec selected one
            if v_spec.chart_spec and not s.get("chart"):
                s["chart"] = {
                    "type": v_spec.chart_spec.family.value.lower(),
                    "title": v_spec.chart_spec.title,
                    "subtitle": v_spec.chart_spec.subtitle,
                    "categories": v_spec.chart_spec.categories,
                    "series": [{"name": ser.name, "values": ser.data} for ser in v_spec.chart_spec.series]
                }
    except Exception as exc:
        logger.warning(f"Visual Intelligence materialization encountered issue, preserving base slides: {exc}")
        for s in slides:
            s["total_slides"] = total_slide_count
    return slides


def generate_presentation_deck_spec(
    scope: dict[str, Any],
    dataset_context: dict[str, Any],
    workspace_evidence: dict[str, Any] | None = None,
    on_slide_progress: Any = None,
    on_phase_progress: Any = None,
    on_slide_start: Any = None,
    materialize_visuals_now: bool = False
) -> dict[str, Any]:
    """Generates a complete, validated, evidence-driven PresentationDeckSpec.

    Adheres strictly to the Data-Driven Presentation Standard:
    1. Source data is the ground truth (no invented facts or quotas).
    2. Explicitly surfaces the dataset in early Analysis Scope slide.
    3. Storyline is dynamically generated from data characteristics.
    4. Executive summary communicates concrete counts and percentages.
    5. Traceable slide_metrics maintained internally.
    """
    if scope.get("deck_style") == "decision_brief":
        from .decision_deck import generate_decision_deck
        if not workspace_evidence or "decision_brief" not in workspace_evidence:
            raise ValueError("Decision brief requires a scoped evidence snapshot.")
        return generate_decision_deck(scope, workspace_evidence["decision_brief"], on_slide_progress)

    target_sheet = dataset_context["target_sheet"]
    records = dataset_context["records"]
    from .hr_report import build_hr_report
    hr_deck = build_hr_report(scope, dataset_context, workspace_evidence)
    if hr_deck is not None:
        total = len(hr_deck["slides"])
        for idx, slide in enumerate(hr_deck["slides"], 1):
            if callable(on_slide_start):
                on_slide_start(idx, total, slide["title"], slide["category"])
            if callable(on_slide_progress):
                on_slide_progress(idx, total, slide["title"], slide["category"], slide_dict=slide)
        if materialize_visuals_now:
            hr_deck["slides"] = materialize_slide_visuals(hr_deck["slides"], hr_deck["metadata"]["theme_id"])
        return hr_deck
    domain = dataset_context["domain"]
    ground_truth = dataset_context["ground_truth"]
    snapshot_hash = dataset_context["snapshot_hash"]
    visuals = dataset_context["visuals"]

    detected_persona = detect_dataset_persona(dataset_context)
    persona_report_title = detected_persona.get("standard_report_name") or "Executive Operational Review & Strategic Performance Diagnostic"

    raw_obj = scope.get("objective")
    if not raw_obj or raw_obj == "Executive Leadership Review":
        objective = persona_report_title
    else:
        objective = raw_obj

    raw_aud = scope.get("audience")
    if not raw_aud or raw_aud == "C-Suite & Operations Leadership":
        audience = detected_persona.get("target_audience") or "C-Suite & Operations Leadership"
    else:
        audience = raw_aud

    theme_id = scope.get("theme_id") or "executive_dark"
    theme = THEMES.get(theme_id, THEMES.get("executive_dark", {}))
    instructions = scope.get("instructions") or ""

    is_sales = "sales" in domain.lower() or "commercial" in domain.lower() or "retail" in domain.lower()
    is_hr = "workforce" in domain.lower() or "people" in domain.lower() or "hr" in domain.lower() or "attendance" in domain.lower()
    is_audit = "audit" in domain.lower() or "compliance" in domain.lower() or "risk" in domain.lower()

    # Step 1: Deep Data Profiling & Traceable Metrics Calculation
    columns = dataset_context.get("columns", [])
    profiled_data = profile_presentation_dataset(records, columns)
    total_records = profiled_data["total_records"]
    completeness_pct = profiled_data["completeness_pct"]
    traceable_metrics = profiled_data["traceable_metrics"]

    # Synthesize Charts
    chart_pack = synthesize_presentation_charts(None, scope, dataset_context, workspace_evidence=workspace_evidence)
    line_chart = chart_pack.get("line_chart")
    bar_chart = chart_pack.get("bar_chart")
    donut_chart = chart_pack.get("donut_chart")
    rel_chart = chart_pack.get("rel_chart")

    mean_sales = ground_truth.get("mean_weekly_sales") or ground_truth.get("average_weekly_sales")
    if mean_sales is None:
        for k, v in ground_truth.items():
            if "sales" in k.lower() and isinstance(v, (int, float)):
                mean_sales = v
                break
    if mean_sales is None:
        mean_sales = float(total_records)

    deck_id = f"deck_{uuid.uuid4().hex[:12]}"
    file_label = target_sheet["original_name"]

    # Scope & Evidence integration
    if workspace_evidence:
        preflight = workspace_evidence.get("preflight", {})
        included_sheets = workspace_evidence.get("included_sheets", [])
        evidence_ledger = workspace_evidence.get("evidence_ledger") or workspace_evidence.get("candidate_findings") or []
        snapshot_hash = workspace_evidence.get("snapshot_hash", "000000000000")
        reporting_period_summary = workspace_evidence.get("reporting_period_summary", "Current Period")
        is_partial_year = workspace_evidence.get("is_partial_year", False)
        disconnected_boundary_note = workspace_evidence.get("disconnected_boundary_note", "Single dataset evaluated on verified empirical records.")
        total_eval_records = workspace_evidence.get("total_records", total_records)
        ev_kpi = next((e for e in evidence_ledger if e.get("evidence_id") == "EVID-KPI-01"), None)
        if ev_kpi and ev_kpi.get("numeric_value") is not None:
            mean_sales = float(ev_kpi["numeric_value"])
    else:
        date_info = detect_sheet_date_range(records, columns)
        is_partial_year = date_info["is_partial_year"]
        reporting_period_summary = date_info["period_label"]
        disconnected_boundary_note = "Single dataset evaluated on verified empirical records."
        total_eval_records = total_records
        included_sheets = [{
            "id": target_sheet["id"],
            "name": target_sheet["name"],
            "original_name": file_label,
            "row_count": total_records
        }]
        preflight = {
            "validated_relationships": [],
            "relationship_coverage_pct": 100.0 if total_records > 0 else 0.0,
            "included_sheets": included_sheets
        }
        mean_val_str_calc = f"${mean_sales:,.2f}" if (is_sales and mean_sales) else (f"{mean_sales:,.2f}" if mean_sales else f"{total_records:,}")

        # Data-driven dispersion and surge metrics from profiling
        disp_metric_str = "Dispersion Uncalculated"
        disp_num_val = None
        cat_prof = profiled_data.get("categorical_profile", {})
        if cat_prof.get("has_categorical_data"):
            dims = cat_prof.get("dimensions", [])
            meas = cat_prof.get("measures", [])
            if dims and meas:
                b_info = cat_prof.get("breakdowns", {}).get(dims[0], {}).get(meas[0])
                if b_info and b_info.get("dispersion_ratio"):
                    disp_num_val = float(b_info["dispersion_ratio"])
                    disp_metric_str = f"{disp_num_val}x Spread"

        surge_metric_str = "Longitudinal surge not recorded"
        temp_prof = profiled_data.get("temporal_profile", {})
        if temp_prof.get("has_temporal_data"):
            weekly = temp_prof.get("weekly", {})
            if weekly.get("avg_wow_velocity") is not None:
                surge_metric_str = f"{weekly['avg_wow_velocity']:+.1f}% WoW Momentum"

        evidence_ledger = build_default_evidence_ledger(
            file_label=file_label,
            total_records=total_records,
            mean_val_str=mean_val_str_calc,
            dispersion_metric_str=disp_metric_str,
            snapshot_hash=snapshot_hash,
            reporting_period_summary=reporting_period_summary,
            is_partial_year=is_partial_year,
            mean_sales=mean_sales,
            surge_metric_str=surge_metric_str,
            dispersion_numeric_val=disp_num_val
        )

    source_summary = f"{len(included_sheets)} dataset source(s)" if len(included_sheets) > 1 else target_sheet["original_name"]

    # Ingest Executive Overview Visual Dashboard & Prioritized Facts
    visual_dashboard = dataset_context.get("visual_dashboard") or {}
    prioritized_facts = visual_dashboard.get("prioritized_facts", [])
    if not prioritized_facts and workspace_evidence and "shared_package" in workspace_evidence:
        prioritized_facts = workspace_evidence["shared_package"].get("prioritized_facts", [])

    workspace_visuals = (
        workspace_evidence.get("workspace_visuals")
        if workspace_evidence and workspace_evidence.get("workspace_visuals")
        else visual_dashboard.get("visualizations", [])
    )
    industrial_models = (
        workspace_evidence.get("industrial_models")
        if workspace_evidence and workspace_evidence.get("industrial_models")
        else visual_dashboard.get("industrial_models", {})
    )

    strengths = [f for f in prioritized_facts if f.get("badge") == "strength"]
    attentions = [f for f in prioritized_facts if f.get("badge") in ("attention", "headwind", "risk")]

    if strengths:
        ev3 = next((e for e in evidence_ledger if e.get("evidence_id") == "EVID-STRENGTH-01"), None)
        if ev3 and (not ev3.get("metric_value") or ev3.get("metric_value") in ("+7.8% Surge", "Single-Period Baseline") or not workspace_evidence):
            ev3["metric_name"] = strengths[0].get("badge_label", "Peak Operating Volume")
            comp_str = f" ({strengths[0].get('comparison')})" if strengths[0].get("comparison") else ""
            ev3["metric_value"] = f"{strengths[0].get('value', '')}{comp_str}"
            from .claim_verifier import _extract_unit
            ev3["unit"] = _extract_unit(strengths[0].get("value", ""))
            nums = re.findall(r'[\d,.]+', strengths[0].get("value", ""))
            if nums:
                try:
                    ev3["numeric_value"] = float(nums[0].replace(",", ""))
                except ValueError:
                    pass
        if len(strengths) >= 2:
            ev3b = next((e for e in evidence_ledger if e.get("evidence_id") in ("EVID-STRENGTH-02", strengths[1].get("id"))), None)
            if not ev3b:
                nums2 = re.findall(r'[\d,.]+', strengths[1].get("value", ""))
                comp_str2 = f" ({strengths[1].get('comparison')})" if strengths[1].get("comparison") else ""
                ev3b = {
                    "evidence_id": strengths[1].get("id") or "EVID-STRENGTH-02",
                    "title": strengths[1].get("headline", "Workforce Operational Leadership"),
                    "metric_name": strengths[1].get("badge_label", "Strength"),
                    "metric_value": f"{strengths[1].get('value', '')}{comp_str2}",
                    "numeric_value": float(nums2[0].replace(",", "")) if nums2 else None,
                    "unit": "pts",
                    "source_sheets": [source_summary],
                    "row_count": total_records
                }
                evidence_ledger.append(ev3b)
    if attentions:
        ev4 = next((e for e in evidence_ledger if e.get("evidence_id") == "EVID-HEADWIND-01"), None)
        if ev4 and (not ev4.get("metric_value") or ev4.get("metric_value") in ("8.11x Spread", "Dispersion Not Observed") or not workspace_evidence):
            ev4["metric_name"] = attentions[0].get("badge_label", "Operational Review")
            comp_str4 = f" ({attentions[0].get('comparison')})" if attentions[0].get("comparison") else ""
            ev4["metric_value"] = f"{attentions[0].get('value', '')}{comp_str4}"
            nums = re.findall(r'[\d,.]+', attentions[0].get("value", ""))
            if nums:
                try:
                    ev4["numeric_value"] = float(nums[0].replace(",", ""))
                except ValueError:
                    pass

    ev4_ref = next((e for e in evidence_ledger if e.get("evidence_id") == "EVID-HEADWIND-01"), {})
    if ev4_ref.get("metric_value"):
        dispersion_metric_str = ev4_ref.get("metric_value")
    elif attentions:
        dispersion_metric_str = attentions[0].get("value", "Identified Spread")
    elif profiled_data.get("numeric_rankings") and profiled_data["numeric_rankings"][0].get("dispersion_ratio"):
        dispersion_metric_str = f"{profiled_data['numeric_rankings'][0]['dispersion_ratio']}x Spread"
    elif profiled_data.get("ranked_categorical") and len(profiled_data["ranked_categorical"][0].get("top_categories", [])) >= 2:
        tc = profiled_data["ranked_categorical"][0]["top_categories"][0]["count"]
        bc = max(1, profiled_data["ranked_categorical"][0]["top_categories"][-1]["count"])
        dispersion_metric_str = f"{round(tc / bc, 1)}x Ratio"
    else:
        dispersion_metric_str = "Verified Benchmark"

    source_summary = f"{len(included_sheets)} dataset source(s)" if len(included_sheets) > 1 else target_sheet["original_name"]
    mean_val_str = f"${mean_sales:,.2f}" if (is_sales and mean_sales) else (f"{mean_sales:,.2f}" if mean_sales else f"{total_records:,}")

    # Category concentration phrasing for executive summary (e.g. 187 of 232 records — 80.6%)
    cat_summary = ""
    if profiled_data.get("ranked_categorical"):
        top_c_dim = profiled_data["ranked_categorical"][0]
        if top_c_dim.get("top_categories"):
            lead_c = top_c_dim["top_categories"][0]
            cat_summary = f" (Led by {lead_c['category']}: {lead_c['count']:,} of {total_eval_records:,} records — {lead_c['percentage']}%)"

    # Ground-truth evidence ledger entries for Data Completeness and Category Share
    has_comp_ev = any(e.get("evidence_id") in ("EVID-COMP-01", "EVID-GOV-02") or e.get("metric_name", "").lower() in ("data completeness", "completeness") for e in evidence_ledger)
    if not has_comp_ev:
        evidence_ledger.append({
            "evidence_id": "EVID-COMP-01",
            "finding_id": "FINDING-DATA-COMPLETENESS",
            "title": "Audited Dataset Completeness & Record Integrity",
            "finding_type": "measured_fact",
            "source_sheets": [source_summary],
            "row_count": total_eval_records,
            "date_range": reporting_period_summary,
            "is_partial_year": is_partial_year,
            "metric_name": "Data Completeness",
            "metric_value": f"{completeness_pct:.1f}%",
            "numeric_value": float(completeness_pct),
            "unit": "%",
            "calculation_methodology": "Ratio of valid non-null cells across evaluated matrix rows.",
            "what_it_establishes": f"Confirms {completeness_pct:.1f}% data completeness across evaluated columns.",
            "what_it_does_not_establish": "Does not impute missing values without explicit instructions."
        })

    if cat_summary and profiled_data.get("ranked_categorical"):
        top_c_dim = profiled_data["ranked_categorical"][0]
        if top_c_dim.get("top_categories"):
            lead_c = top_c_dim["top_categories"][0]
            has_cat_ev = any(e.get("evidence_id") == "EVID-CAT-01" or str(e.get("numeric_value")) == str(lead_c.get("percentage")) for e in evidence_ledger)
            if not has_cat_ev:
                evidence_ledger.append({
                    "evidence_id": "EVID-CAT-01",
                    "finding_id": "FINDING-CATEGORY-CONCENTRATION",
                    "title": f"Category Concentration: {lead_c['category']}",
                    "finding_type": "measured_fact",
                    "source_sheets": [source_summary],
                    "row_count": lead_c["count"],
                    "date_range": reporting_period_summary,
                    "is_partial_year": is_partial_year,
                    "metric_name": "Leading Category Share",
                    "metric_value": f"{lead_c['percentage']}%",
                    "numeric_value": float(lead_c["percentage"]),
                    "unit": "%",
                    "calculation_methodology": "Leading category row count divided by total records.",
                    "what_it_establishes": f"Isolates volume concentration in {lead_c['category']}.",
                    "what_it_does_not_establish": "Does not establish causal concentration."
                })

    if donut_chart and donut_chart.get("categories"):
        seg_count = len(donut_chart["categories"])
        has_seg_ev = any(e.get("evidence_id") == "EVID-SEGMENTS-01" or e.get("metric_name", "").lower() == "segment count" for e in evidence_ledger)
        if not has_seg_ev:
            evidence_ledger.append({
                "evidence_id": "EVID-SEGMENTS-01",
                "finding_id": "FINDING-SEGMENT-COUNT",
                "title": "Evaluated Segment Count",
                "finding_type": "measured_fact",
                "source_sheets": [source_summary],
                "row_count": total_eval_records,
                "date_range": reporting_period_summary,
                "is_partial_year": is_partial_year,
                "metric_name": "Segment Count",
                "metric_value": f"{seg_count} Categories",
                "numeric_value": float(seg_count),
                "unit": "count",
                "calculation_methodology": "Distinct category segments evaluated in distribution visual.",
                "what_it_establishes": f"Confirms {seg_count} distinct operational categories.",
                "what_it_does_not_establish": "Does not establish sub-segment micro-variances."
            })

    if bar_chart and bar_chart.get("categories"):
        lead_cat = str(bar_chart["categories"][0])
    elif profiled_data.get("ranked_categorical") and profiled_data["ranked_categorical"][0].get("leading_category"):
        lead_cat = str(profiled_data["ranked_categorical"][0]["leading_category"])
    else:
        lead_cat = "Primary Operating Unit"

    # Phase 2: Qwen Presentation Director (hierarchical bounded planning - primary path)
    slides: list[dict[str, Any]] = []
    director_deck_spec = None
    if scope.get("enable_ai_planner", True) and not scope.get("force_legacy_builders", False):
        try:
            from .director import (
                presentation_director,
                PresentationPlanningContext,
                PresentationBrief,
                SlideCountConstraint,
            )
            constraint = SlideCountConstraint.from_inputs(
                instructions=instructions,
                target_length=scope.get("target_length"),
                default_mode=getattr(config, "PRESENTATION_DEFAULT_SLIDE_COUNT_MODE", "ADAPTIVE")
            )
            brief_obj = PresentationBrief(
                objective=objective,
                audience=audience,
                decision_requested=scope.get("decision_requested") or "",
                main_takeaway=scope.get("main_takeaway") or "",
                presentation_time_minutes=scope.get("presentation_time_minutes") or 15,
                deliverable=scope.get("deliverable") or "pptx",
                content_preferences=scope.get("content_preferences") or {},
                citation_requirement=scope.get("citation_requirement") or "standard",
                motion_preference=scope.get("motion_preference") or "none",
                is_inferred=not bool(scope.get("decision_requested") and scope.get("main_takeaway"))
            )
            brief_obj.success_criterion = brief_obj.build_success_criterion()

            planning_ctx = PresentationPlanningContext(
                domain=domain,
                objective=objective,
                audience=audience,
                instructions=instructions,
                dataset_label=file_label,
                total_records=total_eval_records,
                completeness_pct=completeness_pct,
                baseline_benchmark=mean_val_str,
                dispersion_metric=dispersion_metric_str,
                reporting_period=reporting_period_summary,
                is_partial_year=is_partial_year,
                brief=brief_obj,
                dataset_profiles=[profiled_data] if profiled_data else [],
                current_evidence=evidence_ledger,
                historical_context=workspace_evidence.get("retrieved_context", {}) if workspace_evidence else {},
                available_charts={
                    "line_chart": line_chart is not None,
                    "bar_chart": bar_chart is not None,
                    "donut_chart": donut_chart is not None,
                },
                industrial_models=industrial_models or {},
                slide_count_constraint=constraint,
                workspace_id=scope.get("workspace_id"),
                theme_id=theme_id,
                snapshot_hash=snapshot_hash
            )
            # Phase 3: IBM Granite 4.0 Presentation Execution Orchestrator
            if getattr(config, "PRESENTATION_ORCHESTRATOR_ENABLED", True):
                from .orchestrator import presentation_orchestrator
                plan_spec = presentation_director.plan_presentation(planning_ctx)
                director_deck_spec, _ = presentation_orchestrator.orchestrate(
                    plan_spec=plan_spec,
                    ctx=planning_ctx,
                    theme=theme,
                    theme_id=theme_id,
                    chart_pack=chart_pack,
                    profiled_data=profiled_data,
                    evidence_ledger=evidence_ledger,
                    on_slide_progress=on_slide_progress,
                    on_slide_start=on_slide_start
                )
            else:
                director_deck_spec = presentation_director.plan_and_adapt(
                    ctx=planning_ctx,
                    theme=theme,
                    theme_id=theme_id,
                    chart_pack=chart_pack,
                    profiled_data=profiled_data,
                    evidence_ledger=evidence_ledger,
                    on_slide_progress=on_slide_progress,
                    on_slide_start=on_slide_start
                )
            if director_deck_spec and not director_deck_spec.get("metadata", {}).get("planning_validation", {}).get("is_valid", False):
                raise ValueError("Presentation plan lacks supported answers or claims.")
            if director_deck_spec and director_deck_spec.get("slides") and len(director_deck_spec["slides"]) >= 4:
                slides = director_deck_spec["slides"]
                logger.info(f"Presentation Orchestrator successfully generated {len(slides)} slides.")
        except Exception as exc:
            logger.exception(f"Presentation Director / Orchestrator execution failed, falling back to deterministic builders: {exc}")
            slides = []

    if not slides:
        from .grounded_review import build_grounded_review
        deck = build_grounded_review(scope, dataset_context, workspace_evidence)
        if materialize_visuals_now:
            deck["slides"] = materialize_slide_visuals(deck["slides"], theme_id)
        return deck

    if not slides:
        # Legacy builders remain encapsulated for historical deck compatibility.
        # Phase 2: High-fidelity deterministic builder pipeline (guaranteed fallback)
        target_count = int(scope.get("target_length") or 8)

        def _notify_slide_start(title: str, category: str = ""):
            if on_slide_start and callable(on_slide_start):
                try:
                    on_slide_start(len(slides) + 1, target_count, title, category)
                except Exception:
                    pass

        def _notify_slide(s: dict[str, Any]):
            if on_slide_progress and callable(on_slide_progress):
                try:
                    on_slide_progress(len(slides), target_count, s.get("title", f"Slide {len(slides)}"), s.get("category", ""), slide_dict=s)
                except Exception:
                    pass

        # Slide 1: Executive Title Cover (Beautified Boardroom Title Slide)
        _notify_slide_start(persona_report_title, "Executive")
        slide_cover = build_executive_title_cover_slide(
            persona=detected_persona,
            included_sheets=included_sheets,
            total_eval_records=total_eval_records,
            reporting_period_summary=reporting_period_summary,
            file_label=file_label,
            evidence_ledger=evidence_ledger,
            current_slide_order=len(slides) + 1
        )
        slides.append(slide_cover)
        _notify_slide(slide_cover)

        # Slide 2: Executive Summary
        _notify_slide_start("Executive Summary & Core Performance", "Strategy")
        slide_1 = build_executive_summary_slide(
            target_sheet=target_sheet,
            included_sheets=included_sheets,
            total_eval_records=total_eval_records,
            completeness_pct=completeness_pct,
            mean_val_str=mean_val_str,
            dispersion_metric_str=dispersion_metric_str,
            reporting_period_summary=reporting_period_summary,
            cat_summary=cat_summary,
            file_label=file_label,
            evidence_ledger=evidence_ledger,
            is_partial_year=is_partial_year,
            current_slide_order=len(slides) + 1
        )
        slides.append(slide_1)
        _notify_slide(slide_1)

        # Slide 2: Analysis Scope & Baseline
        _notify_slide_start("Analysis Scope & Dataset Governance", "Governance")
        slide_2 = build_baseline_scope_slide(
            included_sheets=included_sheets,
            source_summary=source_summary,
            total_eval_records=total_eval_records,
            completeness_pct=completeness_pct,
            mean_val_str=mean_val_str,
            dispersion_metric_str=dispersion_metric_str,
            reporting_period_summary=reporting_period_summary,
            evidence_ledger=evidence_ledger,
            is_partial_year=is_partial_year,
            current_slide_order=len(slides) + 1
        )
        slides.append(slide_2)
        _notify_slide(slide_2)

        # Section 3: Operational Strengths
        strength_slides = build_strengths_slides(
            strengths=strengths,
            line_chart=line_chart,
            source_summary=source_summary,
            evidence_ledger=evidence_ledger,
            is_partial_year=is_partial_year,
            start_order=len(slides) + 1
        )
        for s in strength_slides:
            _notify_slide_start(s.get("title", f"Slide {len(slides)+1}"), s.get("category", "Operations"))
            slides.append(s)
            _notify_slide(s)

        # Section 4: Operational Headwinds
        headwind_slides = build_headwinds_slides(
            attentions=attentions,
            bar_chart=bar_chart,
            profiled_data=profiled_data,
            dispersion_metric_str=dispersion_metric_str,
            source_summary=source_summary,
            evidence_ledger=evidence_ledger,
            is_partial_year=is_partial_year,
            start_order=len(slides) + 1
        )
        for s in headwind_slides:
            _notify_slide_start(s.get("title", f"Slide {len(slides)+1}"), s.get("category", "Diagnostic"))
            slides.append(s)
            _notify_slide(s)

        # Section 5: Industrial Analytics Suite (9-Box, Burnout Strain, Bradford Factor, Relational)
        industrial_slides = build_industrial_slides(
            industrial_models=industrial_models,
            donut_chart=donut_chart,
            bar_chart=bar_chart,
            total_eval_records=total_eval_records,
            source_summary=source_summary,
            evidence_ledger=evidence_ledger,
            is_partial_year=is_partial_year,
            start_order=len(slides) + 1
        )
        for s in industrial_slides:
            _notify_slide_start(s.get("title", f"Slide {len(slides)+1}"), s.get("category", "Diagnostic"))
            slides.append(s)
            _notify_slide(s)

        # Section 6: Governance Boundaries & Data Evidence Table
        gov_slides = build_boundary_and_evidence_slides(
            total_eval_records=total_eval_records,
            reporting_period_summary=reporting_period_summary,
            source_summary=source_summary,
            profiled_data=profiled_data,
            mean_val_str=mean_val_str,
            completeness_pct=completeness_pct,
            dispersion_metric_str=dispersion_metric_str,
            snapshot_hash=snapshot_hash,
            evidence_ledger=evidence_ledger,
            is_partial_year=is_partial_year,
            start_order=len(slides) + 1
        )
        for s in gov_slides:
            _notify_slide_start(s.get("title", f"Slide {len(slides)+1}"), s.get("category", "Governance"))
            slides.append(s)
            _notify_slide(s)

        # Section 7: Strategic Roadmap & Execution Governance SLAs
        roadmap_slides = build_roadmap_slides(
            total_eval_records=total_eval_records,
            dispersion_metric_str=dispersion_metric_str,
            lead_cat=lead_cat,
            source_summary=source_summary,
            evidence_ledger=evidence_ledger,
            is_partial_year=is_partial_year,
            start_order=len(slides) + 1
        )
        for s in roadmap_slides:
            _notify_slide_start(s.get("title", f"Slide {len(slides)+1}"), s.get("category", "Roadmap"))
            slides.append(s)
            _notify_slide(s)

        # Section 8: Governance & Evidence Ledger (Single or Multi-part)
        ledger_slides = build_evidence_ledger_slides(
            evidence_ledger=evidence_ledger,
            total_eval_records=total_eval_records,
            snapshot_hash=snapshot_hash,
            included_sheets=included_sheets,
            source_summary=source_summary,
            mean_val_str=mean_val_str,
            dispersion_metric_str=dispersion_metric_str,
            is_partial_year=is_partial_year,
            start_order=len(slides) + 1
        )
        for s in ledger_slides:
            _notify_slide_start(s.get("title", f"Slide {len(slides)+1}"), s.get("category", "Evidence"))
            slides.append(s)
            _notify_slide(s)

    # Batch AI enrichment pass removed to prevent duplicate whole-deck pauses.
    # Executive tone and persona polish is now executed slide-by-slide in the dedicated 'enrichment' pipeline phase.

    total_slide_count = len(slides)
    for s in slides:
        s["total_slides"] = total_slide_count
    if materialize_visuals_now:
        slides = materialize_slide_visuals(slides, theme_id)

    # Generate coverage manifest
    from ..shared_evidence_package import generate_coverage_manifest
    if workspace_evidence and "candidate_findings" in workspace_evidence:
        coverage_manifest = generate_coverage_manifest(workspace_evidence["candidate_findings"], slides, [])
    else:
        coverage_manifest = {
            "main_deck_count": len(slides),
            "appendix_count": 0,
            "excluded_count": 0,
            "coverage_pct": 100.0,
            "items": [
                {"evidence_id": s.get("evidence_id", f"EVID-{i+1:02d}"), "title": s["title"], "disposition": "main_deck", "reason": "Included in presentation main deck"}
                for i, s in enumerate(slides)
            ]
        }

    deck_dict = {
        "id": deck_id,
        "spec_version": "2.0",
        "theme": theme,
        "metadata": {
            "title": persona_report_title if (slides and slides[0].get("layout") == "title_cover") else (slides[0]["title"] if slides else persona_report_title),
            "theme_id": theme_id,
            "theme": theme,
            "domain": domain,
            "audience": audience,
            "objective": objective,
            "detected_persona": detected_persona,
            "persona_key": detected_persona.get("persona_key"),
            "persona_role": detected_persona.get("role_title"),
            "standard_report_name": persona_report_title,
            "file_label": file_label,
            "total_records": total_eval_records,
            "completeness_pct": completeness_pct,
            "snapshot_hash": snapshot_hash,
            "created_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "is_partial_year": is_partial_year,
            "reporting_period_summary": reporting_period_summary,
            "traceable_metrics": traceable_metrics,
            "source_columns": columns,
            "planning_validation": (director_deck_spec or {}).get("metadata", {}).get("planning_validation", {}) if scope.get("enable_ai_planner", True) and not scope.get("force_legacy_builders", False) else {},
            "brief": {
                "objective": objective,
                "audience": audience,
                "decision_requested": scope.get("decision_requested") or "",
                "main_takeaway": scope.get("main_takeaway") or "",
                "presentation_time_minutes": scope.get("presentation_time_minutes") or 15,
                "deliverable": scope.get("deliverable") or "pptx",
                "content_preferences": scope.get("content_preferences") or {},
                "citation_requirement": scope.get("citation_requirement") or "standard",
                "motion_preference": scope.get("motion_preference") or "none",
                "success_criterion": f"After viewing this deck, the audience should understand {scope.get('main_takeaway') or objective} and decide or do {scope.get('decision_requested') or 'align on operational priority initiatives'}.",
                "is_inferred": not bool(scope.get("decision_requested") and scope.get("main_takeaway")),
            },
            "success_criterion": f"After viewing this deck, the audience should understand {scope.get('main_takeaway') or objective} and decide or do {scope.get('decision_requested') or 'align on operational priority initiatives'}.",
            "is_brief_inferred": not bool(scope.get("decision_requested") and scope.get("main_takeaway")),
            "validation_summary": {
                "status": "PENDING_VERIFICATION",
                "total_metrics_checked": len(evidence_ledger),
                "passed_verification": 0,
                "discrepancies_flagged": 0
            }
        },
        "slides": slides,
        "evidence_ledger": evidence_ledger,
        "coverage_manifest": coverage_manifest,
        "retrieved_context": workspace_evidence.get("retrieved_context", {"status": "empty", "results": [], "historical_decks": []}) if workspace_evidence else {"status": "empty", "results": [], "historical_decks": []}
    }

    from .content_validation import semantic_issues
    if semantic_issues(deck_dict, columns):
        from .grounded_review import build_grounded_review
        deck_dict = build_grounded_review(scope, dataset_context, workspace_evidence)
    from .audience_content import polish_audience_content
    deck_dict = polish_audience_content(deck_dict, bool(scope.get("content_preferences", {}).get("technical_appendix")))

    # Reorder presentation deck into canonical presentation sequence
    from .presentation_reorderer import reorder_presentation_deck
    deck_dict = reorder_presentation_deck(deck_dict)

    # Evaluate automated claim verification and review gates
    from .claim_verifier import verify_presentation_claims
    from .review_gates import evaluate_automated_gates
    actual_verification = verify_presentation_claims(deck_dict, evidence_ledger)
    deck_dict["metadata"]["validation_summary"] = actual_verification
    deck_dict["metadata"]["review_gates"] = evaluate_automated_gates(
        deck_spec=deck_dict,
        verification_summary=actual_verification,
        brief=deck_dict["metadata"]["brief"]
    )
    return deck_dict
