"""Bradford Factor Absenteeism Disruption Index (B = S^2 * D)."""

import math
import pandas as pd
from ..executive_story import coerce_to_numeric


def clean_num(val, default=0.0):
    if val is None:
        return default
    try:
        f = float(val)
        if math.isnan(f) or math.isinf(f):
            return default
        return round(f, 2)
    except (ValueError, TypeError):
        return default


def calculate_bradford_factor(records: list[dict], absent_col: str = 'Absent ( no of days )', dept_col: str = 'Department', name_col: str = 'Employee Name') -> dict:
    """Calculates employee-level and departmental Bradford Factor Disruption Scores."""
    if not records:
        return {'available': False, 'message': 'No absenteeism records provided.'}

    df = pd.DataFrame(records)
    actual_abs_col = None
    for c in df.columns:
        if c == absent_col or any(k in str(c).lower() for k in ('absent', 'absence', 'leave_days', 'days_absent')):
            actual_abs_col = c
            break

    if not actual_abs_col:
        return {'available': False, 'message': 'No absenteeism column found in dataset.'}

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

    df['__absent_days'] = coerce_to_numeric(df[actual_abs_col]).fillna(0)

    # Calculate employee-level Bradford scores
    employee_results = []
    for idx, r in df.iterrows():
        d = float(r['__absent_days'])
        if d <= 0:
            s = 0
            b = 0
        elif d == 1:
            s = 1
            b = 1
        elif d <= 3:
            s = 2
            b = (s ** 2) * d
        elif d <= 7:
            s = 3
            b = (s ** 2) * d
        else:
            s = 4
            b = (s ** 2) * d

        b = round(b, 1)

        if b <= 50:
            tier = 'Normal'
            tier_color = '#10b981'
            action = 'Standard monitoring; no intervention required'
        elif b <= 200:
            tier = 'Moderate Disruption'
            tier_color = '#06b6d4'
            action = 'Informal check-in; monitor absence patterns'
        elif b <= 500:
            tier = 'High Disruption'
            tier_color = '#f59e0b'
            action = 'Formal review required; evaluate operational impact'
        else:
            tier = 'Critical Disruption'
            tier_color = '#f43f5e'
            action = 'Management escalation & wellness intervention threshold'

        emp_name = str(r[actual_name_col]) if actual_name_col and pd.notna(r[actual_name_col]) else f"Staff #{idx+1}"
        emp_dept = str(r[actual_dept_col]) if actual_dept_col and pd.notna(r[actual_dept_col]) else "General"

        employee_results.append({
            'name': emp_name,
            'department': emp_dept,
            'absent_days': d,
            'spells': s,
            'bradford_score': b,
            'tier': tier,
            'tier_color': tier_color,
            'action': action
        })

    # Departmental Aggregations
    dept_aggregates = {}
    for item in employee_results:
        dept = item['department']
        if dept not in dept_aggregates:
            dept_aggregates[dept] = {
                'department': dept,
                'headcount': 0,
                'total_absent_days': 0.0,
                'total_bradford': 0.0,
                'critical_count': 0,
                'high_count': 0
            }
        dept_aggregates[dept]['headcount'] += 1
        dept_aggregates[dept]['total_absent_days'] += item['absent_days']
        dept_aggregates[dept]['total_bradford'] += item['bradford_score']
        if item['tier'] == 'Critical Disruption':
            dept_aggregates[dept]['critical_count'] += 1
        elif item['tier'] == 'High Disruption':
            dept_aggregates[dept]['high_count'] += 1

    dept_list = []
    for dept, data in dept_aggregates.items():
        n = max(1, data['headcount'])
        mean_b = round(data['total_bradford'] / n, 1)
        mean_d = round(data['total_absent_days'] / n, 1)
        dept_list.append({
            'department': dept,
            'headcount': n,
            'total_absent_days': round(data['total_absent_days'], 1),
            'avg_absent_days': mean_d,
            'avg_bradford_score': mean_b,
            'critical_count': data['critical_count'],
            'high_count': data['high_count'],
            'risk_pct': round(((data['critical_count'] + data['high_count']) / n) * 100, 1)
        })

    dept_list.sort(key=lambda x: x['avg_bradford_score'], reverse=True)

    # Organizational Totals
    total_staff = len(employee_results)
    org_mean_b = round(sum(e['bradford_score'] for e in employee_results) / max(1, total_staff), 1)
    critical_staff = [e for e in employee_results if e['tier'] in ('High Disruption', 'Critical Disruption')]

    top_dept = dept_list[0] if dept_list else None
    ai_insight = (
        f"**Bradford Disruption Analysis**: Across {total_staff} tracked employees, organizational absenteeism disruption averages "
        f"a Bradford Score of **{org_mean_b} pts**. **{top_dept['department']}** carries the acute disruption footprint with an "
        f"average Bradford Index of **{top_dept['avg_bradford_score']} pts** ({top_dept['risk_pct']}% of unit staff in elevated disruption tiers). "
        f"**{len(critical_staff)} personnel** exceed formal HR review thresholds (>200 pts), warranting direct management wellness reviews."
    ) if top_dept else "Absence disruption within normal operational boundaries."

    return {
        'available': True,
        'metric_name': 'Bradford Factor Disruption Index',
        'formula': 'B = S² × D (Spells² × Days Lost)',
        'organizational_avg_bradford': org_mean_b,
        'total_employees_reviewed': total_staff,
        'high_disruption_count': len(critical_staff),
        'high_disruption_pct': round((len(critical_staff) / max(1, total_staff)) * 100, 1),
        'departments': dept_list,
        'employees': employee_results,
        'ai_insight': ai_insight
    }
