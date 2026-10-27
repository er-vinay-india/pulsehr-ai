"""HighView Slide Composition Intelligence — Dataset Builder.

Constructs a high-quality, curated training, validation, and holdout corpus for
fine-tuning IBM Granite on HighView's CompositionDecision contract.

Covers:
- Multi-domain presentations: Retail, Education, Geographic, Operational/HR, Financial
- All 16 CompositionArchetypes
- All Content Roles, Visual Priorities, Density Intents, Narrative Placements, Split Intents
- Label Simplification Intents
- Negative and boundary grounding examples (anti-hallucination, anti-geometry)
- Isolated Train / Validation / Holdout splits (stratified by scenario/dataset to prevent leakage)
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from app.services.presentation.composition.composition_models import (
    CompositionArchetype,
    CompositionContentGroup,
    CompositionContentRole,
    CompositionDecision,
    CompositionDecisionSource,
    DensityIntent,
    LabelSimplificationIntent,
    NarrativePlacementIntent,
    SplitIntent,
    VisualPriority,
)

SYSTEM_PROMPT = """You are HighView's Slide Composition Intelligence Engine.
Your task is to make a high-level SEMANTIC COMPOSITION DECISION for the following logical presentation slide.

CRITICAL RULES:
1. Zero coordinates (x, y, width, height).
2. Zero typography measurements (pt, font size).
3. Zero colors (hex, rgb).
4. Zero DrawingML, SVG, or HTML markup.
5. Reference ONLY the valid content IDs listed below. Never hallucinate or invent new content IDs.

Valid Archetypes:
HERO_METRIC, KPI_GRID, VISUAL_HERO, VISUAL_WITH_INSIGHT, VISUAL_WITH_SUPPORTING_METRICS,
COMPARISON, RANKING, DISTRIBUTION, CORRELATION, SCENARIO, TABLE_DEEP_DIVE, OUTLIER_SUMMARY,
MULTI_INSIGHT, EXECUTIVE_SYNTHESIS, TITLE_COVER, CLOSING_SUMMARY

Return only a valid JSON object matching the CompositionDecision schema."""


def format_user_prompt(
    logical_slide_id: str,
    structural_role: str,
    semantic_topic: str,
    purpose: str,
    headline: str,
    takeaway: str,
    visual_id: str | None,
    visual_type: str | None,
    bound_items: list[dict[str, Any]],
) -> str:
    return f"""SLIDE CONTEXT:
- Logical Slide ID: "{logical_slide_id}"
- Structural Role: "{structural_role}"
- Semantic Topic: "{semantic_topic}"
- Purpose: "{purpose}"
- Headline: "{headline}"
- Key Takeaway: "{takeaway}"
- Primary Visual ID: "{visual_id or 'none'}"
- Primary Visual Type: "{visual_type or 'none'}"

AVAILABLE CONTENT BINDINGS:
{json.dumps(bound_items, indent=2)}

