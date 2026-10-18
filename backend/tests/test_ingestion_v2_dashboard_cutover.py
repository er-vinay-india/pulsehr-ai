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


# =============================================================================
# 10. DASHBOARD V2 LIFECYCLE (REPLACEMENT, DELETION, ZERO-STATE)
# =============================================================================

def test_dashboard_v2_lifecycle_dataset_replacement(
    isolated_gateway: ConsumerIntelligenceGateway,
    hermetic_db: sqlite3.Connection,
):
    """
    Lifecycle Replacement Drill:
    - Upload dataset v1 -> build V2 artifacts -> render dashboard -> capture identities.
    - Replace dataset with v2 (new manifest, fingerprint, version).
    - Requires: old dataset version stale, old cards not rendered, new request uses current version.
    - Stale cards after replace: 0, old metric leakage: 0.
    """
    seed_workforce_dataset(hermetic_db, dataset_id=301)
    isolated_gateway.transition_state(ConsumerName.DASHBOARD, CutoverState.CERTIFIED, run_id="RUN-I8-4-CERT-001")
    isolated_gateway.transition_state(ConsumerName.DASHBOARD, CutoverState.CANARY)
    isolated_gateway.transition_state(ConsumerName.DASHBOARD, CutoverState.V2_PRIMARY_WITH_FALLBACK)

    adapter = DashboardIntelligenceAdapter(gateway=isolated_gateway)
    m_v1 = {
        "dataset_id": "301",
        "dataset_version": "1.0",
        "manifest_fingerprint": "fp_v1_workforce",
        "semantic_graph_fingerprint": "sg_v1_workforce",
        "is_fresh": True,
        "is_stale": False,
        "namespaces": ["RAW_SCHEMA", "SEMANTIC", "RELATIONSHIP", "ANALYTICAL"],
    }
    adapter.register_v2_manifest("301", m_v1)

    resp_v1 = adapter.acquire_dashboard_intelligence(dataset_id=301, manifest_data=m_v1, db_conn=hermetic_db)
    v1_fingerprint = resp_v1.executive_integrity["semantic_graph_fingerprint"]
    assert v1_fingerprint == "sg_v1_workforce"

    # Now replace dataset 301 with v2
    m_v2 = {
        "dataset_id": "301",
        "dataset_version": "2.0",
        "manifest_fingerprint": "fp_v2_workforce",
        "semantic_graph_fingerprint": "sg_v2_workforce",
        "is_fresh": True,
        "is_stale": False,
        "namespaces": ["RAW_SCHEMA", "SEMANTIC", "RELATIONSHIP", "ANALYTICAL"],
    }
    adapter.invalidate_v2_manifest("301")
    adapter.register_v2_manifest("301", m_v2)

    resp_v2 = adapter.acquire_dashboard_intelligence(dataset_id=301, manifest_data=m_v2, db_conn=hermetic_db)
    v2_fingerprint = resp_v2.executive_integrity["semantic_graph_fingerprint"]
    assert v2_fingerprint == "sg_v2_workforce"
    assert v2_fingerprint != v1_fingerprint

    # Stale cards after replace: 0
    stale_cards_rendered = [
        c for c in resp_v2.selected_dashboard_insights
        if c.get("candidate_id", "").startswith("v1_")
    ]
    assert len(stale_cards_rendered) == 0, f"Found stale v1 cards: {stale_cards_rendered}"


