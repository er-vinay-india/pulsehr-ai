import json
import math
import re
import struct
import httpx
import pandas as pd
from pathlib import Path

from ..core import config
from ..db.database import get_connection


def fallback_embedding(text: str, dim: int = config.EMBEDDING_DIM) -> list[float]:
    """Deterministic, unit-normalized dense embedding fallback when Ollama is unavailable."""
    vec = [0.0] * dim
    words = text.lower().split()
    for w_idx, word in enumerate(words):
        h = 0
        for char in word:
            h = (h * 31 + ord(char)) % 1000000007
        bucket = h % dim
        weight = 1.0 / (1.0 + math.log(1 + w_idx))
        vec[bucket] += weight
    
    norm = math.sqrt(sum(x * x for x in vec))
    if norm > 1e-9:
        vec = [x / norm for x in vec]
    else:
        vec[0] = 1.0
    return vec


def get_embedding(text: str) -> list[float]:
    """Obtain 768-dim embedding via Ollama nomic-embed-text or fallback."""
    clean_text = (text or "").strip()
    if not clean_text:
        return [0.0] * config.EMBEDDING_DIM
    
    try:
        with httpx.Client(timeout=5.0) as client:
            resp = client.post(
                f"{config.OLLAMA_BASE_URL}/api/embeddings",
                json={"model": config.OLLAMA_EMBED_MODEL, "prompt": clean_text[:2000]}
            )
            if resp.status_code == 200:
                data = resp.json()
                emb = data.get("embedding", [])
                if len(emb) == config.EMBEDDING_DIM:
                    return emb
    except Exception:
        pass
    
    return fallback_embedding(clean_text, config.EMBEDDING_DIM)


def pack_vector(vec: list[float]) -> bytes:
    return struct.pack(f"{len(vec)}f", *vec)


def index_all_employees():
    """Indexes all employees into tabular_chunks and tabular_vectors."""
    conn = get_connection()
    try:
        rows = conn.execute("SELECT id, summary_profile, department, role, name, employee_code FROM employees").fetchall()
        if not rows:
            return 0
        
        # Check if already indexed
        existing_chunks = conn.execute(
            "SELECT COUNT(*) FROM tabular_chunks WHERE metadata_json LIKE '%employee_id%'"
        ).fetchone()[0]
        if existing_chunks >= len(rows):
            return existing_chunks

        conn.execute("DELETE FROM tabular_chunks WHERE metadata_json LIKE '%employee_id%'")
        conn.commit()

        indexed_count = 0
        for r in rows:
            emp_id = r["id"]
            text = r["summary_profile"]
            meta = json.dumps({
                "type": "employee",
                "employee_id": emp_id,
                "employee_code": r["employee_code"],
                "name": r["name"],
                "department": r["department"],
                "role": r["role"]
            })

            cursor = conn.execute(
                "INSERT INTO tabular_chunks (dataset_id, sheet_name, row_index, chunk_text, metadata_json) VALUES (?, ?, ?, ?, ?)",
                (None, "employees", emp_id, text, meta)
            )
            chunk_id = cursor.lastrowid
            emb = get_embedding(text)
            conn.execute(
                "INSERT INTO tabular_vectors (id, embedding) VALUES (?, ?)",
                (chunk_id, pack_vector(emb))
            )
            indexed_count += 1

        conn.commit()
        return indexed_count
    finally:
        conn.close()