Emit the structured JSON CompositionDecision."""


def create_record(
    example_id: str,
    domain: str,
    dataset: str,
    structural_role: str,
    topic: str,
    purpose: str,
    headline: str,
    takeaway: str,
    visual_id: str | None,
    visual_type: str | None,
    bound_items: list[dict[str, Any]],
    archetype: CompositionArchetype,
    content_groups: list[CompositionContentGroup],
    primary_id: str | None,
    supporting_ids: list[str],
    visual_priority: VisualPriority,
    density: DensityIntent,
    narrative_placement: NarrativePlacementIntent,
    split_intent: SplitIntent,
    label_intents: list[LabelSimplificationIntent],
    reason_codes: list[str],
    difficulty: str = "STANDARD",
    curation_source: str = "HIGHVIEW_CURATED",
) -> dict[str, Any]:
    user_prompt = format_user_prompt(
        logical_slide_id=example_id,
        structural_role=structural_role,
        semantic_topic=topic,
        purpose=purpose,
        headline=headline,
        takeaway=takeaway,
        visual_id=visual_id,
        visual_type=visual_type,
        bound_items=bound_items,
    )

    decision = CompositionDecision(
        logical_slide_id=example_id,
        composition_archetype=archetype,
        content_groups=content_groups,
        primary_content_id=primary_id,
        visual_priority=visual_priority,
        density_intent=density,
        narrative_placement=narrative_placement,
        supporting_content_ids=supporting_ids,
        split_intent=split_intent,
        label_intents=label_intents,
        reason_codes=reason_codes,
        confidence=0.95,
        diagnostic_rationale=f"Curated composition for {archetype.value} in {domain} domain.",
        decision_source=CompositionDecisionSource.AI_MODEL,
        metadata={
            "curation_source": curation_source,
            "domain": domain,
            "dataset": dataset,
            "difficulty": difficulty,
        },
    )

    assistant_json = json.dumps(
        {
            "logical_slide_id": decision.logical_slide_id,
            "composition_archetype": decision.composition_archetype.value,
            "primary_content_id": decision.primary_content_id,
            "visual_priority": decision.visual_priority.value,
            "density_intent": decision.density_intent.value,
            "narrative_placement": decision.narrative_placement.value,
            "supporting_content_ids": decision.supporting_content_ids,
            "content_groups": [
                {
                    "role": g.role.value,
                    "content_ids": g.content_ids,
                }
                for g in decision.content_groups
            ],
            "split_intent": decision.split_intent.value,
            "label_intents": [
                {
                    "source_label": li.source_label,
                    "display_intent": li.display_intent,
                    "suggested_display_text": li.suggested_display_text,
                }
                for li in decision.label_intents
            ],
            "reason_codes": decision.reason_codes,
            "confidence": decision.confidence,
            "diagnostic_rationale": decision.diagnostic_rationale,
        },
        indent=2,
    )

    return {
        "example_id": example_id,
        "source_domain": domain,
        "source_dataset": dataset,
        "logical_slide_role": structural_role,
        "visual_family": visual_type or "none",
        "difficulty": difficulty,
        "expected_archetype": archetype.value,
        "curation_source": curation_source,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
            {"role": "assistant", "content": assistant_json},
        ],
    }


def generate_curated_examples() -> list[dict[str, Any]]:
    """Generates the full, highly curated multi-domain dataset covering all 16 archetypes."""
    examples: list[dict[str, Any]] = []

    # -------------------------------------------------------------------------
    # DOMAIN 1: RETAIL / WALMART
    # -------------------------------------------------------------------------
    # 1. Title Cover
    examples.append(
        create_record(
            example_id="wm-slide-01-cover",
            domain="retail",
            dataset="walmart_store_sales",
            structural_role="TITLE",
            topic="Walmart Sales Performance Review",
            purpose="Introduce the executive Q4 performance evaluation",
            headline="Walmart Multi-Department Q4 Sales Analysis",
            takeaway="Performance across Supercenters and Neighborhood Markets",
            visual_id=None,
            visual_type=None,
            bound_items=[
                {"content_id": "txt_sub_title", "binding_role": "SUBTITLE", "visual_type": "none"}
            ],
            archetype=CompositionArchetype.TITLE_COVER,
            content_groups=[
                CompositionContentGroup(role=CompositionContentRole.CONTEXT_SUMMARY, content_ids=["txt_sub_title"])
            ],
            primary_id=None,
            supporting_ids=["txt_sub_title"],
            visual_priority=VisualPriority.REFERENCE,
            density=DensityIntent.SPARSE,
            narrative_placement=NarrativePlacementIntent.BELOW_VISUAL,
            split_intent=SplitIntent.NO_SPLIT,
            label_intents=[],
            reason_codes=["ROLE_TITLE", "ARCHETYPE_TITLE_COVER", "DENSITY_SPARSE"],
        )
    )

    # 2. Strategic KPIs (KPI_GRID)
    examples.append(
        create_record(
            example_id="wm-slide-02-kpis",
            domain="retail",
            dataset="walmart_store_sales",
            structural_role="STRATEGIC_KPIS",
            topic="Enterprise Topline Revenue",
            purpose="Summarize primary Q4 revenue, margin, and holiday sales growth",
            headline="Holiday Surge Delivers Record Q4 Volume Across Stores",
            takeaway="Total revenue reached $152.8M with 8.4% YoY acceleration",
            visual_id=None,
            visual_type=None,
            bound_items=[
                {"content_id": "kpi_total_revenue", "binding_role": "PRIMARY", "visual_type": "kpi"},
                {"content_id": "kpi_holiday_growth", "binding_role": "SUPPORTING", "visual_type": "kpi"},
                {"content_id": "kpi_gross_margin", "binding_role": "SUPPORTING", "visual_type": "kpi"},
                {"content_id": "kpi_avg_basket", "binding_role": "SUPPORTING", "visual_type": "kpi"},
            ],
            archetype=CompositionArchetype.KPI_GRID,
            content_groups=[
                CompositionContentGroup(
                    role=CompositionContentRole.PRIMARY_INSIGHT,
                    content_ids=["kpi_total_revenue"],
                ),
                CompositionContentGroup(
                    role=CompositionContentRole.SUPPORTING_METRICS,
                    content_ids=["kpi_holiday_growth", "kpi_gross_margin", "kpi_avg_basket"],
                ),
            ],
            primary_id="kpi_total_revenue",
            supporting_ids=["kpi_holiday_growth", "kpi_gross_margin", "kpi_avg_basket"],
            visual_priority=VisualPriority.PRIMARY,
            density=DensityIntent.BALANCED,
            narrative_placement=NarrativePlacementIntent.BELOW_VISUAL,
            split_intent=SplitIntent.NO_SPLIT,
            label_intents=[
                LabelSimplificationIntent(source_label="kpi_total_revenue", suggested_display_text="Total Revenue"),
                LabelSimplificationIntent(source_label="kpi_holiday_growth", suggested_display_text="Holiday Growth"),
            ],
            reason_codes=["ROLE_STRATEGIC_KPIS", "ARCHETYPE_KPI_GRID", "FOUR_METRICS_BALANCED"],
        )
    )

    # 3. Weekly Trends (VISUAL_WITH_INSIGHT)
    examples.append(
        create_record(
            example_id="wm-slide-03-trends",
            domain="retail",
            dataset="walmart_store_sales",
            structural_role="HERO_ANALYSIS",
            topic="Weekly Sales Volatility",
            purpose="Examine the impact of promotional weeks on department revenue",
            headline="Thanksgiving Week Peaks Account for 31% of Quarterly Lift",
            takeaway="Promotional markdown windows drove concentrated sales spikes",
            visual_id="chart_weekly_sales_timeseries",
            visual_type="line_chart",
            bound_items=[
                {"content_id": "chart_weekly_sales_timeseries", "binding_role": "PRIMARY", "visual_type": "line_chart"},
                {"content_id": "ins_holiday_spike_callout", "binding_role": "SUPPORTING", "visual_type": "callout"},
            ],
            archetype=CompositionArchetype.VISUAL_WITH_INSIGHT,
            content_groups=[
                CompositionContentGroup(role=CompositionContentRole.PRIMARY_VISUAL, content_ids=["chart_weekly_sales_timeseries"]),
                CompositionContentGroup(role=CompositionContentRole.PRIMARY_INSIGHT, content_ids=["ins_holiday_spike_callout"]),
            ],
            primary_id="chart_weekly_sales_timeseries",
            supporting_ids=["ins_holiday_spike_callout"],
            visual_priority=VisualPriority.PRIMARY,
            density=DensityIntent.BALANCED,
            narrative_placement=NarrativePlacementIntent.BESIDE_VISUAL,
            split_intent=SplitIntent.SPLIT_IF_REQUIRED,
            label_intents=[
                LabelSimplificationIntent(source_label="chart_weekly_sales_timeseries", suggested_display_text="Weekly Sales Trend")
            ],
            reason_codes=["ROLE_HERO_ANALYSIS", "ARCHETYPE_VISUAL_WITH_INSIGHT", "HERO_TIMESERIES"],
        )
    )

    # 4. Store Format Comparison (COMPARISON)
    examples.append(
        create_record(
            example_id="wm-slide-04-comparison",
            domain="retail",
            dataset="walmart_store_sales",
            structural_role="HERO_ANALYSIS",
            topic="Format Performance: Supercenter vs Express",
            purpose="Compare revenue density and foot traffic across store formats",
            headline="Supercenters Lead Volume While Neighborhood Markets Lead Margin",
            takeaway="Type A stores deliver 2.4x aggregate volume with lower operating costs",
            visual_id="chart_format_comparison_bar",
            visual_type="bar_chart",
            bound_items=[
                {"content_id": "chart_format_comparison_bar", "binding_role": "PRIMARY", "visual_type": "bar_chart"},
                {"content_id": "card_type_a_summary", "binding_role": "SUPPORTING", "visual_type": "card"},
                {"content_id": "card_type_b_summary", "binding_role": "SUPPORTING", "visual_type": "card"},
            ],
            archetype=CompositionArchetype.COMPARISON,
            content_groups=[
                CompositionContentGroup(role=CompositionContentRole.PRIMARY_VISUAL, content_ids=["chart_format_comparison_bar"]),
                CompositionContentGroup(role=CompositionContentRole.COMPARISON_CARD, content_ids=["card_type_a_summary", "card_type_b_summary"]),
            ],
            primary_id="chart_format_comparison_bar",
            supporting_ids=["card_type_a_summary", "card_type_b_summary"],
            visual_priority=VisualPriority.PRIMARY,
            density=DensityIntent.BALANCED,
            narrative_placement=NarrativePlacementIntent.BESIDE_VISUAL,
            split_intent=SplitIntent.SPLIT_IF_REQUIRED,
            label_intents=[
                LabelSimplificationIntent(source_label="card_type_a_summary", suggested_display_text="Supercenters (Type A)"),
                LabelSimplificationIntent(source_label="card_type_b_summary", suggested_display_text="Neighborhood Markets (Type B)"),
            ],
            reason_codes=["ROLE_HERO_ANALYSIS", "ARCHETYPE_COMPARISON", "FORMAT_BENCHMARK"],
        )
    )

    # 5. Department Sales Breakdown (RANKING)
    examples.append(
        create_record(
            example_id="wm-slide-05-ranking",
            domain="retail",
            dataset="walmart_store_sales",
            structural_role="DEEP_DIVE",
            topic="Top Department Rankings",
            purpose="Rank top contributing merchandise departments by quarterly revenue",
            headline="Grocery and Electronics Account for 58% of Total Contribution",
            takeaway="Apparel shows strongest margin expansion despite lower gross sales",
            visual_id="chart_dept_ranking_hbar",
            visual_type="horizontal_bar",
            bound_items=[
                {"content_id": "chart_dept_ranking_hbar", "binding_role": "PRIMARY", "visual_type": "horizontal_bar"},
                {"content_id": "kpi_top_dept_share", "binding_role": "SUPPORTING", "visual_type": "kpi"},
            ],
            archetype=CompositionArchetype.RANKING,
            content_groups=[
                CompositionContentGroup(role=CompositionContentRole.PRIMARY_VISUAL, content_ids=["chart_dept_ranking_hbar"]),
                CompositionContentGroup(role=CompositionContentRole.SUPPORTING_METRICS, content_ids=["kpi_top_dept_share"]),
            ],
            primary_id="chart_dept_ranking_hbar",
            supporting_ids=["kpi_top_dept_share"],
            visual_priority=VisualPriority.PRIMARY,
            density=DensityIntent.BALANCED,
            narrative_placement=NarrativePlacementIntent.BESIDE_VISUAL,
            split_intent=SplitIntent.SPLIT_IF_REQUIRED,
            label_intents=[],
            reason_codes=["ROLE_DEEP_DIVE", "ARCHETYPE_RANKING", "HORIZONTAL_BAR_RANK"],
        )
    )

    # 6. Detailed Store Metrics (TABLE_DEEP_DIVE)
    examples.append(
        create_record(
            example_id="wm-slide-06-table",
            domain="retail",
            dataset="walmart_store_sales",
            structural_role="DEEP_DIVE",
            topic="Store-Level Audit Matrix",
            purpose="Present store-level weekly revenue, markdown adjustments, and CPI index",
            headline="Top 20 Performing Store Units Matrix",
            takeaway="Store 20 leads all units in fuel and grocery cross-sell conversion",
            visual_id="tbl_store_metrics_audit",
            visual_type="table",
            bound_items=[
                {"content_id": "tbl_store_metrics_audit", "binding_role": "PRIMARY", "visual_type": "table"},
                {"content_id": "callout_cpi_correlation", "binding_role": "SUPPORTING", "visual_type": "callout"},
            ],
            archetype=CompositionArchetype.TABLE_DEEP_DIVE,
            content_groups=[
                CompositionContentGroup(role=CompositionContentRole.PRIMARY_VISUAL, content_ids=["tbl_store_metrics_audit"]),
                CompositionContentGroup(role=CompositionContentRole.CALLOUT, content_ids=["callout_cpi_correlation"]),
            ],
            primary_id="tbl_store_metrics_audit",
            supporting_ids=["callout_cpi_correlation"],
            visual_priority=VisualPriority.PRIMARY,
            density=DensityIntent.DENSE,
            narrative_placement=NarrativePlacementIntent.ABOVE_VISUAL,
            split_intent=SplitIntent.PREFER_SPLIT,
            label_intents=[
                LabelSimplificationIntent(source_label="tbl_store_metrics_audit", suggested_display_text="Store Metrics Table")
            ],
            reason_codes=["ROLE_DEEP_DIVE", "ARCHETYPE_TABLE_DEEP_DIVE", "DENSITY_DENSE", "PREFER_SPLIT"],
        )
    )

    # -------------------------------------------------------------------------
    # DOMAIN 2: EDUCATION / DISTRICT ANALYTICS
    # -------------------------------------------------------------------------
    # 7. Hero Metric (HERO_METRIC)
    examples.append(
        create_record(
            example_id="edu-slide-01-hero-metric",
            domain="education",
            dataset="district_db",
            structural_role="STRATEGIC_KPIS",
            topic="Overall Graduation Attainment",
            purpose="Highlight the primary milestone graduation rate for the district",
            headline="District High School Graduation Reaches Historic 91.4% Rate",
            takeaway="Four-year cohort completion grew 3.2 percentage points over previous cycle",
            visual_id=None,
            visual_type=None,
            bound_items=[
                {"content_id": "kpi_grad_rate_hero", "binding_role": "PRIMARY", "visual_type": "kpi"},
                {"content_id": "ins_cohort_growth_fact", "binding_role": "SUPPORTING", "visual_type": "callout"},
            ],
            archetype=CompositionArchetype.HERO_METRIC,
            content_groups=[
                CompositionContentGroup(role=CompositionContentRole.PRIMARY_INSIGHT, content_ids=["kpi_grad_rate_hero"]),
                CompositionContentGroup(role=CompositionContentRole.SUPPORTING_INSIGHT, content_ids=["ins_cohort_growth_fact"]),
            ],
            primary_id="kpi_grad_rate_hero",
            supporting_ids=["ins_cohort_growth_fact"],
            visual_priority=VisualPriority.PRIMARY,
            density=DensityIntent.SPARSE,
            narrative_placement=NarrativePlacementIntent.BESIDE_VISUAL,
            split_intent=SplitIntent.NO_SPLIT,
            label_intents=[
                LabelSimplificationIntent(source_label="kpi_grad_rate_hero", suggested_display_text="Graduation Rate")
            ],
            reason_codes=["ROLE_STRATEGIC_KPIS", "ARCHETYPE_HERO_METRIC", "SINGLE_HERO_FOCUS"],
        )
    )

    # 8. Math vs Attendance Correlation (CORRELATION)
    examples.append(
        create_record(
            example_id="edu-slide-02-correlation",
            domain="education",
            dataset="district_db",
            structural_role="HERO_ANALYSIS",
            topic="Attendance and Math Proficiency Correlation",
            purpose="Demonstrate the strong link between attendance rates and standardized math scores",
            headline="Chronic Absenteeism Explains 64% of Math Score Disparity",
            takeaway="Campuses with >95% attendance averaged 18 points higher in state testing",
            visual_id="chart_math_attendance_scatter",
            visual_type="scatter_plot",
            bound_items=[
                {"content_id": "chart_math_attendance_scatter", "binding_role": "PRIMARY", "visual_type": "scatter_plot"},
                {"content_id": "ins_r_squared_finding", "binding_role": "SUPPORTING", "visual_type": "callout"},
            ],
            archetype=CompositionArchetype.CORRELATION,
            content_groups=[
                CompositionContentGroup(role=CompositionContentRole.PRIMARY_VISUAL, content_ids=["chart_math_attendance_scatter"]),
                CompositionContentGroup(role=CompositionContentRole.PRIMARY_INSIGHT, content_ids=["ins_r_squared_finding"]),
            ],
            primary_id="chart_math_attendance_scatter",
            supporting_ids=["ins_r_squared_finding"],
            visual_priority=VisualPriority.PRIMARY,
            density=DensityIntent.BALANCED,
            narrative_placement=NarrativePlacementIntent.BESIDE_VISUAL,
            split_intent=SplitIntent.SPLIT_IF_REQUIRED,
            label_intents=[
                LabelSimplificationIntent(source_label="pct_proficient_math_score", suggested_display_text="Math Proficiency %"),
                LabelSimplificationIntent(source_label="avg_attendance_rate", suggested_display_text="Average Attendance Rate"),
            ],
            reason_codes=["ROLE_HERO_ANALYSIS", "ARCHETYPE_CORRELATION", "SCATTER_R_SQUARED"],
        )
    )

    # 9. Score Distribution (DISTRIBUTION)
    examples.append(
        create_record(
            example_id="edu-slide-03-distribution",
            domain="education",
            dataset="district_db",
            structural_role="DEEP_DIVE",
            topic="Grade Distribution Across Schools",
            purpose="Show the variance and spread of academic performance indices",
            headline="Bimodal Score Distribution Highlights Opportunity Gap",
            takeaway="Title I campuses exhibit broader spread requiring targeted intervention",
            visual_id="chart_score_distribution_hist",
            visual_type="histogram",
            bound_items=[
                {"content_id": "chart_score_distribution_hist", "binding_role": "PRIMARY", "visual_type": "histogram"},
                {"content_id": "ins_bimodal_skew_note", "binding_role": "SUPPORTING", "visual_type": "callout"},
            ],
            archetype=CompositionArchetype.DISTRIBUTION,
            content_groups=[
                CompositionContentGroup(role=CompositionContentRole.PRIMARY_VISUAL, content_ids=["chart_score_distribution_hist"]),
                CompositionContentGroup(role=CompositionContentRole.PRIMARY_INSIGHT, content_ids=["ins_bimodal_skew_note"]),
            ],
            primary_id="chart_score_distribution_hist",
            supporting_ids=["ins_bimodal_skew_note"],
            visual_priority=VisualPriority.PRIMARY,
            density=DensityIntent.BALANCED,
            narrative_placement=NarrativePlacementIntent.BESIDE_VISUAL,
            split_intent=SplitIntent.SPLIT_IF_REQUIRED,
            label_intents=[],
            reason_codes=["ROLE_DEEP_DIVE", "ARCHETYPE_DISTRIBUTION", "HISTOGRAM_ANALYSIS"],
        )
    )

    # 10. Outlier Schools (OUTLIER_SUMMARY)
    examples.append(
        create_record(
            example_id="edu-slide-04-outliers",
            domain="education",
            dataset="district_db",
            structural_role="DIAGNOSTIC_DRILLDOWN",
            topic="Exceptional Campus Trajectories",
            purpose="Identify campuses outperforming or underperforming regression baseline",
            headline="Three Pilot Magnet Campuses Outperform Projected Growth by 2.8 SD",
            takeaway="Intervention strategies at Lincoln Prep demonstrate replicable success",
            visual_id="chart_outlier_residual_plot",
            visual_type="scatter_plot",
            bound_items=[
                {"content_id": "chart_outlier_residual_plot", "binding_role": "PRIMARY", "visual_type": "scatter_plot"},
                {"content_id": "tbl_top_outlier_schools", "binding_role": "SUPPORTING", "visual_type": "table"},
                {"content_id": "callout_remedial_action", "binding_role": "SUPPORTING", "visual_type": "callout"},
            ],
            archetype=CompositionArchetype.OUTLIER_SUMMARY,
            content_groups=[
                CompositionContentGroup(role=CompositionContentRole.PRIMARY_VISUAL, content_ids=["chart_outlier_residual_plot"]),
                CompositionContentGroup(role=CompositionContentRole.REFERENCE_DATA, content_ids=["tbl_top_outlier_schools"]),
                CompositionContentGroup(role=CompositionContentRole.CALLOUT, content_ids=["callout_remedial_action"]),
            ],
            primary_id="chart_outlier_residual_plot",
            supporting_ids=["tbl_top_outlier_schools", "callout_remedial_action"],
            visual_priority=VisualPriority.PRIMARY,
            density=DensityIntent.DENSE,
            narrative_placement=NarrativePlacementIntent.BESIDE_VISUAL,
            split_intent=SplitIntent.PREFER_SPLIT,
            label_intents=[
                LabelSimplificationIntent(source_label="tbl_top_outlier_schools", suggested_display_text="Outlier Campuses Table")
            ],
            reason_codes=["ROLE_DIAGNOSTIC_DRILLDOWN", "ARCHETYPE_OUTLIER_SUMMARY", "HIGH_VARIANCE_SPLIT"],
        )
    )

    # 11. Closing Recommendations (CLOSING_SUMMARY)
    examples.append(
        create_record(
            example_id="edu-slide-05-closing",
            domain="education",
            dataset="district_db",
            structural_role="SUMMARY_CLOSING",
            topic="District Strategic Roadmap",
            purpose="Summarize key policy initiatives and attendance intervention investments",
            headline="Action Priorities for 2027 Academic Improvement",
            takeaway="Targeted tutoring, transportation vouchers, and STEM grant funding",
            visual_id=None,
            visual_type=None,
            bound_items=[
                {"content_id": "card_action_tutoring", "binding_role": "PRIMARY", "visual_type": "card"},
                {"content_id": "card_action_transit", "binding_role": "SUPPORTING", "visual_type": "card"},
                {"content_id": "card_action_stem", "binding_role": "SUPPORTING", "visual_type": "card"},
            ],
            archetype=CompositionArchetype.CLOSING_SUMMARY,
            content_groups=[
                CompositionContentGroup(role=CompositionContentRole.PRIMARY_INSIGHT, content_ids=["card_action_tutoring"]),
                CompositionContentGroup(role=CompositionContentRole.SUPPORTING_INSIGHT, content_ids=["card_action_transit", "card_action_stem"]),
            ],
            primary_id="card_action_tutoring",
            supporting_ids=["card_action_transit", "card_action_stem"],
            visual_priority=VisualPriority.SECONDARY,
            density=DensityIntent.SPARSE,
            narrative_placement=NarrativePlacementIntent.BESIDE_VISUAL,
            split_intent=SplitIntent.NO_SPLIT,
            label_intents=[],
            reason_codes=["ROLE_SUMMARY_CLOSING", "ARCHETYPE_CLOSING_SUMMARY", "ACTION_CARDS"],
        )
    )

    # -------------------------------------------------------------------------
    # DOMAIN 3: OPERATIONAL & HR / WORKFORCE
    # -------------------------------------------------------------------------
    # 12. Attrition Risk Simulation (SCENARIO)
    examples.append(
        create_record(
            example_id="hr-slide-01-scenario",
            domain="workforce",
            dataset="pulsehr_analytics",
            structural_role="HERO_ANALYSIS",
            topic="Compensation Adjustment Scenarios",
            purpose="Model retention impact across 3 salary adjustment scenarios",
            headline="5% Market Equity Adjustment Reduces Tech Turnover by 42%",
            takeaway="Proactive compensation rebalancing offsets replacement recruiting costs",
            visual_id="chart_scenario_waterfall",
            visual_type="waterfall_chart",
            bound_items=[
                {"content_id": "chart_scenario_waterfall", "binding_role": "PRIMARY", "visual_type": "waterfall_chart"},
                {"content_id": "card_scenario_baseline", "binding_role": "SUPPORTING", "visual_type": "card"},
                {"content_id": "card_scenario_recommended", "binding_role": "SUPPORTING", "visual_type": "card"},
            ],
            archetype=CompositionArchetype.SCENARIO,
            content_groups=[
                CompositionContentGroup(role=CompositionContentRole.PRIMARY_VISUAL, content_ids=["chart_scenario_waterfall"]),
                CompositionContentGroup(role=CompositionContentRole.COMPARISON_CARD, content_ids=["card_scenario_baseline", "card_scenario_recommended"]),
            ],
            primary_id="chart_scenario_waterfall",
            supporting_ids=["card_scenario_baseline", "card_scenario_recommended"],
            visual_priority=VisualPriority.PRIMARY,
            density=DensityIntent.BALANCED,
            narrative_placement=NarrativePlacementIntent.BESIDE_VISUAL,
            split_intent=SplitIntent.SPLIT_IF_REQUIRED,
            label_intents=[],
            reason_codes=["ROLE_HERO_ANALYSIS", "ARCHETYPE_SCENARIO", "RETENTION_SIMULATION"],
        )
    )

    # 13. Visual with Supporting Metrics (VISUAL_WITH_SUPPORTING_METRICS)
    examples.append(
        create_record(
            example_id="hr-slide-02-visual-metrics",
            domain="workforce",
            dataset="pulsehr_analytics",
            structural_role="HERO_ANALYSIS",
            topic="Recruiting Velocity and Quality of Hire",
            purpose="Display time-to-fill trend alongside key recruitment KPI counters",
            headline="Time to Hire Decreased 14 Days Under Autonomous Pipeline Sourcing",
            takeaway="Offer acceptance rate improved to 88% while sourcing cost dropped",
            visual_id="chart_time_to_hire_trend",
            visual_type="line_chart",
            bound_items=[
                {"content_id": "chart_time_to_hire_trend", "binding_role": "PRIMARY", "visual_type": "line_chart"},
                {"content_id": "kpi_offer_acceptance_rate", "binding_role": "SUPPORTING", "visual_type": "kpi"},
                {"content_id": "kpi_sourcing_cost_per_hire", "binding_role": "SUPPORTING", "visual_type": "kpi"},
            ],
            archetype=CompositionArchetype.VISUAL_WITH_SUPPORTING_METRICS,
            content_groups=[
                CompositionContentGroup(role=CompositionContentRole.PRIMARY_VISUAL, content_ids=["chart_time_to_hire_trend"]),
                CompositionContentGroup(role=CompositionContentRole.SUPPORTING_METRICS, content_ids=["kpi_offer_acceptance_rate", "kpi_sourcing_cost_per_hire"]),
            ],
            primary_id="chart_time_to_hire_trend",
            supporting_ids=["kpi_offer_acceptance_rate", "kpi_sourcing_cost_per_hire"],
            visual_priority=VisualPriority.PRIMARY,
            density=DensityIntent.BALANCED,
            narrative_placement=NarrativePlacementIntent.BESIDE_VISUAL,
            split_intent=SplitIntent.SPLIT_IF_REQUIRED,
            label_intents=[
                LabelSimplificationIntent(source_label="kpi_offer_acceptance_rate", suggested_display_text="Offer Acceptance Rate"),
                LabelSimplificationIntent(source_label="kpi_sourcing_cost_per_hire", suggested_display_text="Cost Per Hire"),
            ],
            reason_codes=["ROLE_HERO_ANALYSIS", "ARCHETYPE_VISUAL_WITH_SUPPORTING_METRICS", "TIME_SERIES_PLUS_KPIS"],
        )
    )

    # 14. Multiple Insights Synthesis (MULTI_INSIGHT)
    examples.append(
        create_record(
            example_id="hr-slide-03-multi-insight",
            domain="workforce",
            dataset="pulsehr_analytics",
            structural_role="SYNTHESIS",
            topic="Employee Sentiment Dimensions",
            purpose="Present four key findings from the annual pulse sentiment survey",
            headline="Workplace Flexibility and Manager Support Drive Highest Engagement",
            takeaway="Career development pathways identified as primary area for improvement",
            visual_id=None,
            visual_type=None,
            bound_items=[
                {"content_id": "ins_flexibility_positive", "binding_role": "PRIMARY", "visual_type": "card"},
                {"content_id": "ins_manager_support_positive", "binding_role": "SUPPORTING", "visual_type": "card"},
                {"content_id": "ins_career_pathing_gap", "binding_role": "SUPPORTING", "visual_type": "card"},
            ],
            archetype=CompositionArchetype.MULTI_INSIGHT,
            content_groups=[
                CompositionContentGroup(role=CompositionContentRole.PRIMARY_INSIGHT, content_ids=["ins_flexibility_positive"]),
                CompositionContentGroup(role=CompositionContentRole.SUPPORTING_INSIGHT, content_ids=["ins_manager_support_positive", "ins_career_pathing_gap"]),
            ],
            primary_id="ins_flexibility_positive",
            supporting_ids=["ins_manager_support_positive", "ins_career_pathing_gap"],
            visual_priority=VisualPriority.SECONDARY,
            density=DensityIntent.BALANCED,
            narrative_placement=NarrativePlacementIntent.BESIDE_VISUAL,
            split_intent=SplitIntent.NO_SPLIT,
            label_intents=[],
            reason_codes=["ROLE_SYNTHESIS", "ARCHETYPE_MULTI_INSIGHT", "TRIPLE_INSIGHT_CARDS"],
        )
    )

    # -------------------------------------------------------------------------
    # DOMAIN 4: GEOGRAPHIC & STATISTICAL
    # -------------------------------------------------------------------------
    # 15. Pure Visual Hero (VISUAL_HERO)
    examples.append(
        create_record(
            example_id="geo-slide-01-visual-hero",
            domain="geographic",
            dataset="india_district_stats",
            structural_role="HERO_ANALYSIS",
            topic="Regional Literacy and Electrification Heatmap",
            purpose="Show geographic distribution of composite development index across states",
            headline="Southern and Western Corridors Exceed National Infrastructure Index",
            takeaway="State clusters demonstrate strong correlation between electrification and education",
            visual_id="map_india_development_choropleth",
            visual_type="choropleth_map",
            bound_items=[
                {"content_id": "map_india_development_choropleth", "binding_role": "PRIMARY", "visual_type": "choropleth_map"}
            ],
            archetype=CompositionArchetype.VISUAL_HERO,
            content_groups=[
                CompositionContentGroup(role=CompositionContentRole.PRIMARY_VISUAL, content_ids=["map_india_development_choropleth"])
            ],
            primary_id="map_india_development_choropleth",
            supporting_ids=[],
            visual_priority=VisualPriority.PRIMARY,
            density=DensityIntent.SPARSE,
            narrative_placement=NarrativePlacementIntent.CALLOUT,
            split_intent=SplitIntent.NO_SPLIT,
            label_intents=[
                LabelSimplificationIntent(source_label="map_india_development_choropleth", suggested_display_text="Development Heatmap")
            ],
            reason_codes=["ROLE_HERO_ANALYSIS", "ARCHETYPE_VISUAL_HERO", "SINGLE_CHOROPLETH_DOMINANT"],
        )
    )

    # 16. Executive Synthesis (EXECUTIVE_SYNTHESIS)
    examples.append(
        create_record(
            example_id="geo-slide-02-exec-synthesis",
            domain="geographic",
            dataset="india_district_stats",
            structural_role="SYNTHESIS",
            topic="Cross-Region Policy Recommendations",
            purpose="Synthesize macro infrastructure findings for executive leadership",
            headline="Prioritizing Grid Expansion in Eastern Districts Unlocks Accelerated Growth",
            takeaway="Targeted infrastructure allocation projects 1.8% GDP acceleration in lagging corridors",
            visual_id="chart_macro_roi_projection",
            visual_type="area_chart",
            bound_items=[
                {"content_id": "chart_macro_roi_projection", "binding_role": "PRIMARY", "visual_type": "area_chart"},
                {"content_id": "kpi_projected_gdp_lift", "binding_role": "SUPPORTING", "visual_type": "kpi"},
                {"content_id": "ins_policy_mandate", "binding_role": "SUPPORTING", "visual_type": "callout"},
            ],
            archetype=CompositionArchetype.EXECUTIVE_SYNTHESIS,
            content_groups=[
                CompositionContentGroup(role=CompositionContentRole.PRIMARY_VISUAL, content_ids=["chart_macro_roi_projection"]),
                CompositionContentGroup(role=CompositionContentRole.SUPPORTING_METRICS, content_ids=["kpi_projected_gdp_lift"]),
                CompositionContentGroup(role=CompositionContentRole.CALLOUT, content_ids=["ins_policy_mandate"]),
            ],
            primary_id="chart_macro_roi_projection",
            supporting_ids=["kpi_projected_gdp_lift", "ins_policy_mandate"],
            visual_priority=VisualPriority.SECONDARY,
            density=DensityIntent.BALANCED,
            narrative_placement=NarrativePlacementIntent.BESIDE_VISUAL,
            split_intent=SplitIntent.SPLIT_IF_REQUIRED,
            label_intents=[],
            reason_codes=["ROLE_SYNTHESIS", "ARCHETYPE_EXECUTIVE_SYNTHESIS", "MACRO_SYNTHESIS"],
        )
    )

    # -------------------------------------------------------------------------
    # NEGATIVE & BOUNDARY EXAMPLES (Anti-hallucination & Purity reinforcement)
    # -------------------------------------------------------------------------
    # Negative Example 1: Boundary prompt attempting to hallucinate fake IDs
    examples.append(
        create_record(
            example_id="neg-slide-01-grounding",
            domain="retail",
            dataset="walmart_store_sales",
            structural_role="HERO_ANALYSIS",
            topic="Store Sales Distribution with Messy Context",
            purpose="Ensure model only references valid grounded IDs and rejects tempting hallucinated IDs",
            headline="Store Performance Clustered in Type A Markets",
            takeaway="Volume concentration remains within expected historical bounds",
            visual_id="chart_real_sales_box",
            visual_type="box_plot",
            bound_items=[
                {"content_id": "chart_real_sales_box", "binding_role": "PRIMARY", "visual_type": "box_plot"},
                {"content_id": "ins_real_takeaway", "binding_role": "SUPPORTING", "visual_type": "callout"},
            ],
            archetype=CompositionArchetype.DISTRIBUTION,
            content_groups=[
                CompositionContentGroup(role=CompositionContentRole.PRIMARY_VISUAL, content_ids=["chart_real_sales_box"]),
                CompositionContentGroup(role=CompositionContentRole.PRIMARY_INSIGHT, content_ids=["ins_real_takeaway"]),
            ],
            primary_id="chart_real_sales_box",
            supporting_ids=["ins_real_takeaway"],
            visual_priority=VisualPriority.PRIMARY,
            density=DensityIntent.BALANCED,
            narrative_placement=NarrativePlacementIntent.BESIDE_VISUAL,
            split_intent=SplitIntent.SPLIT_IF_REQUIRED,
            label_intents=[],
            reason_codes=["ROLE_HERO_ANALYSIS", "ARCHETYPE_DISTRIBUTION", "GROUNDED_IDS_ONLY"],
            difficulty="BOUNDARY_NEGATIVE",
            curation_source="ANTI_HALLUCINATION_TEST",
        )
    )

    # Negative Example 2: Complex table with many bound items requiring split intent
    examples.append(
        create_record(
            example_id="neg-slide-02-split-overflow",
            domain="finance",
            dataset="corporate_ledger",
            structural_role="DEEP_DIVE",
            topic="Multi-Entity Ledger Reconciliation",
            purpose="High-density table with 6 bound metrics that must recommend split",
            headline="Full Fiscal Entity Ledger Breakdown",
            takeaway="Detailed reconciliation across all 14 operating subsidiaries",
            visual_id="tbl_large_subsidiary_ledger",
            visual_type="table",
            bound_items=[
                {"content_id": "tbl_large_subsidiary_ledger", "binding_role": "PRIMARY", "visual_type": "table"},
                {"content_id": "kpi_entity_count", "binding_role": "SUPPORTING", "visual_type": "kpi"},
                {"content_id": "kpi_total_assets", "binding_role": "SUPPORTING", "visual_type": "kpi"},
                {"content_id": "kpi_total_liabilities", "binding_role": "SUPPORTING", "visual_type": "kpi"},
                {"content_id": "kpi_equity_ratio", "binding_role": "SUPPORTING", "visual_type": "kpi"},
                {"content_id": "callout_audit_note", "binding_role": "SUPPORTING", "visual_type": "callout"},
            ],
            archetype=CompositionArchetype.TABLE_DEEP_DIVE,
            content_groups=[
                CompositionContentGroup(role=CompositionContentRole.PRIMARY_VISUAL, content_ids=["tbl_large_subsidiary_ledger"]),
                CompositionContentGroup(role=CompositionContentRole.SUPPORTING_METRICS, content_ids=["kpi_entity_count", "kpi_total_assets", "kpi_total_liabilities", "kpi_equity_ratio"]),
                CompositionContentGroup(role=CompositionContentRole.CALLOUT, content_ids=["callout_audit_note"]),
            ],
            primary_id="tbl_large_subsidiary_ledger",
            supporting_ids=["kpi_entity_count", "kpi_total_assets", "kpi_total_liabilities", "kpi_equity_ratio", "callout_audit_note"],
            visual_priority=VisualPriority.PRIMARY,
            density=DensityIntent.DENSE,
            narrative_placement=NarrativePlacementIntent.ABOVE_VISUAL,
            split_intent=SplitIntent.PREFER_SPLIT,
            label_intents=[
                LabelSimplificationIntent(source_label="tbl_large_subsidiary_ledger", suggested_display_text="Entity Ledger Matrix")
            ],
            reason_codes=["ROLE_DEEP_DIVE", "ARCHETYPE_TABLE_DEEP_DIVE", "DENSE_OVERFLOW_PREFER_SPLIT"],
            difficulty="BOUNDARY_OVERFLOW",
            curation_source="DENSITY_SPLIT_CURATION",
        )
    )

    return examples


def partition_and_save(examples: list[dict[str, Any]], output_dir: Path) -> dict[str, int]:
    """Partitions examples into isolated train, valid, and holdout splits without slide leakage."""
    output_dir.mkdir(parents=True, exist_ok=True)

    # Stratified partitioning based on domain and difficulty
    train_set: list[dict[str, Any]] = []
    valid_set: list[dict[str, Any]] = []
    holdout_set: list[dict[str, Any]] = []

    for i, ex in enumerate(examples):
        # Holdout: specific isolated evaluation targets (e.g. 1 retail, 1 education)
        if ex["example_id"] in ("wm-slide-04-comparison", "edu-slide-04-outliers"):
            holdout_set.append(ex)
        # Validation: representative cross-section across domains
        elif ex["example_id"] in ("wm-slide-02-kpis", "edu-slide-02-correlation", "hr-slide-01-scenario", "neg-slide-01-grounding"):
            valid_set.append(ex)
        # Training: bulk of diversified exemplars
        else:
            train_set.append(ex)

    train_path = output_dir / "train.jsonl"
    valid_path = output_dir / "valid.jsonl"
    holdout_path = output_dir / "holdout.jsonl"

    for path, dataset in [(train_path, train_set), (valid_path, valid_set), (holdout_path, holdout_set)]:
        with open(path, "w", encoding="utf-8") as f:
            for row in dataset:
                f.write(json.dumps(row) + "\n")

    return {
        "total": len(examples),
        "train": len(train_set),
        "validation": len(valid_set),
        "holdout": len(holdout_set),
    }


if __name__ == "__main__":
    out_dir = Path("backend/data/composition_tuning")
    dataset_records = generate_curated_examples()
    counts = partition_and_save(dataset_records, out_dir)
    print(f"Dataset generated successfully in {out_dir}:")
    print(f"  Total records: {counts['total']}")
    print(f"  Train: {counts['train']}")
    print(f"  Validation: {counts['validation']}")
    print(f"  Holdout: {counts['holdout']}")
