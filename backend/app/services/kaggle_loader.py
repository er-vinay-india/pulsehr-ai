import datetime
import math
import os
import random
from pathlib import Path
import pandas as pd

from ..core import config
from ..db.database import get_connection

FIRST_NAMES = [
    "Alex", "Priya", "Marcus", "Elena", "Jordan", "Sarah", "Liam", "Aisha", 
    "Carlos", "Zoe", "David", "Ananya", "Hiroshi", "Maya", "Daniel", "Chloe", 
    "Rohan", "Fatima", "Ethan", "Olivia", "Vikram", "Sofia", "Lucas", "Leila", 
    "Noah", "Emma", "Arjun", "Amara", "Gabriel", "Isabella", "Kavita", "Mateo", 
    "Zara", "Julian", "Camila", "Dev", "Mia", "Leo", "Nadia", "Siddharth",
    "Hannah", "Sora", "Layla", "Arthur", "Freja", "Sanjay", "Tara", "Felix"
]

LAST_NAMES = [
    "Mercer", "Patel", "Vance", "Rostova", "Lee", "Jenkins", "Chen", "Al-Mansoor",
    "Gomez", "Washington", "Sharma", "Tanaka", "Sinclair", "Kowalski", "Kim", 
    "O'Connor", "Dubois", "Nakamura", "Alvarez", "Gupta", "Lindqvist", "Novak", 
    "Santos", "Chowdhury", "Morales", "Johansson", "Bhatt", "Kapoor", "Muller", 
    "Schneider", "Adler", "Bergman", "Castillo", "Moretti", "Kaur", "Ito"
]

DEPARTMENTS = [
    ("Engineering", ["Principal Architect", "Senior Staff Engineer", "Full Stack Engineer", "DevOps Specialist", "QA Automation Lead"]),
    ("Product & Design", ["Product Director", "Senior Product Manager", "UI/UX Lead", "Design System Architect", "Product Owner"]),
    ("Sales & Enterprise", ["VP Sales", "Enterprise Account Executive", "Solutions Consultant", "Sales Development Rep", "Customer Success Lead"]),
    ("Marketing & Growth", ["Growth Director", "Content Strategist", "Performance Marketer", "Brand Specialist", "SEO Lead"]),
    ("Human Resources", ["HR Business Partner", "Talent Acquisition Lead", "People Ops Manager", "L&D Specialist", "Total Rewards Lead"]),
    ("Finance & Strategy", ["Financial Controller", "Senior FP&A Analyst", "Strategy Consultant", "Accounting Lead", "Risk Analyst"]),
    ("Operations", ["Head of Operations", "Supply Chain Analyst", "IT Systems Admin", "Facilities Manager", "Security Officer"])
]

def generate_employee_name(emp_id: int) -> str:
    rnd = random.Random(1000 + emp_id)
    first = rnd.choice(FIRST_NAMES)
    last = rnd.choice(LAST_NAMES)
    return f"{first} {last}"

def parse_punch_record(val: str, expected_start: str = "08:45"):
    if val is None or str(val).strip() in ("", "0", "nan", "None"):
        return None, None, 0.0, False, False
    
    val_str = str(val).strip()
    if "-" in val_str:
        parts = val_str.split("-")
        try:
            t1 = datetime.datetime.strptime(parts[0], "%H:%M")
            t2 = datetime.datetime.strptime(parts[1], "%H:%M")
            dur = (t2 - t1).total_seconds() / 3600.0
            if dur < 0:
                dur += 24.0
            std_t = datetime.datetime.strptime(expected_start, "%H:%M")
            is_late = (t1 - std_t).total_seconds() > 900
            return parts[0], parts[1], float(round(dur, 2)), bool(is_late), True
        except Exception:
            return None, None, 8.0, False, True
    
    return "08:45", "16:45", 8.0, False, True

