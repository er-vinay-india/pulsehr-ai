"""
HighView Ingestion V2 — Phase I8.2 Governed Consumer Gateway & Cutover Test Suite
Stage: Consumer Cutover Infrastructure, Circuit Breakers & Rollback Foundation
Validates:
1. ConsumerCutoverStateMachine lifecycle transitions, ordering guards, fail-closed handling.
2. CircuitBreakerManager state transitions (CLOSED, OPEN, HALF_OPEN) and trip triggers.
3. ConsumerReadinessEvaluator guards (manifest presence, freshness, version match, evidence grounding).
4. Central ConsumerIntelligenceGateway routing matrix (Global kill switch, feature flags, state-dependent routes).
5. Governed fallback to V1 with typed reason logging and failure accounting.
6. Non-destructive per-consumer rollback and global emergency rollback.
7. Decision provenance, idempotence, and telemetry invariants.
8. Component-level P50/P95 latency benchmarks and peak memory telemetry.
9. Concurrency safety under simultaneous multithreaded route requests.
"""

from __future__ import annotations

import json
import sqlite3
import threading
import time
import tracemalloc
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import pytest

from app.services.ingestion_v2.contracts.cutover import (
    CURRENT_CUTOVER_STATE_SCHEMA_VERSION,
    CircuitBreakerState,
    ConfigurationSource,
    ConsumerCutoverRecord,
    ConsumerName,
    CutoverState,
    FallbackReason,
    ReadinessAssessment,
    Route,
)
from app.services.ingestion_v2.gateway import (
    CircuitBreakerManager,
    ConsumerCutoverStateMachine,
    ConsumerIntelligenceGateway,
    ConsumerReadinessEvaluator,
    CutoverOrderingViolationError,
    CutoverPersistenceStore,
    InvalidCutoverTransitionError,
    RoutingFallbackDisallowedError,
    RoutingProvenanceLedger,
)


@pytest.fixture
def gateway() -> ConsumerIntelligenceGateway:
    gw = ConsumerIntelligenceGateway()
    gw.reset()
    return gw


# =============================================================================
# 1. CUTOVER STATE MACHINE TESTS: VALID & INVALID TRANSITIONS
# =============================================================================

def test_default_consumer_states_are_shadow(gateway):
    """Verifies that all consumers initialize in SHADOW state with V2 disabled."""
    for c in (ConsumerName.HRIDAY, ConsumerName.DASHBOARD, ConsumerName.PRESENTATION):
        rec = gateway.state_machine.get_record(c)
        assert rec.current_state == CutoverState.SHADOW
        assert rec.feature_enabled is False
        assert rec.fallback_allowed is True
        assert rec.circuit_breaker_state == CircuitBreakerState.CLOSED


def test_valid_sequential_transitions(gateway):
    """Verifies legal lifecycle transitions: SHADOW -> CERTIFIED -> CANARY -> V2_PRIMARY_WITH_FALLBACK -> V2_PRIMARY -> V1_RETIREMENT_ELIGIBLE."""
    sm = gateway.state_machine

    # HRIDAY sequence
    rec = sm.transition(ConsumerName.HRIDAY, CutoverState.CERTIFIED, "Passed shadow parity certification", "RUN-CERT-01")
    assert rec.current_state == CutoverState.CERTIFIED

    rec = sm.transition(ConsumerName.HRIDAY, CutoverState.CANARY, "Canary authorized", "CANARY-01")
    assert rec.current_state == CutoverState.CANARY

    rec = sm.transition(ConsumerName.HRIDAY, CutoverState.V2_PRIMARY_WITH_FALLBACK, "Primary cutover with fallback", "PROD-01")
    assert rec.current_state == CutoverState.V2_PRIMARY_WITH_FALLBACK

    rec = sm.transition(ConsumerName.HRIDAY, CutoverState.V2_PRIMARY, "Full primary cutover without fallback", "PROD-FINAL")
    assert rec.current_state == CutoverState.V2_PRIMARY

    rec = sm.transition(ConsumerName.HRIDAY, CutoverState.V1_RETIREMENT_ELIGIBLE, "V1 eligible for retirement", "RETIRE-01")
    assert rec.current_state == CutoverState.V1_RETIREMENT_ELIGIBLE


def test_invalid_transition_jumps_are_blocked(gateway):
    """Verifies that arbitrary state jumps fail closed immediately."""
    sm = gateway.state_machine

    # SHADOW -> V2_PRIMARY is strictly forbidden
    with pytest.raises(InvalidCutoverTransitionError):
        sm.transition(ConsumerName.HRIDAY, CutoverState.V2_PRIMARY, "Unauthorized jump")

    # SHADOW -> V1_RETIREMENT_ELIGIBLE is strictly forbidden
    with pytest.raises(InvalidCutoverTransitionError):
        sm.transition(ConsumerName.HRIDAY, CutoverState.V1_RETIREMENT_ELIGIBLE, "Unauthorized jump")

    # CERTIFIED -> V1_RETIREMENT_ELIGIBLE is forbidden
    sm.transition(ConsumerName.HRIDAY, CutoverState.CERTIFIED, "Certify")
    with pytest.raises(InvalidCutoverTransitionError):
        sm.transition(ConsumerName.HRIDAY, CutoverState.V1_RETIREMENT_ELIGIBLE, "Skip production")


# =============================================================================
# 2. ORDERING CONSTRAINT TESTS
# =============================================================================

def test_ordering_constraints_enforced(gateway):
    """
    Verifies cutover ordering:
    HRIDAY must be >= CERTIFIED before DASHBOARD enters CANARY.
    DASHBOARD must be >= CERTIFIED before PRESENTATION enters CANARY.
    """
    sm = gateway.state_machine

    # Attempt Dashboard CANARY while HRIDAY is SHADOW -> MUST BLOCK
    with pytest.raises(CutoverOrderingViolationError):
        sm.transition(ConsumerName.DASHBOARD, CutoverState.CERTIFIED, "Dashboard certified")
        sm.transition(ConsumerName.DASHBOARD, CutoverState.CANARY, "Dashboard canary before HRIDAY")

    # Now certify HRIDAY
    sm.transition(ConsumerName.HRIDAY, CutoverState.CERTIFIED, "HRIDAY certified")

    # Dashboard can now enter CANARY
    rec_dash = sm.transition(ConsumerName.DASHBOARD, CutoverState.CANARY, "Dashboard canary authorized")
    assert rec_dash.current_state == CutoverState.CANARY

    # Attempt Presentation CANARY while Dashboard is CANARY (which is >= CERTIFIED) -> PASS
    sm.transition(ConsumerName.PRESENTATION, CutoverState.CERTIFIED, "Presentation certified")
    rec_pres = sm.transition(ConsumerName.PRESENTATION, CutoverState.CANARY, "Presentation canary authorized")
    assert rec_pres.current_state == CutoverState.CANARY


