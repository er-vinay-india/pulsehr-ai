"""Translates visual intelligence visualizations into presentation chart specifications."""

from typing import Any
import numpy as np


def convert_visual_to_chart_spec(v: dict[str, Any], default_type: str = "column") -> dict[str, Any] | None:
    """Safely transforms a visual dashboard visualization item into a valid presentation chart spec."""
    raw_type = v.get("chart_type", default_type).lower()

    # Time series / Forecast line chart
    if raw_type in ("forecast", "line"):
        fc_data = v.get("forecast_data") or v.get("line_data")
        if fc_data and isinstance(fc_data, dict):
            pts = fc_data.get("points") or fc_data.get("historical", [])
            if pts:
                cats = [str(p.get("date") or p.get("label", f"T{i}")) for i, p in enumerate(pts[-16:])]
                vals = [round(float(p.get("value") or p.get("sales", 0)), 2) for p in pts[-16:]]
                if cats and vals:
                    return {
                        "chart_type": "line",
                        "title": v.get("title", "Longitudinal Performance Trend"),
                        "subtitle": v.get("subtitle", f"Period tracking across {len(cats)} intervals"),
                        "metric_col": v.get("measured_metric", "Metric"),
                        "dimension_col": "Date",
                        "unit": v.get("unit", ""),
                        "categories": cats,
                        "series": [{"name": v.get("measured_metric", "Recorded Values"), "values": vals}],
                        "overall_mean": round(float(np.mean(vals)), 2),
                        "source_reference": f"Source: {v.get('source_sheets', ['Workspace'])[0]}"
                    }

    # Grouped comparative bar or standard bar/column chart
    if raw_type in ("comparative_bar", "bar", "column"):
        cb_data = v.get("comparative_bar_data") or v.get("bar_data")
        if cb_data and isinstance(cb_data, dict):
            items = cb_data.get("items", [])
            if items:
                cats = [str(it.get("label", f"Entity {i}")) for i, it in enumerate(items[:8])]
                m1_name = cb_data.get("metric1_name", "Primary Metric")
                m1_vals = [round(float(it.get("val1") or it.get("value", 0)), 2) for it in items[:8]]
                series = [{"name": m1_name, "values": m1_vals}]

                m2_name = cb_data.get("metric2_name")
                if m2_name and any("val2" in it for it in items[:8]):
                    m2_vals = [round(float(it.get("val2", 0)), 2) for it in items[:8]]
                    series.append({"name": m2_name, "values": m2_vals})

                return {
                    "chart_type": "column" if len(cats) <= 6 else "bar",
                    "title": v.get("title", "Comparative Entity Benchmarking"),
                    "subtitle": v.get("subtitle", f"Top {len(cats)} entities ranked by operational volume"),
                    "metric_col": m1_name,
                    "dimension_col": cb_data.get("category_column", "Entity"),
                    "unit": v.get("unit", ""),
                    "categories": cats,
                    "series": series,
                    "overall_mean": round(float(np.mean(m1_vals)), 2) if m1_vals else 0.0,
                    "source_reference": f"Source: {v.get('source_sheets', ['Workspace'])[0]}"
                }

    # Donut / Pie chart
    if raw_type in ("donut", "pie"):
        d_data = v.get("donut_data") or v.get("pie_data")
        if d_data and isinstance(d_data, dict):
            slices = d_data.get("slices", [])
            if slices:
                cats = [str(s.get("label", f"Cat {i}")) for i, s in enumerate(slices[:6])]
                vals = [round(float(s.get("count") or s.get("value", 0)), 2) for s in slices[:6]]
                return {
                    "chart_type": "donut",
                    "title": v.get("title", "Population Distribution"),
                    "subtitle": v.get("subtitle", f"Cohort breakdown across {sum(vals):,.0f} entries"),
                    "metric_col": "Count",
                    "dimension_col": d_data.get("category_col", "Category"),
                    "unit": "records",
                    "categories": cats,
                    "series": [{"name": "Share", "values": vals}],
                    "total_population": sum(vals),
                    "source_reference": f"Source: {v.get('source_sheets', ['Workspace'])[0]}"
                }

    return None
