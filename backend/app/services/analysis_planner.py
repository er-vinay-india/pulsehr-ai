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
    has_sales = any(k in cols_clean for k in ('sales', 'weeklysales', 'store', 'revenue', 'orders', 'transactions', 'product', 'retail'))
    has_store = any(k in cols_clean for k in ('store', 'storeid', 'branch', 'location'))

    if has_sales and has_date and has_store:
        entity_type = "store_sales_periodic"
        entity_label = "Store Weekly Sales Record"
        is_event_level = True
    elif has_sales and has_date:
        entity_type = "sales_periodic_record"
        entity_label = "Periodic Sales Transaction"
        is_event_level = True
    elif has_sales:
        entity_type = "sales_record"
        entity_label = "Commercial Sales Record"
        is_event_level = False
    elif has_candidate_id or any(k in cols_clean for k in ('candidate', 'applicant', 'stage', 'resume')):
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
        entity_label = "Tabular Data Record"
        is_event_level = False

    return {
        "entity_type": entity_type,
        "entity_label": entity_label,
        "is_event_level": is_event_level,
        "has_unique_identifier": has_emp_id or has_candidate_id or has_store
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

    # 1. Identify and clean numeric, categorical, and date columns
    numeric_cols = {}
    categorical_cols = {}
    date_cols = []
    id_cols = []

    for col in columns:
        col_clean = str(col).lower().replace('_', '').replace(' ', '')
        if col_clean in ('id', 'employeeid', 'empid', 'candidateid', 'index') or (col_clean.endswith('id') and col_clean not in ('storeid', 'productid')):
            id_cols.append(col)
            continue

        # Check for date with multi-pass parser
        if col_clean in ('date', 'timestamp', 'datetime', 'day', 'period', 'month', 'year') or 'date' in col_clean:
            parsed_dates = None
            try:
                # 1. format='mixed' with dayfirst=True
                p1 = pd.to_datetime(df[col], errors='coerce', format='mixed', dayfirst=True)
                if p1.notna().sum() >= max(3, int(n_rows * 0.4)):
                    parsed_dates = p1
                else:
                    p2 = pd.to_datetime(df[col], errors='coerce', format='mixed', dayfirst=False)
                    if p2.notna().sum() >= max(3, int(n_rows * 0.4)):
                        parsed_dates = p2
            except Exception:
                try:
                    parsed_dates = pd.to_datetime(df[col], errors='coerce')
                except Exception:
                    pass

            if parsed_dates is not None and parsed_dates.notna().sum() >= max(3, int(n_rows * 0.4)):
                date_cols.append(col)
                df[f'__date_{col}'] = parsed_dates
                continue

        # Check distinct values for categorical / grouping dimensions
        distinct_vals = df[col].dropna().unique()
        n_distinct = len(distinct_vals)

        is_dimension_name = any(k in col_clean for k in (
            'store', 'branch', 'location', 'dept', 'department', 'team', 'division',
            'role', 'stage', 'status', 'tier', 'band', 'category', 'type', 'channel',
            'region', 'flag', 'holiday', 'gender', 'education', 'segment'
        ))

        is_discrete_cardinality = (1 < n_distinct <= 60) or (is_dimension_name and n_distinct <= 120) or (1 < n_distinct <= max(2, int(n_rows * 0.05)))

        if is_discrete_cardinality:
            # Format labels nicely for discrete groups
            formatted_vals = []
            for v in distinct_vals[:20]:
                if 'holiday' in col_clean and str(v) in ('1', '1.0', 'True', 'true'):
                    formatted_vals.append("Holiday Weeks")
                elif 'holiday' in col_clean and str(v) in ('0', '0.0', 'False', 'false'):
                    formatted_vals.append("Regular Weeks")
                elif 'store' in col_clean and str(v).isdigit():
                    formatted_vals.append(f"Store {v}")
                else:
                    formatted_vals.append(str(v))

            categorical_cols[col] = {
                "distinct_count": n_distinct,
                "values": formatted_vals,
                "is_dimension": True,
                "is_hierarchical": any(k in col_clean for k in ('dept', 'department', 'team', 'division', 'role', 'stage', 'status', 'tier', 'store', 'region'))
            }

        # Check for numeric measure
        num_s, unit = parse_numeric_series(df[col])
        valid_count = int(num_s.notna().sum())

        if valid_count >= max(2, int(n_rows * 0.3)) and valid_count > 1:
            clean_name = f'__num_{col}'
            df[clean_name] = num_s

            if any(k in col_clean for k in ('sales', 'weeklysales', 'revenue', 'price', 'payroll', 'wage', 'salary', 'cost', 'fuelprice', 'amount')):
                inferred_unit = "$"
            elif any(k in col_clean for k in ('hour', 'ot', 'overtime')):
                inferred_unit = "hrs"
            elif any(k in col_clean for k in ('day', 'absent', 'leave')):
                inferred_unit = "days"
            elif any(k in col_clean for k in ('score', 'rating', 'perf', 'cpi')):
                inferred_unit = "pts"
            elif any(k in col_clean for k in ('rate', 'pct', 'percent', 'unemployment', 'margin')):
                inferred_unit = "%"
            elif any(k in col_clean for k in ('temp', 'temperature')):
                inferred_unit = "°F"
            else:
                inferred_unit = unit or "units"

            is_additive = inferred_unit in ("$", "days", "hrs", "units") and "rate" not in col_clean and "score" not in col_clean and "rating" not in col_clean and "temp" not in col_clean and "cpi" not in col_clean and "unemployment" not in col_clean
            is_primary_measure = not (col_clean in ('id', 'code', 'flag', 'holidayflag') or (col_clean == 'store' and n_distinct < 100))

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
                "is_additive": is_additive,
                "is_primary_measure": is_primary_measure
            }

    # Pick primary categorical dimension (Store, Department, Team, Stage, Region)
    primary_cat = None
    for cand in categorical_cols:
        c_clean = cand.lower().replace('_', '').replace(' ', '')
        if any(k in c_clean for k in ('store', 'location', 'branch', 'department', 'dept', 'team', 'division', 'role', 'stage', 'status', 'tier', 'region')):
            primary_cat = cand
            break
    if not primary_cat and categorical_cols:
        primary_cat = list(categorical_cols.keys())[0]

    # Prioritize primary continuous measures over discrete ID/flag columns
    sorted_numeric = sorted(
        numeric_cols.items(),
        key=lambda x: (
            0 if any(k in x[0].lower() for k in ('sales', 'weeklysales', 'revenue', 'volume', 'amount', 'hours', 'absent', 'rating', 'score', 'salary')) else
            (1 if x[1].get('is_primary_measure') else 2)
        )
    )

    supported_plans = []

    # -------------------------------------------------------------------------
    # Plan Type A: Categorical Bar Chart (Rankings & Group Comparisons)
    # -------------------------------------------------------------------------
    if primary_cat and sorted_numeric:
        for num_col, num_meta in sorted_numeric[:2]:
            c_name = num_meta["clean_col"]
            is_additive = num_meta["is_additive"]
            unit = num_meta["unit"]

            is_sales_metric = any(k in num_col.lower() for k in ('sales', 'revenue', 'volume'))

            # For sales by store or performance by dept, average per period or sum
            if is_sales_metric:
                grp = df.groupby(primary_cat)[c_name].mean().reset_index()
                calc_type = "Average per Period"
                measure_title = f"Average {num_col}"
            elif is_additive:
                grp = df.groupby(primary_cat)[c_name].sum().reset_index()
                calc_type = "Summation"
                measure_title = f"Total {num_col}"
            else:
                grp = df.groupby(primary_cat)[c_name].mean().reset_index()
                calc_type = "Arithmetic Mean"
                measure_title = f"Average {num_col}"

            grp = grp.sort_values(by=c_name, ascending=False)
            bars = []
            for _, r in grp.iterrows():
                if pd.isna(r[primary_cat]):
                    continue
                raw_lbl = str(r[primary_cat])
                if primary_cat.lower() == 'store' and raw_lbl.isdigit():
                    lbl = f"Store {raw_lbl}"
                elif 'holiday' in primary_cat.lower():
                    lbl = "Holiday Weeks" if str(raw_lbl) in ('1', '1.0') else "Regular Weeks"
                else:
                    lbl = raw_lbl
                bars.append({"label": lbl, "value": round(float(r[c_name]), 2)})

            if len(bars) >= 2:
                cat_label_clean = primary_cat.replace('_', ' ')
                supported_plans.append({
                    "chart_type": "bar",
                    "plan_id": f"bar_{num_col}_{primary_cat}",
                    "title": f"{measure_title} by {cat_label_clean}",
                    "subtitle": f"{calc_type} ranked across {len(bars)} recorded {cat_label_clean.lower()} entities",
                    "measured_metric": num_col,
                    "unit": unit,
                    "aggregation_rule": calc_type,
                    "category_col": primary_cat,
                    "metric_col": num_col,
                    "bars": bars,
                    "population": f"{n_rows} source records across {len(bars)} {cat_label_clean.lower()} groups",
                    "source_sheets": [original_file],
                    "coverage_pct": round((num_meta['valid_count'] / max(1, n_rows)) * 100, 1),
                    "missing_records": num_meta['missing_count'],
                    "is_high_cardinality": len(bars) > 15
                })

    # Additional Plan A2: Segment / Flag Comparison (e.g. Holiday Weeks vs Regular Weeks)
    for cat_col, cat_meta in categorical_cols.items():
        if cat_col == primary_cat:
            continue
        c_clean = cat_col.lower().replace('_', '')
        if ('holiday' in c_clean or 'flag' in c_clean or cat_meta['distinct_count'] == 2) and sorted_numeric:
            best_num_col, best_num_meta = sorted_numeric[0]
            c_name = best_num_meta["clean_col"]
            unit = best_num_meta["unit"]

            grp = df.groupby(cat_col)[c_name].mean().reset_index()
            bars = []
            for _, r in grp.iterrows():
                raw_lbl = str(r[cat_col])
                if 'holiday' in c_clean:
                    lbl = "Holiday Weeks" if str(raw_lbl) in ('1', '1.0', 'True') else "Regular Weeks"
                else:
                    lbl = f"{cat_col}: {raw_lbl}"
                bars.append({"label": lbl, "value": round(float(r[c_name]), 2)})

            if len(bars) == 2:
                supported_plans.append({
                    "chart_type": "bar",
                    "plan_id": f"bar_compare_{cat_col}",
                    "title": f"Holiday Season Impact: Average {best_num_col} Comparison",
                    "subtitle": f"Comparative performance between {bars[0]['label']} and {bars[1]['label']}",
                    "measured_metric": best_num_col,
                    "unit": unit,
                    "aggregation_rule": "Arithmetic Mean",
                    "category_col": cat_col,
                    "metric_col": best_num_col,
                    "bars": bars,
                    "population": f"{n_rows} recorded periods",
                    "source_sheets": [original_file],
                    "coverage_pct": 100.0,
                    "missing_records": 0
                })
                break

    # -------------------------------------------------------------------------
    # Plan Type B: Donut / Pie Chart (Categorical Composition)
    # -------------------------------------------------------------------------
    for cat_col, cat_meta in categorical_cols.items():
        if 2 <= cat_meta["distinct_count"] <= 7 and cat_col != primary_cat:
            vc = df[cat_col].value_counts()
            tot = int(vc.sum())
            palette = ['#10b981', '#6366f1', '#06b6d4', '#f59e0b', '#ec4899', '#8b5cf6', '#14b8a6']
            slices = []
            for i, (lbl, cnt) in enumerate(vc.items()):
                raw_lbl = str(lbl)
                if 'holiday' in cat_col.lower():
                    clean_lbl = "Holiday Weeks" if raw_lbl in ('1', '1.0') else "Regular Weeks"
                else:
                    clean_lbl = raw_lbl
                slices.append({
                    "label": clean_lbl,
                    "count": int(cnt),
                    "pct": round((cnt / tot) * 100, 1),
                    "color": palette[i % len(palette)]
                })
            supported_plans.append({
                "chart_type": "donut",
                "plan_id": f"donut_{cat_col}",
                "title": f"Distribution Composition by {cat_col}",
                "subtitle": f"Proportional composition of {tot} recorded entities",
                "measured_metric": f"{cat_col} Share",
                "unit": "periods & %",
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
    # -------------------------------------------------------------------------
    if date_cols and sorted_numeric:
        d_col = date_cols[0]
        date_series = df[f'__date_{d_col}'].dropna()
        if len(date_series) >= 5:
            sorted_df = df.sort_values(by=f'__date_{d_col}').copy()
            sorted_df['__date_str'] = sorted_df[f'__date_{d_col}'].dt.strftime('%Y-%m-%d')

            # Pick top continuous measure (e.g. Weekly_Sales, Revenue, Hours)
            for num_col, num_meta in sorted_numeric[:2]:
                c_name = num_meta['clean_col']
                unit = num_meta['unit']
                is_additive = num_meta['is_additive']

                # Aggregate by date if multiple rows exist per date (e.g. 45 stores per week)
                if is_additive:
                    time_grp = sorted_df.groupby('__date_str')[c_name].sum().reset_index()
                    agg_desc = "Total Network"
                else:
                    time_grp = sorted_df.groupby('__date_str')[c_name].mean().reset_index()
                    agg_desc = "Average"

                points = [
                    {"period": str(r['__date_str']), "value": round(float(r[c_name]), 2)}
                    for _, r in time_grp.iterrows()
                    if pd.notna(r[c_name])
                ]

                if len(points) >= 5:
                    clean_metric_name = num_col.replace('_', ' ')
                    supported_plans.append({
                        "chart_type": "line",
                        "plan_id": f"line_{num_col}_{d_col}",
                        "title": f"{agg_desc} {clean_metric_name} Over Time",
                        "subtitle": f"Longitudinal progression across {len(points)} recorded periods ({points[0]['period']} to {points[-1]['period']})",
                        "measured_metric": num_col,
                        "unit": unit,
                        "date_col": d_col,
                        "metric_col": num_col,
                        "points": points,
                        "population": f"{n_rows} records aggregated across {len(points)} time periods",
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
