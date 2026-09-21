from typing import Any
import uuid

from .common import calculate_timing, find_evidence, format_briefing


def build_headwinds_slides(
    attentions: list[dict[str, Any]],
    bar_chart: dict[str, Any] | None,
    profiled_data: dict[str, Any],
    dispersion_metric_str: str,
    source_summary: str,
    evidence_ledger: list[dict[str, Any]],
    is_partial_year: bool,
    start_order: int
) -> list[dict[str, Any]]:
    slides: list[dict[str, Any]] = []
    ev4 = find_evidence(evidence_ledger, "EVID-HEADWIND-01")

    if bar_chart and bar_chart.get("categories"):
        lead_cat = str(bar_chart["categories"][0])
    elif profiled_data.get("ranked_categorical") and profiled_data["ranked_categorical"][0].get("leading_category"):
        lead_cat = str(profiled_data["ranked_categorical"][0]["leading_category"])
    else:
        lead_cat = "Primary Operating Unit"

    disp_suffix = "" if dispersion_metric_str.endswith(" Spread") or dispersion_metric_str.endswith(" Ratio") else " Spread"

    if attentions:
        top_att = attentions[0]
        s4_title = top_att.get("headline", "Operational Headwinds Identified")
        if len(s4_title) > 78:
            s4_title = s4_title[:75] + "..."
        s4_sub = f"{top_att.get('badge_label', 'Attention Priority')} · Target for management focus"
        s4_narrative = (
            f"[Evidence] {top_att.get('headline', '')}. {top_att.get('comparison', '')}. "
            f"[Interpretation] {top_att.get('why_it_matters', 'Operational variance represents significant untapped capacity.')}"
        )
        s4_bullets = [
            f"[Evidence] {top_att.get('headline', '')} ({top_att.get('value', '')}).",
            f"[Interpretation] {top_att.get('why_it_matters', '')}",
            "[Recommendation] Address underlying root causes through structured workflow standardization."
        ]
        s4_script = f"Turning to operational headwinds: {top_att.get('headline', '')}. {top_att.get('why_it_matters', '')}"
        s4_metrics = [
            {"label": top_att.get("badge_label", "Priority"), "value": top_att.get("value", dispersion_metric_str), "subtext": top_att.get("comparison", "Action Required")},
            {"label": "Benchmark Unit", "value": lead_cat, "subtext": "Current anchor"}
        ]
    else:
        s4_title = f"{lead_cat} Outpaces Lower-Quartile Units by {dispersion_metric_str}{disp_suffix}"
        if len(s4_title) > 78:
            s4_title = f"Operational Headwinds: {dispersion_metric_str} Dispersion Identified"
        s4_sub = "Factual, neutral identification of entity-level variance requiring management focus"
        s4_narrative = (
            f"[Evidence] Comparative benchmarking reveals substantial productivity dispersion across operating locations, "
            f"with top performer **{lead_cat}** outpacing lower-quartile units by **{dispersion_metric_str}**. "
            f"[Interpretation] Operational variance represents significant untapped capacity if systematic workflow standardization is applied."
        )
        s4_bullets = [
            f"[Evidence] Top performing entity ({lead_cat}) outpaces lower-quartile locations by {dispersion_metric_str}.",
            f"[Derived Metric] Entity productivity variance accounts for substantial operational opportunity.",
            f"[Interpretation] Standardizing operating playbooks could elevate lower-quartile performance significantly."
        ]
        s4_script = f"Turning to operational headwinds: comparative benchmarks identify an {dispersion_metric_str} dispersion between top performer {lead_cat} and lower-quartile locations."
        s4_metrics = [
            {"label": "Dispersion Ratio", "value": dispersion_metric_str, "subtext": "Leader vs laggard"},
            {"label": "Top Performer", "value": lead_cat, "subtext": "Benchmark leader"}
        ]

    s4_notes = format_briefing(
        ev4,
        s4_title,
        f"Significant operational leverage exists in reducing the {dispersion_metric_str} spread across units.",
        "Comparative bar chart contrasting high-performing units against lower-quartile cohorts.",
        s4_script
    )
    slides.append({
        "id": f"slide_{uuid.uuid4().hex[:8]}",
        "stable_slide_id": "slide_operational_headwinds",
        "order": start_order + len(slides),
        "layout": "chart_narrative" if bar_chart else "comparison_split",
        "category": "OPERATIONAL HEADWINDS",
        "title": s4_title,
        "subtitle": s4_sub,
        "narrative": s4_narrative,
        "bullets": s4_bullets,
        "metrics": s4_metrics,
        "chart": bar_chart,
        "table": None,
        "speaker_notes": s4_notes,
        "narration_script": s4_script,
        "reading_order": ["category", "title", "subtitle", "narrative", "chart", "metrics", "bullets", "footer"],
        "timing_metadata": calculate_timing(s4_script),
        "evidence_id": "EVID-HEADWIND-01",
        "evidence_item": ev4,
        "evidence_sources": [source_summary],
        "is_partial_year": is_partial_year
    })

    # Section 4B: Additional Headwind / Retention Risk (if available)
    if len(attentions) >= 2:
        second_att = attentions[1]
        s4b_title = second_att.get("headline", "Workforce Risk Area")
        if len(s4b_title) > 78:
            s4b_title = s4b_title[:75] + "..."
        s4b_sub = f"{second_att.get('badge_label', 'Headwind')} · Empirical variance requiring mitigation"
        s4b_narrative = (
            f"[Evidence] {second_att.get('headline', '')}. {second_att.get('comparison', '')}. "
            f"[Interpretation] {second_att.get('why_it_matters', 'Targeted intervention is required.')}"
        )
        s4b_script = f"Secondary risk area: {second_att.get('headline', '')}. {second_att.get('why_it_matters', '')}"
        s4b_notes = format_briefing(
            ev4,
            s4b_title,
            "Documents secondary operational risks requiring structured management check-ins.",
            "Comparison split highlighting empirical metrics against baseline risk thresholds.",
            s4b_script
        )
        slides.append({
            "id": f"slide_{uuid.uuid4().hex[:8]}",
            "stable_slide_id": "slide_operational_headwinds_secondary",
            "order": start_order + len(slides),
            "layout": "comparison_split",
            "category": "OPERATIONAL HEADWINDS",
            "title": s4b_title,
            "subtitle": s4b_sub,
            "narrative": s4b_narrative,
            "bullets": [
                f"[Evidence] {second_att.get('headline', '')} ({second_att.get('value', '')}).",
                f"[Interpretation] {second_att.get('why_it_matters', '')}",
                "[Recommendation] Implement early warning check-ins to stabilize risk cohorts."
            ],
            "metrics": [
                {"label": second_att.get("badge_label", "Risk Area"), "value": second_att.get("value", "Flagged"), "subtext": second_att.get("comparison", "Action Required")},
                {"label": "Risk Level", "value": "Elevated", "subtext": "Review Priority"}
            ],
            "chart": None,
            "table": None,
            "speaker_notes": s4b_notes,
            "narration_script": s4b_script,
            "reading_order": ["category", "title", "subtitle", "narrative", "metrics", "bullets", "footer"],
            "timing_metadata": calculate_timing(s4b_script),
            "evidence_id": "EVID-HEADWIND-01",
            "evidence_item": ev4,
            "evidence_sources": [source_summary],
            "is_partial_year": is_partial_year
        })

    return slides
