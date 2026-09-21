"""Industrial People Analytics visual suite builder (9-Box, Bradford, Burnout, Elasticity)."""

import json
from typing import Any

from .visual_common import clean_file_label


def build_industrial_suite(sheet_meta_map: dict, industrial_res: dict, all_sheet_rows: list) -> list[dict]:
    """Builds McKinsey 9-Box, Bradford Factor, Burnout Strain, and Cross-Sheet Elasticity visual cards."""
    visualizations = []

    # 1. MCKINSEY / GE 9-BOX TALENT & RISK MATRIX
    t9 = industrial_res.get('talent_9box')
    if t9 and t9.get('available'):
        perf_sid = next((sid for sid, s in sheet_meta_map.items() if any('perf' in str(c).lower() or 'rating' in str(c).lower() for c in json.loads(s['columns_json'] or '[]'))), None)
        visualizations.append({
            'id': 'industrial_talent_9box',
            'title': 'McKinsey / GE 9-Box Strategic Talent & Risk Matrix',
            'subtitle': 'Evaluates Performance Scores against Attrition Risk & Leadership Potential',
            'category': 'Industrial People Analytics',
            'chart_type': 'talent_9box',
            'sheet_ids': [perf_sid] if perf_sid else [],
            'sheet_badge': 'Industrial Model · McKinsey / GE Framework',
            'measured_metric': 'Performance vs Attrition Risk Potential',
            'unit': 'Rating / Risk Level',
            'reporting_period': 'Current Upload Window',
            'population': f"{t9['total_evaluated']} evaluated personnel",
            'active_filters': 'Complete Performance Cohort',
            'source_sheets': [clean_file_label(sheet_meta_map[perf_sid]['original_name'])] if perf_sid and perf_sid in sheet_meta_map else ['Workspace Records'],
            'coverage_pct': 100.0,
            'missing_records': 0,
            'talent_9box_data': t9,
            'stats_pills': [
                {'label': 'Evaluated Staff', 'value': f"{t9['total_evaluated']}"},
                {'label': 'Top Performers', 'value': f"{t9['high_performers_count']}"},
                {'label': 'At-Risk Stars', 'value': f"{t9['retention_vulnerable_stars']} (Flight Risk)"},
                {'label': 'Action Required', 'value': f"{t9['underperformers_count']} (PIP)"}
            ],
            'ai_insight': t9['ai_insight']
        })

    # 2. BRADFORD FACTOR ABSENTEEISM DISRUPTION INDEX
    bf = industrial_res.get('bradford_factor')
    if bf and bf.get('available'):
        abs_sid = next((sid for sid, s in sheet_meta_map.items() if any('absent' in str(c).lower() or 'leave' in str(c).lower() for c in json.loads(s['columns_json'] or '[]'))), None)
        visualizations.append({
            'id': 'industrial_bradford_factor',
            'title': 'Bradford Factor Absenteeism Disruption Index (B = S² × D)',
            'subtitle': 'Industrial HR metric measuring operational disruption from frequent short-term absence spells',
            'category': 'Industrial People Analytics',
            'chart_type': 'bradford_factor',
            'sheet_ids': [abs_sid] if abs_sid else [],
            'sheet_badge': 'Industrial Model · Bradford Disruption Index',
            'measured_metric': 'Absenteeism Disruption Score (B = S² × D)',
            'unit': 'Bradford points',
            'reporting_period': 'Current Upload Period',
            'population': f"{bf.get('total_evaluated', len(all_sheet_rows))} personnel evaluated",
            'active_filters': 'All Recorded Absences',
            'source_sheets': [clean_file_label(sheet_meta_map[abs_sid]['original_name'])] if abs_sid and abs_sid in sheet_meta_map else ['Workspace Records'],
            'coverage_pct': 100.0,
            'missing_records': 0,
            'bradford_data': bf,
            'stats_pills': [
                {'label': 'Org Avg Bradford', 'value': f"{bf['organizational_avg_bradford']} pts"},
                {'label': 'Formal Review (>200pts)', 'value': f"{bf['high_disruption_count']} staff ({bf['high_disruption_pct']}%)"},
                {'label': 'Benchmark Threshold', 'value': '< 50 pts (Normal)'}
            ],
            'ai_insight': bf['ai_insight']
        })

    # 3. WORKFORCE BURNOUT & WORKLOAD STRAIN INDEX
    bs = industrial_res.get('burnout_strain')
    if bs and bs.get('available') and bs.get('departments'):
        perf_sid = next((sid for sid, s in sheet_meta_map.items() if any('overtime' in str(c).lower() for c in json.loads(s['columns_json'] or '[]'))), None)
        visualizations.append({
            'id': 'industrial_burnout_strain',
            'title': 'Workforce Workload & Burnout Strain Diagnostic',
            'subtitle': 'Evaluates overtime intensity scaled by departmental absenteeism to flag compensatory workload strain',
            'category': 'Workforce Risk & Burnout',
            'chart_type': 'burnout_strain',
            'sheet_ids': [perf_sid] if perf_sid else [],
            'sheet_badge': 'Workforce Science · Strain Ratio',
            'measured_metric': 'Compensatory Overtime Strain Ratio',
            'unit': '% strain index',
            'reporting_period': 'Current Period',
            'population': f"{sum(d.get('headcount', 0) for d in bs.get('departments', []))} staff in {len(bs.get('departments', []))} departments",
            'active_filters': 'Departments with Recorded Hours',
            'source_sheets': [clean_file_label(s['original_name']) for s in sheet_meta_map.values()],
            'coverage_pct': 100.0,
            'missing_records': 0,
            'burnout_data': bs,
            'stats_pills': [
                {'label': 'Peak Strain Unit', 'value': f"{bs['highest_strain_department']} ({bs['highest_strain_pct']}%)"},
                {'label': 'Burnout Threshold', 'value': '> 20% Critical Strain'}
            ],
            'ai_insight': bs['ai_insight']
        })

    # 4. CROSS-SHEET PERFORMANCE-ABSENTEEISM STATISTICAL ELASTICITY
    el = industrial_res.get('elasticity')
    if el and el.get('available'):
        visualizations.append({
            'id': 'industrial_cross_sheet_elasticity',
            'title': 'Performance-Absenteeism Cross-Sheet Elasticity & Tipping Point',
            'subtitle': 'Ordinary least squares (OLS) linear regression modeling productivity loss per absent day',
            'category': 'Cross-Sheet Intelligence',
            'chart_type': 'elasticity',
            'sheet_ids': list(sheet_meta_map.keys()),
            'sheet_badge': 'Statistical Model · OLS Regression',
            'measured_metric': 'Productivity Penalty Slope (β)',
            'unit': 'pts loss / absent day',
            'reporting_period': 'Cross-Sheet Matched Period',
            'population': f"{el.get('evaluated_staff', len(all_sheet_rows))} matched employee records",
            'active_filters': 'Verified Exact-Key Joins',
            'source_sheets': [clean_file_label(s['original_name']) for s in sheet_meta_map.values()],
            'coverage_pct': 100.0,
            'missing_records': 0,
            'elasticity_data': el,
            'stats_pills': [
                {'label': 'Impact Penalty (β)', 'value': f"{el['beta_coefficient']} pts / day"},
                {'label': 'Tipping Point', 'value': f"{el['tipping_point_days']} absent days"},
                {'label': 'Model Fit R²', 'value': f"{el['r_squared']}"}
            ],
            'ai_insight': el['ai_insight']
        })

    return visualizations
