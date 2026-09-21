from typing import Any
import uuid

from app.services.display_formatters import format_display_label
from .common import calculate_timing, find_evidence, format_briefing


def build_executive_summary_slide(
    target_sheet: dict[str, Any],
    included_sheets: list[dict[str, Any]],
    total_eval_records: int,
    completeness_pct: float,
    mean_val_str: str,
    dispersion_metric_str: str,
    reporting_period_summary: str,
    cat_summary: str,
    file_label: str,
    evidence_ledger: list[dict[str, Any]],
    is_partial_year: bool,
    current_slide_order: int
) -> dict[str, Any]:
    ev1 = find_evidence(evidence_ledger, "EVID-EXEC-01")
    s1_title = f"{format_display_label(target_sheet['name'])}: Operational Performance Executive Briefing" if len(included_sheets) == 1 else "Consolidated Operational Performance & Executive Review"
    if len(s1_title) > 78:
        s1_title = "Operational Performance & Department Executive Briefing"

    s1_sub = f"Synthesis across {len(included_sheets)} dataset source(s) · {reporting_period_summary}"
    if len(s1_sub) > 118:
        s1_sub = f"Synthesis across {len(included_sheets)} dataset(s) ({reporting_period_summary[:50]})"

    s1_narrative = (
        f"[Operational Finding] Performance across evaluated units reveals an operational dispersion of **{dispersion_metric_str}**{cat_summary} "
        f"against an operational benchmark of **{mean_val_str}**. "
        f"[Business Implication & Action] Trailing units demonstrate localized attendance and scheduling lag requiring proactive business partner review to stabilize core coverage."
    )
    s1_bullets = [
        f"[Observation & Comparator] Entity performance establishes an operational dispersion of {dispersion_metric_str} against {mean_val_str} benchmark ({reporting_period_summary}).",
        f"[Business Implication] Department-level variance reflects localized scheduling and leave concentration risks rather than uniform system shortfall.",
        f"[Proposed Action] Deploy targeted scheduling reviews and operational support to trailing units to stabilize workforce performance."
    ]
    s1_script = (
        f"Welcome executive leadership. Today we review operational performance across {file_label} for {reporting_period_summary}. "
        f"Baseline benchmark is {mean_val_str}, with unit dispersion of {dispersion_metric_str} across {total_eval_records:,} verified records."
    )
    s1_notes = format_briefing(
        ev1,
        s1_title,
        f"Defines operational baseline at {mean_val_str} and unit dispersion of {dispersion_metric_str} across {total_eval_records:,} records.",
        "Decision-first scorecards present operational benchmark, dispersion ratio, and evaluated population without row-count noise.",
        s1_script
    )
    return {
        "id": f"slide_{uuid.uuid4().hex[:8]}",
        "stable_slide_id": "slide_exec_overview",
        "order": current_slide_order,
        "layout": "title_hero",
        "category": "EXECUTIVE SUMMARY",
        "title": s1_title,
        "subtitle": s1_sub,
        "narrative": s1_narrative,
        "bullets": s1_bullets,
        "metrics": [
            {"label": "Performance Benchmark", "value": mean_val_str, "subtext": "Central tendency"},
            {"label": "Entity Dispersion", "value": dispersion_metric_str, "subtext": "Leader vs laggard spread"},
            {"label": "Evaluated Population", "value": f"{total_eval_records:,}", "subtext": f"{completeness_pct}% verified coverage"}
        ],
        "chart": None,
        "table": None,
        "speaker_notes": s1_notes,
        "narration_script": s1_script,
        "reading_order": ["category", "title", "subtitle", "narrative", "metrics", "bullets", "footer"],
        "timing_metadata": calculate_timing(s1_script),
        "evidence_id": "EVID-EXEC-01",
        "evidence_item": ev1,
        "evidence_sources": [s["original_name"] for s in included_sheets],
        "is_partial_year": is_partial_year
    }


def build_baseline_scope_slide(
    included_sheets: list[dict[str, Any]],
    source_summary: str,
    total_eval_records: int,
    completeness_pct: float,
    mean_val_str: str,
    dispersion_metric_str: str,
    reporting_period_summary: str,
    evidence_ledger: list[dict[str, Any]],
    is_partial_year: bool,
    current_slide_order: int
) -> dict[str, Any]:
    ev2 = find_evidence(evidence_ledger, "EVID-KPI-01")
    s2_title = f"Analysis Scope & Baseline: {mean_val_str} Mean Across {total_eval_records:,} Records"
    if len(s2_title) > 78:
        s2_title = f"Scope & Baseline: {total_eval_records:,} Records Reviewed ({mean_val_str} Mean)"
    s2_sub = "Explicit population boundaries, chronological coverage, and empirical benchmarks"
    s2_narrative = (
        f"[Evidence] {total_eval_records:,} records were reviewed in this analysis across {reporting_period_summary} "
        f"with **{completeness_pct}% data completeness**. "
        f"[Derived Metric] Operational baseline mean established at **{mean_val_str}**, "
        f"revealing an entity dispersion ratio of **{dispersion_metric_str}**."
    )
    s2_bullets = [
        f"[Evidence] Total Audited Records: {total_eval_records:,} verified entries in {source_summary}.",
        f"[Derived Metric] Network Baseline Mean: {mean_val_str} ({reporting_period_summary}).",
        f"[Derived Metric] Entity Performance Dispersion: {dispersion_metric_str} between top and lower quartiles."
    ]
    s2_script = (
        f"Slide two explicitly surfaces our analysis scope and empirical baseline. We reviewed {total_eval_records:,} records "
        f"across {reporting_period_summary}, establishing an arithmetic mean throughput of {mean_val_str}."
    )
    s2_notes = format_briefing(
        ev2,
        s2_title,
        f"Establishes explicit dataset boundaries across {total_eval_records:,} records with central output tracking at {mean_val_str}.",
        "Scope and baseline scorecards display population totals, date spans, mean throughput, and dispersion ratio.",
        s2_script
    )
    return {
        "id": f"slide_{uuid.uuid4().hex[:8]}",
        "stable_slide_id": "slide_macro_outcomes",
        "order": current_slide_order,
        "layout": "kpi_summary",
        "category": "ANALYSIS SCOPE & BASELINE",
        "title": s2_title,
        "subtitle": s2_sub,
        "narrative": s2_narrative,
        "bullets": s2_bullets,
        "metrics": [
            {"label": "Records Analysed", "value": f"{total_eval_records:,}", "subtext": "Audited population"},
            {"label": "Network Baseline Mean", "value": mean_val_str, "subtext": "Arithmetic mean benchmark"},
            {"label": "Observation Window", "value": reporting_period_summary[:20], "subtext": "Chronological span"},
            {"label": "Store Dispersion", "value": dispersion_metric_str, "subtext": "Leader vs laggard ratio"}
        ],
        "chart": None,
        "table": None,
        "speaker_notes": s2_notes,
        "narration_script": s2_script,
        "reading_order": ["category", "title", "subtitle", "narrative", "metrics", "bullets", "footer"],
        "timing_metadata": calculate_timing(s2_script),
        "evidence_id": "EVID-KPI-01",
        "evidence_item": ev2,
        "evidence_sources": [s["original_name"] for s in included_sheets],
        "is_partial_year": is_partial_year
    }
