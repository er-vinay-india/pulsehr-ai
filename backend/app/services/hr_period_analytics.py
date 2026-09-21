"""Normalized Temporal Fact & Department Analytics Service for PulseHR AI.

Provides:
1. Normalization of wide period columns into employee-period facts with row/column provenance.
2. Cross-validation of weekly period sums against source monthly totals per employee.
3. Department x Month x Metric rollups (distinct employee headcount, sums, averages).
4. Verified deterministic ranking with ties, small-population caveats, and org benchmark comparisons.
5. Cross-sheet employee ID reconciliation without measure multiplication.
6. Explicit data governance handling for single-month history (no fabricated trends) and negative final attendance.
"""

from dataclasses import dataclass, field
from typing import Any
import re
import pandas as pd
from .semantic_mapping import infer_semantic_catalog


@dataclass
class NormalizedPeriod:
    label: str
    start_day: int
    end_day: int
    month: str
    year: int | None
    length_days: int
    attendance_col: str | None
    leave_col: str | None


MONTH_ORDER = {
    'January': 1, 'February': 2, 'March': 3, 'April': 4, 'May': 5, 'June': 6,
    'July': 7, 'August': 8, 'September': 9, 'October': 10, 'November': 11, 'December': 12
}


def parse_period_column(col_name: str, known_year: int | None = None) -> tuple[int, int, str, int | None, int] | None:
    """Extracts start_day, end_day, month, year, length_days from a period header."""
    s = col_name.strip().lower()
    # Match patterns like '1st to 5th july', '6th to 12th july', '27th-31st july', '1st to 5th july 2026'
    m = re.search(r'(\d+)(?:st|nd|rd|th)?\s*(?:to|-)\s*(\d+)(?:st|nd|rd|th)?\s+([a-z]+)(?:\s+(\d{4}))?', s)
    if m:
        start_d = int(m.group(1))
        end_d = int(m.group(2))
        month_name = m.group(3).title()
        yr = int(m.group(4)) if m.group(4) else known_year
        length = max(1, end_d - start_d + 1)
        return start_d, end_d, month_name, yr, length
    return None


def extract_normalized_periods(columns: list[str], known_year: int | None = None) -> list[NormalizedPeriod]:
    """Identifies and pairs attendance and leave period columns in chronological order, keyed with year."""
    periods_map: dict[str, dict[str, Any]] = {}

    for c in columns:
        parsed = parse_period_column(c, known_year=known_year)
        if not parsed:
            continue
        start_d, end_d, month_name, yr, length = parsed
        yr_str = str(yr) if yr is not None else "unspecified"
        # Key with year to prevent multi-year collisions
        key = f"{start_d}_{end_d}_{month_name}_{yr_str}"
        is_leave = 'leave' in c.lower() or 'absent' in c.lower()

        if key not in periods_map:
            label_yr = f" {yr}" if yr else ""
            periods_map[key] = {
                'label': f"{start_d} to {end_d} {month_name}{label_yr}",
                'start_day': start_d,
                'end_day': end_d,
                'month': month_name,
                'year': yr,
                'length_days': length,
                'attendance_col': None,
                'leave_col': None
            }

        if is_leave:
            periods_map[key]['leave_col'] = c
        else:
            periods_map[key]['attendance_col'] = c

    # Sort chronologically by year, month order, then start day
    def sort_key(p: dict[str, Any]):
        y = p['year'] if p['year'] is not None else 0
        m = MONTH_ORDER.get(p['month'], 0)
        d = p['start_day']
        return (y, m, d)

    sorted_items = sorted(periods_map.values(), key=sort_key)
    return [NormalizedPeriod(**item) for item in sorted_items]


def find_column_by_role(df: pd.DataFrame, keywords: tuple[str, ...]) -> str | None:
    for col in df.columns:
        c_norm = col.strip().lower().replace('_', ' ').replace('-', ' ')
        if any(k in c_norm for k in keywords):
            return col
    return None


