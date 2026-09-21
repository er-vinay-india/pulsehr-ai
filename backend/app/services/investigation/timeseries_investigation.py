"""Time series and periodic investigation builder."""

import re
import pandas as pd
from ..executive_story import coerce_to_numeric
from ..display_formatters import format_display_label
from .investigation_common import clean_val
from .entity_investigation import build_general_investigation


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
