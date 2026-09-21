"""Cohort dimension and department-level investigation builders."""

import pandas as pd
from ..executive_story import coerce_to_numeric
from ..display_formatters import format_display_label
from .investigation_common import clean_val, find_connected_evidence
from .entity_investigation import build_general_investigation


def build_dimension_investigation(
    conn, all_sheets, sheet_records, target_sheet, dim_col, target_clean, metric_col
) -> dict:
    records = sheet_records.get(target_sheet["id"], [])
    df = pd.DataFrame(records)
    if df.empty:
        return build_general_investigation(conn, all_sheets, sheet_records, target_sheet, target_clean, metric_col)

    is_currency = any(k in str(metric_col).lower() for k in ('sale', 'rev', 'price', 'cost', 'spend', 'dollar', '$'))

    is_holiday_dim = any(k in dim_col.lower() for k in ('holiday', 'season'))
    if is_holiday_dim or "holiday" in target_clean.lower():
        is_target_holiday = "holiday weeks" in target_clean.lower() or target_clean in ("1", "1.0", "Holiday")
        if is_target_holiday:
            cohort_name = "Holiday Weeks"
            cohort_mask = df[dim_col].astype(str).str.strip().isin(['1', '1.0', 'true', 'True', 'holiday', 'Holiday Weeks'])
            other_cohort_name = "Regular Weeks"
            other_mask = ~cohort_mask
        else:
            cohort_name = "Regular Weeks"
            cohort_mask = df[dim_col].astype(str).str.strip().isin(['0', '0.0', 'false', 'False', 'regular', 'Regular Weeks'])
            other_cohort_name = "Holiday Weeks"
            other_mask = ~cohort_mask
    else:
        cohort_name = target_clean
        cohort_mask = df[dim_col].astype(str).str.strip().str.lower() == target_clean.lower()
        other_cohort_name = f"All Other {dim_col}"
        other_mask = ~cohort_mask

    cohort_rows = df[cohort_mask]
    other_rows = df[other_mask]

    num_series = coerce_to_numeric(cohort_rows[metric_col]) if metric_col in cohort_rows.columns else pd.Series([], dtype=float)
    other_series = coerce_to_numeric(other_rows[metric_col]) if metric_col in other_rows.columns else pd.Series([], dtype=float)

    cohort_avg = float(num_series.dropna().mean()) if len(num_series.dropna()) else 0.0
    cohort_total = float(num_series.dropna().sum()) if len(num_series.dropna()) else 0.0
    other_avg = float(other_series.dropna().mean()) if len(other_series.dropna()) else 0.0
    other_total = float(other_series.dropna().sum()) if len(other_series.dropna()) else 0.0

    diff_pct = ((cohort_avg - other_avg) / other_avg * 100) if other_avg > 0 else 0.0

    cohort_avg_str = f"${cohort_avg:,.2f}/wk" if is_currency else f"{cohort_avg:,.2f}"
    cohort_tot_str = f"${cohort_total / 1_000_000:,.2f}M Total" if is_currency and cohort_total >= 1_000_000 else (f"${cohort_total:,.2f}" if is_currency else f"{cohort_total:,.0f}")
    other_avg_str = f"${other_avg:,.2f}/wk ({other_cohort_name})" if is_currency else f"{other_avg:,.2f} ({other_cohort_name})"

    items = [
        {"name": f"{cohort_name} average", "value": round(cohort_avg, 2), "unit": "$" if is_currency else "pts"},
        {"name": f"{other_cohort_name} average", "value": round(other_avg, 2), "unit": "$" if is_currency else "pts"},
        {"name": f"{cohort_name} total volume", "value": round(cohort_total, 2), "unit": "$" if is_currency else "pts"},
        {"name": f"{cohort_name} sample count", "value": len(cohort_rows), "unit": "periods"},
        {"name": f"{other_cohort_name} sample count", "value": len(other_rows), "unit": "periods"}
    ]

    source_records = [
        {
            "row_index": r.get("__row_index", idx + 1),
            "sheet_name": target_sheet["name"],
            "file": target_sheet["original_name"],
            "data": {k: clean_val(v) for k, v in r.items() if not k.startswith("__")}
        }
        for idx, r in cohort_rows.head(25).iterrows()
    ]

    questions = [
        f"Does the {diff_pct:+0.1f}% variance observed during {cohort_name} hold consistently across all retail store tiers or is it heavily skewed by top supercenters?",
        f"What additional inventory carrying costs and staffing overhead were incurred to capture {cohort_name} volume?",
        "How do markdown timings before and after holiday weeks impact overall gross margin elasticity?"
    ]

    dim_disp = format_display_label(dim_col)

    return {
        "available": True,
        "investigation_type": "dimension",
        "target": cohort_name,
        "metric": metric_col,
        "sheet_name": target_sheet["name"],
        "source_file": target_sheet["original_name"],
        "observation": {
            "headline": f"{cohort_name}: Comparative cohort",
            "observed_value": f"{cohort_avg_str} ({cohort_tot_str})",
            "benchmark_value": other_avg_str,
            "variance": f"{diff_pct:+0.1f}% vs {other_cohort_name}",
            "population_count": f"{len(cohort_rows)} records evaluated",
            "reporting_period": f"Comparative Evaluation across {len(df)} total periods"
        },
        "methodology": {
            "formula": f"Mean({cohort_name}) vs Mean({other_cohort_name})",
            "numerator": f"Sum of {metric_col} in {cohort_name} = {cohort_tot_str}",
            "denominator": f"Count of {cohort_name} periods = {len(cohort_rows)} rows",
            "steps": [
                f"Partitioned {len(df)} workspace rows into {len(cohort_rows)} {cohort_name} and {len(other_rows)} {other_cohort_name}.",
                f"Computed arithmetic mean for {cohort_name} ({cohort_avg_str}) vs {other_cohort_name} ({other_avg_str}).",
                f"Determined net variance of {diff_pct:+0.1f}%."
            ]
        },
        "timelines_and_breakdowns": {
            "title": f"{dim_disp} cohort breakdown",
            "items": items
        },
        "source_records": source_records,
        "connected_evidence": [],
        "limitations_and_uncertainty": [
            f"The classification of {dim_col} is based strictly on the recorded values in `{target_sheet['original_name']}`. Extended seasonal promotional run-up or post-event clearance days are not distinguished if outside the binary flag.",
            "Promotional marketing expenditures and catalog circular releases are not provided in the dataset."
        ],
        "practical_hr_questions": questions,
        "practical_questions": questions
    }