def load_and_seed_kaggle_dataset(force: bool = False):
    conn = get_connection()
    try:
        count = conn.execute("SELECT COUNT(*) FROM employees").fetchone()[0]
        if count > 0 and not force:
            return {"status": "already_seeded", "employees_count": count}

        dataset_path = config.KAGGLE_LOCAL_CACHE
        if not dataset_path.exists() or not (dataset_path / "employees.csv").exists():
            import kagglehub
            dataset_path = Path(kagglehub.dataset_download(config.KAGGLE_DATASET))

        emp_csv = dataset_path / "employees.csv"
        att_csv = dataset_path / "attendance_2023_2024.csv"
        leaves_csv = dataset_path / "attendance_2023_2024_bad_with_leaves.csv"
        hlth_leaves_csv = dataset_path / "attendance_2023_2024_healthy_with_leaves.csv"

        emp_df = pd.read_csv(emp_csv)
        att_df = pd.read_csv(att_csv)
        bad_leaves_df = pd.read_csv(leaves_csv) if leaves_csv.exists() else None
        hlth_leaves_df = pd.read_csv(hlth_leaves_csv) if hlth_leaves_csv.exists() else None

        conn.execute("DELETE FROM attendance_records")
        conn.execute("DELETE FROM hr_alerts")
        conn.execute("DELETE FROM employees")
        conn.execute("DELETE FROM dataset_uploads")

        total_days = int(len(att_df))
        recent_days = att_df.tail(45)

        employees_data = []
        alerts_to_insert = []

        for idx, row in emp_df.iterrows():
            emp_id = int(row["id"])
            col_name = f"Person_{emp_id}"
            
            dept_idx = emp_id % len(DEPARTMENTS)
            dept_name, roles = DEPARTMENTS[dept_idx]
            role_title = roles[(emp_id // len(DEPARTMENTS)) % len(roles)]
            std_start = str(row.get("start_time", "08:45"))

            is_variable = (emp_id % 3 == 0) or (emp_id in [7, 14, 23, 42, 59, 88])
            is_burnout = (emp_id in [5, 12, 28, 45, 62, 79, 91])
            is_remote_star = (emp_id in [9, 18, 33, 54, 71])

            if col_name in att_df.columns:
                raw_punches = att_df[col_name].dropna().tolist()
                
                if is_variable and bad_leaves_df is not None and col_name in bad_leaves_df.columns:
                    leave_samples = int((bad_leaves_df[col_name] == "0").sum())
                    present_days = int(max(int(total_days * 0.76), total_days - leave_samples))
                elif hlth_leaves_df is not None and col_name in hlth_leaves_df.columns:
                    leave_samples = int((hlth_leaves_df[col_name] == "0").sum())
                    present_days = int(max(int(total_days * 0.90), total_days - leave_samples))
                else:
                    present_days = int(total_days * 0.96)

                att_rate = float(round((present_days / total_days) * 100.0, 1))

                durations = []
                late_count = 0
                for p in raw_punches[:100]:
                    cin, cout, dur, is_late, is_pres = parse_punch_record(p, std_start)
                    if dur > 0:
                        durations.append(dur)
                    if is_late:
                        late_count += 1
                
                base_hours = float(round(sum(durations) / max(1, len(durations)), 2)) if durations else 8.0
                if is_burnout:
                    avg_hours = float(round(base_hours + 1.6, 2))
                    overtime_monthly = float(round((avg_hours - 8.0) * 22, 1))
                elif is_variable:
                    avg_hours = float(round(max(7.2, base_hours - 0.5), 2))
                    overtime_monthly = 0.0
                else:
                    avg_hours = float(round(base_hours + 0.2, 2))
                    overtime_monthly = float(max(0.0, round((avg_hours - 8.0) * 22, 1)))

                punct_rate = float(max(68.0, round(((100 - late_count) / 100.0) * 100.0, 1)))
            else:
                att_rate = 94.0
                punct_rate = 91.0
                avg_hours = 8.1
                overtime_monthly = 6.0
                present_days = int(total_days * 0.94)
                late_count = 8

            if is_burnout:
                rating = float(round(random.Random(4000 + emp_id).uniform(4.5, 4.9), 1))
                attrition_risk = "High"
                emp_name = generate_employee_name(emp_id)
                alerts_to_insert.append((
                    "high", "burnout",
                    f"Severe Overtime & Burnout: {emp_name}",
                    f"Averaging {avg_hours}h daily ({overtime_monthly}h overtime/mo) with high rating ({rating}/5.0). Immediate workload rebalance needed.",
                    emp_id, overtime_monthly
                ))
            elif is_remote_star:
                att_rate = float(round(random.Random(5000 + emp_id).uniform(79.0, 84.5), 1))
                rating = float(round(random.Random(6000 + emp_id).uniform(4.6, 5.0), 1))
                attrition_risk = "Moderate"
                emp_name = generate_employee_name(emp_id)
                alerts_to_insert.append((
                    "warning", "rating_disconnect",
                    f"Attendance Disconnect: {emp_name}",
                    f"Low office attendance ({att_rate}%) but top-tier performance rating ({rating}/5.0). High remote leverage, verify policy alignment.",
                    emp_id, att_rate
                ))
            elif is_variable and att_rate < 82.0:
                rating = float(round(random.Random(7000 + emp_id).uniform(2.1, 2.9), 1))
                attrition_risk = "High"
                emp_name = generate_employee_name(emp_id)
                alerts_to_insert.append((
                    "high", "attendance_drop",
                    f"Attendance & Performance PIP: {emp_name}",
                    f"Low attendance ({att_rate}%) and subpar rating ({rating}/5.0) in {dept_name}. Candidate for Performance Improvement Plan.",
                    emp_id, rating
                ))
            else:
                rating = float(round(random.Random(8000 + emp_id).gauss(3.9, 0.4), 1))
                rating = float(min(4.9, max(3.0, rating)))
                attrition_risk = "Low" if rating >= 3.6 else "Moderate"

            tenure = float(round(random.Random(3000 + emp_id).uniform(1.2, 7.8), 1))
            salary_band = "Executive" if tenure > 5.5 else ("Senior" if tenure > 3.0 else "Mid")
            emp_name = generate_employee_name(emp_id)
            code = f"EMP-{emp_id+1:03d}"

            summary = (
                f"{emp_name} ({code}) is a {role_title} in the {dept_name} department. "
                f"Tenure is {tenure} years ({salary_band} level). "
                f"Annual attendance rate is {att_rate}% with {punct_rate}% punctuality. "
                f"Averages {avg_hours} hours per day with {overtime_monthly} hrs monthly overtime. "
                f"Performance rating is {rating}/5.0 with {attrition_risk} attrition risk."
            )

            employees_data.append((
                int(emp_id), code, emp_name, dept_name, role_title,
                std_start, str(row.get("end_time", "16:45")),
                int(total_days), int(present_days), int(late_count),
                float(att_rate), float(punct_rate), float(avg_hours), float(overtime_monthly),
                float(rating), attrition_risk, float(tenure), salary_band,
                "Active", summary
            ))

        conn.executemany("""
            INSERT INTO employees (
                id, employee_code, name, department, role,
                start_time, end_time, total_days, present_days,
                late_days, attendance_rate, punctuality_rate,
                avg_daily_hours, overtime_hours, rating,
                attrition_risk, tenure_years, salary_band,
                status, summary_profile
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, employees_data)

        conn.executemany("""
            INSERT INTO hr_alerts (severity, category, title, message, employee_id, metric_value)
            VALUES (?, ?, ?, ?, ?, ?)
        """, alerts_to_insert)

        punch_records = []
        for _, row in recent_days.iterrows():
            date_str = str(row["Date"])
            for emp_id in range(min(50, len(emp_df))):
                col = f"Person_{emp_id}"
                val = row.get(col)
                cin, cout, dur, is_late, is_pres = parse_punch_record(val)
                if is_pres:
                    punch_records.append((
                        date_str, int(emp_id), cin, cout, float(dur), 1 if is_late else 0, "Present"
                    ))
                else:
                    punch_records.append((
                        date_str, int(emp_id), None, None, 0.0, 0, "Leave"
                    ))

        conn.executemany("""
            INSERT INTO attendance_records (date, employee_id, clock_in, clock_out, duration_hours, is_late, status)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, punch_records)

        conn.execute("""
            INSERT INTO dataset_uploads (
                filename, original_name, file_type, sheet_count, row_count, col_count,
                columns_json, sample_preview_json, summary_insights
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            "attendance_2023_2024.csv",
            "Kaggle: Employee Attendance & Performance Ratings (yasirub/employee-attendance-ratings)",
            "csv", 1, int(len(att_df)), int(len(att_df.columns)),
            '["Date", "Person_0...Person_99", "start_time", "end_time", "std_dev_start"]',
            '{"cohorts": "100 employees across 7 departments with 712 punch logs"}',
            f"Synthesized 100 enterprise employee profiles. Identified {len(alerts_to_insert)} high-priority HR alerts (Burnout, Attendance Disconnects, Attrition Risks)."
        ))

        conn.commit()
        return {
            "status": "success",
            "employees_count": len(employees_data),
            "alerts_count": len(alerts_to_insert),
            "punches_sample_count": len(punch_records)
        }
    finally:
        conn.close()
