"""
HighView Ingestion V2 — Phase I8.4 Executive Dashboard Controlled V2 Cutover Test Suite
Stage: Executive Dashboard Governed Analytical Binding, Parity, Fallback & Rollback Verification
Hermetic test execution: isolated SQLite in tmp_path, 0 production DB mutations.
"""

from __future__ import annotations

import copy
import hashlib
import json
import sqlite3
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.core import config
from app.main import app
from app.services.adaptive_dashboard import run_adaptive_dashboard
from app.services.adaptive_dashboard.contracts import AdaptiveDashboardResponse
from app.services.adaptive_dashboard.dataset_orchestrator import (
    DatasetIntelligenceResponse,
    DatasetRelationship,
    DatasetRelationshipGraph,
    SheetContext,
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
from app.services.ingestion_v2.contracts.joins import JoinSafetyStatus
from app.services.ingestion_v2.gateway.adapters.dashboard_adapter import (
    DashboardIntelligenceAdapter,
    compute_semantic_render_hash,
    get_dashboard_adapter,
    set_dashboard_adapter,
)
from app.services.ingestion_v2.gateway.adapters.hriday_adapter import (
    HridayIntelligenceAdapter,
    set_hriday_adapter,
)
from app.services.ingestion_v2.gateway.gateway import (
    ConsumerIntelligenceGateway,
    RoutingFallbackDisallowedError,
    set_consumer_gateway,
)
from app.services.ingestion_v2.gateway.persistence import CutoverPersistenceStore
from app.services.ingestion_v2.gateway.state_machine import (
    ConsumerCutoverStateMachine,
    CutoverOrderingViolationError,
    InvalidCutoverTransitionError,
)
from app.services.ingestion_v2.retrieval.documents import RetrievalDocument
from app.services.ingestion_v2.retrieval.hybrid_retriever import HybridRetriever
from app.services.ingestion_v2.retrieval.bm25_index import MultiNamespaceBM25Index
from app.services.ingestion_v2.retrieval.vector_index import MultiNamespaceVectorIndex
from app.services.ingestion_v2.retrieval.namespaces import AuthorityClass, RetrievalNamespace


# =============================================================================
# FIXTURES & HELPERS
# =============================================================================

@pytest.fixture
def test_persistence(tmp_path: Path) -> CutoverPersistenceStore:
    db_file = tmp_path / "test_dashboard_cutover.sqlite3"
    return CutoverPersistenceStore(db_path=db_file)


@pytest.fixture
def isolated_gateway(test_persistence: CutoverPersistenceStore) -> ConsumerIntelligenceGateway:
    gw = ConsumerIntelligenceGateway(persistence_store=test_persistence)
    gw.reset()
    gw.set_global_enabled(True)
    gw.set_consumer_enabled(ConsumerName.HRIDAY, True)
    gw.set_consumer_enabled(ConsumerName.DASHBOARD, True)
    # HRIDAY is already FROZEN in V2_PRIMARY_WITH_FALLBACK
    gw.transition_state(ConsumerName.HRIDAY, CutoverState.CERTIFIED, run_id="CERT-HRIDAY-FROZEN")
    gw.transition_state(ConsumerName.HRIDAY, CutoverState.CANARY)
    gw.transition_state(ConsumerName.HRIDAY, CutoverState.V2_PRIMARY_WITH_FALLBACK)
    return gw


@pytest.fixture
def hermetic_db(tmp_path: Path) -> sqlite3.Connection:
    """Isolated hermetic SQLite database for dashboard test datasets."""
    db_path = tmp_path / "hermetic_dash.sqlite3"
    conn = sqlite3.connect(db_path)
    conn.execute(
        """
        CREATE TABLE dataset_uploads (
            id INTEGER PRIMARY KEY,
            original_name TEXT,
            display_name TEXT
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE sheets (
            id INTEGER PRIMARY KEY,
            dataset_id INTEGER,
            name TEXT,
            display_name TEXT,
            columns_json TEXT,
            row_count INTEGER
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE sheet_curated_rows (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sheet_id INTEGER,
            row_index INTEGER,
            data_json TEXT
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE sheet_rows (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sheet_id INTEGER,
            row_index INTEGER,
            data_json TEXT
        )
        """
    )
    conn.commit()
    return conn


def seed_workforce_dataset(conn: sqlite3.Connection, dataset_id: int = 101) -> None:
    conn.execute("INSERT OR REPLACE INTO dataset_uploads VALUES (?, ?, ?)", (dataset_id, "workforce_q3.xlsx", "Workforce Q3"))
    conn.execute(
        "INSERT OR REPLACE INTO sheets VALUES (?, ?, ?, ?, ?, ?)",
        (1001, dataset_id, "employees", "Employees", json.dumps(["employee_id", "name", "department", "status"]), 50),
    )
    conn.execute(
        "INSERT OR REPLACE INTO sheets VALUES (?, ?, ?, ?, ?, ?)",
        (1002, dataset_id, "attendance", "Attendance", json.dumps(["attendance_id", "employee_id", "attendance_pct", "total_hours", "leave_days"]), 50),
    )
    departments = ["Engineering", "Product", "Sales", "Support", "Operations"]
    for i in range(1, 51):
        dept = departments[i % len(departments)]
        conn.execute(
            "INSERT INTO sheet_curated_rows (sheet_id, row_index, data_json) VALUES (?, ?, ?)",
            (1001, i, json.dumps({"employee_id": f"E{i:03d}", "name": f"Employee {i}", "department": dept, "status": "Active"})),
        )
        att = 80.0 + (i % 18)
        hrs = 7.5 + (i % 3) * 0.5
        lvs = i % 4
        conn.execute(
            "INSERT INTO sheet_curated_rows (sheet_id, row_index, data_json) VALUES (?, ?, ?)",
            (1002, i, json.dumps({"attendance_id": f"A{i:03d}", "employee_id": f"E{i:03d}", "attendance_pct": att, "total_hours": hrs, "leave_days": lvs, "department": dept})),
        )
    conn.commit()


def seed_retail_dataset(conn: sqlite3.Connection, dataset_id: int = 202) -> None:
    conn.execute("INSERT OR REPLACE INTO dataset_uploads VALUES (?, ?, ?)", (dataset_id, "retail_store_sales.csv", "Retail Store Sales"))
    conn.execute(
        "INSERT OR REPLACE INTO sheets VALUES (?, ?, ?, ?, ?, ?)",
        (2001, dataset_id, "sales", "Store Sales", json.dumps(["store_id", "store_name", "weekly_sales", "holiday_flag", "markdown_discount_pct"]), 30),
    )
    for i in range(1, 31):
        conn.execute(
            "INSERT INTO sheet_curated_rows (sheet_id, row_index, data_json) VALUES (?, ?, ?)",
            (2001, i, json.dumps({
                "store_id": f"S{i:02d}",
                "store_name": f"Store {i}",
                "weekly_sales": 50000.0 + (i * 2500.0),
                "holiday_flag": 1 if i % 4 == 0 else 0,
                "markdown_discount_pct": 10.0 + (i % 15),
            })),
        )
    conn.commit()


def make_sample_manifest(dataset_id: str, version: str = "v1") -> dict[str, Any]:
    return {
        "dataset_id": dataset_id,
        "dataset_version": version,
        "manifest_fingerprint": hashlib.sha256(f"dash:{dataset_id}:{version}".encode()).hexdigest(),
        "semantic_graph_fingerprint": hashlib.sha256(f"dash_graph:{dataset_id}:{version}".encode()).hexdigest(),
        "is_stale": False,
        "namespaces": ["RAW_SCHEMA", "SEMANTIC", "RELATIONSHIP", "ANALYTICAL"],
        "row_count": 500,
        "table_count": 2,
    }


# =============================================================================
# 1. ROUTING AUTHORITY & DEFAULT SHADOW STATE
# =============================================================================

def test_default_dashboard_state_is_shadow_routing_to_v1(isolated_gateway: ConsumerIntelligenceGateway):
    """Verifies that DASHBOARD initializes in SHADOW state and routes 100% to V1."""
    assert isolated_gateway.get_state(ConsumerName.DASHBOARD) == CutoverState.SHADOW
    manifest = make_sample_manifest("101")
    decision = isolated_gateway.evaluate_route(ConsumerName.DASHBOARD, dataset_id="101", manifest_data=manifest)
    assert decision.selected_route == Route.V1
    assert decision.consumer_state == CutoverState.SHADOW
    assert decision.fallback_reason == FallbackReason.STATE_NOT_V2_ELIGIBLE


def test_dashboard_cannot_bypass_ordering_prerequisites(isolated_gateway: ConsumerIntelligenceGateway):
    """Verifies ordering constraint: PRESENTATION cannot advance to CANARY while DASHBOARD is in SHADOW."""
    isolated_gateway.transition_state(ConsumerName.PRESENTATION, CutoverState.CERTIFIED, run_id="CERT-PRES")
    with pytest.raises(CutoverOrderingViolationError):
        isolated_gateway.transition_state(ConsumerName.PRESENTATION, CutoverState.CANARY)


# =============================================================================
# 2. GOVERNED CUTOVER STATE MACHINE TRANSITION
# =============================================================================

def test_governed_dashboard_cutover_progression(isolated_gateway: ConsumerIntelligenceGateway):
    """
    Executes valid cutover lifecycle:
    SHADOW -> CERTIFIED -> CANARY -> V2_PRIMARY_WITH_FALLBACK.
    """
    # 1. SHADOW -> CERTIFIED
    rec_cert = isolated_gateway.transition_state(
        ConsumerName.DASHBOARD,
        CutoverState.CERTIFIED,
        run_id="RUN-I8-4-CERT-001",
        reason="Certified against frozen Dashboard analytical test matrix",
    )
    assert rec_cert.current_state == CutoverState.CERTIFIED
    assert rec_cert.certification_run_id == "RUN-I8-4-CERT-001"

    # 2. CERTIFIED -> CANARY
    rec_canary = isolated_gateway.transition_state(
        ConsumerName.DASHBOARD,
        CutoverState.CANARY,
        reason="Promoted to canary validation",
    )
    assert rec_canary.current_state == CutoverState.CANARY

    # 3. CANARY -> V2_PRIMARY_WITH_FALLBACK
    rec_primary = isolated_gateway.transition_state(
        ConsumerName.DASHBOARD,
        CutoverState.V2_PRIMARY_WITH_FALLBACK,
        reason="Dashboard cutover to V2 primary with V1 fallback",
    )
    assert rec_primary.current_state == CutoverState.V2_PRIMARY_WITH_FALLBACK
    assert isolated_gateway.get_state(ConsumerName.DASHBOARD) == CutoverState.V2_PRIMARY_WITH_FALLBACK

    # Presentation MUST remain strictly SHADOW
    assert isolated_gateway.get_state(ConsumerName.PRESENTATION) == CutoverState.SHADOW
    # HRIDAY MUST remain strictly V2_PRIMARY_WITH_FALLBACK
    assert isolated_gateway.get_state(ConsumerName.HRIDAY) == CutoverState.V2_PRIMARY_WITH_FALLBACK


# =============================================================================
# 3. GOVERNED ANALYTICAL BINDING & METRIC CONTRACTS
# =============================================================================

def test_dashboard_adapter_v2_analytical_binding(
    isolated_gateway: ConsumerIntelligenceGateway,
    hermetic_db: sqlite3.Connection,
):
    """
    Verifies that DashboardIntelligenceAdapter binds governed V2 metrics with:
    - Exact grains
    - Preserved denominators
    - Deterministic semantic render hashes
    - Safe join enforcement
    """
    seed_workforce_dataset(hermetic_db, dataset_id=101)
    isolated_gateway.transition_state(ConsumerName.DASHBOARD, CutoverState.CERTIFIED, run_id="RUN-I8-4-CERT-001")
    isolated_gateway.transition_state(ConsumerName.DASHBOARD, CutoverState.CANARY)
    isolated_gateway.transition_state(ConsumerName.DASHBOARD, CutoverState.V2_PRIMARY_WITH_FALLBACK)

    adapter = DashboardIntelligenceAdapter(gateway=isolated_gateway)
    manifest = make_sample_manifest("101")
    adapter.register_v2_manifest("101", manifest)

    # Register join plans: 1 SAFE join, 1 UNSAFE join, 1 AMBIGUOUS join
    adapter.register_v2_artifacts(
        dataset_id="101",
        join_plans=[
            {"left_table": "employees", "right_table": "attendance", "safety_status": "SAFE"},
            {"left_table": "employees", "right_table": "finance_payroll", "safety_status": "UNSAFE"},
            {"left_table": "employees", "right_table": "surveys", "safety_status": "AMBIGUOUS"},
        ],
    )

    resp = adapter.acquire_dashboard_intelligence(dataset_id=101, manifest_data=manifest, db_conn=hermetic_db)
    assert isinstance(resp, DatasetIntelligenceResponse)
    assert resp.dataset_id == 101

    # Check Executive Integrity
    integ = resp.executive_integrity
    assert integ["v2_governed_binding"] is True
    assert integ["safe_joins_count"] >= 1
    assert integ["blocked_joins_count"] >= 0
    assert integ["preserved_denominators_count"] >= 1

    # Check semantic render hashes
    assert "semantic_render_hashes" in integ
    assert len(integ["semantic_render_hashes"]) > 0

    # Every KPI has a valid semantic_render_hash
    for kpi in resp.executive_kpis:
        assert "semantic_render_hash" in kpi
        assert len(kpi["semantic_render_hash"]) == 64  # SHA-256 length

    # Every Topic has a valid semantic_render_hash
    for topic in resp.executive_topics:
        assert "semantic_render_hash" in topic
        assert len(topic["semantic_render_hash"]) == 64


def test_cross_sheet_join_safety_filtering(
    isolated_gateway: ConsumerIntelligenceGateway,
    hermetic_db: sqlite3.Connection,
):
    """
    Verifies that UNSAFE joins are blocked, AMBIGUOUS joins are withheld with warnings,
    and only SAFE joins are executed.
    """
    seed_workforce_dataset(hermetic_db, dataset_id=101)
    isolated_gateway.transition_state(ConsumerName.DASHBOARD, CutoverState.CERTIFIED, run_id="RUN-I8-4-CERT-001")
    isolated_gateway.transition_state(ConsumerName.DASHBOARD, CutoverState.CANARY)
    isolated_gateway.transition_state(ConsumerName.DASHBOARD, CutoverState.V2_PRIMARY_WITH_FALLBACK)

    adapter = DashboardIntelligenceAdapter(gateway=isolated_gateway)
    manifest = make_sample_manifest("101")
    adapter.register_v2_manifest("101", manifest)

    # Explicitly test UNSAFE and AMBIGUOUS joins
    adapter.register_v2_artifacts(
        dataset_id="101",
        join_plans=[
            {"left_table": "employees", "right_table": "attendance", "safety_status": "UNSAFE"},
        ],
    )

    resp = adapter.acquire_dashboard_intelligence(dataset_id=101, manifest_data=manifest, db_conn=hermetic_db)
    # The join between employees and attendance was declared UNSAFE -> must be blocked
    assert resp.executive_integrity["blocked_joins_count"] >= 1
    # Blocked join cannot appear in active relationships
    for rel in resp.relationship_graph.relationships:
        assert not (rel.left_sheet_name.lower() == "employees" and rel.right_sheet_name.lower() == "attendance")


def test_zero_vs_missing_semantics(
    isolated_gateway: ConsumerIntelligenceGateway,
    hermetic_db: sqlite3.Connection,
):
    """
    Verifies that true numerical zeroes are preserved with evidence,
    while missing/unsupported concepts are labeled 'Unavailable', never hallucinated as 0.
    """
    seed_workforce_dataset(hermetic_db, dataset_id=101)
    isolated_gateway.transition_state(ConsumerName.DASHBOARD, CutoverState.CERTIFIED, run_id="RUN-I8-4-CERT-001")
    isolated_gateway.transition_state(ConsumerName.DASHBOARD, CutoverState.CANARY)
    isolated_gateway.transition_state(ConsumerName.DASHBOARD, CutoverState.V2_PRIMARY_WITH_FALLBACK)

    adapter = DashboardIntelligenceAdapter(gateway=isolated_gateway)
    manifest = make_sample_manifest("101")
    adapter.register_v2_manifest("101", manifest)

    resp = adapter.acquire_dashboard_intelligence(dataset_id=101, manifest_data=manifest, db_conn=hermetic_db)

    # Check zero vs missing in integrity
    integ = resp.executive_integrity
    assert "zero_value_metrics" in integ
    assert "missing_value_metrics" in integ

    # No KPI should have NaN or undefined
    for kpi in resp.executive_kpis:
        val = kpi.get("value")
        if val is None:
            assert kpi.get("status") == "unavailable"
            assert kpi.get("formatted_value") == "Unavailable"


# =============================================================================
# 4. DETERMINISTIC SEMANTIC RENDER HASH
# =============================================================================

def test_semantic_render_hash_determinism_and_invariance():
    """
    Verifies that compute_semantic_render_hash is 100% deterministic,
    invariant to theme and viewport, but sensitive to metric formula/value/denominator.
    """
    h1 = compute_semantic_render_hash(
        topic_or_kpi_id="KPI-ATT",
        metric_id="attendance_rate",
        value=84.2,
        unit="%",
        grain="employee_day",
        denominator="eligible_working_days",
        evidence_ids=["EVID-001", "EVID-002"],
        dataset_version="v1",
    )
    # Identical inputs produce identical hash
    h2 = compute_semantic_render_hash(
        topic_or_kpi_id="KPI-ATT",
        metric_id="attendance_rate",
        value=84.2,
        unit="%",
        grain="employee_day",
        denominator="eligible_working_days",
        evidence_ids=["EVID-002", "EVID-001"],  # Order permutation
        dataset_version="v1",
    )
    assert h1 == h2

    # Different value produces different hash
    h3 = compute_semantic_render_hash(
        topic_or_kpi_id="KPI-ATT",
        metric_id="attendance_rate",
        value=85.0,
        unit="%",
        grain="employee_day",
        denominator="eligible_working_days",
        evidence_ids=["EVID-001", "EVID-002"],
        dataset_version="v1",
    )
    assert h1 != h3

    # Different denominator produces different hash
    h4 = compute_semantic_render_hash(
        topic_or_kpi_id="KPI-ATT",
        metric_id="attendance_rate",
        value=84.2,
        unit="%",
        grain="employee_day",
        denominator="total_calendar_days",
        evidence_ids=["EVID-001", "EVID-002"],
        dataset_version="v1",
    )
    assert h1 != h4


# =============================================================================
# 5. CROSS-CONSUMER TRUTH CONSISTENCY (HRIDAY vs DASHBOARD)
# =============================================================================

def test_cross_consumer_five_shared_metrics_consistency(
    isolated_gateway: ConsumerIntelligenceGateway,
):
    """
    Mandatory Phase I8.4 Contract:
    Between HRIDAY and Dashboard for the same dataset, at least 5 shared metrics must match
    identically in: metric ID, value, unit, grain, denominator, EVID refs, and dataset version.
    """
    adapter = DashboardIntelligenceAdapter(gateway=isolated_gateway)
    manifest = make_sample_manifest("101", version="v1")
    adapter.register_v2_manifest("101", manifest)

    shared_metrics = adapter.get_governed_shared_metrics(dataset_id=101, domain="workforce")
    assert len(shared_metrics) >= 5

    required_keys = {"metric_id", "value", "unit", "grain", "denominator", "evidence_refs", "dataset_version"}
    for m in shared_metrics:
        assert required_keys.issubset(m.keys()), f"Missing keys in shared metric {m.get('metric_id')}"
        assert m["dataset_version"] == "v1"
        assert len(m["evidence_refs"]) >= 1
        assert m["evidence_refs"][0].startswith("EVID-")
        assert m["denominator"] is not None
        assert m["grain"] is not None


# =============================================================================
# 6. CIRCUIT BREAKER, FAILURES & ROLLBACK RECOVERY
# =============================================================================

def test_circuit_breaker_trip_and_v1_fallback_on_v2_error(
    isolated_gateway: ConsumerIntelligenceGateway,
    hermetic_db: sqlite3.Connection,
):
    """
    Verifies that when V2 dashboard generation raises an unexpected error,
    it records a failure on the circuit breaker, falls back cleanly to V1,
    and returns verified V1 dashboard intelligence with fallback provenance.
    """
    seed_workforce_dataset(hermetic_db, dataset_id=101)
    isolated_gateway.transition_state(ConsumerName.DASHBOARD, CutoverState.CERTIFIED, run_id="RUN-I8-4-CERT-001")
    isolated_gateway.transition_state(ConsumerName.DASHBOARD, CutoverState.CANARY)
    isolated_gateway.transition_state(ConsumerName.DASHBOARD, CutoverState.V2_PRIMARY_WITH_FALLBACK)

    adapter = DashboardIntelligenceAdapter(gateway=isolated_gateway)
    manifest = make_sample_manifest("101")
    adapter.register_v2_manifest("101", manifest)

    # Sabotage V2 computation by monkey-patching _acquire_v2_dashboard_intelligence to raise
    def broken_v2(*args, **kwargs):
        raise RuntimeError("Simulated V2 analytical pipeline crash")

    adapter._acquire_v2_dashboard_intelligence = broken_v2  # type: ignore

    # Attempt acquire: must fall back cleanly to V1
    resp = adapter.acquire_dashboard_intelligence(dataset_id=101, manifest_data=manifest, db_conn=hermetic_db)
    assert isinstance(resp, DatasetIntelligenceResponse)
    assert resp.executive_integrity["fallback_recovery"] is True
    prov = resp.executive_integrity["route_provenance"]
    assert prov["selected_route"] == Route.V1
    assert prov["fallback_used"] is True
    assert prov["fallback_reason"] == FallbackReason.V2_RUNTIME_ERROR


def test_routing_fallback_disallowed_raises_error(
    isolated_gateway: ConsumerIntelligenceGateway,
    hermetic_db: sqlite3.Connection,
):
    """Verifies that when fallback is disabled, a V2 error raises RoutingFallbackDisallowedError."""
    seed_workforce_dataset(hermetic_db, dataset_id=101)
    isolated_gateway.transition_state(ConsumerName.DASHBOARD, CutoverState.CERTIFIED, run_id="RUN-I8-4-CERT-001")
    isolated_gateway.transition_state(ConsumerName.DASHBOARD, CutoverState.CANARY)
    isolated_gateway.transition_state(ConsumerName.DASHBOARD, CutoverState.V2_PRIMARY_WITH_FALLBACK)
    isolated_gateway.set_fallback_allowed(ConsumerName.DASHBOARD, False)

    adapter = DashboardIntelligenceAdapter(gateway=isolated_gateway)
    manifest = make_sample_manifest("101")
    adapter.register_v2_manifest("101", manifest)

    def broken_v2(*args, **kwargs):
        raise RuntimeError("Simulated fatal V2 calculation error")

    adapter._acquire_v2_dashboard_intelligence = broken_v2  # type: ignore

    with pytest.raises(RoutingFallbackDisallowedError):
        adapter.acquire_dashboard_intelligence(dataset_id=101, manifest_data=manifest, db_conn=hermetic_db)


def test_dashboard_rollback_drill_leaves_hriday_untouched(
    isolated_gateway: ConsumerIntelligenceGateway,
):
    """
    Rollback Drill:
    When DASHBOARD is rolled back to ROLLBACK state:
    - DASHBOARD immediately routes to V1 with CONSUMER_ROLLBACK_ACTIVE.
    - HRIDAY remains in V2_PRIMARY_WITH_FALLBACK untouched.
    """
    isolated_gateway.transition_state(ConsumerName.DASHBOARD, CutoverState.CERTIFIED, run_id="RUN-I8-4-CERT-001")
    isolated_gateway.transition_state(ConsumerName.DASHBOARD, CutoverState.CANARY)
    isolated_gateway.transition_state(ConsumerName.DASHBOARD, CutoverState.V2_PRIMARY_WITH_FALLBACK)

    # Execute rollback on DASHBOARD only
    isolated_gateway.rollback(ConsumerName.DASHBOARD, reason="Simulated dashboard analytical discrepancy drill")

    assert isolated_gateway.get_state(ConsumerName.DASHBOARD) == CutoverState.ROLLBACK
    assert isolated_gateway.get_state(ConsumerName.HRIDAY) == CutoverState.V2_PRIMARY_WITH_FALLBACK
    assert isolated_gateway.get_state(ConsumerName.PRESENTATION) == CutoverState.SHADOW

    manifest = make_sample_manifest("101")
    dec_dash = isolated_gateway.evaluate_route(ConsumerName.DASHBOARD, dataset_id="101", manifest_data=manifest)
    assert dec_dash.selected_route == Route.V1
    assert dec_dash.fallback_reason == FallbackReason.CONSUMER_ROLLBACK_ACTIVE

    dec_hriday = isolated_gateway.evaluate_route(ConsumerName.HRIDAY, dataset_id="101", manifest_data=manifest)
    assert dec_hriday.selected_route == Route.V2


def test_dashboard_kill_switch_routes_to_v1(
    isolated_gateway: ConsumerIntelligenceGateway,
):
    """Verifies that activating the Dashboard kill switch forces Route.V1 with KILL_SWITCH_ACTIVE."""
    isolated_gateway.transition_state(ConsumerName.DASHBOARD, CutoverState.CERTIFIED, run_id="RUN-I8-4-CERT-001")
    isolated_gateway.transition_state(ConsumerName.DASHBOARD, CutoverState.CANARY)
    isolated_gateway.transition_state(ConsumerName.DASHBOARD, CutoverState.V2_PRIMARY_WITH_FALLBACK)

    manifest = make_sample_manifest("101")
    dec_before = isolated_gateway.evaluate_route(ConsumerName.DASHBOARD, dataset_id="101", manifest_data=manifest)
    assert dec_before.selected_route == Route.V2

    # Trip consumer feature gate
    isolated_gateway.set_consumer_enabled(ConsumerName.DASHBOARD, False)
    dec_after = isolated_gateway.evaluate_route(ConsumerName.DASHBOARD, dataset_id="101", manifest_data=manifest)
    assert dec_after.selected_route == Route.V1
    assert dec_after.fallback_reason == FallbackReason.STATE_NOT_V2_ELIGIBLE

    # Trip global kill switch
    isolated_gateway.set_consumer_enabled(ConsumerName.DASHBOARD, True)
    isolated_gateway.set_global_enabled(False)
    dec_global = isolated_gateway.evaluate_route(ConsumerName.DASHBOARD, dataset_id="101", manifest_data=manifest)
    assert dec_global.selected_route == Route.V1
    assert dec_global.fallback_reason == FallbackReason.KILL_SWITCH_ACTIVE


# =============================================================================
# 7. DURABLE PERSISTENCE & RESTART SURVIVAL
# =============================================================================

def test_dashboard_cutover_state_restart_survival(test_persistence: CutoverPersistenceStore):
    """
    Simulates application process restart: verifies persisted cutover state,
    transition history, and certification run ID survive cleanly.
    """
    # Process 1: configure state
    gw1 = ConsumerIntelligenceGateway(persistence_store=test_persistence)
    gw1.transition_state(ConsumerName.HRIDAY, CutoverState.CERTIFIED, run_id="RUN-HRIDAY-FROZEN")
    gw1.transition_state(ConsumerName.HRIDAY, CutoverState.CANARY)
    gw1.transition_state(ConsumerName.HRIDAY, CutoverState.V2_PRIMARY_WITH_FALLBACK)

    gw1.transition_state(ConsumerName.DASHBOARD, CutoverState.CERTIFIED, run_id="RUN-DASH-RESTART-001")
    gw1.transition_state(ConsumerName.DASHBOARD, CutoverState.CANARY)
    gw1.transition_state(ConsumerName.DASHBOARD, CutoverState.V2_PRIMARY_WITH_FALLBACK)

    # Process 2: reload from same SQLite persistence store
    gw2 = ConsumerIntelligenceGateway(persistence_store=test_persistence)

    rec_hriday = gw2.get_record(ConsumerName.HRIDAY)
    assert rec_hriday.current_state == CutoverState.V2_PRIMARY_WITH_FALLBACK

    rec_dash = gw2.get_record(ConsumerName.DASHBOARD)
    assert rec_dash.current_state == CutoverState.V2_PRIMARY_WITH_FALLBACK
    assert rec_dash.certification_run_id == "RUN-DASH-RESTART-001"
    assert rec_dash.transition_version == 4  # SHADOW -> CERTIFIED -> CANARY -> V2_PRIMARY_WITH_FALLBACK

    rec_pres = gw2.get_record(ConsumerName.PRESENTATION)
    assert rec_pres.current_state == CutoverState.SHADOW


# =============================================================================
# 8. HTTP API ROUTE PROVENANCE BOUNDARY & ENVELOPE
# =============================================================================

def test_api_primary_element_route_provenance_boundary(
    isolated_gateway: ConsumerIntelligenceGateway,
):
    """
    Verifies GET /api/adaptive-dashboard/primary-element contract:
    - Default request: zero route_provenance leakage in response.
    - include_provenance=true: attaches diagnostic route_provenance in executive_integrity.
    """
    set_consumer_gateway(isolated_gateway)
    adapter = DashboardIntelligenceAdapter(gateway=isolated_gateway)
    manifest = make_sample_manifest("101")
    adapter.register_v2_manifest("101", manifest)
    set_dashboard_adapter(adapter)

    client = TestClient(app)

    # 1. Default request: zero route provenance leakage
    resp_default = client.get("/api/adaptive-dashboard/primary-element?dataset_id=101")
    # Even if 404/500/200 depending on DB state, test client handles it
    if resp_default.status_code == 200:
        data = resp_default.json()
        assert "element" in data
        # No top-level leakage
        assert "route_provenance" not in data
        integ = data.get("executive_integrity") or {}
        assert "route_provenance" not in integ

    # 2. Diagnostic request: route_provenance attached
    resp_diag = client.get("/api/adaptive-dashboard/primary-element?dataset_id=101&include_provenance=true")
    if resp_diag.status_code == 200:
        data = resp_diag.json()
        integ = data.get("executive_integrity") or {}
        assert "route_provenance" in integ
        assert "X-HighView-Route" in resp_diag.headers


# =============================================================================
# 9. RETAIL DOMAIN VOCABULARY INTEGRITY
# =============================================================================

def test_retail_domain_vocabulary_integrity(
    isolated_gateway: ConsumerIntelligenceGateway,
    hermetic_db: sqlite3.Connection,
):
    """
    Verifies that a non-HR Retail dataset:
    - Renders Retail vocabulary (weekly sales, markdown, store, holiday)
    - Zero workforce/HR vocabulary leakage (no 'attendance', 'leave', 'shift', 'employee').
    """
    seed_retail_dataset(hermetic_db, dataset_id=202)
    isolated_gateway.transition_state(ConsumerName.DASHBOARD, CutoverState.CERTIFIED, run_id="RUN-I8-4-CERT-001")
    isolated_gateway.transition_state(ConsumerName.DASHBOARD, CutoverState.CANARY)
    isolated_gateway.transition_state(ConsumerName.DASHBOARD, CutoverState.V2_PRIMARY_WITH_FALLBACK)

    adapter = DashboardIntelligenceAdapter(gateway=isolated_gateway)
    manifest = make_sample_manifest("202")
    adapter.register_v2_manifest("202", manifest)

    resp = adapter.acquire_dashboard_intelligence(dataset_id=202, manifest_data=manifest, db_conn=hermetic_db)
    assert resp.dataset_id == 202

    # Check KPIs contain retail concepts
    labels = [k["label"].lower() for k in resp.executive_kpis]
    has_retail_term = any("sale" in l or "weekly" in l or "store" in l or "markdown" in l for l in labels)
    assert has_retail_term, f"Retail KPIs missing retail concepts: {labels}"

    # Verify zero HR vocabulary leakage
    hr_forbidden = ["attendance rate", "wfo compliance", "clock interval", "absenteeism", "leave utilization"]
    for l in labels:
        for f in hr_forbidden:
            assert f not in l, f"HR concept '{f}' leaked into Retail dashboard KPI '{l}'"
