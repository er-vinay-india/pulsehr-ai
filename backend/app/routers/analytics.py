from fastapi import APIRouter
from ..db.database import get_connection

router = APIRouter(prefix="/api/analytics", tags=["analytics"])

@router.get("/overview")
def get_analytics_overview():
    conn = get_connection()
    try:
        emp_stats = conn.execute("""
            SELECT 
                COUNT(*) as total_employees,
                ROUND(AVG(attendance_rate), 1) as avg_attendance,
                ROUND(AVG(punctuality_rate), 1) as avg_punctuality,
                ROUND(AVG(rating), 2) as avg_rating,
                ROUND(AVG(overtime_hours), 1) as avg_overtime_hours,
                SUM(CASE WHEN attrition_risk = 'High' THEN 1 ELSE 0 END) as high_risk_count,
                SUM(CASE WHEN rating >= 4.5 THEN 1 ELSE 0 END) as top_performers_count
            FROM employees
        """).fetchone()

        dept_stats = conn.execute("""
            SELECT 
                department,
                COUNT(*) as headcount,
                ROUND(AVG(attendance_rate), 1) as avg_attendance,
                ROUND(AVG(punctuality_rate), 1) as avg_punctuality,
                ROUND(AVG(rating), 2) as avg_rating,
                ROUND(AVG(overtime_hours), 1) as avg_overtime
            FROM employees
            GROUP BY department
            ORDER BY avg_attendance DESC
        """).fetchall()

        alerts = conn.execute("""
            SELECT id, severity, category, title, message, employee_id, metric_value, created_at
            FROM hr_alerts
            ORDER BY 
                CASE severity WHEN 'high' THEN 1 WHEN 'warning' THEN 2 ELSE 3 END,
                id DESC
            LIMIT 12
        """).fetchall()

        rating_dist = conn.execute("""
            SELECT 
                CASE 
                    WHEN rating >= 4.5 THEN '4.5 - 5.0 (Elite)'
                    WHEN rating >= 4.0 THEN '4.0 - 4.4 (Exceeds)'
                    WHEN rating >= 3.5 THEN '3.5 - 3.9 (Meets)'
                    ELSE 'Below 3.5 (Needs Support)'
                END as bucket,
                COUNT(*) as count
            FROM employees
            GROUP BY bucket
            ORDER BY count DESC
        """).fetchall()

        # Ingested datasets provenance
        recent_uploads = conn.execute("""
            SELECT id, filename, original_name, row_count, col_count, uploaded_at
            FROM dataset_uploads
            ORDER BY id DESC
        """).fetchall()

        latest_upload = None
        for u in recent_uploads:
            if u["filename"] != "attendance_2023_2024.csv":
                latest_upload = dict(u)
                break

        return {
            "stats": dict(emp_stats),
            "departments": [dict(d) for d in dept_stats],
            "alerts": [dict(a) for a in alerts],
            "rating_distribution": [dict(r) for r in rating_dist],
            "sources": [dict(u) for u in recent_uploads],
            "latest_upload": latest_upload
        }
    finally:
        conn.close()

@router.get("/departments")
def get_departments():
    conn = get_connection()
    try:
        rows = conn.execute("""
            SELECT 
                department,
                COUNT(*) as headcount,
                ROUND(AVG(attendance_rate), 1) as avg_attendance,
                ROUND(AVG(rating), 2) as avg_rating,
                ROUND(AVG(overtime_hours), 1) as avg_overtime
            FROM employees
            GROUP BY department
            ORDER BY department ASC
        """).fetchall()
        return {"departments": [dict(r) for r in rows]}
    finally:
        conn.close()

@router.get("/alerts")
def get_alerts(severity: str | None = None):
    conn = get_connection()
    try:
        query = "SELECT id, severity, category, title, message, employee_id, metric_value, created_at FROM hr_alerts"
        params = []
        if severity:
            query += " WHERE severity = ?"
            params.append(severity)
        query += " ORDER BY id DESC"
        rows = conn.execute(query, params).fetchall()
        return {"alerts": [dict(r) for r in rows]}
    finally:
        conn.close()