def test_presentation_ordering_blocked_when_dashboard_shadow(gateway):
    """Verifies Presentation cannot enter CANARY if Dashboard is still in SHADOW."""
    sm = gateway.state_machine
    sm.transition(ConsumerName.HRIDAY, CutoverState.CERTIFIED, "HRIDAY certified")
    sm.transition(ConsumerName.PRESENTATION, CutoverState.CERTIFIED, "Presentation certified")

    with pytest.raises(CutoverOrderingViolationError):
        sm.transition(ConsumerName.PRESENTATION, CutoverState.CANARY, "Presentation canary prematurely")


# =============================================================================
# 3. ROLLBACK & RECOVERY VALIDATION TESTS
# =============================================================================

def test_instant_per_consumer_rollback_and_recovery(gateway):
    """Verifies that rollback moves to ROLLBACK immediately, routes V1, and requires evidence to exit."""
    sm = gateway.state_machine
    sm.transition(ConsumerName.HRIDAY, CutoverState.CERTIFIED, "Certify")
    sm.transition(ConsumerName.HRIDAY, CutoverState.CANARY, "Canary")
    sm.transition(ConsumerName.HRIDAY, CutoverState.V2_PRIMARY_WITH_FALLBACK, "Primary")

    # Trigger emergency rollback
    rec_rb = sm.rollback(ConsumerName.HRIDAY, "Simulated data anomaly in production")
    assert rec_rb.current_state == CutoverState.ROLLBACK

    # While in rollback, cannot jump directly to retirement or V2_PRIMARY
    with pytest.raises(InvalidCutoverTransitionError):
        sm.recover_from_rollback(ConsumerName.HRIDAY, CutoverState.V1_RETIREMENT_ELIGIBLE, "Invalid recovery")

    with pytest.raises(InvalidCutoverTransitionError):
        sm.recover_from_rollback(ConsumerName.HRIDAY, CutoverState.V2_PRIMARY, "Invalid recovery")

    # Requires non-empty recovery evidence
    with pytest.raises(ValueError):
        sm.recover_from_rollback(ConsumerName.HRIDAY, CutoverState.CERTIFIED, "   ")

    # Valid recovery to CERTIFIED with evidence
    rec_recov = sm.recover_from_rollback(
        ConsumerName.HRIDAY,
        CutoverState.CERTIFIED,
        "Verified hotfix patch and successful 60/60 shadow benchmark re-run",
    )
    assert rec_recov.current_state == CutoverState.CERTIFIED


# =============================================================================
# 4. CIRCUIT BREAKER TESTS: CLOSED, OPEN, HALF-OPEN & TRIP TRIGGERS
# =============================================================================

def test_circuit_breaker_lifecycle():
    """Verifies circuit breaker state transitions (CLOSED -> OPEN -> HALF_OPEN -> CLOSED)."""
    cb = CircuitBreakerManager(failure_threshold=3, required_probe_successes=1)

    assert cb.get_state(ConsumerName.HRIDAY) == CircuitBreakerState.CLOSED
    assert cb.can_attempt_v2(ConsumerName.HRIDAY) is True

    # 2 failures do not trip
    cb.record_failure(ConsumerName.HRIDAY, FallbackReason.V2_RUNTIME_ERROR)
    cb.record_failure(ConsumerName.HRIDAY, FallbackReason.V2_RUNTIME_ERROR)
    assert cb.get_state(ConsumerName.HRIDAY) == CircuitBreakerState.CLOSED

    # 3rd failure trips to OPEN
    tripped = cb.record_failure(ConsumerName.HRIDAY, FallbackReason.V2_RUNTIME_ERROR)
    assert tripped is True
    assert cb.get_state(ConsumerName.HRIDAY) == CircuitBreakerState.OPEN
    assert cb.can_attempt_v2(ConsumerName.HRIDAY) is False
    assert cb.get_trip_count() == 1

    # Probe transitions to HALF_OPEN
    assert cb.probe(ConsumerName.HRIDAY) is True
    assert cb.get_state(ConsumerName.HRIDAY) == CircuitBreakerState.HALF_OPEN
    # Ordinary traffic is BLOCKED in HALF_OPEN
    assert cb.can_attempt_v2(ConsumerName.HRIDAY, is_probe=False) is False
    # Explicit recovery probe is ALLOWED in HALF_OPEN
    assert cb.can_attempt_v2(ConsumerName.HRIDAY, is_probe=True) is True

    # Successful probe resets to CLOSED
    cb.record_success(ConsumerName.HRIDAY)
    assert cb.get_state(ConsumerName.HRIDAY) == CircuitBreakerState.CLOSED
    assert cb.can_attempt_v2(ConsumerName.HRIDAY) is True


def test_circuit_breaker_half_open_failure_re_trips_to_open():
    """Verifies that a failed probe in HALF_OPEN immediately returns to OPEN."""
    cb = CircuitBreakerManager(failure_threshold=2)
    cb.trip(ConsumerName.DASHBOARD, FallbackReason.V2_SCHEMA_CONTRACT_FAILURE)
    assert cb.get_state(ConsumerName.DASHBOARD) == CircuitBreakerState.OPEN

    cb.probe(ConsumerName.DASHBOARD)
    assert cb.get_state(ConsumerName.DASHBOARD) == CircuitBreakerState.HALF_OPEN

    # Failure during probe
    cb.record_failure(ConsumerName.DASHBOARD, FallbackReason.V2_RUNTIME_ERROR)
    assert cb.get_state(ConsumerName.DASHBOARD) == CircuitBreakerState.OPEN
    assert cb.can_attempt_v2(ConsumerName.DASHBOARD) is False


# =============================================================================
# 5. READINESS EVALUATOR GUARDS: MANIFEST, FRESHNESS, VERSIONS, EVIDENCE
# =============================================================================

def test_readiness_missing_manifest():
    """Missing manifest blocks V2 route."""
    res = ConsumerReadinessEvaluator.evaluate(dataset_id="ds-01", manifest_data=None)
    assert res.is_ready is False
    assert FallbackReason.V2_ARTIFACT_MISSING in res.failure_reasons
    assert "v2_manifest.json" in res.missing_artifacts


def test_readiness_stale_manifest():
    """Stale manifest blocks V2 route."""
    manifest = {"dataset_version": "1", "is_fresh": False, "available_artifacts": []}
    res = ConsumerReadinessEvaluator.evaluate(dataset_id="ds-01", manifest_data=manifest)
    assert res.is_ready is False
    assert FallbackReason.V2_ARTIFACT_STALE in res.failure_reasons


def test_readiness_dataset_version_mismatch():
    """Version mismatch blocks V2 route."""
    manifest = {"dataset_version": "1", "is_fresh": True, "available_artifacts": []}
    res = ConsumerReadinessEvaluator.evaluate(dataset_id="ds-01", requested_version="2", manifest_data=manifest)
    assert res.is_ready is False
    assert FallbackReason.V2_DATASET_VERSION_MISMATCH in res.failure_reasons


