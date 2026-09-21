"""Workforce Workload & Burnout Strain Index, and Cross-Sheet OLS Elasticity Regression."""

import numpy as np
import pandas as pd
from ..executive_story import coerce_to_numeric
from .bradford_model import clean_num


def calculate_burnout_strain_index(df_perf: pd.DataFrame, df_absent: pd.DataFrame | None = None) -> dict:
    """Calculates departmental workload strain to detect burnout and compensatory overtime."""
    if df_perf is None or len(df_perf) < 3:
        return {'available': False, 'message': 'Insufficient performance records.'}

    ot_col = None
    for c in df_perf.columns:
        if any(k in str(c).lower() for k in ('overtime', 'extra_hours', 'ot_hours')):
            ot_col = c
            break

    dept_col = None
    for c in df_perf.columns:
        if any(k in str(c).lower() for k in ('dept', 'department', 'team', 'division')):
            dept_col = c
            break

    if not ot_col or not dept_col:
        return {'available': False, 'message': 'Overtime hours or department column not identified.'}

    merged = df_perf.copy()
    merged['__ot'] = coerce_to_numeric(merged[ot_col]).fillna(0)

    absent_col = None
    if df_absent is not None and len(df_absent) > 0:
        for c in df_absent.columns:
            if any(k in str(c).lower() for k in ('absent', 'leave', 'days_off')):
                absent_col = c
                break
        if absent_col:
            shared_key = None
            for cand in ('Employee ID', 'EmployeeName', 'Department', 'Employee Name'):
                if cand in df_perf.columns and cand in df_absent.columns:
                    shared_key = cand
                    break
            if shared_key:
                m_sub = df_absent[[shared_key, absent_col]].copy()
                m_sub['__abs_days'] = coerce_to_numeric(m_sub[absent_col]).fillna(0)
                merged = pd.merge(merged, m_sub, on=shared_key, how='left')
                merged['__abs_days'] = merged['__abs_days'].fillna(0)
            else:
                merged['__abs_days'] = 0.0
        else:
            merged['__abs_days'] = 0.0
    else:
        merged['__abs_days'] = 0.0

    dept_stats = []
    for dept, grp in merged.groupby(dept_col):
        n = len(grp)
        mean_ot = clean_num(grp['__ot'].mean(), 0.0)
        tot_ot = clean_num(grp['__ot'].sum(), 0.0)
        mean_abs = clean_num(grp['__abs_days'].mean(), 0.0) if '__abs_days' in grp.columns else 0.0

        # Formula: Strain % = (Avg Overtime / 160) * (1 + Avg Absent Days / 20) * 100
        strain_pct = round(((mean_ot / 160.0) * (1.0 + (mean_abs / 20.0))) * 100.0, 1)

        if strain_pct >= 20.0:
            status = 'Critical Burnout Zone'
            status_color = '#f43f5e'
        elif strain_pct >= 10.0:
            status = 'Elevated Strain'
            status_color = '#f59e0b'
        else:
            status = 'Sustainable Load'
            status_color = '#10b981'

        dept_stats.append({
            'department': str(dept),
            'headcount': n,
            'avg_overtime_hours': mean_ot,
            'total_overtime_hours': tot_ot,
            'avg_absent_days': mean_abs,
            'strain_index_pct': strain_pct,
            'status': status,
            'status_color': status_color
        })

    dept_stats.sort(key=lambda x: x['strain_index_pct'], reverse=True)
    top_strain = dept_stats[0] if dept_stats else None

    ai_insight = (
        f"**Workload Strain Diagnostic**: **{top_strain['department']}** operates at peak strain of "
        f"**{top_strain['strain_index_pct']}%** (averaging **{top_strain['avg_overtime_hours']} hrs overtime** per staff). "
        f"Elevated overtime paired with absenteeism suggests compensatory coverage strain. "
        f"Review staffing allocations in {top_strain['department']} to mitigate productivity burnout."
    ) if top_strain and top_strain['strain_index_pct'] > 5.0 else "Workforce overtime remains within sustainable operational boundaries."

    return {
        'available': True,
        'metric_name': 'Workforce Burnout & Workload Strain Index',
        'formula': 'Strain Index = (Avg OT / 160h) × (1 + Avg Absent / 20d) × 100%',
        'departments': dept_stats,
        'highest_strain_department': top_strain['department'] if top_strain else None,
        'highest_strain_pct': top_strain['strain_index_pct'] if top_strain else 0.0,
        'ai_insight': ai_insight
    }


