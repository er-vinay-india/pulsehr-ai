"""Autonomous AI Multi-Sheet Visual Intelligence Dashboard Engine.

Provides:
1. Industrial People Analytics Visual Intelligence Suite (for Executive Overview):
   - 9-Box Talent Performance-Potential & Risk Matrix
   - Bradford Factor Absenteeism Disruption Index (B = S^2 * D)
   - Workforce Burnout & Workload Strain Index
   - Statistical Cross-Sheet Performance Elasticity & Tipping Point Regression
   - Cross-Sheet Grouped Comparative Groupings
   - Longitudinal 712-Day Trajectory Forecasting
2. Sheet Visual Projections & Column Profiles Engine (for Data Explorer):
   - Raw column averages, ratings, overtime, and categorical distributions.
"""

import json
import math
import re
from datetime import datetime, timedelta
from typing import Any

import numpy as np
import pandas as pd

from ..core import config
from .time_series_forecast import (
    clean_float,
    detect_date_column,
    holt_damped_forecast,
    infer_measure_unit,
)
from .executive_story import clean_ai_markdown, detect_sheet_domain, is_id_or_unwanted_column, coerce_to_numeric
from .industrial_analytics import (
    calculate_bradford_factor,
    calculate_9box_matrix,
    calculate_burnout_strain_index,
    calculate_cross_sheet_elasticity,
    run_ingestion_industrial_pipeline
)


PALETTE = [
    '#10b981', '#6366f1', '#06b6d4', '#f59e0b', '#ec4899',
    '#8b5cf6', '#14b8a6', '#f97316', '#3b82f6', '#84cc16'
]


def is_name_or_text_column(col_name: str) -> bool:
    """Detects if a column is a person name, notes, comments, or free-form text."""
    c = str(col_name).lower().replace('_', '').replace(' ', '')
    if any(t in c for t in ('name', 'employeename', 'candidate', 'person', 'note', 'comment', 'description', 'text', 'email', 'url', 'address')):
        return True
    return False


def clean_file_label(filename: str) -> str:
    """Formats file names into clean badges."""
    s = str(filename)
    if s.lower().endswith('.csv'):
        s = s[:-4]
    elif s.lower().endswith('.xlsx') or s.lower().endswith('.xls'):
        s = s.rsplit('.', 1)[0]
    if len(s) > 32:
        return s[:29] + '…'
    return s


def generate_comparative_insight(cat_col: str, m1: str, m2: str, u1: str, u2: str, items: list[dict]) -> str:
    """Generates an executive AI insight interpreting a cross-sheet comparative grouped bar chart."""
    if not items:
        return f"Cross-sheet comparative analysis between **{m1}** and **{m2}** across departments."

    top_m1 = max(items, key=lambda x: x.get('val1', 0))
    top_m2 = max(items, key=lambda x: x.get('val2', 0))

    is_absent = any(k in m2.lower() for k in ('absent', 'leave', 'sick'))
    is_perf = any(k in m1.lower() for k in ('performance', 'rating', 'score'))
    is_ot = any(k in m1.lower() for k in ('overtime', 'hours'))

    if is_perf and is_absent:
        return (
            f"**Cross-Sheet Impact**: **{top_m1['label']}** benchmarks peak performance at "
            f"**{top_m1['val1']} {u1}** alongside **{top_m1['val2']} {u2}** absent. Conversely, **{top_m2['label']}** "
            f"logs the highest absence impact (**{top_m2['val2']} {u2}**), correlating with performance at "
            f"**{top_m2['val1']} {u1}**. Target leadership coaching on high-absence clusters to protect department velocity."
        )
    elif is_ot and is_absent:
        return (
            f"**Workload vs Absenteeism**: **{top_m1['label']}** carries peak overtime load at "
            f"**{top_m1['val1']} {u1}** with **{top_m1['val2']} {u2}** absent. Elevated overtime can signal compensatory "
            f"workload covering for absent teammates. Evaluate staffing balance to avert operational burnout."
        )

    return (
        f"**Cross-Sheet Synthesis**: Across {len(items)} {cat_col.lower()}s, **{top_m1['label']}** records peak "
        f"**{m1}** of **{top_m1['val1']} {u1}** (paired with {top_m1['val2']} {u2} {m2}), while **{top_m2['label']}** "
        f"shows the highest **{m2}** (**{top_m2['val2']} {u2}**). Leadership should balance operational priorities across both vectors."
    )


