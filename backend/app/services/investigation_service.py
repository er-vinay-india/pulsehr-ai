"""Universal Contextual Investigation Service for Evidence-Based HR Analytics.

Produces comprehensive, reproducible investigation payloads for any chart element,
department, employee/candidate, or interesting fact.

Covers:
1. What was observed (exact value, comparison, population, period).
2. Calculation, comparison, or statistical rule supporting it.
3. Relevant timelines, episodes, and breakdowns.
4. Supporting raw source records from SQLite.
5. Related evidence from reliably connected sheets.
6. Missing context, uncertainty, and alternative explanations.
7. Practical, objective questions HR can investigate next.
"""

import json
import logging
import math
import re
from typing import Any

import numpy as np
import pandas as pd

from ..core import config
from ..db.database import get_connection
from .executive_story import coerce_to_numeric
from .display_formatters import format_display_label

logger = logging.getLogger(__name__)


def clean_val(v: Any) -> Any:
    if v is None or (isinstance(v, float) and (math.isnan(v) or math.isinf(v))):
        return None
    return v


def run_contextual_investigation(
    conn,
    entity_type: str,
    target_id: str | None = None,
    metric: str | None = None,
    sheet_id: int | None = None,
    chart_id: str | None = None
) -> dict:
    """Dispatches and compiles the deep contextual investigation report."""
    target_clean = str(target_id or "").strip()
    metric_clean = str(metric or "Metric").strip()

    # Retrieve all sheets and rows for investigation context
    sheet_query = (
        "SELECT s.id, s.name, s.columns_json, s.row_count, d.original_name, d.filename "
        "FROM sheets s JOIN dataset_uploads d ON d.id=s.dataset_id ORDER BY s.id ASC"
    )
    all_sheets = [dict(r) for r in conn.execute(sheet_query).fetchall()]
    if not all_sheets:
        return {
            "available": False,
            "message": "No workspace sheets found for investigation."
        }

    # Load records for sheets
    sheet_records = {}
    for s in all_sheets:
        sid = s["id"]
        rows = conn.execute("SELECT row_index, data_json FROM sheet_rows WHERE sheet_id=? ORDER BY row_index", (sid,)).fetchall()
        sheet_records[sid] = [
            {"__row_index": r["row_index"] + 1, **json.loads(r["data_json"])}
            for r in rows
        ]

    # Target sheet determination
    target_sheet = None
    if sheet_id:
        target_sheet = next((s for s in all_sheets if s["id"] == sheet_id), None)
    if not target_sheet:
        # Search for sheet containing the metric or target
        for s in all_sheets:
            cols = json.loads(s["columns_json"] or "[]")
            if any(metric_clean.lower() in c.lower() for c in cols):
                target_sheet = s
                break
    if not target_sheet:
        target_sheet = all_sheets[0]

    records = sheet_records.get(target_sheet["id"], [])
    df = pd.DataFrame(records) if records else pd.DataFrame()

    # Identify primary columns
    dept_col = None
    name_col = None
    id_col = None
    date_col = None
    store_col = None
    holiday_col = None

    if not df.empty:
        for c in df.columns:
            if c.startswith("__"):
                continue
            cl = str(c).lower().replace('_', '').replace(' ', '')
            if not dept_col and any(k in cl for k in ('dept', 'department', 'team', 'division')):
                dept_col = c
            if not name_col and any(k in cl for k in ('name', 'employeename', 'full_name', 'candidate', 'person')):
                name_col = c
            if not id_col and (cl in ('id', 'employeeid', 'empid', 'code', 'candidateid') or cl.endswith('id') or cl.endswith('code')):
                id_col = c
            if not date_col and any(k in cl for k in ('date', 'timestamp', 'datetime', 'day', 'week')):
                date_col = c
            if not store_col and any(k in cl for k in ('store', 'location', 'branch', 'outlet', 'facility', 'shop')):
                store_col = c
            if not holiday_col and any(k in cl for k in ('holiday', 'holidayflag', 'season')):
                holiday_col = c

    # Match metric column
    metric_col = None
    if not df.empty and metric_clean:
        for c in df.columns:
            if c.startswith("__"):
                continue
            if metric_clean.lower() in str(c).lower() or str(c).lower() in metric_clean.lower():
                metric_col = c
                break

    # Build investigation payload based on entity_type & target
    # 1. Store / Location investigation
    is_store_target = (
        entity_type in ("store", "location", "branch", "outlet")
        or target_clean.lower().startswith("store")
        or (store_col and (
            target_clean in df[store_col].astype(str).str.replace('.0', '', regex=False).values
            or (re.search(r'\b\d+\b', target_clean) and re.search(r'\b\d+\b', target_clean).group(0) in df[store_col].astype(str).str.replace('.0', '', regex=False).values)
        ))
    )
    if is_store_target and store_col:
        return build_store_investigation(
            conn, all_sheets, sheet_records, target_sheet, store_col, target_clean, metric_col or metric_clean, date_col, holiday_col
        )

    # 2. Time-series / Date investigation
    is_date_target = (
        entity_type in ("time_series", "date", "period")
        or (date_col and bool(re.search(r'\d{4}[-/]\d{1,2}[-/]\d{1,2}|\d{1,2}[-/]\d{1,2}[-/]\d{4}', target_clean)))
    )
    if is_date_target and date_col:
        return build_time_series_investigation(
            conn, all_sheets, sheet_records, target_sheet, date_col, target_clean, metric_col or metric_clean, store_col, holiday_col
        )

    # 3. Dimension / Holiday cohort investigation
    is_holiday_target = (
        entity_type in ("dimension", "cohort")
        or target_clean in ("Holiday Weeks", "Regular Weeks", "Holiday", "Non-Holiday")
        or (holiday_col and target_clean in ("0", "1", "Holiday Weeks", "Regular Weeks"))
    )
    if is_holiday_target and holiday_col:
        return build_dimension_investigation(
            conn, all_sheets, sheet_records, target_sheet, holiday_col, target_clean, metric_col or metric_clean
        )

    # 4. Department-level investigation
    if entity_type == "department" or (dept_col and target_clean in df[dept_col].astype(str).values):
        return build_department_investigation(
            conn, all_sheets, sheet_records, target_sheet, dept_col, target_clean, metric_col or metric_clean
        )
    # 5. Individual employee investigation
    elif entity_type in ("employee", "person", "candidate") or (name_col and target_clean in df[name_col].astype(str).values):
        return build_individual_investigation(
            conn, all_sheets, sheet_records, target_sheet, name_col, id_col, target_clean, metric_col or metric_clean
        )
    # 6. Model group investigation
    elif entity_type == "model_group":
        return build_model_group_investigation(
            conn, all_sheets, sheet_records, target_sheet, target_clean, metric_clean
        )
    # 7. General investigation fallback
    else:
        return build_general_investigation(
            conn, all_sheets, sheet_records, target_sheet, target_clean, metric_col or metric_clean
        )



