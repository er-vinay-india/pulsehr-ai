"""Comparative and longitudinal visual suite builders."""

from datetime import datetime, timedelta
from typing import Any
import pandas as pd

from ..time_series_forecast import (
    clean_float,
    holt_damped_forecast,
    infer_measure_unit,
)
from ..executive_story import coerce_to_numeric
from ..display_formatters import format_display_label
from .visual_common import (
    clean_file_label,
    generate_comparative_insight,
    extract_sheet_temporal_profile,
)


def build_comparative_suite(conn, sheet_meta_map: dict, sheet_data_map: dict) -> list[dict]:
    """Builds cross-sheet grouped comparative bars."""
    visualizations = []
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

            c1_disp = format_display_label(col1_raw)
            c2_disp = format_display_label(col2_raw)

            visualizations.append({
                'id': f"comp_{left_sid}_{right_sid}_{col1_raw}_{col2_raw}",
                'title': f"{c1_disp} and {c2_disp.lower()} by department",
                'subtitle': f"Unified relational view connecting `{left_file}` and `{right_file}`",
                'category': 'Cross-Sheet Intelligence',
                'chart_type': 'comparative_bar',
                'sheet_ids': [left_sid, right_sid],
                'sheet_badge': badge_label,
                'comparative_data': {
                    'category_col': 'Department',
                    'series': [
                        {'name': f"Average {c1_disp.lower()}", 'unit': u1, 'color': '#10b981'},
                        {'name': f"Average {c2_disp.lower()}", 'unit': u2, 'color': '#f43f5e'}
                    ],
                    'items': items
                },
                'stats_pills': [
                    {'label': 'Matched Personnel', 'value': f"{len(valid_m)} rows"},
                    {'label': 'Evaluated Departments', 'value': f"{len(items)}"}
                ],
                'ai_insight': insight
            })

    return visualizations


def build_longitudinal_suite(sheet_meta_map: dict, sheet_data_map: dict) -> list[dict]:
    """Builds longitudinal trajectory forecasts for multi-person attendance sheets."""
    visualizations = []
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

    return visualizations