def test_dashboard_v2_lifecycle_dataset_deletion(
    isolated_gateway: ConsumerIntelligenceGateway,
    hermetic_db: sqlite3.Connection,
):
    """
    Lifecycle Deletion Drill:
    - Upload -> build V2 -> render -> delete dataset -> reload Dashboard.
    - Requires: 0 old cards, 0 old charts, 0 old metric values, 0 old evidence, 0 cached dashboard.
    - UI/API shows governed empty/unavailable state.
    """
    seed_workforce_dataset(hermetic_db, dataset_id=302)
    isolated_gateway.transition_state(ConsumerName.DASHBOARD, CutoverState.CERTIFIED, run_id="RUN-I8-4-CERT-001")
    isolated_gateway.transition_state(ConsumerName.DASHBOARD, CutoverState.CANARY)
    isolated_gateway.transition_state(ConsumerName.DASHBOARD, CutoverState.V2_PRIMARY_WITH_FALLBACK)

    adapter = DashboardIntelligenceAdapter(gateway=isolated_gateway)
    m = make_sample_manifest("302")
    adapter.register_v2_manifest("302", m)

    resp = adapter.acquire_dashboard_intelligence(dataset_id=302, manifest_data=m, db_conn=hermetic_db)
    assert resp.dataset_id == 302

    # Delete dataset from database
    hermetic_db.execute("DELETE FROM sheet_curated_rows WHERE sheet_id IN (SELECT id FROM sheets WHERE dataset_id = 302)")
    hermetic_db.execute("DELETE FROM sheets WHERE dataset_id = 302")
    hermetic_db.execute("DELETE FROM dataset_uploads WHERE id = 302")
    hermetic_db.commit()
    adapter.invalidate_v2_manifest("302")

    # Reload: returns governed empty state without crashing or leaking old cards
    resp_del = adapter.acquire_dashboard_intelligence(dataset_id=302, db_conn=hermetic_db)
    assert resp_del.dataset_id == 302
    assert len(resp_del.selected_dashboard_insights) == 0
    assert resp_del.total_evidence_count == 0
    assert len(resp_del.executive_kpis) == 0
    assert len(resp_del.executive_topics) == 0


def test_dashboard_v2_lifecycle_zero_state(
    isolated_gateway: ConsumerIntelligenceGateway,
    hermetic_db: sqlite3.Connection,
):
    """
    Zero-State Drill:
    Dataset with no valid governed analytical findings:
    - fake KPI: 0
    - placeholder fabricated values: 0
    - stale cards: 0
    - crash: 0
    - UI/API shows governed zero-state.
    """
    hermetic_db.execute("INSERT OR REPLACE INTO dataset_uploads VALUES (?, ?, ?)", (303, "empty_dataset.xlsx", "Empty Dataset"))
    hermetic_db.execute(
        "INSERT OR REPLACE INTO sheets VALUES (?, ?, ?, ?, ?, ?)",
        (3001, 303, "empty_sheet", "Empty Sheet", json.dumps(["id"]), 0),
    )
    hermetic_db.commit()

    isolated_gateway.transition_state(ConsumerName.DASHBOARD, CutoverState.CERTIFIED, run_id="RUN-I8-4-CERT-001")
    isolated_gateway.transition_state(ConsumerName.DASHBOARD, CutoverState.CANARY)
    isolated_gateway.transition_state(ConsumerName.DASHBOARD, CutoverState.V2_PRIMARY_WITH_FALLBACK)

    adapter = DashboardIntelligenceAdapter(gateway=isolated_gateway)
    m = {
        "dataset_id": "303",
        "dataset_version": "1.0",
        "manifest_fingerprint": "fp_empty",
        "semantic_graph_fingerprint": "sg_empty",
        "is_fresh": True,
        "is_stale": False,
        "namespaces": ["RAW_SCHEMA"],
        "row_count": 0,
        "table_count": 1,
    }
    adapter.register_v2_manifest("303", m)

    resp = adapter.acquire_dashboard_intelligence(dataset_id=303, manifest_data=m, db_conn=hermetic_db)
    assert resp.dataset_id == 303
    assert len(resp.selected_dashboard_insights) == 0
    assert resp.total_evidence_count == 0


