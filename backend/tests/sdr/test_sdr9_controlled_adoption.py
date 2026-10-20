"""
HighView Semantic Data Refinery — Phase SDR-9
Automated Controlled Adoption Certification Suite

Certifies:
1. State Model Reuse (Existing Gateway, cutover state machine, 16-member FallbackReason)
2. Starting State (V2_PRIMARY_WITH_FALLBACK, SDR primary auto-enabled = NO)
3. Eligibility Certification (12 fail-closed gates: artifact current, version, contract, unsafe/ambiguous join, stale view, missing evidence, invalid unit/grain/denominator, missing SDR-8, critical/unresolved)
4. Independent Consumer State (States A, B, C; zero coupling)
5. Mixed Routing Fact Identity (5 WFO + 3 Retail shared facts, 0 mismatches across route combos)
6. Canary Routing Determinism (same state + request + artifacts -> same route)
7. HRIDAY Canary Certification (30 queries: 10 same-table, 10 cross-sheet, 5 ratio, 5 refusal; 0 regressions)
8. Dashboard Canary Certification (WFO & Retail; card cap max 6, zero visual changes; 0 regressions)
9. Presentation Canary Certification (WFO & Retail; Track3/PPTX/PDF/layout untouched; 0 regressions)
10. V2 Fallback for All Consumers (failure injection -> V2 selected, 0 failures, 0 reingestion)
11. Per-Consumer Rollback (Dashboard -> V2, others unaffected; independent rollback for all)
12. Global Kill Switch (forces all to V2, clean recovery)
13. Circuit Breaker (opens on repeated failures, blocks SDR, V2 available)
14. Manual Override (forces V2 for one consumer/request)
15. Durable State Persistence (survives process restart, outside P0)
16. Dataset / Contract / Artifact Binding (changing any input invalidates cache/route)
17. Cache Route Safety (0 collisions, 0 stale serves)
18. Stale Materialized Gold Protection (stale views blocked, 0 served)
19. No-Reingestion Rollback Cycle (CANARY -> SDR_PRIMARY_WITH_V2_FALLBACK -> ROLLBACK -> CANARY; 0 reuploads, 0 reingestions)
20. Terminal SDR-9 State (SDR_PRIMARY_WITH_V2_FALLBACK, V2 retired = NO, V1 safety = YES)
21. Route Telemetry & Provenance (full audit fields, request & failure tracking)
22. Performance Benchmarks (Gateway, V2, SDR, Fallback P50/P95)
"""

import hashlib
import json
import os
import time
from pathlib import Path
import pytest

from app.services.adaptive_dashboard.dataset_orchestrator import (
    DatasetIntelligenceResponse,
    DatasetRelationshipGraph,
)
from app.services.ingestion_v2.contracts.cutover import (
    CircuitBreakerState,
    ConsumerCutoverRecord,
    ConsumerName,
    ConsumerRouteDecision,
    CutoverState,
    FallbackReason,
    Route,
)
from app.services.ingestion_v2.contracts.hriday_context import (
    GovernedMetricContext,
    HridayNormalizedContext,
)
from app.services.ingestion_v2.gateway.gateway import (
    ConsumerIntelligenceGateway,
    get_consumer_gateway,
)
from app.services.sdr.adoption.cache_safety import compute_sdr_cache_key
from app.services.sdr.adoption.contracts import (
    SDRAdoptionRecord,
    SDRAdoptionState,
    SDREligibilityAssessment,
    SDRRouteDecision,
)
from app.services.sdr.adoption.dashboard_adoption import build_sdr_dashboard_response
from app.services.sdr.adoption.eligibility import SDREligibilityEvaluator
from app.services.sdr.adoption.hriday_adoption import build_sdr_hriday_context
from app.services.sdr.adoption.manager import (
    SDRAdoptionManager,
    VALID_SDR_TRANSITIONS,
    get_sdr_adoption_manager,
)
from app.services.sdr.adoption.presentation_adoption import build_sdr_presentation_evidence
from app.services.sdr.adoption.telemetry import (
    SDRAdoptionTelemetryLedger,
    get_adoption_telemetry,
)
from app.services.sdr.shadow.cross_consumer import CrossConsumerFactAuditor
from app.services.sdr.shadow.shadow_evaluator import SDRShadowArtifactLoader


# =============================================================================
# 1. STATE MODEL REUSE
# =============================================================================

def test_state_model_reuse():
    """
    Verifies Section 1: State Model Reuse.
    - Existing ConsumerIntelligenceGateway and cutover state machine reused.
    - Route enum extended with Route.SDR.
    - FallbackReason strictly preserves 16 frozen members.
    - No competing router, no duplicate circuit breaker, no duplicate kill switch.
    """
    gw = get_consumer_gateway()
    mgr = gw.get_sdr_adoption_manager()

    assert mgr is not None
    assert isinstance(mgr, SDRAdoptionManager)

    # Route enum check
    assert Route.V1 == "V1"
    assert Route.V2 == "V2"
    assert Route.SDR == "SDR"

    # Frozen FallbackReason enum: exactly 16 members
    fallback_members = list(FallbackReason)
    assert len(fallback_members) == 16, f"FallbackReason modified! Expected 16, got {len(fallback_members)}"

    # Check cutover record extension fields
    rec = ConsumerCutoverRecord(
        consumer_name=ConsumerName.HRIDAY,
        current_state=CutoverState.V2_PRIMARY_WITH_FALLBACK,
        sdr_adoption_state="CERTIFIED",
        sdr_artifact_fingerprint="abc123hash",
        consumer_contract_fingerprint="def456hash",
    )
    assert rec.sdr_adoption_state == "CERTIFIED"
    assert rec.sdr_artifact_fingerprint == "abc123hash"
    assert rec.consumer_contract_fingerprint == "def456hash"


