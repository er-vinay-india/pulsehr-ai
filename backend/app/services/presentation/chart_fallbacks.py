"""Fallback synthesis routines for presentation charts when dashboard charts are unavailable."""

import math
from typing import Any
import pandas as pd

from ..display_formatters import format_display_label
from ..time_series_forecast import infer_measure_unit


def synthesize_fallback_line_chart(sheet_candidates: list[dict[str, Any]]) -> dict[str, Any] | None:
    """Synthesizes a chronological trend line chart from raw sheet columns."""
    for sc in sheet_candidates:
        records = sc["records"]
        cols = sc["columns"]
        if not records:
            continue

        # Multi-grain temporal extraction (supports long date columns and wide-format sequential periods)
        try:
            from ..analytics.temporal_categorical_engine import extract_multi_grain_temporal_insights
            temp_res = extract_multi_grain_temporal_insights(pd.DataFrame(records), cols)
            if temp_res.get("has_temporal_data"):
                weekly_tl = temp_res.get("weekly", {}).get("timeline", [])
                monthly_tl = temp_res.get("monthly", {}).get("timeline", [])
                tl_series = temp_res.get("timeline_series", [])

                if weekly_tl and len(weekly_tl) >= 2:
                    active_tl = weekly_tl
                    period_type = "Weekly"
                    cats = [t["period_label"] for t in active_tl]
                    vals = [round(float(t["mean"]), 2) for t in active_tl]
                elif monthly_tl and len(monthly_tl) >= 2:
                    active_tl = monthly_tl
                    period_type = "Monthly"
                    cats = [t["period_label"] for t in active_tl]
                    vals = [round(float(t["mean"]), 2) for t in active_tl]
                elif tl_series and len(tl_series) >= 2:
                    active_tl = tl_series
                    period_type = "Observation Cycle"
                    cats = [t["period"] for t in active_tl]
                    vals = [round(float(t["value"]), 2) for t in active_tl]
                else:
                    active_tl = []

                if active_tl and len(cats) == len(vals) and len(cats) >= 2:
                    u = temp_res.get("unit", "units")
                    meas_name = temp_res.get("primary_measure", "Metric")
                    meas_label = format_display_label(meas_name)
                    val_mean = round(sum(vals) / len(vals), 2)
                    avg_wow = temp_res.get("weekly", {}).get("avg_wow_velocity", 0.0)
                    wow_note = f" (Avg WoW Momentum: {avg_wow:+.1f}%)" if avg_wow else ""

                    return {
                        "chart_type": "line",
                        "title": f"{meas_label} Multi-Grain Trajectory",
                        "subtitle": f"{period_type} operational trend across {len(cats)} continuous observation periods{wow_note}",
                        "metric_col": meas_name,
                        "dimension_col": temp_res.get("date_column", "Date"),
                        "unit": u,
                        "categories": cats,
                        "series": [{"name": f"{meas_label} ({period_type} Mean)", "values": vals}],
                        "overall_mean": val_mean,
                        "ranking_basis": "Chronological Observation Window",
                        "source_reference": f"Source: {sc['original_name']} ({len(cats)} {period_type.lower()} periods)"
                    }
        except Exception:
            pass

        person_cols = [c for c in cols if str(c).startswith("Person_")]
        date_col = next((c for c in cols if any(k in str(c).lower() for k in ("date", "period", "timestamp", "day"))), None)

        if date_col and person_cols:
            date_pts = []
            for r in records:
                d_val = r.get(date_col)
                if not d_val:
                    continue
                p_vals = []
                for pc in person_cols:
                    v = r.get(pc)
                    try:
                        if v is not None and str(v).strip() != "":
                            p_vals.append(float(v))
                    except Exception:
                        pass
                if p_vals:
                    date_pts.append((str(d_val), sum(p_vals) / len(p_vals)))

            if date_pts:
                pts_slice = date_pts[-20:]
                cats = [p[0] for p in pts_slice]
                vals = [round(p[1], 2) for p in pts_slice]
                val_mean = sum(vals) / len(vals)
                return {
                    "chart_type": "line",
                    "title": "Longitudinal Attendance & Daily Working Hours",
                    "subtitle": f"Daily recorded hours across {len(person_cols)} tracked personnel",
                    "metric_col": "Daily Working Hours",
                    "dimension_col": date_col,
                    "unit": "hrs",
                    "categories": cats,
                    "series": [{"name": "Average Daily Hours", "values": vals}],
                    "overall_mean": round(val_mean, 2),
                    "ranking_basis": "Chronological Observation Window",
                    "source_reference": f"Source: {sc['original_name']} ({len(cats)} observation dates)"
                }

        if date_col:
            num_col = next((c for c in cols if c != date_col and any(k in str(c).lower() for k in ("sales", "revenue", "perf", "hour", "amount", "count", "score", "value"))), None)
            if not num_col:
                for c in cols:
                    if c != date_col:
                        sample_v = records[0].get(c)
                        try:
                            float(sample_v)
                            num_col = c
                            break
                        except Exception:
                            pass

            if num_col:
                df = pd.DataFrame(records)
                df[num_col] = pd.to_numeric(df[num_col], errors="coerce")
                valid_df = df.dropna(subset=[date_col, num_col])
                if len(valid_df) > 0:
                    grp = valid_df.groupby(date_col)[num_col].mean().reset_index()
                    grp_slice = grp.tail(20)
                    cats = [str(r[date_col]) for _, r in grp_slice.iterrows()]
                    vals = [round(float(r[num_col]), 2) for _, r in grp_slice.iterrows()]
                    if cats and vals:
                        val_mean = sum(vals) / len(vals)
                        u = infer_measure_unit(num_col)
                        return {
                            "chart_type": "line",
                            "title": f"{format_display_label(num_col)} Longitudinal Trend",
                            "subtitle": f"Period-over-period tracking across {len(cats)} recorded intervals",
                            "metric_col": num_col,
                            "dimension_col": date_col,
                            "unit": u,
                            "categories": cats,
                            "series": [{"name": format_display_label(num_col), "values": vals}],
                            "overall_mean": round(val_mean, 2),
                            "ranking_basis": "Chronological Observation Window",
                            "source_reference": f"Source: {sc['original_name']} ({len(cats)} periods)"
                        }

    return None


