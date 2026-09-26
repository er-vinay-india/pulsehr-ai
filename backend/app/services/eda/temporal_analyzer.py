"""Temporal Segmentation & Date-Separated Dynamics Engine.
Extracts period intervals, cohorts data by date ranges, and analyzes temporal attendance & leave trajectories.
"""
from __future__ import annotations

import re
from typing import Any
import numpy as np


PERIOD_REGEX = re.compile(
    r"(?:\d+(?:st|nd|rd|th))\s+to\s+(?:\d+(?:st|nd|rd|th))\s*([a-z]+)?|"
    r"\b\d{4}-\d{2}-\d{2}\b|"
    r"\b(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\s*(?:\d{1,2}|week\s*\d+)?\b",
    re.IGNORECASE
)


def extract_temporal_periods(columns: list[str]) -> list[dict[str, Any]]:
    """Identifies and orders period-based columns (e.g. weekly date brackets and corresponding leave counts)."""
    attendance_periods = []
    leave_periods = []

    for c in columns:
        m = PERIOD_REGEX.search(c)
        if m:
            if "leave" in c.lower():
                leave_periods.append((c, m.group(0)))
            else:
                attendance_periods.append((c, m.group(0)))

    matched_pairs = []
    # Match attendance period with corresponding leave period
    for att_col, att_token in attendance_periods:
        # Find matching leave period
        att_norm = re.sub(r"[^\w]", "", att_col.lower())
        best_leave = None
        for l_col, l_token in leave_periods:
            l_norm = re.sub(r"[^\w]", "", l_col.lower())
            if att_norm in l_norm or (att_token and att_token.lower() in l_col.lower()):
                best_leave = l_col
                break

        matched_pairs.append({
            "period_label": att_col,
            "attendance_col": att_col,
            "leave_col": best_leave
        })

    # If no matched attendance columns but leave columns exist
    if not matched_pairs and leave_periods:
        for l_col, _ in leave_periods:
            matched_pairs.append({
                "period_label": l_col,
                "attendance_col": None,
                "leave_col": l_col
            })

    return matched_pairs


def analyze_temporal_dynamics(
    records: list[dict[str, Any]],
    columns: list[str]
) -> dict[str, Any] | None:
    """Computes period-over-period attendance, leave rates, and temporal correlations."""
    periods_meta = extract_temporal_periods(columns)
    if not periods_meta or len(periods_meta) < 2:
        return None

    timeline_points = []
    period_vectors = {}

    for idx, p in enumerate(periods_meta):
        label = p["period_label"]
        att_col = p["attendance_col"]
        leave_col = p["leave_col"]

        att_vals = []
        if att_col:
            for r in records:
                v = r.get(att_col)
                if v is not None:
                    try:
                        att_vals.append(float(v))
                    except (ValueError, TypeError):
                        pass

        leave_vals = []
        if leave_col:
            for r in records:
                v = r.get(leave_col)
                if v is not None:
                    try:
                        leave_vals.append(float(v))
                    except (ValueError, TypeError):
                        pass

        att_mean = float(np.mean(att_vals)) if att_vals else 0.0
        leave_mean = float(np.mean(leave_vals)) if leave_vals else 0.0
        total_leave = float(np.sum(leave_vals)) if leave_vals else 0.0
        total_att = float(np.sum(att_vals)) if att_vals else 0.0

        denom = total_att + total_leave
        leave_rate_pct = round((total_leave / denom) * 100.0, 1) if denom > 0 else 0.0

        timeline_points.append({
            "period_index": idx + 1,
            "period_label": label,
            "average_attendance": round(att_mean, 2),
            "average_leaves": round(leave_mean, 2),
            "total_attendance": round(total_att, 1),
            "total_leaves": round(total_leave, 1),
            "leave_rate_percentage": leave_rate_pct
        })

        if leave_vals and len(leave_vals) == len(records):
            period_vectors[label] = leave_vals

    # Identify temporal anomalies (e.g. peak leave period)
    peak_leave_period = max(timeline_points, key=lambda pt: pt["average_leaves"]) if timeline_points else None
    lowest_att_period = min(timeline_points, key=lambda pt: pt["average_attendance"]) if timeline_points else None

    # Temporal lag correlations (e.g. Early Month vs Late Month)
    temporal_correlations = []
    keys = list(period_vectors.keys())
    for i in range(len(keys)):
        for j in range(i + 1, len(keys)):
            k1, k2 = keys[i], keys[j]
            v1, v2 = np.array(period_vectors[k1]), np.array(period_vectors[k2])
            if np.std(v1) > 0 and np.std(v2) > 0:
                corr = float(np.corrcoef(v1, v2)[0, 1])
                if not np.isnan(corr) and abs(corr) >= 0.10:
                    temporal_correlations.append({
                        "period_a": k1,
                        "period_b": k2,
                        "correlation": round(corr, 3),
                        "direction": "positive" if corr > 0 else "negative",
                        "interpretation": (
                            f"Staff taking leave in '{k1}' had a "
                            f"{'higher' if corr > 0 else 'lower'} tendency to also take leave in '{k2}' (r = {corr:+.2f})."
                        )
                    })

    # Plain language HR Domain Insight
    hr_insights = []
    if peak_leave_period and peak_leave_period["average_leaves"] > 0:
        hr_insights.append(
            f"Peak Leave Period: '{peak_leave_period['period_label']}' recorded the highest absenteeism "
            f"(Avg: {peak_leave_period['average_leaves']} days/person, {peak_leave_period['leave_rate_percentage']}% leave rate). "
            f"Recommend scheduled coverage adjustments for this window."
        )
    if lowest_att_period and lowest_att_period["average_attendance"] > 0:
        hr_insights.append(
            f"Lowest Attendance Window: '{lowest_att_period['period_label']}' averaged {lowest_att_period['average_attendance']} days attendance."
        )

    return {
        "has_temporal_data": True,
        "timeline_series": timeline_points,
        "temporal_correlations": temporal_correlations,
        "peak_period": peak_leave_period["period_label"] if peak_leave_period else None,
        "insights": hr_insights
    }
