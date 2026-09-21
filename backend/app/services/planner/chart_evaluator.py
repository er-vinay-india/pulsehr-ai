"""Bounded sheet profiling and dynamic chart prerequisite evaluation."""

import logging
from typing import Any
import pandas as pd

from .entity_classifier import classify_row_entity
from .numeric_parser import parse_numeric_series
from .chart_plans import (
    build_bar_chart_plans,
    build_flag_comparison_plans,
    build_donut_chart_plans,
    build_line_chart_plans,
)

logger = logging.getLogger(__name__)


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

    # Plan Type A: Categorical Bar Chart (Rankings & Group Comparisons)
    supported_plans.extend(
        build_bar_chart_plans(df, n_rows, primary_cat, sorted_numeric, original_file)
    )

    # Additional Plan A2: Segment / Flag Comparison (e.g. Holiday Weeks vs Regular Weeks)
    supported_plans.extend(
        build_flag_comparison_plans(df, n_rows, categorical_cols, primary_cat, sorted_numeric, original_file)
    )

    # Plan Type B: Donut / Pie Chart (Categorical Composition)
    supported_plans.extend(
        build_donut_chart_plans(df, n_rows, categorical_cols, primary_cat, original_file, max_plans=4)
    )

    # Plan Type C: Line Chart (Time Trends & Sequential Projections)
    supported_plans.extend(
        build_line_chart_plans(df, n_rows, date_cols, sorted_numeric, original_file)
    )

    if not supported_plans:
        limitations.append("No sufficient numeric variance or categorical dimensions detected to project charts.")

    return {
        "supported_charts": supported_plans,
        "limitations": limitations,
        "entity_classification": classify_row_entity(columns, records[:5]),
        "numeric_count": len(numeric_cols),
        "categorical_count": len(categorical_cols)
    }