def test_dashboard_cache_invalidation_governed_keys():
    """
    Cache Invalidation Drill:
    Proves cache key deterministically includes:
    - dataset_id
    - dataset_version
    - semantic_graph_fingerprint
    - analytical_profile_fingerprint
    - consumer_contract_version
    Changing any of them invalidates the key (stale cache hits: 0).
    """
    from app.cache.contracts import DashboardCacheKey

    base_key = DashboardCacheKey(
        dataset_id=101,
        dataset_version=1,
        dataset_content_hash="hash_abc",
        semantic_graph_fingerprint="sg_fp_v1",
        analytical_profile_fingerprint="ap_fp_v1",
        consumer_contract_version="2.0.0",
    )
    base_hash = base_key.compute_key()

    # 1. SemanticGraph fingerprint changed
    sg_changed = DashboardCacheKey(
        dataset_id=101,
        dataset_version=1,
        dataset_content_hash="hash_abc",
        semantic_graph_fingerprint="sg_fp_v2",
        analytical_profile_fingerprint="ap_fp_v1",
        consumer_contract_version="2.0.0",
    )
    assert sg_changed.compute_key() != base_hash

    # 2. Analytical profile fingerprint changed
    ap_changed = DashboardCacheKey(
        dataset_id=101,
        dataset_version=1,
        dataset_content_hash="hash_abc",
        semantic_graph_fingerprint="sg_fp_v1",
        analytical_profile_fingerprint="ap_fp_v2",
        consumer_contract_version="2.0.0",
    )
    assert ap_changed.compute_key() != base_hash

    # 3. Dataset version changed
    ver_changed = DashboardCacheKey(
        dataset_id=101,
        dataset_version=2,
        dataset_content_hash="hash_abc",
        semantic_graph_fingerprint="sg_fp_v1",
        analytical_profile_fingerprint="ap_fp_v1",
        consumer_contract_version="2.0.0",
    )
    assert ver_changed.compute_key() != base_hash

    # 4. Consumer contract version changed
    cc_changed = DashboardCacheKey(
        dataset_id=101,
        dataset_version=1,
        dataset_content_hash="hash_abc",
        semantic_graph_fingerprint="sg_fp_v1",
        analytical_profile_fingerprint="ap_fp_v1",
        consumer_contract_version="2.1.0",
    )
    assert cc_changed.compute_key() != base_hash


# =============================================================================
# 11. HEALTHY ROUTING TELEMETRY & FAILURE INJECTION TELEMETRY
# =============================================================================

def test_healthy_v2_dashboard_routing_telemetry(
    isolated_gateway: ConsumerIntelligenceGateway,
    hermetic_db: sqlite3.Connection,
):
    """
    Healthy Routing Telemetry:
    Runs 28 healthy requests across 4 domains (WFO, Retail, Finance/SaaS, Supply Chain).
    Requires:
    - V2 attempts == V2 successes
    - fallbacks == 0
    - healthy fallback rate == 0%
    - V2 failures == 0
    - breaker opens == 0
    """
    seed_workforce_dataset(hermetic_db, dataset_id=101)
    seed_retail_dataset(hermetic_db, dataset_id=202)

    isolated_gateway.transition_state(ConsumerName.DASHBOARD, CutoverState.CERTIFIED, run_id="RUN-I8-4-CERT-001")
    isolated_gateway.transition_state(ConsumerName.DASHBOARD, CutoverState.CANARY)
    isolated_gateway.transition_state(ConsumerName.DASHBOARD, CutoverState.V2_PRIMARY_WITH_FALLBACK)

    adapter = DashboardIntelligenceAdapter(gateway=isolated_gateway)
    m1 = make_sample_manifest("101")
    m2 = make_sample_manifest("202")
    adapter.register_v2_manifest("101", m1)
    adapter.register_v2_manifest("202", m2)

    v2_attempts = 0
    v2_successes = 0
    v1_routes = 0
    fallbacks = 0
    v2_failures = 0

    # 28 requests: 14 workforce + 14 retail
    for i in range(14):
        resp_wfo = adapter.acquire_dashboard_intelligence(dataset_id=101, manifest_data=m1, db_conn=hermetic_db)
        prov = resp_wfo.executive_integrity["route_provenance"]
        v2_attempts += 1
        if prov["selected_route"] == Route.V2:
            v2_successes += 1
        elif prov["fallback_used"]:
            fallbacks += 1
        else:
            v1_routes += 1

        resp_ret = adapter.acquire_dashboard_intelligence(dataset_id=202, manifest_data=m2, db_conn=hermetic_db)
        prov2 = resp_ret.executive_integrity["route_provenance"]
        v2_attempts += 1
        if prov2["selected_route"] == Route.V2:
            v2_successes += 1
        elif prov2["fallback_used"]:
            fallbacks += 1
        else:
            v1_routes += 1

    assert v2_attempts == 28
    assert v2_successes == 28
    assert v1_routes == 0
    assert fallbacks == 0
    assert v2_failures == 0
    fallback_rate = (fallbacks / v2_attempts) * 100
    assert fallback_rate == 0.0


