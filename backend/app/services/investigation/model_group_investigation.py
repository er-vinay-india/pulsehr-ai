"""Model group, Bradford factor, and talent risk investigation builders."""

import pandas as pd
from .investigation_common import clean_val


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
