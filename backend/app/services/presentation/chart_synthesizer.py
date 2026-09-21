import logging
import math
from typing import Any

from ...db.database import get_connection
from ..display_formatters import format_display_label
from ..time_series_forecast import infer_measure_unit
from ..visual_intelligence import build_workspace_visual_dashboard
from .chart_fallbacks import (
    synthesize_fallback_line_chart,
    synthesize_fallback_bar_chart,
    synthesize_fallback_donut_chart,
)

logger = logging.getLogger(__name__)


def extract_presentation_charts(visuals: list[dict], domain: str) -> list[dict[str, Any]]:
    """Transforms dashboard visualizations into structured slide chart specs."""
    deck_charts = []

    for v in visuals:
        c_type = v.get("chart_type")
        unit = v.get("unit", "")
        title = v.get("title", "")
        subtitle = v.get("subtitle", "")

        # 1. Line Charts
        if c_type == "line" and "line_data" in v:
            ld = v["line_data"]
            pts = ld.get("points", [])
            if pts:
                categories = [str(p.get("period")) for p in pts if p.get("period") is not None]
                values = [round(float(p.get("value", 0)), 2) for p in pts if p.get("period") is not None and math.isfinite(float(p.get("value", 0)))]
                if len(categories) == len(values) and len(categories) > 0:
                    val_mean = sum(values) / len(values) if values else 0.0
                    u = unit or infer_measure_unit(ld.get("metric_col", ""))
                    deck_charts.append({
                        "chart_type": "line",
                        "title": title or f"{format_display_label(ld.get('metric_col', 'Metric'))} Trend",
                        "subtitle": subtitle or "Chronological observation trajectory",
                        "metric_col": ld.get("metric_col", "Metric"),
                        "dimension_col": ld.get("date_col", "Date"),
                        "unit": u,
                        "categories": categories,
                        "series": [{"name": format_display_label(ld.get("metric_col", "Metric")), "values": values}],
                        "overall_mean": round(val_mean, 2),
                        "ranking_basis": "Chronological Observation Window",
                        "source_reference": f"Source: {v.get('sheet_badge', 'Dataset')} ({len(pts)} periods)"
                    })

        # 2. Longitudinal Forecasts (converted to multi-series or chronological line)
        elif c_type == "forecast" and "forecast_data" in v:
            fd = v["forecast_data"]
            hist = fd.get("historical", [])
            target_col = fd.get("target_column", "Daily Volume")
            f_unit = fd.get("unit") or unit or infer_measure_unit(target_col)
            if hist:
                pts = hist[-20:]
                categories = [str(p.get("period")) for p in pts if p.get("period") is not None]
                values = [round(float(p.get("actual", 0)), 2) for p in pts if p.get("period") is not None and math.isfinite(float(p.get("actual", 0)))]
                if len(categories) == len(values) and len(categories) > 0:
                    val_mean = sum(values) / len(values) if values else 0.0
                    deck_charts.append({
                        "chart_type": "line",
                        "title": title or f"{format_display_label(target_col)} Longitudinal Trajectory",
                        "subtitle": subtitle or f"Recorded operational volume across {len(pts)} continuous observation dates",
                        "metric_col": target_col,
                        "dimension_col": "Date",
                        "unit": f_unit,
                        "categories": categories,
                        "series": [{"name": f"Recorded {format_display_label(target_col)}", "values": values}],
                        "overall_mean": round(val_mean, 2),
                        "ranking_basis": "Chronological Observation Window",
                        "source_reference": f"Source: {v.get('sheet_badge', 'Dataset')} ({len(pts)} periods)"
                    })

        # 3. Cross-Sheet Grouped Comparative Bars (Multi-Series)
        elif c_type == "comparative_bar" and "comparative_data" in v:
            comp = v["comparative_data"]
            items = comp.get("items", [])
            series_defs = comp.get("series", [])
            if items and series_defs and len(series_defs) >= 2:
                categories = [str(it.get("label")) for it in items[:8]]
                s1_name = series_defs[0].get("name", "Series 1")
                s2_name = series_defs[1].get("name", "Series 2")
                s1_vals = [round(float(it.get("val1", 0)), 2) for it in items[:8]]
                s2_vals = [round(float(it.get("val2", 0)), 2) for it in items[:8]]
                if len(categories) == len(s1_vals) == len(s2_vals) and len(categories) > 0:
                    deck_charts.append({
                        "chart_type": "column" if len(categories) <= 6 else "bar",
                        "title": title or "Comparative Operational Diagnostics",
                        "subtitle": subtitle or f"Multi-metric evaluation across {len(categories)} operational units",
                        "metric_col": f"{s1_name} & {s2_name}",
                        "dimension_col": comp.get("category_col", "Department"),
                        "unit": series_defs[0].get("unit", unit),
                        "categories": categories,
                        "series": [
                            {"name": s1_name, "values": s1_vals},
                            {"name": s2_name, "values": s2_vals}
                        ],
                        "ranking_basis": "Categorical Grouping",
                        "source_reference": f"Source: {v.get('sheet_badge', 'Cross-Sheet Join')}"
                    })

        # 4. Standard Bar / Column Charts
        elif c_type == "bar" and "bars" in v:
            bars = v["bars"]
            if bars:
                display_bars = bars[:10]
                categories = [str(b.get("label")) for b in display_bars]
                values = [round(float(b.get("value", 0)), 2) for b in display_bars]
                cat_disp = format_display_label(v.get("category_col", "Entity"))
                if len(categories) == len(values) and len(categories) > 0:
                    deck_charts.append({
                        "chart_type": "column" if len(categories) <= 6 else "bar",
                        "title": title,
                        "subtitle": f"Top {len(display_bars)} of {len(bars)} {cat_disp.lower()} entities" if len(bars) > 10 else subtitle,
                        "metric_col": v.get("metric_col", "Metric"),
                        "dimension_col": v.get("category_col", "Category"),
                        "unit": unit or infer_measure_unit(v.get("metric_col", "")),
                        "categories": categories,
                        "series": [{"name": format_display_label(v.get("metric_col", "Metric")), "values": values}],
                        "overall_mean": v.get("overall_mean"),
                        "all_bars": bars,
                        "ranking_basis": v.get("ranking_basis", "Ranked High to Low"),
                        "source_reference": f"Source: {v.get('sheet_badge', 'Dataset')} ({len(bars)} categories)"
                    })

        # 5. Part-to-Whole Pie & Donut Charts (preserving 100% population via 'Other')
        elif (c_type in ("donut", "pie")) and ("donut_data" in v or "pie_data" in v):
            dd = v.get("donut_data") or v.get("pie_data", {})
            slices = dd.get("slices", [])
            if slices:
                is_pie = (c_type == "pie")
                if len(slices) > 6:
                    top5 = slices[:5]
                    remainder = slices[5:]
                    other_sum = round(sum(float(s.get("count", 0)) for s in remainder), 2)
                    categories = [str(s.get("label")) for s in top5] + ["Other"]
                    values = [round(float(s.get("count", 0)), 2) for s in top5] + [other_sum]
                    agg_disclosure = f"Top 5 categories; {len(remainder)} remaining segments aggregated into 'Other' ({other_sum:,.0f} entries) to preserve 100% population."
                else:
                    categories = [str(s.get("label")) for s in slices]
                    values = [round(float(s.get("count", 0)), 2) for s in slices]
                    agg_disclosure = "All recorded categories displayed (100% population)."

                total_pop = dd.get("total", sum(values))
                deck_charts.append({
                    "chart_type": "pie" if is_pie else "donut",
                    "title": title,
                    "subtitle": subtitle,
                    "metric_col": "Proportion",
                    "dimension_col": dd.get("category_col", "Segment"),
                    "unit": "%",
                    "categories": categories,
                    "series": [{"name": "Share", "values": values}],
                    "total_population": total_pop,
                    "aggregation_disclosure": agg_disclosure,
                    "source_reference": f"Source: {v.get('sheet_badge', 'Dataset')} ({total_pop} total entries)"
                })

        # 6. Burnout & Strain Multi-Series Bar
        elif c_type == "burnout_strain" and "burnout_data" in v:
            bs = v["burnout_data"]
            depts = bs.get("departments", [])
            if depts:
                categories = [str(d.get("department")) for d in depts[:8]]
                s1_vals = [round(float(d.get("strain_score_pct", 0)), 2) for d in depts[:8]]
                s2_vals = [round(float(d.get("overtime_intensity_pct", 0)), 2) for d in depts[:8]]
                if len(categories) == len(s1_vals) == len(s2_vals) and len(categories) > 0:
                    deck_charts.append({
                        "chart_type": "column" if len(categories) <= 6 else "bar",
                        "title": title or "Department Strain & Overtime Diagnostic",
                        "subtitle": subtitle or "Comparative compensatory overtime strain ratio by department",
                        "metric_col": "Strain Ratio & Overtime",
                        "dimension_col": "Department",
                        "unit": "%",
                        "categories": categories,
                        "series": [
                            {"name": "Strain Score (%)", "values": s1_vals},
                            {"name": "Overtime Intensity (%)", "values": s2_vals}
                        ],
                        "ranking_basis": "Departmental Workload",
                        "source_reference": f"Source: {v.get('sheet_badge', 'Workforce Science')}"
                    })

        # 7. Talent 9-Box Distribution Donut
        elif c_type == "talent_9box" and "talent_9box_data" in v:
            t9 = v["talent_9box_data"]
            categories = ["High Performers", "Core Contributors", "Retention Risk Stars", "Action Required (PIP)"]
            values = [
                float(t9.get("high_performers_count", 0)),
                float(t9.get("core_performers_count", 0)),
                float(t9.get("retention_vulnerable_stars", 0)),
                float(t9.get("underperformers_count", 0))
            ]
            if sum(values) > 0:
                deck_charts.append({
                    "chart_type": "donut",
                    "title": title or "Talent & Risk Cohort Distribution",
                    "subtitle": subtitle or f"McKinsey / GE 9-Box distribution across {t9.get('total_evaluated', sum(values))} personnel",
                    "metric_col": "Staff Count",
                    "dimension_col": "Talent Tier",
                    "unit": "personnel",
                    "categories": categories,
                    "series": [{"name": "Cohort Count", "values": values}],
                    "total_population": t9.get("total_evaluated", sum(values)),
                    "aggregation_disclosure": "4 strategic talent segments evaluated across complete cohort.",
                    "source_reference": f"Source: {v.get('sheet_badge', 'Industrial Model')}"
                })

    return deck_charts