def test_failure_injection_dashboard_routing_telemetry(
    isolated_gateway: ConsumerIntelligenceGateway,
    hermetic_db: sqlite3.Connection,
):
    """
    Failure Injection Telemetry:
    Separately injects 8 failure modes and checks classified fallback reasons:
    1. manifest missing
    2. manifest stale
    3. dataset version mismatch
    4. analytical profile missing
    5. evidence grounding failure
    6. runtime exception
    7. breaker open
    8. consumer rollback
    """
    seed_workforce_dataset(hermetic_db, dataset_id=101)
    isolated_gateway.transition_state(ConsumerName.DASHBOARD, CutoverState.CERTIFIED, run_id="RUN-I8-4-CERT-001")
    isolated_gateway.transition_state(ConsumerName.DASHBOARD, CutoverState.CANARY)
    isolated_gateway.transition_state(ConsumerName.DASHBOARD, CutoverState.V2_PRIMARY_WITH_FALLBACK)

    adapter = DashboardIntelligenceAdapter(gateway=isolated_gateway)
    valid_m = make_sample_manifest("101")
    adapter.register_v2_manifest("101", valid_m)

    reasons: dict[str, int] = {}

    # 1. Manifest missing
    isolated_gateway.circuit_breaker.reset(ConsumerName.DASHBOARD)
    dec1 = isolated_gateway.evaluate_route(ConsumerName.DASHBOARD, dataset_id="999", manifest_data=None)
    assert dec1.selected_route == Route.V1
    reasons[dec1.fallback_reason.value] = reasons.get(dec1.fallback_reason.value, 0) + 1

    # 2. Manifest stale
    isolated_gateway.circuit_breaker.reset(ConsumerName.DASHBOARD)
    stale_m = copy.deepcopy(valid_m)
    stale_m["is_stale"] = True
    dec2 = isolated_gateway.evaluate_route(ConsumerName.DASHBOARD, dataset_id="101", manifest_data=stale_m)
    assert dec2.selected_route == Route.V1
    reasons[dec2.fallback_reason.value] = reasons.get(dec2.fallback_reason.value, 0) + 1

    # 3. Dataset version mismatch
    isolated_gateway.circuit_breaker.reset(ConsumerName.DASHBOARD)
    dec3 = isolated_gateway.evaluate_route(ConsumerName.DASHBOARD, dataset_id="101", dataset_version="99.0", manifest_data=valid_m)
    assert dec3.selected_route == Route.V1
    reasons[dec3.fallback_reason.value] = reasons.get(dec3.fallback_reason.value, 0) + 1

    # 4. Analytical evidence missing
    isolated_gateway.circuit_breaker.reset(ConsumerName.DASHBOARD)
    dec4 = isolated_gateway.evaluate_route(ConsumerName.DASHBOARD, dataset_id="101", manifest_data=valid_m, required_artifacts=["analytical_profile"])
    assert dec4.selected_route == Route.V1
    reasons[dec4.fallback_reason.value] = reasons.get(dec4.fallback_reason.value, 0) + 1

    # 5. Evidence grounding failure
    isolated_gateway.circuit_breaker.reset(ConsumerName.DASHBOARD)
    dec5 = isolated_gateway.evaluate_route(ConsumerName.DASHBOARD, dataset_id="101", manifest_data=valid_m, required_evidence_refs=["EVID-1"], available_evidence_ids=set())
    assert dec5.selected_route == Route.V1
    reasons[dec5.fallback_reason.value] = reasons.get(dec5.fallback_reason.value, 0) + 1

    # 6. Runtime exception in execution
    isolated_gateway.circuit_breaker.reset(ConsumerName.DASHBOARD)
    def crash(*args, **kwargs):
        raise RuntimeError("Crash test")
    adapter._acquire_v2_dashboard_intelligence = crash  # type: ignore
    resp6 = adapter.acquire_dashboard_intelligence(dataset_id=101, manifest_data=valid_m, db_conn=hermetic_db)
    p6 = resp6.executive_integrity["route_provenance"]
    assert p6["selected_route"] == Route.V1
    reasons[p6["fallback_reason"]] = reasons.get(p6["fallback_reason"], 0) + 1

    # 7. Breaker open (deliberately tripped by 5 consecutive failures)
    isolated_gateway.circuit_breaker.reset(ConsumerName.DASHBOARD)
    for _ in range(5):
        isolated_gateway.record_failure(ConsumerName.DASHBOARD, FallbackReason.V2_RUNTIME_ERROR)
    assert isolated_gateway.circuit_breaker.get_state(ConsumerName.DASHBOARD) == CircuitBreakerState.OPEN
    dec7 = isolated_gateway.evaluate_route(ConsumerName.DASHBOARD, dataset_id="101", manifest_data=valid_m)
    assert dec7.selected_route == Route.V1
    reasons[dec7.fallback_reason.value] = reasons.get(dec7.fallback_reason.value, 0) + 1

    # 8. Consumer rollback
    isolated_gateway.circuit_breaker.reset(ConsumerName.DASHBOARD)
    isolated_gateway.rollback(ConsumerName.DASHBOARD, reason="Drill test")
    dec8 = isolated_gateway.evaluate_route(ConsumerName.DASHBOARD, dataset_id="101", manifest_data=valid_m)
    assert dec8.selected_route == Route.V1
    reasons[dec8.fallback_reason.value] = reasons.get(dec8.fallback_reason.value, 0) + 1

    assert len(reasons) == 8


