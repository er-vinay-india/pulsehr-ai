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

import threading
import time
import tracemalloc
from concurrent.futures import ThreadPoolExecutor
import pytest

from app.services.ingestion_v2.contracts.cutover import (
    CircuitBreakerState,
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
    InvalidCutoverTransitionError,
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
    cb = CircuitBreakerManager(failure_threshold=3)

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
    assert cb.can_attempt_v2(ConsumerName.HRIDAY) is True

    # Successful request in HALF_OPEN resets to CLOSED
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