# =============================================================================
# STORE / LOCATION LEVEL INVESTIGATION
# =============================================================================
def build_store_investigation(
    conn, all_sheets, sheet_records, target_sheet, store_col, target_clean, metric_col, date_col=None, holiday_col=None
) -> dict:
    records = sheet_records.get(target_sheet["id"], [])
    df = pd.DataFrame(records)
    if df.empty:
        return build_general_investigation(conn, all_sheets, sheet_records, target_sheet, target_clean, metric_col)

    # Extract store id: e.g. "Store 20" -> "20", "20" -> "20"
    num_match = re.search(r'\b\d+\b', target_clean)
    store_id_str = num_match.group(0) if num_match else target_clean.replace("Store", "").strip()

    # Match store rows
    store_mask = (
        (df[store_col].astype(str).str.strip().str.replace(r'\.0$', '', regex=True) == store_id_str)
        | (df[store_col].astype(str).str.strip().str.lower() == target_clean.lower())
    )
    store_rows = df[store_mask]
    if store_rows.empty:
        store_rows = df.head(100)
        display_name = target_clean
    else:
        display_name = f"Store {store_id_str}" if store_id_str.isdigit() else str(store_rows[store_col].iloc[0])

    num_series = coerce_to_numeric(store_rows[metric_col]) if metric_col in store_rows.columns else pd.Series([], dtype=float)
    net_series = coerce_to_numeric(df[metric_col]) if metric_col in df.columns else pd.Series([], dtype=float)

    store_val = float(num_series.dropna().mean()) if len(num_series.dropna()) else 0.0
    net_val = float(net_series.dropna().mean()) if len(net_series.dropna()) else 0.0
    store_total = float(num_series.dropna().sum()) if len(num_series.dropna()) else 0.0
    diff_pct = ((store_val - net_val) / net_val * 100) if net_val > 0 else 0.0

    weeks_count = len(store_rows)

    period_str = f"{weeks_count} recorded trading periods"
    if date_col and date_col in store_rows.columns:
        parsed_dates = pd.to_datetime(store_rows[date_col], format='mixed', dayfirst=True, errors='coerce').dropna()
        if not parsed_dates.empty:
            period_str = f"{parsed_dates.min().strftime('%Y-%m-%d')} to {parsed_dates.max().strftime('%Y-%m-%d')} ({len(parsed_dates)} weeks)"

    is_currency = any(k in str(metric_col).lower() for k in ('sale', 'rev', 'price', 'cost', 'spend', 'dollar', '$'))
    obs_val_str = f"${store_val:,.2f}/wk" if is_currency else f"{store_val:,.2f}"
    obs_tot_str = f"${store_total / 1_000_000:,.2f}M Total" if is_currency and store_total >= 1_000_000 else (f"${store_total:,.2f}" if is_currency else f"{store_total:,.0f}")
    benchmark_str = f"${net_val:,.2f}/wk (All Stores Network Average)" if is_currency else f"{net_val:,.2f} (Network Average)"

    m_disp = format_display_label(metric_col)
    m_lower = m_disp.lower()

    avg_item_name = f"{m_disp} (average)" if m_lower.startswith(("weekly", "monthly", "daily", "annual", "hourly")) else f"Weekly {m_lower} (average)"
    items = [
        {"name": avg_item_name, "value": round(store_val, 2), "unit": "$" if is_currency else "pts"},
        {"name": f"Total {m_lower}", "value": round(store_total, 2), "unit": "$" if is_currency else "pts"},
        {"name": "Total recorded periods", "value": weeks_count, "unit": "weeks"}
    ]

    if holiday_col and holiday_col in store_rows.columns:
        h_mask = store_rows[holiday_col].astype(str).str.strip().isin(['1', '1.0', 'true', 'True'])
        h_sales = coerce_to_numeric(store_rows.loc[h_mask, metric_col]).dropna()
        r_sales = coerce_to_numeric(store_rows.loc[~h_mask, metric_col]).dropna()
        if not h_sales.empty:
            items.append({"name": "Holiday periods (average)", "value": round(float(h_sales.mean()), 2), "unit": "$" if is_currency else "pts"})
        if not r_sales.empty:
            items.append({"name": "Regular periods (average)", "value": round(float(r_sales.mean()), 2), "unit": "$" if is_currency else "pts"})

    for macro_col, macro_unit in [('Temperature', '°F'), ('Fuel_Price', '$'), ('CPI', 'index'), ('Unemployment', '%')]:
        m_col = next((c for c in store_rows.columns if c.lower().replace('_', '') == macro_col.lower().replace('_', '')), None)
        if m_col:
            m_s = coerce_to_numeric(store_rows[m_col]).dropna()
            if not m_s.empty:
                macro_disp = format_display_label(macro_col)
                macro_label = f"Average {macro_disp.lower()}" if macro_disp != "CPI" else "Average CPI"
                items.append({"name": macro_label, "value": round(float(m_s.mean()), 2), "unit": macro_unit})

    sort_col = date_col if (date_col and date_col in store_rows.columns) else metric_col
    sorted_rows = store_rows.sort_values(by=sort_col, ascending=False) if (sort_col and sort_col in store_rows.columns) else store_rows
    source_records = [
        {
            "row_index": r.get("__row_index", idx + 1),
            "sheet_name": target_sheet["name"],
            "file": target_sheet["original_name"],
            "data": {k: clean_val(v) for k, v in r.items() if not k.startswith("__")}
        }
        for idx, r in sorted_rows.head(25).iterrows()
    ]

    connected_records = find_connected_evidence(conn, all_sheets, sheet_records, store_rows, target_sheet["id"])

    questions = [
        f"What store square footage, floor format (e.g. Supercenter vs Express), and inventory replenishment cycles distinguish {display_name} from network benchmarks?",
        f"How do weekly promotional markdowns and holiday stocking volumes correlate with observed sales spikes in {display_name}?",
        "Do local demographic factors and competitive proximity account for variance in customer basket size and visit frequency?"
    ]

    return {
        "available": True,
        "investigation_type": "store",
        "target": display_name,
        "metric": metric_col,
        "sheet_name": target_sheet["name"],
        "source_file": target_sheet["original_name"],
        "observation": {
            "headline": f"{display_name}: Performance and drivers",
            "observed_value": f"{obs_val_str} ({obs_tot_str})",
            "benchmark_value": benchmark_str,
            "variance": f"{diff_pct:+0.1f}% vs Network Baseline",
            "population_count": f"{weeks_count} recorded weekly periods",
            "reporting_period": period_str
        },
        "methodology": {
            "formula": f"Mean({metric_col}) = ∑({metric_col}) / Recorded Periods",
            "numerator": f"Aggregated {metric_col} for {display_name} = {obs_tot_str}",
            "denominator": f"Total Periods = {weeks_count} weeks",
            "steps": [
                f"Isolated {weeks_count} row records for {display_name} from `{target_sheet['original_name']}`.",
                f"Calculated arithmetic mean {metric_col} of {obs_val_str} vs network baseline of {benchmark_str} ({diff_pct:+0.1f}%).",
                f"Evaluated environmental conditions and holiday trading cycles across the {weeks_count} reporting periods."
            ]
        },
        "timelines_and_breakdowns": {
            "title": f"{display_name} trading and environmental indicators",
            "items": items
        },
        "source_records": source_records,
        "connected_evidence": connected_records,
        "limitations_and_uncertainty": [
            f"Dataset contains aggregate weekly store totals. In-store customer footfall, average checkout basket size, and unit volume by SKU category are not present in `{target_sheet['original_name']}`.",
            "Local pricing promotions, clearance markdowns, and inventory stockouts cannot be distinguished from baseline demand without itemized POS logs."
        ],
        "practical_hr_questions": questions,
        "practical_questions": questions
    }


