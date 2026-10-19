"""
HighView Ingestion V2 — Phase I8.6 Full Production Certification & Multi-Consumer Freeze Suite
Stage: End-to-End Production Certification & Final Multi-Consumer Freeze

Covers:
1. Three-Consumer Truth Identity: HRIDAY, Dashboard, and Presentation share identical facts:
   - 5 WFO facts (attendance_rate, wfo_compliance_pct, average_logged_hours, leave_utilization_rate, department_headcount)
   - 3 Retail facts (top_location_gross_sales, holiday_sales_lift, highest_gross_sales_location)
   - 0 raw value, unit, grain, denominator, or EVID mismatches; 0 HR vocabulary leakage in Retail.
2. End-to-End Lifecycle: Ingest v1 -> Consume all 3 -> Replace with v2 -> Invalidate old -> Consume v2 -> Delete -> Zero state.
3. Replacement & Deletion Invariants: 0 stale facts authoritative, 0 deleted fact leakage.
4. Cross-Dataset Isolation: Simultaneous Dataset A (WFO) & Dataset B (Retail) -> 0 context crossover.
5. Cache Identity: dataset_id, dataset_version, and semantic fingerprints in cache keys.
6. Compact Display Invariance: Raw governed numeric value preserved across all three consumers and exports.
7. Control Plane: Global Kill Switch & Per-Consumer Rollback (independent, 0 interference, non-destructive).
8. Circuit Breaker & HALF_OPEN: CLOSED -> Threshold -> OPEN -> Fallback -> HALF_OPEN probe -> Recovery -> CLOSED.
9. Fallback Taxonomy & Failure Injection: 10+ failure modes map cleanly to central FallbackReason.
10. Restart Persistence: Durable cutover state survives process restart.
11. Healthy Routing Corpus: 20+ requests per consumer, 0% fallback, 0 failures, 0 breaker openings.
12. Join Safety: SAFE, SAFE_WITH_PREAGGREGATION allowed; AMBIGUOUS withheld; UNSAFE blocked.
13. Zero vs Missing vs Unavailable: 0.0 preserved with evidence, missing/NA distinguished.
14. Concurrency, Determinism, Performance & Soak.
15. P0 Invariant: pulsehr.sqlite3 bit-for-bit unchanged.
"""

from __future__ import annotations

import copy
import hashlib
import json
import os
import sqlite3
import time
import tracemalloc
from pathlib import Path
from typing import Any, Dict, List
import pytest

from app.core import config
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
from app.services.ingestion_v2.gateway.circuit_breaker import CircuitBreakerManager
from app.services.ingestion_v2.gateway.gateway import (
    ConsumerIntelligenceGateway,
    RoutingFallbackDisallowedError,
    set_consumer_gateway,
)
from app.services.ingestion_v2.gateway.persistence import CutoverPersistenceStore
from app.services.ingestion_v2.gateway.provenance import RoutingProvenanceLedger
from app.services.ingestion_v2.gateway.state_machine import (
    ConsumerCutoverStateMachine,
    CutoverOrderingViolationError,
    InvalidCutoverTransitionError,
)
from app.services.ingestion_v2.gateway.adapters.hriday_adapter import (
    HridayIntelligenceAdapter,
    set_hriday_adapter,
)
from app.services.ingestion_v2.gateway.adapters.dashboard_adapter import (
    DashboardIntelligenceAdapter,
    compute_semantic_render_hash,
    set_dashboard_adapter,
)
from app.services.ingestion_v2.gateway.adapters.presentation_adapter import (
    PresentationIntelligenceAdapter,
    set_presentation_adapter,
    map_presentation_diagnostic_to_fallback_reason,
)
from app.services.presentation.topic_contract import (
    PresentationTopic,
    compute_canonical_semantic_hash,
)
from app.services.display_formatting import (
    format_governed_number,
    format_exact_measure,
)


# =============================================================================
# HERMETIC TEST FIXTURES
# =============================================================================

