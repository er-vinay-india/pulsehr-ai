import json
import struct
from ..core import config
from ..db.database import get_connection


def pack_vector(vec: list[float]) -> bytes:
    return struct.pack(f"{len(vec)}f", *vec)


def semantic_search(
    query_text: str,
    top_k: int = 5,
    dataset_id: int | None = None,
    sheet_id: int | None = None,
    entity_grain: str | None = None,
    conn=None
) -> list[dict]:
    """Searches the vector database for tabular chunks matching the natural query with strict dataset scoping."""
    should_close = False
    if conn is None:
        conn = get_connection()
        should_close = True
    try:
        from .sheet_catalog import model_embeddings
        embeddings = model_embeddings([query_text])
        if not embeddings:
            return []
        query_emb = embeddings[0]
        blob = pack_vector(query_emb)

        query_sql = """
            SELECT v.id, v.distance, c.chunk_text, c.metadata_json, c.sheet_name, c.row_index, c.dataset_id,
                   COALESCE(d.original_name, d.filename, 'Workforce DB') AS source_file
            FROM tabular_vectors v
            JOIN tabular_chunks c ON c.id = v.id
            LEFT JOIN dataset_uploads d ON d.id = c.dataset_id
            WHERE v.embedding MATCH ? AND k = ?
        """
        params: list = [blob, top_k * 4 if (dataset_id or entity_grain) else top_k]

        if dataset_id is not None:
            query_sql += " AND c.dataset_id = ?"
            params.append(dataset_id)

        query_sql += " ORDER BY v.distance ASC"

        rows = conn.execute(query_sql, tuple(params)).fetchall()

        results = []
        for r in rows:
            meta = {}
            if r["metadata_json"]:
                try:
                    meta = json.loads(r["metadata_json"])
                except Exception:
                    pass
            if meta.get("embedding_model") and meta.get("embedding_model") != config.OLLAMA_EMBED_MODEL:
                continue

            # Scope by sheet_id if specified in metadata
            if sheet_id is not None and meta.get("sheet_id") is not None and meta.get("sheet_id") != sheet_id:
                continue

            c_text = r["chunk_text"] or ""
            # Enforce entity_grain matching
            if entity_grain == "employee":
                # For employee-grain requests, penalize chunks that are purely department summaries with no employee signal
                is_pure_dept = ("department summary" in c_text.lower() or "department average" in c_text.lower()) and not any(k in c_text.lower() for k in ("id:", "employee", "staff"))
                if is_pure_dept:
                    continue
            elif entity_grain == "department":
                # For department-grain requests, penalize individual row dumps if requested
                pass

            distance = round(float(r["distance"]), 4)
            relevance = round(max(0.0, 1.0 - float(r["distance"])), 3)

            results.append({
                "chunk_id": r["id"],
                "source_file": r["source_file"],
                "row_index": r["row_index"],
                "dataset_id": r["dataset_id"],
                "distance": distance,
                "relevance_score": relevance,
                "text": c_text,
                "sheet_name": r["sheet_name"],
                "metadata": meta
            })
            if len(results) >= top_k:
                break
        return results
    finally:
        if should_close:
            conn.close()