def synthesize_fallback_bar_chart(sheet_candidates: list[dict[str, Any]]) -> dict[str, Any] | None:
    """Synthesizes a comparative bar/column chart from raw sheet categorical & numeric columns."""
    for sc in sheet_candidates:
        records = sc["records"]
        cols = sc["columns"]
        if not records or len(records) < 3:
            continue

        person_cols = [c for c in cols if str(c).startswith("Person_")]
        if person_cols:
            df = pd.DataFrame(records)
            p_means = []
            for pc in person_cols:
                series = pd.to_numeric(df[pc], errors="coerce").dropna()
                if len(series) > 0:
                    p_means.append((pc, round(float(series.mean()), 2)))
            if p_means:
                p_means.sort(key=lambda x: x[1], reverse=True)
                top_p = p_means[:8]
                cats = [p[0] for p in top_p]
                vals = [p[1] for p in top_p]
                val_mean = sum(p[1] for p in p_means) / len(p_means)
                return {
                    "chart_type": "column" if len(cats) <= 6 else "bar",
                    "title": "Personnel Working Hours Comparison",
                    "subtitle": f"Top {len(cats)} of {len(p_means)} personnel ranked by average daily hours",
                    "metric_col": "Daily Hours",
                    "dimension_col": "Personnel",
                    "unit": "hrs",
                    "categories": cats,
                    "series": [{"name": "Average Daily Hours", "values": vals}],
                    "overall_mean": round(val_mean, 2),
                    "ranking_basis": "Ranked High to Low",
                    "source_reference": f"Source: {sc['original_name']} ({len(p_means)} tracked personnel)"
                }

        # Bivariate categorical group-by extraction
        try:
            from ..analytics.temporal_categorical_engine import extract_bivariate_categorical_insights
            cat_res = extract_bivariate_categorical_insights(pd.DataFrame(records), cols)
            if cat_res.get("has_categorical_data"):
                p_dims = cat_res.get("dimensions", [])
                p_meas = cat_res.get("measures", [])
                if p_dims and p_meas:
                    first_dim = p_dims[0]
                    first_meas = p_meas[0]
                    b_info = cat_res.get("breakdowns", {}).get(first_dim, {}).get(first_meas)
                    if b_info and b_info.get("categories"):
                        top_cats = b_info["categories"][:8]
                        top_vals = b_info["means"][:8]
                        all_bars = [{"label": c, "value": m} for c, m in zip(b_info["categories"], b_info["means"])]
                        disp_str = f" ({b_info['dispersion_ratio']}x spread)" if b_info.get("dispersion_ratio") else ""

                        return {
                            "chart_type": "column" if len(top_cats) <= 6 else "bar",
                            "title": f"Comparative Entity Benchmark: {b_info['dimension_label']}",
                            "subtitle": f"Top {len(top_cats)} of {len(all_bars)} entities ranked by average {b_info['measure_label'].lower()}{disp_str}",
                            "metric_col": b_info["measure"],
                            "dimension_col": b_info["dimension"],
                            "unit": b_info["unit"],
                            "categories": top_cats,
                            "series": [{"name": f"Average {b_info['measure_label']}", "values": top_vals}],
                            "overall_mean": b_info["overall_mean"],
                            "all_bars": all_bars,
                            "ranking_basis": "Ranked High to Low",
                            "source_reference": f"Source: {sc['original_name']} ({len(all_bars)} {b_info['dimension_label'].lower()} entities)"
                        }
        except Exception:
            pass

        cat_col = next((c for c in cols if any(k in str(c).lower() for k in ("store", "dept", "department", "team", "region", "category", "role", "entity"))), None)
        if not cat_col:
            for c in cols:
                unique_vals = set(r.get(c) for r in records if r.get(c) is not None)
                if 2 <= len(unique_vals) <= 30 and not any(k in str(c).lower() for k in ("date", "id", "timestamp")):
                    cat_col = c
                    break

        num_col = next((c for c in cols if c != cat_col and any(k in str(c).lower() for k in ("sales", "perf", "rating", "score", "hours", "overtime", "amount", "days"))), None)
        if not num_col and cat_col:
            for c in cols:
                if c != cat_col:
                    try:
                        float(records[0].get(c))
                        num_col = c
                        break
                    except Exception:
                        pass

        if cat_col and num_col:
            df = pd.DataFrame(records)
            df[num_col] = pd.to_numeric(df[num_col], errors="coerce")
            valid_df = df.dropna(subset=[cat_col, num_col])
            if len(valid_df) > 0:
                grp = valid_df.groupby(cat_col)[num_col].mean().reset_index()
                grp = grp.sort_values(by=num_col, ascending=False)
                all_bars = [{"label": str(r[cat_col]), "value": round(float(r[num_col]), 2)} for _, r in grp.iterrows()]
                top_bars = all_bars[:8]
                cats = [b["label"] for b in top_bars]
                vals = [b["value"] for b in top_bars]
                u = infer_measure_unit(num_col)
                c_disp = format_display_label(cat_col)
                m_disp = format_display_label(num_col)

                return {
                    "chart_type": "column" if len(cats) <= 6 else "bar",
                    "title": f"Comparative Entity Benchmark: {c_disp}",
                    "subtitle": f"Top {len(cats)} of {len(all_bars)} entities ranked by average {m_disp.lower()}",
                    "metric_col": num_col,
                    "dimension_col": cat_col,
                    "unit": u,
                    "categories": cats,
                    "series": [{"name": f"Average {m_disp}", "values": vals}],
                    "overall_mean": round(valid_df[num_col].mean(), 2),
                    "all_bars": all_bars,
                    "ranking_basis": "Ranked High to Low",
                    "source_reference": f"Source: {sc['original_name']} ({len(all_bars)} {c_disp.lower()} entities)"
                }

    return None