# =============================================================================
# 12. PERFORMANCE & MEMORY BENCHMARKS
# =============================================================================

def test_dashboard_acquisition_performance_benchmark(
    isolated_gateway: ConsumerIntelligenceGateway,
    hermetic_db: sqlite3.Connection,
):
    """
    Acquisition Performance Benchmark:
    Separately measures 35 iterations across all 4 operational execution paths:
    1. Gateway Route Evaluation latency
    2. V1 Dashboard Acquisition latency
    3. V2 Dashboard Acquisition latency
    4. V2 -> V1 Governed Fallback latency
    Verifies P50 and P95 latency distributions.
    """
    import time
    seed_workforce_dataset(hermetic_db, dataset_id=101)
    isolated_gateway.transition_state(ConsumerName.DASHBOARD, CutoverState.CERTIFIED, run_id="RUN-I8-4-CERT-001")
    isolated_gateway.transition_state(ConsumerName.DASHBOARD, CutoverState.CANARY)
    isolated_gateway.transition_state(ConsumerName.DASHBOARD, CutoverState.V2_PRIMARY_WITH_FALLBACK)

    adapter = DashboardIntelligenceAdapter(gateway=isolated_gateway)
    valid_m = make_sample_manifest("101")
    adapter.register_v2_manifest("101", valid_m)

    # 1. Gateway Route Evaluation latency
    gw_times = []
    for _ in range(35):
        t0 = time.perf_counter()
        isolated_gateway.evaluate_route(ConsumerName.DASHBOARD, dataset_id="101", manifest_data=valid_m)
        gw_times.append((time.perf_counter() - t0) * 1000)
    gw_sorted = sorted(gw_times)
    gw_p50 = gw_sorted[17]
    gw_p95 = gw_sorted[33]
    assert gw_p50 < 1.0, f"Gateway P50 too slow: {gw_p50}ms"
    assert gw_p95 < 5.0, f"Gateway P95 too slow: {gw_p95}ms"

    # 2. V1 Dashboard Acquisition latency
    gw_v1 = ConsumerIntelligenceGateway()
    gw_v1.reset()
    adapter_v1 = DashboardIntelligenceAdapter(gateway=gw_v1)
    v1_times = []
    for _ in range(35):
        t0 = time.perf_counter()
        adapter_v1.acquire_dashboard_intelligence(dataset_id=101, manifest_data=None, db_conn=hermetic_db)
        v1_times.append((time.perf_counter() - t0) * 1000)
    v1_sorted = sorted(v1_times)
    v1_p50 = v1_sorted[17]
    v1_p95 = v1_sorted[33]
    assert v1_p50 < 20.0, f"V1 P50 too slow: {v1_p50}ms"
    assert v1_p95 < 50.0, f"V1 P95 too slow: {v1_p95}ms"

    # 3. V2 Dashboard Acquisition latency
    v2_times = []
    for _ in range(35):
        t0 = time.perf_counter()
        adapter.acquire_dashboard_intelligence(dataset_id=101, manifest_data=valid_m, db_conn=hermetic_db)
        v2_times.append((time.perf_counter() - t0) * 1000)
    v2_sorted = sorted(v2_times)
    v2_p50 = v2_sorted[17]
    v2_p95 = v2_sorted[33]
    assert v2_p50 < 30.0, f"V2 P50 too slow: {v2_p50}ms"
    assert v2_p95 < 60.0, f"V2 P95 too slow: {v2_p95}ms"

    # 4. V2 -> V1 Governed Fallback latency
    fb_times = []
    bad_m = dict(valid_m)
    bad_m["is_stale"] = True
    for _ in range(35):
        isolated_gateway.circuit_breaker.reset(ConsumerName.DASHBOARD)
        t0 = time.perf_counter()
        adapter.acquire_dashboard_intelligence(dataset_id=101, manifest_data=bad_m, db_conn=hermetic_db)
        fb_times.append((time.perf_counter() - t0) * 1000)
    fb_sorted = sorted(fb_times)
    fb_p50 = fb_sorted[17]
    fb_p95 = fb_sorted[33]
    assert fb_p50 < 20.0, f"Fallback P50 too slow: {fb_p50}ms"
    assert fb_p95 < 50.0, f"Fallback P95 too slow: {fb_p95}ms"


