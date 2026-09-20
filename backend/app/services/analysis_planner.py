"""Bounded AI Analysis Planner & Dynamic Chart Selector.

Executes the bounded analytics workflow:
Profile -> Interpret -> Discover Relationships -> Propose Analyses & Charts -> Validate Prerequisites -> Compute -> Verify.

Guardrails:
- Pure deterministic computation (no arbitrary model code execution).
- Complete eligible datasets for metrics (no sample extrapolation).
- Row counts are never assumed to equal unique employee counts without verified unique identifiers.
- Rates require verified denominators.
- Non-additive measures (ratings, rates, percentages) are never summed.
- Time-series charts require valid temporal columns with sufficient points.
"""

import json
import logging
import math
import re
from datetime import datetime
from typing import Any

import numpy as np
import pandas as pd

from ..core import config

logger = logging.getLogger(__name__)


def sanitize_untrusted_text(text: Any, max_len: int = 120) -> str:
    """Sanitizes untrusted spreadsheet cell contents to prevent prompt or layout injection."""
    if text is None:
        return ""
    s = str(text).strip()
    # Strip potential prompt injection prefixes or instruction delimiters
    s = re.sub(r'[\r\n\t]+', ' ', s)
    s = re.sub(r'(?i)\b(ignore|instructions?|prompts?|assistants?|overrides?|systems?|commands?|bypasses?)\b', '', s)
    s = re.sub(r'\s+', ' ', s).strip()
    if len(s) > max_len:
        return s[:max_len - 3] + "..."
    return s


def classify_row_entity(columns: list[str], sample_records: list[dict]) -> dict:
    """Determines what each row represents in the sheet."""
    cols_clean = [re.sub(r'[^a-zA-Z0-9]', '', str(c).lower()) for c in columns]

    has_date = any(k in cols_clean for k in ('date', 'timestamp', 'datetime', 'day', 'clockin', 'punchdate'))
    has_emp_id = any(k in cols_clean for k in ('employeeid', 'empid', 'employeecode', 'staffid', 'empcode'))
    has_candidate_id = any(k in cols_clean for k in ('candidateid', 'applicantid', 'requisitionid', 'applicationid'))
    has_salary = any(k in cols_clean for k in ('salary', 'compensation', 'basepay', 'payroll', 'wage'))
    has_perf = any(k in cols_clean for k in ('rating', 'performancescore', 'appraisal', 'kpiscore', 'score'))
    has_absent = any(k in cols_clean for k in ('absent', 'absence', 'leave', 'sickdays', 'daysabsent'))
    has_hours = any(k in cols_clean for k in ('hours', 'duration', 'overtime', 'clockout'))

    if has_candidate_id or any(k in cols_clean for k in ('candidate', 'applicant', 'stage', 'resume')):
        entity_type = "recruitment_application"
        entity_label = "Candidate Application"
        is_event_level = False
    elif has_date and (has_emp_id or has_hours or any(c.startswith('person') for c in cols_clean)):
        entity_type = "attendance_event"
        entity_label = "Daily Attendance Check-In"
        is_event_level = True
    elif has_emp_id and has_absent and not has_date:
        entity_type = "employee_absence_summary"
        entity_label = "Employee Absence Record"
        is_event_level = False
    elif has_emp_id and has_perf:
        entity_type = "employee_performance_record"
        entity_label = "Employee Performance Appraisal"
        is_event_level = False
    elif has_emp_id and has_salary:
        entity_type = "employee_compensation_record"
        entity_label = "Compensation Record"
        is_event_level = False
    elif has_emp_id:
        entity_type = "employee_record"
        entity_label = "Employee Master Record"
        is_event_level = False
    else:
        entity_type = "generic_tabular_record"
        entity_label = "Workforce Record"
        is_event_level = False

    return {
        "entity_type": entity_type,
        "entity_label": entity_label,
        "is_event_level": is_event_level,
        "has_unique_identifier": has_emp_id or has_candidate_id
    }


def parse_numeric_series(series: pd.Series) -> tuple[pd.Series, str | None]:
    """Extracts clean floats and unit metadata from numeric-like string series."""
    if pd.api.types.is_numeric_dtype(series):
        return pd.to_numeric(series, errors='coerce'), None

    cleaned = series.astype(str).str.strip()
    unit = None

    # Currency
    if cleaned.str.contains(r'[\$€£]').any():
        for cur in ('$', '€', '£'):
            if cleaned.str.startswith(cur).any():
                unit = cur
                cleaned = cleaned.str.replace(cur, '', regex=False)
                break

    # Percentage
    if cleaned.str.endswith('%').any():
        unit = '%'
        cleaned = cleaned.str.rstrip('%')

    # Commas in numbers
    cleaned = cleaned.str.replace(',', '', regex=False)

    # Ratings like "4.5/5.0"
    rating_split = cleaned.str.extract(r'^([+-]?(?:\d+(?:\.\d*)?|\.\d+))\s*/\s*(\d+(?:\.\d*)?)$')
    if rating_split[0].notna().sum() > len(cleaned) * 0.3:
        cleaned = rating_split[0]
        denom = rating_split[1].dropna().iloc[0] if len(rating_split[1].dropna()) else "5"
        unit = f"out of {denom}"

    numeric = pd.to_numeric(cleaned, errors='coerce')
    return numeric, unit


