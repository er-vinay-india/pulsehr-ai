import re
import math
import pandas as pd
from ..core import config
from ..db.database import get_connection

def parse_percentage(val) -> float | None:
    if val is None or pd.isna(val):
        return None
    val_str = str(val).strip().replace("%", "")
    try:
        num = float(val_str)
        if 0.0 <= num <= 1.0:
            num *= 100.0
        return round(num, 1)
    except Exception:
        return None

def parse_rating(val) -> float | None:
    if val is None or pd.isna(val):
        return None
    val_str = str(val).strip()
    if "/" in val_str:
        val_str = val_str.split("/")[0].strip()
    try:
        num = float(val_str)
        return min(5.0, max(1.0, round(num, 1)))
    except Exception:
        return None

def parse_float_val(val) -> float | None:
    if val is None or pd.isna(val):
        return None
    try:
        return round(float(str(val).strip()), 1)
    except Exception:
        return None

def find_column(columns: list[str], target_keywords: list[str]) -> str | None:
    for col in columns:
        col_clean = re.sub(r"[^a-zA-Z0-9]", "", col.lower())
        for kw in target_keywords:
            kw_clean = re.sub(r"[^a-zA-Z0-9]", "", kw.lower())
            if kw_clean in col_clean:
                return col
    return None

def merge_uploaded_sheet_into_database(dataset_id: int, df: pd.DataFrame, filename: str) -> dict:
    """
    Intelligently maps columns from an uploaded spreadsheet, updates/inserts matching employees
    in the `employees` table, recalculates metrics, and triggers new HR risk alerts.
    """
    conn = get_connection()
    try:
        cols = list(df.columns)
        id_col = find_column(cols, ["employeeid", "empid", "id", "code"])
        name_col = find_column(cols, ["employeename", "name", "fullname"])
        dept_col = find_column(cols, ["department", "dept", "division"])
        role_col = find_column(cols, ["role", "jobtitle", "position", "designation"])
        att_col = find_column(cols, ["attendancerate", "attendance", "attpct"])
        absent_col = find_column(cols, ["absent", "absences", "leaves", "absentdays"])
        rating_col = find_column(cols, ["rating", "performancescore", "score", "appraisal"])
        ot_col = find_column(cols, ["overtimehours", "overtime", "ot"])
        risk_col = find_column(cols, ["risklevel", "risk", "attritionrisk"])
        notes_col = find_column(cols, ["notes", "remarks", "comments", "feedback"])

        updated_count = 0
        inserted_count = 0
        new_alerts = []

        for idx, row in df.iterrows():
            code_val = str(row[id_col]).strip() if id_col and pd.notna(row.get(id_col)) else None
            name_val = str(row[name_col]).strip() if name_col and pd.notna(row.get(name_col)) else None

            if not code_val and not name_val:
                continue

            # Look up existing employee
            emp = None
            if code_val:
                emp = conn.execute("SELECT * FROM employees WHERE UPPER(employee_code) = ?", (code_val.upper(),)).fetchone()
            if not emp and name_val:
                emp = conn.execute("SELECT * FROM employees WHERE LOWER(name) = ?", (name_val.lower(),)).fetchone()

            # Extracted values from row
            new_att = parse_percentage(row.get(att_col)) if att_col else None
            new_absent = parse_float_val(row.get(absent_col)) if absent_col else None
            new_rating = parse_rating(row.get(rating_col)) if rating_col else None
            new_ot = parse_float_val(row.get(ot_col)) if ot_col else None
            new_risk = str(row.get(risk_col)).strip() if risk_col and pd.notna(row.get(risk_col)) else None
            new_notes = str(row.get(notes_col)).strip() if notes_col and pd.notna(row.get(notes_col)) else None

            if emp:
                emp_id = emp["id"]
                current_att = new_att if new_att is not None else emp["attendance_rate"]
                current_rating = new_rating if new_rating is not None else emp["rating"]
                current_ot = new_ot if new_ot is not None else emp["overtime_hours"]
                current_risk = new_risk if new_risk in ["Low", "Moderate", "High", "Warning"] else emp["attrition_risk"]
                if current_risk == "Warning":
                    current_risk = "Moderate"

                # Update attendance rate based on absent days if absent_days provided and total_days exists
                if new_absent is not None and new_att is None:
                    total_d = emp["total_days"] or 20
                    pres_d = max(0, total_d - int(new_absent))
                    current_att = round((pres_d / total_d) * 100.0, 1)

                updated_profile = emp["summary_profile"] or ""
                if new_notes and new_notes not in updated_profile:
                    updated_profile += f" [Updated via {filename}: {new_notes}]"
                if new_absent is not None:
                    updated_profile += f" [Uploaded Absences: {int(new_absent)} days]"

                conn.execute("""
                    UPDATE employees
                    SET attendance_rate = ?,
                        rating = ?,
                        overtime_hours = ?,
                        attrition_risk = ?,
                        summary_profile = ?
                    WHERE id = ?
                """, (current_att, current_rating, current_ot, current_risk, updated_profile, emp_id))

                # Check for new alerts triggered by uploaded figures
                if current_ot > 25 and current_rating >= 4.5:
                    new_alerts.append((
                        "high", "burnout",
                        f"Severe Overtime Alert ({filename}): {emp['name']}",
                        f"Updated data shows {current_ot}h monthly overtime with high rating ({current_rating}/5.0). Immediate retention priority.",
                        emp_id, current_ot
                    ))
                elif new_absent and new_absent >= 5:
                    new_alerts.append((
                        "high", "attendance_drop",
                        f"Elevated Absence Alert ({filename}): {emp['name']}",
                        f"Uploaded record indicates {int(new_absent)} absent days in {emp['department']}.",
                        emp_id, new_absent
                    ))
                elif current_att < 85.0 and current_rating >= 4.5:
                    new_alerts.append((
                        "warning", "rating_disconnect",
                        f"Attendance Disconnect ({filename}): {emp['name']}",
                        f"Attendance at {current_att}% with high performance rating ({current_rating}/5.0).",
                        emp_id, current_att
                    ))

                updated_count += 1
            else:
                # Insert new employee if not currently in database
                dept_val = str(row.get(dept_col)).strip() if dept_col and pd.notna(row.get(dept_col)) else "General"
                role_val = str(row.get(role_col)).strip() if role_col and pd.notna(row.get(role_col)) else "Associate"
                emp_name = name_val or f"Employee {code_val}"
                emp_code = code_val or f"EMP-U{idx+1:03d}"
                att_val = new_att or 94.0
                rating_val = new_rating or 3.8
                ot_val = new_ot or 0.0
                risk_val = new_risk or "Low"

                summary = f"{emp_name} ({emp_code}) is a {role_val} in {dept_val}. Uploaded from {filename}. Attendance: {att_val}%, Rating: {rating_val}/5.0."
                cursor = conn.execute("""
                    INSERT INTO employees (
                        employee_code, name, department, role, attendance_rate, rating, overtime_hours, attrition_risk, summary_profile
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (emp_code, emp_name, dept_val, role_val, att_val, rating_val, ot_val, risk_val, summary))
                emp_id = cursor.lastrowid
                inserted_count += 1

        # Insert new alerts
        if new_alerts:
            conn.executemany("""
                INSERT INTO hr_alerts (severity, category, title, message, employee_id, metric_value)
                VALUES (?, ?, ?, ?, ?, ?)
            """, new_alerts)

        conn.commit()
        return {
            "updated_employees": updated_count,
            "inserted_employees": inserted_count,
            "new_alerts_count": len(new_alerts),
            "filename": filename
        }
    finally:
        conn.close()