def extract_sheet_temporal_profile(sheet_rows: list[dict]) -> tuple[list[str], list[float], str] | None:
    """Detects if a sheet has Date + multi-person check-ins (like Kaggle attendance) and aggregates daily metrics."""
    if not sheet_rows:
        return None

    sample = sheet_rows[0]
    date_key = None
    for k in sample.keys():
        if str(k).lower().replace('_', '').replace(' ', '') in ('date', 'timestamp', 'datetime', 'day'):
            date_key = k
            break

    if not date_key:
        return None

    person_keys = [k for k in sample.keys() if k.startswith('Person_') or k.startswith('Emp_') or k.startswith('Staff_')]
    if len(person_keys) < 5:
        return None

    dates = []
    daily_values = []

    # Calculate average daily hours from timestamps e.g. "08:43-16:42"
    for r in sheet_rows:
        dt = r.get(date_key)
        if not dt:
            continue
        durations = []
        for pk in person_keys:
            val = str(r.get(pk, '')).strip()
            if val and val.lower() not in ('', 'none', 'absent', 'nan'):
                m = re.match(r'(\d{1,2}):(\d{2})\s*-\s*(\d{1,2}):(\d{2})', val)
                if m:
                    h1, m1, h2, m2 = map(int, m.groups())
                    hrs = (h2 * 60 + m2 - (h1 * 60 + m1)) / 60.0
                    if 0 < hrs < 24:
                        durations.append(hrs)
        if durations:
            dates.append(str(dt))
            daily_values.append(round(sum(durations) / len(durations), 2))

    if len(daily_values) >= 10:
        return dates, daily_values, 'hrs'

    return None


