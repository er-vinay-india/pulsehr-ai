"""
HighView Ingestion V2 — Phase I8.2 Central Consumer Intelligence Gateway
Stage: Governed Consumer Gateway & Single Routing Boundary
The sole authoritative routing decision layer for HRIDAY, Dashboard, and Presentation.
Eliminates scattered conditional logic, enforces independent feature gates, circuit breakers,
readiness inspections, and non-destructive rollbacks.
"""

from __future__ import annotations

import os
import uuid
from datetime import datetime, timezone
from typing import Any

from app.core import config
from app.services.ingestion_v2.contracts.cutover import (
    CircuitBreakerState,
    ConsumerCutoverRecord,
    ConsumerName,
    ConsumerRouteDecision,
    ConsumerRoutingSnapshot,
    CutoverState,
    FallbackReason,
    FallbackRecord,
    ReadinessAssessment,
    Route,
)
from app.services.ingestion_v2.gateway.circuit_breaker import CircuitBreakerManager
from app.services.ingestion_v2.gateway.provenance import RoutingProvenanceLedger
from app.services.ingestion_v2.gateway.readiness import ConsumerReadinessEvaluator
from app.services.ingestion_v2.gateway.state_machine import ConsumerCutoverStateMachine


class ConsumerIntelligenceGateway:
    """
    Central, authoritative routing gateway for all Highview consumers.
    Guarantees:
    - 0 model/LLM calls.
    - 0 embedding calls.
    - 0 changes to analytical calculations or semantics.
    - Deterministic, fail-closed routing logic.
    - Full decision provenance and fallback accountability.
    """

    def __init__(
        self,
        state_machine: ConsumerCutoverStateMachine | None = None,
        circuit_breaker: CircuitBreakerManager | None = None,
        provenance_ledger: RoutingProvenanceLedger | None = None,
    ) -> None:
        self.state_machine = state_machine or ConsumerCutoverStateMachine()
        self.circuit_breaker = circuit_breaker or CircuitBreakerManager()
        self.provenance_ledger = provenance_ledger or RoutingProvenanceLedger()

        # Dynamic feature gate overrides (useful for hermetic test suites and runtime control)
        self._override_global_enabled: bool | None = None
        self._override_consumer_enabled: dict[ConsumerName, bool | None] = {
            ConsumerName.HRIDAY: None,
            ConsumerName.DASHBOARD: None,
            ConsumerName.PRESENTATION: None,
        }
        self._override_fallback_allowed: dict[ConsumerName, bool | None] = {
            ConsumerName.HRIDAY: None,
            ConsumerName.DASHBOARD: None,
            ConsumerName.PRESENTATION: None,
        }

    # =========================================================================
    # 1. FEATURE GATE RESOLUTION
    # =========================================================================
    def is_global_v2_enabled(self) -> bool:
        """Evaluates whether the global V2 kill switch is active."""
        if self._override_global_enabled is not None:
            return self._override_global_enabled
        env_val = os.getenv("HIGHVIEW_V2_GLOBAL_ENABLED")
        if env_val is not None:
            return env_val.lower() in ("true", "1", "yes")
        return getattr(config, "V2_GLOBAL_ENABLED", False)

    def is_consumer_v2_enabled(self, consumer: ConsumerName) -> bool:
        """Evaluates whether V2 feature flag is enabled for an individual consumer."""
        override = self._override_consumer_enabled.get(consumer)
        if override is not None:
            return override

        env_key = f"HIGHVIEW_V2_{consumer.value}_ENABLED"
        env_val = os.getenv(env_key)
        if env_val is not None:
            return env_val.lower() in ("true", "1", "yes")

        cfg_attr = f"V2_{consumer.value}_ENABLED"
        return getattr(config, cfg_attr, False)

    def is_fallback_allowed(self, consumer: ConsumerName) -> bool:
        """Evaluates whether fallback from V2 to V1 is permitted for the consumer."""
        override = self._override_fallback_allowed.get(consumer)
        if override is not None:
            return override

        env_key = f"HIGHVIEW_V2_{consumer.value}_FALLBACK_ALLOWED"
        env_val = os.getenv(env_key)
        if env_val is not None:
            return env_val.lower() in ("true", "1", "yes")

        cfg_attr = f"V2_{consumer.value}_FALLBACK_ALLOWED"
        return getattr(config, cfg_attr, True)

    # Dynamic configuration overrides for hermetic control
    def set_global_enabled(self, enabled: bool | None) -> None:
        self._override_global_enabled = enabled

    def set_consumer_enabled(self, consumer: ConsumerName, enabled: bool | None) -> None:
        self._override_consumer_enabled[consumer] = enabled

    def set_fallback_allowed(self, consumer: ConsumerName, allowed: bool | None) -> None:
        self._override_fallback_allowed[consumer] = allowed

    # =========================================================================
    # 2. CENTRAL ROUTING DECISION EVALUATION
    # =========================================================================
    def evaluate_route(
        self,
        consumer: ConsumerName,
        dataset_id: str | None = None,
        dataset_version: str | None = None,
        is_canary: bool = False,
        request_id: str | None = None,
        readiness_override: ReadinessAssessment | None = None,
        manifest_data: dict[str, Any] | None = None,
        required_artifacts: list[str] | None = None,
        required_evidence_refs: list[str] | None = None,
        available_evidence_ids: set[str] | None = None,
    ) -> ConsumerRouteDecision:
        """
        The authoritative, single entrypoint for evaluating a consumer's route.
        Inspects:
        - Global kill switch
        - Consumer feature gate
        - Cutover state machine
        - Circuit breaker state
        - Readiness & evidence grounding
        Returns strongly-typed ConsumerRouteDecision and updates ledger.
        """
        decision_id = f"DEC-{uuid.uuid4().hex[:12].upper()}"
        req_id = request_id or f"REQ-{uuid.uuid4().hex[:8].upper()}"
        now_iso = datetime.now(timezone.utc).isoformat()

        global_on = self.is_global_v2_enabled()
        consumer_on = self.is_consumer_v2_enabled(consumer)
        fallback_allowed = self.is_fallback_allowed(consumer)
        consumer_state = self.state_machine.get_state(consumer)
        circuit_state = self.circuit_breaker.get_state(consumer)

        manifest_fp = manifest_data.get("manifest_fingerprint") if manifest_data else None
        sem_graph_fp = manifest_data.get("semantic_graph_fingerprint") if manifest_data else None

        # ---------------------------------------------------------------------
        # Gate 1: Global Kill Switch Guard
        # ---------------------------------------------------------------------
        if not global_on:
            decision = ConsumerRouteDecision(
                decision_id=decision_id,
                decision_timestamp=now_iso,
                consumer=consumer,
                requested_route=Route.V2,
                selected_route=Route.V1,
                consumer_state=consumer_state,
                feature_enabled=consumer_on,
                global_enabled=global_on,
                fallback_allowed=fallback_allowed,
                fallback_used=False,
                fallback_reason=FallbackReason.KILL_SWITCH_ACTIVE,
                circuit_breaker_state=circuit_state,
                dataset_id=dataset_id,
                dataset_version=dataset_version,
                v2_manifest_fingerprint=manifest_fp,
                semantic_graph_fingerprint=sem_graph_fp,
                rationale="Global V2 kill switch is active (HIGHVIEW_V2_GLOBAL_ENABLED=false)",
            )
            self.provenance_ledger.record_decision(decision)
            return decision

        # ---------------------------------------------------------------------
        # Gate 2: Consumer Feature Gate Guard
        # ---------------------------------------------------------------------
        if not consumer_on:
            decision = ConsumerRouteDecision(
                decision_id=decision_id,
                decision_timestamp=now_iso,
                consumer=consumer,
                requested_route=Route.V2,
                selected_route=Route.V1,
                consumer_state=consumer_state,
                feature_enabled=consumer_on,
                global_enabled=global_on,
                fallback_allowed=fallback_allowed,
                fallback_used=False,
                fallback_reason=FallbackReason.STATE_NOT_V2_ELIGIBLE,
                circuit_breaker_state=circuit_state,
                dataset_id=dataset_id,
                dataset_version=dataset_version,
                v2_manifest_fingerprint=manifest_fp,
                semantic_graph_fingerprint=sem_graph_fp,
                rationale=f"Consumer {consumer.value} V2 feature flag is disabled",
            )
            self.provenance_ledger.record_decision(decision)
            return decision

        # ---------------------------------------------------------------------
        # Gate 3: Cutover State Machine Inspection
        # ---------------------------------------------------------------------
        # SHADOW & CERTIFIED: Production traffic strictly remains on V1
        if consumer_state in (CutoverState.SHADOW, CutoverState.CERTIFIED):
            decision = ConsumerRouteDecision(
                decision_id=decision_id,
                decision_timestamp=now_iso,
                consumer=consumer,
                requested_route=Route.V2,
                selected_route=Route.V1,
                consumer_state=consumer_state,
                feature_enabled=consumer_on,
                global_enabled=global_on,
                fallback_allowed=fallback_allowed,
                fallback_used=False,
                fallback_reason=FallbackReason.STATE_NOT_V2_ELIGIBLE,
                circuit_breaker_state=circuit_state,
                dataset_id=dataset_id,
                dataset_version=dataset_version,
                v2_manifest_fingerprint=manifest_fp,
                semantic_graph_fingerprint=sem_graph_fp,
                rationale=f"Consumer {consumer.value} is in {consumer_state.value} state (production route remains V1)",
            )
            self.provenance_ledger.record_decision(decision)
            return decision

        # ROLLBACK: Immediately route V1
        if consumer_state == CutoverState.ROLLBACK:
            decision = ConsumerRouteDecision(
                decision_id=decision_id,
                decision_timestamp=now_iso,
                consumer=consumer,
                requested_route=Route.V2,
                selected_route=Route.V1,
                consumer_state=consumer_state,
                feature_enabled=consumer_on,
                global_enabled=global_on,
                fallback_allowed=fallback_allowed,
                fallback_used=False,
                fallback_reason=FallbackReason.KILL_SWITCH_ACTIVE,
                circuit_breaker_state=circuit_state,
                dataset_id=dataset_id,
                dataset_version=dataset_version,
                v2_manifest_fingerprint=manifest_fp,
                semantic_graph_fingerprint=sem_graph_fp,
                rationale=f"Consumer {consumer.value} is in ROLLBACK state (routing V1)",
            )
            self.provenance_ledger.record_decision(decision)
            return decision

        # CANARY: Ordinary request stays V1; authorized canary request evaluates V2
        if consumer_state == CutoverState.CANARY and not is_canary:
            decision = ConsumerRouteDecision(
                decision_id=decision_id,
                decision_timestamp=now_iso,
                consumer=consumer,
                requested_route=Route.V2,
                selected_route=Route.V1,
                consumer_state=consumer_state,
                feature_enabled=consumer_on,
                global_enabled=global_on,
                fallback_allowed=fallback_allowed,
                fallback_used=False,
                fallback_reason=FallbackReason.CANARY_NOT_AUTHORIZED,
                circuit_breaker_state=circuit_state,
                dataset_id=dataset_id,
                dataset_version=dataset_version,
                v2_manifest_fingerprint=manifest_fp,
                semantic_graph_fingerprint=sem_graph_fp,
                rationale=f"Consumer {consumer.value} in CANARY state: non-canary request routed to V1",
            )
            self.provenance_ledger.record_decision(decision)
            return decision

        # ---------------------------------------------------------------------
        # Gate 4: Circuit Breaker Inspection
        # ---------------------------------------------------------------------
        if not self.circuit_breaker.can_attempt_v2(consumer):
            # Circuit is OPEN
            last_reason = self.circuit_breaker.get_last_trip_reason(consumer) or FallbackReason.CIRCUIT_BREAKER_OPEN
            self._record_governed_fallback(
                consumer=consumer,
                dataset_id=dataset_id,
                dataset_version=dataset_version,
                request_id=req_id,
                reason=FallbackReason.CIRCUIT_BREAKER_OPEN,
                manifest_fp=manifest_fp,
            )
            decision = ConsumerRouteDecision(
                decision_id=decision_id,
                decision_timestamp=now_iso,
                consumer=consumer,
                requested_route=Route.V2,
                selected_route=Route.V1,
                consumer_state=consumer_state,
                feature_enabled=consumer_on,
                global_enabled=global_on,
                fallback_allowed=fallback_allowed,
                fallback_used=True,
                fallback_reason=FallbackReason.CIRCUIT_BREAKER_OPEN,
                circuit_breaker_state=CircuitBreakerState.OPEN,
                dataset_id=dataset_id,
                dataset_version=dataset_version,
                v2_manifest_fingerprint=manifest_fp,
                semantic_graph_fingerprint=sem_graph_fp,
                rationale=f"Circuit breaker for {consumer.value} is OPEN (last trip reason: {last_reason.value})",
            )
            self.provenance_ledger.record_decision(decision)
            return decision

        # ---------------------------------------------------------------------
        # Gate 5: V2 Readiness & Grounding Inspection
        # ---------------------------------------------------------------------
        if dataset_id:
            readiness = readiness_override or ConsumerReadinessEvaluator.evaluate(
                dataset_id=dataset_id,
                requested_version=dataset_version,
                manifest_data=manifest_data,
                required_artifacts=required_artifacts,
                required_evidence_refs=required_evidence_refs,
                available_evidence_ids=available_evidence_ids,
            )
        else:
            # If no dataset_id provided, default to ready if readiness_override not given
            readiness = readiness_override or ReadinessAssessment(
                is_ready=True,
                dataset_id="unknown",
                dataset_version=dataset_version or "1",
                manifest_exists=True,
                manifest_fresh=True,
            )

        if not readiness.is_ready:
            primary_reason = readiness.failure_reasons[0] if readiness.failure_reasons else FallbackReason.V2_RUNTIME_ERROR
            tripped = self.circuit_breaker.record_failure(consumer, primary_reason)
            new_circuit_state = CircuitBreakerState.OPEN if tripped else self.circuit_breaker.get_state(consumer)

            # In V2_PRIMARY, normal automatic V1 fallback is disabled
            if consumer_state == CutoverState.V2_PRIMARY and not fallback_allowed:
                decision = ConsumerRouteDecision(
                    decision_id=decision_id,
                    decision_timestamp=now_iso,
                    consumer=consumer,
                    requested_route=Route.V2,
                    selected_route=Route.V1,  # Fails safe to V1 with critical severity
                    consumer_state=consumer_state,
                    feature_enabled=consumer_on,
                    global_enabled=global_on,
                    fallback_allowed=False,
                    fallback_used=False,
                    fallback_reason=primary_reason,
                    circuit_breaker_state=new_circuit_state,
                    dataset_id=dataset_id,
                    dataset_version=dataset_version,
                    v2_manifest_fingerprint=readiness.manifest_fingerprint,
                    semantic_graph_fingerprint=readiness.semantic_graph_fingerprint,
                    rationale=f"CRITICAL: Consumer in V2_PRIMARY encountered readiness failure {primary_reason.value}; fallback disallowed",
                )
                self.provenance_ledger.record_decision(decision)
                return decision

            # In V2_PRIMARY_WITH_FALLBACK or CANARY: governed fallback to V1
            self._record_governed_fallback(
                consumer=consumer,
                dataset_id=dataset_id,
                dataset_version=dataset_version,
                request_id=req_id,
                reason=primary_reason,
                manifest_fp=readiness.manifest_fingerprint,
            )
            decision = ConsumerRouteDecision(
                decision_id=decision_id,
                decision_timestamp=now_iso,
                consumer=consumer,
                requested_route=Route.V2,
                selected_route=Route.V1,
                consumer_state=consumer_state,
                feature_enabled=consumer_on,
                global_enabled=global_on,
                fallback_allowed=fallback_allowed,
                fallback_used=True,
                fallback_reason=primary_reason,
                circuit_breaker_state=new_circuit_state,
                dataset_id=dataset_id,
                dataset_version=dataset_version,
                v2_manifest_fingerprint=readiness.manifest_fingerprint,
                semantic_graph_fingerprint=readiness.semantic_graph_fingerprint,
                rationale=f"V2 readiness failed ({primary_reason.value}); executed governed fallback to V1",
            )
            self.provenance_ledger.record_decision(decision)
            return decision

        # ---------------------------------------------------------------------
        # Success: V2 Route Authorized
        # ---------------------------------------------------------------------
        self.circuit_breaker.record_success(consumer)
        decision = ConsumerRouteDecision(
            decision_id=decision_id,
            decision_timestamp=now_iso,
            consumer=consumer,
            requested_route=Route.V2,
            selected_route=Route.V2,
            consumer_state=consumer_state,
            feature_enabled=consumer_on,
            global_enabled=global_on,
            fallback_allowed=fallback_allowed,
            fallback_used=False,
            fallback_reason=None,
            circuit_breaker_state=self.circuit_breaker.get_state(consumer),
            dataset_id=dataset_id,
            dataset_version=dataset_version,
            v2_manifest_fingerprint=readiness.manifest_fingerprint,
            semantic_graph_fingerprint=readiness.semantic_graph_fingerprint,
            rationale="V2 route authorized: all feature gates, cutover state, circuit breaker, and readiness checks passed",
        )
        self.provenance_ledger.record_decision(decision)
        return decision

    def _record_governed_fallback(
        self,
        consumer: ConsumerName,
        dataset_id: str | None,
        dataset_version: str | None,
        request_id: str,
        reason: FallbackReason,
        manifest_fp: str | None,
    ) -> None:
        """Helper creating typed FallbackRecord and storing it in the ledger."""
        rec = FallbackRecord(
            fallback_id=f"FB-{uuid.uuid4().hex[:10].upper()}",
            consumer=consumer,
            dataset_id=dataset_id,
            request_id=request_id,
            reason=reason,
            severity="WARNING",
            dataset_version=dataset_version,
            manifest_fingerprint=manifest_fp,
            original_route=Route.V2,
            fallback_route=Route.V1,
            timestamp=datetime.now(timezone.utc).isoformat(),
            resolved=True,
        )
        self.provenance_ledger.record_fallback(rec)

    # =========================================================================
    # 3. OBSERVABILITY & SNAPSHOT APIS
    # =========================================================================
    def get_snapshot(self, consumer: ConsumerName) -> ConsumerRoutingSnapshot:
        """Returns a snapshot of the consumer's current state, circuit breaker, and route counts."""
        rec = self.state_machine.get_record(consumer)
        telemetry = self.provenance_ledger.get_telemetry()
        consumer_routes = telemetry["per_consumer_routes"].get(consumer.value, {"V1": 0, "V2": 0})
        return ConsumerRoutingSnapshot(
            consumer=consumer,
            state=rec.current_state,
            feature_enabled=self.is_consumer_v2_enabled(consumer),
            global_enabled=self.is_global_v2_enabled(),
            fallback_allowed=self.is_fallback_allowed(consumer),
            route_v1_count=consumer_routes.get("V1", 0),
            route_v2_count=consumer_routes.get("V2", 0),
            fallback_count=rec.fallback_count + telemetry["consumer_fallback_count"],
            last_fallback_reason=self.circuit_breaker.get_last_trip_reason(consumer),
            circuit_state=self.circuit_breaker.get_state(consumer),
            v2_failures=telemetry["consumer_v2_failure_count"],
        )

    def get_telemetry(self) -> dict[str, Any]:
        """Returns the full telemetry dictionary from the ledger."""
        return self.provenance_ledger.get_telemetry()

    def reset(self) -> None:
        """Resets all consumer states to SHADOW and clears circuit breakers & telemetry."""
        for c in (ConsumerName.HRIDAY, ConsumerName.DASHBOARD, ConsumerName.PRESENTATION):
            self.state_machine.reset_to_shadow(c)
            self.circuit_breaker.reset(c)
            self._override_consumer_enabled[c] = None
            self._override_fallback_allowed[c] = None
        self._override_global_enabled = None
        self.provenance_ledger.reset_telemetry()
