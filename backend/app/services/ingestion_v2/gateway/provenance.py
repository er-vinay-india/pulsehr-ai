"""
HighView Ingestion V2 — Phase I8.2 Routing Provenance & Fallback Ledger
Stage: Governed Consumer Gateway & Accountability
Records every route decision, fallback event, and telemetry counter so that
no cutover or fallback operation exists only in ephemeral logs.
"""

from __future__ import annotations

import threading
from typing import Any

from app.services.ingestion_v2.contracts.cutover import (
    ConsumerName,
    ConsumerRouteDecision,
    FallbackReason,
    FallbackRecord,
    Route,
)


class RoutingProvenanceLedger:
    """
    Thread-safe ledger recording all routing decisions, fallback events, and telemetry counters.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._decisions: list[ConsumerRouteDecision] = []
        self._fallbacks: list[FallbackRecord] = []

        # Telemetry counters
        self._counters = {
            "consumer_route_v1_count": 0,
            "consumer_route_v2_count": 0,
            "consumer_fallback_count": 0,
            "consumer_v2_failure_count": 0,
            "stale_artifact_block_count": 0,
            "dataset_mismatch_block_count": 0,
            "evidence_grounding_failure_count": 0,
            "circuit_breaker_open_count": 0,
            "rollback_count": 0,
        }
        self._fallback_reason_counts: dict[str, int] = {}
        self._per_consumer_routes: dict[ConsumerName, dict[Route, int]] = {
            ConsumerName.HRIDAY: {Route.V1: 0, Route.V2: 0},
            ConsumerName.DASHBOARD: {Route.V1: 0, Route.V2: 0},
            ConsumerName.PRESENTATION: {Route.V1: 0, Route.V2: 0},
        }

    def record_decision(self, decision: ConsumerRouteDecision) -> None:
        """Records a routing decision and updates telemetry."""
        with self._lock:
            self._decisions.append(decision)
            if decision.selected_route == Route.V1:
                self._counters["consumer_route_v1_count"] += 1
                self._per_consumer_routes[decision.consumer][Route.V1] += 1
            else:
                self._counters["consumer_route_v2_count"] += 1
                self._per_consumer_routes[decision.consumer][Route.V2] += 1

            if decision.fallback_used:
                self._counters["consumer_fallback_count"] += 1
                if decision.fallback_reason:
                    r_str = decision.fallback_reason.value
                    self._fallback_reason_counts[r_str] = self._fallback_reason_counts.get(r_str, 0) + 1

    def record_fallback(self, record: FallbackRecord) -> None:
        """Records an explicit fallback event and increments failure telemetry."""
        with self._lock:
            self._fallbacks.append(record)
            self._counters["consumer_v2_failure_count"] += 1

            # Specific failure classification counters
            if record.reason == FallbackReason.V2_ARTIFACT_STALE:
                self._counters["stale_artifact_block_count"] += 1
            elif record.reason == FallbackReason.V2_DATASET_VERSION_MISMATCH:
                self._counters["dataset_mismatch_block_count"] += 1
            elif record.reason == FallbackReason.V2_CONTEXT_GROUNDING_FAILURE:
                self._counters["evidence_grounding_failure_count"] += 1
            elif record.reason == FallbackReason.CIRCUIT_BREAKER_OPEN:
                self._counters["circuit_breaker_open_count"] += 1

    def increment_rollback_counter(self) -> None:
        """Increments the rollback counter."""
        with self._lock:
            self._counters["rollback_count"] += 1

    def get_telemetry(self) -> dict[str, Any]:
        """Returns a snapshot of all routing telemetry counters."""
        with self._lock:
            return {
                **self._counters,
                "fallback_reasons": dict(self._fallback_reason_counts),
                "per_consumer_routes": {
                    k.value: {rk.value: rv for rk, rv in v.items()}
                    for k, v in self._per_consumer_routes.items()
                },
                "total_decisions": len(self._decisions),
                "total_fallbacks": len(self._fallbacks),
            }

    def get_decisions(self) -> list[ConsumerRouteDecision]:
        """Returns all recorded routing decisions."""
        with self._lock:
            return list(self._decisions)

    def get_fallbacks(self) -> list[FallbackRecord]:
        """Returns all recorded fallback records."""
        with self._lock:
            return list(self._fallbacks)

    def reset_telemetry(self) -> None:
        """Resets all telemetry counters and clear decision logs (for isolated test runs)."""
        with self._lock:
            self._decisions.clear()
            self._fallbacks.clear()
            for k in self._counters:
                self._counters[k] = 0
            self._fallback_reason_counts.clear()
            for c in self._per_consumer_routes:
                self._per_consumer_routes[c] = {Route.V1: 0, Route.V2: 0}