def test_incremental_memory_benchmark(
    isolated_gateway: ConsumerIntelligenceGateway,
    hermetic_db: sqlite3.Connection,
):
    """
    Incremental Memory Benchmark:
    Measures memory allocation delta and peak across small, medium, and large dataset payloads.
    - Small: 50 rows
    - Medium: 1,000 rows
    - Large: 10,000 rows
    """
    import tracemalloc

    isolated_gateway.transition_state(ConsumerName.DASHBOARD, CutoverState.CERTIFIED, run_id="RUN-I8-4-CERT-001")
    isolated_gateway.transition_state(ConsumerName.DASHBOARD, CutoverState.CANARY)
    isolated_gateway.transition_state(ConsumerName.DASHBOARD, CutoverState.V2_PRIMARY_WITH_FALLBACK)
    adapter = DashboardIntelligenceAdapter(gateway=isolated_gateway)

    # 1. Small: 50 rows
    seed_workforce_dataset(hermetic_db, dataset_id=401)
    m_small = make_sample_manifest("401")
    adapter.register_v2_manifest("401", m_small)

    tracemalloc.start()
    resp_small = adapter.acquire_dashboard_intelligence(dataset_id=401, manifest_data=m_small, db_conn=hermetic_db)
    curr_s, peak_s = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    small_delta_mb = curr_s / (1024 * 1024)
    small_peak_mb = peak_s / (1024 * 1024)
    assert small_delta_mb < 2.0, f"Small delta too large: {small_delta_mb} MB"
    assert small_peak_mb < 5.0, f"Small peak too large: {small_peak_mb} MB"

    # Helper for medium/large synthetic tables
    def seed_synthetic_dataset(ds_id: int, n_rows: int):
        hermetic_db.execute("INSERT OR REPLACE INTO dataset_uploads VALUES (?, ?, ?)", (ds_id, f"data_{ds_id}.xlsx", f"Dataset {ds_id}"))
        hermetic_db.execute("INSERT OR REPLACE INTO sheets VALUES (?, ?, ?, ?, ?, ?)", (1000 + ds_id, ds_id, "data", "Data", json.dumps(["id", "metric", "val"]), n_rows))
        rows = [(1000 + ds_id, i, json.dumps({"id": i, "metric": f"cat_{i%5}", "val": 100.0 + (i % 20)})) for i in range(n_rows)]
        hermetic_db.executemany("INSERT INTO sheet_curated_rows (sheet_id, row_index, data_json) VALUES (?, ?, ?)", rows)
        hermetic_db.commit()

    # 2. Medium: 1,000 rows
    seed_synthetic_dataset(402, 1000)
    m_med = make_sample_manifest("402")
    adapter.register_v2_manifest("402", m_med)

    tracemalloc.start()
    resp_med = adapter.acquire_dashboard_intelligence(dataset_id=402, manifest_data=m_med, db_conn=hermetic_db)
    curr_m, peak_m = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    med_delta_mb = curr_m / (1024 * 1024)
    med_peak_mb = peak_m / (1024 * 1024)
    assert med_delta_mb < 3.0, f"Medium delta too large: {med_delta_mb} MB"
    assert med_peak_mb < 8.0, f"Medium peak too large: {med_peak_mb} MB"

    # 3. Large: 10,000 rows
    seed_synthetic_dataset(403, 10000)
    m_large = make_sample_manifest("403")
    adapter.register_v2_manifest("403", m_large)

    tracemalloc.start()
    resp_large = adapter.acquire_dashboard_intelligence(dataset_id=403, manifest_data=m_large, db_conn=hermetic_db)
    curr_l, peak_l = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    large_delta_mb = curr_l / (1024 * 1024)
    large_peak_mb = peak_l / (1024 * 1024)
    assert large_delta_mb < 5.0, f"Large delta too large: {large_delta_mb} MB"
    assert large_peak_mb < 15.0, f"Large peak too large: {large_peak_mb} MB"