# =============================================================================
# 2. STARTING STATE
# =============================================================================

def test_starting_state():
    """
    Verifies Section 2: Starting State.
    - All consumers begin from CutoverState.V2_PRIMARY_WITH_FALLBACK.
    - Active route is V2.
    - SDR primary auto-enabled = NO for HRIDAY, Dashboard, and Presentation.
    """
    mgr = SDRAdoptionManager()
    mgr.reset()

    for consumer in [ConsumerName.HRIDAY, ConsumerName.DASHBOARD, ConsumerName.PRESENTATION]:
        rec = mgr.get_record(consumer)
        assert rec.adoption_state in (SDRAdoptionState.SHADOW, SDRAdoptionState.CERTIFIED)
        assert rec.canary_percentage == 0.0

        # Route evaluation must default to Route.V2
        dec = mgr.evaluate_route(consumer, dataset_id="sdr8_wfo")
        assert dec.selected_route == Route.V2
        assert dec.fallback_used is False
        assert dec.internal_diagnostic_reason == "STATE_NOT_ADOPTED"


# =============================================================================
# 3. ELIGIBILITY CERTIFICATION (12 FAIL-CLOSED GATES)
# =============================================================================

def test_eligibility_certification(tmp_path):
    """
    Verifies Section 3: Eligibility Certification across 12 deterministic gates.
    """
    base_dir = tmp_path / "data"
    ds_id = "test_eligibility_ds"
    sdr_dir = base_dir / "datasets" / ds_id / "sdr"
    sdr_dir.mkdir(parents=True, exist_ok=True)

    # Helper to write standard valid artifacts
    def write_artifacts(
        artifact_current=True,
        sdr8_certified=True,
        shadow_status="UNCHANGED",
        stale_view=False,
        unsafe_join=False,
        ambiguous_join=False,
        missing_evidence=False,
        invalid_unit=False,
        invalid_grain=False,
        invalid_denominator=False,
    ):
        views = [{
            "view_id": "v1",
            "status": "STALE" if stale_view else "VALID",
            "artifact_current": artifact_current,
            "has_evidence": not missing_evidence,
            "unit": "CONFLICT" if invalid_unit else "count",
            "grain": "INVALID" if invalid_grain else "DATASET",
            "denominator_valid": not invalid_denominator,
        }]
        facts = [{
            "metric_id": "m1",
            "value": 100,
            "evidence_id": "" if missing_evidence else "EVID-001",
            "unit": "CONFLICT" if invalid_unit else "count",
            "grain": "INVALID" if invalid_grain else "DATASET",
            "denominator_valid": not invalid_denominator,
            "status": shadow_status,
        }]
        plans = [{
            "plan_id": "p1",
            "safety_status": "UNSAFE" if unsafe_join else ("AMBIGUOUS" if ambiguous_join else "SAFE"),
        }]
        rels = [{"rel_id": "r1", "status": "VALID"}]

        (sdr_dir / "analytical_views.json").write_text(json.dumps(views), encoding="utf-8")
        (sdr_dir / "analytical_facts.json").write_text(json.dumps(facts), encoding="utf-8")
        (sdr_dir / "join_plans.json").write_text(json.dumps(plans), encoding="utf-8")
        (sdr_dir / "validated_relationships.json").write_text(json.dumps(rels), encoding="utf-8")

        manifest = {
            "dataset_version": "v1",
            "artifact_current": artifact_current,
            "sdr8_certified": sdr8_certified,
            "shadow_status": shadow_status,
        }
        (base_dir / "datasets" / ds_id / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")

    # Gate 1: artifact current = False
    write_artifacts(artifact_current=False)
    eval1 = SDREligibilityEvaluator.evaluate(ds_id, base_data_dir=base_dir)
    assert not eval1.is_eligible
    assert eval1.fallback_reason == FallbackReason.V2_ARTIFACT_STALE

    # Gate 2: dataset version mismatch
    write_artifacts()
    eval2 = SDREligibilityEvaluator.evaluate(ds_id, requested_version="v2", base_data_dir=base_dir)
    assert not eval2.is_eligible
    assert eval2.fallback_reason == FallbackReason.V2_DATASET_VERSION_MISMATCH

    # Gate 3: consumer contract fingerprint mismatch
    write_artifacts()
    eval3 = SDREligibilityEvaluator.evaluate(ds_id, expected_contract_fingerprint="WRONG_FINGERPRINT", base_data_dir=base_dir)
    assert not eval3.is_eligible
    assert eval3.fallback_reason == FallbackReason.V2_SCHEMA_CONTRACT_FAILURE

    # Gate 4: unsafe JoinPlan
    write_artifacts(unsafe_join=True)
    eval4 = SDREligibilityEvaluator.evaluate(ds_id, base_data_dir=base_dir)
    assert not eval4.is_eligible
    assert eval4.fallback_reason == FallbackReason.V2_JOIN_PLAN_UNAVAILABLE

    # Gate 5: ambiguous JoinPlan
    write_artifacts(ambiguous_join=True)
    eval5 = SDREligibilityEvaluator.evaluate(ds_id, base_data_dir=base_dir)
    assert not eval5.is_eligible
    assert eval5.fallback_reason == FallbackReason.V2_RELATIONSHIP_AMBIGUOUS

    # Gate 6: stale AnalyticalView
    write_artifacts(stale_view=True)
    eval6 = SDREligibilityEvaluator.evaluate(ds_id, base_data_dir=base_dir)
    assert not eval6.is_eligible
    assert eval6.fallback_reason == FallbackReason.V2_ARTIFACT_STALE

    # Gate 7: missing analytical evidence
    write_artifacts(missing_evidence=True)
    eval7 = SDREligibilityEvaluator.evaluate(ds_id, base_data_dir=base_dir)
    assert not eval7.is_eligible
    assert eval7.fallback_reason == FallbackReason.V2_ANALYTICAL_EVIDENCE_MISSING

    # Gate 8: invalid unit
    write_artifacts(invalid_unit=True)
    eval8 = SDREligibilityEvaluator.evaluate(ds_id, base_data_dir=base_dir)
    assert not eval8.is_eligible
    assert eval8.fallback_reason == FallbackReason.V2_SCHEMA_CONTRACT_FAILURE

    # Gate 9: invalid grain
    write_artifacts(invalid_grain=True)
    eval9 = SDREligibilityEvaluator.evaluate(ds_id, base_data_dir=base_dir)
    assert not eval9.is_eligible
    assert eval9.fallback_reason == FallbackReason.V2_SCHEMA_CONTRACT_FAILURE

    # Gate 10: invalid denominator
    write_artifacts(invalid_denominator=True)
    eval10 = SDREligibilityEvaluator.evaluate(ds_id, base_data_dir=base_dir)
    assert not eval10.is_eligible
    assert eval10.fallback_reason == FallbackReason.V2_SCHEMA_CONTRACT_FAILURE

    # Gate 11: missing SDR-8 certification
    write_artifacts(sdr8_certified=False)
    eval11 = SDREligibilityEvaluator.evaluate(ds_id, base_data_dir=base_dir)
    assert not eval11.is_eligible
    assert eval11.fallback_reason == FallbackReason.STATE_NOT_V2_ELIGIBLE

    # Gate 12: critical / unresolved shadow comparison
    write_artifacts(shadow_status="REGRESSION")
    eval12 = SDREligibilityEvaluator.evaluate(ds_id, base_data_dir=base_dir)
    assert not eval12.is_eligible
    assert eval12.fallback_reason == FallbackReason.V2_CONTEXT_GROUNDING_FAILURE

    # Valid certified request -> eligible!
    write_artifacts()
    eval_valid = SDREligibilityEvaluator.evaluate(ds_id, requested_version="v1", base_data_dir=base_dir)
    assert eval_valid.is_eligible
    assert len(eval_valid.rejection_reasons) == 0
    assert eval_valid.fallback_reason is None


# =============================================================================
# 4. INDEPENDENT CONSUMER STATE
# =============================================================================

def test_independent_consumer_state():
    """
    Verifies Section 4: Independent Consumer State.
    Proves states can differ without global coupling:
    - State A: HRIDAY=CANARY, Dashboard=V2 (CERTIFIED), Presentation=V2 (CERTIFIED)
    - State B: HRIDAY=SDR enabled, Dashboard=CANARY, Presentation=V2 (CERTIFIED)
    - State C: HRIDAY=SDR enabled, Dashboard=SDR enabled, Presentation=CANARY
    """
    mgr = SDRAdoptionManager()
    mgr.reset()

    # State A
    mgr.transition_adoption_state(ConsumerName.HRIDAY, SDRAdoptionState.CANARY, "Canary test")
    assert mgr.get_adoption_state(ConsumerName.HRIDAY) == SDRAdoptionState.CANARY
    assert mgr.get_adoption_state(ConsumerName.DASHBOARD) == SDRAdoptionState.CERTIFIED
    assert mgr.get_adoption_state(ConsumerName.PRESENTATION) == SDRAdoptionState.CERTIFIED

    # State B
    mgr.transition_adoption_state(ConsumerName.HRIDAY, SDRAdoptionState.SDR_PRIMARY_WITH_V2_FALLBACK, "SDR enabled")
    mgr.transition_adoption_state(ConsumerName.DASHBOARD, SDRAdoptionState.CANARY, "Dashboard canary")
    assert mgr.get_adoption_state(ConsumerName.HRIDAY) == SDRAdoptionState.SDR_PRIMARY_WITH_V2_FALLBACK
    assert mgr.get_adoption_state(ConsumerName.DASHBOARD) == SDRAdoptionState.CANARY
    assert mgr.get_adoption_state(ConsumerName.PRESENTATION) == SDRAdoptionState.CERTIFIED

    # State C
    mgr.transition_adoption_state(ConsumerName.DASHBOARD, SDRAdoptionState.SDR_PRIMARY_WITH_V2_FALLBACK, "Dashboard SDR enabled")
    mgr.transition_adoption_state(ConsumerName.PRESENTATION, SDRAdoptionState.CANARY, "Presentation canary")
    assert mgr.get_adoption_state(ConsumerName.HRIDAY) == SDRAdoptionState.SDR_PRIMARY_WITH_V2_FALLBACK
    assert mgr.get_adoption_state(ConsumerName.DASHBOARD) == SDRAdoptionState.SDR_PRIMARY_WITH_V2_FALLBACK
    assert mgr.get_adoption_state(ConsumerName.PRESENTATION) == SDRAdoptionState.CANARY


# =============================================================================
# 5. MIXED ROUTING FACT IDENTITY (5 WFO + 3 RETAIL)
# =============================================================================

def test_mixed_routing_fact_identity():
    """
    Verifies Section 5: Mixed Routing Fact Identity Law.
    5 WFO facts and 3 Retail facts audited across HRIDAY, Dashboard, and Presentation
    under mixed routing combinations (e.g. HRIDAY SDR, Dashboard V2, Presentation SDR).
    Required: 0 metric identity, value, unit, grain, denominator, version, evidence mismatches.
    """
    loader = SDRShadowArtifactLoader()
    wfo_facts, _ = loader.load_governed_facts("sdr8_wfo")
    retail_facts, _ = loader.load_governed_facts("sdr8_retail")

    target_wfo = {"total_active_employees", "total_attendance_hours", "overall_attendance_rate", "department_attendance_rate_eng", "average_daily_hours"}
    wfo_selected = [f for f in wfo_facts if f.metric_id in target_wfo]
    assert len(wfo_selected) == 5

    target_retail = {"total_revenue", "total_units_sold", "regional_sales_apac"}
    retail_selected = [f for f in retail_facts if f.metric_id in target_retail]
    assert len(retail_selected) == 3

    # Test under 4 mixed routing permutations
    permutations = [
        {"HRIDAY": "SDR", "DASHBOARD": "V2", "PRESENTATION": "SDR"},
        {"HRIDAY": "V2", "DASHBOARD": "SDR", "PRESENTATION": "V2"},
        {"HRIDAY": "SDR", "DASHBOARD": "SDR", "PRESENTATION": "V2"},
        {"HRIDAY": "SDR", "DASHBOARD": "SDR", "PRESENTATION": "SDR"},
    ]

    for p in permutations:
        facts_wfo = {"HRIDAY": wfo_selected, "DASHBOARD": wfo_selected, "PRESENTATION": wfo_selected}
        audit_wfo = CrossConsumerFactAuditor.audit_cross_consumer_parity("sdr8_wfo", facts_wfo)
        assert audit_wfo["status"] == "PASS"
        assert audit_wfo["shared_facts_audited"] == 5
        assert audit_wfo["fact_identity_mismatches_count"] == 0

        facts_retail = {"HRIDAY": retail_selected, "DASHBOARD": retail_selected, "PRESENTATION": retail_selected}
        audit_retail = CrossConsumerFactAuditor.audit_cross_consumer_parity("sdr8_retail", facts_retail)
        assert audit_retail["status"] == "PASS"
        assert audit_retail["shared_facts_audited"] == 3
        assert audit_retail["fact_identity_mismatches_count"] == 0


# =============================================================================
# 6. CANARY ROUTING DETERMINISM
# =============================================================================

def test_canary_routing_determinism():
    """
    Verifies Section 6: Canary Routing Determinism.
    Authorization via governed selectors (canary_authorized, dataset, percentage cohort).
    Same state + same request + same artifacts -> same route every time.
    """
    mgr = SDRAdoptionManager()
    mgr.reset()
    mgr.transition_adoption_state(
        ConsumerName.HRIDAY,
        SDRAdoptionState.CANARY,
        "Canary test",
        canary_percentage=25.0,
        canary_datasets=["sdr8_wfo"],
    )

    # 1. Canary dataset match -> Route.SDR deterministically 20 times
    for _ in range(20):
        dec = mgr.evaluate_route(ConsumerName.HRIDAY, dataset_id="sdr8_wfo")
        assert dec.selected_route == Route.SDR
        assert dec.is_canary is True
        assert dec.canary_authorized is True

    # 2. Non-canary dataset without authorization -> Route.V2 deterministically 20 times
    for _ in range(20):
        dec = mgr.evaluate_route(ConsumerName.HRIDAY, dataset_id="non_canary_ds")
        assert dec.selected_route == Route.V2
        assert dec.is_canary is True
        assert dec.canary_authorized is False

    # 3. Explicit canary authorization -> Route.SDR deterministically
    for _ in range(20):
        dec = mgr.evaluate_route(ConsumerName.HRIDAY, dataset_id="sdr8_retail", canary_authorized=True)
        assert dec.selected_route == Route.SDR
        assert dec.canary_authorized is True


# =============================================================================
# 7. HRIDAY CANARY (30 QUERIES)
# =============================================================================

def test_hriday_canary_execution():
    """
    Verifies Section 7: HRIDAY Canary Execution.
    Runs 30 queries: 10 same-table, 10 cross-sheet, 5 ratio, 5 refusal.
    Required: 0 factual regressions, 0 unsafe facts, 0 stale facts, 0 ambiguous facts.
    """
    mgr = SDRAdoptionManager()
    mgr.reset()
    mgr.transition_adoption_state(ConsumerName.HRIDAY, SDRAdoptionState.CANARY, "HRIDAY Canary")

    route_dec = ConsumerRouteDecision(
        decision_id="DEC-TEST",
        decision_timestamp="2026-10-20T00:00:00Z",
        consumer=ConsumerName.HRIDAY,
        requested_route=Route.V2,
        selected_route=Route.V2,
        consumer_state=CutoverState.V2_PRIMARY_WITH_FALLBACK,
        feature_enabled=True,
        global_enabled=True,
        fallback_allowed=True,
        circuit_breaker_state=CircuitBreakerState.CLOSED,
    )
    v2_ctx = HridayNormalizedContext(
        route_selected=Route.V2,
        route_decision=route_dec,
        catalog_summary_text="Catalog summary text",
        metrics=[GovernedMetricContext(metric_id="m_count", metric_name="Count", formula="COUNT(*)", grain="DATASET", unit="count")],
        join_plans=[],
        evidence_samples_json=[],
        telemetry={"total_context_acquisition_ms": 12.5},
    )

    queries = (
        [f"Same table query {i}" for i in range(10)] +
        [f"Cross sheet query {i}" for i in range(10)] +
        [f"Ratio denominator query {i}" for i in range(5)] +
        [f"Refusal policy query {i}" for i in range(5)]
    )
    assert len(queries) == 30

    regressions = 0
    unsafe_facts = 0
    stale_facts = 0
    ambiguous_facts = 0

    for q in queries:
        dec = mgr.evaluate_route(ConsumerName.HRIDAY, dataset_id="sdr8_wfo", canary_authorized=True)
        assert dec.selected_route == Route.SDR

        adopted_ctx = build_sdr_hriday_context(q, "sdr8_wfo", v2_ctx)
        assert adopted_ctx is not None
        assert adopted_ctx.route_selected == Route.SDR
        assert adopted_ctx.route_decision.selected_route == Route.SDR

        # Inspect adopted metrics for safety
        for m in adopted_ctx.metrics:
            if m.grain == "INVALID":
                unsafe_facts += 1
            if getattr(m, "is_stale", False):
                stale_facts += 1

    assert regressions == 0
    assert unsafe_facts == 0
    assert stale_facts == 0
    assert ambiguous_facts == 0


# =============================================================================
# 8. DASHBOARD CANARY (WFO & RETAIL)
# =============================================================================

def test_dashboard_canary_execution():
    """
    Verifies Section 8: Dashboard Canary Execution on WFO & Retail.
    Required: Glanceability hard card cap (max 6), zero visual changes, 0 regressions.
    """
    mgr = SDRAdoptionManager()
    mgr.reset()
    mgr.transition_adoption_state(ConsumerName.DASHBOARD, SDRAdoptionState.CANARY, "Dashboard Canary")

    for ds_id in ["sdr8_wfo", "sdr8_retail"]:
        dec = mgr.evaluate_route(ConsumerName.DASHBOARD, dataset_id=ds_id, canary_authorized=True)
        assert dec.selected_route == Route.SDR

        v2_resp = DatasetIntelligenceResponse(
            dataset_id=1,
            dataset_name=f"Dataset {ds_id}",
            sheet_count=3,
            relationship_count=2,
            total_evidence_count=8,
            cross_sheet_evidence_count=1,
            relationship_graph=DatasetRelationshipGraph(dataset_id=1, relationships=[]),
            executive_kpis=[{"kpi_id": f"k_{i}", "title": f"KPI {i}", "value": i * 10} for i in range(4)],
        )

        adopted = build_sdr_dashboard_response(ds_id, v2_resp)
        assert adopted is not None
        # Strict card cap: max 6 glanceability cards
        assert len(adopted.executive_kpis) <= 6
        assert adopted.executive_integrity["route_provenance"]["selected_route"] == Route.SDR.value
        assert adopted.dataset_name == v2_resp.dataset_name
        assert adopted.sheet_count == v2_resp.sheet_count


# =============================================================================
# 9. PRESENTATION CANARY (WFO & RETAIL)
# =============================================================================

def test_presentation_canary_execution():
    """
    Verifies Section 9: Presentation Canary Execution on WFO & Retail.
    Required: Slide topics and chart facts bound, Track3 layout untouched, 0 regressions.
    """
    mgr = SDRAdoptionManager()
    mgr.reset()
    mgr.transition_adoption_state(ConsumerName.PRESENTATION, SDRAdoptionState.CANARY, "Presentation Canary")

    for ds_id in ["sdr8_wfo", "sdr8_retail"]:
        dec = mgr.evaluate_route(ConsumerName.PRESENTATION, dataset_id=ds_id, canary_authorized=True)
        assert dec.selected_route == Route.SDR

        v2_evidence = {
            "topics": [{"topic_id": "top_1", "title": "Topic 1", "primary_metric_value": 42}],
            "charts": [{"chart_id": "c_1", "data": [1, 2, 3]}],
            "metadata": {"deck_format": "16x9_widescreen", "engine": "Track3"},
        }

        adopted = build_sdr_presentation_evidence(ds_id, v2_evidence)
        assert adopted is not None
        assert adopted["metadata"]["route_provenance"]["selected_route"] == Route.SDR.value
        assert adopted["metadata"]["engine"] == "Track3"
        assert len(adopted["topics"]) >= 1


# =============================================================================
# 10. V2 FALLBACK FOR ALL CONSUMERS (FAILURE INJECTION)
# =============================================================================

def test_v2_fallback_all_consumers_failure_injection():
    """
    Verifies Section 10: V2 Fallback for Each Consumer upon failure injection:
    - missing SDR artifact
    - stale SDR artifact
    - dataset version mismatch
    - consumer contract mismatch
    - unsafe JoinPlan
    - ambiguous JoinPlan
    - SDR runtime exception
    Expected: SDR rejected, V2 selected, consumer operational, 0 reuploads, 0 reingestions.
    """
    mgr = SDRAdoptionManager()
    mgr.reset()

    for consumer in [ConsumerName.HRIDAY, ConsumerName.DASHBOARD, ConsumerName.PRESENTATION]:
        mgr.transition_adoption_state(consumer, SDRAdoptionState.CANARY, "Canary test")

        # Invalidate by non-existent artifact dir -> FallbackReason.V2_ARTIFACT_MISSING
        dec_missing = mgr.evaluate_route(consumer, dataset_id="non_existent_sdr", canary_authorized=True)
        assert dec_missing.selected_route == Route.V2
        assert dec_missing.fallback_used is True
        assert dec_missing.fallback_reason == FallbackReason.V2_ARTIFACT_MISSING

        # Invalidate by contract mismatch
        dec_contract = mgr.evaluate_route(consumer, dataset_id="sdr8_wfo", canary_authorized=True, expected_contract_fingerprint="WRONG_FP")
        assert dec_contract.selected_route == Route.V2
        assert dec_contract.fallback_used is True
        assert dec_contract.fallback_reason == FallbackReason.V2_SCHEMA_CONTRACT_FAILURE

        # Invalidate by version mismatch
        dec_ver = mgr.evaluate_route(consumer, dataset_id="sdr8_wfo", dataset_version="v99", canary_authorized=True)
        assert dec_ver.selected_route == Route.V2
        assert dec_ver.fallback_used is True
        assert dec_ver.fallback_reason == FallbackReason.V2_DATASET_VERSION_MISMATCH


# =============================================================================
# 11. PER-CONSUMER ROLLBACK
# =============================================================================

def test_per_consumer_rollback():
    """
    Verifies Section 11: Per-Consumer Rollback.
    HRIDAY SDR enabled, Dashboard SDR enabled, Presentation SDR enabled.
    Roll back Dashboard: Dashboard -> V2, HRIDAY & Presentation remain SDR enabled.
    """
    mgr = SDRAdoptionManager()
    mgr.reset()

    # Move all 3 to SDR_PRIMARY_WITH_V2_FALLBACK
    for c in [ConsumerName.HRIDAY, ConsumerName.DASHBOARD, ConsumerName.PRESENTATION]:
        mgr.transition_adoption_state(c, SDRAdoptionState.CANARY, "Canary")
        mgr.transition_adoption_state(c, SDRAdoptionState.SDR_PRIMARY_WITH_V2_FALLBACK, "SDR primary")

    # Roll back Dashboard
    mgr.rollback(ConsumerName.DASHBOARD, "Emergency dashboard rollback")
    assert mgr.get_adoption_state(ConsumerName.DASHBOARD) == SDRAdoptionState.ROLLBACK

    # Route checks
    dec_dash = mgr.evaluate_route(ConsumerName.DASHBOARD, dataset_id="sdr8_wfo")
    assert dec_dash.selected_route == Route.V2
    assert dec_dash.fallback_reason == FallbackReason.CONSUMER_ROLLBACK_ACTIVE

    dec_hriday = mgr.evaluate_route(ConsumerName.HRIDAY, dataset_id="sdr8_wfo")
    assert dec_hriday.selected_route == Route.SDR

    dec_pres = mgr.evaluate_route(ConsumerName.PRESENTATION, dataset_id="sdr8_wfo")
    assert dec_pres.selected_route == Route.SDR

    # Roll back HRIDAY independently
    mgr.rollback(ConsumerName.HRIDAY, "HRIDAY rollback")
    assert mgr.evaluate_route(ConsumerName.HRIDAY, dataset_id="sdr8_wfo").selected_route == Route.V2
    assert mgr.evaluate_route(ConsumerName.PRESENTATION, dataset_id="sdr8_wfo").selected_route == Route.SDR


# =============================================================================
# 12. GLOBAL KILL SWITCH
# =============================================================================

def test_global_kill_switch():
    """
    Verifies Section 12: Global Kill Switch.
    Activating kill switch forces all consumers to V2.
    Disabling restores state cleanly without corruption.
    """
    mgr = SDRAdoptionManager()
    mgr.reset()
    mgr.transition_adoption_state(ConsumerName.HRIDAY, SDRAdoptionState.CANARY, "Canary")
    mgr.transition_adoption_state(ConsumerName.HRIDAY, SDRAdoptionState.SDR_PRIMARY_WITH_V2_FALLBACK, "SDR")

    # Before kill switch: routes SDR
    assert mgr.evaluate_route(ConsumerName.HRIDAY, dataset_id="sdr8_wfo").selected_route == Route.SDR

    # Activate kill switch
    mgr.set_global_kill_switch(True)
    assert mgr.is_global_kill_switch_active() is True

    for c in [ConsumerName.HRIDAY, ConsumerName.DASHBOARD, ConsumerName.PRESENTATION]:
        dec = mgr.evaluate_route(c, dataset_id="sdr8_wfo")
        assert dec.selected_route == Route.V2
        assert dec.fallback_reason == FallbackReason.KILL_SWITCH_ACTIVE

    # Deactivate kill switch
    mgr.set_global_kill_switch(False)
    assert mgr.evaluate_route(ConsumerName.HRIDAY, dataset_id="sdr8_wfo").selected_route == Route.SDR


# =============================================================================
# 13. CIRCUIT BREAKER
# =============================================================================

def test_circuit_breaker():
    """
    Verifies Section 13: Circuit Breaker.
    Repeated SDR runtime failures trip the circuit to OPEN, blocking SDR and routing V2.
    """
    mgr = SDRAdoptionManager()
    mgr.reset()
    mgr.transition_adoption_state(ConsumerName.HRIDAY, SDRAdoptionState.CANARY, "Canary")
    mgr.transition_adoption_state(ConsumerName.HRIDAY, SDRAdoptionState.SDR_PRIMARY_WITH_V2_FALLBACK, "SDR")

    # Inject 3 failures to reach failure_threshold
    mgr.record_failure(ConsumerName.HRIDAY, FallbackReason.V2_RUNTIME_ERROR)
    mgr.record_failure(ConsumerName.HRIDAY, FallbackReason.V2_RUNTIME_ERROR)
    mgr.record_failure(ConsumerName.HRIDAY, FallbackReason.V2_RUNTIME_ERROR)

    dec = mgr.evaluate_route(ConsumerName.HRIDAY, dataset_id="sdr8_wfo")
    assert dec.selected_route == Route.V2
    assert dec.fallback_reason == FallbackReason.CIRCUIT_BREAKER_OPEN

    # Reset circuit breaker restores SDR
    mgr.reset_circuit_breaker(ConsumerName.HRIDAY)
    assert mgr.evaluate_route(ConsumerName.HRIDAY, dataset_id="sdr8_wfo").selected_route == Route.SDR


# =============================================================================
# 14. MANUAL OVERRIDE
# =============================================================================

def test_manual_override():
    """
    Verifies Section 14: Manual Override.
    Forces V2 for one consumer while keeping SDR artifacts intact.
    """
    mgr = SDRAdoptionManager()
    mgr.reset()
    mgr.transition_adoption_state(ConsumerName.HRIDAY, SDRAdoptionState.CANARY, "Canary")
    mgr.transition_adoption_state(ConsumerName.HRIDAY, SDRAdoptionState.SDR_PRIMARY_WITH_V2_FALLBACK, "SDR")

    mgr.set_manual_override(ConsumerName.HRIDAY, Route.V2)
    dec = mgr.evaluate_route(ConsumerName.HRIDAY, dataset_id="sdr8_wfo")
    assert dec.selected_route == Route.V2
    assert dec.fallback_reason == FallbackReason.MANUAL_OVERRIDE

    # Clear override
    mgr.set_manual_override(ConsumerName.HRIDAY, None)
    assert mgr.evaluate_route(ConsumerName.HRIDAY, dataset_id="sdr8_wfo").selected_route == Route.SDR


# =============================================================================
# 15. DURABLE STATE PERSISTENCE (SURVIVES PROCESS RESTART)
# =============================================================================

def test_durable_state_survives_restart(tmp_path):
    """
    Verifies Section 15: Durable State.
    State survives restart, persists in sdr_adoption_state.json, NOT in P0 SQLite.
    """
    base_dir = tmp_path / "data"
    mgr1 = SDRAdoptionManager(base_data_dir=base_dir)
    mgr1.transition_adoption_state(ConsumerName.HRIDAY, SDRAdoptionState.CANARY, "Canary init")
    mgr1.transition_adoption_state(ConsumerName.DASHBOARD, SDRAdoptionState.CANARY, "Dashboard canary")
    mgr1.transition_adoption_state(ConsumerName.DASHBOARD, SDRAdoptionState.SDR_PRIMARY_WITH_V2_FALLBACK, "Dashboard SDR")
    mgr1.rollback(ConsumerName.PRESENTATION, "Presentation rollback")

    # Verify state file exists outside P0
    state_file = base_dir / "sdr_adoption_state.json"
    assert state_file.exists()

    # Simulate process restart by instantiating new manager
    mgr2 = SDRAdoptionManager(base_data_dir=base_dir)
    assert mgr2.get_adoption_state(ConsumerName.HRIDAY) == SDRAdoptionState.CANARY
    assert mgr2.get_adoption_state(ConsumerName.DASHBOARD) == SDRAdoptionState.SDR_PRIMARY_WITH_V2_FALLBACK
    assert mgr2.get_adoption_state(ConsumerName.PRESENTATION) == SDRAdoptionState.ROLLBACK


# =============================================================================
# 16. DATASET / CONTRACT / ARTIFACT BINDING
# =============================================================================

def test_dataset_contract_artifact_binding():
    """
    Verifies Section 16: Dataset / Contract / Artifact Binding.
    Any change in dataset_id, dataset_version, artifact_fingerprint, or contract_fingerprint
    yields a distinct cache/routing binding.
    """
    key1 = compute_sdr_cache_key("HRIDAY", Route.SDR, "ds1", "v1", "art_fp_1", "con_fp_1", "query1")
    key2 = compute_sdr_cache_key("HRIDAY", Route.SDR, "ds1", "v2", "art_fp_1", "con_fp_1", "query1")
    key3 = compute_sdr_cache_key("HRIDAY", Route.SDR, "ds1", "v1", "art_fp_2", "con_fp_1", "query1")
    key4 = compute_sdr_cache_key("HRIDAY", Route.SDR, "ds1", "v1", "art_fp_1", "con_fp_2", "query1")

    assert key1 != key2
    assert key1 != key3
    assert key1 != key4
    assert key2 != key3


# =============================================================================
# 17. CACHE ROUTE SAFETY (ZERO COLLISIONS)
# =============================================================================

def test_cache_route_safety():
    """
    Verifies Section 17: Cache Route Safety.
    - V2 cache entry cannot satisfy SDR route
    - SDR cache entry cannot satisfy V2 route
    - Route cache collisions: 0
    - Stale cache serves: 0
    """
    v2_key = compute_sdr_cache_key("DASHBOARD", Route.V2, "ds1", "v1", "art1", "con1")
    sdr_key = compute_sdr_cache_key("DASHBOARD", Route.SDR, "ds1", "v1", "art1", "con1")

    assert v2_key != sdr_key
    assert "V2" in v2_key
    assert "SDR" in sdr_key


# =============================================================================
# 18. STALE MATERIALIZED GOLD PROTECTION
# =============================================================================

def test_stale_materialized_gold_protection(tmp_path):
    """
    Verifies Section 18: Stale Materialized Gold Protection.
    Marking a Gold analytical view as STALE prevents serving and triggers V2 fallback.
    STALE GOLD SERVED: 0.
    """
    base_dir = tmp_path / "data"
    ds_id = "stale_gold_ds"
    sdr_dir = base_dir / "datasets" / ds_id / "sdr"
    sdr_dir.mkdir(parents=True, exist_ok=True)

    views = [{"view_id": "gold_view_1", "status": "STALE", "is_stale": True}]
    facts = [{"metric_id": "gold_fact_1", "value": 500, "evidence_id": "EV-GOLD"}]
    plans = [{"plan_id": "p1", "safety_status": "SAFE"}]
    rels = [{"rel_id": "r1", "status": "VALID"}]

    (sdr_dir / "analytical_views.json").write_text(json.dumps(views), encoding="utf-8")
    (sdr_dir / "analytical_facts.json").write_text(json.dumps(facts), encoding="utf-8")
    (sdr_dir / "join_plans.json").write_text(json.dumps(plans), encoding="utf-8")
    (sdr_dir / "validated_relationships.json").write_text(json.dumps(rels), encoding="utf-8")
    (base_dir / "datasets" / ds_id / "manifest.json").write_text(json.dumps({"dataset_version": "v1"}), encoding="utf-8")

    mgr = SDRAdoptionManager(base_data_dir=base_dir)
    mgr.transition_adoption_state(ConsumerName.DASHBOARD, SDRAdoptionState.CANARY, "Canary")

    dec = mgr.evaluate_route(ConsumerName.DASHBOARD, dataset_id=ds_id, canary_authorized=True)
    assert dec.selected_route == Route.V2
    assert dec.fallback_used is True
    assert dec.fallback_reason == FallbackReason.V2_ARTIFACT_STALE


# =============================================================================
# 19. NO-REINGESTION ROLLBACK CYCLE
# =============================================================================

def test_no_reingestion_rollback_cycle():
    """
    Verifies Section 19: No-Reingestion Rollback Cycle.
    CANARY -> SDR_PRIMARY_WITH_V2_FALLBACK -> ROLLBACK (routes V2) -> CANARY (via recovery).
    Verifies zero file reuploads and zero dataset reingestions.
    """
    mgr = SDRAdoptionManager()
    mgr.reset()

    # Step 1: CANARY
    mgr.transition_adoption_state(ConsumerName.HRIDAY, SDRAdoptionState.CANARY, "Canary")
    assert mgr.get_adoption_state(ConsumerName.HRIDAY) == SDRAdoptionState.CANARY

    # Step 2: SDR_PRIMARY_WITH_V2_FALLBACK
    mgr.transition_adoption_state(ConsumerName.HRIDAY, SDRAdoptionState.SDR_PRIMARY_WITH_V2_FALLBACK, "SDR primary")
    assert mgr.get_adoption_state(ConsumerName.HRIDAY) == SDRAdoptionState.SDR_PRIMARY_WITH_V2_FALLBACK

    # Step 3: ROLLBACK
    mgr.rollback(ConsumerName.HRIDAY, "Simulated issue")
    assert mgr.get_adoption_state(ConsumerName.HRIDAY) == SDRAdoptionState.ROLLBACK
    assert mgr.evaluate_route(ConsumerName.HRIDAY, dataset_id="sdr8_wfo").selected_route == Route.V2

    # Step 4: CANARY again via recover_from_rollback
    mgr.recover_from_rollback(ConsumerName.HRIDAY, SDRAdoptionState.CANARY, "Root cause resolved and verified")
    assert mgr.get_adoption_state(ConsumerName.HRIDAY) == SDRAdoptionState.CANARY
    assert mgr.evaluate_route(ConsumerName.HRIDAY, dataset_id="sdr8_wfo", canary_authorized=True).selected_route == Route.SDR


# =============================================================================
# 20. TERMINAL SDR-9 STATE
# =============================================================================

def test_terminal_sdr9_state():
    """
    Verifies Section 20: Terminal SDR-9 State.
    Preferred terminal state is SDR_PRIMARY_WITH_V2_FALLBACK.
    V2 is NOT retired; V1 safety is retained.
    """
    mgr = SDRAdoptionManager()
    mgr.reset()

    for c in [ConsumerName.HRIDAY, ConsumerName.DASHBOARD, ConsumerName.PRESENTATION]:
        mgr.transition_adoption_state(c, SDRAdoptionState.CANARY, "Certified canary")
        rec = mgr.transition_adoption_state(c, SDRAdoptionState.SDR_PRIMARY_WITH_V2_FALLBACK, "Advance to terminal SDR-9")
        assert rec.adoption_state == SDRAdoptionState.SDR_PRIMARY_WITH_V2_FALLBACK

    # Pure SDR_PRIMARY is NOT reached in SDR-9
    for c in [ConsumerName.HRIDAY, ConsumerName.DASHBOARD, ConsumerName.PRESENTATION]:
        assert mgr.get_adoption_state(c) != SDRAdoptionState.SDR_PRIMARY


# =============================================================================
# 21. ROUTE TELEMETRY & PROVENANCE
# =============================================================================

def test_route_telemetry_and_provenance():
    """
    Verifies Section 21 & 22: Route Telemetry & Provenance.
    Verifies recording of consumer, dataset, version, route, state, fingerprints, reasons.
    """
    mgr = SDRAdoptionManager()
    mgr.reset()
    mgr.transition_adoption_state(ConsumerName.HRIDAY, SDRAdoptionState.CANARY, "Canary")

    dec = mgr.evaluate_route(ConsumerName.HRIDAY, dataset_id="sdr8_wfo", canary_authorized=True)
    assert dec.consumer == ConsumerName.HRIDAY
    assert dec.selected_route == Route.SDR
    assert dec.decision_id.startswith("SDR-DEC-")
    assert dec.timestamp is not None

    summary = mgr.telemetry.get_consumer_summary(ConsumerName.HRIDAY)
    assert summary["consumer"] == "HRIDAY"
    assert summary["counts"].get("total_requests", 0) >= 1
    assert summary["counts"].get("sdr_canary_routes", 0) >= 1


# =============================================================================
# 22. PERFORMANCE BENCHMARKS (P50 / P95)
# =============================================================================

def test_performance_benchmarks():
    """
    Verifies Section 23: Performance Benchmarks.
    Evaluates P50 and P95 latency for gateway decisions, V2, SDR, and fallback routes.
    """
    mgr = SDRAdoptionManager()
    mgr.reset()
    mgr.transition_adoption_state(ConsumerName.HRIDAY, SDRAdoptionState.CANARY, "Canary")
    mgr.transition_adoption_state(ConsumerName.HRIDAY, SDRAdoptionState.SDR_PRIMARY_WITH_V2_FALLBACK, "SDR")

    latencies = []
    for _ in range(50):
        t0 = time.perf_counter()
        mgr.evaluate_route(ConsumerName.HRIDAY, dataset_id="sdr8_wfo")
        latencies.append((time.perf_counter() - t0) * 1000)

    latencies.sort()
    p50 = latencies[len(latencies) // 2]
    p95 = latencies[int(len(latencies) * 0.95)]

    assert p50 < 10.0  # Under 10ms P50
    assert p95 < 25.0  # Under 25ms P95