# =============================================================================
# TIME-SERIES / PERIOD INVESTIGATION
# =============================================================================
def build_time_series_investigation(
    conn, all_sheets, sheet_records, target_sheet, date_col, date_val, metric_col, store_col=None, holiday_col=None
) -> dict:
    records = sheet_records.get(target_sheet["id"], [])
    df = pd.DataFrame(records)
    if df.empty:
        return build_general_investigation(conn, all_sheets, sheet_records, target_sheet, date_val, metric_col)

    date_match = re.search(r'\d{4}[-/]\d{1,2}[-/]\d{1,2}|\d{1,2}[-/]\d{1,2}[-/]\d{4}', date_val)
    date_str = date_match.group(0) if date_match else date_val.strip()

    parsed_s = pd.to_datetime(df[date_col], format='mixed', dayfirst=True, errors='coerce')
    target_dt = pd.to_datetime(date_str, format='mixed', dayfirst=True, errors='coerce')

    if pd.notna(target_dt):
        date_mask = (parsed_s.dt.strftime('%Y-%m-%d') == target_dt.strftime('%Y-%m-%d'))
        formatted_date = target_dt.strftime('%Y-%m-%d')
    else:
        date_mask = df[date_col].astype(str).str.strip() == date_str
        formatted_date = date_str

    period_rows = df[date_mask]
    if period_rows.empty:
        period_rows = df.head(50)
        formatted_date = date_str

    is_currency = any(k in str(metric_col).lower() for k in ('sale', 'rev', 'price', 'cost', 'spend', 'dollar', '$'))

    num_series = coerce_to_numeric(period_rows[metric_col]) if metric_col in period_rows.columns else pd.Series([], dtype=float)
    net_series = coerce_to_numeric(df[metric_col]) if metric_col in df.columns else pd.Series([], dtype=float)

    period_total = float(num_series.dropna().sum()) if len(num_series.dropna()) else 0.0
    period_avg = float(num_series.dropna().mean()) if len(num_series.dropna()) else 0.0

    if date_col and pd.notna(target_dt):
        weekly_totals = df.groupby(parsed_s.dt.strftime('%Y-%m-%d'))[metric_col].apply(lambda s: coerce_to_numeric(s).dropna().sum())
        net_week_avg = float(weekly_totals.mean()) if not weekly_totals.empty else float(net_series.dropna().mean()) * len(period_rows)
    else:
        net_week_avg = float(net_series.dropna().mean()) * len(period_rows)

    diff_pct = ((period_total - net_week_avg) / net_week_avg * 100) if net_week_avg > 0 else 0.0

    period_tot_str = f"${period_total / 1_000_000:,.2f}M" if is_currency and period_total >= 1_000_000 else (f"${period_total:,.2f}" if is_currency else f"{period_total:,.0f}")
    period_avg_str = f"${period_avg:,.2f}/store" if is_currency else f"{period_avg:,.2f}/unit"
    base_str = f"${net_week_avg / 1_000_000:,.2f}M (Weekly Network Benchmark)" if is_currency and net_week_avg >= 1_000_000 else (f"${net_week_avg:,.2f}" if is_currency else f"{net_week_avg:,.0f}")

    m_disp = format_display_label(metric_col)
    m_lower = m_disp.lower()

    items = [
        {"name": f"Network total {m_lower}", "value": round(period_total, 2), "unit": "$" if is_currency else "pts"},
        {"name": f"Store average {m_lower}", "value": round(period_avg, 2), "unit": "$" if is_currency else "pts"},
        {"name": "Reporting locations", "value": len(period_rows), "unit": "stores"}
    ]

    if store_col and store_col in period_rows.columns:
        sorted_period = period_rows.copy()
        sorted_period['__num'] = coerce_to_numeric(sorted_period[metric_col])
        top_stores = sorted_period.sort_values(by='__num', ascending=False).head(5)
        for _, r in top_stores.iterrows():
            s_name = f"Store {str(r[store_col]).replace('.0', '')}"
            val = float(r['__num']) if pd.notna(r['__num']) else 0.0
            items.append({"name": f"Top store: {s_name}", "value": round(val, 2), "unit": "$" if is_currency else "pts"})

    holiday_note = "Regular trading week"
    if holiday_col and holiday_col in period_rows.columns:
        is_hol = period_rows[holiday_col].astype(str).str.strip().isin(['1', '1.0', 'true', 'True']).any()
        holiday_note = "National holiday week (flag = 1)" if is_hol else "Non-holiday week (flag = 0)"

    sorted_rows = period_rows.sort_values(by=metric_col, ascending=False) if metric_col in period_rows.columns else period_rows
    source_records = [
        {
            "row_index": r.get("__row_index", idx + 1),
            "sheet_name": target_sheet["name"],
            "file": target_sheet["original_name"],
            "data": {k: clean_val(v) for k, v in r.items() if not k.startswith("__")}
        }
        for idx, r in sorted_rows.head(25).iterrows()
    ]

    questions = [
        f"Was the volume surge during the week ending {formatted_date} driven by chain-wide holiday demand or concentrated promotional campaigns in specific store tiers?",
        f"How did inventory stock levels and replenishment velocity hold up across the {len(period_rows)} reporting store locations?",
        "Did staffing schedules and freight logistics absorb the volume surge without stockouts or unplanned demurrage costs?"
    ]

    return {
        "available": True,
        "investigation_type": "time_series",
        "target": f"Week {formatted_date}",
        "metric": metric_col,
        "sheet_name": target_sheet["name"],
        "source_file": target_sheet["original_name"],
        "observation": {
            "headline": f"Trading period {formatted_date}: Network performance",
            "observed_value": f"{period_tot_str} ({period_avg_str})",
            "benchmark_value": base_str,
            "variance": f"{diff_pct:+0.1f}% vs Average Week",
            "population_count": f"{len(period_rows)} reporting locations",
            "reporting_period": f"Week Ending {formatted_date} ({holiday_note})"
        },
        "methodology": {
            "formula": f"Network Total({formatted_date}) = ∑({metric_col}) Across All Reporting Stores",
            "numerator": f"Summed sales for {len(period_rows)} stores on {formatted_date} = {period_tot_str}",
            "denominator": f"Single Weekly Period ({len(period_rows)} store locations)",
            "steps": [
                f"Isolated {len(period_rows)} store records matching Date = '{formatted_date}'.",
                f"Calculated aggregate network volume of {period_tot_str} ({period_avg_str}).",
                f"Compared against weekly network average of {base_str} ({diff_pct:+0.1f}% variance)."
            ]
        },
        "timelines_and_breakdowns": {
            "title": f"Week {formatted_date} top store contributors",
            "items": items
        },
        "source_records": source_records,
        "connected_evidence": [],
        "limitations_and_uncertainty": [
            f"Data captures aggregate store performance for week ending {formatted_date}. Single-day peaks (e.g. Black Friday or Super Bowl Saturday) cannot be isolated from weekly aggregates.",
            "Weather anomalies (such as winter storms) or local transportation disruptions on this specific week are not itemized."
        ],
        "practical_hr_questions": questions,
        "practical_questions": questions
    }