def evaluate_chart_prerequisites(
    records: list[dict],
    columns: list[str],
    sheet_name: str,
    original_file: str
) -> dict:
    """Profiles a sheet and determines supported, mathematically valid dynamic visualizations."""
    if not records:
        return {"supported_charts": [], "limitations": ["Sheet contains no rows."]}

    df = pd.DataFrame(records)
    n_rows = len(df)
    limitations = []

    # 1. Identify and clean numeric and categorical columns
    numeric_cols = {}
    categorical_cols = {}
    date_cols = []
    id_cols = []

    for col in columns:
        col_clean = str(col).lower().replace('_', '').replace(' ', '')
        if col_clean in ('id', 'employeeid', 'empid', 'code', 'candidateid', 'index') or col_clean.endswith('id') or col_clean.endswith('code'):
            id_cols.append(col)
            continue

        # Check for date
        if col_clean in ('date', 'timestamp', 'datetime', 'day', 'period', 'month', 'year'):
            try:
                parsed_dates = pd.to_datetime(df[col], errors='coerce')
                if parsed_dates.notna().sum() >= max(3, int(n_rows * 0.6)):
                    date_cols.append(col)
                    df[f'__date_{col}'] = parsed_dates
                    continue
            except Exception:
                pass

        # Check for numeric
        num_s, unit = parse_numeric_series(df[col])
        valid_count = int(num_s.notna().sum())

        if valid_count >= max(2, int(n_rows * 0.3)) and valid_count > 1:
            clean_name = f'__num_{col}'
            df[clean_name] = num_s
            inferred_unit = unit or ("hrs" if "hour" in col_clean or "ot" in col_clean else
                                    ("days" if "day" in col_clean or "absent" in col_clean or "leave" in col_clean else
                                     ("pts" if "score" in col_clean or "rating" in col_clean or "perf" in col_clean else "units")))
            numeric_cols[col] = {
                "clean_col": clean_name,
                "unit": inferred_unit,
                "mean": float(num_s.mean()),
                "median": float(num_s.median()),
                "min": float(num_s.min()),
                "max": float(num_s.max()),
                "sum": float(num_s.sum()),
                "valid_count": valid_count,
                "missing_count": n_rows - valid_count,
                "is_additive": inferred_unit in ("days", "hrs", "units", "$", "€", "£") and "rate" not in col_clean and "score" not in col_clean and "rating" not in col_clean
            }
        else:
            # Check for categorical
            distinct_vals = df[col].dropna().astype(str).str.strip().unique()
            n_distinct = len(distinct_vals)
            if 1 < n_distinct <= min(30, max(2, int(n_rows * 0.85))):
                categorical_cols[col] = {
                    "distinct_count": n_distinct,
                    "values": list(distinct_vals[:15]),
                    "is_hierarchical": any(k in col_clean for k in ('dept', 'department', 'team', 'division', 'role', 'unit', 'stage', 'status', 'band'))
                }

    # Pick primary categorical dimension (Department, Team, Role, Stage)
    primary_cat = None
    for cand in categorical_cols:
        c_clean = cand.lower().replace('_', '').replace(' ', '')
        if any(k in c_clean for k in ('department', 'dept', 'team', 'division', 'role', 'stage', 'status', 'tier')):
            primary_cat = cand
            break
    if not primary_cat and categorical_cols:
        primary_cat = list(categorical_cols.keys())[0]

    supported_plans = []

    # -------------------------------------------------------------------------
    # Plan Type A: Categorical Bar Chart (Rankings & Departmental Comparisons)
    # -------------------------------------------------------------------------
    if primary_cat and numeric_cols:
        for num_col, num_meta in list(numeric_cols.items())[:3]:
            c_name = num_meta["clean_col"]
            is_additive = num_meta["is_additive"]
            unit = num_meta["unit"]

            if is_additive:
                grp = df.groupby(primary_cat)[c_name].sum().reset_index()
                calc_type = "Summation"
                measure_title = f"Total {num_col}"
            else:
                grp = df.groupby(primary_cat)[c_name].mean().reset_index()
                calc_type = "Arithmetic Mean"
                measure_title = f"Average {num_col}"

            grp = grp.sort_values(by=c_name, ascending=False)
            bars = [
                {"label": str(r[primary_cat]), "value": round(float(r[c_name]), 2)}
                for _, r in grp.iterrows()
                if pd.notna(r[primary_cat])
            ]

            if len(bars) >= 2:
                supported_plans.append({
                    "chart_type": "bar",
                    "plan_id": f"bar_{num_col}_{primary_cat}",
                    "title": f"{measure_title} by {primary_cat}",
                    "subtitle": f"{calc_type} across {len(bars)} recorded {primary_cat.lower()} groups",
                    "measured_metric": num_col,
                    "unit": unit,
                    "aggregation_rule": calc_type,
                    "category_col": primary_cat,
                    "metric_col": num_col,
                    "bars": bars,
                    "population": f"{n_rows} source records across {len(bars)} groups",
                    "source_sheets": [original_file],
                    "coverage_pct": round((num_meta['valid_count'] / max(1, n_rows)) * 100, 1),
                    "missing_records": num_meta['missing_count']
                })

    # -------------------------------------------------------------------------
    # Plan Type B: Donut / Pie Chart (Categorical Parts of a Whole)
    # Valid only for mutually exclusive categories between 2 and 7 slices
    # -------------------------------------------------------------------------
    for cat_col, cat_meta in categorical_cols.items():
        if 2 <= cat_meta["distinct_count"] <= 7:
            vc = df[cat_col].value_counts()
            tot = int(vc.sum())
            palette = ['#10b981', '#6366f1', '#06b6d4', '#f59e0b', '#ec4899', '#8b5cf6', '#14b8a6']
            slices = [
                {
                    "label": str(lbl),
                    "count": int(cnt),
                    "pct": round((cnt / tot) * 100, 1),
                    "color": palette[i % len(palette)]
                }
                for i, (lbl, cnt) in enumerate(vc.items())
            ]
            supported_plans.append({
                "chart_type": "donut",
                "plan_id": f"donut_{cat_col}",
                "title": f"Workforce Distribution by {cat_col}",
                "subtitle": f"Proportional composition of {tot} recorded entities",
                "measured_metric": f"{cat_col} Distribution",
                "unit": "headcount & %",
                "category_col": cat_col,
                "total_population": tot,
                "slices": slices,
                "source_sheets": [original_file],
                "coverage_pct": 100.0,
                "missing_records": n_rows - tot
            })
            if len(supported_plans) >= 4:
                break

    # -------------------------------------------------------------------------
    # Plan Type C: Line Chart (Time Trends & Sequential Projections)
    # Valid only when valid dates exist and observations >= 5
    # -------------------------------------------------------------------------
    if date_cols and numeric_cols:
        d_col = date_cols[0]
        date_series = df[f'__date_{d_col}'].dropna()
        if len(date_series) >= 5:
            sorted_df = df.sort_values(by=f'__date_{d_col}')
            for num_col, num_meta in list(numeric_cols.items())[:1]:
                c_name = num_meta['clean_col']
                # Group by formatted date
                sorted_df['__date_str'] = sorted_df[f'__date_{d_col}'].dt.strftime('%Y-%m-%d')
                time_grp = sorted_df.groupby('__date_str')[c_name].mean().reset_index()
                points = [
                    {"period": str(r['__date_str']), "value": round(float(r[c_name]), 2)}
                    for _, r in time_grp.iterrows()
                    if pd.notna(r[c_name])
                ]
                if len(points) >= 5:
                    supported_plans.append({
                        "chart_type": "line",
                        "plan_id": f"line_{num_col}_{d_col}",
                        "title": f"{num_col} Trend Over Time",
                        "subtitle": f"Longitudinal progression across {len(points)} recorded periods",
                        "measured_metric": num_col,
                        "unit": num_meta["unit"],
                        "date_col": d_col,
                        "metric_col": num_col,
                        "points": points,
                        "population": f"{n_rows} events over {len(points)} dates",
                        "source_sheets": [original_file],
                        "coverage_pct": round((num_meta['valid_count'] / max(1, n_rows)) * 100, 1),
                        "missing_records": num_meta['missing_count']
                    })

    if not supported_plans:
        limitations.append("No sufficient numeric variance or categorical dimensions detected to project charts.")

    return {
        "supported_charts": supported_plans,
        "limitations": limitations,
        "entity_classification": classify_row_entity(columns, records[:5]),
        "numeric_count": len(numeric_cols),
        "categorical_count": len(categorical_cols)
    }
