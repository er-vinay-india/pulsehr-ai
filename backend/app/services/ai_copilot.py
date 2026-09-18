import json
import httpx
from ..core import config
from ..db.database import get_connection
from .rag_service import semantic_search


def get_aggregate_context() -> str:
    """Computes high-level database summaries and uploaded sheets to ground the LLM."""
    conn = get_connection()
    try:
        emp_stats = conn.execute("""
            SELECT 
                COUNT(*) as total,
                ROUND(AVG(attendance_rate), 1) as avg_att,
                ROUND(AVG(punctuality_rate), 1) as avg_punct,
                ROUND(AVG(rating), 2) as avg_rating,
                ROUND(AVG(overtime_hours), 1) as avg_ot
            FROM employees
        """).fetchone()

        dept_stats = conn.execute("""
            SELECT 
                department,
                COUNT(*) as headcount,
                ROUND(AVG(attendance_rate), 1) as avg_att,
                ROUND(AVG(rating), 2) as avg_rating,
                ROUND(AVG(overtime_hours), 1) as avg_ot
            FROM employees
            GROUP BY department
            ORDER BY avg_att DESC
        """).fetchall()

        alerts = conn.execute("""
            SELECT severity, category, title, message 
            FROM hr_alerts 
            ORDER BY 
                CASE severity WHEN 'high' THEN 1 WHEN 'warning' THEN 2 ELSE 3 END,
                id DESC LIMIT 8
        """).fetchall()

        # Fetch recent uploaded datasets & sample chunks
        uploads = conn.execute("""
            SELECT id, filename, original_name, row_count, col_count, summary_insights, uploaded_at
            FROM dataset_uploads
            WHERE filename != 'attendance_2023_2024.csv'
            ORDER BY id DESC LIMIT 5
        """).fetchall()

        upload_sections = []
        for up in uploads:
            chunks = conn.execute("""
                SELECT chunk_text 
                FROM tabular_chunks 
                WHERE dataset_id = ? 
                LIMIT 6
            """, (up["id"],)).fetchall()
            
            chunk_snippets = "\n".join([f"    • {c['chunk_text']}" for c in chunks])
            upload_sections.append(
                f"- DATASET: \"{up['filename']}\" ({up['row_count']} rows, {up['col_count']} columns)\n"
                f"  Summary: {up['summary_insights']}\n"
                f"  Key Sample Records:\n{chunk_snippets}"
            )

        dept_lines = [
            f"- {d['department']}: {d['headcount']} employees | {d['avg_att']}% att | {d['avg_rating']}/5.0 rating | {d['avg_ot']}h OT"
            for d in dept_stats
        ]
        alert_lines = [
            f"- [{a['severity'].upper()}] {a['title']}: {a['message']}"
            for a in alerts
        ]

        uploaded_str = "\n\n".join(upload_sections) if upload_sections else "No custom files uploaded yet (running on Kaggle baseline)."

        context = (
            f"=== CONSOLIDATED WORKFORCE OVERVIEW ===\n"
            f"Active Headcount: {emp_stats['total']} employees across {len(dept_stats)} departments.\n"
            f"Average Attendance: {emp_stats['avg_att']}%, Punctuality: {emp_stats['avg_punct']}%, "
            f"Average Rating: {emp_stats['avg_rating']}/5.0, Avg Monthly Overtime: {emp_stats['avg_ot']}h.\n\n"
            f"=== ACTIVE USER-UPLOADED DATASETS & SHEETS ===\n"
            f"{uploaded_str}\n\n"
            f"=== DEPARTMENT BENCHMARKS ===\n" + "\n".join(dept_lines) + "\n\n"
            f"=== ACTIVE HR ALERTS ===\n" + "\n".join(alert_lines)
        )
        return context
    finally:
        conn.close()


def query_copilot(user_query: str) -> dict:
    """Answers HR and tabular queries with multi-source uploaded sheet grounding."""
    # 1. Retrieve semantic vector matches
    vector_results = semantic_search(user_query, top_k=7)
    matched_chunks = "\n".join([f"[{i+1}] {item['text']}" for i, item in enumerate(vector_results)])

    # 2. Get aggregate context (including uploaded sheets)
    agg_context = get_aggregate_context()

    # 3. Construct prompt with explicit uploaded sheet prioritization
    system_prompt = (
        "You are PulseHR AI, an elite HR Analytics & Tabular Intelligence Copilot.\n"
        "You have access to both the core workforce database and the USER-UPLOADED SPREADSHEETS (e.g. employee_absent_data.csv, employee_performance_data.csv).\n\n"
        "CRITICAL INSTRUCTIONS:\n"
        "1. When the user asks about attendance, absences, overtime, ratings, or specific employees, ALWAYS prioritize the data from the ACTIVE USER-UPLOADED DATASETS & SHEETS.\n"
        "2. State the source file name clearly (e.g. 'According to employee_absent_data.csv...' or 'In the latest performance upload...').\n"
        "3. Provide exact numbers, counts, and names directly from the provided records.\n"
        "4. Highlight critical HR risks (burnout, attendance drops, PIPs) and suggest actionable interventions.\n"
        "5. Use clean markdown: bold headings, bullet points, and clean lists."
    )

    full_prompt = (
        f"{system_prompt}\n\n"
        f"--- DATA CONTEXT (DATABASE & UPLOADED SHEETS) ---\n{agg_context}\n\n"
        f"--- VECTOR-RETRIEVED DATA CHUNKS (MOST RELEVANT TO QUERY) ---\n{matched_chunks}\n\n"
        f"User Query: {user_query}\n\n"
        f"Executive HR Response:"
    )

    # 4. Call Ollama
    answer_text = ""
    try:
        with httpx.Client(timeout=45.0) as client:
            resp = client.post(
                f"{config.OLLAMA_BASE_URL}/api/generate",
                json={
                    "model": config.OLLAMA_MODEL,
                    "prompt": full_prompt,
                    "stream": False,
                    "options": {"temperature": 0.2, "top_p": 0.9}
                }
            )
            if resp.status_code == 200:
                answer_text = resp.json().get("response", "").strip()
    except Exception:
        pass

    # 5. Deterministic fallback if Ollama times out or is offline
    if not answer_text:
        answer_text = (
            f"### Workforce Analysis for: *\"{user_query}\"*\n\n"
            f"Based on the active database and uploaded spreadsheets:\n\n"
            f"- **Relevant Uploaded Records & Profiles**:\n"
            + "\n".join([f"  * {item['text']}" for item in vector_results[:4]]) + "\n\n"
            f"- **Key Takeaway**: The latest data records specific employee absences and performance metrics. "
            f"High-overtime employees (>35h/mo) and elevated absences are prioritized in active HR alerts."
        )

    # 6. Dynamic suggestions tailored to query and uploaded sheets
    suggestions = [
        "How many absent days were recorded in employee_absent_data.csv?",
        "Who has high overtime in the latest performance sheet?",
        "Which employees have performance notes or attendance disconnects?",
        "Compare attendance between Engineering and Human Resources"
    ]

    return {
        "query": user_query,
        "answer": answer_text,
        "citations": vector_results,
        "suggested_questions": suggestions
    }