def synthesize_presentation_charts(
    conn: Any | None,
    scope: dict[str, Any],
    dataset_context: dict[str, Any],
    workspace_evidence: dict[str, Any] | None = None
) -> dict[str, Any]:
    """Ensures deterministic, evidence-backed chart specifications for all analytical presentation slides."""
    domain = dataset_context.get("domain", "Operations")
    candidate_visuals = list(dataset_context.get("visuals", []))
    
    close_conn = False
    if conn is None:
        conn = get_connection()
        close_conn = True

    try:
        if workspace_evidence:
            included_sheets = workspace_evidence.get("included_sheets", [])
            for s in included_sheets:
                try:
                    s_dash = build_workspace_visual_dashboard(conn, sheet_id=s["id"])
                    for sv in s_dash.get("visualizations", []):
                        if not any(v.get("id") == sv.get("id") for v in candidate_visuals):
                            candidate_visuals.append(sv)
                except Exception as exc:
                    logger.debug(f"Visual dashboard fetch error for sheet {s['id']}: {exc}")

            try:
                ws_dash = build_workspace_visual_dashboard(conn, sheet_id=None)
                for wv in ws_dash.get("visualizations", []):
                    if not any(v.get("id") == wv.get("id") for v in candidate_visuals):
                        candidate_visuals.append(wv)
            except Exception as exc:
                logger.debug(f"Workspace visual dashboard fetch error: {exc}")

        extracted = extract_presentation_charts(candidate_visuals, domain)

        line_chart = next((c for c in extracted if c["chart_type"] == "line"), None)
        bar_chart = next((c for c in extracted if c["chart_type"] in ("bar", "column")), None)
        donut_chart = next((c for c in extracted if c["chart_type"] in ("donut", "pie")), None)
        rel_chart = next((c for c in extracted if len(c.get("series", [])) > 1), None)

        sheet_candidates = []
        if workspace_evidence and "sheet_contexts" in workspace_evidence:
            for sid, sctx in workspace_evidence["sheet_contexts"].items():
                sheet_candidates.append({
                    "id": sid,
                    "name": sctx["sheet"]["name"],
                    "original_name": sctx["sheet"]["original_name"],
                    "records": sctx["records"],
                    "columns": sctx["columns"]
                })
        else:
            sheet_candidates.append({
                "id": dataset_context["target_sheet"]["id"],
                "name": dataset_context["target_sheet"]["name"],
                "original_name": dataset_context["target_sheet"]["original_name"],
                "records": dataset_context["records"],
                "columns": dataset_context["columns"]
            })

        # Synthesize fallback charts if any missing
        if not line_chart:
            line_chart = synthesize_fallback_line_chart(sheet_candidates)

        if not bar_chart:
            bar_chart = synthesize_fallback_bar_chart(sheet_candidates)

        if not donut_chart:
            donut_chart = synthesize_fallback_donut_chart(sheet_candidates)

        return {
            "line_chart": line_chart,
            "bar_chart": bar_chart,
            "donut_chart": donut_chart,
            "rel_chart": rel_chart,
            "all_charts": extracted
        }
    finally:
        if close_conn and conn:
            conn.close()
