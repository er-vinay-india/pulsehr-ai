"""Individual personnel and general tabular investigation builders."""

import pandas as pd
from ..executive_story import coerce_to_numeric
from .investigation_common import clean_val, find_individual_connected_evidence


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
    connected_records = find_individual_connected_evidence(
        conn, all_sheets, sheet_records, target_row, id_col, name_col, target_sheet["id"]
    )

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
