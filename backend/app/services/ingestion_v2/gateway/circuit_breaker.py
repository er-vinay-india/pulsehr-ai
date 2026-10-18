"""
HighView Ingestion V2 — Phase I8.2 Local Circuit Breakers
Stage: Governed Consumer Gateway & Safety Guards
Implements deterministic, local circuit breaking per consumer without
external dependencies or distributed coordination.

Restart & Recovery Semantics:
- On process restart, runtime failure counters begin clean.
- Consumer cutover state does NOT reset (it is durably loaded from CutoverPersistenceStore).
- V2 execution strictly requires Gate 5 (ConsumerReadinessEvaluator) to validate manifest
  freshness, dataset versions, canonical artifact existence, and existential evidence grounding.
- Thus, process restart CANNOT bypass stale, missing, or ungrounded artifact guards.
- After trip to OPEN, time expiry marks a consumer ELIGIBLE for a probe.
- In HALF_OPEN, ordinary traffic remains strictly on V1; only an explicit recovery probe
  (is_probe=True) may test V2.
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
    - HALF_OPEN: Exactly one controlled probe evaluation allowed at a time; ordinary traffic stays V1.
    """

    def __init__(
        self,
        failure_threshold: int = 3,
        cooldown_seconds: float = 30.0,
        required_probe_successes: int = 2,
    ) -> None:
        self.failure_threshold = failure_threshold
        self.cooldown_seconds = cooldown_seconds
        self.required_probe_successes = required_probe_successes
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
        self._probe_success_count: dict[ConsumerName, int] = {
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
            self._check_and_update_cooldown(consumer)
            return self._states[consumer]

    def _check_and_update_cooldown(self, consumer: ConsumerName) -> None:
        """Internal helper: checks if cooldown has elapsed for an OPEN breaker."""
        if self._states[consumer] == CircuitBreakerState.OPEN:
            trip_time = self._trip_timestamps.get(consumer)
            if trip_time:
                try:
                    dt = datetime.fromisoformat(trip_time)
                    elapsed = (datetime.now(timezone.utc) - dt).total_seconds()
                    if elapsed >= self.cooldown_seconds:
                        self._states[consumer] = CircuitBreakerState.HALF_OPEN
                        self._probe_success_count[consumer] = 0
                except Exception:
                    pass

    def is_probe_eligible(self, consumer: ConsumerName) -> bool:
        """
        Returns True if the circuit breaker is eligible for a probe
        (either already HALF_OPEN or OPEN with elapsed cooldown).
        """
        with self._lock:
            self._check_and_update_cooldown(consumer)
            return self._states[consumer] == CircuitBreakerState.HALF_OPEN

    def can_attempt_v2(self, consumer: ConsumerName, is_probe: bool = False) -> bool:
        """
        Returns True if the consumer's circuit breaker allows V2 execution.
        - In CLOSED: returns True.
        - In HALF_OPEN: only an explicit recovery probe (is_probe=True) is allowed!
          Ordinary traffic returns False and routes to V1.
        - In OPEN: returns True ONLY if cooldown has elapsed AND is_probe=True (which transitions to HALF_OPEN).
        """
        with self._lock:
            self._check_and_update_cooldown(consumer)
            state = self._states[consumer]

            if state == CircuitBreakerState.CLOSED:
                return True
            if state == CircuitBreakerState.HALF_OPEN:
                return is_probe
            return False

    def record_success(self, consumer: ConsumerName) -> None:
        """
        Records a successful V2 request.
        If in HALF_OPEN, increments probe success count.
        Once required_probe_successes reached, transitions to CLOSED.
        """
        with self._lock:
            self._consecutive_failures[consumer] = 0
            if self._states[consumer] == CircuitBreakerState.HALF_OPEN:
                self._probe_success_count[consumer] += 1
                if self._probe_success_count[consumer] >= self.required_probe_successes:
                    self._states[consumer] = CircuitBreakerState.CLOSED
                    self._last_trip_reason[consumer] = None
                    self._trip_timestamps[consumer] = None
                    self._probe_success_count[consumer] = 0

    def record_failure(self, consumer: ConsumerName, reason: FallbackReason) -> bool:
        """
        Records a V2 failure.
        - If in HALF_OPEN: probe failed, immediately trips back to OPEN.
        - If in CLOSED: increments failure count; trips to OPEN when threshold reached.
        Returns True if the breaker tripped or re-tripped OPEN.
        """
        with self._lock:
            current_state = self._states[consumer]
            now_iso = datetime.now(timezone.utc).isoformat()

            if current_state == CircuitBreakerState.HALF_OPEN:
                # Probe failed, return immediately to OPEN
                self._states[consumer] = CircuitBreakerState.OPEN
                self._last_trip_reason[consumer] = reason
                self._trip_timestamps[consumer] = now_iso
                self._probe_success_count[consumer] = 0
                self._total_trip_count += 1
                return True

            self._consecutive_failures[consumer] += 1
            if self._consecutive_failures[consumer] >= self.failure_threshold:
                self._states[consumer] = CircuitBreakerState.OPEN
                self._last_trip_reason[consumer] = reason
                self._trip_timestamps[consumer] = now_iso
                self._total_trip_count += 1
                return True

            return False

    def trip(self, consumer: ConsumerName, reason: FallbackReason) -> None:
        """Forces the circuit breaker to OPEN immediately (e.g. on severe contract failure)."""
        with self._lock:
            self._states[consumer] = CircuitBreakerState.OPEN
            self._last_trip_reason[consumer] = reason
            self._trip_timestamps[consumer] = datetime.now(timezone.utc).isoformat()
            self._probe_success_count[consumer] = 0
            self._total_trip_count += 1

    def probe(self, consumer: ConsumerName) -> bool:
        """
        Transitions the circuit breaker from OPEN to HALF_OPEN for a controlled probe.
        Returns True if transitioned, False if already CLOSED or HALF_OPEN.
        """
        with self._lock:
            if self._states[consumer] == CircuitBreakerState.OPEN:
                self._states[consumer] = CircuitBreakerState.HALF_OPEN
                self._probe_success_count[consumer] = 0
                return True
            return False

    def reset(self, consumer: ConsumerName) -> None:
        """Resets the circuit breaker to CLOSED and clears failure counters."""
        with self._lock:
            self._states[consumer] = CircuitBreakerState.CLOSED
            self._consecutive_failures[consumer] = 0
            self._probe_success_count[consumer] = 0
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
