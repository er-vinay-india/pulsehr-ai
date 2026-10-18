"""
HighView Ingestion V2 — Phase I8.2 Consumer Cutover State Machine
Enforces strict, fail-closed cutover lifecycle transitions, ordering guards,
and rollback recovery validation for HRIDAY, Dashboard, and Presentation.
"""

from __future__ import annotations

import threading
from datetime import datetime, timezone
from typing import Any

from app.services.ingestion_v2.contracts.cutover import (
    CircuitBreakerState,
    ConsumerCutoverRecord,
    ConsumerName,
    CutoverState,
    CutoverTransitionLedgerEntry,
)


class InvalidCutoverTransitionError(ValueError):
    """Raised when an unauthorized or out-of-order cutover transition is attempted."""
    pass


class CutoverOrderingViolationError(ValueError):
    """Raised when a consumer attempts to advance before prerequisite consumers have certified."""
    pass


# Strict whitelist of permitted forward and rollback transitions
VALID_TRANSITIONS: dict[CutoverState, set[CutoverState]] = {
    CutoverState.SHADOW: {CutoverState.CERTIFIED, CutoverState.ROLLBACK},
    CutoverState.CERTIFIED: {CutoverState.CANARY, CutoverState.ROLLBACK},
    CutoverState.CANARY: {CutoverState.V2_PRIMARY_WITH_FALLBACK, CutoverState.ROLLBACK},
    CutoverState.V2_PRIMARY_WITH_FALLBACK: {CutoverState.V2_PRIMARY, CutoverState.ROLLBACK},
    CutoverState.V2_PRIMARY: {CutoverState.V1_RETIREMENT_ELIGIBLE, CutoverState.ROLLBACK},
    CutoverState.ROLLBACK: {
        CutoverState.SHADOW,
        CutoverState.CERTIFIED,
        CutoverState.CANARY,
        CutoverState.V2_PRIMARY_WITH_FALLBACK,
    },
    CutoverState.V1_RETIREMENT_ELIGIBLE: {CutoverState.ROLLBACK},
}

# State hierarchy rank for ordering prerequisites
STATE_RANK: dict[CutoverState, int] = {
    CutoverState.SHADOW: 0,
    CutoverState.CERTIFIED: 1,
    CutoverState.CANARY: 2,
    CutoverState.V2_PRIMARY_WITH_FALLBACK: 3,
    CutoverState.V2_PRIMARY: 4,
    CutoverState.V1_RETIREMENT_ELIGIBLE: 5,
    CutoverState.ROLLBACK: -1,
}


