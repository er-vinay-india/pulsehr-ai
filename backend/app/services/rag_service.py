import json
import struct
from ..core import config
from ..db.database import get_connection


def pack_vector(vec: list[float]) -> bytes:
    return struct.pack(f"{len(vec)}f", *vec)


def semantic_search(query_text: str, top_k: int = 5):
    """Searches the vector database for tabular chunks matching the natural query."""
    conn = get_connection()
    try:
        from .sheet_catalog import model_embeddings
        embeddings = model_embeddings([query_text])
        if not embeddings:
            return []
        query_emb = embeddings[0]
        blob = pack_vector(query_emb)

        rows = conn.execute(
            """
            SELECT v.id, v.distance, c.chunk_text, c.metadata_json, c.sheet_name, c.row_index,
                   COALESCE(d.original_name, d.filename, 'Workforce DB') AS source_file
            FROM tabular_vectors v
            JOIN tabular_chunks c ON c.id = v.id
            LEFT JOIN dataset_uploads d ON d.id = c.dataset_id
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
            if meta.get("embedding_model") != config.OLLAMA_EMBED_MODEL:
                continue
            results.append({
                "chunk_id": r["id"],
                "source_file": r["source_file"],
                "row_index": r["row_index"],
                "distance": round(float(r["distance"]), 4),
                "relevance_score": round(max(0.0, 1.0 - float(r["distance"])), 3),
                "text": r["chunk_text"],
                "sheet_name": r["sheet_name"],
                "metadata": meta
            })
        return results
    finally:
        conn.close()