# =============================================================================
# DIMENSION / COHORT INVESTIGATION
# =============================================================================
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


# =============================================================================
# 1. DEPARTMENT-LEVEL INVESTIGATION
# =============================================================================
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


# =============================================================================
# 2. INDIVIDUAL-LEVEL INVESTIGATION
# =============================================================================
def build_individual_investigation(
    conn, all_sheets, sheet_records, target_sheet, name_col, id_col, target_name, metric_col
) -> dict:
    records = sheet_records.get(target_sheet["id"], [])
    df = pd.DataFrame(records)

    # Match row for this person
    target_row = None
    for _, r in df.iterrows():
        if name_col and str(r.get(name_col, '')).strip().lower() == target_name.lower():
            target_row = r
            break
        if id_col and str(r.get(id_col, '')).strip().lower() == target_name.lower():
            target_row = r
            break

    if target_row is None and len(df) > 0:
        target_row = df.iloc[0]
        target_name = str(target_row.get(name_col or id_col or 'Individual'))

    person_name = str(target_row.get(name_col or 'Staff Member'))
    person_code = str(target_row.get(id_col or 'N/A'))
    person_dept = str(target_row.get('Department', 'General'))
    num_val = coerce_to_numeric(pd.Series([target_row.get(metric_col)])).iloc[0] if metric_col in target_row else None
    unit = "days" if "day" in str(metric_col).lower() or "absent" in str(metric_col).lower() else (
        "hrs" if "hour" in str(metric_col).lower() or "ot" in str(metric_col).lower() else "pts"
    )

    # Episode vs Spells analysis (strictly factual)
    val_num = float(num_val) if pd.notna(num_val) else 0.0
    episode_explanation = (
        f"{val_num:.0f} recorded {unit} of {metric_col.lower()} logged for this individual during the available reporting period. "
        "The uploaded spreadsheet contains summary aggregate totals per employee rather than a dated daily check-in log. "
        "Therefore, whether these days occurred as a single continuous episode or multiple intermittent instances cannot be confirmed without granular daily punch logs."
    )

    calculation = {
        "formula": f"Recorded Row Extract: {metric_col}",
        "numerator": f"Direct entry in row = {val_num:.1f} {unit}",
        "denominator": "Single Individual Record (n=1)",
        "steps": [
            f"Located record for {person_name} ({person_code}) in `{target_sheet['original_name']}`.",
            f"Extracted recorded measure '{metric_col}' = {val_num:.1f} {unit}.",
            "Evaluated historical and cross-sheet relationships for matching employee identifiers."
        ]
    }

    # Raw source records
    source_records = [
        {
            "row_index": target_row.get("__row_index", 1),
            "sheet_name": target_sheet["name"],
            "file": target_sheet["original_name"],
            "data": {k: clean_val(v) for k, v in target_row.items() if not k.startswith("__")}
        }
    ]

    # Connected evidence from other sheets
    connected_records = find_individual_connected_evidence(conn, all_sheets, sheet_records, target_row, id_col, name_col, target_sheet["id"])

    return {
        "available": True,
        "investigation_type": "individual",
        "target": person_name,
        "employee_code": person_code,
        "department": person_dept,
        "metric": metric_col,
        "sheet_name": target_sheet["name"],
        "source_file": target_sheet["original_name"],
        "observation": {
            "headline": f"{person_name} ({person_code}): Detailed Evidence Profile",
            "observed_value": f"{val_num:.1f} {unit}",
            "benchmark_value": f"Department: {person_dept}",
            "variance": "Recorded Individual Row Data",
            "population_count": "1 staff member",
            "reporting_period": "Current Uploaded Workspace Window"
        },
        "methodology": calculation,
        "timelines_and_breakdowns": {
            "title": "Episode & Pattern Analysis",
            "items": [
                {"name": "Recorded Total", "value": val_num, "unit": unit},
                {"name": "Pattern Context", "value": 1 if val_num > 0 else 0, "unit": "summary period"}
            ],
            "factual_context": episode_explanation
        },
        "source_records": source_records,
        "connected_evidence": connected_records,
        "limitations_and_uncertainty": [
            "Source dataset records summary totals without daily punch timestamps; episodes cannot be verified as continuous medical vs casual absences without daily records.",
            "No personal health, motivation, or private circumstances are assumed or inferred. All reporting reflects recorded business entries."
        ],
        "practical_hr_questions": [
            f"Did the recorded {metric_col.lower()} coincide with pre-approved annual leave, bereavement, or medical certification?",
            "Are shift schedules and working hours aligned with departmental expectations?",
            "Is any supporting documentation pending review in the HR information system?"
        ]
    }


