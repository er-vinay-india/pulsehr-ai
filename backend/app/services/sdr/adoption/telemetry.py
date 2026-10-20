"""
HighView Semantic Data Refinery — Phase SDR-9
Controlled Adoption Telemetry & Observability Ledger
Tracks routing telemetry, canary evaluations, fallback occurrences,
failure diagnostics, and execution latencies outside P0.
"""

from __future__ import annotations

import json
import logging
from collections import defaultdict
from pathlib import Path
from typing import Any

from app.core import config
from app.services.ingestion_v2.contracts.cutover import ConsumerName, FallbackReason, Route
from app.services.sdr.adoption.contracts import SDRRouteDecision

logger = logging.getLogger(__name__)


def compute_latency_stats(samples: list[float]) -> dict[str, float]:
    """Computes average, P50, and P95 for a list of latency samples."""
    if not samples:
        return {"avg": 0.0, "p50": 0.0, "p95": 0.0, "count": 0}
    s = sorted(samples)
    n = len(s)
    avg = sum(s) / n
    p50 = s[n // 2]
    idx95 = min(n - 1, int(round(0.95 * (n - 1))))
    p95 = s[idx95]
    return {
        "avg": round(avg, 2),
        "p50": round(p50, 2),
        "p95": round(p95, 2),
        "count": n,
    }


class SDRAdoptionTelemetryLedger:
    """
    Isolated in-memory and file-based telemetry ledger for SDR controlled adoption.
    """

    def __init__(self, base_data_dir: Path | str | None = None):
        self.base_dir = Path(base_data_dir) if base_data_dir else getattr(config, "DATA_DIR", Path("data"))
        self._decisions: list[SDRRouteDecision] = []
        self._latencies: dict[str, dict[str, list[float]]] = {
            ConsumerName.HRIDAY.value: defaultdict(list),
            ConsumerName.DASHBOARD.value: defaultdict(list),
            ConsumerName.PRESENTATION.value: defaultdict(list),
        }
        self._counts: dict[str, dict[str, int]] = {
            ConsumerName.HRIDAY.value: defaultdict(int),
            ConsumerName.DASHBOARD.value: defaultdict(int),
            ConsumerName.PRESENTATION.value: defaultdict(int),
        }

    def record_decision(
        self,
        decision: SDRRouteDecision,
        latencies_ms: dict[str, float] | None = None,
    ) -> None:
        """Records an adoption routing decision and updates consumer counters."""
        self._decisions.append(decision)
        c = decision.consumer.value
        counts = self._counts[c]

        counts["total_requests"] += 1

        if decision.selected_route == Route.SDR:
            if decision.is_canary:
                counts["sdr_canary_routes"] += 1
            else:
                counts["sdr_primary_routes"] += 1
        elif decision.selected_route == getattr(Route, "V2"):
            counts["v2_routes"] += 1
        elif decision.selected_route == Route.V1:
            counts["v1_routes"] += 1

        if decision.fallback_used:
            counts["fallbacks"] += 1

        fb = decision.fallback_reason
        if fb == FallbackReason.KILL_SWITCH_ACTIVE:
            counts["kill_switch_routes"] += 1
        elif fb == FallbackReason.CONSUMER_ROLLBACK_ACTIVE:
            counts["rollback_routes"] += 1
        elif fb == FallbackReason.CIRCUIT_BREAKER_OPEN:
            counts["circuit_open_routes"] += 1
        elif fb == FallbackReason.MANUAL_OVERRIDE:
            counts["manual_override_routes"] += 1
        elif fb == FallbackReason.V2_ARTIFACT_STALE:
            counts["stale_blocks"] += 1
        elif fb in (FallbackReason.V2_JOIN_PLAN_UNAVAILABLE, FallbackReason.V2_RELATIONSHIP_AMBIGUOUS):
            counts["unsafe_blocks"] += 1
        elif fb == FallbackReason.V2_DATASET_VERSION_MISMATCH:
            counts["version_mismatch_blocks"] += 1
        elif fb == FallbackReason.V2_SCHEMA_CONTRACT_FAILURE:
            counts["contract_mismatch_blocks"] += 1
        elif fb == FallbackReason.V2_RUNTIME_ERROR:
            counts["runtime_failures"] += 1

        if latencies_ms:
            for k, v in latencies_ms.items():
                self._latencies[c][k].append(v)

    def get_consumer_summary(self, consumer: ConsumerName) -> dict[str, Any]:
        c = consumer.value
        counts = dict(self._counts[c])
        lats = {}
        for lat_key, samples in self._latencies[c].items():
            lats[lat_key] = compute_latency_stats(samples)

        return {
            "consumer": c,
            "counts": counts,
            "latencies": lats,
        }

    def get_all_summaries(self) -> dict[str, Any]:
        return {
            c.value: self.get_consumer_summary(c)
            for c in [ConsumerName.HRIDAY, ConsumerName.DASHBOARD, ConsumerName.PRESENTATION]
        }

    def reset(self) -> None:
        self._decisions.clear()
        for c in [ConsumerName.HRIDAY.value, ConsumerName.DASHBOARD.value, ConsumerName.PRESENTATION.value]:
            self._latencies[c] = defaultdict(list)
            self._counts[c] = defaultdict(int)


_shared_adoption_telemetry: SDRAdoptionTelemetryLedger | None = None


def get_adoption_telemetry() -> SDRAdoptionTelemetryLedger:
    global _shared_adoption_telemetry
    if _shared_adoption_telemetry is None:
        _shared_adoption_telemetry = SDRAdoptionTelemetryLedger()
    return _shared_adoption_telemetry