class ConsumerCutoverStateMachine:
    """
    Thread-safe, deterministic state machine managing the cutover state of all consumers.
    Enforces that:
    1. Every transition follows the valid transition graph (fails closed on invalid jumps).
    2. HRIDAY advances first, Dashboard advances second, Presentation advances third.
    3. Rollback can be triggered instantly from any state.
    4. Recovery from rollback requires explicit recovery validation.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._records: dict[ConsumerName, ConsumerCutoverRecord] = {
            ConsumerName.HRIDAY: ConsumerCutoverRecord(
                consumer_name=ConsumerName.HRIDAY,
                current_state=CutoverState.SHADOW,
                feature_enabled=False,
                fallback_allowed=True,
            ),
            ConsumerName.DASHBOARD: ConsumerCutoverRecord(
                consumer_name=ConsumerName.DASHBOARD,
                current_state=CutoverState.SHADOW,
                feature_enabled=False,
                fallback_allowed=True,
            ),
            ConsumerName.PRESENTATION: ConsumerCutoverRecord(
                consumer_name=ConsumerName.PRESENTATION,
                current_state=CutoverState.SHADOW,
                feature_enabled=False,
                fallback_allowed=True,
            ),
        }
        self._transition_history: list[CutoverTransitionLedgerEntry] = []

    def get_state(self, consumer: ConsumerName) -> CutoverState:
        """Returns the current CutoverState of the consumer."""
        with self._lock:
            return self._records[consumer].current_state

    def get_record(self, consumer: ConsumerName) -> ConsumerCutoverRecord:
        """Returns an immutable copy of the consumer's cutover record."""
        with self._lock:
            return self._records[consumer].model_copy()

    def get_all_records(self) -> dict[ConsumerName, ConsumerCutoverRecord]:
        """Returns copies of all consumer records."""
        with self._lock:
            return {k: v.model_copy() for k, v in self._records.items()}

    def transition(
        self,
        consumer: ConsumerName,
        target_state: CutoverState,
        reason: str,
        certification_evidence: str = "",
        commit: str = "HEAD",
        authorized_source: str = "control-plane",
        artifact_fingerprints: dict[str, str] | None = None,
    ) -> ConsumerCutoverRecord:
        """
        Executes a validated transition for a consumer.
        Fails closed with InvalidCutoverTransitionError or CutoverOrderingViolationError.
        """
        with self._lock:
            current_rec = self._records[consumer]
            current_state = current_rec.current_state

            # Idempotent no-op
            if current_state == target_state:
                return current_rec.model_copy()

            # 1. Validate against permitted transitions
            permitted = VALID_TRANSITIONS.get(current_state, set())
            if target_state not in permitted:
                raise InvalidCutoverTransitionError(
                    f"Illegal transition for consumer {consumer.value}: "
                    f"cannot move from {current_state.value} to {target_state.value}. "
                    f"Permitted next states: {[s.value for s in permitted]}"
                )

            # 2. Enforce cutover ordering prerequisites
            self._validate_ordering_constraints(consumer, target_state)

            now_iso = datetime.now(timezone.utc).isoformat()
            new_version = current_rec.transition_version + 1

            new_record = current_rec.model_copy(
                update={
                    "current_state": target_state,
                    "previous_state": current_state,
                    "transition_version": new_version,
                    "activated_at": now_iso if target_state in (CutoverState.CANARY, CutoverState.V2_PRIMARY_WITH_FALLBACK, CutoverState.V2_PRIMARY) else current_rec.activated_at,
                    "certification_run_id": certification_evidence if target_state == CutoverState.CERTIFIED else current_rec.certification_run_id,
                }
            )
            self._records[consumer] = new_record

            ledger_entry = CutoverTransitionLedgerEntry(
                transition_id=f"TR-{consumer.value}-{new_version:04d}",
                consumer=consumer,
                from_state=current_state,
                to_state=target_state,
                reason=reason,
                certification_evidence=certification_evidence,
                commit=commit,
                artifact_fingerprints=artifact_fingerprints or {},
                authorized_configuration_source=authorized_source,
                timestamp=now_iso,
            )
            self._transition_history.append(ledger_entry)
            return new_record.model_copy()

    def rollback(self, consumer: ConsumerName, reason: str, commit: str = "HEAD") -> ConsumerCutoverRecord:
        """
        Immediately transitions the consumer to ROLLBACK state from any active state.
        Safe, instantaneous, non-destructive to V2 data.
        """
        return self.transition(
            consumer=consumer,
            target_state=CutoverState.ROLLBACK,
            reason=f"EMERGENCY_ROLLBACK: {reason}",
            commit=commit,
            authorized_source="circuit-breaker/admin",
        )

    def recover_from_rollback(
        self,
        consumer: ConsumerName,
        target_state: CutoverState,
        recovery_validation_evidence: str,
        commit: str = "HEAD",
    ) -> ConsumerCutoverRecord:
        """
        Recovers a consumer from ROLLBACK to a verified safe state after explicit recovery validation.
        Cannot jump directly to V1_RETIREMENT_ELIGIBLE or V2_PRIMARY.
        """
        if target_state not in (CutoverState.SHADOW, CutoverState.CERTIFIED, CutoverState.CANARY, CutoverState.V2_PRIMARY_WITH_FALLBACK):
            raise InvalidCutoverTransitionError(
                f"Cannot recover from ROLLBACK directly to {target_state.value}. "
                "Must recover to SHADOW, CERTIFIED, CANARY, or V2_PRIMARY_WITH_FALLBACK."
            )
        if not recovery_validation_evidence.strip():
            raise ValueError("Recovery validation evidence is strictly required to exit ROLLBACK state.")

        return self.transition(
            consumer=consumer,
            target_state=target_state,
            reason=f"RECOVERY_VALIDATED: {recovery_validation_evidence}",
            certification_evidence=recovery_validation_evidence,
            commit=commit,
            authorized_source="recovery-validation",
        )

    def reset_to_shadow(self, consumer: ConsumerName) -> ConsumerCutoverRecord:
        """Resets consumer back to SHADOW (for hermetic test fixture isolation)."""
        with self._lock:
            rec = ConsumerCutoverRecord(
                consumer_name=consumer,
                current_state=CutoverState.SHADOW,
                previous_state=self._records[consumer].current_state,
                feature_enabled=False,
                fallback_allowed=True,
                circuit_breaker_state=CircuitBreakerState.CLOSED,
            )
            self._records[consumer] = rec
            return rec.model_copy()

    def _validate_ordering_constraints(self, consumer: ConsumerName, target_state: CutoverState) -> None:
        """
        Strict ordering enforcement:
        - Dashboard cannot enter CANARY or higher unless HRIDAY >= CERTIFIED.
        - Presentation cannot enter CANARY or higher unless Dashboard >= CERTIFIED.
        """
        target_rank = STATE_RANK.get(target_state, 0)
        canary_rank = STATE_RANK[CutoverState.CANARY]

        # Only check ordering when attempting to enter CANARY or higher
        if target_rank < canary_rank:
            return

        hriday_state = self._records[ConsumerName.HRIDAY].current_state
        dashboard_state = self._records[ConsumerName.DASHBOARD].current_state

        if consumer == ConsumerName.DASHBOARD:
            if STATE_RANK.get(hriday_state, -1) < STATE_RANK[CutoverState.CERTIFIED]:
                raise CutoverOrderingViolationError(
                    f"Ordering violation: DASHBOARD cannot enter {target_state.value} "
                    f"because HRIDAY is in {hriday_state.value} (must be >= CERTIFIED)."
                )

        elif consumer == ConsumerName.PRESENTATION:
            if STATE_RANK.get(dashboard_state, -1) < STATE_RANK[CutoverState.CERTIFIED]:
                raise CutoverOrderingViolationError(
                    f"Ordering violation: PRESENTATION cannot enter {target_state.value} "
                    f"because DASHBOARD is in {dashboard_state.value} (must be >= CERTIFIED)."
                )

    def get_transition_history(self) -> list[CutoverTransitionLedgerEntry]:
        """Returns the full audit log of all cutover transitions."""
        with self._lock:
            return list(self._transition_history)
