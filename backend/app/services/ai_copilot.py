import json
import re
import httpx
from ..core import config
from ..db.database import get_connection
from .rag_service import semantic_search


def get_available_models() -> list[dict]:
    """Discovers installed generative models from local Ollama."""
    models = []
    try:
        with httpx.Client(timeout=3.0) as client:
            resp = client.get(f"{config.OLLAMA_BASE_URL}/api/tags")
            if resp.status_code == 200:
                data = resp.json()
                for m in data.get("models", []):
                    name = m.get("name", "")
                    # Filter out embedding models
                    if "embed" in name.lower():
                        continue
                    
                    details = m.get("details", {})
                    family = details.get("family", "")
                    param_size = details.get("parameter_size", "")
                    
                    label = name
                    if "llama3.1" in name.lower():
                        label = f"Meta Llama 3.1 ({param_size}) · High Accuracy & Factual"
                    elif "deepseek" in name.lower():
                        label = f"DeepSeek R1 ({param_size}) · Chain of Thought Reasoning"
                    elif "qwen" in name.lower():
                        label = f"Qwen 2.5 ({param_size}) · Fast Generalist"
                    elif "mistral" in name.lower():
                        label = f"Mistral ({param_size}) · Precise Instruction Following"

                    models.append({
                        "id": name,
                        "name": label,
                        "size_bytes": m.get("size", 0),
                        "parameter_size": param_size
                    })
    except Exception:
        pass

    if not models:
        models.append({
            "id": config.OLLAMA_MODEL,
            "name": f"Default Model ({config.OLLAMA_MODEL})",
            "size_bytes": 0,
            "parameter_size": "7B"
        })

    # Sort so Llama 3.1 or reasoning models appear first
    models.sort(key=lambda x: (0 if "llama" in x["id"].lower() else (1 if "deepseek" in x["id"].lower() else 2)))
    return models