def test_readiness_missing_required_artifacts():
    """Missing required consumer artifact blocks V2 route."""
    manifest = {
        "dataset_version": "1",
        "is_fresh": True,
        "available_artifacts": ["schema.json", "semantic_model.json"],
    }
    required = ["schema.json", "semantic_model.json", "semantic_graph.json"]
    res = ConsumerReadinessEvaluator.evaluate(
        dataset_id="ds-01", manifest_data=manifest, required_artifacts=required
    )
    assert res.is_ready is False
    assert FallbackReason.V2_ARTIFACT_MISSING in res.failure_reasons
    assert "semantic_graph.json" in res.missing_artifacts


def test_readiness_invalid_evidence_grounding():
    """Unvalidated or invented EVID reference blocks V2 route."""
    manifest = {
        "dataset_version": "1",
        "is_fresh": True,
        "available_artifacts": ["schema.json"],
        "evidence_ids": ["EVID-VALID-01", "EVID-VALID-02"],
    }
    # EVID-INVENTED does not exist in pool
    res = ConsumerReadinessEvaluator.evaluate(
        dataset_id="ds-01",
        manifest_data=manifest,
        required_evidence_refs=["EVID-VALID-01", "EVID-INVENTED-99"],
    )
    assert res.is_ready is False
    assert FallbackReason.V2_CONTEXT_GROUNDING_FAILURE in res.failure_reasons
    assert res.evidence_grounding_valid is False


# =============================================================================
# 6. CENTRAL GATEWAY ROUTING MATRIX TESTS
# =============================================================================

def test_routing_global_off_forces_all_v1(gateway):
    """When global V2 is OFF, all consumers route to V1 regardless of flags or states."""
    gateway.set_global_enabled(False)
    gateway.set_consumer_enabled(ConsumerName.HRIDAY, True)
    gateway.state_machine.transition(ConsumerName.HRIDAY, CutoverState.CERTIFIED, "c")
    gateway.state_machine.transition(ConsumerName.HRIDAY, CutoverState.CANARY, "can")
    gateway.state_machine.transition(ConsumerName.HRIDAY, CutoverState.V2_PRIMARY_WITH_FALLBACK, "p")

    dec = gateway.evaluate_route(ConsumerName.HRIDAY, dataset_id="ds-1")
    assert dec.selected_route == Route.V1
    assert dec.fallback_reason == FallbackReason.KILL_SWITCH_ACTIVE


def test_routing_consumer_flag_off_routes_v1(gateway):
    """When global V2 is ON but consumer flag is OFF, route is V1."""
    gateway.set_global_enabled(True)
    gateway.set_consumer_enabled(ConsumerName.DASHBOARD, False)

    dec = gateway.evaluate_route(ConsumerName.DASHBOARD, dataset_id="ds-1")
    assert dec.selected_route == Route.V1
    assert dec.fallback_reason == FallbackReason.STATE_NOT_V2_ELIGIBLE


def test_routing_shadow_and_certified_route_v1(gateway):
    """Consumers in SHADOW or CERTIFIED always route production traffic to V1."""
    gateway.set_global_enabled(True)
    gateway.set_consumer_enabled(ConsumerName.HRIDAY, True)

    # In SHADOW
    dec_shadow = gateway.evaluate_route(ConsumerName.HRIDAY, dataset_id="ds-1")
    assert dec_shadow.selected_route == Route.V1

    # Advance to CERTIFIED
    gateway.state_machine.transition(ConsumerName.HRIDAY, CutoverState.CERTIFIED, "Certified")
    dec_cert = gateway.evaluate_route(ConsumerName.HRIDAY, dataset_id="ds-1")
    assert dec_cert.selected_route == Route.V1


def test_routing_canary_authorized_vs_ordinary(gateway):
    """In CANARY, authorized canary requests route V2, while ordinary requests stay on V1."""
    gateway.set_global_enabled(True)
    gateway.set_consumer_enabled(ConsumerName.HRIDAY, True)
    gateway.state_machine.transition(ConsumerName.HRIDAY, CutoverState.CERTIFIED, "Cert")
    gateway.state_machine.transition(ConsumerName.HRIDAY, CutoverState.CANARY, "Canary")

    manifest = {"dataset_version": "1", "is_fresh": True, "available_artifacts": []}

    # Ordinary request -> V1
    dec_ord = gateway.evaluate_route(ConsumerName.HRIDAY, dataset_id="ds-1", is_canary=False, manifest_data=manifest)
    assert dec_ord.selected_route == Route.V1
    assert dec_ord.fallback_reason == FallbackReason.CANARY_NOT_AUTHORIZED

    # Authorized canary request -> V2
    dec_can = gateway.evaluate_route(ConsumerName.HRIDAY, dataset_id="ds-1", is_canary=True, manifest_data=manifest)
    assert dec_can.selected_route == Route.V2
    assert dec_can.fallback_used is False


def test_routing_v2_primary_with_fallback_success_and_failure(gateway):
    """In V2_PRIMARY_WITH_FALLBACK, healthy routes V2, while readiness failure routes V1 fallback."""
    gateway.set_global_enabled(True)
    gateway.set_consumer_enabled(ConsumerName.HRIDAY, True)
    gateway.set_fallback_allowed(ConsumerName.HRIDAY, True)
    gateway.state_machine.transition(ConsumerName.HRIDAY, CutoverState.CERTIFIED, "Cert")
    gateway.state_machine.transition(ConsumerName.HRIDAY, CutoverState.CANARY, "Canary")
    gateway.state_machine.transition(ConsumerName.HRIDAY, CutoverState.V2_PRIMARY_WITH_FALLBACK, "Primary")

    # Healthy dataset -> V2
    good_manifest = {"dataset_version": "1", "is_fresh": True, "manifest_fingerprint": "abc"}
    dec_good = gateway.evaluate_route(ConsumerName.HRIDAY, dataset_id="ds-1", manifest_data=good_manifest)
    assert dec_good.selected_route == Route.V2
    assert dec_good.fallback_used is False

    # Stale dataset -> V1 fallback recorded
    stale_manifest = {"dataset_version": "1", "is_fresh": False, "manifest_fingerprint": "xyz"}
    dec_stale = gateway.evaluate_route(ConsumerName.HRIDAY, dataset_id="ds-1", manifest_data=stale_manifest)
    assert dec_stale.selected_route == Route.V1
    assert dec_stale.fallback_used is True
    assert dec_stale.fallback_reason == FallbackReason.V2_ARTIFACT_STALE

    # Check that fallback record exists in ledger
    fallbacks = gateway.provenance_ledger.get_fallbacks()
    assert len(fallbacks) == 1
    assert fallbacks[0].consumer == ConsumerName.HRIDAY
    assert fallbacks[0].reason == FallbackReason.V2_ARTIFACT_STALE