# =============================================================================
# DATA EXPLORER: RAW SHEET PROJECTIONS & COLUMN PROFILES
# Direct data extracts, column averages, sums, and value distributions
# =============================================================================
def get_sheet_raw_projections(conn, sheet_id: int) -> dict:
    """Generates direct data extracts, column statistics, and basic charts for Data Explorer."""
    sheet = conn.execute(
        'SELECT s.*, d.original_name, d.filename FROM sheets s JOIN dataset_uploads d ON d.id=s.dataset_id WHERE s.id=?',
        (sheet_id,)
    ).fetchone()
    if not sheet:
        return {'available': False, 'message': 'Sheet not found'}

    rows = conn.execute('SELECT data_json FROM sheet_rows WHERE sheet_id=? ORDER BY row_index', (sheet_id,)).fetchall()
    records = [json.loads(r['data_json']) for r in rows]
    if not records:
        return {'available': False, 'message': 'No rows available for this sheet'}

    df = pd.DataFrame(records)
    cols = json.loads(sheet['columns_json'] or '[]')

    # Compute column summary statistics
    column_stats = []
    numeric_cols = []
    categorical_cols = []

    for c in cols:
        vals = [r[c] for r in records if c in r and str(r[c]).strip() not in ('', 'None', 'nan')]
        nonempty = len(vals)
        missing = len(records) - nonempty
        distinct = len(set(str(v).strip().lower() for v in vals))

        is_id = is_id_or_unwanted_column(c)
        s_num = coerce_to_numeric(pd.Series(vals)) if not is_id else pd.Series([])

        stat_item = {
            'column': c,
            'nonempty': nonempty,
            'missing': missing,
            'distinct': distinct,
            'is_numeric': False
        }

        if len(s_num.dropna()) >= max(2, int(len(records) * 0.3)) and not is_id:
            unit = infer_measure_unit(c)
            stat_item.update({
                'is_numeric': True,
                'mean': round(float(s_num.mean()), 2),
                'median': round(float(s_num.median()), 2),
                'min': round(float(s_num.min()), 2),
                'max': round(float(s_num.max()), 2),
                'unit': unit
            })
            numeric_cols.append(c)
            df[f'__clean_{c}'] = coerce_to_numeric(df[c])
        elif 1 < distinct <= 10 and not is_id and not is_name_or_text_column(c):
            categorical_cols.append(c)

        column_stats.append(stat_item)

    # Find primary categorical grouping column (Department, Team, Role, Stage)
    primary_cat = None
    for term in ('department', 'dept', 'team', 'division', 'role', 'status', 'stage'):
        for c in categorical_cols:
            if term in str(c).lower().replace('_', '').replace(' ', ''):
                primary_cat = c
                break
        if primary_cat:
            break
    if not primary_cat and categorical_cols:
        primary_cat = categorical_cols[0]

    # Build direct data extract bar charts (Average Rating, Attendance, Overtime, Absent Days)
    projections = []
    for num_col in numeric_cols:
        clean_c = f'__clean_{num_col}' if f'__clean_{num_col}' in df.columns else num_col
        unit = infer_measure_unit(num_col)

        if primary_cat:
            is_additive = unit in ('days', 'hrs', 'count', '$') and 'rate' not in str(num_col).lower()
            if is_additive:
                grp = df.groupby(primary_cat)[clean_c].sum().reset_index()
                title = f"Total {num_col} by {primary_cat}"
            else:
                grp = df.groupby(primary_cat)[clean_c].mean().reset_index()
                title = f"Average {num_col} by {primary_cat}"

            grp = grp.sort_values(by=clean_c, ascending=False)
            bars = [
                {'label': str(r[primary_cat]), 'value': round(clean_float(r[clean_c]), 2)}
                for _, r in grp.iterrows()
                if pd.notna(r[primary_cat])
            ]
            if bars:
                projections.append({
                    'id': f"proj_bar_{num_col}",
                    'type': 'bar',
                    'title': title,
                    'category_col': primary_cat,
                    'metric_col': num_col,
                    'unit': unit,
                    'bars': bars
                })

    # Build categorical distribution donuts
    for cat_col in categorical_cols:
        vc = df[cat_col].value_counts().head(8)
        tot = max(1, int(vc.sum()))
        slices = [
            {
                'label': str(lbl),
                'count': int(cnt),
                'pct': round((cnt / tot) * 100, 1),
                'color': PALETTE[idx % len(PALETTE)]
            }
            for idx, (lbl, cnt) in enumerate(vc.items())
        ]
        if len(slices) >= 2:
            projections.append({
                'id': f"proj_donut_{cat_col}",
                'type': 'donut',
                'title': f"{cat_col} Distribution",
                'category_col': cat_col,
                'total': tot,
                'slices': slices
            })

    return {
        'available': True,
        'sheet_id': sheet['id'],
        'sheet_name': sheet['name'],
        'original_name': sheet['original_name'],
        'row_count': len(records),
        'col_count': len(cols),
        'column_stats': column_stats,
        'projections': projections
    }


