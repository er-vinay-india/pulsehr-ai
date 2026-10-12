"""
HighView DashboardCacheService (Phase G2).
Coordinates key generation, repository access, fail-closed integrity validation,
single-flight thundering-herd concurrency protection, and telemetry metrics.
"""
from __future__ import annotations

import logging
import threading
import time
from collections import defaultdict
from typing import Any, Callable

from .contracts import DashboardCacheKey
from .integrity import CacheIsolationIntegrity
from .metrics import cache_metrics
from .repository import DashboardCacheRepository

logger = logging.getLogger(__name__)


class DashboardCacheService:
    """Authoritative service boundary for deterministic dashboard intelligence caching."""

    def __init__(self, repo: type[DashboardCacheRepository] | None = None):
        self.repo = repo or DashboardCacheRepository
        self._flight_locks: dict[str, threading.Lock] = defaultdict(threading.Lock)
        self._global_lock = threading.Lock()

    def _get_flight_lock(self, key_hash: str) -> threading.Lock:
        with self._global_lock:
            return self._flight_locks[key_hash]

    def get(self, key: DashboardCacheKey) -> dict[str, Any] | None:
        """
        Retrieves cached payload if present, valid, and unpolluted.
        Fails closed: Any integrity violation or corruption immediately purges entry.
        """
        start = time.perf_counter()
        key_hash = key.compute_key()

        payload, meta = self.repo.get(key_hash)
        lookup_ms = (time.perf_counter() - start) * 1000.0

        if payload is None:
            return None

        # Hard integrity verification
        if not CacheIsolationIntegrity.validate_payload(payload, key, is_write=False):
            cache_metrics.record_invalid(lookup_ms)
            logger.warning("[DashboardCacheService] Integrity failed for %s. Evicting.", key_hash)
            self.repo.delete_by_key(key_hash)
            return None

        cache_metrics.record_hit(lookup_ms)
        return payload

    def put(self, key: DashboardCacheKey, payload: dict[str, Any]) -> bool:
        """
        Caches validated payload in SQLite.
        Never raises: cache write failure is logged without disrupting callers.
        """
        start = time.perf_counter()
        if not CacheIsolationIntegrity.validate_payload(payload, key, is_write=True):
            logger.warning("[DashboardCacheService] Pre-cache validation failed. Rejecting put.")
            return False

        success = self.repo.put(key, payload)
        write_ms = (time.perf_counter() - start) * 1000.0
        if success:
            cache_metrics.record_write(write_ms)
        return success

    def invalidate_dataset(self, dataset_id: int) -> int:
        """Purges all cached intelligence for a deleted, replaced, or mutated dataset."""
        count = self.repo.delete_by_dataset(dataset_id)
        cache_metrics.record_invalidation(count)
        logger.info("[DashboardCacheService] Invalidated %d cache entries for dataset %s.", count, dataset_id)
        return count

    def get_or_compute(
        self,
        key: DashboardCacheKey,
        compute_fn: Callable[[], dict[str, Any]],
    ) -> dict[str, Any]:
        """
        Executes single-flight retrieval with thundering-herd protection.
        Multiple concurrent requests for the same cache key compute once.
        """
        start_lookup = time.perf_counter()
        cached = self.get(key)
        if cached is not None:
            return cached

        key_hash = key.compute_key()
        lock = self._get_flight_lock(key_hash)

        with lock:
            # Double-check lock: check if another thread completed the computation
            cached = self.get(key)
            if cached is not None:
                return cached

            # Cache miss: compute from Highview Core
            lookup_ms = (time.perf_counter() - start_lookup) * 1000.0
            start_compute = time.perf_counter()
            try:
                fresh_payload = compute_fn()
            except Exception as comp_err:
                logger.error("[DashboardCacheService] Compute failed for key %s: %s", key_hash, comp_err)
                raise

            compute_ms = (time.perf_counter() - start_compute) * 1000.0
            cache_metrics.record_miss(lookup_ms, compute_ms)

            # Store in cache asynchronously / safely
            try:
                self.put(key, fresh_payload)
            except Exception as put_err:
                logger.warning("[DashboardCacheService] Non-blocking put error: %s", put_err)

            return fresh_payload

    def stats(self) -> dict[str, Any]:
        """Returns comprehensive cache health, storage, and performance telemetry."""
        storage = self.repo.get_stats()
        telemetry = cache_metrics.get_summary()
        return {
            **storage,
            **telemetry,
        }


# Global singleton instance
dashboard_cache = DashboardCacheService()