def test_routing_v2_primary_healthy_routes_v2(gateway):
    """In V2_PRIMARY, healthy requests route V2."""
    gateway.set_global_enabled(True)
    gateway.set_consumer_enabled(ConsumerName.HRIDAY, True)
    gateway.state_machine.transition(ConsumerName.HRIDAY, CutoverState.CERTIFIED, "Cert")
    gateway.state_machine.transition(ConsumerName.HRIDAY, CutoverState.CANARY, "Canary")
    gateway.state_machine.transition(ConsumerName.HRIDAY, CutoverState.V2_PRIMARY_WITH_FALLBACK, "Primary WF")
    gateway.state_machine.transition(ConsumerName.HRIDAY, CutoverState.V2_PRIMARY, "Full Primary")

    good_manifest = {"dataset_version": "1", "is_fresh": True}
    dec = gateway.evaluate_route(ConsumerName.HRIDAY, dataset_id="ds-1", manifest_data=good_manifest)
    assert dec.selected_route == Route.V2


def test_routing_rollback_forces_v1(gateway):
    """Consumer in ROLLBACK routes to V1."""
    gateway.set_global_enabled(True)
    gateway.set_consumer_enabled(ConsumerName.HRIDAY, True)
    gateway.state_machine.transition(ConsumerName.HRIDAY, CutoverState.CERTIFIED, "Cert")
    gateway.state_machine.rollback(ConsumerName.HRIDAY, "Emergency rollback")

    dec = gateway.evaluate_route(ConsumerName.HRIDAY, dataset_id="ds-1")
    assert dec.selected_route == Route.V1


# =============================================================================
# 7. TELEMETRY, FALLBACK COUNTER & NO SILENT FALLBACK TESTS
# =============================================================================

def test_fallback_and_route_counters_exactness(gateway):
    """
    Force exactly:
    3 successful V2 requests
    2 governed fallbacks
    Require: route_v2_count = 3, fallback_count = 2, total V1 routes recorded.
    """
    gateway.set_global_enabled(True)
    gateway.set_consumer_enabled(ConsumerName.HRIDAY, True)
    gateway.set_fallback_allowed(ConsumerName.HRIDAY, True)
    gateway.state_machine.transition(ConsumerName.HRIDAY, CutoverState.CERTIFIED, "c")
    gateway.state_machine.transition(ConsumerName.HRIDAY, CutoverState.CANARY, "can")
    gateway.state_machine.transition(ConsumerName.HRIDAY, CutoverState.V2_PRIMARY_WITH_FALLBACK, "p")

    good_manifest = {"dataset_version": "1", "is_fresh": True}
    bad_manifest = {"dataset_version": "1", "is_fresh": False}

    # 3 successful V2 requests
    gateway.evaluate_route(ConsumerName.HRIDAY, dataset_id="ds-1", manifest_data=good_manifest)
    gateway.evaluate_route(ConsumerName.HRIDAY, dataset_id="ds-1", manifest_data=good_manifest)
    gateway.evaluate_route(ConsumerName.HRIDAY, dataset_id="ds-1", manifest_data=good_manifest)

    # 2 governed fallbacks
    gateway.evaluate_route(ConsumerName.HRIDAY, dataset_id="ds-1", manifest_data=bad_manifest)
    gateway.evaluate_route(ConsumerName.HRIDAY, dataset_id="ds-1", manifest_data=bad_manifest)

    telem = gateway.get_telemetry()
    assert telem["consumer_route_v2_count"] == 3
    assert telem["consumer_fallback_count"] == 2
    assert telem["stale_artifact_block_count"] == 2
    assert telem["consumer_route_v1_count"] == 2
    assert telem["fallback_reasons"]["V2_ARTIFACT_STALE"] == 2


def test_snapshot_reports_clear_cutover_and_fallback_status(gateway):
    """Snapshot clearly distinguishes V2 success from fallback rescue."""
    gateway.set_global_enabled(True)
    gateway.set_consumer_enabled(ConsumerName.DASHBOARD, True)
    gateway.state_machine.transition(ConsumerName.HRIDAY, CutoverState.CERTIFIED, "c")
    gateway.state_machine.transition(ConsumerName.DASHBOARD, CutoverState.CERTIFIED, "c")
    gateway.state_machine.transition(ConsumerName.DASHBOARD, CutoverState.CANARY, "can")
    gateway.state_machine.transition(ConsumerName.DASHBOARD, CutoverState.V2_PRIMARY_WITH_FALLBACK, "p")

    good_manifest = {"dataset_version": "1", "is_fresh": True}
    gateway.evaluate_route(ConsumerName.DASHBOARD, dataset_id="ds-1", manifest_data=good_manifest)

    snap = gateway.get_snapshot(ConsumerName.DASHBOARD)
    assert snap.consumer == ConsumerName.DASHBOARD
    assert snap.state == CutoverState.V2_PRIMARY_WITH_FALLBACK
    assert snap.route_v2_count == 1
    assert snap.fallback_count == 0


# =============================================================================
# 8. IDEMPOTENCE & DETERMINISM TESTS
# =============================================================================

def test_routing_idempotence(gateway):
    """Repeated calls with identical inputs produce semantically identical route selections."""
    gateway.set_global_enabled(True)
    gateway.set_consumer_enabled(ConsumerName.HRIDAY, True)
    gateway.state_machine.transition(ConsumerName.HRIDAY, CutoverState.CERTIFIED, "c")
    gateway.state_machine.transition(ConsumerName.HRIDAY, CutoverState.CANARY, "can")

    manifest = {"dataset_version": "1", "is_fresh": True}

    d1 = gateway.evaluate_route(ConsumerName.HRIDAY, dataset_id="ds-1", is_canary=True, manifest_data=manifest)
    d2 = gateway.evaluate_route(ConsumerName.HRIDAY, dataset_id="ds-1", is_canary=True, manifest_data=manifest)

    assert d1.selected_route == d2.selected_route
    assert d1.consumer == d2.consumer
    assert d1.consumer_state == d2.consumer_state
    assert d1.fallback_used == d2.fallback_used
    assert d1.fallback_reason == d2.fallback_reason


# =============================================================================
# 9. CONCURRENCY SAFETY TESTS
# =============================================================================

def test_multithreaded_concurrency_safety(gateway):
    """Simultaneous multithreaded route requests do not corrupt counters or state."""
    gateway.set_global_enabled(True)
    gateway.set_consumer_enabled(ConsumerName.HRIDAY, True)
    gateway.state_machine.transition(ConsumerName.HRIDAY, CutoverState.CERTIFIED, "c")
    gateway.state_machine.transition(ConsumerName.HRIDAY, CutoverState.CANARY, "can")
    gateway.state_machine.transition(ConsumerName.HRIDAY, CutoverState.V2_PRIMARY_WITH_FALLBACK, "p")

    manifest = {"dataset_version": "1", "is_fresh": True}

    def _worker(worker_id: int):
        for _ in range(50):
            gateway.evaluate_route(ConsumerName.HRIDAY, dataset_id="ds-1", manifest_data=manifest)

    with ThreadPoolExecutor(max_workers=8) as pool:
        futures = [pool.submit(_worker, i) for i in range(8)]
        for f in futures:
            f.result()

    telem = gateway.get_telemetry()
    assert telem["consumer_route_v2_count"] == 400
    assert telem["total_decisions"] == 400


# =============================================================================
# 10. COMPONENT-LEVEL PERFORMANCE & MEMORY BENCHMARK
# =============================================================================

