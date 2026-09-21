"""Chart plan builders for dynamic analytical visualizations."""

from typing import Any
import pandas as pd

from ..display_formatters import format_display_label, generate_analytical_title


def build_bar_chart_plans(
    df: pd.DataFrame,
    n_rows: int,
    primary_cat: str | None,
    sorted_numeric: list[tuple[str, dict[str, Any]]],
    original_file: str,
) -> list[dict[str, Any]]:
    """Builds ranking and group comparison bar chart plans."""
    plans = []
    if not (primary_cat and sorted_numeric):
        return plans

    for num_col, num_meta in sorted_numeric[:2]:
        c_name = num_meta["clean_col"]
        is_additive = num_meta["is_additive"]
        unit = num_meta["unit"]

        is_sales_metric = any(k in num_col.lower() for k in ('sales', 'revenue', 'volume'))

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
            overall_mean = round(float(df[c_name].mean()), 2) if not df[c_name].empty else 0.0
            overall_total = round(float(df[c_name].sum()), 2) if not df[c_name].empty else 0.0
            spread_ratio = round(bars[0]["value"] / max(bars[-1]["value"], 0.01), 2) if bars[-1]["value"] > 0 else 1.0

            chart_title, chart_sub = generate_analytical_title(
                calc_type=calc_type,
                metric_col=num_col,
                group_col=primary_cat,
                total_count=len(bars)
            )

            ranking_basis_text = f"{format_display_label(measure_title)} (high to low)"

            plans.append({
                "chart_type": "bar",
                "plan_id": f"bar_{num_col}_{primary_cat}",
                "title": chart_title,
                "subtitle": chart_sub,
                "measured_metric": num_col,
                "metric_label": format_display_label(num_col),
                "category_label": format_display_label(primary_cat),
                "unit": unit,
                "aggregation_rule": calc_type,
                "category_col": primary_cat,
                "metric_col": num_col,
                "bars": bars,
                "population": f"{n_rows} source records across {len(bars)} {format_display_label(primary_cat).lower()} groups",
                "source_sheets": [original_file],
                "coverage_pct": round((num_meta['valid_count'] / max(1, n_rows)) * 100, 1),
                "missing_records": num_meta['missing_count'],
                "is_high_cardinality": len(bars) > 10,
                "overall_mean": overall_mean,
                "overall_total": overall_total,
                "total_categories": len(bars),
                "ranking_basis": ranking_basis_text,
                "spread_ratio": spread_ratio
            })

    return plans


def build_flag_comparison_plans(
    df: pd.DataFrame,
    n_rows: int,
    categorical_cols: dict[str, dict[str, Any]],
    primary_cat: str | None,
    sorted_numeric: list[tuple[str, dict[str, Any]]],
    original_file: str,
) -> list[dict[str, Any]]:
    """Builds segment and binary flag comparison bar chart plans."""
    plans = []
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
                comp_title, comp_sub = generate_analytical_title(
                    calc_type="Arithmetic Mean",
                    metric_col=best_num_col,
                    group_col=cat_col,
                    comparison_type="binary_flag"
                )
                plans.append({
                    "chart_type": "bar",
                    "plan_id": f"bar_compare_{cat_col}",
                    "title": comp_title,
                    "subtitle": comp_sub,
                    "measured_metric": best_num_col,
                    "metric_label": format_display_label(best_num_col),
                    "category_label": format_display_label(cat_col),
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

    return plans


def build_donut_chart_plans(
    df: pd.DataFrame,
    n_rows: int,
    categorical_cols: dict[str, dict[str, Any]],
    primary_cat: str | None,
    original_file: str,
    max_plans: int = 4,
) -> list[dict[str, Any]]:
    """Builds donut / composition chart plans for categorical dimensions."""
    plans = []
    palette = ['#10b981', '#6366f1', '#06b6d4', '#f59e0b', '#ec4899', '#8b5cf6', '#14b8a6']

    for cat_col, cat_meta in categorical_cols.items():
        if 2 <= cat_meta["distinct_count"] <= 7 and cat_col != primary_cat:
            vc = df[cat_col].value_counts()
            tot = int(vc.sum())
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
            donut_title, donut_sub = generate_analytical_title(
                calc_type="Distribution",
                metric_col=cat_col,
                group_col=cat_col,
                comparison_type="donut",
                total_count=tot
            )
            plans.append({
                "chart_type": "donut",
                "plan_id": f"donut_{cat_col}",
                "title": donut_title,
                "subtitle": donut_sub,
                "measured_metric": f"{format_display_label(cat_col)} share",
                "metric_label": format_display_label(cat_col),
                "category_label": format_display_label(cat_col),
                "unit": "periods & %",
                "category_col": cat_col,
                "total_population": tot,
                "slices": slices,
                "source_sheets": [original_file],
                "coverage_pct": 100.0,
                "missing_records": n_rows - tot
            })
            if len(plans) >= max_plans:
                break

    return plans


def build_line_chart_plans(
    df: pd.DataFrame,
    n_rows: int,
    date_cols: list[str],
    sorted_numeric: list[tuple[str, dict[str, Any]]],
    original_file: str,
) -> list[dict[str, Any]]:
    """Builds time-series trend line chart plans."""
    plans = []
    if not (date_cols and sorted_numeric):
        return plans

    d_col = date_cols[0]
    date_series = df[f'__date_{d_col}'].dropna()
    if len(date_series) < 5:
        return plans

    sorted_df = df.sort_values(by=f'__date_{d_col}').copy()
    sorted_df['__date_str'] = sorted_df[f'__date_{d_col}'].dt.strftime('%Y-%m-%d')

    for num_col, num_meta in sorted_numeric[:2]:
        c_name = num_meta['clean_col']
        unit = num_meta['unit']
        is_additive = num_meta['is_additive']

        if is_additive:
            time_grp = sorted_df.groupby('__date_str')[c_name].sum().reset_index()
        else:
            time_grp = sorted_df.groupby('__date_str')[c_name].mean().reset_index()

        points = [
            {"period": str(r['__date_str']), "value": round(float(r[c_name]), 2)}
            for _, r in time_grp.iterrows()
            if pd.notna(r[c_name])
        ]

        if len(points) >= 5:
            available_years = sorted(list({p['period'][:4] for p in points if len(p['period']) >= 4 and p['period'][:4].isdigit()}))
            line_title, line_sub = generate_analytical_title(
                calc_type="Total" if is_additive else "Average",
                metric_col=num_col,
                group_col=d_col,
                comparison_type="time_series",
                total_count=len(points)
            )
            plans.append({
                "chart_type": "line",
                "plan_id": f"line_{num_col}_{d_col}",
                "title": line_title,
                "subtitle": line_sub,
                "measured_metric": num_col,
                "metric_label": format_display_label(num_col),
                "category_label": format_display_label(d_col),
                "unit": unit,
                "date_col": d_col,
                "metric_col": num_col,
                "points": points,
                "population": f"{n_rows} records aggregated across {len(points)} time periods",
                "source_sheets": [original_file],
                "coverage_pct": round((num_meta['valid_count'] / max(1, n_rows)) * 100, 1),
                "missing_records": num_meta['missing_count'],
                "total_periods": len(points),
                "period_min_date": points[0]['period'],
                "period_max_date": points[-1]['period'],
                "available_years": available_years
            })

    return plans