def calculate_cross_sheet_elasticity(df_perf: pd.DataFrame, df_absent: pd.DataFrame, perf_col: str = 'Performance Score', absent_col: str = 'Absent ( no of days )', join_key: str = 'Employee ID') -> dict:
    """Calculates empirical regression slope (beta) of performance loss per absent day."""
    if df_perf is None or df_absent is None or join_key not in df_perf.columns or join_key not in df_absent.columns:
        return {'available': False, 'message': 'Missing join key between performance and absence datasets.'}

    m = pd.merge(df_perf, df_absent, on=join_key, suffixes=('_perf', '_abs'))
    if len(m) < 4:
        return {'available': False, 'message': 'Insufficient matched records for regression analysis.'}

    # Resolve columns
    p_col = perf_col if perf_col in m.columns else next((c for c in m.columns if 'perf' in c.lower() or 'score' in c.lower()), None)
    a_col = absent_col if absent_col in m.columns else next((c for c in m.columns if 'absent' in c.lower() or 'leave' in c.lower()), None)

    if not p_col or not a_col:
        return {'available': False, 'message': 'Required performance and absence columns not matched.'}

    m['__p'] = coerce_to_numeric(m[p_col])
    m['__a'] = coerce_to_numeric(m[a_col])
    valid = m.dropna(subset=['__p', '__a'])
    if len(valid) < 4:
        return {'available': False, 'message': 'Insufficient valid numeric pairs.'}

    x = valid['__a'].to_numpy()
    y = valid['__p'].to_numpy()

    # Linear Regression: y = alpha + beta * x
    n = len(x)
    x_mean = np.mean(x)
    y_mean = np.mean(y)

    var_x = np.sum((x - x_mean) ** 2)
    if var_x == 0:
        return {'available': False, 'message': 'Zero variance in absenteeism records.'}

    cov_xy = np.sum((x - x_mean) * (y - y_mean))
    beta = float(cov_xy / var_x)
    alpha = float(y_mean - beta * x_mean)

    # R-squared
    y_pred = alpha + beta * x
    ss_res = np.sum((y - y_pred) ** 2)
    ss_tot = np.sum((y - y_mean) ** 2)
    r_squared = float(1.0 - (ss_res / ss_tot)) if ss_tot > 0 else 0.0
    r_squared = max(0.0, min(1.0, round(r_squared, 3)))

    # Pearson r
    pearson_r = float(np.corrcoef(x, y)[0, 1]) if len(x) > 1 else 0.0

    # Empirical tipping point (where absence causes performance to drop below organizational median)
    med_perf = float(np.median(y))
    tipping_point_days = round(float((med_perf - alpha) / beta), 1) if beta != 0 else 3.0
    tipping_point_days = max(1.0, tipping_point_days)

    impact_direction = 'penalty' if beta < 0 else 'gain'
    ai_insight = (
        f"**Cross-Sheet Elasticity**: Statistical OLS regression across **{n} matched employee records** confirms a "
        f"**{abs(round(beta, 2))} pt performance {impact_direction}** for each additional absent day "
        f"(Pearson $r = {round(pearson_r, 2)}$, $R^2 = {r_squared}$). The model identifies **{tipping_point_days} absent days** "
        f"as the critical operational tipping point, beyond which individual productivity drops below company median."
    )

    return {
        'available': True,
        'metric_name': 'Performance-Absenteeism Cross-Elasticity',
        'matched_records': n,
        'beta_coefficient': round(beta, 3),
        'intercept_alpha': round(alpha, 2),
        'r_squared': r_squared,
        'pearson_correlation': round(pearson_r, 3),
        'tipping_point_days': tipping_point_days,
        'ai_insight': ai_insight
    }
