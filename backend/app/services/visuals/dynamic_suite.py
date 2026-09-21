"""Schema-driven dynamic visual suite builder (bar, donut, and line charts)."""

import json
from typing import Any
import pandas as pd

from ..executive_story import detect_sheet_domain
from ..analysis_planner import evaluate_chart_prerequisites
from ..display_formatters import format_display_label
from .visual_common import clean_file_label


def build_dynamic_suite(sheet_meta_map: dict, sheet_data_map: dict) -> list[dict]:
    """Builds schema-driven dynamic bar, donut, and line charts."""
    visualizations = []
    for sid, meta in sheet_meta_map.items():
        records = sheet_data_map.get(sid, [])
        if not records:
            continue
        cols = json.loads(meta['columns_json'] or '[]')
        if any(str(c).startswith('Person_') for c in cols):
            continue

        domain_name, domain_type = detect_sheet_domain(cols)
        is_retail = "retail" in domain_name.lower() or "commercial" in domain_name.lower()
        is_wf = "workforce" in domain_name.lower() or "hr" in domain_name.lower()
        ops_category = "Commercial & Sales Operations" if is_retail else ("Workforce Operations" if is_wf else "Operations & Performance")
        trends_category = "Sales & Revenue Trends" if is_retail else ("Workforce Trends" if is_wf else "Longitudinal Trends")

        prereq = evaluate_chart_prerequisites(records, cols, meta['name'], meta['original_name'])
        supported_charts = list(prereq.get('supported_charts', []))

        def chart_priority(p):
            m_col = str(p.get('metric_col', '')).lower()
            c_type = p.get('chart_type', '')
            is_pri = any(k in m_col for k in ('sales', 'revenue', 'performance', 'rating'))
            if is_pri and c_type == 'line':
                return 1
            if is_pri and c_type == 'bar':
                return 2
            if 'compare' in p.get('plan_id', ''):
                return 3
            if c_type == 'donut':
                return 4
            if c_type == 'line':
                return 5
            return 6

        supported_charts.sort(key=chart_priority)

        for p in supported_charts:
            chart_type = p['chart_type']
            unit = p.get('unit', 'units')
            pop = p.get('population', f"{len(records)} records")
            cov = p.get('coverage_pct', 100.0)
            miss = p.get('missing_records', 0)
            srcs = [clean_file_label(meta['original_name'])]

            if chart_type == 'bar':
                cat_disp = format_display_label(p['category_col']).lower()
                cat_noun = f"{cat_disp} entities" if any(k in cat_disp for k in ('store', 'group', 'unit', 'team', 'dept', 'department')) else f"{cat_disp} segments"
                if len(p['bars']) >= 2:
                    v0 = p['bars'][0]['value']
                    v1 = p['bars'][1]['value']
                    v0_str = f"${v0:,.2f}" if unit == '$' else (f"{v0:,.2f} {unit}" if isinstance(v0, float) else f"{v0} {unit}")
                    v1_str = f"${v1:,.2f}" if unit == '$' else (f"{v1:,.2f} {unit}" if isinstance(v1, float) else f"{v1} {unit}")
                    insight = f"**Distribution Analysis**: Across {len(p['bars'])} {cat_noun}, **{p['bars'][0]['label']}** leads with **{v0_str}**, followed by {p['bars'][1]['label']} ({v1_str})."
                else:
                    insight = ""
                visualizations.append({
                    'id': f"dynamic_{p['plan_id']}_{sid}",
                    'title': p['title'],
                    'subtitle': p['subtitle'],
                    'category': ops_category,
                    'chart_type': 'bar',
                    'sheet_ids': [sid],
                    'sheet_badge': clean_file_label(meta['original_name']),
                    'measured_metric': p['measured_metric'],
                    'unit': unit,
                    'reporting_period': 'Current Upload Window',
                    'population': pop,
                    'active_filters': 'Complete Sheet Cohort',
                    'source_sheets': srcs,
                    'coverage_pct': cov,
                    'missing_records': miss,
                    'bars': p['bars'],
                    'category_col': p['category_col'],
                    'metric_col': p['metric_col'],
                    'overall_mean': p.get('overall_mean'),
                    'overall_total': p.get('overall_total'),
                    'total_categories': p.get('total_categories', len(p['bars'])),
                    'ranking_basis': p.get('ranking_basis', 'Ranked High to Low'),
                    'aggregation_rule': p.get('aggregation_rule', 'Arithmetic Mean'),
                    'spread_ratio': p.get('spread_ratio', 1.0),
                    'is_high_cardinality': p.get('is_high_cardinality', len(p['bars']) > 10),
                    'stats_pills': [
                        {'label': 'Evaluated Records', 'value': f"{len(records)}"},
                        {'label': 'Categories', 'value': f"{len(p['bars'])}"},
                        {'label': 'Data Coverage', 'value': f"{cov}%"}
                    ],
                    'ai_insight': insight
                })
            elif chart_type == 'donut':
                visualizations.append({
                    'id': f"dynamic_{p['plan_id']}_{sid}",
                    'title': p['title'],
                    'subtitle': p['subtitle'],
                    'category': ops_category,
                    'chart_type': 'donut',
                    'sheet_ids': [sid],
                    'sheet_badge': clean_file_label(meta['original_name']),
                    'measured_metric': p['measured_metric'],
                    'unit': unit,
                    'reporting_period': 'Current Upload Window',
                    'population': pop,
                    'active_filters': 'All Categories',
                    'source_sheets': srcs,
                    'coverage_pct': cov,
                    'missing_records': miss,
                    'donut_data': {
                        'category_col': p['category_col'],
                        'total': p['total_population'],
                        'slices': p['slices']
                    },
                    'stats_pills': [
                        {'label': 'Total Entities', 'value': f"{p['total_population']}"},
                        {'label': 'Top Segment', 'value': f"{p['slices'][0]['label']} ({p['slices'][0]['pct']}%)"}
                    ],
                    'ai_insight': f"**Composition**: **{p['slices'][0]['label']}** constitutes the largest proportion at **{p['slices'][0]['pct']}%** ({p['slices'][0]['count']} entries)."
                })
            elif chart_type == 'line':
                pts = p.get('points', [])
                if pts and is_retail and unit == '$':
                    max_pt = max(pts, key=lambda pt: pt.get('value', 0))
                    min_pt = min(pts, key=lambda pt: pt.get('value', 0))
                    avg_val = sum(pt.get('value', 0) for pt in pts) / len(pts)
                    stats_pills = [
                        {'label': 'Observation Periods', 'value': f"{len(pts)} dates"},
                        {'label': 'Peak Volume', 'value': f"${max_pt['value'] / 1_000_000:.2f}M ({max_pt['period']})"},
                        {'label': 'Network Mean', 'value': f"${avg_val / 1_000_000:.2f}M/wk"}
                    ]
                    line_insight = (
                        f"**Revenue Trajectory**: Total weekly sales across all locations peaked on **{max_pt['period']}** at "
                        f"**${max_pt['value'] / 1_000_000:.2f}M**, with lowest volume on **{min_pt['period']}** (${min_pt['value'] / 1_000_000:.2f}M). "
                        f"Overall network volume stabilized around an average of **${avg_val / 1_000_000:.2f}M** per week across {len(pts)} observation dates."
                    )
                else:
                    stats_pills = [
                        {'label': 'Observations', 'value': f"{len(pts)} dates"},
                        {'label': 'Metric', 'value': p['metric_col']}
                    ]
                    line_insight = f"**Sequential Trend**: Profiled {len(pts)} chronological observations from {pts[0]['period']} to {pts[-1]['period']}." if pts else ""

                visualizations.append({
                    'id': f"dynamic_{p['plan_id']}_{sid}",
                    'title': p['title'],
                    'subtitle': p['subtitle'],
                    'category': trends_category,
                    'chart_type': 'line',
                    'sheet_ids': [sid],
                    'sheet_badge': clean_file_label(meta['original_name']),
                    'measured_metric': p['measured_metric'],
                    'unit': unit,
                    'reporting_period': 'Recorded Date Window',
                    'population': pop,
                    'active_filters': 'Sequential Observations',
                    'source_sheets': srcs,
                    'coverage_pct': cov,
                    'missing_records': miss,
                    'line_data': {
                        'date_col': p['date_col'],
                        'metric_col': p['metric_col'],
                        'points': p['points'],
                        'total_periods': p.get('total_periods', len(p['points'])),
                        'period_min_date': p.get('period_min_date'),
                        'period_max_date': p.get('period_max_date'),
                        'available_years': p.get('available_years', [])
                    },
                    'stats_pills': stats_pills,
                    'ai_insight': line_insight
                })

    return visualizations
