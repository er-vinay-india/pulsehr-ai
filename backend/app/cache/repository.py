"""
SQLite repository for dashboard_cache (Phase G2).
Encapsulates all SQL statements for storing, retrieving, and pruning cached analytical payloads.
"""
from __future__ import annotations

import datetime
import json
import logging
import sqlite3
from typing import Any

from ..db.database import session_scope
from .contracts import DashboardCacheKey, CacheEntryMetadata

logger = logging.getLogger(__name__)


class DashboardCacheRepository:
    """Encapsulates persistent SQLite storage in the `dashboard_cache` table."""

    @staticmethod
    def get(
        cache_key: str,
        conn: sqlite3.Connection | None = None,
    ) -> tuple[dict[str, Any] | None, CacheEntryMetadata | None]:
        """
        Retrieves and deserializes cached payload.
        Updates hit_count and last_accessed_at.
        If payload JSON is corrupted, deletes the record and returns (None, None).
        """
        def _execute(db: sqlite3.Connection):
            row = db.execute(
                """
                SELECT cache_key, dataset_id, dataset_version, content_hash,
                       semantic_schema_version, context_version, policy_version,
                       analytics_engine_version, composition_engine_version,
                       filter_hash, payload_json, created_at, last_accessed_at,
                       hit_count, size_bytes
                FROM dashboard_cache
                WHERE cache_key = ?
                """,
                (cache_key,),
            ).fetchone()

            if not row:
                return None, None

            raw_json = row["payload_json"]
            try:
                payload = json.loads(raw_json)
            except Exception as dec_err:
                logger.warning(
                    "[DashboardCacheRepository] Corrupted payload JSON for key %s. Purging entry. Error: %s",
                    cache_key,
                    dec_err,
                )
                db.execute("DELETE FROM dashboard_cache WHERE cache_key = ?", (cache_key,))
                return None, None

            # Increment hit_count and update last_accessed_at
            now = datetime.datetime.now(datetime.timezone.utc).isoformat()
            db.execute(
                "UPDATE dashboard_cache SET hit_count = hit_count + 1, last_accessed_at = ? WHERE cache_key = ?",
                (now, cache_key),
            )

            meta = CacheEntryMetadata(
                cache_key=row["cache_key"],
                dataset_id=row["dataset_id"],
                dataset_version=row["dataset_version"] or 1,
                content_hash=row["content_hash"] or "",
                semantic_schema_version=row["semantic_schema_version"] or "",
                context_version=row["context_version"] or "",
                policy_version=row["policy_version"] or "",
                analytics_engine_version=row["analytics_engine_version"] or "",
                composition_engine_version=row["composition_engine_version"] or "",
                filter_hash=row["filter_hash"] or "",
                created_at=row["created_at"] or now,
                last_accessed_at=now,
                hit_count=(row["hit_count"] or 0) + 1,
                size_bytes=row["size_bytes"] or len(raw_json.encode("utf-8")),
            )

            return payload, meta

        if conn is not None:
            return _execute(conn)
        with session_scope() as scoped_conn:
            return _execute(scoped_conn)

    @staticmethod
    def put(
        key: DashboardCacheKey,
        payload: dict[str, Any],
        conn: sqlite3.Connection | None = None,
    ) -> bool:
        """
        Stores serialized payload in dashboard_cache.
        Catches and logs all errors, returning False instead of raising.
        """
        def _execute(db: sqlite3.Connection) -> bool:
            try:
                cache_key = key.compute_key()
                payload_json = json.dumps(payload)
                size_bytes = len(payload_json.encode("utf-8"))
                now = datetime.datetime.now(datetime.timezone.utc).isoformat()

                db.execute(
                    """
                    INSERT OR REPLACE INTO dashboard_cache (
                        cache_key, dataset_id, dataset_version, content_hash,
                        semantic_schema_version, context_version, policy_version,
                        analytics_engine_version, composition_engine_version,
                        filter_hash, payload_json, created_at, last_accessed_at,
                        hit_count, size_bytes
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, ?)
                    """,
                    (
                        cache_key,
                        key.dataset_id,
                        key.dataset_version,
                        key.dataset_content_hash,
                        key.semantic_schema_version,
                        key.context_version,
                        key.policy_version,
                        key.analytics_engine_version,
                        key.composition_engine_version,
                        key.filter_hash,
                        payload_json,
                        now,
                        now,
                        size_bytes,
                    ),
                )
                return True
            except Exception as exc:
                logger.warning(
                    "[DashboardCacheRepository] Cache put failed for key %s: %s",
                    key.compute_key(),
                    exc,
                )
                return False

        if conn is not None:
            return _execute(conn)
        try:
            with session_scope() as scoped_conn:
                return _execute(scoped_conn)
        except Exception as exc:
            logger.warning("[DashboardCacheRepository] Session scope error on cache put: %s", exc)
            return False

    @staticmethod
    def delete_by_key(cache_key: str, conn: sqlite3.Connection | None = None) -> bool:
        """Deletes a specific cache entry."""
        def _execute(db: sqlite3.Connection) -> bool:
            res = db.execute("DELETE FROM dashboard_cache WHERE cache_key = ?", (cache_key,))
            return res.rowcount > 0

        if conn is not None:
            return _execute(conn)
        with session_scope() as scoped_conn:
            return _execute(scoped_conn)

    @staticmethod
    def delete_by_dataset(dataset_id: int, conn: sqlite3.Connection | None = None) -> int:
        """Deletes all cache entries belonging to a dataset."""
        def _execute(db: sqlite3.Connection) -> int:
            res = db.execute("DELETE FROM dashboard_cache WHERE dataset_id = ?", (dataset_id,))
            return res.rowcount

        if conn is not None:
            return _execute(conn)
        with session_scope() as scoped_conn:
            return _execute(scoped_conn)

    @staticmethod
    def get_stats(conn: sqlite3.Connection | None = None) -> dict[str, Any]:
        """Returns storage statistics for Technical Explorer and Telemetry."""
        def _execute(db: sqlite3.Connection) -> dict[str, Any]:
            row = db.execute(
                """
                SELECT COUNT(*) as total_entries,
                       COALESCE(SUM(size_bytes), 0) as total_bytes,
                       COALESCE(SUM(hit_count), 0) as total_hits
                FROM dashboard_cache
                """
            ).fetchone()
            return {
                "total_entries": row["total_entries"] if row else 0,
                "total_bytes": row["total_bytes"] if row else 0,
                "total_hits": row["total_hits"] if row else 0,
            }

        if conn is not None:
            return _execute(conn)
        with session_scope() as scoped_conn:
            return _execute(scoped_conn)
