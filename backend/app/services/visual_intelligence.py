"""Autonomous AI Multi-Sheet Visual Intelligence Dashboard Engine.

Discovers, joins, and projects multi-chart intelligence suites across all uploaded datasets,
cross-sheet relationships, and longitudinal trajectories without artificial single-chart constraints.
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
    low_m1 = min(items, key=lambda x: x.get('val1', 0))

    is_absent = any(k in m2.lower() for k in ('absent', 'leave', 'sick'))
    is_perf = any(k in m1.lower() for k in ('performance', 'rating', 'score'))
    is_ot = any(k in m1.lower() for k in ('overtime', 'hours'))

    if is_perf and is_absent:
        return (
            f"**Cross-Sheet Impact**: **{top_m1['label']}** benchmarks peak performance at "
            f"**{top_m1['val1']} {u1}** alongside **{top_m1['val2']} {u2}** absent. Conversely, **{top_m2['label']}** "
            f"logs the highest absence impact (**{top_m2['val2']} {u2}**), correlating with performance at "
            f"**{top_m2['val1']} {u1}**. Focus leadership coaching on high-absence clusters to protect department velocity."
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


def generate_bar_insight(cat_col: str, metric_col: str, unit: str, bars: list[dict]) -> str:
    """Generates a data-grounded AI insight for a single-metric bar chart."""
    if not bars:
        return f"Distribution of **{metric_col}** across {cat_col} segments."

    top = bars[0]
    bottom = bars[-1]
    values = [b['value'] for b in bars]
    avg_val = round(sum(values) / len(values), 2)

    c_lower = metric_col.lower()
    if 'absent' in c_lower or 'leave' in c_lower:
        return (
            f"**Absenteeism Profile**: **{top['label']}** accounts for the highest absenteeism footprint with "
            f"**{top['value']} {unit}**, exceeding the organizational mean of **{avg_val} {unit}**. "
            f"In contrast, **{bottom['label']}** maintains the healthiest attendance record at **{bottom['value']} {unit}**."
        )
    elif 'performance' in c_lower or 'score' in c_lower or 'rating' in c_lower:
        return (
            f"**Talent Appraisal Baseline**: **{top['label']}** benchmarks workforce output at "
            f"**{top['value']} {unit}**, exceeding the department average of **{avg_val} {unit}**. "
            f"**{bottom['label']}** presents growth and enablement potential at **{bottom['value']} {unit}**."
        )
    elif 'overtime' in c_lower or 'hours' in c_lower:
        return (
            f"**Overtime Concentration**: **{top['label']}** registers highest overtime strain at "
            f"**{top['value']} {unit}**, compared to an organizational average of **{avg_val} {unit}**. "
            f"Review resourcing in {top['label']} to preserve sustainable team delivery."
        )
    elif 'attendance' in c_lower:
        return (
            f"**Punctuality & Presence**: Attendance across departments averages **{avg_val} {unit}**, led by "
            f"**{top['label']}** at **{top['value']} {unit}**. **{bottom['label']}** logs the lowest presence at "
            f"**{bottom['value']} {unit}**, warranting departmental check-in."
        )

    return (
        f"**Metric Analysis**: **{metric_col}** averages **{avg_val} {unit}** across {len(bars)} recorded {cat_col} groups. "
        f"**{top['label']}** ranks highest at **{top['value']} {unit}**, while **{bottom['label']}** holds the base at **{bottom['value']} {unit}**."
    )


def generate_donut_insight(cat_col: str, slices: list[dict], total: int) -> str:
    """Generates an executive AI takeaway for a donut distribution chart."""
    if not slices:
        return f"Distribution of records by {cat_col}."

    dominant = max(slices, key=lambda s: s.get('count', 0))
    c_lower = cat_col.lower()

    if 'risk' in c_lower:
        high_risk = next((s for s in slices if any(k in s['label'].lower() for k in ('high', 'elevated', 'critical'))), None)
        high_risk_str = f", with **{high_risk['pct']}% ({high_risk['count']} staff)** in elevated risk tiers" if high_risk else ""
        return (
            f"**Workforce Risk Segmentation**: The majority ({dominant['pct']}%) of personnel falls into **{dominant['label']}**"
            f"{high_risk_str}. Focus retention and support programs on elevated segments."
        )
    elif 'rating' in c_lower or 'band' in c_lower or 'tier' in c_lower:
        return (
            f"**Appraisal Concentration**: **{dominant['label']}** represents **{dominant['pct']}% ({dominant['count']} of {total} employees)**. "
            f"The talent distribution reflects a balanced appraisal spectrum across units."
        )
    elif 'absence' in c_lower or 'leave' in c_lower:
        return (
            f"**Absence Severity Segmentation**: **{dominant['label']}** comprises **{dominant['pct']}%** of all tracked employees. "
            f"Staff in multi-day absence tiers should be scheduled for proactive wellness reviews."
        )

    return (
        f"**Category Distribution**: **{dominant['label']}** is the prevailing segment, encompassing "
        f"**{dominant['pct']}% ({dominant['count']}/{total})** of all entries across {len(slices)} distinct categories."
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


def build_workspace_visual_dashboard(conn, sheet_id: int | None = None, model: str | None = None) -> dict:
    """Assembles an autonomous, multi-sheet visual gallery spanning all uploaded datasets and cross-sheet relationships."""
    visualizations = []

    # 1. Fetch all sheets with their datasets
    sheets_query = (
        'SELECT s.id, s.name, s.row_count, s.columns_json, d.original_name '
        'FROM sheets s JOIN dataset_uploads d ON d.id=s.dataset_id ORDER BY s.id ASC'
    )
    all_sheet_rows = conn.execute(sheets_query).fetchall()
    sheet_meta_map = {r['id']: dict(r) for r in all_sheet_rows}

    # Fetch rows for each sheet
    sheet_data_map = {}
    for sid in sheet_meta_map:
        rows = conn.execute('SELECT data_json FROM sheet_rows WHERE sheet_id=? ORDER BY row_index', (sid,)).fetchall()
        sheet_data_map[sid] = [json.loads(r['data_json']) for r in rows]

    # =========================================================================
    # 2. CROSS-SHEET INTELLIGENCE VISUALIZATIONS (Grouped Comparative Bars)
    # =========================================================================
    # Group relationships by sheet pair to avoid duplicate chart projections
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

        # Find shared categorical column (e.g. Department)
        dept_col = None
        for cand in ('Department_left', 'Department_right', 'Department', 'dept', 'Team', 'Role'):
            if cand in merged.columns:
                dept_col = cand
                break
        if not dept_col:
            for c in merged.columns:
                if any(t in c.lower() for t in ('dept', 'department', 'team', 'division')):
                    dept_col = c
                    break

        if not dept_col:
            continue

        # Find candidate numeric columns on left and right
        l_num_cols = [
            c for c in df_l.columns
            if not is_id_or_unwanted_column(c) and coerce_to_numeric(df_l[c]).notna().sum() >= max(2, int(len(df_l) * 0.3))
        ]
        r_num_cols = [
            c for c in df_r.columns
            if not is_id_or_unwanted_column(c) and coerce_to_numeric(df_r[c]).notna().sum() >= max(2, int(len(df_r) * 0.3))
        ]

        # Prioritize high-impact pairings (Perf vs Absent, Attendance vs Absent, Overtime vs Absent)
        def pair_score(p):
            s = 0
            t1, t2 = p[0].lower(), p[1].lower()
            if ('perf' in t1 or 'score' in t1 or 'rating' in t1) and ('absent' in t2 or 'leave' in t2):
                s += 10
            if ('absent' in t1 or 'leave' in t1) and ('perf' in t2 or 'score' in t2 or 'rating' in t2):
                s += 10
            if ('att' in t1 and 'absent' in t2) or ('absent' in t1 and 'att' in t2):
                s += 8
            if ('overtime' in t1 and 'absent' in t2) or ('absent' in t1 and 'overtime' in t2):
                s += 6
            return s

        pair_candidates = []
        for lc in l_num_cols:
            for rc in r_num_cols:
                if lc == rc:
                    continue
                pair_candidates.append((lc, rc))

        pair_candidates.sort(key=pair_score, reverse=True)

        for col1_raw, col2_raw in pair_candidates[:3]:
            c1_merged = f"{col1_raw}_left" if f"{col1_raw}_left" in merged.columns else col1_raw
            c2_merged = f"{col2_raw}_right" if f"{col2_raw}_right" in merged.columns else col2_raw

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

            top_item1 = max(items, key=lambda x: x['val1'])
            top_item2 = max(items, key=lambda x: x['val2'])

            visualizations.append({
                'id': f"comp_{left_sid}_{right_sid}_{col1_raw}_{col2_raw}",
                'title': f"Cross-Sheet: {col1_raw} vs {col2_raw} by Department",
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
                    {'label': f"Top {col1_raw}", 'value': f"{top_item1['label']} ({top_item1['val1']} {u1})"},
                    {'label': f"Highest {col2_raw}", 'value': f"{top_item2['label']} ({top_item2['val2']} {u2})"},
                    {'label': 'Matched Records', 'value': f"{len(valid_m)} rows"}
                ],
                'ai_insight': insight
            })

    # =========================================================================
    # 3. PER-SHEET MULTI-METRIC BAR CHARTS & DISTRIBUTION DONUTS
    # =========================================================================
    for sid, meta in sheet_meta_map.items():
        records = sheet_data_map.get(sid, [])
        if not records or len(records) < 3:
            continue

        df = pd.DataFrame(records)
        cols = json.loads(meta['columns_json']) if meta['columns_json'] else list(df.columns)
        domain, domain_badge = detect_sheet_domain(cols)

        # Categorize column into domain category
        def get_category_name(d: str, c: str) -> str:
            cl = str(c).lower()
            if any(k in cl for k in ('perf', 'score', 'rating', 'appraisal', 'eval', 'risk')):
                return 'Performance & Talent'
            if any(k in cl for k in ('absent', 'leave', 'sick', 'attendance', 'hours', 'overtime', 'punctual')):
                return 'Attendance & Leave'
            if any(k in cl for k in ('hire', 'candidate', 'applicant', 'pipeline', 'salary', 'payroll')):
                return 'Operations & Pipeline'
            if 'Attendance' in d:
                return 'Attendance & Leave'
            if 'Performance' in d:
                return 'Performance & Talent'
            return 'Workforce Demographics'

        # Classify numeric and categorical columns
        numeric_cols = []
        categorical_cols = []
        for c in cols:
            if is_id_or_unwanted_column(c):
                continue
            s_num = coerce_to_numeric(df[c])
            if s_num.notna().sum() >= max(2, int(len(df) * 0.25)):
                numeric_cols.append(c)
                df[f'__clean_{c}'] = s_num
            else:
                n_uniq = df[c].nunique()
                # Exclude freeform text, employee names, notes, and 100% unique columns
                if 1 < n_uniq <= 10 and n_uniq < len(df) and not is_name_or_text_column(c):
                    categorical_cols.append(c)

        # Primary grouping column for bars
        primary_cat = None
        for term in ('department', 'dept', 'team', 'division', 'role', 'status'):
            for c in categorical_cols:
                if term in str(c).lower().replace('_', '').replace(' ', ''):
                    primary_cat = c
                    break
            if primary_cat:
                break
        if not primary_cat and categorical_cols:
            primary_cat = categorical_cols[0]

        # 3A. Generate Single-Metric Bar Charts for all numeric columns
        for num_col in numeric_cols:
            clean_c = f'__clean_{num_col}' if f'__clean_{num_col}' in df.columns else num_col
            unit = infer_measure_unit(num_col)
            cat_label = get_category_name(domain, num_col)

            if primary_cat:
                is_additive = unit in ('days', 'hrs', 'count', '$') and 'rate' not in str(num_col).lower()
                if is_additive:
                    grouped = df.groupby(primary_cat)[clean_c].sum().reset_index()
                    title = f"Total {num_col} by {primary_cat}"
                else:
                    grouped = df.groupby(primary_cat)[clean_c].mean().reset_index()
                    title = f"Average {num_col} by {primary_cat}"

                grouped = grouped.sort_values(by=clean_c, ascending=False)
                bars = [
                    {'label': str(r[primary_cat]), 'value': round(clean_float(r[clean_c]), 2)}
                    for _, r in grouped.iterrows()
                    if pd.notna(r[primary_cat])
                ]

                if bars:
                    insight = generate_bar_insight(primary_cat, num_col, unit, bars)
                    top_bar = bars[0]
                    avg_v = round(sum(b['value'] for b in bars) / len(bars), 2)

                    visualizations.append({
                        'id': f"bar_{sid}_{num_col}",
                        'title': title,
                        'subtitle': f"Granular {primary_cat} metric breakdown in `{clean_file_label(meta['original_name'])}`",
                        'category': cat_label,
                        'chart_type': 'bar',
                        'sheet_ids': [sid],
                        'sheet_badge': clean_file_label(meta['original_name']),
                        'bar_data': {
                            'category_col': primary_cat,
                            'metric_col': num_col,
                            'unit': unit,
                            'bars': bars
                        },
                        'stats_pills': [
                            {'label': f"Top {primary_cat}", 'value': f"{top_bar['label']} ({top_bar['value']} {unit})"},
                            {'label': 'Cohort Average', 'value': f"{avg_v} {unit}"},
                            {'label': 'Records', 'value': f"{len(df)}"}
                        ],
                        'ai_insight': insight
                    })

        # 3B. Generate Donut Distribution Charts for clean categorical columns
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
                cat_label = get_category_name(domain, cat_col)
                insight = generate_donut_insight(cat_col, slices, tot)
                dominant = max(slices, key=lambda s: s['count'])

                visualizations.append({
                    'id': f"donut_{sid}_{cat_col}",
                    'title': f"{cat_col} Distribution",
                    'subtitle': f"Demographic and categorical composition in `{clean_file_label(meta['original_name'])}`",
                    'category': cat_label,
                    'chart_type': 'donut',
                    'sheet_ids': [sid],
                    'sheet_badge': clean_file_label(meta['original_name']),
                    'donut_data': {
                        'category_col': cat_col,
                        'total': tot,
                        'slices': slices
                    },
                    'stats_pills': [
                        {'label': 'Leading Segment', 'value': f"{dominant['label']} ({dominant['pct']}%)"},
                        {'label': 'Unique Categories', 'value': f"{len(slices)}"},
                        {'label': 'Total Sample', 'value': f"{tot}"}
                    ],
                    'ai_insight': insight
                })

        # 3C. Dynamic Binned Donut Charts (e.g. Absence Severity, Performance Rating Bands)
        for num_col in numeric_cols:
            c_low = num_col.lower()
            s_vals = coerce_to_numeric(df[num_col]).dropna()
            if len(s_vals) < 4:
                continue

            if 'absent' in c_low or 'leave' in c_low:
                # Absence severity tiers
                c0 = int((s_vals == 0).sum())
                c1 = int(((s_vals >= 1) & (s_vals <= 3)).sum())
                c2 = int((s_vals > 3).sum())
                tot = len(s_vals)
                if tot > 0 and (c0 > 0 or c1 > 0 or c2 > 0):
                    slices = [
                        {'label': 'Zero Absence (0 Days)', 'count': c0, 'pct': round((c0/tot)*100, 1), 'color': '#10b981'},
                        {'label': 'Standard Leave (1–3 Days)', 'count': c1, 'pct': round((c1/tot)*100, 1), 'color': '#06b6d4'},
                        {'label': 'Critical Absence (> 3 Days)', 'count': c2, 'pct': round((c2/tot)*100, 1), 'color': '#f43f5e'},
                    ]
                    slices = [s for s in slices if s['count'] > 0]
                    insight = generate_donut_insight('Absence Severity', slices, tot)
                    visualizations.append({
                        'id': f"donut_binned_{sid}_absence_severity",
                        'title': "Absence Severity Breakdown",
                        'subtitle': f"Risk segmentation derived from `{clean_file_label(meta['original_name'])}`",
                        'category': 'Attendance & Leave',
                        'chart_type': 'donut',
                        'sheet_ids': [sid],
                        'sheet_badge': clean_file_label(meta['original_name']),
                        'donut_data': {
                            'category_col': 'Absence Severity',
                            'total': tot,
                            'slices': slices
                        },
                        'stats_pills': [
                            {'label': 'Critical Absence (>3d)', 'value': f"{c2} staff ({round((c2/tot)*100, 1)}%)"},
                            {'label': 'Zero Absence', 'value': f"{c0} staff ({round((c0/tot)*100, 1)}%)"}
                        ],
                        'ai_insight': insight
                    })

    # =========================================================================
    # 4. LONGITUDINAL TRAJECTORIES & TIME-SERIES FORECASTS
    # =========================================================================
    for sid, meta in sheet_meta_map.items():
        records = sheet_data_map.get(sid, [])
        if not records or len(records) < 3:
            continue

        # 4A. Check if this is a wide multi-person temporal dataset (like Kaggle attendance with 712 rows)
        temporal_res = extract_sheet_temporal_profile(records)
        if temporal_res:
            dates, daily_values, unit = temporal_res
            # Run Holt's damped smoothing over daily values
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
                f"**Longitudinal Attendance Trajectory**: Over **{len(records)} continuous days** in `{clean_file_label(meta['original_name'])}`, "
                f"daily workforce hours average **{metrics['last_actual']} hrs**. The 7-day damped Holt model predicts a "
                f"**{metrics['trend_direction']}** trend ({chg_sign}) shifting to **{metrics['final_projected']} hrs** "
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

        # 4B. Standard sequential or date forecasts for other sheets
        else:
            df = pd.DataFrame(records)
            num_cols = [
                c for c in df.columns
                if not is_id_or_unwanted_column(c) and coerce_to_numeric(df[c]).notna().sum() >= max(3, int(len(df) * 0.4))
            ]
            if num_cols:
                primary_col = num_cols[0]
                unit = infer_measure_unit(primary_col)
                vals = [float(v) for v in coerce_to_numeric(df[primary_col]).dropna()]
                if len(vals) >= 4:
                    pts_slice = vals[-20:] if len(vals) > 20 else vals
                    periods_slice = [f"Cohort {i+1}" for i in range(len(pts_slice))]
                    steps = min(5, max(2, len(pts_slice) // 2))
                    model_res = holt_damped_forecast(pts_slice, steps=steps)

                    future_labels = [f"Projected +{s}" for s in range(1, steps + 1)]
                    historical_pts = [{'period': p, 'actual': round(v, 2)} for p, v in zip(periods_slice, pts_slice)]
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
                        f"**Cohort Predictive Model**: Sequential trend analysis on **{primary_col}** projects a "
                        f"**{metrics['trend_direction']}** movement ({chg_sign}) from baseline **{metrics['last_actual']} {unit}** "
                        f"to **{metrics['final_projected']} {unit}** across future cohorts ($R^2 = {metrics['r_squared']}$). "
                        f"Monitor ongoing intake to ensure target alignment."
                    )

                    visualizations.append({
                        'id': f"forecast_sequential_{sid}_{primary_col}",
                        'title': f"{primary_col} Trend & Cohort Projection",
                        'subtitle': f"Holt-Winters predictive smoothing on `{clean_file_label(meta['original_name'])}`",
                        'category': 'Longitudinal Forecasts',
                        'chart_type': 'forecast',
                        'sheet_ids': [sid],
                        'sheet_badge': clean_file_label(meta['original_name']),
                        'forecast_data': {
                            'target_column': primary_col,
                            'unit': unit,
                            'has_dates': False,
                            'historical': historical_pts,
                            'forecast': forecast_pts,
                            'metrics': metrics
                        },
                        'stats_pills': [
                            {'label': 'Trajectory', 'value': metrics['trend_direction']},
                            {'label': 'Projected Shift', 'value': chg_sign},
                            {'label': 'Model R²', 'value': f"{metrics['r_squared']}"}
                        ],
                        'ai_insight': insight
                    })

    # =========================================================================
    # 5. FILTERING (if specific sheet_id requested) & CATEGORY ASSEMBLY
    # =========================================================================
    if sheet_id is not None:
        # Keep charts associated with this sheet or cross-sheet charts involving this sheet
        visualizations = [v for v in visualizations if sheet_id in v.get('sheet_ids', [])]

    # Calculate category counts
    cat_counts = {}
    for v in visualizations:
        c = v.get('category', 'Other')
        cat_counts[c] = cat_counts.get(c, 0) + 1

    category_list = ['All'] + [c for c in ('Cross-Sheet Intelligence', 'Performance & Talent', 'Attendance & Leave', 'Longitudinal Forecasts', 'Operations & Pipeline') if c in cat_counts]
    for c in cat_counts:
        if c not in category_list:
            category_list.append(c)

    return {
        'total_visualizations': len(visualizations),
        'categories': category_list,
        'category_counts': {'All': len(visualizations), **cat_counts},
        'visualizations': visualizations
    }
