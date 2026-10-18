"""
HighView Ingestion V2 — Phase I8.2 Local Circuit Breakers
Stage: Governed Consumer Gateway & Safety Guards
Implements deterministic, in-memory circuit breaking per consumer without
external dependencies or distributed coordination.
"""

from __future__ import annotations

import threading
from datetime import datetime, timezone
from typing import Any

from app.services.ingestion_v2.contracts.cutover import (
    CircuitBreakerState,
    ConsumerName,
    FallbackReason,
)


class CircuitBreakerManager:
    """
    Thread-safe, deterministic circuit breaker protecting each consumer.
    - CLOSED: V2 requests allowed according to cutover state.
    - OPEN: V2 requests blocked; routed to V1 or governed fallback.
    - HALF_OPEN: Exactly one controlled canary validation request allowed.
    """

    def __init__(self, failure_threshold: int = 3) -> None:
        self.failure_threshold = failure_threshold
        self._lock = threading.Lock()
        self._states: dict[ConsumerName, CircuitBreakerState] = {
            ConsumerName.HRIDAY: CircuitBreakerState.CLOSED,
            ConsumerName.DASHBOARD: CircuitBreakerState.CLOSED,
            ConsumerName.PRESENTATION: CircuitBreakerState.CLOSED,
        }
        self._consecutive_failures: dict[ConsumerName, int] = {
            ConsumerName.HRIDAY: 0,
            ConsumerName.DASHBOARD: 0,
            ConsumerName.PRESENTATION: 0,
        }
        self._last_trip_reason: dict[ConsumerName, FallbackReason | None] = {
            ConsumerName.HRIDAY: None,
            ConsumerName.DASHBOARD: None,
            ConsumerName.PRESENTATION: None,
        }
        self._trip_timestamps: dict[ConsumerName, str | None] = {
            ConsumerName.HRIDAY: None,
            ConsumerName.DASHBOARD: None,
            ConsumerName.PRESENTATION: None,
        }
        self._total_trip_count: int = 0

    def get_state(self, consumer: ConsumerName) -> CircuitBreakerState:
        """Returns the current CircuitBreakerState for the consumer."""
        with self._lock:
            return self._states[consumer]

    def can_attempt_v2(self, consumer: ConsumerName) -> bool:
        """Returns True if the consumer's circuit breaker allows V2 execution."""
        with self._lock:
            state = self._states[consumer]
            return state in (CircuitBreakerState.CLOSED, CircuitBreakerState.HALF_OPEN)

    def record_success(self, consumer: ConsumerName) -> None:
        """
        Records a successful V2 request.
        Resets consecutive failure count and transitions HALF_OPEN -> CLOSED.
        """
        with self._lock:
            self._consecutive_failures[consumer] = 0
            if self._states[consumer] == CircuitBreakerState.HALF_OPEN:
                self._states[consumer] = CircuitBreakerState.CLOSED
                self._last_trip_reason[consumer] = None

    def record_failure(self, consumer: ConsumerName, reason: FallbackReason) -> bool:
        """
        Records a V2 failure.
        If in HALF_OPEN, immediately re-trips to OPEN.
        If in CLOSED, increments failure count and trips to OPEN if threshold reached.
        Returns True if the circuit breaker tripped OPEN on this failure.
        """
        with self._lock:
            current_state = self._states[consumer]

            if current_state == CircuitBreakerState.HALF_OPEN:
                # Probe failed, return immediately to OPEN
                self._states[consumer] = CircuitBreakerState.OPEN
                self._last_trip_reason[consumer] = reason
                self._trip_timestamps[consumer] = datetime.now(timezone.utc).isoformat()
                self._total_trip_count += 1
                return True

            self._consecutive_failures[consumer] += 1
            if self._consecutive_failures[consumer] >= self.failure_threshold:
                self._states[consumer] = CircuitBreakerState.OPEN
                self._last_trip_reason[consumer] = reason
                self._trip_timestamps[consumer] = datetime.now(timezone.utc).isoformat()
                self._total_trip_count += 1
                return True

            return False

    def trip(self, consumer: ConsumerName, reason: FallbackReason) -> None:
        """Forces the circuit breaker to OPEN immediately (e.g. on severe contract failure)."""
        with self._lock:
            self._states[consumer] = CircuitBreakerState.OPEN
            self._last_trip_reason[consumer] = reason
            self._trip_timestamps[consumer] = datetime.now(timezone.utc).isoformat()
            self._total_trip_count += 1

    def probe(self, consumer: ConsumerName) -> bool:
        """
        Transitions the circuit breaker from OPEN to HALF_OPEN for a controlled probe.
        Returns True if transitioned, False if already CLOSED or HALF_OPEN.
        """
        with self._lock:
            if self._states[consumer] == CircuitBreakerState.OPEN:
                self._states[consumer] = CircuitBreakerState.HALF_OPEN
                return True
            return False

    def reset(self, consumer: ConsumerName) -> None:
        """Resets the circuit breaker to CLOSED and clears failure counters."""
        with self._lock:
            self._states[consumer] = CircuitBreakerState.CLOSED
            self._consecutive_failures[consumer] = 0
            self._last_trip_reason[consumer] = None
            self._trip_timestamps[consumer] = None

    def get_trip_count(self) -> int:
        """Returns the total number of times any circuit breaker tripped OPEN."""
        with self._lock:
            return self._total_trip_count

    def get_last_trip_reason(self, consumer: ConsumerName) -> FallbackReason | None:
        """Returns the last trip reason for the consumer."""
        with self._lock:
            return self._last_trip_reason[consumer]