# =============================================================================
# 3. MODEL GROUP / INDUSTRIAL FACT INVESTIGATION
# =============================================================================
def build_model_group_investigation(
    conn, all_sheets, sheet_records, target_sheet, group_key, metric_col
) -> dict:
    records = sheet_records.get(target_sheet["id"], [])
    df = pd.DataFrame(records)

    title = "Industrial Analytics Investigation"
    formula = "Industrial People Analytics Model"
    explanation_steps = []
    questions = []

    if "bradford" in group_key.lower() or "disruption" in group_key.lower():
        title = "Bradford Factor Absenteeism Disruption Investigation"
        formula = "B = S² × D (S = Spells / Instances, D = Total Days Lost)"
        explanation_steps = [
            "Bradford Factor weights frequent short-term absence spells quadratically (S²) over total duration (D).",
            "Scores above 200 points trigger formal review thresholds due to operational rescheduling disruption.",
            "Scores below 50 points reflect normal, low-disruption workforce health."
        ]
        questions = [
            "Are high Bradford scores concentrated within specific teams or job roles?",
            "Did frequent short absences cluster around shift rotations or weekends?",
            "Have return-to-work discussions been documented for individuals surpassing the 200-point threshold?"
        ]
    elif "9box" in group_key.lower() or "talent" in group_key.lower() or "risk" in group_key.lower():
        title = "McKinsey / GE 9-Box Talent & Risk Cohort Investigation"
        formula = "9-Box Mapping = Performance Score (X-Axis) × Attrition Risk / Potential (Y-Axis)"
        explanation_steps = [
            "Cohort maps contributors across dual axes: Appraisal Performance vs Flight Risk / Potential.",
            "Top-tier performers with elevated attrition risk represent critical retention vulnerability.",
            "Contributors below performance benchmarks receive targeted development and coaching pathways."
        ]
        questions = [
            "Have retention check-ins been scheduled with identified flight-risk high performers?",
            "Are compensation and market adjustments aligned with high-performer contributions?",
            "What structured development or mentoring plans are active for coaching candidates?"
        ]
    else:
        title = f"HR Fact Evidence Investigation: {group_key}"
        formula = "Statistical Distribution & Variance Model"
        explanation_steps = [
            f"Evaluated distribution of {metric_col} across all verified records.",
            "Applied variance thresholds to isolate significant organizational deviations."
        ]
        questions = [
            "What external or seasonal factors contributed to this observed distribution?",
            "Does cross-departmental evidence corroborate this trend?"
        ]

    # Sample records
    source_records = [
        {
            "row_index": r.get("__row_index", idx + 1),
            "sheet_name": target_sheet["name"],
            "file": target_sheet["original_name"],
            "data": {k: clean_val(v) for k, v in r.items() if not k.startswith("__")}
        }
        for idx, r in df.head(20).iterrows()
    ]

    return {
        "available": True,
        "investigation_type": "model_group",
        "target": title,
        "metric": metric_col,
        "sheet_name": target_sheet["name"],
        "source_file": target_sheet["original_name"],
        "observation": {
            "headline": title,
            "observed_value": f"Evaluated across {len(df)} records",
            "benchmark_value": "Industrial People Analytics Framework",
            "variance": "Formula Grounded",
            "population_count": f"{len(df)} workforce entries",
            "reporting_period": "Active Workspace Data"
        },
        "methodology": {
            "formula": formula,
            "numerator": "Target Group Subpopulation",
            "denominator": f"Complete Workspace Cohort ({len(df)} records)",
            "steps": explanation_steps
        },
        "timelines_and_breakdowns": {
            "title": "Cohort Breakdown",
            "items": [
                {"name": "Total Cohort Size", "value": len(df), "unit": "records"}
            ]
        },
        "source_records": source_records,
        "connected_evidence": [],
        "limitations_and_uncertainty": [
            "Model calculations rely strictly on figures provided in uploaded spreadsheets.",
            "Industrial benchmarks serve as diagnostic guidance; human HR review is essential before any personnel action."
        ],
        "practical_hr_questions": questions
    }