def find_exact_employee_matches(query: str) -> list[dict]:
    """
    Deterministic entity extraction: looks up employees mentioned by code or name,
    and extracts their exact database records and uploaded sheet chunks.
    """
    conn = get_connection()
    try:
        emp_rows = conn.execute("SELECT id, employee_code, name, department, role, attendance_rate, rating, overtime_hours, attrition_risk, summary_profile FROM employees").fetchall()
        matches = []
        q_lower = query.lower()

        for emp in emp_rows:
            code = emp["employee_code"].lower()
            name_parts = emp["name"].lower().split()
            full_name = emp["name"].lower()

            # Match on full name, employee code, or both first and last name
            is_match = False
            if code in q_lower or full_name in q_lower:
                is_match = True
            elif len(name_parts) >= 2 and (name_parts[0] in q_lower and name_parts[1] in q_lower):
                is_match = True

            if is_match:
                # Fetch exact chunks for this employee from uploaded spreadsheets
                emp_chunks = conn.execute("""
                    SELECT DISTINCT chunk_text, sheet_name 
                    FROM tabular_chunks 
                    WHERE (chunk_text LIKE ? OR metadata_json LIKE ?) AND dataset_id IS NOT NULL
                    ORDER BY id DESC
                    LIMIT 3
                """, (f"%{emp['name']}%", f"%\"employee_id\": {emp['id']}%")).fetchall()

                matches.append({
                    "employee": dict(emp),
                    "exact_chunks": [dict(c) for c in emp_chunks]
                })

        return matches
    finally:
        conn.close()


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

        # Fetch recent uploaded datasets & all chunks
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
                LIMIT 10
            """, (up["id"],)).fetchall()
            
            chunk_snippets = "\n".join([f"    • {c['chunk_text']}" for c in chunks])
            upload_sections.append(
                f"- FILE: \"{up['filename']}\" ({up['row_count']} rows, {up['col_count']} cols):\n"
                f"  Summary: {up['summary_insights']}\n"
                f"  Verified Spreadsheet Rows:\n{chunk_snippets}"
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
            f"=== ACTIVE USER-UPLOADED DATASETS & SHEETS (GROUND TRUTH) ===\n"
            f"{uploaded_str}\n\n"
            f"=== DEPARTMENT BENCHMARKS ===\n" + "\n".join(dept_lines) + "\n\n"
            f"=== ACTIVE HR ALERTS ===\n" + "\n".join(alert_lines)
        )
        return context
    finally:
        conn.close()


def query_copilot(user_query: str, selected_model: str | None = None) -> dict:
    """Answers HR queries with deterministic entity extraction and anti-hallucination rules."""
    # 1. Deterministic Entity Extraction
    exact_matches = find_exact_employee_matches(user_query)
    exact_match_section = ""
    if exact_matches:
        lines = []
        for m in exact_matches:
            emp = m["employee"]
            lines.append(
                f"• EMPLOYEE: {emp['name']} ({emp['employee_code']})\n"
                f"  Department: {emp['department']} | Role: {emp['role']}\n"
                f"  Attendance Rate: {emp['attendance_rate']}% | Appraisal Rating: {emp['rating']}/5.0 | Monthly Overtime: {emp['overtime_hours']}h\n"
                f"  Attrition Risk: {emp['attrition_risk']}\n"
                f"  Detailed Profile / Notes: {emp['summary_profile']}"
            )
            for ch in m["exact_chunks"]:
                lines.append(f"  Exact Uploaded Row: {ch['chunk_text']}")
        exact_match_section = "=== VERIFIED EXACT DATABASE RECORDS FOR MENTIONED EMPLOYEE(S) ===\n" + "\n\n".join(lines) + "\n\n"

    # 2. Retrieve semantic vector matches
    vector_results = semantic_search(user_query, top_k=7)
    matched_chunks = "\n".join([f"[{i+1}] {item['text']}" for i, item in enumerate(vector_results)])

    # 3. Get aggregate context
    agg_context = get_aggregate_context()

    # Determine which model to run
    available = get_available_models()
    avail_ids = [m["id"] for m in available]
    
    target_model = selected_model if selected_model and selected_model in avail_ids else (
        "llama3.1:8b" if "llama3.1:8b" in avail_ids else config.OLLAMA_MODEL
    )

    # 4. Strict prompt engineering: Anti-hallucination and exact factual retrieval
    system_prompt = (
        "You are PulseHR AI, an elite HR Analytics & Tabular Intelligence Copilot.\n\n"
        "STRICT ANTI-HALLUCINATION & FACTUAL ACCURACY RULES:\n"
        "1. GROUND TRUTH: Look at the VERIFIED EXACT DATABASE RECORDS and ACTIVE USER-UPLOADED SPREADSHEET ROWS first.\n"
        "2. ZERO ESTIMATIONS: NEVER calculate, invent, extrapolate, or assume unstated numbers.\n"
        "   - DO NOT assume a 20-day work month or multiply attendance percentages to guess absences.\n"
        "   - If a sheet records 'Absent ( no of days ): 2', state EXACTLY '2 days absent'.\n"
        "   - If a sheet records 'Absent ( no of days ): 5', state EXACTLY '5 days absent'.\n"
        "3. SOURCE CITATION: Always cite the exact source file (e.g. 'In employee_absent_data.csv' or 'In the employee record').\n"
        "4. DIRECT & CONCISE: Answer the specific question clearly first, then provide relevant context or HR recommendations.\n"
        "5. Format using clean markdown: bold employee names, bullet points, and clean numbers."
    )

    full_prompt = (
        f"{system_prompt}\n\n"
        f"{exact_match_section}"
        f"--- DATA CONTEXT (DATABASE & UPLOADED SPREADSHEETS) ---\n{agg_context}\n\n"
        f"--- VECTOR RETRIEVED CHUNKS ---\n{matched_chunks}\n\n"
        f"User Query: {user_query}\n\n"
        f"Factual Executive Response:"
    )

    # 5. Query Ollama
    answer_text = ""
    try:
        with httpx.Client(timeout=60.0) as client:
            resp = client.post(
                f"{config.OLLAMA_BASE_URL}/api/generate",
                json={
                    "model": target_model,
                    "prompt": full_prompt,
                    "stream": False,
                    "options": {"temperature": 0.1, "top_p": 0.8} # Lower temperature to prevent hallucination
                }
            )
            if resp.status_code == 200:
                answer_text = resp.json().get("response", "").strip()
    except Exception:
        pass

    # 6. High-accuracy deterministic fallback if Ollama times out
    if not answer_text:
        if exact_matches:
            lines = []
            for m in exact_matches:
                emp = m["employee"]
                lines.append(
                    f"- **{emp['name']} ({emp['employee_code']})**:\n"
                    f"  * Department: {emp['department']} · Role: {emp['role']}\n"
                    f"  * Attendance: {emp['attendance_rate']}% · Rating: {emp['rating']}/5.0 · Overtime: {emp['overtime_hours']}h\n"
                    f"  * Profile & Notes: {emp['summary_profile']}"
                )
            answer_text = (
                f"### Verified Records for: *\"{user_query}\"*\n\n"
                + "\n".join(lines)
            )
        else:
            answer_text = (
                f"### Analysis for: *\"{user_query}\"*\n\n"
                f"Based on the active database and uploaded spreadsheets:\n\n"
                + "\n".join([f"- {c['text']}" for c in vector_results[:4]])
            )

    # 7. Curate high-confidence, non-repetitive citations for the UI
    display_citations = []
    if exact_matches:
        # When specific employees are mentioned, display only their verified ground truth and exact rows
        for m in exact_matches:
            emp = m["employee"]
            for ch in m["exact_chunks"]:
                display_citations.append({
                    "chunk_id": f"exact-row-{emp['id']}",
                    "type": "exact_match",
                    "is_exact": True,
                    "relevance_score": 1.0,
                    "employee_name": emp["name"],
                    "employee_code": emp["employee_code"],
                    "department": emp["department"],
                    "text": ch["chunk_text"],
                    "sheet_name": ch.get("sheet_name", "Uploaded Sheet"),
                    "metadata": {
                        "employee_id": emp["id"],
                        "employee_name": emp["name"],
                        "name": emp["name"],
                        "employee_code": emp["employee_code"],
                        "department": emp["department"],
                    }
                })
            # Also add verified database baseline
            display_citations.append({
                "chunk_id": f"emp-profile-{emp['id']}",
                "type": "exact_match",
                "is_exact": True,
                "relevance_score": 1.0,
                "employee_name": emp["name"],
                "employee_code": emp["employee_code"],
                "department": emp["department"],
                "text": f"Verified Database Profile: {emp['name']} ({emp['employee_code']}), {emp['role']} in {emp['department']} · Attendance: {emp['attendance_rate']}% · Rating: {emp['rating']}/5.0 · Overtime: {emp['overtime_hours']}h · Risk: {emp['attrition_risk']}",
                "sheet_name": "Workforce DB",
                "metadata": {
                    "employee_id": emp["id"],
                    "employee_name": emp["name"],
                    "name": emp["name"],
                    "employee_code": emp["employee_code"],
                    "department": emp["department"],
                }
            })
    else:
        # General query: filter by relevance threshold, deduplicate, and limit to top 3
        seen_keys = set()
        for v in vector_results:
            if v["relevance_score"] < 0.55:
                continue
            meta = v.get("metadata", {})
            dedup_key = meta.get("employee_code") or meta.get("name") or v["text"][:60]
            if dedup_key in seen_keys:
                continue
            seen_keys.add(dedup_key)

            display_citations.append({
                "chunk_id": v["chunk_id"],
                "type": "vector_search",
                "is_exact": False,
                "relevance_score": v["relevance_score"],
                "employee_name": meta.get("employee_name") or meta.get("name"),
                "employee_code": meta.get("employee_code"),
                "department": meta.get("department"),
                "text": v["text"],
                "sheet_name": v.get("sheet_name", "Vector Chunk"),
                "metadata": meta
            })
            if len(display_citations) >= 3:
                break

    suggestions = [
        "How many absent days were recorded in employee_absent_data.csv?",
        "Who has high overtime in the latest performance sheet?",
        "Compare attendance between Engineering and Human Resources",
        "Which employees have performance notes or attendance disconnects?"
    ]

    return {
        "query": user_query,
        "model_used": target_model,
        "answer": answer_text,
        "exact_matches": [m["employee"]["name"] for m in exact_matches],
        "citations": display_citations,
        "suggested_questions": suggestions
    }
