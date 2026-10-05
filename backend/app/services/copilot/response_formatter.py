"""Shared response formatter for copilot analytical execution.

Uses the coordinator's response-detail setting to determine what appears in chat:
- Brief: Default for direct factual questions (e.g. 'which department has the highest attendance?').
- Detailed: When the user asks for explanation, comparison, evidence, or a breakdown.

Keeps necessary qualifications beside the answer; displays tables, recommendations,
and extra governance notes when requested.
"""
from __future__ import annotations

import re
from typing import Any, Literal


DETAIL_REQUEST_PATTERNS = re.compile(
    r'\b(?:explain|explanation|why|factors?|root\s*cause|reasons?|'
    r'compare|comparison|versus|vs|gap|difference\s*between|'
    r'evidence|methodology|governance|audit|limitations?|caveats?|'
    r'breakdown|break\s*down|table|drilldown|drill\s*down|'
    r'recommend(?:ation|ations)?|actions?|action\s*plan|'
    r'details?|detailed|full\s*list|all\s*departments?|every\s*department)\b',
    re.IGNORECASE
)


def decide_response_detail(
    query: str,
    plan_intent: str | None = None,
    ranking_limit: int = 1
) -> Literal['brief', 'detailed']:
    """Decides response detail level for the coordinator's enriched request.

    - Brief: Default for direct factual questions such as 'which department has the highest attendance?'.
    - Detailed: When the user asks for explanation, comparison, evidence, or a breakdown.
    """
    q = query.strip()

    # 1. Explicit user request for explanation, comparison, evidence, or breakdown
    if DETAIL_REQUEST_PATTERNS.search(q):
        return 'detailed'

    # 2. Plan intent requiring multi-perspective synthesis, action plans, or deep breakdowns
    if plan_intent in ('breakdown', 'summary_concerns', 'summary_actions', 'followup_why', 'correlation_causation'):
        return 'detailed'

    # 3. Explicit multi-row table/breakdown requested via limit > 1
    if ranking_limit > 1:
        return 'detailed'

    # 4. Default to brief for direct factual questions
    return 'brief'


