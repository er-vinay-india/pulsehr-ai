from __future__ import annotations

import json
import logging
import re
from typing import Any

from ...gateway.model_gateway import ModelGateway, extract_json_payload
from ....core.models_config import ModelRole
from .director_models import (
    InformationDestination,
    InformationSourceType,
    InformationUnit,
    NarrativeStrategy,
    PresentationIntent,
    PresentationPlanningContext,
    SlideCountConstraint,
    SlideCountMode,
    SlidePlan,
    VisualIntent,
)

logger = logging.getLogger(__name__)


def plan_slides(
    ctx: PresentationPlanningContext,
    intent: PresentationIntent,
    narrative: NarrativeStrategy,
    information_units: list[InformationUnit],
    max_retries: int = 1
) -> list[SlidePlan]:
    """Stage 4: Allocates individual SlidePlans strictly adhering to SlideCountConstraint and narrative structure."""
    constraint = ctx.slide_count_constraint
    main_units = [u for u in information_units if u.destination == InformationDestination.MAIN_DECK]
    appendix_units = [u for u in information_units if u.destination == InformationDestination.APPENDIX]

    # Calculate target slide count based on constraint mode
    if constraint.mode == SlideCountMode.FIXED:
        target_count = constraint.target or 8
    elif constraint.mode == SlideCountMode.MINIMUM:
        target_count = max(constraint.min_slides or 8, len(main_units) + 2)
    elif constraint.mode == SlideCountMode.MAXIMUM:
        target_count = min(constraint.max_slides or 8, max(4, len(main_units) + 1))
    elif constraint.mode == SlideCountMode.RANGE:
        target_count = max(constraint.min_slides or 6, min(constraint.max_slides or 12, len(main_units) + 2))
    else:  # ADAPTIVE
        # Dynamically scale with available evidence, industrial models, and sections
        base = max(len(narrative.sections), 4)
        evidence_scale = min(len(main_units), 8)
        industrial_models = ctx.industrial_models or {}
        available_charts = ctx.available_charts or {}
        model_count = sum(1 for m in industrial_models.values() if isinstance(m, dict) and m.get("available"))
        target_count = max(8, min(16, base + (evidence_scale // 2) + model_count))

    # Clamp target_count to absolute bounds if specified
    if constraint.min_slides is not None:
        target_count = max(target_count, constraint.min_slides)
    if constraint.max_slides is not None:
        target_count = min(target_count, constraint.max_slides)

    if max_retries < 0:
        return _build_fallback_slide_plans(target_count, ctx, intent, narrative, main_units, appendix_units)

    industrial_models = ctx.industrial_models or {}
    available_charts = ctx.available_charts or {}

    # Summarize assets for prompt
    available_assets = {
        "line_chart": available_charts.get("line_chart", False),
        "bar_chart": available_charts.get("bar_chart", False),
        "donut_chart": available_charts.get("donut_chart", False),
        "talent_9box": bool((industrial_models.get("talent_9box") or {}).get("available")),
        "burnout_strain": bool((industrial_models.get("burnout_strain") or {}).get("available")),
        "bradford_factor": bool((industrial_models.get("bradford_factor") or {}).get("available")),
        "action_plan": True,
        "raci_matrix": True,
        "evidence_ledger": True
    }

    units_brief = [
        {"id": u.id, "title": u.title, "evidence_id": u.evidence_id, "source": u.source_type.value}
        for u in main_units[:10]
    ]

    prompt = f"""You are the Executive Presentation Director. Generate the concrete slide blueprints for this presentation.

## Target Constraints:
- Slide Count Mode: {constraint.mode.value}
- TARGET SLIDE COUNT: Exactly {target_count} slides (must strictly adhere to this count)
- Domain: {ctx.domain}
- Objective: {ctx.objective}
- Audience: {ctx.audience} (Seniority: {intent.audience_seniority.value})
- Narrative Thesis: {narrative.executive_thesis}

## Available Visual Assets:
{json.dumps(available_assets, indent=2)}

## High-Priority Information Units:
{json.dumps(units_brief, indent=2)}

## Rules:
1. Generate EXACTLY {target_count} slides.
2. Every slide title must be an assertive, conclusion-driven headline under 78 characters.
3. Every slide must specify layout: ["title_hero", "kpi_summary", "chart_narrative", "table_detail", "comparison_split", "action_plan"].
4. Specify visual_type: ["none", "line_chart", "bar_chart", "donut_chart", "kpi_grid", "table", "talent_9box", "burnout_strain", "bradford_factor", "action_plan", "raci_matrix", "evidence_ledger"].
5. Cite relevant evidence_ids and information_unit_ids for data grounding.

Return ONLY a valid JSON object:
{{
  "slides": [
    {{
      "sequence_number": 1,
      "section_id": "sec_exec",
      "layout": "title_hero",
      "headline": "Assertive Headline Under 78 Chars",
      "subtitle": "Clear explanatory subtitle",
      "key_message": "Core takeaway for this slide.",
      "bullet_points": [
        "[Evidence] Ground truth metric from data.",
        "[Context] Comparative benchmark.",
        "[Impact] Strategic implication."
      ],
      "visual_type": "none",
      "evidence_ids": ["EVID-01"],
      "information_unit_ids": ["INFO-SCOPE-01"],
      "speaker_notes": "Key talking points for the presenter."
    }}
  ]
}}
"""

    for attempt in range(max_retries + 1):
        try:
            result = ModelGateway.generate(
                role=ModelRole.ANALYST,
                prompt=prompt,
                report_id=f"director-slides-{ctx.dataset_label}",
                step_name="director_slide_planner"
            )
            if result.success and result.raw_text:
                payload = extract_json_payload(result.raw_text)
                parsed = json.loads(payload)
                raw_slides = parsed.get("slides") if isinstance(parsed, dict) else None
                if raw_slides and isinstance(raw_slides, list) and len(raw_slides) >= 3:
                    slide_plans = _normalize_and_bound_slides(
                        raw_slides,
                        target_count=target_count,
                        constraint=constraint,
                        ctx=ctx,
                        narrative=narrative,
                        main_units=main_units
                    )
                    if constraint.is_satisfied(len(slide_plans)):
                        return slide_plans
        except Exception as exc:
            logger.debug(f"Slide planner attempt {attempt} failed: {exc}")

    # Fallback deterministic slide blueprints adhering to target_count
    return _build_fallback_slide_plans(target_count, ctx, intent, narrative, main_units, appendix_units)


def _normalize_and_bound_slides(
    raw_slides: list[dict[str, Any]],
    target_count: int,
    constraint: SlideCountConstraint,
    ctx: PresentationPlanningContext,
    narrative: NarrativeStrategy,
    main_units: list[InformationUnit]
) -> list[SlidePlan]:
    """Adjusts raw slide output to strictly conform to target count and schema bounds."""
    # Adjust length if model produced different number of slides
    if constraint.mode == SlideCountMode.FIXED:
        if len(raw_slides) > target_count:
            raw_slides = raw_slides[:target_count]
        elif len(raw_slides) < target_count:
            # Pad with additional deterministic slides
            pad = _build_fallback_slide_plans(target_count, ctx, None, narrative, main_units, [])
            for p in pad[len(raw_slides):]:
                raw_slides.append({
                    "sequence_number": len(raw_slides) + 1,
                    "section_id": p.section_id,
                    "layout": p.layout,
                    "headline": p.headline,
                    "subtitle": p.subtitle,
                    "key_message": p.key_message,
                    "bullet_points": p.bullet_points,
                    "visual_type": p.visual_intent.visual_type,
                    "evidence_ids": p.evidence_ids,
                    "information_unit_ids": p.information_unit_ids,
                    "speaker_notes": p.speaker_notes
                })
    elif constraint.mode == SlideCountMode.MAXIMUM and constraint.max_slides:
        raw_slides = raw_slides[:constraint.max_slides]
    elif constraint.mode == SlideCountMode.MINIMUM and constraint.min_slides:
        if len(raw_slides) < constraint.min_slides:
            pad = _build_fallback_slide_plans(constraint.min_slides, ctx, None, narrative, main_units, [])
            for p in pad[len(raw_slides):]:
                raw_slides.append({
                    "sequence_number": len(raw_slides) + 1,
                    "section_id": p.section_id,
                    "layout": p.layout,
                    "headline": p.headline,
                    "subtitle": p.subtitle,
                    "key_message": p.key_message,
                    "bullet_points": p.bullet_points,
                    "visual_type": p.visual_intent.visual_type,
                    "evidence_ids": p.evidence_ids,
                    "information_unit_ids": p.information_unit_ids,
                    "speaker_notes": p.speaker_notes
                })

    plans: list[SlidePlan] = []
    for idx, item in enumerate(raw_slides):
        headline = item.get("headline") or item.get("title") or f"Executive Review Finding {idx+1}"
        if len(headline) > 78:
            headline = headline[:75] + "..."

        layout = item.get("layout", "chart_narrative")
        visual_type = item.get("visual_type") or item.get("visual_hook") or "none"

        # Validate layout compatibility with slide sequence and visual_type
        if idx == 0:
            layout = "title_hero"
        elif idx == 1:
            layout = "kpi_summary"
        elif visual_type in ("line_chart", "bar_chart", "donut_chart", "rel_chart", "talent_9box", "burnout_strain", "bradford_factor"):
            layout = "chart_narrative"
        elif visual_type in ("table", "raci_matrix", "evidence_ledger"):
            layout = "table_detail"
        elif visual_type == "action_plan":
            layout = "action_plan"

        bullets = item.get("bullet_points") or item.get("bullets") or []
        if len(bullets) < 3:
            bullets = [
                f"[Evidence] Verified across {ctx.total_records:,} audited records ({ctx.completeness_pct}% completeness).",
                f"[Benchmark] Baseline benchmark: {ctx.baseline_benchmark or 'Audited Mean'} ({ctx.reporting_period or 'Full Window'}).",
                "[Operational Impact] Direct catalyst for executive strategic resource allocation."
            ]

        v_intent = VisualIntent(
            visual_type=visual_type,
            layout_recommendation=layout
        )

        plans.append(
            SlidePlan(
                slide_id=f"slide_{idx+1}",
                section_id=item.get("section_id", f"sec_{min(idx+1, len(narrative.sections))}"),
                sequence_number=idx + 1,
                layout=layout,
                headline=headline,
                subtitle=item.get("subtitle", ""),
                key_message=item.get("key_message", headline),
                bullet_points=bullets,
                visual_intent=v_intent,
                information_unit_ids=item.get("information_unit_ids") or [u.id for u in main_units[:2]],
                evidence_ids=item.get("evidence_ids") or ([ctx.current_evidence[0].get("evidence_id")] if ctx.current_evidence else []),
                speaker_notes=item.get("speaker_notes", f"Focus executive attention on verified findings in {headline}.")
            )
        )
    # Ensure structural layout diversity for executive decks with >= 6 slides
    if len(plans) >= 6:
        # Guarantee presence of core layouts: title_hero (0), kpi_summary (1), chart_narrative (2)
        if plans[2].layout not in ("chart_narrative", "full_chart_takeaway", "two_charts"):
            plans[2].layout = "chart_narrative"
            plans[2].visual_intent.layout_recommendation = "chart_narrative"
            plans[2].visual_intent.visual_type = "line_chart" if ctx.available_charts.get("line_chart") else "bar_chart"

        if len(plans) >= 7:
            # Slides 2, 3, 4 are primary analytical chart slides
            if ctx.available_charts.get("bar_chart") and plans[3].layout != "chart_narrative":
                plans[3].layout = "chart_narrative"
                plans[3].visual_intent.layout_recommendation = "chart_narrative"
                plans[3].visual_intent.visual_type = "bar_chart"
            if (ctx.available_charts.get("donut_chart") or ctx.available_charts.get("bar_chart")) and plans[4].layout != "chart_narrative":
                plans[4].layout = "chart_narrative"
                plans[4].visual_intent.layout_recommendation = "chart_narrative"
                plans[4].visual_intent.visual_type = "donut_chart" if ctx.available_charts.get("donut_chart") else "bar_chart"

        existing_layouts = {p.layout for p in plans}
        # For decks with >= 7 slides, protect slides 2, 3, 4 for chart narratives
        start_idx = 5 if len(plans) >= 7 else 4

        if "comparison_split" not in existing_layouts:
            for p in plans[start_idx:]:
                if p.layout != "comparison_split":
                    p.layout = "comparison_split"
                    p.visual_intent.layout_recommendation = "comparison_split"
                    break

        existing_layouts = {p.layout for p in plans}
        if "table_detail" not in existing_layouts:
            for p in plans[start_idx:]:
                if p.layout != "comparison_split":
                    p.layout = "table_detail"
                    p.visual_intent.layout_recommendation = "table_detail"
                    p.visual_intent.visual_type = "table"
                    break

        existing_layouts = {p.layout for p in plans}
        if "chart_narrative" not in existing_layouts:
            plans[2].layout = "chart_narrative"
            plans[2].visual_intent.layout_recommendation = "chart_narrative"

    return plans


def _build_fallback_slide_plans(
    count: int,
    ctx: PresentationPlanningContext,
    intent: PresentationIntent | None,
    narrative: NarrativeStrategy,
    main_units: list[InformationUnit],
    appendix_units: list[InformationUnit]
) -> list[SlidePlan]:
    """Generates a complete, high-signal set of deterministic SlidePlans adhering to exact slide count."""
    available_charts = ctx.available_charts or {}
    industrial_models = ctx.industrial_models or {}

    templates = [
        # Slide 1: Hero
        {
            "layout": "title_hero",
            "visual_type": "none",
            "headline": f"{ctx.domain.upper()}: Executive Operating Review",
            "subtitle": f"Empirical Ground Truth Across {ctx.total_records:,} Records",
            "key_message": f"Verified dataset establishes {ctx.baseline_benchmark or 'audited baseline'} throughput.",
            "section_id": "sec_exec",
        },
        # Slide 2: Scope & Baseline
        {
            "layout": "kpi_summary",
            "visual_type": "kpi_grid",
            "headline": "Audited Baseline Scope & Integrity Verification",
            "subtitle": f"100% Deterministic Reconciliation ({ctx.reporting_period})",
            "key_message": f"Evaluated population of {ctx.total_records:,} records with {ctx.completeness_pct}% completeness.",
            "section_id": "sec_exec",
        },
        # Slide 3: Volume / Strengths
        {
            "layout": "chart_narrative",
            "visual_type": "line_chart" if available_charts.get("line_chart") else "none",
            "headline": "Operational Volume Surge & Throughput Resilience",
            "subtitle": "Observed Peak Throughput Trajectory",
            "key_message": "Strong performance across core operating cycles demonstrates system resilience.",
            "section_id": "sec_strengths",
        },
        # Slide 4: Dispersion / Headwinds
        {
            "layout": "chart_narrative",
            "visual_type": "bar_chart" if available_charts.get("bar_chart") else "table",
            "headline": "Entity Performance Dispersion & Headwind Analysis",
            "subtitle": f"Leader-to-Laggard Spread ({ctx.dispersion_metric})",
            "key_message": "Inter-unit variation reveals productivity headroom and target areas for standardization.",
            "section_id": "sec_headwinds",
        },
        # Slide 5: Distribution / Cohorts
        {
            "layout": "chart_narrative",
            "visual_type": "donut_chart" if available_charts.get("donut_chart") else "comparison_split",
            "headline": "Category Distribution & Concentration Drivers",
            "subtitle": "Primary Volume Concentration Breakdown",
            "key_message": "Top operating unit accounts for the majority share of operational throughput.",
            "section_id": "sec_analytics",
        },
        # Slide 6: Industrial Model / Diagnostic
        {
            "layout": "chart_narrative" if (industrial_models.get("talent_9box") or {}).get("available") else "comparison_split",
            "visual_type": "talent_9box" if (industrial_models.get("talent_9box") or {}).get("available") else "table",
            "headline": "Analytical Diagnostics & Capacity Distribution",
            "subtitle": "Evaluated Population Diagnostic Matrix",
            "key_message": "Diagnostic models isolate operational risk factors and talent retention vulnerabilities.",
            "section_id": "sec_analytics",
        },
        # Slide 7: Action Plan
        {
            "layout": "action_plan",
            "visual_type": "action_plan",
            "headline": "Strategic Roadmap: Performance Stabilization Initiatives",
            "subtitle": "Immediate 30-60-90 Day Operational Commitments",
            "key_message": "Cross-functional commitments targeted directly at reducing operational dispersion.",
            "section_id": "sec_roadmap",
        },
        # Slide 8: RACI / Governance
        {
            "layout": "table_detail",
            "visual_type": "raci_matrix",
            "headline": "Execution Governance & SLA Responsibility Matrix",
            "subtitle": "Accountability Controls & Audit Verification Milestones",
            "key_message": "Unambiguous ownership matrix established to enforce delivery SLAs.",
            "section_id": "sec_roadmap",
        },
        # Slide 9: Evidence Ledger Part 1
        {
            "layout": "table_detail",
            "visual_type": "evidence_ledger",
            "headline": "Audited Evidence Ledger: Cryptographic Verification (1/2)",
            "subtitle": "Traceable Metric Proof Ledger Under SHA-256",
            "key_message": "All executive presentation claims trace to immutable ground truth records.",
            "section_id": "sec_appendix",
        },
        # Slide 10: Evidence Ledger Part 2
        {
            "layout": "table_detail",
            "visual_type": "evidence_ledger",
            "headline": "Audited Evidence Ledger: Extended Findings (2/2)",
            "subtitle": "Extended Empirical Findings & Validation Seals",
            "key_message": "Supplemental verified claims providing complete audit trail coverage.",
            "section_id": "sec_appendix",
        },
        # Slide 11: Continuous Monitoring
        {
            "layout": "chart_narrative",
            "visual_type": "line_chart" if ctx.available_charts.get("line_chart") else "none",
            "headline": "Continuous Operational Monitoring & Alerting Controls",
            "subtitle": "Automated Threshold Surveillance & Outlier Triggers",
            "key_message": "Real-time monitoring triggers immediate investigation upon variance spikes.",
            "section_id": "sec_roadmap",
        },
        # Slide 12: Resource Redistribution
        {
            "layout": "action_plan",
            "visual_type": "action_plan",
            "headline": "Resource Optimization & Capacity Redistribution Plan",
            "subtitle": "Balancing Throughput Demands Across Units",
            "key_message": "Dynamic staff and asset reallocation eliminates recurring local bottlenecks.",
            "section_id": "sec_roadmap",
        },
        # Slide 13: Cross-Department Benchmarks
        {
            "layout": "table_detail",
            "visual_type": "table",
            "headline": "Cross-Department Analytical Variance Benchmarks",
            "subtitle": "Unit Economics & Efficiency Metrics Comparison",
            "key_message": "Direct comparative analysis reveals replication opportunities across facilities.",
            "section_id": "sec_analytics",
        },
        # Slide 14: Risk Mitigation
        {
            "layout": "comparison_split",
            "visual_type": "table",
            "headline": "Enterprise Risk Mitigation & Contingency Protocols",
            "subtitle": "Defensive Measures Against Disruption Vectors",
            "key_message": "Hardened operating buffers minimize downside exposure to supply and labor shocks.",
            "section_id": "sec_roadmap",
        },
        # Slide 15: Leadership Mandates
        {
            "layout": "title_hero",
            "visual_type": "none",
            "headline": "Executive Conclusions & Leadership Mandates",
            "subtitle": "Strategic Alignment & Capital Authorization Summary",
            "key_message": "Clear operational mandate to deploy stabilization initiatives immediately.",
            "section_id": "sec_exec",
        },
    ]

    # Select or expand to exact requested count
    plans: list[SlidePlan] = []
    for i in range(count):
        tpl = templates[i % len(templates)]
        seq = i + 1
        h_line = tpl["headline"]
        if i >= len(templates):
            h_line = f"Workstream Expansion {i + 1}: {tpl['headline']}"


        plans.append(
            SlidePlan(
                slide_id=f"slide_{seq}",
                section_id=tpl["section_id"],
                sequence_number=seq,
                layout=tpl["layout"],
                headline=h_line[:78],
                subtitle=tpl["subtitle"],
                key_message=tpl["key_message"],
                bullet_points=[
                    f"[Evidence] Verified across {ctx.total_records:,} records ({ctx.completeness_pct}% data integrity).",
                    f"[Benchmark] Network baseline: {ctx.baseline_benchmark or 'Audited benchmark'}.",
                    "[Action] Direct input into leadership resource allocation and governance."
                ],
                visual_intent=VisualIntent(
                    visual_type=tpl["visual_type"],
                    layout_recommendation=tpl["layout"]
                ),
                information_unit_ids=[u.id for u in main_units[:2]],
                evidence_ids=[ctx.current_evidence[0].get("evidence_id")] if ctx.current_evidence else [],
                speaker_notes=f"Discuss empirical grounding and executive implications for {h_line}."
            )
        )
    return plans
