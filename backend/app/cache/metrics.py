"""
Telemetry and metrics tracker for HighView Analytics Cache (Phase G2).
Tracks latency distributions, hit/miss ratios, and cache health for Technical Explorer.
"""
from __future__ import annotations

import threading
import time
from typing import Any
import numpy as np


class CacheMetricsTracker:
    """Thread-safe metrics accumulator for cache operations."""

    def __init__(self):
        self._lock = threading.Lock()
        self.hit_count: int = 0
        self.miss_count: int = 0
        self.invalid_count: int = 0
        self.write_count: int = 0
        self.invalidation_count: int = 0
        self._cold_latencies: list[float] = []
        self._warm_latencies: list[float] = []

    def record_hit(self, lookup_ms: float) -> None:
        with self._lock:
            self.hit_count += 1
            self._warm_latencies.append(lookup_ms)
            if len(self._warm_latencies) > 1000:
                self._warm_latencies = self._warm_latencies[-1000:]

    def record_miss(self, lookup_ms: float, compute_ms: float) -> None:
        with self._lock:
            self.miss_count += 1
            total_cold_ms = lookup_ms + compute_ms
            self._cold_latencies.append(total_cold_ms)
            if len(self._cold_latencies) > 1000:
                self._cold_latencies = self._cold_latencies[-1000:]

    def record_invalid(self, lookup_ms: float) -> None:
        with self._lock:
            self.invalid_count += 1

    def record_write(self, write_ms: float) -> None:
        with self._lock:
            self.write_count += 1

    def record_invalidation(self, count: int) -> None:
        with self._lock:
            self.invalidation_count += count

    def get_summary(self) -> dict[str, Any]:
        with self._lock:
            total_requests = self.hit_count + self.miss_count
            hit_rate = round((self.hit_count / total_requests * 100.0), 2) if total_requests > 0 else 0.0

            cold_p50 = float(np.percentile(self._cold_latencies, 50)) if self._cold_latencies else 0.0
            cold_p95 = float(np.percentile(self._cold_latencies, 95)) if self._cold_latencies else 0.0

            warm_p50 = float(np.percentile(self._warm_latencies, 50)) if self._warm_latencies else 0.0
            warm_p95 = float(np.percentile(self._warm_latencies, 95)) if self._warm_latencies else 0.0

            speedup = round((cold_p50 / warm_p50), 1) if (cold_p50 > 0 and warm_p50 > 0) else 1.0

            return {
                "total_requests": total_requests,
                "hit_count": self.hit_count,
                "miss_count": self.miss_count,
                "invalid_count": self.invalid_count,
                "write_count": self.write_count,
                "invalidation_count": self.invalidation_count,
                "hit_rate_pct": hit_rate,
                "cold_p50_ms": round(cold_p50, 2),
                "cold_p95_ms": round(cold_p95, 2),
                "warm_p50_ms": round(warm_p50, 2),
                "warm_p95_ms": round(warm_p95, 2),
                "speedup_ratio": f"{speedup}x" if speedup > 1.0 else "1.0x",
            }


cache_metrics = CacheMetricsTracker()