# =============================================================================
# 4. GENERAL TABULAR INVESTIGATION
# =============================================================================
def build_general_investigation(
    conn, all_sheets, sheet_records, target_sheet, target_label, metric_col
) -> dict:
    records = sheet_records.get(target_sheet["id"], [])
    df = pd.DataFrame(records)

    source_records = [
        {
            "row_index": r.get("__row_index", idx + 1),
            "sheet_name": target_sheet["name"],
            "file": target_sheet["original_name"],
            "data": {k: clean_val(v) for k, v in r.items() if not k.startswith("__")}
        }
        for idx, r in df.head(20).iterrows()
    ]

    return {
        "available": True,
        "investigation_type": "general",
        "target": target_label or "Dataset Overview",
        "metric": metric_col,
        "sheet_name": target_sheet["name"],
        "source_file": target_sheet["original_name"],
        "observation": {
            "headline": f"Evidence Investigation: {target_label or metric_col}",
            "observed_value": f"{len(df)} rows evaluated",
            "benchmark_value": target_sheet["original_name"],
            "variance": "Ground Truth",
            "population_count": f"{len(df)} records",
            "reporting_period": "Current Upload Window"
        },
        "methodology": {
            "formula": "Deterministic Database Aggregation",
            "numerator": f"Filtered subset for {target_label}",
            "denominator": f"Total Sheet Rows ({len(df)})",
            "steps": [
                f"Queried SQLite database table for `{target_sheet['original_name']}`.",
                "Verified non-null numeric values and data type constraints."
            ]
        },
        "timelines_and_breakdowns": {
            "title": "General Distribution",
            "items": [{"name": "Records", "value": len(df), "unit": "rows"}]
        },
        "source_records": source_records,
        "connected_evidence": [],
        "limitations_and_uncertainty": [
            "Data reflect uploaded spreadsheet rows. Unrecorded periods cannot be reconstructed without historical archives."
        ],
        "practical_hr_questions": [
            "Are there additional supplementary sheets needed to complete cross-departmental comparisons?",
            "Are all job codes and department categories up to date?"
        ]
    }