def build_department_investigation(
    conn, all_sheets, sheet_records, target_sheet, dept_col, dept_name, metric_col
) -> dict:
    records = sheet_records.get(target_sheet["id"], [])
    df = pd.DataFrame(records)

    dept_rows = df[df[dept_col].astype(str) == dept_name] if dept_col in df.columns else df
    other_rows = df[df[dept_col].astype(str) != dept_name] if dept_col in df.columns else pd.DataFrame()

    num_series = coerce_to_numeric(dept_rows[metric_col]) if metric_col in dept_rows.columns else pd.Series([])
    org_num_series = coerce_to_numeric(df[metric_col]) if metric_col in df.columns else pd.Series([])

    dept_val = round(float(num_series.dropna().mean()), 2) if len(num_series.dropna()) else 0.0
    org_val = round(float(org_num_series.dropna().mean()), 2) if len(org_num_series.dropna()) else 0.0
    diff_pct = round(((dept_val - org_val) / org_val) * 100, 1) if org_val > 0 else 0.0

    is_additive = any(k in str(metric_col).lower() for k in ('overtime', 'absent', 'days', 'hours')) and 'rate' not in str(metric_col).lower()
    total_val = round(float(num_series.dropna().sum()), 2) if is_additive and len(num_series.dropna()) else None

    # Formula explanation
    unit = "hrs" if "hour" in str(metric_col).lower() or "ot" in str(metric_col).lower() else (
        "days" if "day" in str(metric_col).lower() or "absent" in str(metric_col).lower() else "pts"
    )

    calculation = {
        "formula": f"Mean({metric_col}) = ∑(Individual Values) / Department Headcount",
        "numerator": f"Sum of {metric_col} in {dept_name} = {total_val or dept_val * len(dept_rows):.1f} {unit}",
        "denominator": f"Recorded {dept_name} Personnel Count = {len(dept_rows)} staff",
        "steps": [
            f"Filtered {len(df)} total sheet records to {len(dept_rows)} rows matching Department = '{dept_name}'.",
            f"Evaluated {len(num_series.dropna())} non-null numeric values for column '{metric_col}'.",
            f"Calculated group mean of {dept_val} {unit} compared to organization-wide mean of {org_val} {unit} ({diff_pct:+0.1f}% variance)."
        ]
    }

    # Individual breakdown within department
    name_col = next((c for c in df.columns if any(k in str(c).lower() for k in ('name', 'employee'))), None)
    breakdown_items = []
    if name_col and metric_col in dept_rows.columns:
        for _, r in dept_rows.iterrows():
            val = coerce_to_numeric(pd.Series([r[metric_col]])).iloc[0]
            if pd.notna(val):
                breakdown_items.append({
                    "name": str(r[name_col]),
                    "value": round(float(val), 2),
                    "unit": unit
                })
        breakdown_items.sort(key=lambda x: x["value"], reverse=True)

    # Raw source records (clean display)
    source_records = [
        {
            "row_index": r.get("__row_index", idx + 1),
            "sheet_name": target_sheet["name"],
            "file": target_sheet["original_name"],
            "data": {k: clean_val(v) for k, v in r.items() if not k.startswith("__")}
        }
        for idx, r in dept_rows.head(25).iterrows()
    ]

    # Connected evidence from other sheets
    connected_records = find_connected_evidence(conn, all_sheets, sheet_records, dept_rows, target_sheet["id"])

    return {
        "available": True,
        "investigation_type": "department",
        "target": dept_name,
        "metric": metric_col,
        "sheet_name": target_sheet["name"],
        "source_file": target_sheet["original_name"],
        "observation": {
            "headline": f"{dept_name} Department: {metric_col} Benchmark Evaluation",
            "observed_value": f"{dept_val} {unit}" + (f" (Total: {total_val} {unit})" if total_val is not None else ""),
            "benchmark_value": f"{org_val} {unit} (Org Benchmark)",
            "variance": f"{diff_pct:+0.1f}% vs Org Average",
            "population_count": f"{len(dept_rows)} recorded staff",
            "reporting_period": "Current Uploaded Workspace Period"
        },
        "methodology": calculation,
        "timelines_and_breakdowns": {
            "title": f"Staff Breakdown within {dept_name}",
            "items": breakdown_items[:10]
        },
        "source_records": source_records,
        "connected_evidence": connected_records,
        "limitations_and_uncertainty": [
            f"Department staffing reflects {len(dept_rows)} records present in `{target_sheet['original_name']}`. Shift schedules, temporary contract designations, or off-cycle leaves were not recorded in the uploaded data.",
            "Attitudinal sentiment, workload perception, or morale cannot be inferred solely from working hours or absence figures without direct employee survey feedback."
        ],
        "practical_hr_questions": [
            f"Are the observed {metric_col.lower()} levels in {dept_name} driven by planned operational projects or unplanned surge coverage?",
            f"How is workload distributed among the {len(dept_rows)} team members—does a small subset carry the majority of hours?",
            "Have team leads conducted workload alignment reviews to prevent compensatory fatigue?"
        ]
    }
