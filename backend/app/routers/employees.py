from fastapi import APIRouter, HTTPException, Query
from ..db.database import get_connection

router = APIRouter(prefix="/api/employees", tags=["employees"])

@router.get("")
def list_employees(
    search: str | None = None,
    department: str | None = None,
    risk: str | None = None,
    min_rating: float | None = None,
    sort_by: str = "id",
    sort_dir: str = "asc",
    page: int = 1,
    limit: int = 25
):
    conn = get_connection()
    try:
        where_clauses = ["1=1"]
        params = []

        if search:
            where_clauses.append("(name LIKE ? OR employee_code LIKE ? OR role LIKE ?)")
            pat = f"%{search.strip()}%"
            params.extend([pat, pat, pat])
        
        if department and department != "All":
            where_clauses.append("department = ?")
            params.append(department)

        if risk and risk != "All":
            where_clauses.append("attrition_risk = ?")
            params.append(risk)

        if min_rating is not None:
            where_clauses.append("rating >= ?")
            params.append(min_rating)

        where_sql = " AND ".join(where_clauses)
        total_count = conn.execute(f"SELECT COUNT(*) FROM employees WHERE {where_sql}", params).fetchone()[0]

        valid_sort_cols = {
            "id": "id",
            "name": "name",
            "department": "department",
            "attendance_rate": "attendance_rate",
            "punctuality_rate": "punctuality_rate",
            "rating": "rating",
            "overtime_hours": "overtime_hours",
            "attrition_risk": "attrition_risk"
        }
        order_col = valid_sort_cols.get(sort_by, "id")
        order_direction = "DESC" if sort_dir.lower() == "desc" else "ASC"

        offset = (page - 1) * limit
        query_sql = f"""
            SELECT 
                id, employee_code, name, department, role,
                start_time, end_time, total_days, present_days,
                late_days, attendance_rate, punctuality_rate,
                avg_daily_hours, overtime_hours, rating,
                attrition_risk, tenure_years, salary_band,
                status, summary_profile
            FROM employees
            WHERE {where_sql}
            ORDER BY {order_col} {order_direction}
            LIMIT ? OFFSET ?
        """
        rows = conn.execute(query_sql, params + [limit, offset]).fetchall()

        return {
            "total": total_count,
            "page": page,
            "limit": limit,
            "pages": (total_count + limit - 1) // limit if limit > 0 else 1,
            "employees": [dict(r) for r in rows]
        }
    finally:
        conn.close()

@router.get("/{emp_id}")
def get_employee_detail(emp_id: int):
    conn = get_connection()
    try:
        row = conn.execute("SELECT * FROM employees WHERE id = ?", (emp_id,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Employee not found")

        punches = conn.execute("""
            SELECT date, clock_in, clock_out, duration_hours, is_late, status
            FROM attendance_records
            WHERE employee_id = ?
            ORDER BY date DESC
            LIMIT 45
        """, (emp_id,)).fetchall()

        alerts = conn.execute("""
            SELECT id, severity, category, title, message, created_at
            FROM hr_alerts
            WHERE employee_id = ?
            ORDER BY id DESC
        """, (emp_id,)).fetchall()

        return {
            "employee": dict(row),
            "recent_punches": [dict(p) for p in punches],
            "alerts": [dict(a) for a in alerts]
        }
    finally:
        conn.close()