def format_analytical_response(
    result: dict[str, Any],
    response_detail: Literal['brief', 'detailed'] = 'brief'
) -> str:
    """Shared response formatter using the coordinator's detail setting.

    Preserves identical calculations, dense ranks, and ties between brief and detailed.
    """
    if response_detail == 'detailed':
        # Detailed mode: Return full structured answer with tables, recommendations, and governance notes
        return result.get('detailed_answer') or result.get('answer', '')

    # Brief mode: Produce direct, concise factual finding with necessary qualifications beside the answer
    findings = result.get('findings') or {}
    plan = result.get('query_plan') or {}
    raw_analysis = result.get('raw_analysis') or {}

    # Case 1: HR Period Attendance Analytics
    if 'dense_ranked' in findings or ('departments' in raw_analysis and 'organization_benchmarks' in raw_analysis):
        dense_ranked = findings.get('dense_ranked') or []
        if not dense_ranked and 'departments' in raw_analysis:
            # Fallback if findings not pre-attached
            metric_key = findings.get('metric_key') or (
                'avg_attendance_per_employee' if plan.get('metric') == 'attendance' else 'net_attendance_days'
            )
            reverse_sort = (plan.get('direction') == 'highest')
            depts = raw_analysis.get('departments', [])
            sorted_depts = sorted(depts, key=lambda d: (d.get(metric_key, 0), d.get('headcount', 0)), reverse=reverse_sort)
            curr_rank = 1
            for idx, d in enumerate(sorted_depts):
                if idx > 0 and abs(d.get(metric_key, 0) - sorted_depts[idx - 1].get(metric_key, 0)) > 0.001:
                    curr_rank += 1
                dc = dict(d)
                dc['dense_rank'] = curr_rank
                dense_ranked.append(dc)

        if dense_ranked:
            direction = plan.get('direction', 'highest')
            tied_targets = [d for d in dense_ranked if d.get('dense_rank') == 1]
            primary_target = dense_ranked[0]
            metric_key = findings.get('metric_key') or (
                'avg_attendance_per_employee' if plan.get('metric') == 'attendance' else 'net_attendance_days'
            )

            metric_name = plan.get('metric', 'attendance')
            if metric_name == 'attendance':
                metric_phrase = 'average office attendance'
            elif metric_name == 'leaves':
                metric_phrase = 'average approved leaves'
            else:
                metric_phrase = findings.get('metric_display_name', 'attendance')

            month = findings.get('month') or raw_analysis.get('month') or plan.get('time_window') or 'July'
            val_num = primary_target.get(metric_key, 0.0)

            unit_suffix = findings.get('unit_suffix', ' days/employee')
            if 'day' in unit_suffix:
                val_str = f"{val_num:.2f} days per employee"
            else:
                val_str = f"{val_num:.2f}{unit_suffix}"

            if len(tied_targets) > 1:
                tied_names = " and ".join(d['department'] for d in tied_targets)
                pop_counts = " and ".join(str(d.get('headcount', 1)) for d in tied_targets)
                emp_label = "employee" if all(d.get('headcount', 1) == 1 for d in tied_targets) and len(tied_targets) == 1 else "employees"
                ans = f"{tied_names} tied for the {direction} {metric_phrase} in {month}: {val_str}, across {pop_counts} {emp_label}."
                if any(d.get('is_small_population') for d in tied_targets):
                    ans += " (Note: Group headcount is small; individual absences impact the average heavily.)"
                return ans
            else:
                dept_name = primary_target['department']
                pop = primary_target.get('headcount', 1)
                emp_label = "employee" if pop == 1 else "employees"
                ans = f"{dept_name} had the {direction} {metric_phrase} in {month}: {val_str}, across {pop} {emp_label}."
                if primary_target.get('is_small_population'):
                    ans += f" (Note: Group headcount ({pop} staff) is small; individual absences impact the average heavily.)"
                return ans

    # Case 2: General Tabular Query
    if 'dense_groups' in findings or ('groups' in raw_analysis and 'baseline' in raw_analysis):
        dense_groups = findings.get('dense_groups') or []
        if dense_groups:
            direction = plan.get('direction', 'highest')
            metric_lbl = findings.get('metric_label') or plan.get('metric', 'value')
            tied_targets = [g for g in dense_groups if g.get('dense_rank') == 1]
            primary_target = dense_groups[0]
            val = primary_target.get('value', 0.0)
            time_win = plan.get('time_window')
            period_str = f" in {time_win}" if time_win else ""

            if len(tied_targets) > 1:
                tied_names = " and ".join(g['group'] for g in tied_targets)
                ans = f"{tied_names} tied for the {direction} {metric_lbl}{period_str}: {val:,.2f}."
                if any(g.get('small_sample') for g in tied_targets):
                    ans += " (Note: Group size is small; individual entries heavily impact the average.)"
                return ans
            else:
                g_name = primary_target['group']
                used_rows = primary_target.get('used_rows', 1)
                ans = f"{g_name} recorded the {direction} {metric_lbl}{period_str}: {val:,.2f} across {used_rows} valid records."
                if primary_target.get('small_sample'):
                    ans += f" (Note: Group size ({used_rows} records) is small; individual entries heavily impact the average.)"
                return ans

    # Case 3: Employee Attendance Query
    if raw_analysis.get('entity_grain') == 'employee' or plan.get('entity_grain') == 'employee':
        rows = raw_analysis.get('rows', [])
        direction = plan.get('direction', 'highest')
        time_win = plan.get('time_window')
        period_str = f" in {time_win}" if time_win else ""
        if rows:
            top_rank_rows = [r for r in rows if r.get('rank') == 1]
            if len(top_rank_rows) > 1:
                tied_ids = " and ".join(r.get('id', 'N/A') for r in top_rank_rows)
                top_att = top_rank_rows[0].get('attendance', 0.0)
                att_str = f"{top_att:.0f} days" if top_att == int(top_att) else f"{top_att:.2f} days"
                return f"{tied_ids} tied for the {direction} recorded attendance{period_str}: {att_str}."
            else:
                top_r = rows[0]
                emp_id = top_r.get('id', 'N/A')
                top_att = top_r.get('attendance', 0.0)
                att_str = f"{top_att:.0f} days" if top_att == int(top_att) else f"{top_att:.2f} days"
                return f"{emp_id} had the {direction} recorded attendance{period_str}: {att_str}."

    # Fallback to result's default answer
    return result.get('answer', '')