# =============================================================================
# EXECUTIVE OVERVIEW: AUTONOMOUS INDUSTRIAL AI VISUAL INTELLIGENCE DASHBOARD
# Strictly formula-grounded industrial People Analytics models & cross-sheet insights
# =============================================================================
def build_workspace_visual_dashboard(conn, sheet_id: int | None = None, model: str | None = None) -> dict:
    """Assembles the executive suite with industrial formula-based People Analytics."""
    visualizations = []

    # Fetch sheets and rows
    sheets_query = (
        'SELECT s.id, s.name, s.row_count, s.columns_json, d.original_name '
        'FROM sheets s JOIN dataset_uploads d ON d.id=s.dataset_id ORDER BY s.id ASC'
    )
    all_sheet_rows = conn.execute(sheets_query).fetchall()
    sheet_meta_map = {r['id']: dict(r) for r in all_sheet_rows}

    sheet_data_map = {}
    for sid in sheet_meta_map:
        rows = conn.execute('SELECT data_json FROM sheet_rows WHERE sheet_id=? ORDER BY row_index', (sid,)).fetchall()
        sheet_data_map[sid] = [json.loads(r['data_json']) for r in rows]

    # Run Industrial Pipeline
    industrial_res = run_ingestion_industrial_pipeline(conn)

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
            'elasticity_data': el,
            'stats_pills': [
                {'label': 'Impact Penalty (β)', 'value': f"{el['beta_coefficient']} pts / day"},
                {'label': 'Tipping Point', 'value': f"{el['tipping_point_days']} absent days"},
                {'label': 'Model Fit R²', 'value': f"{el['r_squared']}"}
            ],
            'ai_insight': el['ai_insight']
        })

    # 5. CROSS-SHEET GROUPED COMPARATIVE BARS
    rels = conn.execute(
        "SELECT r.*, l.name as left_name, rg.name as right_name "
        "FROM sheet_relationships r "
        "JOIN sheets l ON l.id = r.left_sheet "
        "JOIN sheets rg ON rg.id = r.right_sheet "
        "WHERE r.matching_pairs > 0 "
        "ORDER BY (r.status='linked') DESC, r.matching_pairs DESC"
    ).fetchall()

    seen_sheet_pairs = set()
    deduped_rels = []
    for rel in rels:
        pair_key = (min(rel['left_sheet'], rel['right_sheet']), max(rel['left_sheet'], rel['right_sheet']))
        if pair_key not in seen_sheet_pairs:
            seen_sheet_pairs.add(pair_key)
            deduped_rels.append(rel)

    for rel in deduped_rels:
        left_sid = rel['left_sheet']
        right_sid = rel['right_sheet']
        if left_sid not in sheet_data_map or right_sid not in sheet_data_map:
            continue

        left_rows = sheet_data_map[left_sid]
        right_rows = sheet_data_map[right_sid]
        if not left_rows or not right_rows:
            continue

        df_l = pd.DataFrame(left_rows)
        df_r = pd.DataFrame(right_rows)

        l_key = rel['left_column']
        r_key = rel['right_column']
        if l_key not in df_l.columns or r_key not in df_r.columns:
            continue

        merged = pd.merge(df_l, df_r, left_on=l_key, right_on=r_key, suffixes=('_left', '_right'))
        if len(merged) < 3:
            continue

        dept_col = None
        for cand in ('Department_left', 'Department_right', 'Department', 'dept', 'Team'):
            if cand in merged.columns:
                dept_col = cand
                break
        if not dept_col:
            continue

        # Pair candidates: (Performance vs Absent, Overtime vs Absent)
        pair_candidates = [
            ('Performance Score', 'Absent ( no of days )'),
            ('Overtime Hours', 'Absent ( no of days )')
        ]

        for col1_raw, col2_raw in pair_candidates:
            c1_merged = next((c for c in merged.columns if col1_raw.lower() in c.lower()), None)
            c2_merged = next((c for c in merged.columns if col2_raw.lower() in c.lower()), None)
            if not c1_merged or not c2_merged:
                continue

            merged[c1_merged] = coerce_to_numeric(merged[c1_merged])
            merged[c2_merged] = coerce_to_numeric(merged[c2_merged])
            valid_m = merged.dropna(subset=[c1_merged, c2_merged, dept_col])
            if len(valid_m) < 3:
                continue

            grp = valid_m.groupby(dept_col)[[c1_merged, c2_merged]].mean().reset_index()
            u1 = infer_measure_unit(col1_raw)
            u2 = infer_measure_unit(col2_raw)

            items = [
                {
                    'label': str(r[dept_col]),
                    'val1': round(clean_float(r[c1_merged]), 2),
                    'val2': round(clean_float(r[c2_merged]), 2)
                }
                for _, r in grp.iterrows()
                if pd.notna(r[dept_col])
            ]
            if len(items) < 2:
                continue

            insight = generate_comparative_insight('Department', col1_raw, col2_raw, u1, u2, items)
            left_file = sheet_meta_map[left_sid]['original_name']
            right_file = sheet_meta_map[right_sid]['original_name']
            badge_label = f"Cross-Sheet Join: {clean_file_label(left_file)} ↔ {clean_file_label(right_file)}"

            visualizations.append({
                'id': f"comp_{left_sid}_{right_sid}_{col1_raw}_{col2_raw}",
                'title': f"Cross-Sheet Impact: {col1_raw} vs {col2_raw} by Department",
                'subtitle': f"Unified relational view connecting `{left_file}` and `{right_file}`",
                'category': 'Cross-Sheet Intelligence',
                'chart_type': 'comparative_bar',
                'sheet_ids': [left_sid, right_sid],
                'sheet_badge': badge_label,
                'comparative_data': {
                    'category_col': 'Department',
                    'series': [
                        {'name': f"Avg {col1_raw}", 'unit': u1, 'color': '#10b981'},
                        {'name': f"Avg {col2_raw}", 'unit': u2, 'color': '#f43f5e'}
                    ],
                    'items': items
                },
                'stats_pills': [
                    {'label': 'Matched Personnel', 'value': f"{len(valid_m)} rows"},
                    {'label': 'Evaluated Departments', 'value': f"{len(items)}"}
                ],
                'ai_insight': insight
            })

    # 6. LONGITUDINAL 712-DAY TRAJECTORY FORECAST
    for sid, meta in sheet_meta_map.items():
        records = sheet_data_map.get(sid, [])
        if not records or len(records) < 10:
            continue

        temporal_res = extract_sheet_temporal_profile(records)
        if temporal_res:
            dates, daily_values, unit = temporal_res
            max_pts = 30
            vals_slice = daily_values[-max_pts:]
            dates_slice = dates[-max_pts:]
            model_res = holt_damped_forecast(vals_slice, steps=7)

            last_dt = datetime.fromisoformat(dates_slice[-1])
            future_labels = [(last_dt + timedelta(days=step)).strftime('%Y-%m-%d') for step in range(1, 8)]

            historical_pts = [{'period': p, 'actual': round(v, 2)} for p, v in zip(dates_slice, vals_slice)]
            forecast_pts = [
                {
                    'period': lbl,
                    'forecast': round(f['forecast'], 2),
                    'lower_95': round(f['lower_95'], 2),
                    'upper_95': round(f['upper_95'], 2),
                    'step': f['step']
                }
                for f, lbl in zip(model_res['forecasts'], future_labels)
            ]

            metrics = model_res['metrics']
            chg_sign = f"+{metrics['projected_change_pct']}%" if metrics['projected_change_pct'] >= 0 else f"{metrics['projected_change_pct']}%"
            insight = (
                f"**Longitudinal Attendance Trajectory**: Across **{len(records)} continuous observation days** in `{clean_file_label(meta['original_name'])}`, "
                f"workforce attendance and hours stabilize at **{metrics['last_actual']} hrs**. The 7-day damped Holt model predicts a "
                f"**{metrics['trend_direction']}** trajectory ({chg_sign}) shifting to **{metrics['final_projected']} hrs** "
                f"($R^2 = {metrics['r_squared']}$). Staffing stability remains robust."
            )

            visualizations.append({
                'id': f"forecast_longitudinal_{sid}",
                'title': "Workforce Daily Hours Trajectory & 7-Day Forecast",
                'subtitle': f"Longitudinal Holt-Winters model across {len(records)} observation dates in `{clean_file_label(meta['original_name'])}`",
                'category': 'Longitudinal Forecasts',
                'chart_type': 'forecast',
                'sheet_ids': [sid],
                'sheet_badge': clean_file_label(meta['original_name']),
                'forecast_data': {
                    'target_column': 'Daily Working Hours',
                    'unit': 'hrs',
                    'has_dates': True,
                    'historical': historical_pts,
                    'forecast': forecast_pts,
                    'metrics': metrics
                },
                'stats_pills': [
                    {'label': 'History Window', 'value': f"{len(records)} days"},
                    {'label': 'Trajectory', 'value': metrics['trend_direction']},
                    {'label': 'Model Fit R²', 'value': f"{metrics['r_squared']}"},
                    {'label': 'Projected Shift', 'value': chg_sign}
                ],
                'ai_insight': insight
            })

    # Filtering by sheet_id if provided
    if sheet_id is not None:
        visualizations = [v for v in visualizations if sheet_id in v.get('sheet_ids', [])]

    # Category counts
    cat_counts = {}
    for v in visualizations:
        c = v.get('category', 'Other')
        cat_counts[c] = cat_counts.get(c, 0) + 1

    category_list = ['All'] + [c for c in ('Cross-Sheet Intelligence', 'Industrial People Analytics', 'Workforce Risk & Burnout', 'Longitudinal Forecasts') if c in cat_counts]
    for c in cat_counts:
        if c not in category_list:
            category_list.append(c)

    return {
        'total_visualizations': len(visualizations),
        'categories': category_list,
        'category_counts': {'All': len(visualizations), **cat_counts},
        'visualizations': visualizations
    }