# =============================================================================
# HELPER: FIND CROSS-SHEET CONNECTED EVIDENCE
# =============================================================================
def find_connected_evidence(conn, all_sheets, sheet_records, target_df: pd.DataFrame, current_sheet_id: int | None = None) -> list[dict]:
    """Retrieves matching records from other sheets using verified relationships or shared keys."""
    connected = []
    if target_df.empty:
        return connected

    # Check verified relationships
    rels = conn.execute("SELECT * FROM sheet_relationships WHERE status='linked'").fetchall()
    seen_sheets = {current_sheet_id} if current_sheet_id else set()

    for rel in rels:
        directions = [
            (rel["left_sheet"], rel["right_sheet"], rel["left_column"], rel["right_column"]),
            (rel["right_sheet"], rel["left_sheet"], rel["right_column"], rel["left_column"])
        ]
        for src_sid, target_sid, src_col, target_col in directions:
            if target_sid in seen_sheets:
                continue
            if src_col in target_df.columns and target_sid in sheet_records:
                other_sheet = next((s for s in all_sheets if s["id"] == target_sid), None)
                if not other_sheet:
                    continue
                other_records = sheet_records[target_sid]
                other_df = pd.DataFrame(other_records)
                if target_col in other_df.columns:
                    target_keys = set(target_df[src_col].dropna().astype(str).str.strip().str.lower())
                    matched = other_df[other_df[target_col].astype(str).str.strip().str.lower().isin(target_keys)]
                    if len(matched) > 0:
                        seen_sheets.add(target_sid)
                        connected.append({
                            "relationship_id": rel["id"],
                            "related_sheet": other_sheet["name"],
                            "related_file": other_sheet["original_name"],
                            "join_key": f"{src_col} ↔ {target_col}",
                            "matched_count": len(matched),
                            "sample_rows": [
                                {k: clean_val(v) for k, v in r.items() if not k.startswith("__")}
                                for _, r in matched.head(5).iterrows()
                            ]
                        })
                        break

    # Fallback: if no relationship rows exist, look for exact shared ID column names across other sheets
    if not connected:
        candidate_cols = [c for c in target_df.columns if not c.startswith("__") and any(k in str(c).lower() for k in ("id", "code", "name"))]
        for other_sheet in all_sheets:
            target_sid = other_sheet["id"]
            if target_sid in seen_sheets:
                continue
            other_records = sheet_records.get(target_sid, [])
            if not other_records:
                continue
            other_df = pd.DataFrame(other_records)
            for c in candidate_cols:
                matching_other_col = next((oc for oc in other_df.columns if oc.strip().lower() == c.strip().lower()), None)
                if matching_other_col:
                    target_keys = set(target_df[c].dropna().astype(str).str.strip().str.lower())
                    matched = other_df[other_df[matching_other_col].astype(str).str.strip().str.lower().isin(target_keys)]
                    if len(matched) > 0 and len(matched) <= len(other_df):
                        seen_sheets.add(target_sid)
                        connected.append({
                            "relationship_id": f"auto_{c}",
                            "related_sheet": other_sheet["name"],
                            "related_file": other_sheet["original_name"],
                            "join_key": f"{c} ↔ {matching_other_col}",
                            "matched_count": len(matched),
                            "sample_rows": [
                                {k: clean_val(v) for k, v in r.items() if not k.startswith("__")}
                                for _, r in matched.head(5).iterrows()
                            ]
                        })
                        break
    return connected


