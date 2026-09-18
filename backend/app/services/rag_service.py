import json
import math
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
        rows = conn.execute("SELECT id, summary_profile, department, role, name FROM employees").fetchall()
        if not rows:
            return 0
        
        # Check if already indexed
        existing_chunks = conn.execute(
            "SELECT COUNT(*) FROM tabular_chunks WHERE metadata_json LIKE '%employee_id%'"
        ).fetchone()[0]
        if existing_chunks >= len(rows):
            return existing_chunks

        # Clear employee chunks
        conn.execute("DELETE FROM tabular_chunks WHERE metadata_json LIKE '%employee_id%'")
        conn.commit()

        indexed_count = 0
        for r in rows:
            emp_id = r["id"]
            text = r["summary_profile"]
            meta = json.dumps({
                "type": "employee",
                "employee_id": emp_id,
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
    """Indexes an uploaded Excel or CSV file into tabular_chunks and tabular_vectors."""
    conn = get_connection()
    try:
        suffix = file_path.suffix.lower()
        dfs = {}
        if suffix in (".xlsx", ".xls"):
            xls = pd.ExcelFile(file_path)
            for sheet in xls.sheet_names:
                dfs[sheet] = pd.read_excel(xls, sheet_name=sheet)
        elif suffix == ".csv":
            dfs["Sheet1"] = pd.read_csv(file_path)
        else:
            raise ValueError(f"Unsupported file format: {suffix}")

        total_chunks = 0
        for sheet_name, df in dfs.items():
            # sample up to 250 rows to keep indexing snappy
            sample_df = df.head(250)
            columns = [str(c) for c in df.columns]

            for row_idx, row in sample_df.iterrows():
                # Formulate natural sentence
                parts = []
                for col in columns:
                    val = row.get(col)
                    if pd.notna(val):
                        parts.append(f"{col}: {val}")
                
                chunk_text = f"[{sheet_name} Row {row_idx+1}] " + ", ".join(parts)
                meta = json.dumps({
                    "dataset_id": dataset_id,
                    "sheet_name": sheet_name,
                    "row_index": int(row_idx)
                })

                cursor = conn.execute(
                    "INSERT INTO tabular_chunks (dataset_id, sheet_name, row_index, chunk_text, metadata_json) VALUES (?, ?, ?, ?, ?)",
                    (dataset_id, sheet_name, int(row_idx), chunk_text, meta)
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