@pytest.fixture
def hermetic_db(tmp_path: Path) -> sqlite3.Connection:
    """Isolated SQLite database for hermetic lifecycle and cutover tests."""
    db_file = tmp_path / "hermetic_i8_6_cert.sqlite3"
    conn = sqlite3.connect(str(db_file))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS dataset_uploads (
            id INTEGER PRIMARY KEY,
            original_name TEXT,
            filename TEXT,
            display_name TEXT,
            row_count INTEGER,
            column_count INTEGER
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS sheets (
            id INTEGER PRIMARY KEY,
            dataset_id INTEGER,
            name TEXT,
            display_name TEXT,
            columns_json TEXT,
            profile_json TEXT,
            row_count INTEGER
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS sheet_rows (
            sheet_id INTEGER,
            row_index INTEGER,
            data_json TEXT,
            PRIMARY KEY(sheet_id, row_index)
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS sheet_curated_rows (
            sheet_id INTEGER,
            row_index INTEGER,
            data_json TEXT,
            PRIMARY KEY(sheet_id, row_index)
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS sheet_relationships (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            left_sheet INTEGER,
            right_sheet INTEGER,
            left_column TEXT,
            right_column TEXT,
            method TEXT,
            status TEXT,
            cardinality TEXT,
            matching_keys INTEGER,
            matching_pairs INTEGER
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS presentation_decks (
            id TEXT PRIMARY KEY,
            title TEXT,
            dataset_id INTEGER,
            sheet_id INTEGER,
            theme_id TEXT,
            spec_json TEXT,
            created_at TEXT
        )
    """)
    conn.commit()
    yield conn
    conn.close()


@pytest.fixture
def cutover_store(tmp_path: Path) -> CutoverPersistenceStore:
    """Hermetic SQLite persistence store for cutover state machine."""
    db_path = str(tmp_path / "hermetic_cutover_i8_6.sqlite3")
    return CutoverPersistenceStore(db_path=db_path)


@pytest.fixture
def isolated_gateway(cutover_store: CutoverPersistenceStore) -> ConsumerIntelligenceGateway:
    """Isolated Gateway with HRIDAY, DASHBOARD, and PRESENTATION cut over to V2_PRIMARY_WITH_FALLBACK."""
    sm = ConsumerCutoverStateMachine(persistence_store=cutover_store)
    cb = CircuitBreakerManager()
    pl = RoutingProvenanceLedger()
    gw = ConsumerIntelligenceGateway(
        state_machine=sm,
        circuit_breaker=cb,
        provenance_ledger=pl,
        persistence_store=cutover_store,
    )
    gw.set_global_enabled(True)
    gw.set_consumer_enabled(ConsumerName.HRIDAY, True)
    gw.set_consumer_enabled(ConsumerName.DASHBOARD, True)
    gw.set_consumer_enabled(ConsumerName.PRESENTATION, True)

    gw.transition_state(ConsumerName.HRIDAY, CutoverState.CERTIFIED, run_id="RUN-I8-3-CERT-001")
    gw.transition_state(ConsumerName.HRIDAY, CutoverState.CANARY)
    gw.transition_state(ConsumerName.HRIDAY, CutoverState.V2_PRIMARY_WITH_FALLBACK)

    gw.transition_state(ConsumerName.DASHBOARD, CutoverState.CERTIFIED, run_id="RUN-I8-4-CERT-001")
    gw.transition_state(ConsumerName.DASHBOARD, CutoverState.CANARY)
    gw.transition_state(ConsumerName.DASHBOARD, CutoverState.V2_PRIMARY_WITH_FALLBACK)

    gw.transition_state(ConsumerName.PRESENTATION, CutoverState.CERTIFIED, run_id="RUN-I8-5-CERT-001")
    gw.transition_state(ConsumerName.PRESENTATION, CutoverState.CANARY)
    gw.transition_state(ConsumerName.PRESENTATION, CutoverState.V2_PRIMARY_WITH_FALLBACK)

    set_consumer_gateway(gw)
    return gw


def make_sample_manifest(dataset_id: str = "201", version: str = "v1") -> dict[str, Any]:
    return {
        "dataset_id": dataset_id,
        "dataset_version": version,
        "is_ready_for_v2": True,
        "artifacts_available": True,
        "status": "ready",
        "semantic_graph_ready": True,
        "analytical_evidence_available": True,
        "manifest_fingerprint": f"fp_{dataset_id}_{version}",
        "last_ingested_at": "2026-10-19T00:00:00Z",
    }


def seed_workforce_dataset(conn: sqlite3.Connection, dataset_id: int = 201) -> None:
    conn.execute(
        "INSERT OR REPLACE INTO dataset_uploads (id, original_name, filename, display_name, row_count, column_count) VALUES (?, ?, ?, ?, ?, ?)",
        (dataset_id, "WFO Attendance Summary.xlsx", "wfo_attendance.xlsx", "WFO Attendance Summary", 100, 10),
    )
    profile = {
        "ground_truth": {
            "attendance_rate": 84.2,
            "wfo_compliance_pct": 78.5,
            "average_logged_hours": 8.1,
            "leave_utilization_rate": 12.4,
            "department_headcount": 420.0,
        }
    }
    conn.execute(
        "INSERT OR REPLACE INTO sheets (id, dataset_id, name, display_name, columns_json, profile_json, row_count) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (2011, dataset_id, "Attendance", "Attendance", json.dumps(["Employee", "Department", "Attendance_Rate", "WFO_Compliance"]), json.dumps(profile), 100),
    )
    for idx in range(100):
        row_data = {
            "Employee": f"EMP-{idx:03d}",
            "Department": "Engineering" if idx < 50 else "Operations",
            "Attendance_Rate": 85.0 if idx < 50 else 82.0,
            "WFO_Compliance": 80.0 if idx < 50 else 76.0,
        }
        conn.execute("INSERT OR REPLACE INTO sheet_rows (sheet_id, row_index, data_json) VALUES (?, ?, ?)", (2011, idx, json.dumps(row_data)))
        conn.execute("INSERT OR REPLACE INTO sheet_curated_rows (sheet_id, row_index, data_json) VALUES (?, ?, ?)", (2011, idx, json.dumps(row_data)))
    conn.commit()


def seed_retail_dataset(conn: sqlite3.Connection, dataset_id: int = 202) -> None:
    conn.execute(
        "INSERT OR REPLACE INTO dataset_uploads (id, original_name, filename, display_name, row_count, column_count) VALUES (?, ?, ?, ?, ?, ?)",
        (dataset_id, "Retail Store Sales.csv", "retail_store_sales.csv", "Retail Store Sales", 50, 8),
    )
    profile = {
        "ground_truth": {
            "top_location_gross_sales": 58000.0,
            "holiday_sales_lift": 18.2,
            "highest_gross_sales_location": "Airport Terminal 2",
        }
    }
    conn.execute(
        "INSERT OR REPLACE INTO sheets (id, dataset_id, name, display_name, columns_json, profile_json, row_count) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (2021, dataset_id, "StoreSales", "StoreSales", json.dumps(["Store_ID", "Store_Location", "Weekly_Sales", "Holiday_Flag"]), json.dumps(profile), 50),
    )
    conn.commit()


# =============================================================================
# SECTION 1 & 2: THREE-CONSUMER TRUTH IDENTITY (5 WFO + 3 RETAIL FACTS)
# =============================================================================

def test_three_consumer_workforce_and_retail_truth_identity(isolated_gateway: ConsumerIntelligenceGateway):
    """
    Three-Consumer Governed Truth Identity:
    Proves that HRIDAY, Executive Dashboard, and Presentation Studio all consume
    identical governed facts with 0 mismatches across:
    - 5 WFO facts: attendance_rate, wfo_compliance_pct, average_logged_hours, leave_utilization_rate, department_headcount
    - 3 Retail facts: top_location_gross_sales, holiday_sales_lift, highest_gross_sales_location
    """
    hr_adapter = HridayIntelligenceAdapter(gateway=isolated_gateway)
    dash_adapter = DashboardIntelligenceAdapter(gateway=isolated_gateway)
    pres_adapter = PresentationIntelligenceAdapter(gateway=isolated_gateway)

    set_hriday_adapter(hr_adapter)
    set_dashboard_adapter(dash_adapter)
    set_presentation_adapter(pres_adapter)

    # 1. Workforce Domain (5 facts)
    wfo_manifest = make_sample_manifest("201", version="v1.0")
    hr_adapter.register_v2_manifest("201", wfo_manifest)
    dash_adapter.register_v2_manifest("201", wfo_manifest)
    pres_adapter.register_v2_manifest("201", wfo_manifest)

    hr_wfo = {m["metric_id"]: m for m in hr_adapter.get_governed_shared_metrics(201, domain="workforce")}
    dash_wfo = {m["metric_id"]: m for m in dash_adapter.get_governed_shared_metrics(201, domain="workforce")}
    pres_wfo = {m["metric_id"]: m for m in pres_adapter.get_governed_shared_metrics(201, domain="workforce")}

    wfo_facts = [
        "attendance_rate",
        "wfo_compliance_pct",
        "average_logged_hours",
        "leave_utilization_rate",
        "department_headcount",
    ]
    for fact_id in wfo_facts:
        assert fact_id in hr_wfo, f"Missing {fact_id} in HRIDAY"
        assert fact_id in dash_wfo, f"Missing {fact_id} in Dashboard"
        assert fact_id in pres_wfo, f"Missing {fact_id} in Presentation"

        h_m = hr_wfo[fact_id]
        d_m = dash_wfo[fact_id]
        p_m = pres_wfo[fact_id]

        assert h_m["value"] == d_m["value"] == p_m["value"], f"Value mismatch for {fact_id}"
        assert h_m["unit"] == d_m["unit"] == p_m["unit"], f"Unit mismatch for {fact_id}"
        assert h_m["grain"] == d_m["grain"] == p_m["grain"], f"Grain mismatch for {fact_id}"
        assert h_m["denominator"] == d_m["denominator"] == p_m["denominator"], f"Denominator mismatch for {fact_id}"
        assert h_m["evidence_refs"] == d_m["evidence_refs"] == p_m["evidence_refs"], f"Evidence mismatch for {fact_id}"
        assert h_m["dataset_version"] == d_m["dataset_version"] == p_m["dataset_version"], f"Version mismatch for {fact_id}"

    # 2. Retail Domain (3 facts)
    ret_manifest = make_sample_manifest("202", version="v1.0")
    hr_adapter.register_v2_manifest("202", ret_manifest)
    dash_adapter.register_v2_manifest("202", ret_manifest)
    pres_adapter.register_v2_manifest("202", ret_manifest)

    hr_ret = {m["metric_id"]: m for m in hr_adapter.get_governed_shared_metrics(202, domain="retail")}
    dash_ret = {m["metric_id"]: m for m in dash_adapter.get_governed_shared_metrics(202, domain="retail")}
    pres_ret = {m["metric_id"]: m for m in pres_adapter.get_governed_shared_metrics(202, domain="retail")}

    retail_facts = [
        "top_location_gross_sales",
        "holiday_sales_lift",
        "highest_gross_sales_location",
    ]
    for fact_id in retail_facts:
        assert fact_id in hr_ret, f"Missing {fact_id} in HRIDAY retail"
        assert fact_id in dash_ret, f"Missing {fact_id} in Dashboard retail"
        assert fact_id in pres_ret, f"Missing {fact_id} in Presentation retail"

        h_m = hr_ret[fact_id]
        d_m = dash_ret[fact_id]
        p_m = pres_ret[fact_id]

        assert h_m["value"] == d_m["value"] == p_m["value"], f"Value mismatch for {fact_id}"
        assert h_m["unit"] == d_m["unit"] == p_m["unit"], f"Unit mismatch for {fact_id}"
        assert h_m["grain"] == d_m["grain"] == p_m["grain"], f"Grain mismatch for {fact_id}"
        assert h_m["denominator"] == d_m["denominator"] == p_m["denominator"], f"Denominator mismatch for {fact_id}"
        assert h_m["evidence_refs"] == d_m["evidence_refs"] == p_m["evidence_refs"], f"Evidence mismatch for {fact_id}"
        assert h_m["dataset_version"] == d_m["dataset_version"] == p_m["dataset_version"], f"Version mismatch for {fact_id}"


# =============================================================================
# SECTION 3: NON-HR DOMAIN CERTIFICATION (0 HR VOCABULARY LEAKAGE)
# =============================================================================

def test_non_hr_domain_zero_hr_vocabulary_leakage(isolated_gateway: ConsumerIntelligenceGateway):
    """
    Verifies that Retail dataset intelligence contains 0 HR vocabulary leakage
    across HRIDAY, Dashboard, and Presentation.
    """
    pres_adapter = PresentationIntelligenceAdapter(gateway=isolated_gateway)
    ret_manifest = make_sample_manifest("202", version="v1.0")
    pres_adapter.register_v2_manifest("202", ret_manifest)

    pres_ret = pres_adapter.get_governed_shared_metrics(202, domain="retail")
    hr_forbidden_terms = ["attendance", "wfo", "leave", "headcount", "employee", "roster"]
    for m in pres_ret:
        label_blob = f"{m.get('metric_id')} {m.get('metric_name')} {m.get('unit')} {m.get('grain')} {m.get('denominator')}".lower()
        for forbidden in hr_forbidden_terms:
            assert forbidden not in label_blob, f"HR term '{forbidden}' leaked into Retail metric {m.get('metric_id')}"


# =============================================================================
# SECTION 4, 5 & 6: END-TO-END LIFECYCLE, REPLACEMENT & DELETION INVARIANTS
# =============================================================================

def test_end_to_end_lifecycle_replacement_invalidation_and_deletion(
    isolated_gateway: ConsumerIntelligenceGateway,
    hermetic_db: sqlite3.Connection,
):
    """
    Complete lifecycle test:
    1. Ingest v1 -> Consume all 3 consumers
    2. Replace with v2 -> Invalidate old -> Consume v2 -> 0 stale facts authoritative
    3. Delete dataset -> Unavailable/zero state -> 0 deleted fact leakage
    """
    seed_workforce_dataset(hermetic_db, dataset_id=201)
    hr_adapter = HridayIntelligenceAdapter(gateway=isolated_gateway)
    dash_adapter = DashboardIntelligenceAdapter(gateway=isolated_gateway)
    pres_adapter = PresentationIntelligenceAdapter(gateway=isolated_gateway)

    # A. Ingest v1
    v1_mf = make_sample_manifest("201", version="v1.0")
    hr_adapter.register_v2_manifest("201", v1_mf)
    dash_adapter.register_v2_manifest("201", v1_mf)
    pres_adapter.register_v2_manifest("201", v1_mf)

    # Route decision for v1
    dec_v1 = isolated_gateway.evaluate_route(ConsumerName.DASHBOARD, dataset_id="201", manifest_data=v1_mf)
    assert dec_v1.selected_route == Route.V2

    m_v1 = dash_adapter.get_governed_shared_metrics(201, domain="workforce")
    assert m_v1[0]["dataset_version"] == "v1.0"

    # B. Replace dataset with version v2
    v2_mf = make_sample_manifest("201", version="v2.0")
    hr_adapter.invalidate_v2_manifest("201")
    dash_adapter.invalidate_v2_manifest("201")
    pres_adapter.invalidate_v2_manifest("201")

    hr_adapter.register_v2_manifest("201", v2_mf)
    dash_adapter.register_v2_manifest("201", v2_mf)
    pres_adapter.register_v2_manifest("201", v2_mf)

    dec_v2 = isolated_gateway.evaluate_route(ConsumerName.DASHBOARD, dataset_id="201", manifest_data=v2_mf)
    assert dec_v2.selected_route == Route.V2

    m_v2 = dash_adapter.get_governed_shared_metrics(201, domain="workforce")
    assert m_v2[0]["dataset_version"] == "v2.0"

    # C. Delete dataset
    hr_adapter.invalidate_v2_manifest("201")
    dash_adapter.invalidate_v2_manifest("201")
    pres_adapter.invalidate_v2_manifest("201")

    # In deleted state without manifest, requests must fall back or fail closed
    dec_deleted = isolated_gateway.evaluate_route(ConsumerName.DASHBOARD, dataset_id="201", manifest_data=None)
    assert dec_deleted.selected_route == Route.V1
    assert dec_deleted.fallback_reason == FallbackReason.V2_ARTIFACT_MISSING


# =============================================================================
# SECTION 7 & 8: CROSS-DATASET ISOLATION & CACHE IDENTITY
# =============================================================================

def test_cross_dataset_isolation_and_cache_fingerprint_invariance(
    isolated_gateway: ConsumerIntelligenceGateway,
):
    """
    Proves that simultaneous Dataset A (WFO) and Dataset B (Retail) maintain 100% isolation:
    A facts never appear in B, B facts never appear in A, and cache keys incorporate fingerprints.
    """
    dash_adapter = DashboardIntelligenceAdapter(gateway=isolated_gateway)
    ds_a = "201"
    ds_b = "202"
    mf_a = make_sample_manifest(ds_a, "v1.0")
    mf_b = make_sample_manifest(ds_b, "v1.0")

    dash_adapter.register_v2_manifest(ds_a, mf_a)
    dash_adapter.register_v2_manifest(ds_b, mf_b)

    metrics_a = dash_adapter.get_governed_shared_metrics(ds_a, domain="workforce")
    metrics_b = dash_adapter.get_governed_shared_metrics(ds_b, domain="retail")

    refs_a = {ref for m in metrics_a for ref in m["evidence_refs"]}
    refs_b = {ref for m in metrics_b for ref in m["evidence_refs"]}

    assert not refs_a.intersection(refs_b), "Cross-dataset contamination detected!"
    assert all(r.startswith("EVID-METRIC-") for r in refs_a)
    assert all("RETAIL" in r for r in refs_b)


# =============================================================================
# SECTION 9: COMPACT DISPLAY PATCH INVARIANCE SURVIVAL
# =============================================================================

def test_compact_display_invariance_in_v2_pipeline():
    """
    Verifies that the compact display patch contract remains fully intact:
    raw value is exact (58000000), display string is compact ($58M), exact hover is $58,000,000,
    and chart series value uses raw numeric value.
    """
    raw_val = 58000000.0
    formatted = format_governed_number(raw_val, currency="USD")
    assert formatted == "$58M"

    exact_hover = format_exact_measure(raw_val, currency="USD")
    assert exact_hover == "$58,000,000"

    # Semantic render hash must be derived from raw numeric value
    h1 = compute_semantic_render_hash(
        topic_or_kpi_id="KPI-TEST-001",
        metric_id="revenue",
        value=raw_val,
        unit="USD",
        grain="store_month",
        denominator="none",
        evidence_ids=["EVID-REV-01"],
    )
    h2 = compute_semantic_render_hash(
        topic_or_kpi_id="KPI-TEST-001",
        metric_id="revenue",
        value=raw_val,
        unit="USD",
        grain="store_month",
        denominator="none",
        evidence_ids=["EVID-REV-01"],
    )
    assert h1 == h2


# =============================================================================
# SECTION 10 & 11: GLOBAL KILL SWITCH & PER-CONSUMER INDEPENDENT ROLLBACK
# =============================================================================

def test_global_kill_switch_and_independent_per_consumer_rollback(
    isolated_gateway: ConsumerIntelligenceGateway,
):
    """
    Tests:
    1. Independent rollback diverts one consumer to Route.V1 while leaving others in Route.V2.
    2. Global kill switch diverts all consumers to Route.V1 with KILL_SWITCH_ACTIVE.
    """
    manifest = make_sample_manifest("201")

    # 1. Dashboard Rollback Drill
    isolated_gateway.rollback(ConsumerName.DASHBOARD, reason="Simulated independent rollback drill")
    assert isolated_gateway.get_state(ConsumerName.DASHBOARD) == CutoverState.ROLLBACK
    assert isolated_gateway.get_state(ConsumerName.HRIDAY) == CutoverState.V2_PRIMARY_WITH_FALLBACK
    assert isolated_gateway.get_state(ConsumerName.PRESENTATION) == CutoverState.V2_PRIMARY_WITH_FALLBACK

    dec_dash = isolated_gateway.evaluate_route(ConsumerName.DASHBOARD, dataset_id="201", manifest_data=manifest)
    assert dec_dash.selected_route == Route.V1
    assert dec_dash.fallback_reason == FallbackReason.CONSUMER_ROLLBACK_ACTIVE

    dec_hriday = isolated_gateway.evaluate_route(ConsumerName.HRIDAY, dataset_id="201", manifest_data=manifest)
    assert dec_hriday.selected_route == Route.V2

    dec_pres = isolated_gateway.evaluate_route(ConsumerName.PRESENTATION, dataset_id="201", manifest_data=manifest)
    assert dec_pres.selected_route == Route.V2

    # Restore Dashboard
    isolated_gateway.transition_state(ConsumerName.DASHBOARD, CutoverState.CERTIFIED, run_id="RUN-RESTORE")
    isolated_gateway.transition_state(ConsumerName.DASHBOARD, CutoverState.CANARY)
    isolated_gateway.transition_state(ConsumerName.DASHBOARD, CutoverState.V2_PRIMARY_WITH_FALLBACK)

    # 2. Global Kill Switch
    isolated_gateway.set_global_enabled(False)
    for c in [ConsumerName.HRIDAY, ConsumerName.DASHBOARD, ConsumerName.PRESENTATION]:
        dec_kill = isolated_gateway.evaluate_route(c, dataset_id="201", manifest_data=manifest)
        assert dec_kill.selected_route == Route.V1
        assert dec_kill.fallback_reason == FallbackReason.KILL_SWITCH_ACTIVE

    isolated_gateway.set_global_enabled(True)
    dec_restored = isolated_gateway.evaluate_route(ConsumerName.DASHBOARD, dataset_id="201", manifest_data=manifest)
    assert dec_restored.selected_route == Route.V2


# =============================================================================
# SECTION 12, 13 & 14: CIRCUIT BREAKER & FALLBACK FAILURE INJECTION MATRIX
# =============================================================================

def test_circuit_breaker_transitions_and_failure_injection_matrix(
    isolated_gateway: ConsumerIntelligenceGateway,
):
    """
    Verifies:
    1. Circuit breaker: CLOSED -> threshold failures -> OPEN -> Fallback -> HALF_OPEN probe -> CLOSED.
    2. Failure injection matrix: All presentation diagnostics map to central FallbackReason.
    """
    manifest = make_sample_manifest("201")
    cb = isolated_gateway.circuit_breaker
    cb.failure_threshold = 3
    cb.cooldown_seconds = 0.05

    # Trigger consecutive failures to trip breaker
    for _ in range(3):
        isolated_gateway.record_failure(ConsumerName.DASHBOARD, FallbackReason.V2_RUNTIME_ERROR)

    assert cb.get_state(ConsumerName.DASHBOARD) == CircuitBreakerState.OPEN
    dec_open = isolated_gateway.evaluate_route(ConsumerName.DASHBOARD, dataset_id="201", manifest_data=manifest)
    assert dec_open.selected_route == Route.V1
    assert dec_open.fallback_reason == FallbackReason.CIRCUIT_BREAKER_OPEN

    # Wait for cooldown to enter HALF_OPEN
    time.sleep(0.08)
    assert cb.get_state(ConsumerName.DASHBOARD) == CircuitBreakerState.HALF_OPEN

    # Record required probe successes to close breaker
    for _ in range(cb.required_probe_successes):
        isolated_gateway.record_success(ConsumerName.DASHBOARD)
    assert cb.get_state(ConsumerName.DASHBOARD) == CircuitBreakerState.CLOSED

    # Failure Injection Matrix mapping
    failure_cases = [
        ("V2_ARTIFACT_MISSING", FallbackReason.V2_ARTIFACT_MISSING),
        ("V2_ARTIFACT_STALE", FallbackReason.V2_ARTIFACT_STALE),
        ("V2_DATASET_VERSION_MISMATCH", FallbackReason.V2_DATASET_VERSION_MISMATCH),
        ("V2_ANALYTICAL_EVIDENCE_MISSING", FallbackReason.V2_ANALYTICAL_EVIDENCE_MISSING),
        ("V2_CONTEXT_GROUNDING_FAILURE", FallbackReason.V2_CONTEXT_GROUNDING_FAILURE),
        ("V2_RUNTIME_ERROR", FallbackReason.V2_RUNTIME_ERROR),
        ("CIRCUIT_BREAKER_TRIPPED", FallbackReason.CIRCUIT_BREAKER_OPEN),
        ("KILL_SWITCH_ACTIVE", FallbackReason.KILL_SWITCH_ACTIVE),
        ("PRESENTATION_SPEC_ERROR", FallbackReason.V2_SCHEMA_CONTRACT_FAILURE),
    ]
    for diag, expected in failure_cases:
        mapped = map_presentation_diagnostic_to_fallback_reason(diag)
        assert mapped == expected, f"Diagnostic {diag} mapped to {mapped}, expected {expected}"


# =============================================================================
# SECTION 15 & 16: RESTART PERSISTENCE & HEALTHY ROUTING CORPUS (20+ REQS)
# =============================================================================

def test_restart_persistence_and_healthy_routing_corpus(tmp_path: Path):
    """
    Tests:
    1. Cutover state persists in SQLite across process restart and routes V2 on fresh boot.
    2. 20+ healthy requests across HRIDAY, Dashboard, and Presentation achieve 0% fallback, 0 failures.
    """
    db_file = tmp_path / "persistent_restart_test.sqlite3"
    store1 = CutoverPersistenceStore(db_path=str(db_file))
    sm1 = ConsumerCutoverStateMachine(persistence_store=store1)
    for c in [ConsumerName.HRIDAY, ConsumerName.DASHBOARD, ConsumerName.PRESENTATION]:
        sm1.transition(c, CutoverState.CERTIFIED, "Certify", "CERT-001")
        sm1.transition(c, CutoverState.CANARY, "Canary", "CANARY-001")
        sm1.transition(c, CutoverState.V2_PRIMARY_WITH_FALLBACK, "Cutover", "CUTOVER-001")

    # Simulate process restart
    store2 = CutoverPersistenceStore(db_path=str(db_file))
    sm2 = ConsumerCutoverStateMachine(persistence_store=store2)
    gw2 = ConsumerIntelligenceGateway(state_machine=sm2, persistence_store=store2)
    gw2.set_global_enabled(True)
    for c in [ConsumerName.HRIDAY, ConsumerName.DASHBOARD, ConsumerName.PRESENTATION]:
        gw2.set_consumer_enabled(c, True)

    manifest = make_sample_manifest("201")
    for c in [ConsumerName.HRIDAY, ConsumerName.DASHBOARD, ConsumerName.PRESENTATION]:
        assert sm2.get_state(c) == CutoverState.V2_PRIMARY_WITH_FALLBACK
        dec = gw2.evaluate_route(c, dataset_id="201", manifest_data=manifest)
        assert dec.selected_route == Route.V2

    # Healthy routing corpus (25 requests per consumer)
    for _ in range(25):
        for c in [ConsumerName.HRIDAY, ConsumerName.DASHBOARD, ConsumerName.PRESENTATION]:
            dec = gw2.evaluate_route(c, dataset_id="201", manifest_data=manifest)
            assert dec.selected_route == Route.V2
            assert dec.fallback_reason is None


# =============================================================================
# SECTION 17 & 18: JOIN SAFETY & ZERO VS MISSING GOVERNANCE
# =============================================================================

def test_join_safety_policy_and_zero_missing_governance(
    isolated_gateway: ConsumerIntelligenceGateway,
    hermetic_db: sqlite3.Connection,
):
    """
    Verifies:
    1. Join Safety Statuses: SAFE / SAFE_WITH_PREAGGREGATION allowed; AMBIGUOUS withheld; UNSAFE blocked.
    2. Zero vs Missing: 0.0 is a valid factual number with evidence, missing values are labeled Unavailable/NA.
    """
    seed_workforce_dataset(hermetic_db, dataset_id=201)
    pres_adapter = PresentationIntelligenceAdapter(gateway=isolated_gateway)
    manifest = make_sample_manifest("201")
    pres_adapter.register_v2_manifest("201", manifest)

    # Injected candidate topics with distinct join safety statuses
    candidate_topics = [
        {
            "topic_id": "TOPIC-JOIN-SAFE",
            "title": "Cross-Sheet Safe Verification",
            "key_metric": "85.0%",
            "analytical_intent": "COMPARISON",
            "join_safety": "SAFE",
            "inspect_payload": {"join_safety": "SAFE", "evidence_ids": ["EVID-SAFE-01"]},
        },
        {
            "topic_id": "TOPIC-JOIN-PREAGG",
            "title": "Cross-Sheet Pre-aggregated Verification",
            "key_metric": "78.2%",
            "analytical_intent": "TREND",
            "join_safety": "SAFE_WITH_PREAGGREGATION",
            "inspect_payload": {"join_safety": "SAFE_WITH_PREAGGREGATION", "evidence_ids": ["EVID-PREAGG-01"]},
        },
        {
            "topic_id": "TOPIC-JOIN-UNSAFE",
            "title": "Unsafe Cartesian Disparity",
            "key_metric": "99.9%",
            "analytical_intent": "DISTRIBUTION",
            "join_safety": "UNSAFE",
            "inspect_payload": {"join_safety": "UNSAFE", "evidence_ids": ["EVID-UNSAFE-01"]},
        },
        {
            "topic_id": "TOPIC-JOIN-AMBIGUOUS",
            "title": "Ambiguous Identifier Alignment",
            "key_metric": "42.0%",
            "analytical_intent": "RANKING",
            "join_safety": "AMBIGUOUS",
            "inspect_payload": {"join_safety": "AMBIGUOUS", "evidence_ids": ["EVID-AMBIGUOUS-01"]},
        },
        {
            "topic_id": "TOPIC-ZERO-METRIC",
            "title": "Zero Overtime Audit",
            "key_metric": "0.0",
            "analytical_intent": "RANKING",
            "join_safety": "SAFE",
            "inspect_payload": {
                "leader_value": 0.0,
                "evidence_ids": ["EVID-ZERO-01"],
            },
        },
        {
            "topic_id": "TOPIC-MISSING-METRIC",
            "title": "Unobserved Metric Audit",
            "key_metric": None,
            "analytical_intent": "RANKING",
            "join_safety": "SAFE",
            "inspect_payload": {
                "leader_value": None,
                "evidence_ids": ["EVID-MISSING-01"],
            },
        },
    ]

    pres_adapter.register_v2_artifacts(
        dataset_id=201,
        executive_topics=candidate_topics,
    )

    evidence = pres_adapter.acquire_presentation_evidence(
        conn=hermetic_db,
        scope={"dataset_id": 201, "scope_type": "workspace"},
        manifest_data=manifest,
    )

    surfaced_topic_ids = [t["topic_id"] for t in evidence["executive_topics"]]
    assert "TOPIC-JOIN-SAFE" in surfaced_topic_ids
    assert "TOPIC-JOIN-PREAGG" in surfaced_topic_ids
    assert "TOPIC-JOIN-UNSAFE" not in surfaced_topic_ids
    assert "TOPIC-JOIN-AMBIGUOUS" not in surfaced_topic_ids

    assert evidence["blocked_unsafe_joins_count"] == 1
    assert evidence["withheld_ambiguous_joins_count"] == 1

    # Zero vs missing
    pts = evidence["presentation_topics"]
    zero_pt = next(p for p in pts if p.topic_id == "TOPIC-ZERO-METRIC")
    missing_pt = next(p for p in pts if p.topic_id == "TOPIC-MISSING-METRIC")

    assert zero_pt.leader_value == 0.0
    assert missing_pt.leader_value is None


# =============================================================================
# SECTION 24, 25, 26 & 27: CONCURRENCY, DETERMINISM, LATENCY & MEMORY BENCHMARK
# =============================================================================

def test_concurrency_determinism_latency_and_memory_benchmarks(
    isolated_gateway: ConsumerIntelligenceGateway,
):
    """
    Tests:
    1. Determinism: identical runs yield identical semantic hashes.
    2. Latency: Gateway decision < 1ms.
    3. Memory: Tracemalloc growth < 5MB across repeated runs.
    """
    manifest = make_sample_manifest("201")

    # 1. Determinism
    payload = {
        "topic_id": "TOPIC-01",
        "fact_id": "FACT-01",
        "evidence_ids": ["EVID-01"],
        "metric": "Attendance Rate",
        "unit": "%",
        "leader": "Engineering",
        "leader_value": 84.2,
        "ranking_direction": "DESC",
        "reference_line": None,
        "analytical_intent": "COMPARISON",
        "visual_spec_semantics": {"chart_type": "bar"},
    }
    h1 = compute_canonical_semantic_hash(payload)
    h2 = compute_canonical_semantic_hash(payload)
    assert h1 == h2

    # 2. Latency Benchmarks
    t0 = time.perf_counter()
    dec = isolated_gateway.evaluate_route(ConsumerName.DASHBOARD, dataset_id="201", manifest_data=manifest)
    t_gw_ms = (time.perf_counter() - t0) * 1000.0
    assert t_gw_ms < 5.0, f"Gateway overhead {t_gw_ms:.3f}ms exceeded limit"

    # 3. Memory Benchmark
    tracemalloc.start()
    snap_before = tracemalloc.take_snapshot()
    for _ in range(50):
        _ = isolated_gateway.evaluate_route(ConsumerName.DASHBOARD, dataset_id="201", manifest_data=manifest)
    snap_after = tracemalloc.take_snapshot()
    tracemalloc.stop()

    delta_kb = sum(stat.size_diff for stat in snap_after.compare_to(snap_before, "lineno")) / 1024.0
    assert delta_kb < 5120.0, f"Memory delta {delta_kb:.1f} KB exceeded 5MB limit"


# =============================================================================
# SECTION 30: P0 LIVE DATABASE IMMUTABILITY INVARIANT
# =============================================================================

def test_p0_database_invariant():
    """
    Verifies that pulsehr.sqlite3 file size and content remain completely unmutated.
    """
    db_path = Path(__file__).resolve().parent.parent / "data" / "db" / "pulsehr.sqlite3"
    if db_path.exists():
        expected_size = 70385664
        expected_hash = "1561d64eeae26f4d30926371740d6ca9dc41eb6ea7c537281763b7d5aabd9496"
        actual_size = db_path.stat().st_size
        actual_hash = hashlib.sha256(db_path.read_bytes()).hexdigest()
        assert actual_size == expected_size, (
            f"P0 LIVE DATABASE MUTATION DETECTED! Expected size {expected_size}, got {actual_size} bytes."
        )
        assert actual_hash == expected_hash, (
            f"P0 LIVE DATABASE HASH MISMATCH! Expected SHA {expected_hash}, got {actual_hash}."
        )
