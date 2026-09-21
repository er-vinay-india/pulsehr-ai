"""McKinsey / GE 9-Box Talent Performance-Potential Matrix."""

import pandas as pd
from ..executive_story import coerce_to_numeric
from .bradford_model import clean_num


def calculate_9box_matrix(records: list[dict], perf_col: str = 'Performance Score', risk_col: str = 'Risk Level', name_col: str = 'Employee Name', dept_col: str = 'Department') -> dict:
    """Evaluates workforce into an industrial 3x3 Talent Matrix."""
    if not records:
        return {'available': False, 'message': 'No talent appraisal records provided.'}

    df = pd.DataFrame(records)

    # Discover Performance Column
    actual_perf_col = None
    for c in df.columns:
        if c == perf_col or any(k in str(c).lower() for k in ('perf', 'score', 'kpi', 'rating')):
            actual_perf_col = c
            break

    # Discover Risk / Potential Column
    actual_risk_col = None
    for c in df.columns:
        if c == risk_col or any(k in str(c).lower() for k in ('risk', 'potential', 'attrition', 'flight')):
            actual_risk_col = c
            break

    if not actual_perf_col:
        return {'available': False, 'message': 'No performance appraisal measure found.'}

    actual_dept_col = None
    for c in df.columns:
        if c == dept_col or any(k in str(c).lower() for k in ('dept', 'department', 'team', 'division')):
            actual_dept_col = c
            break

    actual_name_col = None
    for c in df.columns:
        if c == name_col or any(k in str(c).lower() for k in ('name', 'employeename', 'full_name', 'employee')):
            actual_name_col = c
            break

    df['__clean_perf'] = coerce_to_numeric(df[actual_perf_col]).dropna()
    if len(df['__clean_perf'].dropna()) < 3:
        return {'available': False, 'message': 'Insufficient numeric performance records.'}

    # Derive performance thresholds (Dynamic Terciles or Scale Boundaries)
    p_max = float(df['__clean_perf'].max())
    if p_max <= 5.5:
        low_cut, high_cut = 3.2, 4.2
    elif p_max <= 10.5:
        low_cut, high_cut = 7.5, 8.5
    else:
        low_cut = float(df['__clean_perf'].quantile(0.33))
        high_cut = float(df['__clean_perf'].quantile(0.67))

    grid_cells = {
        'cell_high_low': {'id': 'stars', 'title': 'Stars (Future Leaders)', 'row': 'High', 'col': 'Low Risk', 'color': '#10b981', 'roster': [], 'desc': 'Benchmark performance with strong retention stability.'},
        'cell_high_med': {'id': 'high_impact', 'title': 'High-Impact Performers', 'row': 'High', 'col': 'Med Risk', 'color': '#06b6d4', 'roster': [], 'desc': 'Superior output; ensure ongoing engagement & recognition.'},
        'cell_high_high': {'id': 'at_risk_stars', 'title': 'At-Risk Stars', 'row': 'High', 'col': 'High Risk', 'color': '#f97316', 'roster': [], 'desc': 'Critical flight risk! High output paired with elevated attrition vulnerability.'},

        'cell_med_low': {'id': 'workhorses', 'title': 'Core Workhorses', 'row': 'Med', 'col': 'Low Risk', 'color': '#6366f1', 'roster': [], 'desc': 'Steady, dependable backbone of organizational delivery.'},
        'cell_med_med': {'id': 'contributors', 'title': 'Solid Contributors', 'row': 'Med', 'col': 'Med Risk', 'color': '#3b82f6', 'roster': [], 'desc': 'Consistent performers delivering within expected parameters.'},
        'cell_med_high': {'id': 'dilemma', 'title': 'Retention Dilemma', 'row': 'Med', 'col': 'High Risk', 'color': '#f59e0b', 'roster': [], 'desc': 'Moderate output coupled with disengagement signals.'},

        'cell_low_low': {'id': 'specialists', 'title': 'Effective Specialists', 'row': 'Low', 'col': 'Low Risk', 'color': '#8b5cf6', 'roster': [], 'desc': 'Loyal team members needing skill enablement.'},
        'cell_low_med': {'id': 'questions', 'title': 'Development Questions', 'row': 'Low', 'col': 'Med Risk', 'color': '#64748b', 'roster': [], 'desc': 'Under-delivering; establish structured 60-day performance goals.'},
        'cell_low_high': {'id': 'underperformers', 'title': 'Underperformers (Action Required)', 'row': 'Low', 'col': 'High Risk', 'color': '#ef4444', 'roster': [], 'desc': 'Immediate PIP or restructuring candidate; severe operational drag.'}
    }

    total_evaluated = len(df)
    for idx, r in df.iterrows():
        p_val = clean_num(r.get('__clean_perf'), 0.0)
        p_tier = 'High' if p_val >= high_cut else ('Med' if p_val >= low_cut else 'Low')

        r_val = str(r.get(actual_risk_col, '')).lower() if actual_risk_col else ''
        if any(k in r_val for k in ('high', 'elevated', 'critical', 'severe')):
            r_tier = 'High'
        elif any(k in r_val for k in ('low', 'safe', 'minimal', 'solid')):
            r_tier = 'Low'
        else:
            r_tier = 'Med'

        cell_key = f"cell_{p_tier.lower()}_{r_tier.lower()}"
        if cell_key not in grid_cells:
            cell_key = 'cell_med_med'

        emp_name = str(r[actual_name_col]) if actual_name_col and pd.notna(r[actual_name_col]) else f"Staff #{idx+1}"
        emp_dept = str(r[actual_dept_col]) if actual_dept_col and pd.notna(r[actual_dept_col]) else "General"

        grid_cells[cell_key]['roster'].append({
            'name': emp_name,
            'department': emp_dept,
            'performance': p_val,
            'risk_level': r_tier
        })

    # Summary counts
    summary_grid = []
    for k, v in grid_cells.items():
        cnt = len(v['roster'])
        pct = round((cnt / max(1, total_evaluated)) * 100, 1)
        summary_grid.append({
            **v,
            'key': k,
            'count': cnt,
            'pct': pct
        })

    stars_count = len(grid_cells['cell_high_low']['roster']) + len(grid_cells['cell_high_med']['roster'])
    at_risk_star_count = len(grid_cells['cell_high_high']['roster'])
    underperf_count = len(grid_cells['cell_low_high']['roster'])

    ai_insight = (
        f"**9-Box Talent Diagnostic**: Across **{total_evaluated} evaluated employees**, **{stars_count} leaders ({round((stars_count/total_evaluated)*100, 1)}%)** "
        f"anchor top-tier organizational output. Crucially, **{at_risk_star_count} High-Impact Star(s)** are flagged in elevated attrition risk tiers, "
        f"posing immediate IP loss exposure. **{underperf_count} employee(s)** occupy the critical underperformance quadrant, requiring structured intervention."
    )

    return {
        'available': True,
        'framework': 'McKinsey / GE 9-Box Talent Matrix',
        'total_evaluated': total_evaluated,
        'cells': summary_grid,
        'high_performers_count': stars_count + at_risk_star_count,
        'retention_vulnerable_stars': at_risk_star_count,
        'underperformers_count': underperf_count,
        'ai_insight': ai_insight
    }
