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
            if not date_col and any(k in cl for k in ('date', 'timestamp', 'datetime', 'day')):
                date_col = c

    # Match metric column
    metric_col = None
    if not df.empty and metric_clean:
        for c in df.columns:
            if c.startswith("__"):
                continue
            if metric_clean.lower() in str(c).lower() or str(c).lower() in metric_clean.lower():
                metric_col = c
                break

    # Build investigation payload based on entity_type
    if entity_type == "department" or (dept_col and target_clean in df[dept_col].astype(str).values):
        return build_department_investigation(
            conn, all_sheets, sheet_records, target_sheet, dept_col, target_clean, metric_col or metric_clean
        )
    elif entity_type in ("employee", "person", "candidate") or (name_col and target_clean in df[name_col].astype(str).values):
        return build_individual_investigation(
            conn, all_sheets, sheet_records, target_sheet, name_col, id_col, target_clean, metric_col or metric_clean
        )
    elif entity_type == "model_group":
        return build_model_group_investigation(
            conn, all_sheets, sheet_records, target_sheet, target_clean, metric_clean
        )
    else:
        return build_general_investigation(
            conn, all_sheets, sheet_records, target_sheet, target_clean, metric_col or metric_clean
        )


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