def analyze_hr_attendance_sheet(
    records: list[dict],
    columns: list[str],
    sheet_name: str = 'Sheet1',
    comparison_sheet_records: list[dict] | None = None,
    comparison_sheet_name: str | None = None,
    known_year: int | None = None,
    requested_period: str | None = None
) -> dict[str, Any]:
    """Core analytical service for HR attendance datasets with rigorous validation and governance."""
    if not records:
        return {'error': 'No records to analyze.'}

    df = pd.DataFrame(records)
    total_records = len(df)

    # 1. Identify primary columns
    id_col = None
    for c in columns:
        c_clean = c.strip().lower().replace(' ', '').replace('_', '')
        if c_clean in ('id', 'employeeid', 'empid', 'staffid'):
            id_col = c
            break
    if not id_col:
        for c in columns:
            if 'id' in c.strip().lower():
                id_col = c
                break

    dept_col = None
    for c in columns:
        if 'department' in c.strip().lower() or 'dept' in c.strip().lower():
            dept_col = c
            break
    if not dept_col:
        dept_col = 'Department' if 'Department' in df.columns else None

    # Preserve string ID representation to prevent dropping leading zeros (e.g. "00123")
    if id_col and id_col in df.columns:
        df[id_col] = df[id_col].astype(str).str.strip()

    # Detect entity-period duplicate employee records
    duplicate_records_detected = False
    duplicate_record_count = 0
    if id_col and id_col in df.columns:
        dup_mask = df.duplicated(subset=[id_col], keep=False)
        if dup_mask.any():
            duplicate_records_detected = True
            duplicate_record_count = int(df.duplicated(subset=[id_col]).sum())

    tot_att_col = find_column_by_role(df, ('total attendance', 'total attended', 'monthly attendance'))
    app_leave_col = find_column_by_role(df, ('approved leaves', 'approved leave', 'total approved leaves', 'total leave'))
    final_att_col = find_column_by_role(df, ('final attendance', 'net attendance', 'adjusted attendance'))

    # 2. Extract structured periods
    periods = extract_normalized_periods(columns, known_year=known_year)

    # Validate requested period against available periods (reject period substitution)
    available_months = {p.month.lower() for p in periods}
    for c in columns:
        for m_name in MONTH_ORDER:
            if m_name.lower() in c.lower():
                available_months.add(m_name.lower())
    for m_name in MONTH_ORDER:
        if m_name.lower() in sheet_name.lower():
            available_months.add(m_name.lower())

    if requested_period:
        req_clean = requested_period.strip().lower()
        req_months = [m.lower() for m in MONTH_ORDER if m.lower() in req_clean]
        if req_months:
            matching = [m for m in req_months if m in available_months]
            if not matching:
                avail_str = ", ".join(sorted(m.title() for m in available_months)) if available_months else "None"
                return {
                    'status': 'period_unavailable',
                    'error': f"Requested period '{requested_period}' is not present in the dataset. Available period(s): {avail_str}.",
                    'requested_period': requested_period,
                    'available_periods': [p.label for p in periods] if periods else list(available_months),
                    'total_evaluated_records': total_records,
                    'departments': [],
                    'distinct_employees': 0,
                    'organization_benchmarks': {
                        'headcount': 0,
                        'avg_attendance_per_employee': 0.0,
                        'avg_leaves_per_employee': 0.0,
                        'total_attended_days': 0.0,
                        'total_approved_leaves': 0.0
                    }
                }

    # 3. Employee-level reconciliation without destructive fillna(0.0)
    if tot_att_col:
        df['__num_tot_att'] = pd.to_numeric(df[tot_att_col], errors='coerce')
    else:
        df['__num_tot_att'] = pd.Series([float('nan')] * len(df))

    if app_leave_col:
        df['__num_app_leave'] = pd.to_numeric(df[app_leave_col], errors='coerce')
    else:
        df['__num_app_leave'] = pd.Series([float('nan')] * len(df))

    if final_att_col:
        df['__num_final_att'] = pd.to_numeric(df[final_att_col], errors='coerce')
    else:
        df['__num_final_att'] = pd.Series([float('nan')] * len(df))

    missing_att_count = int(df['__num_tot_att'].isna().sum()) if tot_att_col else 0
    missing_leave_count = int(df['__num_app_leave'].isna().sum()) if app_leave_col else 0

    # Sum weekly attendance and leaves per employee
    att_cols = [p.attendance_col for p in periods if p.attendance_col in df.columns]
    leave_cols = [p.leave_col for p in periods if p.leave_col in df.columns]

    for ac in att_cols:
        df[f'__num_{ac}'] = pd.to_numeric(df[ac], errors='coerce')
    for lc in leave_cols:
        df[f'__num_{lc}'] = pd.to_numeric(df[lc], errors='coerce')

    if att_cols:
        df['__sum_weekly_att'] = df[[f'__num_{ac}' for ac in att_cols]].sum(axis=1, skipna=True)
    else:
        df['__sum_weekly_att'] = df['__num_tot_att'].fillna(0.0)

    if leave_cols:
        df['__sum_weekly_leave'] = df[[f'__num_{lc}' for lc in leave_cols]].sum(axis=1, skipna=True)
    else:
        df['__sum_weekly_leave'] = df['__num_app_leave'].fillna(0.0)

    att_mismatches = []
    if tot_att_col and att_cols:
        valid_tot = df['__num_tot_att'].notna()
        diff = (df.loc[valid_tot, '__sum_weekly_att'] - df.loc[valid_tot, '__num_tot_att']).abs()
        mismatch_rows = df.loc[valid_tot][diff > 0.01]
        for _, r in mismatch_rows.iterrows():
            att_mismatches.append({
                'employee_id': str(r.get(id_col, 'Unknown')),
                'weekly_sum': float(r['__sum_weekly_att']),
                'total_attendance_claimed': float(r['__num_tot_att']),
                'difference': float(r['__sum_weekly_att'] - r['__num_tot_att'])
            })

    leave_mismatches = []
    if app_leave_col and leave_cols:
        valid_l = df['__num_app_leave'].notna()
        diff = (df.loc[valid_l, '__sum_weekly_leave'] - df.loc[valid_l, '__num_app_leave']).abs()
        mismatch_rows = df.loc[valid_l][diff > 0.01]
        for _, r in mismatch_rows.iterrows():
            leave_mismatches.append({
                'employee_id': str(r.get(id_col, 'Unknown')),
                'weekly_sum': float(r['__sum_weekly_leave']),
                'approved_leaves_claimed': float(r['__num_app_leave']),
                'difference': float(r['__sum_weekly_leave'] - r['__num_app_leave'])
            })

    # Negative final attendance audit
    neg_final_count = 0
    min_final_val = 0.0
    if final_att_col:
        valid_final = df['__num_final_att'].dropna()
        neg_mask = valid_final < 0
        neg_final_count = int(neg_mask.sum())
        min_final_val = float(valid_final.min()) if not valid_final.empty else 0.0

    # Cross-sheet validation with 1-to-1 cardinality enforcement
    cross_sheet_summary = None
    if comparison_sheet_records and id_col:
        cdf = pd.DataFrame(comparison_sheet_records)
        c_id_col = next((c for c in cdf.columns if 'id' in c.lower()), None)
        c_leave_col = next((c for c in cdf.columns if 'leave' in c.lower() and 'total' in c.lower()), None)
        if c_id_col and c_leave_col:
            cdf[c_id_col] = cdf[c_id_col].astype(str).str.strip()
            cdf['__num_c_leave'] = pd.to_numeric(cdf[c_leave_col], errors='coerce').fillna(0.0)

            # Enforce 1-to-1 cardinality before cross-sheet join
            cdf_has_dups = bool(cdf.duplicated(subset=[c_id_col]).any())
            cdf_clean = cdf.drop_duplicates(subset=[c_id_col], keep='first') if cdf_has_dups else cdf
            df_clean = df.drop_duplicates(subset=[id_col], keep='first') if duplicate_records_detected else df

            merged = pd.merge(
                df_clean[[id_col, '__num_app_leave']],
                cdf_clean[[c_id_col, '__num_c_leave']],
                left_on=id_col,
                right_on=c_id_col,
                how='inner'
            )
            valid_merge = merged['__num_app_leave'].notna()
            diff_cross = (merged.loc[valid_merge, '__num_app_leave'] - merged.loc[valid_merge, '__num_c_leave']).abs()
            cross_mismatches = int((diff_cross > 0.01).sum())
            cross_sheet_summary = {
                'comparison_sheet': comparison_sheet_name or 'Leave Calculation Check',
                'primary_sheet_rows': len(df),
                'comparison_sheet_rows': len(cdf),
                'matched_employees_count': len(merged),
                'unmatched_in_comparison': len(df_clean) - len(merged),
                'exact_leave_matches': len(merged) - cross_mismatches,
                'leave_mismatch_count': cross_mismatches,
                'enforced_one_to_one': True,
                'comparison_duplicate_keys_handled': cdf_has_dups
            }

    # 4. Department rollups (using deduplicated entity records if duplicate rows present)
    departments = []
    eval_df = df.drop_duplicates(subset=[id_col], keep='first') if (id_col and duplicate_records_detected) else df

    if dept_col and dept_col in eval_df.columns:
        dept_groups = eval_df.groupby(dept_col)
        total_org_headcount = len(eval_df[id_col].dropna().unique()) if id_col else len(eval_df)
        total_org_attended_days = float(eval_df['__num_tot_att'].sum(skipna=True)) if tot_att_col else float(eval_df['__sum_weekly_att'].sum(skipna=True))
        total_org_leaves = float(eval_df['__num_app_leave'].sum(skipna=True)) if app_leave_col else float(eval_df['__sum_weekly_leave'].sum(skipna=True))

        org_valid_att_count = int(eval_df['__num_tot_att'].notna().sum()) if tot_att_col else total_org_headcount
        org_avg_att_per_emp = round(total_org_attended_days / max(1, org_valid_att_count), 2)
        org_avg_leave_per_emp = round(total_org_leaves / max(1, total_org_headcount), 2)

        for d_name, grp in dept_groups:
            d_headcount = len(grp[id_col].dropna().unique()) if id_col else len(grp)
            d_valid_att_count = int(grp['__num_tot_att'].notna().sum()) if tot_att_col else d_headcount
            d_missing_att = int(grp['__num_tot_att'].isna().sum()) if tot_att_col else 0

            d_tot_att = float(grp['__num_tot_att'].sum(skipna=True)) if tot_att_col else float(grp['__sum_weekly_att'].sum(skipna=True))
            d_tot_leave = float(grp['__num_app_leave'].sum(skipna=True)) if app_leave_col else float(grp['__sum_weekly_leave'].sum(skipna=True))
            d_net_att = float(grp['__num_final_att'].sum(skipna=True)) if final_att_col else (d_tot_att - d_tot_leave)

            avg_att_emp = round(d_tot_att / max(1, d_valid_att_count), 2)
            med_att_emp = round(float(grp['__num_tot_att'].dropna().median()), 2) if (tot_att_col and d_valid_att_count > 0) else avg_att_emp
            avg_leave_emp = round(d_tot_leave / max(1, d_headcount), 2)

            # Weekly drilldown
            drilldown = []
            for p in periods:
                p_att = float(grp[f'__num_{p.attendance_col}'].sum(skipna=True)) if (p.attendance_col and p.attendance_col in grp.columns) else 0.0
                p_leave = float(grp[f'__num_{p.leave_col}'].sum(skipna=True)) if (p.leave_col and p.leave_col in grp.columns) else 0.0
                drilldown.append({
                    'period': p.label,
                    'start_day': p.start_day,
                    'end_day': p.end_day,
                    'length_days': p.length_days,
                    'attended_days': p_att,
                    'avg_attended_per_emp': round(p_att / max(1, d_headcount), 2),
                    'leave_days': p_leave,
                    'avg_leave_per_emp': round(p_leave / max(1, d_headcount), 2)
                })

            benchmark_gap = round(avg_att_emp - org_avg_att_per_emp, 2)
            is_small = d_headcount < 5

            # Issue identification
            primary_issue = None
            proposed_action = "Maintain regular attendance monitoring."
            if benchmark_gap <= -2.0:
                primary_issue = f"Attendance trails organization benchmark by {abs(benchmark_gap):.1f} days/emp"
                proposed_action = f"HR business partner review of scheduling and coverage constraints with {d_name} management."
            elif avg_leave_emp >= org_avg_leave_per_emp * 1.5 and avg_leave_emp >= 3.0:
                primary_issue = f"High leave concentration ({avg_leave_emp:.1f} days/emp vs {org_avg_leave_per_emp:.1f} org avg)"
                proposed_action = "Review approved leave scheduling and project staffing backfill arrangements."

            departments.append({
                'department': str(d_name),
                'headcount': d_headcount,
                'headcount_share_pct': round((d_headcount / max(1, total_org_headcount)) * 100, 1),
                'total_attended_days': d_tot_att,
                'avg_attendance_per_employee': avg_att_emp,
                'median_attendance_per_employee': med_att_emp,
                'missing_attendance_records': d_missing_att,
                'total_approved_leaves': d_tot_leave,
                'avg_leaves_per_employee': avg_leave_emp,
                'net_attendance_days': d_net_att,
                'weekly_drilldown': drilldown,
                'is_small_population': is_small,
                'benchmark_gap': benchmark_gap,
                'primary_issue': primary_issue,
                'proposed_action': proposed_action
            })

    # Dense ranking for ties (lowest attendance first)
    depts_by_attendance = sorted(departments, key=lambda d: (d['avg_attendance_per_employee'], -d['headcount']))
    current_rank = 1
    for i, d in enumerate(depts_by_attendance):
        if i > 0 and d['avg_attendance_per_employee'] > depts_by_attendance[i - 1]['avg_attendance_per_employee']:
            current_rank += 1
        d['attendance_rank'] = current_rank

    has_attendance_ties = len({d['attendance_rank'] for d in depts_by_attendance}) < len(depts_by_attendance) if depts_by_attendance else False
    worst_attendance_depts = [d for d in depts_by_attendance if d['attendance_rank'] == 1]
    worst_attendance_department = worst_attendance_depts[0] if worst_attendance_depts else None

    best_rank = max((d['attendance_rank'] for d in depts_by_attendance), default=1) if depts_by_attendance else 1
    best_attendance_depts = [d for d in depts_by_attendance if d['attendance_rank'] == best_rank]
    best_attendance_department = best_attendance_depts[-1] if best_attendance_depts else None

    # Month and period labels
    month_name = periods[0].month if periods else "July"
    period_label = f"{month_name} (Reporting Year Unspecified)" if not known_year else f"{month_name} {known_year}"

    return {
        'status': 'success',
        'total_evaluated_records': total_records,
        'distinct_employees': len(df[id_col].dropna().unique()) if id_col else total_records,
        'duplicate_records_detected': duplicate_records_detected,
        'duplicate_record_count': duplicate_record_count,
        'missing_attendance_records': missing_att_count,
        'missing_leaves_records': missing_leave_count,
        'period_label': period_label,
        'month': month_name,
        'known_year': known_year,
        'historical_trend_available': False,
        'historical_trend_notice': f"Prior-month comparison unavailable. Evaluated workbook contains {month_name} records only.",
        'denominator_notice': "Scheduled workday denominators unavailable in source workbook. Calculations report validated attended days and approved leaves without fabricated absence percentages.",
        'reconciliation': {
            'attendance_mismatches_count': len(att_mismatches),
            'attendance_mismatches_sample': att_mismatches[:5],
            'leave_mismatches_count': len(leave_mismatches),
            'leave_mismatches_sample': leave_mismatches[:5],
            'cross_sheet_reconciliation': cross_sheet_summary,
            'negative_final_attendance_count': neg_final_count,
            'min_final_attendance': min_final_val,
            'final_attendance_policy_note': (
                "Final Attendance is computed as Total Attendance minus Approved Leaves. "
                "Negative values reflect net balance accounting, not employee underperformance."
                if neg_final_count > 0 else "All final attendance values are non-negative."
            )
        },
        'organization_benchmarks': {
            'headcount': total_org_headcount if dept_col else total_records,
            'avg_attendance_per_employee': org_avg_att_per_emp if dept_col else 0.0,
            'avg_leaves_per_employee': org_avg_leave_per_emp if dept_col else 0.0,
            'total_attended_days': total_org_attended_days if dept_col else 0.0,
            'total_approved_leaves': total_org_leaves if dept_col else 0.0
        },
        'departments': depts_by_attendance,
        'has_attendance_ties': has_attendance_ties,
        'worst_attendance_department': worst_attendance_department,
        'worst_attendance_departments': worst_attendance_depts,
        'best_attendance_department': best_attendance_department,
        'best_attendance_departments': best_attendance_depts
    }