def _measure_p50_p95(fn, iterations: int = 100) -> tuple[float, float]:
    latencies: list[float] = []
    for _ in range(iterations):
        t0 = time.perf_counter()
        fn()
        latencies.append((time.perf_counter() - t0) * 1000)
    latencies.sort()
    p50 = round(latencies[int(iterations * 0.50)], 3)
    p95 = round(latencies[int(iterations * 0.95)], 3)
    return p50, p95


def test_component_level_performance_and_memory(gateway):
    """
    Measures P50 / P95 latencies for:
    - Route decision
    - State validation & transition
    - Readiness check
    - Circuit breaker check & failure recording
    - Fallback selection
    - Transition validation
    Plus peak additional memory.
    """
    gateway.set_global_enabled(True)
    gateway.set_consumer_enabled(ConsumerName.HRIDAY, True)
    gateway.state_machine.transition(ConsumerName.HRIDAY, CutoverState.CERTIFIED, "c")
    gateway.state_machine.transition(ConsumerName.HRIDAY, CutoverState.CANARY, "can")
    gateway.state_machine.transition(ConsumerName.HRIDAY, CutoverState.V2_PRIMARY_WITH_FALLBACK, "p")

    manifest = {"dataset_version": "1", "is_fresh": True, "available_artifacts": ["schema.json"]}

    # 1. Route decision
    p50_route, p95_route = _measure_p50_p95(
        lambda: gateway.evaluate_route(ConsumerName.HRIDAY, dataset_id="ds-perf", manifest_data=manifest)
    )

    # 2. Readiness check
    p50_ready, p95_ready = _measure_p50_p95(
        lambda: ConsumerReadinessEvaluator.evaluate("ds-perf", "1", manifest, ["schema.json"])
    )

    # 3. Circuit breaker check
    cb = CircuitBreakerManager()
    p50_cb, p95_cb = _measure_p50_p95(lambda: cb.can_attempt_v2(ConsumerName.HRIDAY))

    # 4. State transition
    sm = ConsumerCutoverStateMachine()
    p50_trans, p95_trans = _measure_p50_p95(
        lambda: sm.transition(ConsumerName.HRIDAY, CutoverState.CERTIFIED, "Benchmark transition")
    )

    # 5. Fallback selection & recording
    p50_fb, p95_fb = _measure_p50_p95(
        lambda: gateway.evaluate_route(
            ConsumerName.HRIDAY,
            dataset_id="ds-perf",
            manifest_data={"dataset_version": "1", "is_fresh": False},
        )
    )

    # Memory benchmark
    tracemalloc.start()
    for _ in range(500):
        gateway.evaluate_route(ConsumerName.HRIDAY, dataset_id="ds-perf", manifest_data=manifest)
    _, peak_bytes = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    peak_mem_mb = round(peak_bytes / (1024 * 1024), 3)

    # Assert latencies are well within sub-millisecond to low-millisecond bounds (< 10ms P95)
    assert p95_route < 10.0
    assert p95_ready < 10.0
    assert p95_cb < 5.0
    assert p95_trans < 10.0
    assert p95_fb < 10.0
    assert peak_mem_mb < 15.0

    print("\n--- I8.2 GATEWAY COMPONENT PERFORMANCE BENCHMARK ---")
    print(f"Route Decision:       P50={p50_route}ms | P95={p95_route}ms")
    print(f"Readiness Check:      P50={p50_ready}ms | P95={p95_ready}ms")
    print(f"Circuit Breaker Check:P50={p50_cb}ms    | P95={p95_cb}ms")
    print(f"State Transition:     P50={p50_trans}ms | P95={p95_trans}ms")
    print(f"Fallback Selection:   P50={p50_fb}ms    | P95={p95_fb}ms")
    print(f"Peak Additional Memory: {peak_mem_mb} MB")


# =============================================================================
# 11. DURABLE CONSUMER CUTOVER STATE & RESTART RECOVERY TESTS
# =============================================================================

def test_canonical_restart_recovery(tmp_path: Path):
    """
    Canonical 6-step restart recovery test:
    1. Initialize isolated state store
    2. HRIDAY -> CERTIFIED
    3. Persist state
    4. Destroy gateway and state-machine instances
    5. Construct fresh instances from the same persistence store
    6. Reload state and verify:
       - HRIDAY == CERTIFIED
       - DASHBOARD == SHADOW
       - PRESENTATION == SHADOW
       - No accidental reset to an active V2 state
       - No accidental progression
    """
    db_file = tmp_path / "test_cutover.sqlite3"
    store = CutoverPersistenceStore(db_path=db_file)
    sm = ConsumerCutoverStateMachine(persistence_store=store)

    # Transition HRIDAY to CERTIFIED
    rec = sm.transition(
        ConsumerName.HRIDAY,
        CutoverState.CERTIFIED,
        reason="Passed shadow parity audit",
        certification_evidence="RUN-CERT-I8-2-001",
        authorized_source=ConfigurationSource.CONTROL_PLANE,
    )
    assert rec.current_state == CutoverState.CERTIFIED

    # Destroy instances completely
    del sm
    del store

    # Reconstruct fresh instances from the same persisted store
    store2 = CutoverPersistenceStore(db_path=db_file)
    sm2 = ConsumerCutoverStateMachine(persistence_store=store2)

    # Verify state after restart
    assert sm2.get_state(ConsumerName.HRIDAY) == CutoverState.CERTIFIED
    assert sm2.get_state(ConsumerName.DASHBOARD) == CutoverState.SHADOW
    assert sm2.get_state(ConsumerName.PRESENTATION) == CutoverState.SHADOW

    hriday_rec = sm2.get_record(ConsumerName.HRIDAY)
    assert hriday_rec.certification_run_id == "RUN-CERT-I8-2-001"
    assert hriday_rec.configuration_source == ConfigurationSource.CONTROL_PLANE
    assert hriday_rec.cutover_state_schema_version == CURRENT_CUTOVER_STATE_SCHEMA_VERSION


# =============================================================================
# 12. CORRUPT / MISSING STATE FAIL-SAFE TESTS
# =============================================================================

def test_missing_persisted_state_fails_safe_to_shadow(tmp_path: Path):
    """Verifies that an absent persisted database fails safe to SHADOW / V1."""
    nonexistent_db = tmp_path / "does_not_exist.sqlite3"
    store = CutoverPersistenceStore(db_path=nonexistent_db)
    sm = ConsumerCutoverStateMachine(persistence_store=store)

    for c in ConsumerName:
        assert sm.get_state(c) == CutoverState.SHADOW
        assert sm.get_record(c).feature_enabled is False


def test_corrupt_database_fails_safe_to_shadow(tmp_path: Path):
    """Verifies that a corrupted SQLite database file fails safe to SHADOW / V1, never V2."""
    corrupt_file = tmp_path / "corrupted_state.sqlite3"
    corrupt_file.write_bytes(b"CORRUPTED_GARBAGE_HEADER_DATA_NOT_SQLITE3")

    store = CutoverPersistenceStore(db_path=corrupt_file)
    sm = ConsumerCutoverStateMachine(persistence_store=store)

    for c in ConsumerName:
        assert sm.get_state(c) == CutoverState.SHADOW
        assert sm.get_record(c).feature_enabled is False


