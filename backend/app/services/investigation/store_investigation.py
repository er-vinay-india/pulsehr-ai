"""Store and location-level investigation builder."""

import re
import pandas as pd
from ..executive_story import coerce_to_numeric
from ..display_formatters import format_display_label
from .investigation_common import clean_val, find_connected_evidence
from .entity_investigation import build_general_investigation


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
