"""
HighView Semantic Data Refinery — Phase SDR-9
SDR Controlled Adoption Manager
The authoritative control plane orchestrating independent, reversible, version-bound,
and contract-bound consumer adoption of SDR governed truth.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.core import config
from app.services.ingestion_v2.contracts.cutover import (
    CircuitBreakerState,
    ConsumerName,
    FallbackReason,
    Route,
)
from app.services.sdr.adoption.contracts import (
    SDRAdoptionRecord,
    SDRAdoptionState,
    SDREligibilityAssessment,
    SDRRouteDecision,
)
from app.services.sdr.adoption.eligibility import SDREligibilityEvaluator
from app.services.sdr.adoption.telemetry import (
    SDRAdoptionTelemetryLedger,
    get_adoption_telemetry,
)

ROUTE_V2 = getattr(Route, "V2")

logger = logging.getLogger(__name__)


# Permitted state transition rules for SDR adoption
VALID_SDR_TRANSITIONS: dict[SDRAdoptionState, set[SDRAdoptionState]] = {
    SDRAdoptionState.SHADOW: {SDRAdoptionState.CERTIFIED, SDRAdoptionState.ROLLBACK},
    SDRAdoptionState.CERTIFIED: {SDRAdoptionState.CANARY, SDRAdoptionState.ROLLBACK},
    SDRAdoptionState.CANARY: {SDRAdoptionState.SDR_PRIMARY_WITH_V2_FALLBACK, SDRAdoptionState.ROLLBACK},
    SDRAdoptionState.SDR_PRIMARY_WITH_V2_FALLBACK: {SDRAdoptionState.SDR_PRIMARY, SDRAdoptionState.ROLLBACK},
    SDRAdoptionState.SDR_PRIMARY: {SDRAdoptionState.SDR_RETIREMENT_ELIGIBLE, SDRAdoptionState.ROLLBACK},
    SDRAdoptionState.ROLLBACK: {
        SDRAdoptionState.SHADOW,
        SDRAdoptionState.CERTIFIED,
        SDRAdoptionState.CANARY,
        SDRAdoptionState.SDR_PRIMARY_WITH_V2_FALLBACK,
    },
    SDRAdoptionState.SDR_RETIREMENT_ELIGIBLE: {SDRAdoptionState.ROLLBACK},
}


class SDRAdoptionManager:
    """
    Manages independent consumer adoption states, canary routing,
    multi-tier fallback, and fail-closed safety gates outside P0.
    """

    def __init__(
        self,
        base_data_dir: Path | str | None = None,
        telemetry_ledger: SDRAdoptionTelemetryLedger | None = None,
    ):
        self._lock = threading.Lock()
        self.base_dir = Path(base_data_dir) if base_data_dir else getattr(config, "DATA_DIR", Path("data"))
        self.state_file = self.base_dir / "sdr_adoption_state.json"
        self.telemetry = telemetry_ledger or get_adoption_telemetry()

        # Global kill switch override
        self._override_global_kill_switch: bool | None = None

        # Manual overrides per consumer
        self._manual_overrides: dict[ConsumerName, Route | None] = {
            ConsumerName.HRIDAY: None,
            ConsumerName.DASHBOARD: None,
            ConsumerName.PRESENTATION: None,
        }

        # Circuit breaker tracking for SDR runtime failures
        self._failure_counts: dict[ConsumerName, int] = {
            ConsumerName.HRIDAY: 0,
            ConsumerName.DASHBOARD: 0,
            ConsumerName.PRESENTATION: 0,
        }
        self._circuit_states: dict[ConsumerName, CircuitBreakerState] = {
            ConsumerName.HRIDAY: CircuitBreakerState.CLOSED,
            ConsumerName.DASHBOARD: CircuitBreakerState.CLOSED,
            ConsumerName.PRESENTATION: CircuitBreakerState.CLOSED,
        }
        self.failure_threshold: int = 3

        # Load or initialize durable records
        self._records = self._load_records()

    def _default_records(self) -> dict[ConsumerName, SDRAdoptionRecord]:
        return {
            ConsumerName.HRIDAY: SDRAdoptionRecord(
                consumer=ConsumerName.HRIDAY,
                adoption_state=SDRAdoptionState.CERTIFIED,
                canary_percentage=0.0,
                canary_datasets=["sdr8_wfo", "sdr8_retail"],
            ),
            ConsumerName.DASHBOARD: SDRAdoptionRecord(
                consumer=ConsumerName.DASHBOARD,
                adoption_state=SDRAdoptionState.CERTIFIED,
                canary_percentage=0.0,
                canary_datasets=["sdr8_wfo", "sdr8_retail"],
            ),
            ConsumerName.PRESENTATION: SDRAdoptionRecord(
                consumer=ConsumerName.PRESENTATION,
                adoption_state=SDRAdoptionState.CERTIFIED,
                canary_percentage=0.0,
                canary_datasets=["sdr8_wfo", "sdr8_retail"],
            ),
        }

    def _load_records(self) -> dict[ConsumerName, SDRAdoptionRecord]:
        if self.state_file.exists():
            try:
                with open(self.state_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    records = {}
                    for c in [ConsumerName.HRIDAY, ConsumerName.DASHBOARD, ConsumerName.PRESENTATION]:
                        if c.value in data:
                            records[c] = SDRAdoptionRecord.model_validate(data[c.value])
                    if len(records) == 3:
                        return records
            except Exception as exc:
                logger.warning("Failed to load durable SDR adoption state from %s: %s", self.state_file, exc)
        return self._default_records()

    def _save_records(self) -> None:
        try:
            self.state_file.parent.mkdir(parents=True, exist_ok=True)
            data = {c.value: rec.model_dump() for c, rec in self._records.items()}
            with open(self.state_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
        except Exception as exc:
            logger.warning("Failed to save durable SDR adoption state to %s: %s", self.state_file, exc)

    # =========================================================================
    # 1. STATE INSPECTION & TRANSITION
    # =========================================================================
    def get_adoption_state(self, consumer: ConsumerName) -> SDRAdoptionState:
        with self._lock:
            return self._records[consumer].adoption_state

    def get_record(self, consumer: ConsumerName) -> SDRAdoptionRecord:
        with self._lock:
            return self._records[consumer].model_copy()

    def transition_adoption_state(
        self,
        consumer: ConsumerName,
        target_state: SDRAdoptionState,
        reason: str,
        canary_percentage: float | None = None,
        canary_datasets: list[str] | None = None,
    ) -> SDRAdoptionRecord:
        """Executes a validated transition for a consumer's SDR adoption state."""
        with self._lock:
            rec = self._records[consumer]
            current_state = rec.adoption_state

            if current_state == target_state:
                return rec.model_copy()

            permitted = VALID_SDR_TRANSITIONS.get(current_state, set())
            if target_state not in permitted:
                raise ValueError(
                    f"Illegal SDR adoption transition for {consumer.value}: "
                    f"cannot move from {current_state.value} to {target_state.value}. "
                    f"Permitted: {[s.value for s in permitted]}"
                )

            now_iso = datetime.now(timezone.utc).isoformat()
            updated = rec.model_copy(
                update={
                    "adoption_state": target_state,
                    "previous_state": current_state,
                    "canary_percentage": canary_percentage if canary_percentage is not None else rec.canary_percentage,
                    "canary_datasets": canary_datasets if canary_datasets is not None else rec.canary_datasets,
                    "last_transition_timestamp": now_iso,
                    "activated_at": now_iso if target_state in (SDRAdoptionState.CANARY, SDRAdoptionState.SDR_PRIMARY_WITH_V2_FALLBACK) else rec.activated_at,
                }
            )
            self._records[consumer] = updated
            self._save_records()
            return updated.model_copy()

    def rollback(self, consumer: ConsumerName, reason: str) -> SDRAdoptionRecord:
        """Instantly rolls back a single consumer to ROLLBACK state, forcing V2 route."""
        return self.transition_adoption_state(
            consumer=consumer,
            target_state=SDRAdoptionState.ROLLBACK,
            reason=f"SDR_ROLLBACK: {reason}",
        )

    def recover_from_rollback(
        self,
        consumer: ConsumerName,
        target_state: SDRAdoptionState,
        recovery_evidence: str,
    ) -> SDRAdoptionRecord:
        """Exits ROLLBACK state after verified recovery validation."""
        if target_state not in (SDRAdoptionState.SHADOW, SDRAdoptionState.CERTIFIED, SDRAdoptionState.CANARY, SDRAdoptionState.SDR_PRIMARY_WITH_V2_FALLBACK):
            raise ValueError(f"Cannot recover from ROLLBACK directly to {target_state.value}")
        if not recovery_evidence.strip():
            raise ValueError("Recovery validation evidence is required to exit ROLLBACK.")

        return self.transition_adoption_state(
            consumer=consumer,
            target_state=target_state,
            reason=f"RECOVERY_VALIDATED: {recovery_evidence}",
        )

    # =========================================================================
    # 2. EMERGENCY OVERRIDES & CIRCUIT BREAKER
    # =========================================================================
    def set_global_kill_switch(self, active: bool | None) -> None:
        self._override_global_kill_switch = active

    def is_global_kill_switch_active(self) -> bool:
        if self._override_global_kill_switch is not None:
            return self._override_global_kill_switch
        env_val = os.getenv("HIGHVIEW_SDR_GLOBAL_KILL_SWITCH")
        if env_val is not None:
            return env_val.lower() in ("true", "1", "yes")
        return False

    def set_manual_override(self, consumer: ConsumerName, route: Route | None) -> None:
        self._manual_overrides[consumer] = route

    def record_failure(self, consumer: ConsumerName, reason: FallbackReason) -> None:
        with self._lock:
            self._failure_counts[consumer] += 1
            if self._failure_counts[consumer] >= self.failure_threshold:
                self._circuit_states[consumer] = CircuitBreakerState.OPEN
            rec = self._records[consumer]
            self._records[consumer] = rec.model_copy(
                update={
                    "fallback_count": rec.fallback_count + 1,
                    "last_fallback_reason": reason,
                }
            )
            self._save_records()

    def record_success(self, consumer: ConsumerName) -> None:
        with self._lock:
            self._failure_counts[consumer] = 0
            if self._circuit_states[consumer] == CircuitBreakerState.HALF_OPEN:
                self._circuit_states[consumer] = CircuitBreakerState.CLOSED

    def reset_circuit_breaker(self, consumer: ConsumerName) -> None:
        with self._lock:
            self._failure_counts[consumer] = 0
            self._circuit_states[consumer] = CircuitBreakerState.CLOSED

    # =========================================================================
    # 3. ROUTE EVALUATION
    # =========================================================================
    def evaluate_route(
        self,
        consumer: ConsumerName,
        dataset_id: str | None = None,
        dataset_version: str | None = None,
        is_canary_request: bool = False,
        canary_authorized: bool = False,
        cohort: str | None = None,
        expected_contract_fingerprint: str | None = None,
        manifest_data: dict[str, Any] | None = None,
    ) -> SDRRouteDecision:
        """
        The authoritative SDR controlled adoption routing engine.
        Evaluates gates in strict fail-closed order:
        1. Global Kill Switch
        2. Manual Override
        3. Consumer Rollback State
        4. Adoption State (SHADOW / CERTIFIED -> route V2)
        5. Circuit Breaker
        6. Canary Authorization
        7. Artifact & Semantic Eligibility (version, contract, stale, unsafe, ambiguous)
        Returns strongly-typed SDRRouteDecision and updates adoption telemetry.
        """
        decision_id = f"SDR-DEC-{uuid.uuid4().hex[:10].upper()}"
        now_iso = datetime.now(timezone.utc).isoformat()
        rec = self.get_record(consumer)
        state = rec.adoption_state
        cb_state = self._circuit_states[consumer]

        # Gate 1: Global Kill Switch
        if self.is_global_kill_switch_active():
            dec = SDRRouteDecision(
                decision_id=decision_id,
                timestamp=now_iso,
                consumer=consumer,
                requested_route=Route.SDR,
                selected_route=ROUTE_V2,
                adoption_state=state,
                dataset_id=dataset_id,
                dataset_version=dataset_version,
                fallback_used=True,
                fallback_reason=FallbackReason.KILL_SWITCH_ACTIVE,
                internal_diagnostic_reason="GLOBAL_KILL_SWITCH_ACTIVE",
                rationale="SDR adoption global kill switch is active. Immediate fallback to authoritative V2.",
            )
            self.telemetry.record_decision(dec)
            return dec

        # Gate 2: Manual Override
        man_override = self._manual_overrides.get(consumer)
        if man_override == ROUTE_V2:
            dec = SDRRouteDecision(
                decision_id=decision_id,
                timestamp=now_iso,
                consumer=consumer,
                requested_route=Route.SDR,
                selected_route=ROUTE_V2,
                adoption_state=state,
                dataset_id=dataset_id,
                dataset_version=dataset_version,
                fallback_used=True,
                fallback_reason=FallbackReason.MANUAL_OVERRIDE,
                internal_diagnostic_reason="MANUAL_OVERRIDE_V2",
                rationale="Manual administrative override forces V2 routing.",
            )
            self.telemetry.record_decision(dec)
            return dec

        # Gate 3: Consumer Rollback State
        if state == SDRAdoptionState.ROLLBACK:
            dec = SDRRouteDecision(
                decision_id=decision_id,
                timestamp=now_iso,
                consumer=consumer,
                requested_route=Route.SDR,
                selected_route=ROUTE_V2,
                adoption_state=state,
                dataset_id=dataset_id,
                dataset_version=dataset_version,
                fallback_used=True,
                fallback_reason=FallbackReason.CONSUMER_ROLLBACK_ACTIVE,
                internal_diagnostic_reason="CONSUMER_ROLLBACK_ACTIVE",
                rationale=f"Consumer {consumer.value} is in ROLLBACK state. Immediate fallback to V2.",
            )
            self.telemetry.record_decision(dec)
            return dec

        # Gate 4: Starting States (SHADOW, CERTIFIED)
        if state in (SDRAdoptionState.SHADOW, SDRAdoptionState.CERTIFIED):
            dec = SDRRouteDecision(
                decision_id=decision_id,
                timestamp=now_iso,
                consumer=consumer,
                requested_route=Route.SDR,
                selected_route=ROUTE_V2,
                adoption_state=state,
                dataset_id=dataset_id,
                dataset_version=dataset_version,
                fallback_used=False,
                fallback_reason=None,
                internal_diagnostic_reason="STATE_NOT_ADOPTED",
                rationale=f"Consumer {consumer.value} in {state.value} state. Authoritative route remains V2.",
            )
            self.telemetry.record_decision(dec)
            return dec

        # Gate 5: Circuit Breaker
        if cb_state == CircuitBreakerState.OPEN:
            dec = SDRRouteDecision(
                decision_id=decision_id,
                timestamp=now_iso,
                consumer=consumer,
                requested_route=Route.SDR,
                selected_route=ROUTE_V2,
                adoption_state=state,
                dataset_id=dataset_id,
                dataset_version=dataset_version,
                fallback_used=True,
                fallback_reason=FallbackReason.CIRCUIT_BREAKER_OPEN,
                internal_diagnostic_reason="CIRCUIT_BREAKER_OPEN",
                rationale=f"Circuit breaker for {consumer.value} is OPEN due to repeated SDR runtime failures.",
            )
            self.telemetry.record_decision(dec)
            return dec

        # Gate 6: Canary Authorization
        is_canary = False
        canary_auth = False
        if state == SDRAdoptionState.CANARY:
            is_canary = True
            if is_canary_request or canary_authorized:
                canary_auth = True
            elif dataset_id and dataset_id in rec.canary_datasets:
                canary_auth = True
            elif cohort and rec.canary_percentage:
                chash = hashlib.sha256(cohort.encode("utf-8")).hexdigest()
                score = (int(chash[:8], 16) % 10000) / 100.0
                if score < rec.canary_percentage:
                    canary_auth = True

            if not canary_auth:
                dec = SDRRouteDecision(
                    decision_id=decision_id,
                    timestamp=now_iso,
                    consumer=consumer,
                    requested_route=Route.SDR,
                    selected_route=ROUTE_V2,
                    adoption_state=state,
                    dataset_id=dataset_id,
                    dataset_version=dataset_version,
                    is_canary=True,
                    canary_authorized=False,
                    fallback_used=False,
                    fallback_reason=FallbackReason.CANARY_NOT_AUTHORIZED,
                    internal_diagnostic_reason="CANARY_NOT_AUTHORIZED",
                    rationale=f"Consumer {consumer.value} in CANARY state: non-canary request routed to V2.",
                )
                self.telemetry.record_decision(dec)
                return dec

        # Gate 7: Eligibility & Safety Evaluation
        if dataset_id:
            assessment = SDREligibilityEvaluator.evaluate(
                dataset_id=dataset_id,
                requested_version=dataset_version,
                expected_contract_fingerprint=expected_contract_fingerprint,
                manifest_data=manifest_data,
                base_data_dir=self.base_dir,
            )
            if not assessment.is_eligible:
                primary_fb = assessment.fallback_reason or FallbackReason.V2_RUNTIME_ERROR
                self.record_failure(consumer, primary_fb)
                dec = SDRRouteDecision(
                    decision_id=decision_id,
                    timestamp=now_iso,
                    consumer=consumer,
                    requested_route=Route.SDR,
                    selected_route=ROUTE_V2,
                    adoption_state=state,
                    dataset_id=dataset_id,
                    dataset_version=assessment.dataset_version,
                    sdr_artifact_fingerprint=assessment.sdr_artifact_fingerprint,
                    consumer_contract_fingerprint=assessment.consumer_contract_fingerprint,
                    is_canary=is_canary,
                    canary_authorized=canary_auth,
                    fallback_used=True,
                    fallback_reason=primary_fb,
                    internal_diagnostic_reason="; ".join(assessment.rejection_reasons),
                    rationale=f"SDR eligibility failed ({'; '.join(assessment.rejection_reasons)}). Fallback to V2.",
                )
                self.telemetry.record_decision(dec)
                return dec
        else:
            assessment = None

        # Success: Route to SDR
        sdr_fp = assessment.sdr_artifact_fingerprint if assessment else None
        con_fp = assessment.consumer_contract_fingerprint if assessment else None
        actual_ver = assessment.dataset_version if assessment else dataset_version

        dec = SDRRouteDecision(
            decision_id=decision_id,
            timestamp=now_iso,
            consumer=consumer,
            requested_route=Route.SDR,
            selected_route=Route.SDR,
            adoption_state=state,
            dataset_id=dataset_id,
            dataset_version=actual_ver,
            sdr_artifact_fingerprint=sdr_fp,
            consumer_contract_fingerprint=con_fp,
            is_canary=is_canary,
            canary_authorized=canary_auth,
            fallback_used=False,
            fallback_reason=None,
            internal_diagnostic_reason=None,
            rationale="SDR route authorized: all safety gates, version bindings, and contract checks passed.",
        )
        self.telemetry.record_decision(dec)
        return dec

    def reset(self) -> None:
        """Resets adoption states to default CERTIFIED baseline."""
        with self._lock:
            self._records = self._default_records()
            self._save_records()
            self._override_global_kill_switch = None
            for c in [ConsumerName.HRIDAY, ConsumerName.DASHBOARD, ConsumerName.PRESENTATION]:
                self._manual_overrides[c] = None
                self._failure_counts[c] = 0
                self._circuit_states[c] = CircuitBreakerState.CLOSED
            self.telemetry.reset()


_shared_adoption_manager: SDRAdoptionManager | None = None


def get_sdr_adoption_manager() -> SDRAdoptionManager:
    global _shared_adoption_manager
    if _shared_adoption_manager is None:
        _shared_adoption_manager = SDRAdoptionManager()
    return _shared_adoption_manager
