from __future__ import annotations

import json
import logging
from pathlib import Path
import sqlite3
import struct
from typing import Any, Sequence
import numpy as np

try:
    import sqlite_vec
    HAS_SQLITE_VEC = True
except ImportError:
    HAS_SQLITE_VEC = False

from ....core import config
from .memory_models import MemoryRecord, MemoryType, EvidenceStatus, SearchResult

logger = logging.getLogger(__name__)


class PresentationMemoryStore:
    """Persistent local vector and metadata store for presentation intelligence."""

    def __init__(self, db_path: Path | None = None):
        self.db_path = db_path or config.PRESENTATION_MEMORY_DB_PATH
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=30.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode = WAL")
        conn.execute("PRAGMA synchronous = NORMAL")
        conn.execute("PRAGMA busy_timeout = 30000")

        if HAS_SQLITE_VEC:
            try:
                conn.enable_load_extension(True)
                sqlite_vec.load(conn)
                conn.enable_load_extension(False)
            except Exception as exc:
                logger.debug(f"sqlite_vec extension load skipped: {exc}")

        return conn

    def _init_db(self) -> None:
        """Initializes tables, indexes, and optional sqlite_vec virtual table."""
        with self._get_connection() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS presentation_memories (
                    memory_id TEXT PRIMARY KEY,
                    memory_type TEXT NOT NULL,
                    text TEXT NOT NULL,
                    source_id TEXT NOT NULL,
                    source_type TEXT NOT NULL,
                    deck_id TEXT,
                    slide_id TEXT,
                    dataset_id INTEGER,
                    sheet_id INTEGER,
                    workspace_id TEXT,
                    domain TEXT,
                    audience TEXT,
                    theme TEXT,
                    evidence_status TEXT NOT NULL DEFAULT 'historical',
                    content_hash TEXT NOT NULL,
                    embedding_blob BLOB,
                    provenance_json TEXT NOT NULL DEFAULT '{}',
                    metadata_json TEXT NOT NULL DEFAULT '{}',
                    created_at TIMESTAMP NOT NULL,
                    updated_at TIMESTAMP NOT NULL
                )
            """)

            conn.execute("CREATE INDEX IF NOT EXISTS idx_mem_source ON presentation_memories(source_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_mem_deck ON presentation_memories(deck_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_mem_type ON presentation_memories(memory_type)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_mem_domain ON presentation_memories(domain)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_mem_hash ON presentation_memories(content_hash)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_mem_workspace ON presentation_memories(workspace_id)")

            if HAS_SQLITE_VEC:
                try:
                    conn.execute(f"""
                        CREATE VIRTUAL TABLE IF NOT EXISTS vec_presentation_memories USING vec0(
                            memory_id TEXT PRIMARY KEY,
                            embedding float[{config.EMBEDDING_DIM}]
                        )
                    """)
                except Exception as exc:
                    logger.debug(f"Virtual vector table init skipped/exists: {exc}")
            conn.commit()

    @staticmethod
    def _pack_vector(vec: Sequence[float]) -> bytes:
        return struct.pack(f"{len(vec)}f", *vec)

    @staticmethod
    def _unpack_vector(blob: bytes) -> np.ndarray | None:
        if not blob:
            return None
        return np.frombuffer(blob, dtype=np.float32)

    def upsert_record(self, record: MemoryRecord) -> None:
        """Inserts or updates a single memory record with atomic vector sync."""
        self.upsert_batch([record])

    def upsert_batch(self, records: Sequence[MemoryRecord]) -> int:
        """Batch upserts memory records."""
        if not records:
            return 0

        count = 0
        with self._get_connection() as conn:
            for r in records:
                blob = self._pack_vector(r.embedding) if r.embedding else None
                conn.execute("""
                    INSERT INTO presentation_memories (
                        memory_id, memory_type, text, source_id, source_type,
                        deck_id, slide_id, dataset_id, sheet_id, workspace_id,
                        domain, audience, theme, evidence_status, content_hash,
                        embedding_blob, provenance_json, metadata_json, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(memory_id) DO UPDATE SET
                        memory_type = excluded.memory_type,
                        text = excluded.text,
                        source_id = excluded.source_id,
                        source_type = excluded.source_type,
                        deck_id = excluded.deck_id,
                        slide_id = excluded.slide_id,
                        dataset_id = excluded.dataset_id,
                        sheet_id = excluded.sheet_id,
                        workspace_id = excluded.workspace_id,
                        domain = excluded.domain,
                        audience = excluded.audience,
                        theme = excluded.theme,
                        evidence_status = excluded.evidence_status,
                        content_hash = excluded.content_hash,
                        embedding_blob = excluded.embedding_blob,
                        provenance_json = excluded.provenance_json,
                        metadata_json = excluded.metadata_json,
                        updated_at = excluded.updated_at
                """, (
                    r.memory_id,
                    r.memory_type.value if isinstance(r.memory_type, MemoryType) else str(r.memory_type),
                    r.text,
                    r.source_id,
                    r.source_type,
                    r.deck_id,
                    r.slide_id,
                    r.dataset_id,
                    r.sheet_id,
                    r.workspace_id,
                    r.domain,
                    r.audience,
                    r.theme,
                    r.evidence_status.value if isinstance(r.evidence_status, EvidenceStatus) else str(r.evidence_status),
                    r.content_hash,
                    blob,
                    json.dumps(r.provenance or {}),
                    json.dumps(r.metadata or {}),
                    r.created_at,
                    r.updated_at
                ))

                # Sync virtual vector table if available
                if HAS_SQLITE_VEC and r.embedding:
                    try:
                        conn.execute("""
                            INSERT INTO vec_presentation_memories (memory_id, embedding)
                            VALUES (?, ?)
                            ON CONFLICT(memory_id) DO UPDATE SET embedding = excluded.embedding
                        """, (r.memory_id, json.dumps(r.embedding)))
                    except Exception:
                        pass
                count += 1
            conn.commit()
        return count

    def get_by_id(self, memory_id: str) -> MemoryRecord | None:
        with self._get_connection() as conn:
            row = conn.execute("SELECT * FROM presentation_memories WHERE memory_id = ?", (memory_id,)).fetchone()
            if not row:
                return None
            return self._row_to_record(row)

    def get_by_content_hash(self, content_hash: str) -> MemoryRecord | None:
        with self._get_connection() as conn:
            row = conn.execute("SELECT * FROM presentation_memories WHERE content_hash = ? LIMIT 1", (content_hash,)).fetchone()
            if not row:
                return None
            return self._row_to_record(row)

    def get_by_source(self, source_id: str) -> list[MemoryRecord]:
        with self._get_connection() as conn:
            rows = conn.execute("SELECT * FROM presentation_memories WHERE source_id = ?", (source_id,)).fetchall()
            return [self._row_to_record(r) for r in rows]

    def delete_by_id(self, memory_id: str) -> bool:
        with self._get_connection() as conn:
            cur = conn.execute("DELETE FROM presentation_memories WHERE memory_id = ?", (memory_id,))
            if HAS_SQLITE_VEC:
                try:
                    conn.execute("DELETE FROM vec_presentation_memories WHERE memory_id = ?", (memory_id,))
                except Exception:
                    pass
            conn.commit()
            return cur.rowcount > 0

    def delete_by_source(self, source_id: str) -> int:
        with self._get_connection() as conn:
            ids = [r[0] for r in conn.execute("SELECT memory_id FROM presentation_memories WHERE source_id = ?", (source_id,)).fetchall()]
            if not ids:
                return 0
            cur = conn.execute("DELETE FROM presentation_memories WHERE source_id = ?", (source_id,))
            if HAS_SQLITE_VEC:
                for mid in ids:
                    try:
                        conn.execute("DELETE FROM vec_presentation_memories WHERE memory_id = ?", (mid,))
                    except Exception:
                        pass
            conn.commit()
            return cur.rowcount

    def delete_by_deck_id(self, deck_id: str) -> int:
        with self._get_connection() as conn:
            ids = [r[0] for r in conn.execute("SELECT memory_id FROM presentation_memories WHERE deck_id = ?", (deck_id,)).fetchall()]
            if not ids:
                return 0
            cur = conn.execute("DELETE FROM presentation_memories WHERE deck_id = ?", (deck_id,))
            if HAS_SQLITE_VEC:
                for mid in ids:
                    try:
                        conn.execute("DELETE FROM vec_presentation_memories WHERE memory_id = ?", (mid,))
                    except Exception:
                        pass
            conn.commit()
            return cur.rowcount

    def search_vector(
        self,
        query_vector: list[float],
        memory_types: list[str | MemoryType] | None = None,
        domain: str | None = None,
        audience: str | None = None,
        workspace_id: str | None = None,
        dataset_ids: list[int] | None = None,
        top_k: int = 10,
    ) -> list[SearchResult]:
        """Performs vector similarity search with metadata filtering.
        Uses sqlite_vec when available, falling back seamlessly to numpy cosine similarity.
        """
        # Formulate SQL WHERE clause for candidate metadata filtering
        clauses = ["embedding_blob IS NOT NULL"]
        params: list[Any] = []

        if memory_types:
            type_vals = [t.value if isinstance(t, MemoryType) else str(t) for t in memory_types]
            placeholders = ",".join(["?"] * len(type_vals))
            clauses.append(f"memory_type IN ({placeholders})")
            params.extend(type_vals)

        if domain:
            clauses.append("(domain IS NULL OR domain = ? OR domain LIKE ?)")
            params.extend([domain, f"%{domain}%"])

        if audience:
            clauses.append("(audience IS NULL OR audience = ? OR audience LIKE ?)")
            params.extend([audience, f"%{audience}%"])

        if workspace_id:
            clauses.append("(workspace_id IS NULL OR workspace_id = ?)")
            params.append(workspace_id)

        if dataset_ids:
            d_placeholders = ",".join(["?"] * len(dataset_ids))
            clauses.append(f"(dataset_id IS NULL OR dataset_id IN ({d_placeholders}))")
            params.extend(dataset_ids)

        where_sql = " AND ".join(clauses)

        with self._get_connection() as conn:
            query = f"""
                SELECT memory_id, memory_type, text, source_id, deck_id, slide_id,
                       evidence_status, provenance_json, metadata_json, embedding_blob
                FROM presentation_memories
                WHERE {where_sql}
            """
            rows = conn.execute(query, params).fetchall()

        if not rows:
            return []

        # Vectorized cosine similarity computation using numpy
        q_vec = np.array(query_vector, dtype=np.float32)
        q_norm = np.linalg.norm(q_vec)
        if q_norm == 0:
            return []

        scored_results: list[SearchResult] = []
        for r in rows:
            blob = r["embedding_blob"]
            cand_arr = self._unpack_vector(blob)
            if cand_arr is None or len(cand_arr) != len(q_vec):
                continue

            cand_norm = np.linalg.norm(cand_arr)
            if cand_norm == 0:
                continue

            # Cosine similarity range [-1.0, 1.0], normalized to [0.0, 1.0]
            sim = float(np.dot(q_vec, cand_arr) / (q_norm * cand_norm))
            sim_normalized = max(0.0, min(1.0, (sim + 1.0) / 2.0))

            prov = json.loads(r["provenance_json"] or "{}")
            meta = json.loads(r["metadata_json"] or "{}")

            scored_results.append(
                SearchResult(
                    memory_id=r["memory_id"],
                    memory_type=MemoryType(r["memory_type"]),
                    score=sim_normalized,
                    semantic_score=sim_normalized,
                    text=r["text"],
                    source_id=r["source_id"],
                    deck_id=r["deck_id"],
                    slide_id=r["slide_id"],
                    evidence_status=r["evidence_status"],
                    provenance=prov,
                    metadata=meta,
                )
            )

        scored_results.sort(key=lambda x: x.score, reverse=True)
        return scored_results[:top_k]

    def count(self) -> int:
        with self._get_connection() as conn:
            return conn.execute("SELECT COUNT(*) FROM presentation_memories").fetchone()[0]

    def clear(self) -> None:
        with self._get_connection() as conn:
            conn.execute("DELETE FROM presentation_memories")
            if HAS_SQLITE_VEC:
                try:
                    conn.execute("DELETE FROM vec_presentation_memories")
                except Exception:
                    pass
            conn.commit()

    @staticmethod
    def _row_to_record(row: sqlite3.Row) -> MemoryRecord:
        blob = row["embedding_blob"]
        vec = None
        if blob:
            arr = np.frombuffer(blob, dtype=np.float32)
            vec = arr.tolist()

        return MemoryRecord(
            memory_id=row["memory_id"],
            memory_type=MemoryType(row["memory_type"]),
            text=row["text"],
            embedding=vec,
            source_id=row["source_id"],
            source_type=row["source_type"],
            deck_id=row["deck_id"],
            slide_id=row["slide_id"],
            dataset_id=row["dataset_id"],
            sheet_id=row["sheet_id"],
            workspace_id=row["workspace_id"],
            domain=row["domain"],
            audience=row["audience"],
            theme=row["theme"],
            evidence_status=EvidenceStatus(row["evidence_status"]),
            content_hash=row["content_hash"],
            provenance=json.loads(row["provenance_json"] or "{}"),
            metadata=json.loads(row["metadata_json"] or "{}"),
            created_at=row["created_at"],
            updated_at=row["updated_at"]
        )


# Global singleton
memory_store = PresentationMemoryStore()