def index_uploaded_dataset(dataset_id: int, file_path: Path):
    """Indexes an uploaded Excel or CSV file into tabular_chunks and tabular_vectors with semantic linking."""
    conn = get_connection()
    try:
        suffix = file_path.suffix.lower()
        dfs = {}
        if suffix in (".xlsx", ".xls"):
            xls = pd.ExcelFile(file_path)
            for sheet in xls.sheet_names:
                df = pd.read_excel(xls, sheet_name=sheet)
                dfs[sheet] = df
        elif suffix == ".csv":
            df = None
            for enc in ["utf-8", "utf-8-sig", "latin1", "cp1252"]:
                try:
                    df = pd.read_csv(file_path, encoding=enc)
                    break
                except UnicodeDecodeError:
                    continue
            if df is None:
                raise ValueError("Could not decode CSV file.")
            dfs["Sheet1"] = df
        else:
            raise ValueError(f"Unsupported file format: {suffix}")

        # Build lookup tables of existing employees for accurate linking
        emp_by_code = {}
        emp_by_name = {}
        emp_rows = conn.execute("SELECT id, employee_code, name, department, role, rating, attendance_rate FROM employees").fetchall()
        for er in emp_rows:
            emp_by_code[er["employee_code"].strip().upper()] = dict(er)
            emp_by_name[er["name"].strip().lower()] = dict(er)

        total_chunks = 0
        for sheet_name, df in dfs.items():
            # Clean empty unnamed columns
            unnamed_empty = [c for c in df.columns if str(c).startswith("Unnamed") and df[c].isna().all()]
            if unnamed_empty:
                df = df.drop(columns=unnamed_empty)
            df.columns = [str(c).strip() for c in df.columns]

            sample_df = df.head(300)
            columns = [str(c) for c in df.columns]

            # Identify key columns for accurate semantic linking
            name_col = None
            id_col = None
            dept_col = None
            for c in columns:
                c_clean = re.sub(r"[^a-zA-Z0-9]", "", str(c).lower())
                if not name_col and ("employeename" in c_clean or c_clean == "name" or "fullname" in c_clean):
                    name_col = c
                elif not id_col and ("employeeid" in c_clean or c_clean in ["empid", "id", "code"]):
                    id_col = c
                elif not dept_col and ("department" in c_clean or c_clean in ["dept", "division"]):
                    dept_col = c

            for row_idx, row in sample_df.iterrows():
                row_name = str(row[name_col]).strip() if name_col and pd.notna(row.get(name_col)) else None
                row_code = str(row[id_col]).strip() if id_col and pd.notna(row.get(id_col)) else None
                row_dept = str(row[dept_col]).strip() if dept_col and pd.notna(row.get(dept_col)) else None

                parts = []
                for col in columns:
                    if str(col).startswith("Unnamed"):
                        continue
                    val = row.get(col)
                    if pd.notna(val) and str(val).strip() != "":
                        parts.append(f"{col}: {str(val).strip()}")

                if not parts:
                    continue

                # Match employee with strict name-first consistency to prevent identity clashes
                matched_emp = None
                if row_name and row_name.lower() in emp_by_name:
                    matched_emp = emp_by_name[row_name.lower()]
                elif row_code and row_code.upper() in emp_by_code:
                    cand = emp_by_code[row_code.upper()]
                    # Only link if the row doesn't specify a conflicting name
                    if not row_name or cand["name"].strip().lower() == row_name.lower():
                        matched_emp = cand

                chunk_text = f"[{sheet_name} Record {row_idx+1}] " + ", ".join(parts)
                if matched_emp:
                    chunk_text += (
                        f" | Ground Truth Profile: {matched_emp['name']} ({matched_emp['employee_code']}), "
                        f"{matched_emp['role']} in {matched_emp['department']} (Rating: {matched_emp['rating']}/5.0, Attendance: {matched_emp['attendance_rate']}%)."
                    )

                emp_display_name = row_name or (matched_emp["name"] if matched_emp else None)
                emp_display_code = row_code or (matched_emp["employee_code"] if matched_emp else None)
                emp_display_dept = row_dept or (matched_emp["department"] if matched_emp else None)

                meta_data = {
                    "dataset_id": dataset_id,
                    "sheet_name": sheet_name,
                    "row_index": int(row_idx),
                    "employee_id": matched_emp["id"] if matched_emp else None,
                    "employee_code": emp_display_code,
                    "employee_name": emp_display_name,
                    "name": emp_display_name,
                    "department": emp_display_dept
                }

                cursor = conn.execute(
                    "INSERT INTO tabular_chunks (dataset_id, sheet_name, row_index, chunk_text, metadata_json) VALUES (?, ?, ?, ?, ?)",
                    (dataset_id, sheet_name, int(row_idx), chunk_text, json.dumps(meta_data))
                )
                chunk_id = cursor.lastrowid
                emb = get_embedding(chunk_text)
                conn.execute(
                    "INSERT INTO tabular_vectors (id, embedding) VALUES (?, ?)",
                    (chunk_id, pack_vector(emb))
                )
                total_chunks += 1

        conn.commit()
        return total_chunks
    finally:
        conn.close()


def semantic_search(query_text: str, top_k: int = 5):
    """Searches the vector database for tabular chunks matching the natural query."""
    conn = get_connection()
    try:
        query_emb = get_embedding(query_text)
        blob = pack_vector(query_emb)

        rows = conn.execute(
            """
            SELECT v.id, v.distance, c.chunk_text, c.metadata_json, c.sheet_name
            FROM tabular_vectors v
            JOIN tabular_chunks c ON c.id = v.id
            WHERE v.embedding MATCH ? AND k = ?
            ORDER BY v.distance ASC
            """,
            (blob, top_k)
        ).fetchall()

        results = []
        for r in rows:
            meta = {}
            if r["metadata_json"]:
                try:
                    meta = json.loads(r["metadata_json"])
                except Exception:
                    pass
            results.append({
                "chunk_id": r["id"],
                "distance": round(float(r["distance"]), 4),
                "relevance_score": round(max(0.0, 1.0 - float(r["distance"])), 3),
                "text": r["chunk_text"],
                "sheet_name": r["sheet_name"],
                "metadata": meta
            })
        return results
    finally:
        conn.close()