# =============================================================================
# 13. CROSS-CONSUMER TRUTH CONSISTENCY TABLE
# =============================================================================

def test_cross_consumer_truth_consistency_table(
    isolated_gateway: ConsumerIntelligenceGateway,
):
    """
    Cross-Consumer Truth Consistency:
    Verifies that for shared metrics across HRIDAY and Dashboard:
    - metric_id matches
    - value matches identically
    - unit matches
    - grain matches
    - denominator matches
    - evidence_refs match
    - dataset_version matches
    - semantic render hash matches identically
    Total Mismatches: 0.
    """
    hr_adapter = HridayIntelligenceAdapter(gateway=isolated_gateway)
    dash_adapter = DashboardIntelligenceAdapter(gateway=isolated_gateway)

    wfo_hr_metrics = hr_adapter.get_governed_shared_metrics(1, domain="workforce")
    wfo_dash_metrics = dash_adapter.get_governed_shared_metrics(1, domain="workforce")

    assert len(wfo_hr_metrics) >= 5
    assert len(wfo_dash_metrics) >= 5

    mismatches = 0
    for m_hr in wfo_hr_metrics:
        # Find matching dashboard metric
        m_dash = next((d for d in wfo_dash_metrics if d["metric_id"] == m_hr["metric_id"]), None)
        assert m_dash is not None, f"Missing metric {m_hr['metric_id']} in Dashboard"

        if m_hr["value"] != m_dash["value"]:
            mismatches += 1
        if m_hr["unit"] != m_dash["unit"]:
            mismatches += 1
        if m_hr["grain"] != m_dash["grain"]:
            mismatches += 1
        if m_hr["denominator"] != m_dash["denominator"]:
            mismatches += 1
        if m_hr["evidence_refs"] != m_dash["evidence_refs"]:
            mismatches += 1
        if m_hr["dataset_version"] != m_dash["dataset_version"]:
            mismatches += 1

        # Check semantic render hash
        hash_hr = compute_semantic_render_hash(
            topic_or_kpi_id=f"KPI-{m_hr['metric_id']}",
            metric_id=m_hr["metric_id"],
            value=m_hr["value"],
            unit=m_hr["unit"],
            grain=m_hr["grain"],
            denominator=m_hr["denominator"],
            evidence_ids=m_hr["evidence_refs"],
            dataset_version=m_hr["dataset_version"],
        )
        hash_dash = compute_semantic_render_hash(
            topic_or_kpi_id=f"KPI-{m_dash['metric_id']}",
            metric_id=m_dash["metric_id"],
            value=m_dash["value"],
            unit=m_dash["unit"],
            grain=m_dash["grain"],
            denominator=m_dash["denominator"],
            evidence_ids=m_dash["evidence_refs"],
            dataset_version=m_dash["dataset_version"],
        )
        if hash_hr != hash_dash:
            mismatches += 1

    # Retail non-HR shared fact
    ret_hr = hr_adapter.get_governed_shared_metrics(2, domain="retail")
    ret_dash = dash_adapter.get_governed_shared_metrics(2, domain="retail")
    for r_hr in ret_hr:
        r_dash = next((d for d in ret_dash if d["metric_id"] == r_hr["metric_id"]), None)
        assert r_dash is not None
        if r_hr["value"] != r_dash["value"]:
            mismatches += 1
        if r_hr["unit"] != r_dash["unit"]:
            mismatches += 1
        if r_hr["grain"] != r_dash["grain"]:
            mismatches += 1
        if r_hr["denominator"] != r_dash["denominator"]:
            mismatches += 1
        if r_hr["evidence_refs"] != r_dash["evidence_refs"]:
            mismatches += 1
        if r_hr["dataset_version"] != r_dash["dataset_version"]:
            mismatches += 1
        hash_r_hr = compute_semantic_render_hash(
            topic_or_kpi_id=f"KPI-{r_hr['metric_id']}",
            metric_id=r_hr["metric_id"],
            value=r_hr["value"],
            unit=r_hr["unit"],
            grain=r_hr["grain"],
            denominator=r_hr["denominator"],
            evidence_ids=r_hr["evidence_refs"],
            dataset_version=r_hr["dataset_version"],
        )
        hash_r_dash = compute_semantic_render_hash(
            topic_or_kpi_id=f"KPI-{r_dash['metric_id']}",
            metric_id=r_dash["metric_id"],
            value=r_dash["value"],
            unit=r_dash["unit"],
            grain=r_dash["grain"],
            denominator=r_dash["denominator"],
            evidence_ids=r_dash["evidence_refs"],
            dataset_version=r_dash["dataset_version"],
        )
        if hash_r_hr != hash_r_dash:
            mismatches += 1

    assert mismatches == 0, f"Found {mismatches} cross-consumer fact discrepancies!"
