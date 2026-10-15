"""Compare recorded attendance and leave measures without assuming a duty roster."""
import hashlib
import re

import pandas as pd

from ..data_engine.visualization_models import ChartSeries, VisualChartSpec


def _words(value):
    return re.sub(r"[^a-z0-9]+", " ", str(value).lower()).strip()


def attendance_leave_visual(query, df, sheet_name, sheet_id, descriptor):
    """Return response fields for a bounded comparison, or defer other requests.

    Totals are independent source measures. In particular, Total Attendance and
    Final Attendance may overlap, so a pie/stacked partition is not defensible.
    """
    text = _words(query)
    followup_words = set("show display draw render give me it this that the same previous again as in a an chart graph plot format bar column pie donut please switch change to instead now".split())
    followup = (descriptor.get("kind") == "attendance_leave_totals"
                and bool(text) and set(text.split()) <= followup_words)
    source_query = descriptor.get("source_query", "") if followup else query
    source_text = _words(source_query)
    if not (re.search(r"\battendance\b", source_text) and re.search(r"\bleaves?\b", source_text)):
        return None

    def clarify(answer):
        return {"answer": answer, "status": "clarification_required"}

    # Do not silently discard a department filter, time window, grouping or a
    # requested average. Those need a separately resolved analytical plan.
    allowed = followup_words | set("of how do does and vs versus compare comparing comparison balance balances balanced reconcile records recorded days approved final total totals sum attendance leave leaves overall all across sheet dataset data for can could you make create generate visualize visualise visualization visualisation".split())
    if (set(source_text.split()) - allowed
            or re.search(r"[<>=]", source_query)):
        return clarify("I can chart the overall recorded attendance and approved-leave totals. Please specify the columns and calculation for a filtered, grouped, or time-specific comparison.")

    aliases = [
        {"total attendance", "total attendance days", "attendance", "attendance days", "recorded attendance", "attended days", "office attendance", "office attendance days"},
        {"approved leave", "approved leaves", "approved leave days", "approved leaves days", "leave", "leaves", "leave days", "total approved leaves"},
        {"final attendance", "final attendance days"},
    ]
    matches = [[column for column in df.columns if _words(column) in names] for names in aliases]
    if any(len(columns) > 1 for columns in matches):
        return clarify("Several attendance or leave columns could apply. Please name the attendance and approved-leave columns to compare.")
    if not matches[1] or not (matches[0] or matches[2]):
        return clarify("Please select a sheet with recorded attendance days and approved leave days. Attendance rates and leave percentages cannot be compared as day totals.")
    columns = [column for group in matches for column in group]
    numeric = pd.DataFrame({column: pd.to_numeric(df[column].astype("string").str.replace(",", "", regex=False), errors="coerce")
                            for column in columns}).replace([float("inf"), -float("inf")], pd.NA)
    valid = numeric.loc[numeric.notna().all(axis=1) & numeric.ge(0).all(axis=1)]
    if valid.empty:
        return {"answer": "No complete, non-negative attendance and leave records are available to chart.", "status": "no_data"}
    values = [float(valid[column].sum()) for column in columns]
    used, excluded = len(valid), len(df) - len(valid)
    disclosure = f"Column totals across {used:,} complete records; {excluded:,} incomplete, invalid or negative records excluded."
    chart_type = "bar" if re.search(r"\bbar\b", text) else "column"
    note = "These recorded measures may overlap; they do not establish scheduled working days or an attendance rate."
    if re.search(r"\b(pie|donut)\b", text):
        note = "A column chart is used because these recorded measures may overlap. " + note
    chart = VisualChartSpec(
        chart_id="CHAT-" + hashlib.sha256(f"{sheet_id}:{columns}:attendance_leave_totals".encode()).hexdigest()[:12],
        chart_type=chart_type, title="Recorded attendance and approved leave", subtitle=sheet_name,
        unit="days", categories=columns, series=[ChartSeries(name="Recorded days", values=values)],
        dimension_col="Source measure", aggregation_disclosure=disclosure,
        metadata={"sheet_id": sheet_id, "operation": "sum", "source_columns": columns, "valid_rows": used},
    )
    answer = "### Recorded attendance and approved leave\n\n" + "\n".join(
        f"- **{column}**: {value:,.2f} days" for column, value in zip(columns, values)
    ) + f"\n\n{disclosure}\n\n{note}"
    return {
        "answer": answer, "charts": [chart.model_dump()],
        "context": {"visualization_context": {"kind": "attendance_leave_totals", "operation": "sum", "source_query": source_query}},
        "evidence": {"source_ids": [sheet_id], "source_columns": columns,
                     "calculation_method": "Sum each source column over the same complete, finite, non-negative records; no derived attendance or roster assumptions.",
                     "coverage": {"total_rows": len(df), "used_rows": used, "excluded_rows": excluded}},
    }