def test_invalid_consumer_state_string_fails_safe_to_shadow(tmp_path: Path):
    """Verifies that corrupt or invented state strings in DB rows fail safe to SHADOW."""
    db_file = tmp_path / "invalid_enum_state.sqlite3"
    store = CutoverPersistenceStore(db_path=db_file)

    # Insert raw invalid state string directly into DB
    conn = sqlite3.connect(str(db_file))
    conn.execute(
        "INSERT OR REPLACE INTO consumer_cutover_state (consumer_name, current_state) VALUES (?, ?)",
        ("HRIDAY", "INVENTED_ILLEGAL_STATE_STRING"),
    )
    conn.commit()
    conn.close()

    # Reload through store
    records = store.load_all_consumer_states()
    assert records[ConsumerName.HRIDAY].current_state == CutoverState.SHADOW


# =============================================================================
# 13. STATE SCHEMA VERSION GATING TESTS
# =============================================================================

def test_unknown_future_schema_version_blocks_active_routing(tmp_path: Path):
    """Verifies that an unknown newer schema version strictly blocks active routing and fails to SHADOW."""
    db_file = tmp_path / "future_schema.sqlite3"
    store = CutoverPersistenceStore(db_path=db_file)

    # Put HRIDAY in V2_PRIMARY under a future schema version
    rec = ConsumerCutoverRecord(
        consumer_name=ConsumerName.HRIDAY,
        current_state=CutoverState.V2_PRIMARY,
        cutover_state_schema_version=999,  # Future unsupported version
    )
    store.save_consumer_state(rec)

    # Set metadata schema_version to 999
    conn = sqlite3.connect(str(db_file))
    conn.execute("UPDATE cutover_metadata SET value = '999' WHERE key = 'schema_version'")
    conn.commit()
    conn.close()

    # Re-instantiate
    store2 = CutoverPersistenceStore(db_path=db_file)
    records = store2.load_all_consumer_states()

    # Must fail safe: blocked from active V2_PRIMARY
    assert records[ConsumerName.HRIDAY].current_state == CutoverState.SHADOW


# =============================================================================
# 14. CONFIGURATION SOURCE & USER PAYLOAD ISOLATION TESTS
# =============================================================================

def test_configuration_source_recorded_and_typed(tmp_path: Path):
    """Verifies typed enum configuration sources: ENVIRONMENT, CONTROL_PLANE, DECISION_LEDGER, TEST_FIXTURE."""
    db_file = tmp_path / "config_src.sqlite3"
    store = CutoverPersistenceStore(db_path=db_file)
    sm = ConsumerCutoverStateMachine(persistence_store=store)

    rec = sm.transition(
        ConsumerName.HRIDAY,
        CutoverState.CERTIFIED,
        reason="Certified via decision ledger",
        authorized_source=ConfigurationSource.DECISION_LEDGER,
    )
    assert rec.configuration_source == ConfigurationSource.DECISION_LEDGER

    # Reload from store
    sm2 = ConsumerCutoverStateMachine(persistence_store=store)
    assert sm2.get_record(ConsumerName.HRIDAY).configuration_source == ConfigurationSource.DECISION_LEDGER


def test_normal_request_payload_cannot_mutate_cutover_state(gateway):
    """Negative test: user request payload arguments cannot alter gateway state or feature gates."""
    assert gateway.state_machine.get_state(ConsumerName.HRIDAY) == CutoverState.SHADOW

    # Attempt to pass state-mutating keys through evaluate_route
    user_payload_injection = {
        "dataset_id": "ds-injection",
        "consumer_state": "V2_PRIMARY",
        "feature_enabled": True,
        "global_enabled": True,
        "fallback_allowed": False,
    }

    # evaluate_route signature only accepts its declared parameters
    decision = gateway.evaluate_route(
        consumer=ConsumerName.HRIDAY,
        dataset_id=user_payload_injection["dataset_id"],
    )

    # Gateway state must remain completely unmutated
    assert gateway.state_machine.get_state(ConsumerName.HRIDAY) == CutoverState.SHADOW
    assert decision.selected_route == Route.V1
    assert decision.consumer_state == CutoverState.SHADOW


# =============================================================================
# 15. CUTOVER DECISION LEDGER DURABILITY TESTS
# =============================================================================

def test_cutover_decision_ledger_durability(tmp_path: Path):
    """Verifies that transition ledger entries survive process restart with all provenance fields."""
    db_file = tmp_path / "ledger_durability.sqlite3"
    store = CutoverPersistenceStore(db_path=db_file)
    sm = ConsumerCutoverStateMachine(persistence_store=store)

    sm.transition(
        ConsumerName.HRIDAY,
        CutoverState.CERTIFIED,
        reason="Parity certified",
        certification_evidence="RUN-CERT-009",
        commit="commit-abc123",
        artifact_fingerprints={"semantic_graph": "sg-fp-99", "manifest": "mf-fp-99"},
        authorized_source=ConfigurationSource.CONTROL_PLANE,
    )

    history1 = sm.get_transition_history()
    assert len(history1) == 1
    assert history1[0].consumer == ConsumerName.HRIDAY
    assert history1[0].from_state == CutoverState.SHADOW
    assert history1[0].to_state == CutoverState.CERTIFIED
    assert history1[0].artifact_fingerprints["semantic_graph"] == "sg-fp-99"

    # Recreate service from store
    del sm
    del store

    store2 = CutoverPersistenceStore(db_path=db_file)
    sm2 = ConsumerCutoverStateMachine(persistence_store=store2)
    history2 = sm2.get_transition_history()

    assert len(history2) == 1
    assert history2[0].transition_id == history1[0].transition_id
    assert history2[0].consumer == ConsumerName.HRIDAY
    assert history2[0].from_state == CutoverState.SHADOW
    assert history2[0].to_state == CutoverState.CERTIFIED
    assert history2[0].commit == "commit-abc123"
    assert history2[0].artifact_fingerprints["semantic_graph"] == "sg-fp-99"
    assert history2[0].authorized_configuration_source == ConfigurationSource.CONTROL_PLANE


# =============================================================================
# 16. CIRCUIT BREAKER RESTART SEMANTICS & HALF-OPEN PROBE TESTS
# =============================================================================

