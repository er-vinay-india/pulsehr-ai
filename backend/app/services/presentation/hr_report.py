"""Business attendance report built from source cells, without inferred policy.

The analytics service owns period normalization. This report keeps missing values,
employee identity and the calculation inputs explicit in its internal contract.
"""
from __future__ import annotations

import datetime
import math
import re
import uuid
from collections import Counter
from statistics import mean, median
from typing import Any

from ..hr_period_analytics import extract_normalized_periods
from .builders.common import THEMES


def _number(value):
    try:
        number = float(value)
        return number if math.isfinite(number) else None
    except (TypeError, ValueError):
        return None


def _norm(value):
    return re.sub(r"[^a-z0-9]", "", str(value).lower())


def _column(columns, aliases):
    return next((c for c in columns if _norm(c) in aliases), None)


def build_hr_report(scope: dict, ctx: dict, workspace: dict | None = None) -> dict | None:
    """Return an attendance report only for recognizable attendance fields.

    Duplicate or missing employee IDs prevent employee rollups. Multi-month wide
    tables need explicit scoping before monthly totals can be interpreted safely.
    Neither condition is silently repaired by choosing an arbitrary row/period.
    """
    columns = ctx.get("columns") or list((ctx.get("records") or [{}])[0])
    id_col = _column(columns, {"id", "empid", "employeeid", "staffid"})
    att_col = _column(columns, {"totalattendance", "totalattended", "monthlyattendance", "totalofficedays"})
    leave_col = _column(columns, {"approvedleaves", "approvedleave", "totalapprovedleaves", "totalleave", "totalleaves"})
    final_col = _column(columns, {"finalattendance", "netattendance", "adjustedattendance"})
    dept_col = _column(columns, {"department", "dept", "departmentname"})
    periods = extract_normalized_periods(columns)
    if not id_col or not (att_col or any(p.attendance_col for p in periods)):
        return None
    records = ctx.get("records") or []
    sheet = ctx.get("target_sheet") or {}
    label = sheet.get("name") or sheet.get("original_name") or "Attendance records"
    months = {(p.month, p.year) for p in periods}
    period = next(iter(months)) if len(months) == 1 else None
    period_label = f"{period[0]} {period[1]}" if period and period[1] else (f"{period[0]} (year not recorded)" if period else "Recorded reporting period")
    ids = [str(r[id_col]).strip() if r.get(id_col) is not None else "" for r in records]
    missing_ids = sum(not i for i in ids)
    duplicate_ids = sorted(i for i, count in Counter(ids).items() if i and count > 1)
    safe_population = not missing_ids and not duplicate_ids and len(months) <= 1
    ledger, slides = [], []
    policy_limit = "WFO policy and working-day calendar were not supplied; compliance and working-day rates cannot be determined."

    def fact(name, value, unit, inputs=None, method="count", denominator=None):
        eid = f"HR-{len(ledger)+1:03d}"
        ledger.append({"evidence_id": eid, "title": name, "metric_name": name,
                       "numeric_value": value, "metric_value": f"{value:g} {unit}", "unit": unit,
                       "date_range": period_label, "source_sheets": [label],
                       "finding_type": "measured_fact", "denominator": denominator,
                       "calculation_methodology": method, "calculation_inputs": inputs or [],
                       "limitations": policy_limit})
        return {"label": name, "value": f"{value:g}", "unit": unit, "evidence_id": eid,
                "subtext": unit}

    def slide(title, narrative, bullets=None, metrics=None, chart=None, table=None):
        refs = [m["evidence_id"] for m in metrics or []]
        refs += (chart or {}).get("evidence_ids", [])
        refs += (table or {}).get("evidence_ids", [])
        slides.append({"id": f"slide_{len(slides)+1}", "order": len(slides)+1,
                       "category": "ATTENDANCE REVIEW", "title": title, "subtitle": period_label,
                       "layout": "chart_narrative" if chart else ("table_detail" if table else "kpi_summary" if metrics else "comparison_split"),
                       "narrative": narrative, "bullets": bullets or [], "metrics": metrics or [],
                       "chart": chart, "table": table, "evidence_ids": refs,
                       "evidence_id": refs[0] if refs else None, "source_label": label,
                       "speaker_notes": narrative + " " + " ".join(bullets or []),
                       "narration_script": narrative + " " + " ".join(bullets or []),
                       "limitations": policy_limit, "business_report": True})

    def values(row, column, period_role):
        if column:
            return _number(row.get(column))
        fields = [getattr(p, period_role) for p in periods if getattr(p, period_role)]
        nums = [_number(row.get(c)) for c in fields]
        return sum(nums) if nums and all(n is not None for n in nums) else None

    office = [values(r, att_col, "attendance_col") for r in records]
    leave = [values(r, leave_col, "leave_col") for r in records]
    slide("Office attendance review", "Review recorded office days, approved leave and the checks needed before making policy decisions.",
          [policy_limit], [fact("Source rows", len(records), "rows")])
    if not safe_population:
        issues = []
        if duplicate_ids:
            issues.append("Employee IDs occur more than once: " + ", ".join(duplicate_ids[:8]) + ". Confirm the employee-period grain before adding office days.")
        if missing_ids:
            issues.append("Some records have no employee ID. Confirm identity before counting employees.")
        if len(months) > 1:
            issues.append("Several reporting months are present. Select one employee-period before using monthly totals.")
        slide("Resolve record scope before comparing attendance", "Employee summaries are withheld until these source issues are resolved.", issues)
        slide("Next steps", "Confirm employee identity and reporting period, then regenerate the attendance review.", [policy_limit])
    else:
        measured = [v for v in office if v is not None]
        known_leave = [v for v in leave if v is not None]
        summary = [fact("Employees", len(ids), "employees")]
        if measured:
            summary += [fact("Recorded office days", sum(measured), "days", measured, "sum"),
                        fact("Median office days", median(measured), "days", measured, "median", len(measured))]
        if known_leave:
            summary.append(fact("Recorded approved leave", sum(known_leave), "days", known_leave, "sum"))
        slide("Attendance at a glance", "Office days and leave are reported separately. Missing attendance values are excluded from averages.",
              ["The figures describe recorded attendance; they do not establish policy compliance."], summary)
        weekly_rows, weekly_refs, weekly_means = [], [], []
        for p in periods:
            if not p.attendance_col:
                continue
            nums = [_number(r.get(p.attendance_col)) for r in records]
            nums = [n for n in nums if n is not None]
            if not nums:
                continue
            m = fact("Average office days: " + p.label, mean(nums), "days", nums, "mean", len(nums))
            weekly_refs.append(m["evidence_id"])
            weekly_means.append(mean(nums))
            weekly_rows.append([p.label, f"{mean(nums):.2f}", str(len(nums))])
        if weekly_rows:
            slide("Office days across the recorded weeks", "Weekly averages use employees with a recorded attendance value in each week.",
                  ["Week lengths differ. These are recorded days per employee, not attendance rates or a historical trend."],
                  chart={"type": "bar", "title": "Average office days per employee", "categories": [r[0] for r in weekly_rows],
                         "series": [{"name": "Office days", "values": weekly_means}], "unit": "days", "evidence_ids": weekly_refs,
                         "metric_name": "Average office days", "period": period_label, "group_by": "recorded week"})
        if dept_col:
            rows, refs = [], []
            groups = sorted({str(r.get(dept_col) or "Unspecified") for r in records})
            for dept in groups:
                indices = [i for i, r in enumerate(records) if str(r.get(dept_col) or "Unspecified") == dept]
                nums = [office[i] for i in indices if office[i] is not None]
                if not nums:
                    continue
                metric = fact("Average office days: " + dept, mean(nums), "days", nums, "mean", len(nums))
                refs.append(metric["evidence_id"])
                rows.append([dept, str(len(indices)), f"{mean(nums):.2f}", str(len(nums))])
            rows.sort(key=lambda r: float(r[2]))
            for offset in range(0, len(rows), 6):
                slide("Office days by department" + (" — continued" if offset else ""),
                      "Compare department averages alongside the number of employees with recorded attendance.",
                      ["Leave, role requirements and small teams can affect comparisons; no performance ranking is implied."],
                      table={"headers": ["Department", "Employees", "Avg office days", "Recorded employees"], "rows": rows[offset:offset+6], "evidence_ids": refs})
        if measured:
            bands = [("0–5", 0, 5), ("6–9", 5, 9), ("10–12", 9, 12), ("13–15", 12, 15), ("16–19", 15, 19), ("20+", 19, math.inf)]
            counts = [sum((v >= low if low == 0 else v > low) and v <= high for v in measured) for _, low, high in bands]
            distribution_refs = [fact("Employees with " + b[0] + " office days", n, "employees", [n], "sum")["evidence_id"] for b, n in zip(bands, counts)]
            slide("How recorded office days are distributed", "The bands show recorded office days, without classifying employees as compliant or non-compliant.",
                  ["Missing or negative attendance is outside these bands and needs review."],
                  chart={"type": "bar", "title": "Employees by office-day band", "categories": [b[0] for b in bands],
                         "series": [{"name": "Employees", "values": counts}], "unit": "employees", "evidence_ids": distribution_refs,
                         "metric_name": "Employees by office-day band", "period": period_label, "group_by": "office-day band"})
        exceptions = []
        missing = sum(v is None for v in office)
        if missing:
            exceptions.append(["Missing office-day value", str(missing), "Confirm the source value; it is not treated as zero."])
        negative = [i for i, v in enumerate(office) if v is not None and v < 0]
        if negative:
            exceptions.append(["Negative office days", ", ".join(ids[i] for i in negative[:5]), "Check attendance entries."])
        if final_col:
            negative_final = [i for i, r in enumerate(records) if (_number(r.get(final_col)) or 0) < 0]
            subtraction = [i for i, r in enumerate(records) if office[i] is not None and leave[i] is not None and leave[i] > 0 and _number(r.get(final_col)) is not None and abs(office[i]-leave[i]-_number(r.get(final_col))) < 1e-8]
            if negative_final:
                exceptions.append(["Negative final attendance", ", ".join(ids[i] for i in negative_final[:5]), "Confirm what the final-attendance field means."])
            if subtraction:
                exceptions.append(["Final attendance equals office days minus leave", ", ".join(ids[i] for i in subtraction[:5]), "Check for double subtraction if office days already exclude leave; confirm policy first."])
        check_rows = []
        for name, column, role in [("Office-day totals", att_col, "attendance_col"), ("Leave totals", leave_col, "leave_col")]:
            fields = [getattr(p, role) for p in periods if getattr(p, role)]
            if not column or not fields:
                continue
            eligible, matches, mismatch_ids = 0, 0, []
            for i, r in enumerate(records):
                nums = [_number(r.get(c)) for c in fields]
                total = _number(r.get(column))
                if total is None or any(n is None for n in nums):
                    continue
                eligible += 1
                if abs(sum(nums)-total) < 1e-8:
                    matches += 1
                else:
                    mismatch_ids.append(ids[i])
            check_rows.append([name, str(matches), str(eligible), "Weekly sum agrees with monthly total"])
            if mismatch_ids:
                exceptions.append([name + " differ from weekly sums", ", ".join(mismatch_ids[:5]), "Recheck the formula and weekly entries."])
        for offset in range(0, len(exceptions), 5):
            slide("Attendance entries that need checking" + (" — continued" if offset else ""),
                  "These are source checks for HR review, not conclusions about individual employees.",
                  table={"headers": ["Check", "Affected rows or employee IDs", "Follow-up"], "rows": exceptions[offset:offset+5]})
        if check_rows:
            slide("Do weekly entries agree with monthly totals?", "Only rows with every required value are included in these checks.",
                  ["A matching total verifies arithmetic; it does not verify leave policy or the final-attendance definition."],
                  table={"headers": ["Check", "Matching rows", "Checked rows", "Meaning"], "rows": check_rows})
        slide("What HR should confirm next", "Use the recorded attendance for discussion, then resolve definitions before making compliance decisions.",
              ["Confirm the WFO requirement and working-day calendar.", "Confirm whether leave is recorded in calendar days or working days.",
               "Check flagged entries and the final-attendance formula."])
    theme_id = scope.get("theme_id") or "executive_dark"
    for s in slides:
        s["total_slides"] = len(slides)
    return {"id": "deck_"+uuid.uuid4().hex[:12], "spec_version": "2.0", "theme": THEMES.get(theme_id, THEMES["executive_dark"]),
            "metadata": {"title": "Office attendance review", "theme_id": theme_id, "domain": "Workforce attendance",
                         "audience": scope.get("audience") or "HR managers", "objective": scope.get("objective") or "Attendance review",
                         "file_label": label, "total_records": len(records), "snapshot_hash": (workspace or {}).get("snapshot_hash") or ctx.get("snapshot_hash"),
                         "reporting_period_summary": period_label, "content_contract": "hr_attendance_v1",
                         "created_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                         "brief": {"objective": scope.get("objective") or "Attendance review"}},
            "slides": slides, "evidence_ledger": ledger,
            "coverage_manifest": {"items": [{"evidence_id": e["evidence_id"], "title": e["title"], "disposition": "main_deck"} for e in ledger]},
            "retrieved_context": (workspace or {}).get("retrieved_context", {})}
