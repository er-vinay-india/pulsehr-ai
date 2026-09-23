"""Relational cross-sheet correlation and 2D quadrant segmentation analysis."""

import json
import math
import httpx
import pandas as pd

from ...core import config
from .story_profiler import (
    coerce_to_numeric,
    is_id_or_unwanted_column,
    clean_ai_markdown,
)
from ..time_series_forecast import clean_float, infer_measure_unit
from ..ai_evaluation import evaluate_ai_narrative


def compute_relational_story(conn, model: str | None = None) -> dict | None:
    """Discovers exact-key relationships between uploaded sheets and computes dynamic 2D correlation and quadrant segmentation."""
    rel = conn.execute(
        "SELECT r.*, l.name as left_name, l.columns_json as left_cols, "
        "rg.name as right_name, rg.columns_json as right_cols "
        "FROM sheet_relationships r "
        "JOIN sheets l ON l.id = r.left_sheet "
        "JOIN sheets rg ON rg.id = r.right_sheet "
        "WHERE r.status='linked' ORDER BY r.matching_pairs DESC LIMIT 1"
    ).fetchone()

    if not rel:
        return None

    left_sheet = conn.execute("SELECT s.*, d.original_name FROM sheets s JOIN dataset_uploads d ON d.id=s.dataset_id WHERE s.id=?", (rel['left_sheet'],)).fetchone()
    right_sheet = conn.execute("SELECT s.*, d.original_name FROM sheets s JOIN dataset_uploads d ON d.id=s.dataset_id WHERE s.id=?", (rel['right_sheet'],)).fetchone()
    if not left_sheet or not right_sheet:
        return None

    # Fetch joined rows across the complete matched set
    joined_rows = conn.execute("""
        SELECT l.data_json as left_data, r.data_json as right_data
        FROM sheet_rows l
        JOIN sheet_rows r ON json_extract(l.data_json, ?) = json_extract(r.data_json, ?)
        WHERE l.sheet_id = ? AND r.sheet_id = ?
    """, (f"$.{rel['left_column']}", f"$.{rel['right_column']}", rel['left_sheet'], rel['right_sheet'])).fetchall()

    if not joined_rows:
        return None

    # Merge records without overwriting identically named columns
    records = []
    l_name = left_sheet['name']
    r_name = right_sheet['name']
    for r in joined_rows:
        l_dict = json.loads(r['left_data'])
        r_dict = json.loads(r['right_data'])
        rec = {}
        for k, v in l_dict.items():
            rec[k] = v
        for k, v in r_dict.items():
            if k in rec and k not in (rel['left_column'], rel['right_column']):
                rec[f"{r_name}_{k}"] = v
            else:
                rec[k] = v
        records.append(rec)

    df = pd.DataFrame(records)
    total_joined = len(records)

    left_cols = json.loads(left_sheet['columns_json'])
    right_cols = json.loads(right_sheet['columns_json'])

    # Find candidate numeric measures on both sides
    left_num_candidates = [
        c for c in left_cols 
        if c in df.columns and coerce_to_numeric(df[c]).notna().sum() >= max(2, int(total_joined * 0.3))
        and not is_id_or_unwanted_column(c)
    ]
    right_num_candidates = [
        c for c in right_cols 
        if c in df.columns and coerce_to_numeric(df[c]).notna().sum() >= max(2, int(total_joined * 0.3))
        and not is_id_or_unwanted_column(c)
    ]

    # Select best pair (col_x from left or right, col_y from the other)
    col_x, col_y = None, None
    best_corr = None

    if left_num_candidates and right_num_candidates:
        # Check all cross combinations to find the strongest correlation
        for lx in left_num_candidates:
            for ry in right_num_candidates:
                if lx == ry:
                    continue
                sx = coerce_to_numeric(df[lx])
                sy = coerce_to_numeric(df[ry])
                valid = sx.notna() & sy.notna()
                if valid.sum() > 2:
                    val_c = sx[valid].corr(sy[valid])
                    if pd.notna(val_c):
                        if best_corr is None or abs(val_c) > abs(best_corr):
                            best_corr = val_c
                            col_x = lx
                            col_y = ry
        if not col_x:
            col_x = left_num_candidates[0]
            col_y = right_num_candidates[0]
    else:
        # Fallback to any two numeric columns in the joined DataFrame
        all_numeric = [
            c for c in df.columns 
            if coerce_to_numeric(df[c]).notna().sum() >= max(2, int(total_joined * 0.3))
            and not is_id_or_unwanted_column(c)
        ]
        if len(all_numeric) >= 2:
            col_x, col_y = all_numeric[0], all_numeric[1]

    # Name and Dept columns
    col_name = None
    for term in ('name', 'employeename', 'full_name', 'candidate', 'person'):
        for c in df.columns:
            if term in str(c).lower().replace('_', '').replace(' ', ''):
                col_name = c
                break
        if col_name:
            break

    col_dept = None
    for term in ('department', 'dept', 'team', 'division', 'role', 'unit'):
        for c in df.columns:
            if term in str(c).lower().replace('_', '').replace(' ', ''):
                col_dept = c
                break
        if col_dept:
            break

    quadrant_data = {'q1': [], 'q2': [], 'q3': [], 'q4': []}
    correlation = None
    unit_x = infer_measure_unit(col_x) if col_x else 'units'
    unit_y = infer_measure_unit(col_y) if col_y else 'units'

    # Dynamic quadrant definitions based on metric semantics
    q_titles = {
        'q1': {'title': f"High {col_x} · High {col_y}", 'badgeColor': '#10b981', 'icon': '⭐', 'desc': f"Above median in both {col_x} and {col_y}."},
        'q2': {'title': f"Lower {col_x} · High {col_y}", 'badgeColor': '#818cf8', 'icon': '⚡', 'desc': f"Below median in {col_x}, but excels in {col_y}."},
        'q3': {'title': f"High {col_x} · Lower {col_y}", 'badgeColor': '#f59e0b', 'icon': '🎯', 'desc': f"Above median in {col_x}, with development opportunities in {col_y}."},
        'q4': {'title': f"Lower {col_x} · Lower {col_y}", 'badgeColor': '#ef4444', 'icon': '⚠️', 'desc': f"Below median in both {col_x} and {col_y}."}
    }

    # Contextual tailoring for common HR pairings
    is_x_absent = any(k in str(col_x).lower() for k in ('absent', 'leave', 'sick'))
    is_y_perf = any(k in str(col_y).lower() for k in ('rating', 'score', 'perf'))
    is_x_att = any(k in str(col_x).lower() for k in ('attendance', 'present'))

    if is_x_absent and is_y_perf:
        q_titles['q1'] = {'title': 'Burnout Vulnerability', 'badgeColor': '#f97316', 'icon': '🔥', 'desc': f'High {col_y} paired with elevated {col_x}. Vulnerable to exhaustion.'}
        q_titles['q2'] = {'title': 'Core Workforce Anchors', 'badgeColor': '#10b981', 'icon': '⚓', 'desc': f'High {col_y} with low {col_x}. Dependable high performers.'}
        q_titles['q3'] = {'title': 'Attrition Risk', 'badgeColor': '#ef4444', 'icon': '⚠️', 'desc': f'High {col_x} paired with lower {col_y}. Disengagement signals.'}
        q_titles['q4'] = {'title': 'Performance Alignment', 'badgeColor': '#64748b', 'icon': '🎯', 'desc': f'Low {col_x} with growth potential in {col_y}.'}
    elif is_x_att and is_y_perf:
        q_titles['q1'] = {'title': 'Core Workforce Anchors', 'badgeColor': '#10b981', 'icon': '⚓', 'desc': f'Superior {col_x} and dependable {col_y}. Operational pillars.'}
        q_titles['q2'] = {'title': 'High-Efficiency Stars', 'badgeColor': '#818cf8', 'icon': '⚡', 'desc': f'Flexible {col_x} delivering high {col_y}.'}
        q_titles['q3'] = {'title': 'Diligent Focus', 'badgeColor': '#f59e0b', 'icon': '🎯', 'desc': f'High {col_x} needing coaching in {col_y}.'}
        q_titles['q4'] = {'title': 'Retention & Risk Review', 'badgeColor': '#ef4444', 'icon': '⚠️', 'desc': f'Lower {col_x} paired with sub-threshold {col_y}.'}

    if col_x and col_y:
        s_x = coerce_to_numeric(df[col_x])
        s_y = coerce_to_numeric(df[col_y])
        valid = s_x.notna() & s_y.notna()

        if valid.sum() > 2:
            corr_val = float(s_x[valid].corr(s_y[valid]))
            correlation = round(corr_val, 2) if not math.isnan(corr_val) else None

        med_x = clean_float(s_x.median(), 0.0)
        med_y = clean_float(s_y.median(), 0.0)

        for _, row in df.iterrows():
            raw_x = coerce_to_numeric(pd.Series([row.get(col_x)])).iloc[0]
            raw_y = coerce_to_numeric(pd.Series([row.get(col_y)])).iloc[0]
            val_x = clean_float(raw_x, 0.0)
            val_y = clean_float(raw_y, 0.0)
            emp_name = str(row.get(col_name) or row.get(rel['left_column']) or 'Entity')
            emp_dept = str(row.get(col_dept) or 'General')

            item = {'name': emp_name, 'dept': emp_dept, 'val_x': round(val_x, 2), 'val_y': round(val_y, 2)}

            if val_x >= med_x and val_y >= med_y:
                quadrant_data['q1'].append(item)
            elif val_x < med_x and val_y >= med_y:
                quadrant_data['q2'].append(item)
            elif val_x >= med_x and val_y < med_y:
                quadrant_data['q3'].append(item)
            else:
                quadrant_data['q4'].append(item)

    gt_relational = {
        'joined_entities': total_joined,
        'relationship': f"{left_sheet['name']} [{rel['left_column']}] ↔ {right_sheet['name']} [{rel['right_column']}]",
        'metric_x': col_x,
        'metric_y': col_y,
        'correlation': correlation,
        'q1_count': len(quadrant_data['q1']),
        'q2_count': len(quadrant_data['q2']),
        'q3_count': len(quadrant_data['q3']),
        'q4_count': len(quadrant_data['q4']),
    }

    # Prompt AI for relational narrative
    target_model = model or config.OLLAMA_MODEL
    prompt = (
        f"You are the Chief HR Analytics Officer. Write a concise relational synthesis for joined sheets:\n"
        f"Relationship: {gt_relational['relationship']} across {total_joined} matched rows.\n"
        f"Analyzed Measures: X = '{col_x}' ({unit_x}) vs Y = '{col_y}' ({unit_y}) with Pearson correlation r = {correlation}.\n"
        f"Quadrant Breakdown: {q_titles['q1']['title']} ({gt_relational['q1_count']}), "
        f"{q_titles['q2']['title']} ({gt_relational['q2_count']}), {q_titles['q3']['title']} ({gt_relational['q3_count']}), "
        f"{q_titles['q4']['title']} ({gt_relational['q4_count']}).\n"
        f"Write an executive paragraph interpreting this relationship for overall organizational health. Format in markdown."
    )

    narrative = ''
    try:
        from ..gateway.model_gateway import ModelGateway
        from ...core.models_config import ModelRole
        res = ModelGateway.generate(
            role=ModelRole.ANALYST,
            prompt=prompt,
            step_name="story_relational_synthesis"
        )
        if res.success and res.raw_text:
            narrative = clean_ai_markdown(res.raw_text)
    except Exception:
        pass

    if not narrative:
        corr_phrase = f"correlation coefficient of {correlation}" if correlation is not None else "distributional relationship"
        narrative = (
            f"### Cross-Sheet Relational Discovery\n"
            f"By joining **{left_sheet['name']}** with **{right_sheet['name']}** across **{total_joined} matched entities**, "
            f"we observe a **{corr_phrase}** between **{col_x}** and **{col_y}**.\n\n"
            f"- **{q_titles['q1']['title']}**: **{gt_relational['q1_count']} entities** place in the upper tier of both measures.\n"
            f"- **{q_titles['q2']['title']}**: **{gt_relational['q2_count']} entities** exhibit elevated {col_y} alongside lower {col_x}.\n"
            f"- **{q_titles['q3']['title']}**: **{gt_relational['q3_count']} entities** show elevated {col_x} paired with lower {col_y}.\n"
            f"- **{q_titles['q4']['title']}**: **{gt_relational['q4_count']} entities** require active review in both dimensions."
        )

    eval_res = evaluate_ai_narrative(narrative, gt_relational, total_joined)

    return {
        'relationship_id': rel['id'],
        'left_sheet_name': left_sheet['name'],
        'right_sheet_name': right_sheet['name'],
        'matching_pairs': total_joined,
        'metric_x': col_x,
        'metric_y': col_y,
        'unit_x': unit_x,
        'unit_y': unit_y,
        'correlation': correlation,
        'quadrant_configs': q_titles,
        'quadrants': quadrant_data,
        'narrative': narrative,
        'evaluation': eval_res,
        'model_used': target_model
    }