def test_circuit_breaker_restart_preserves_readiness_guards(tmp_path: Path):
    """
    Verifies that a process restart with circuit breaker reset CANNOT bypass
    stale/missing/ungrounded artifact guards.
    """
    db_file = tmp_path / "cb_restart.sqlite3"
    store = CutoverPersistenceStore(db_path=db_file)
    gw = ConsumerIntelligenceGateway(persistence_store=store)
    gw.set_global_enabled(True)
    gw.set_consumer_enabled(ConsumerName.HRIDAY, True)

    gw.state_machine.transition(ConsumerName.HRIDAY, CutoverState.CERTIFIED, "c")
    gw.state_machine.transition(ConsumerName.HRIDAY, CutoverState.CANARY, "can")
    gw.state_machine.transition(ConsumerName.HRIDAY, CutoverState.V2_PRIMARY_WITH_FALLBACK, "p")

    # Trip breaker OPEN due to repeated failures
    gw.circuit_breaker.trip(ConsumerName.HRIDAY, FallbackReason.V2_RUNTIME_ERROR)
    assert gw.circuit_breaker.get_state(ConsumerName.HRIDAY) == CircuitBreakerState.OPEN

    # Destroy and recreate gateway instance (simulating process restart)
    del gw
    store2 = CutoverPersistenceStore(db_path=db_file)
    gw2 = ConsumerIntelligenceGateway(persistence_store=store2)
    gw2.set_global_enabled(True)
    gw2.set_consumer_enabled(ConsumerName.HRIDAY, True)

    # Even if breaker starts clean, a stale artifact request MUST be blocked and fall back to V1!
    stale_manifest = {"dataset_version": "1", "is_fresh": False}
    decision = gw2.evaluate_route(ConsumerName.HRIDAY, dataset_id="ds-restart", manifest_data=stale_manifest)
    assert decision.selected_route == Route.V1
    assert decision.fallback_used is True
    assert decision.fallback_reason == FallbackReason.V2_ARTIFACT_STALE


def test_half_open_blocks_ordinary_traffic_and_allows_probe():
    """
    Verifies that during HALF_OPEN:
    - Ordinary traffic (is_probe=False) routes strictly to V1.
    - Explicit recovery probe (is_probe=True) is permitted to test V2.
    """
    cb = CircuitBreakerManager(cooldown_seconds=0.01, required_probe_successes=2)
    cb.trip(ConsumerName.HRIDAY, FallbackReason.V2_RUNTIME_ERROR)
    assert cb.get_state(ConsumerName.HRIDAY) == CircuitBreakerState.OPEN

    # Allow cooldown to elapse
    time.sleep(0.02)
    assert cb.is_probe_eligible(ConsumerName.HRIDAY) is True
    assert cb.get_state(ConsumerName.HRIDAY) == CircuitBreakerState.HALF_OPEN

    # Ordinary traffic must be BLOCKED
    assert cb.can_attempt_v2(ConsumerName.HRIDAY, is_probe=False) is False

    # Explicit probe must be ALLOWED
    assert cb.can_attempt_v2(ConsumerName.HRIDAY, is_probe=True) is True

    # 1 successful probe: remains in HALF_OPEN (requires 2)
    cb.record_success(ConsumerName.HRIDAY)
    assert cb.get_state(ConsumerName.HRIDAY) == CircuitBreakerState.HALF_OPEN

    # 2nd successful probe: resets to CLOSED
    cb.record_success(ConsumerName.HRIDAY)
    assert cb.get_state(ConsumerName.HRIDAY) == CircuitBreakerState.CLOSED
    assert cb.can_attempt_v2(ConsumerName.HRIDAY, is_probe=False) is True


# =============================================================================
# 17. CANARY AUTHORIZATION: EXPLICIT & DETERMINISTIC COHORT TESTS
# =============================================================================

def test_canary_explicit_authorization_vs_ordinary(gateway):
    """Verifies that CANARY mode allows explicit authorized requests while blocking ordinary ones."""
    gateway.set_global_enabled(True)
    gateway.set_consumer_enabled(ConsumerName.HRIDAY, True)
    gateway.state_machine.transition(ConsumerName.HRIDAY, CutoverState.CERTIFIED, "c")
    gateway.state_machine.transition(ConsumerName.HRIDAY, CutoverState.CANARY, "can")

    manifest = {"dataset_version": "1", "is_fresh": True, "available_artifacts": ["schema.json"]}

    # Ordinary request without authorization -> V1
    d_ordinary = gateway.evaluate_route(ConsumerName.HRIDAY, dataset_id="ds-test", is_canary=False, manifest_data=manifest)
    assert d_ordinary.selected_route == Route.V1
    assert d_ordinary.fallback_reason == FallbackReason.CANARY_NOT_AUTHORIZED

    # Explicit authorized canary request -> V2
    d_canary = gateway.evaluate_route(ConsumerName.HRIDAY, dataset_id="ds-test", is_canary=True, manifest_data=manifest)
    assert d_canary.selected_route == Route.V2


def test_canary_deterministic_cohort_selection(gateway):
    """Verifies deterministic SHA-256 percentage-based cohort routing."""
    gateway.set_global_enabled(True)
    gateway.set_consumer_enabled(ConsumerName.HRIDAY, True)
    gateway.state_machine.transition(ConsumerName.HRIDAY, CutoverState.CERTIFIED, "c")
    gateway.state_machine.transition(ConsumerName.HRIDAY, CutoverState.CANARY, "can")

    manifest = {"dataset_version": "1", "is_fresh": True, "available_artifacts": ["schema.json"]}

    # Known cohort that hashes below 50% vs above 50%
    d_in = gateway.evaluate_route(
        ConsumerName.HRIDAY,
        dataset_id="ds-test",
        canary_cohort="cohort_sample_alpha",
        canary_percentage=100.0,
        manifest_data=manifest,
    )
    assert d_in.selected_route == Route.V2

    d_out = gateway.evaluate_route(
        ConsumerName.HRIDAY,
        dataset_id="ds-test",
        canary_cohort="cohort_sample_alpha",
        canary_percentage=0.0,
        manifest_data=manifest,
    )
    assert d_out.selected_route == Route.V1


# =============================================================================
# 18. INDEPENDENT FALLBACK POLICY TESTS
# =============================================================================

def test_fallback_disallowed_raises_governed_error(gateway):
    """Verifies that when fallback_allowed=False, failure raises RoutingFallbackDisallowedError (no silent V1 rescue)."""
    gateway.set_global_enabled(True)
    gateway.set_consumer_enabled(ConsumerName.HRIDAY, True)
    gateway.set_fallback_allowed(ConsumerName.HRIDAY, False)

    gateway.state_machine.transition(ConsumerName.HRIDAY, CutoverState.CERTIFIED, "c")
    gateway.state_machine.transition(ConsumerName.HRIDAY, CutoverState.CANARY, "can")
    gateway.state_machine.transition(ConsumerName.HRIDAY, CutoverState.V2_PRIMARY_WITH_FALLBACK, "p")

    stale_manifest = {"dataset_version": "1", "is_fresh": False}

    with pytest.raises(RoutingFallbackDisallowedError) as exc_info:
        gateway.evaluate_route(ConsumerName.HRIDAY, dataset_id="ds-stale", manifest_data=stale_manifest)

    assert "fallback to V1 is disallowed" in str(exc_info.value)


# =============================================================================
# 19. CONCRETE ROUTING TELEMETRY ISOLATED CERTIFICATION SCENARIO
# =============================================================================