def synthesize_fallback_donut_chart(sheet_candidates: list[dict[str, Any]]) -> dict[str, Any] | None:
    """Synthesizes a cohort distribution donut chart from raw sheet columns."""
    for sc in sheet_candidates:
        records = sc["records"]
        cols = sc["columns"]
        if not records:
            continue

        person_cols = [c for c in cols if str(c).startswith("Person_")]
        if person_cols:
            df = pd.DataFrame(records)
            p_means = []
            for pc in person_cols:
                series = pd.to_numeric(df[pc], errors="coerce").dropna()
                if len(series) > 0:
                    p_means.append(float(series.mean()))
            if p_means:
                min_m, max_m = min(p_means), max(p_means)
                if max_m > min_m:
                    split_pt = (min_m + max_m) / 2.0
                    upper_count = sum(1 for v in p_means if v >= split_pt)
                    lower_count = sum(1 for v in p_means if v < split_pt)
                    cats = [f"Upper Band (>={split_pt:.1f}h)", f"Lower Band (<{split_pt:.1f}h)"]
                    vals = [float(upper_count), float(lower_count)]
                else:
                    cats = [f"Standard ({min_m:.1f}h)"]
                    vals = [float(len(p_means))]
                total_p = sum(vals)
                return {
                    "chart_type": "donut",
                    "title": "Personnel Workload Cohort Distribution",
                    "subtitle": f"Workload distribution across {int(total_p)} evaluated personnel",
                    "metric_col": "Personnel Count",
                    "dimension_col": "Workload Cohort",
                    "unit": "personnel",
                    "categories": cats,
                    "series": [{"name": "Headcount", "values": vals}],
                    "total_population": total_p,
                    "aggregation_disclosure": "All recorded personnel cohorts displayed (100% population).",
                    "source_reference": f"Source: {sc['original_name']} ({int(total_p)} personnel)"
                }

        cand_cat = None
        for c in cols:
            if any(k in str(c).lower() for k in ("dept", "department", "holiday", "status", "category", "flag", "shift", "tier", "role")):
                cand_cat = c
                break
        if not cand_cat:
            for c in cols:
                if not str(c).startswith("Person_") and "date" not in str(c).lower() and "id" not in str(c).lower():
                    u_vals = set(r.get(c) for r in records if r.get(c) is not None)
                    if 2 <= len(u_vals) <= 12:
                        cand_cat = c
                        break

        if cand_cat:
            df = pd.DataFrame(records)
            counts = df[cand_cat].value_counts().reset_index()
            counts.columns = ["cat", "count"]
            slices = [{"label": str(r["cat"]), "count": float(r["count"])} for _, r in counts.iterrows()]
            
            if len(slices) > 6:
                top5 = slices[:5]
                remainder = slices[5:]
                other_sum = round(sum(s["count"] for s in remainder), 2)
                cats = [s["label"] for s in top5] + ["Other"]
                vals = [round(s["count"], 2) for s in top5] + [other_sum]
                agg_disclosure = f"Top 5 categories; {len(remainder)} remaining segments aggregated into 'Other' ({other_sum:,.0f} entries) to preserve 100% population."
            else:
                cats = [s["label"] for s in slices]
                vals = [round(s["count"], 2) for s in slices]
                agg_disclosure = "All recorded categories displayed (100% population)."

            total_pop = sum(vals)
            c_disp = format_display_label(cand_cat)
            return {
                "chart_type": "donut",
                "title": f"{c_disp} Population Distribution",
                "subtitle": f"Cohort breakdown across {total_pop:,.0f} evaluated entries",
                "metric_col": "Proportion",
                "dimension_col": cand_cat,
                "unit": "%" if "flag" in cand_cat.lower() else "records",
                "categories": cats,
                "series": [{"name": "Share", "values": vals}],
                "total_population": total_pop,
                "aggregation_disclosure": agg_disclosure,
                "source_reference": f"Source: {sc['original_name']} ({total_pop:,.0f} total entries)"
            }

        for c in cols:
            if "date" in str(c).lower() or "id" in str(c).lower():
                continue
            df = pd.DataFrame(records)
            series = pd.to_numeric(df[c], errors="coerce").dropna()
            if len(series) >= 6:
                q1, q2 = series.quantile(0.33), series.quantile(0.66)
                low = int((series <= q1).sum())
                mid = int(((series > q1) & (series <= q2)).sum())
                high = int((series > q2).sum())
                total_p = low + mid + high
                if total_p > 0:
                    c_disp = format_display_label(c)
                    return {
                        "chart_type": "donut",
                        "title": f"{c_disp} Tier Distribution",
                        "subtitle": f"Population tier segmentation across {total_p:,} records",
                        "metric_col": "Count",
                        "dimension_col": f"{c_disp} Tier",
                        "unit": "records",
                        "categories": ["Top Tier", "Mid Tier", "Base Tier"],
                        "series": [{"name": "Records", "values": [float(high), float(mid), float(low)]}],
                        "total_population": float(total_p),
                        "aggregation_disclosure": "Quartile segmentation preserving 100% population.",
                        "source_reference": f"Source: {sc['original_name']} ({total_p:,} total records)"
                    }

    return None