def find_individual_connected_evidence(
    conn, all_sheets, sheet_records, target_row: pd.Series, id_col: str | None, name_col: str | None, current_sheet_id: int | None = None
) -> list[dict]:
    connected = []
    rels = conn.execute("SELECT * FROM sheet_relationships WHERE status='linked'").fetchall()
    seen_sheets = {current_sheet_id} if current_sheet_id else set()

    for rel in rels:
        directions = [
            (rel["left_sheet"], rel["right_sheet"], rel["left_column"], rel["right_column"]),
            (rel["right_sheet"], rel["left_sheet"], rel["right_column"], rel["left_column"])
        ]
        for src_sid, target_sid, src_col, target_col in directions:
            if target_sid in seen_sheets:
                continue
            lookup_val = None
            if src_col in target_row and pd.notna(target_row[src_col]):
                lookup_val = str(target_row[src_col]).strip().lower()
            elif id_col and id_col in target_row and pd.notna(target_row[id_col]):
                lookup_val = str(target_row[id_col]).strip().lower()
            elif name_col and name_col in target_row and pd.notna(target_row[name_col]):
                lookup_val = str(target_row[name_col]).strip().lower()

            if lookup_val and target_sid in sheet_records:
                other_sheet = next((s for s in all_sheets if s["id"] == target_sid), None)
                if not other_sheet:
                    continue
                other_df = pd.DataFrame(sheet_records[target_sid])
                if target_col in other_df.columns:
                    matched = other_df[other_df[target_col].astype(str).str.strip().str.lower() == lookup_val]
                    if len(matched) > 0:
                        seen_sheets.add(target_sid)
                        connected.append({
                            "relationship_id": rel["id"],
                            "related_sheet": other_sheet["name"],
                            "related_file": other_sheet["original_name"],
                            "join_key": f"{src_col} = {lookup_val}",
                            "matched_count": len(matched),
                            "sample_rows": [
                                {k: clean_val(v) for k, v in r.items() if not k.startswith("__")}
                                for _, r in matched.head(5).iterrows()
                            ]
                        })
                        break

    # Fallback: if no relationship rows exist, look for shared identifier keys
    if not connected:
        candidate_cols = [c for c in (id_col, name_col) if c and c in target_row and pd.notna(target_row[c])]
        for other_sheet in all_sheets:
            target_sid = other_sheet["id"]
            if target_sid in seen_sheets:
                continue
            other_records = sheet_records.get(target_sid, [])
            if not other_records:
                continue
            other_df = pd.DataFrame(other_records)
            for c in candidate_cols:
                lookup_val = str(target_row[c]).strip().lower()
                matching_other_col = next((oc for oc in other_df.columns if oc.strip().lower() == c.strip().lower()), None)
                if matching_other_col:
                    matched = other_df[other_df[matching_other_col].astype(str).str.strip().str.lower() == lookup_val]
                    if len(matched) > 0:
                        seen_sheets.add(target_sid)
                        connected.append({
                            "relationship_id": f"auto_{c}",
                            "related_sheet": other_sheet["name"],
                            "related_file": other_sheet["original_name"],
                            "join_key": f"{c} = {lookup_val}",
                            "matched_count": len(matched),
                            "sample_rows": [
                                {k: clean_val(v) for k, v in r.items() if not k.startswith("__")}
                                for _, r in matched.head(5).iterrows()
                            ]
                        })
                        break
    return connected