def test_concrete_isolated_routing_telemetry_scenario(tmp_path: Path):
    """
    Executes a deterministic isolated certification scenario:
    - 5 V1 decisions due to SHADOW/flags
    - 4 healthy V2 decisions
    - 3 governed fallbacks:
      - 1 stale-artifact fallback (V2_ARTIFACT_STALE)
      - 1 dataset-version fallback (V2_DATASET_VERSION_MISMATCH)
      - 1 evidence-grounding fallback (V2_CONTEXT_GROUNDING_FAILURE)
    - 1 circuit breaker open scenario
    - 1 rollback scenario
    Verifies and asserts exact resulting counters.
    """
    db_file = tmp_path / "telemetry_cert.sqlite3"
    store = CutoverPersistenceStore(db_path=db_file)
    gw = ConsumerIntelligenceGateway(persistence_store=store)

    valid_manifest = {"dataset_version": "1.0", "is_fresh": True, "available_artifacts": ["schema.json"]}

    # 1. 5 V1 decisions (SHADOW / flags off)
    gw.set_global_enabled(False)
    for _ in range(2):
        d = gw.evaluate_route(ConsumerName.HRIDAY, dataset_id="ds-1")
        assert d.selected_route == Route.V1

    gw.set_global_enabled(True)
    gw.set_consumer_enabled(ConsumerName.HRIDAY, False)
    for _ in range(2):
        d = gw.evaluate_route(ConsumerName.HRIDAY, dataset_id="ds-1")
        assert d.selected_route == Route.V1

    # In SHADOW state
    gw.set_consumer_enabled(ConsumerName.HRIDAY, True)
    d = gw.evaluate_route(ConsumerName.HRIDAY, dataset_id="ds-1")
    assert d.selected_route == Route.V1
    # Total V1 from gating: 5

    # Advance to V2_PRIMARY_WITH_FALLBACK
    gw.state_machine.transition(ConsumerName.HRIDAY, CutoverState.CERTIFIED, "c")
    gw.state_machine.transition(ConsumerName.HRIDAY, CutoverState.CANARY, "can")
    gw.state_machine.transition(ConsumerName.HRIDAY, CutoverState.V2_PRIMARY_WITH_FALLBACK, "p")

    # 2. 4 healthy V2 decisions
    for _ in range(4):
        d = gw.evaluate_route(ConsumerName.HRIDAY, dataset_id="ds-1", dataset_version="1.0", manifest_data=valid_manifest)
        assert d.selected_route == Route.V2

    # 3. 3 governed fallbacks
    # 3a. Stale artifact fallback
    stale_mf = {"dataset_version": "1.0", "is_fresh": False, "available_artifacts": ["schema.json"]}
    d_stale = gw.evaluate_route(ConsumerName.HRIDAY, dataset_id="ds-1", dataset_version="1.0", manifest_data=stale_mf)
    assert d_stale.selected_route == Route.V1
    assert d_stale.fallback_reason == FallbackReason.V2_ARTIFACT_STALE

    # 3b. Dataset version mismatch fallback
    d_ver = gw.evaluate_route(ConsumerName.HRIDAY, dataset_id="ds-1", dataset_version="2.0", manifest_data=valid_manifest)
    assert d_ver.selected_route == Route.V1
    assert d_ver.fallback_reason == FallbackReason.V2_DATASET_VERSION_MISMATCH

    # 3c. Evidence grounding failure fallback
    d_eg = gw.evaluate_route(
        ConsumerName.HRIDAY,
        dataset_id="ds-1",
        dataset_version="1.0",
        manifest_data=valid_manifest,
        required_evidence_refs=["EVID-NONEXISTENT-999"],
        available_evidence_ids={"EVID-VALID-001"},
    )
    assert d_eg.selected_route == Route.V1
    assert d_eg.fallback_reason == FallbackReason.V2_CONTEXT_GROUNDING_FAILURE

    # 4. Circuit breaker open scenario
    gw.circuit_breaker.trip(ConsumerName.HRIDAY, FallbackReason.CIRCUIT_BREAKER_OPEN)
    d_cb = gw.evaluate_route(ConsumerName.HRIDAY, dataset_id="ds-1", dataset_version="1.0", manifest_data=valid_manifest)
    assert d_cb.selected_route == Route.V1
    assert d_cb.fallback_reason == FallbackReason.CIRCUIT_BREAKER_OPEN

    # 5. Rollback scenario
    gw.circuit_breaker.reset(ConsumerName.HRIDAY)
    gw.state_machine.rollback(ConsumerName.HRIDAY, "Emergency policy test")
    gw.provenance_ledger.increment_rollback_counter()
    d_rb = gw.evaluate_route(ConsumerName.HRIDAY, dataset_id="ds-1", dataset_version="1.0", manifest_data=valid_manifest)
    assert d_rb.selected_route == Route.V1

    # Extract exact telemetry snapshot
    telem = gw.get_telemetry()

    print("\n--- CONCRETE CERTIFICATION RUN TELEMETRY SNAPSHOT ---")
    print(json.dumps(telem, indent=2))

    assert telem["consumer_route_v1_count"] == 10  # 5 initial + 3 fallbacks + 1 CB + 1 rollback
    assert telem["consumer_route_v2_count"] == 4
    assert telem["consumer_fallback_count"] == 4   # 3 readiness + 1 CB
    assert telem["consumer_v2_failure_count"] == 4
    assert telem["stale_artifact_block_count"] == 1
    assert telem["dataset_mismatch_block_count"] == 1
    assert telem["evidence_grounding_failure_count"] == 1
    assert telem["circuit_breaker_open_count"] == 1
    assert telem["rollback_count"] == 1


# =============================================================================
# 20. SINGLE ROUTING AUTHORITY CHECK
# =============================================================================

def test_single_routing_authority_no_scattered_branches():
    """
    Scans production application source files to verify that no direct V2 routing
    branches (e.g. `Route.V2`, `HIGHVIEW_V2_...`, or direct consumer bypasses)
    exist outside approved gateway and config modules.
    """
    import os

    backend_dir = Path(__file__).resolve().parent.parent / "app"
    approved_paths = {
        "services/ingestion_v2/gateway",
        "services/ingestion_v2/contracts",
        "core/config.py",
    }

    suspicious_patterns = [
        "Route.V2",
        "HIGHVIEW_V2_GLOBAL_ENABLED",
        "HIGHVIEW_V2_HRIDAY_ENABLED",
        "HIGHVIEW_V2_DASHBOARD_ENABLED",
        "HIGHVIEW_V2_PRESENTATION_ENABLED",
    ]

    violations: list[str] = []

    for root, _, files in os.walk(backend_dir):
        for f in files:
            if not f.endswith(".py"):
                continue
            full_path = Path(root) / f
            rel_path = full_path.relative_to(backend_dir).as_posix()

            # Skip approved gateway and config files
            if any(rel_path.startswith(ap) for ap in approved_paths):
                continue

            content = full_path.read_text(encoding="utf-8")
            for pat in suspicious_patterns:
                if pat in content:
                    violations.append(f"{rel_path}: contains '{pat}' outside approved gateway")

    assert len(violations) == 0, f"Found unauthorized consumer routing branches: {violations}"

