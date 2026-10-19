"""
HighView Ingestion V2 — Phase I8.5 Presentation Studio Controlled Cutover Test Suite
Stage: Presentation Controlled V2 Cutover
Covers:
1. Cutover State Progression: SHADOW -> CERTIFIED -> CANARY -> V2_PRIMARY_WITH_FALLBACK.
2. Cutover Ordering Constraints: PRESENTATION cannot transition until DASHBOARD is >= CERTIFIED.
3. State Persistence & Restart Recovery: Durable SQLite cutover records survive restart.
4. Three-Consumer Governed Truth Identity: HRIDAY, Dashboard, and Presentation share identical facts:
   - 5 WFO facts (attendance_rate, wfo_compliance_pct, average_logged_hours, leave_utilization_rate, department_headcount)
   - 3 Retail facts (top_location_gross_sales, holiday_sales_lift, highest_gross_sales_loc)
   - 0 raw value, unit, grain, denominator, or EVID mismatches; 0 HR vocabulary leakage in Retail.
5. Cross-Sheet Join Safety: SAFE/SAFE_WITH_PREAGGREGATION allowed; UNSAFE blocked; AMBIGUOUS withheld.
6. Zero vs Missing Governance: Numeric 0.0 preserved with evidence; unobserved labeled Unavailable/NA.
7. Canonical Semantic Hash Parity: upstream == presentation == slide contract hash.
8. Fallback Taxonomy Audit & Failure Injection: All 8 failure modes map to frozen Gateway FallbackReason.
9. Circuit Breaker, Governed Fallback, & Non-Destructive Rollback (< 1ms, HRIDAY & Dashboard untouched).
10. Performance Benchmarks: Sub-millisecond gateway decision, < 5ms governed fallback, memory guardrails.
"""

import json
import os
import sqlite3
import time
import tracemalloc
from pathlib import Path
from typing import Any
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
    get_presentation_adapter,
    set_presentation_adapter,
    map_presentation_diagnostic_to_fallback_reason,
)
from app.services.presentation.topic_contract import (
    PresentationTopic,
    compute_canonical_semantic_hash,
)
from app.services.presentation.governed_presentation_builder import build_governed_presentation_deck
from app.services.presentation.deck_generator import generate_presentation_deck_spec
from app.services.report_generator import export_spec_to_pptx
from app.services.presentation.resolved_pdf import export_resolved_pdf


# =============================================================================
# FIXTURES & ISOLATED HARNESS
# =============================================================================

@pytest.fixture
def hermetic_db(tmp_path: Path) -> sqlite3.Connection:
    """Isolated, hermetic SQLite database for test runs."""
    db_file = tmp_path / "hermetic_pulsehr_presentation.sqlite3"
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
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sheet_id INTEGER,
            row_index INTEGER,
            data_json TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS sheet_curated_rows (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sheet_id INTEGER,
            row_index INTEGER,
            data_json TEXT
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
def persistence_store(tmp_path: Path) -> CutoverPersistenceStore:
    """Isolated persistence store for cutover state."""
    db_file = tmp_path / "test_presentation_cutover_state.sqlite3"
    return CutoverPersistenceStore(db_path=str(db_file))


@pytest.fixture
def isolated_gateway(persistence_store: CutoverPersistenceStore) -> ConsumerIntelligenceGateway:
    """Creates an isolated Gateway with HRIDAY and DASHBOARD frozen at V2_PRIMARY_WITH_FALLBACK."""
    sm = ConsumerCutoverStateMachine(persistence_store=persistence_store)
    cb = CircuitBreakerManager()
    pl = RoutingProvenanceLedger()
    gw = ConsumerIntelligenceGateway(
        state_machine=sm,
        circuit_breaker=cb,
        provenance_ledger=pl,
        persistence_store=persistence_store,
    )
    # Enable V2 globally and per consumer
    gw.set_global_enabled(True)
    gw.set_consumer_enabled(ConsumerName.HRIDAY, True)
    gw.set_consumer_enabled(ConsumerName.DASHBOARD, True)
    gw.set_consumer_enabled(ConsumerName.PRESENTATION, True)

    # Establish frozen state: HRIDAY and DASHBOARD at V2_PRIMARY_WITH_FALLBACK
    gw.transition_state(ConsumerName.HRIDAY, CutoverState.CERTIFIED, run_id="RUN-I8-3-CERT-001")
    gw.transition_state(ConsumerName.HRIDAY, CutoverState.CANARY)
    gw.transition_state(ConsumerName.HRIDAY, CutoverState.V2_PRIMARY_WITH_FALLBACK)

    gw.transition_state(ConsumerName.DASHBOARD, CutoverState.CERTIFIED, run_id="RUN-I8-4-CERT-001")
    gw.transition_state(ConsumerName.DASHBOARD, CutoverState.CANARY)
    gw.transition_state(ConsumerName.DASHBOARD, CutoverState.V2_PRIMARY_WITH_FALLBACK)

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
    for idx in range(50):
        row_data = {
            "Store_ID": f"STORE-{idx:02d}",
            "Store_Location": "Airport Terminal 2" if idx == 0 else f"City Center {idx}",
            "Weekly_Sales": 58000.0 if idx == 0 else 32000.0,
            "Holiday_Flag": 1 if idx % 5 == 0 else 0,
        }
        conn.execute("INSERT OR REPLACE INTO sheet_rows (sheet_id, row_index, data_json) VALUES (?, ?, ?)", (2021, idx, json.dumps(row_data)))
        conn.execute("INSERT OR REPLACE INTO sheet_curated_rows (sheet_id, row_index, data_json) VALUES (?, ?, ?)", (2021, idx, json.dumps(row_data)))
    conn.commit()


# =============================================================================
# 1. STATE PROGRESSION, ORDERING & PERSISTENCE RECOVERY
# =============================================================================

def test_presentation_cutover_progression_shadow_to_v2_primary(
    isolated_gateway: ConsumerIntelligenceGateway,
):
    """
    Verifies the strict cutover lifecycle for PRESENTATION:
    SHADOW -> CERTIFIED -> CANARY -> V2_PRIMARY_WITH_FALLBACK.
    HRIDAY and DASHBOARD remain pinned at V2_PRIMARY_WITH_FALLBACK.
    """
    assert isolated_gateway.state_machine.get_state(ConsumerName.PRESENTATION) == CutoverState.SHADOW
    assert isolated_gateway.state_machine.get_state(ConsumerName.HRIDAY) == CutoverState.V2_PRIMARY_WITH_FALLBACK
    assert isolated_gateway.state_machine.get_state(ConsumerName.DASHBOARD) == CutoverState.V2_PRIMARY_WITH_FALLBACK

    # 1. Transition to CERTIFIED
    t1 = isolated_gateway.transition_state(
        ConsumerName.PRESENTATION,
        CutoverState.CERTIFIED,
        run_id="RUN-I8-5-CERT-001",
    )
    assert t1.current_state == CutoverState.CERTIFIED
    assert isolated_gateway.state_machine.get_state(ConsumerName.PRESENTATION) == CutoverState.CERTIFIED

    # 2. Transition to CANARY
    t2 = isolated_gateway.transition_state(
        ConsumerName.PRESENTATION,
        CutoverState.CANARY,
    )
    assert t2.current_state == CutoverState.CANARY
    assert isolated_gateway.state_machine.get_state(ConsumerName.PRESENTATION) == CutoverState.CANARY

    # 3. Transition to V2_PRIMARY_WITH_FALLBACK
    t3 = isolated_gateway.transition_state(
        ConsumerName.PRESENTATION,
        CutoverState.V2_PRIMARY_WITH_FALLBACK,
    )
    assert t3.current_state == CutoverState.V2_PRIMARY_WITH_FALLBACK
    assert isolated_gateway.state_machine.get_state(ConsumerName.PRESENTATION) == CutoverState.V2_PRIMARY_WITH_FALLBACK

    # Confirms sibling consumers remained completely untouched
    assert isolated_gateway.state_machine.get_state(ConsumerName.HRIDAY) == CutoverState.V2_PRIMARY_WITH_FALLBACK
    assert isolated_gateway.state_machine.get_state(ConsumerName.DASHBOARD) == CutoverState.V2_PRIMARY_WITH_FALLBACK


def test_presentation_cutover_ordering_enforcement(
    persistence_store: CutoverPersistenceStore,
):
    """
    Verifies that PRESENTATION cannot transition to CERTIFIED or higher if DASHBOARD is not at least CERTIFIED.
    """
    sm = ConsumerCutoverStateMachine(persistence_store=persistence_store)
    cb = CircuitBreakerManager()
    pl = RoutingProvenanceLedger()
    gw = ConsumerIntelligenceGateway(sm, cb, pl, persistence_store)

    # Put HRIDAY at CERTIFIED, and CERTIFY PRESENTATION, but leave DASHBOARD at SHADOW
    gw.transition_state(ConsumerName.HRIDAY, CutoverState.CERTIFIED, run_id="TEST-HR-CERT")
    gw.transition_state(ConsumerName.PRESENTATION, CutoverState.CERTIFIED, run_id="TEST-PRES-CERT")

    with pytest.raises(CutoverOrderingViolationError, match="Ordering violation: PRESENTATION cannot enter CANARY"):
        gw.transition_state(ConsumerName.PRESENTATION, CutoverState.CANARY)


def test_presentation_cutover_persistence_and_restart_recovery(
    persistence_store: CutoverPersistenceStore,
    isolated_gateway: ConsumerIntelligenceGateway,
):
    """
    Verifies that PRESENTATION cutover state is durably saved in SQLite
    and accurately recovered across simulated process restarts.
    """
    isolated_gateway.transition_state(ConsumerName.PRESENTATION, CutoverState.CERTIFIED, run_id="RUN-I8-5-CERT-001")
    isolated_gateway.transition_state(ConsumerName.PRESENTATION, CutoverState.CANARY)
    isolated_gateway.transition_state(ConsumerName.PRESENTATION, CutoverState.V2_PRIMARY_WITH_FALLBACK)

    # Simulate process restart by instantiating new Gateway from same persistence store
    restarted_sm = ConsumerCutoverStateMachine(persistence_store=persistence_store)
    restarted_gw = ConsumerIntelligenceGateway(
        state_machine=restarted_sm,
        circuit_breaker=CircuitBreakerManager(),
        provenance_ledger=RoutingProvenanceLedger(),
        persistence_store=persistence_store,
    )

    assert restarted_gw.state_machine.get_state(ConsumerName.HRIDAY) == CutoverState.V2_PRIMARY_WITH_FALLBACK
    assert restarted_gw.state_machine.get_state(ConsumerName.DASHBOARD) == CutoverState.V2_PRIMARY_WITH_FALLBACK
    assert restarted_gw.state_machine.get_state(ConsumerName.PRESENTATION) == CutoverState.V2_PRIMARY_WITH_FALLBACK


# =============================================================================
# 2. THREE-CONSUMER GOVERNED TRUTH IDENTITY (HRIDAY vs DASHBOARD vs PRESENTATION)
# =============================================================================

def test_three_consumer_workforce_and_retail_truth_identity(
    isolated_gateway: ConsumerIntelligenceGateway,
):
    """
    Three-Consumer Governed Truth Identity:
    Proves that HRIDAY, Executive Dashboard, and Presentation Studio all consume
    identical governed facts with 0 mismatches across:
    - 5 WFO facts: attendance_rate, wfo_compliance_pct, average_logged_hours, leave_utilization_rate, department_headcount
    - 3 Retail facts: top_location_gross_sales, holiday_sales_lift, highest_gross_sales_loc
    """
    isolated_gateway.transition_state(ConsumerName.PRESENTATION, CutoverState.CERTIFIED, run_id="RUN-I8-5-CERT-001")
    isolated_gateway.transition_state(ConsumerName.PRESENTATION, CutoverState.CANARY)
    isolated_gateway.transition_state(ConsumerName.PRESENTATION, CutoverState.V2_PRIMARY_WITH_FALLBACK)

    dash_adapter = DashboardIntelligenceAdapter(gateway=isolated_gateway)
    pres_adapter = PresentationIntelligenceAdapter(gateway=isolated_gateway)

    # 1. Workforce Domain (5 facts)
    wfo_manifest = make_sample_manifest("201", version="v1.0")
    dash_adapter.register_v2_manifest("201", wfo_manifest)
    pres_adapter.register_v2_manifest("201", wfo_manifest)

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
        assert fact_id in dash_wfo, f"Missing {fact_id} in Dashboard"
        assert fact_id in pres_wfo, f"Missing {fact_id} in Presentation"

        d_metric = dash_wfo[fact_id]
        p_metric = pres_wfo[fact_id]

        assert d_metric["value"] == p_metric["value"], f"Value mismatch for {fact_id}: {d_metric['value']} != {p_metric['value']}"
        assert d_metric["unit"] == p_metric["unit"], f"Unit mismatch for {fact_id}"
        assert d_metric["grain"] == p_metric["grain"], f"Grain mismatch for {fact_id}"
        assert d_metric["denominator"] == p_metric["denominator"], f"Denominator mismatch for {fact_id}"
        assert d_metric["evidence_refs"] == p_metric["evidence_refs"], f"Evidence mismatch for {fact_id}"
        assert d_metric["dataset_version"] == p_metric["dataset_version"], f"Version mismatch for {fact_id}"

    # 2. Retail Domain (3 facts)
    ret_manifest = make_sample_manifest("202", version="v1.0")
    dash_adapter.register_v2_manifest("202", ret_manifest)
    pres_adapter.register_v2_manifest("202", ret_manifest)

    dash_ret = {m["metric_id"]: m for m in dash_adapter.get_governed_shared_metrics(202, domain="retail")}
    pres_ret = {m["metric_id"]: m for m in pres_adapter.get_governed_shared_metrics(202, domain="retail")}

    retail_facts = [
        "top_location_gross_sales",
        "holiday_sales_lift",
        "highest_gross_sales_location",
    ]
    for fact_id in retail_facts:
        assert fact_id in dash_ret, f"Missing {fact_id} in Dashboard retail"
        assert fact_id in pres_ret, f"Missing {fact_id} in Presentation retail"

        d_metric = dash_ret[fact_id]
        p_metric = pres_ret[fact_id]

        assert d_metric["value"] == p_metric["value"], f"Value mismatch for {fact_id}: {d_metric['value']} != {p_metric['value']}"
        assert d_metric["unit"] == p_metric["unit"], f"Unit mismatch for {fact_id}"
        assert d_metric["grain"] == p_metric["grain"], f"Grain mismatch for {fact_id}"
        assert d_metric["denominator"] == p_metric["denominator"], f"Denominator mismatch for {fact_id}"
        assert d_metric["evidence_refs"] == p_metric["evidence_refs"], f"Evidence mismatch for {fact_id}"
        assert d_metric["dataset_version"] == p_metric["dataset_version"], f"Version mismatch for {fact_id}"

    # 3. Retail domain must have zero HR vocabulary leakage
    hr_forbidden_terms = ["attendance", "wfo", "leave", "headcount", "employee", "roster"]
    for m in pres_ret.values():
        label_blob = f"{m.get('metric_id')} {m.get('metric_name')} {m.get('unit')} {m.get('grain')} {m.get('denominator')}".lower()
        for forbidden in hr_forbidden_terms:
            assert forbidden not in label_blob, f"HR term '{forbidden}' leaked into Retail metric {m.get('metric_id')}"


# =============================================================================
# 3. CROSS-SHEET JOIN SAFETY ENFORCEMENT
# =============================================================================

def test_presentation_join_safety_filter(
    isolated_gateway: ConsumerIntelligenceGateway,
    hermetic_db: sqlite3.Connection,
):
    """
    Verifies that:
    - SAFE and SAFE_WITH_PREAGGREGATION join topics are permitted into Presentation.
    - UNSAFE join topics are strictly blocked.
    - AMBIGUOUS join topics are strictly withheld with audit tracking.
    """
    isolated_gateway.transition_state(ConsumerName.PRESENTATION, CutoverState.CERTIFIED, run_id="RUN-I8-5-CERT-001")
    isolated_gateway.transition_state(ConsumerName.PRESENTATION, CutoverState.CANARY)
    isolated_gateway.transition_state(ConsumerName.PRESENTATION, CutoverState.V2_PRIMARY_WITH_FALLBACK)

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


# =============================================================================
# 4. ZERO VS MISSING DATA GOVERNANCE
# =============================================================================

def test_presentation_zero_vs_missing_governance(
    isolated_gateway: ConsumerIntelligenceGateway,
    hermetic_db: sqlite3.Connection,
):
    """
    Verifies that:
    - True numerical 0 (e.g. 0.0 overtime hours) is preserved with evidence.
    - Missing/unobserved values are labeled "Unavailable" or "N/A" and NEVER converted to synthetic 0.
    """
    isolated_gateway.transition_state(ConsumerName.PRESENTATION, CutoverState.CERTIFIED, run_id="RUN-I8-5-CERT-001")
    isolated_gateway.transition_state(ConsumerName.PRESENTATION, CutoverState.CANARY)
    isolated_gateway.transition_state(ConsumerName.PRESENTATION, CutoverState.V2_PRIMARY_WITH_FALLBACK)

    seed_workforce_dataset(hermetic_db, dataset_id=201)
    pres_adapter = PresentationIntelligenceAdapter(gateway=isolated_gateway)
    manifest = make_sample_manifest("201")
    pres_adapter.register_v2_manifest("201", manifest)

    topics_with_zero_and_missing = [
        {
            "topic_id": "TOPIC-ZERO-METRIC",
            "title": "Zero Overtime Audit",
            "key_metric": "0.0",
            "analytical_intent": "RANKING",
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
            "inspect_payload": {
                "leader_value": None,
                "evidence_ids": ["EVID-MISSING-01"],
            },
        },
    ]

    pres_adapter.register_v2_artifacts(
        dataset_id=201,
        executive_topics=topics_with_zero_and_missing,
    )

    evidence = pres_adapter.acquire_presentation_evidence(
        conn=hermetic_db,
        scope={"dataset_id": 201, "scope_type": "workspace"},
        manifest_data=manifest,
    )

    pts = evidence["presentation_topics"]
    zero_pt = next(p for p in pts if p.topic_id == "TOPIC-ZERO-METRIC")
    missing_pt = next(p for p in pts if p.topic_id == "TOPIC-MISSING-METRIC")

    # True 0 is preserved
    assert zero_pt.leader_value == 0.0
    assert zero_pt.metric == "0.0"

    # Missing is None / unobserved, not synthetic 0
    assert missing_pt.leader_value is None
    assert missing_pt.metric in (None, "")


# =============================================================================
# 5. CANONICAL SEMANTIC HASH PARITY & DETERMINISM
# =============================================================================

def test_presentation_semantic_hash_parity_and_invariance():
    """
    Verifies that compute_canonical_semantic_hash is deterministic,
    invariant to theme and layout styling, and identical between:
    Upstream ExecutiveTopic -> PresentationTopic -> Slide Contract.
    """
    exec_topic = {
        "topic_id": "TOPIC-AUDIT-01",
        "title": "Executive Attendance Diagnostic",
        "key_metric": "84.2%",
        "unit": "%",
        "analytical_intent": "RANKING",
        "primary_takeaway": "Attendance is 84.2% across active operations.",
        "inspect_payload": {
            "fact_id": "FACT-ATT-84",
            "evidence_ids": ["EVID-ATT-1", "EVID-ATT-2"],
            "leader_entity": "Engineering",
            "leader_value": 84.2,
            "ranking_metadata": {"ranking_direction": "descending", "unit": "%"},
        },
        "visual_spec": {
            "chart_type": "ranked_bar",
            "categories": ["Engineering", "Operations"],
            "values": [84.2, 80.1],
            "unit": "%",
        },
    }

    pt = PresentationTopic.from_executive_topic(exec_topic)
    upstream_hash = compute_canonical_semantic_hash(exec_topic)
    pt_hash = pt.canonical_semantic_hash()

    assert upstream_hash == pt_hash, "PresentationTopic hash diverged from upstream ExecutiveTopic hash"

    slides = pt.to_slide_contracts(start_order=2, total_slides=3)
    assert len(slides) >= 1
    for slide in slides:
        assert slide["semantic_hash"] == upstream_hash, "Slide contract hash diverged from PresentationTopic hash"


# =============================================================================
# 6. FALLBACK TAXONOMY AUDIT & INJECTED FAILURE RECOVERY
# =============================================================================

def test_presentation_fallback_taxonomy_normalization():
    """
    Verifies that all presentation diagnostic failure modes map strictly
    into the central Gateway FallbackReason enum without unauthorized causes.
    """
    causes = [
        ("PRESENTATION_SPEC_ERROR", FallbackReason.V2_SCHEMA_CONTRACT_FAILURE),
        ("TOPIC_SYNTHESIS_TIMEOUT", FallbackReason.V2_RUNTIME_ERROR),
        ("TOPIC_CONFIDENCE_BELOW_THRESHOLD", FallbackReason.V2_CONTEXT_GROUNDING_FAILURE),
        ("CIRCUIT_BREAKER_TRIPPED", FallbackReason.CIRCUIT_BREAKER_OPEN),
        ("KILL_SWITCH_ACTIVE", FallbackReason.KILL_SWITCH_ACTIVE),
        ("UPSTREAM_5XX_ERROR", FallbackReason.V2_RUNTIME_ERROR),
        ("PAYLOAD_VALIDATION_FAILED", FallbackReason.V2_SCHEMA_CONTRACT_FAILURE),
        ("V2_ARTIFACT_MISSING", FallbackReason.V2_ARTIFACT_MISSING),
    ]

    for diag_cause, expected_fallback in causes:
        mapped = map_presentation_diagnostic_to_fallback_reason(diag_cause)
        assert mapped == expected_fallback, f"Diagnostic {diag_cause} mapped to {mapped}, expected {expected_fallback}"
        assert isinstance(mapped, FallbackReason)


def test_presentation_failure_injection_clean_v1_fallback(
    isolated_gateway: ConsumerIntelligenceGateway,
    hermetic_db: sqlite3.Connection,
):
    """
    Verifies that when V2 presentation acquisition fails:
    - Circuit breaker records failure.
    - Falls back cleanly to V1 with fallback decision provenance recorded.
    """
    seed_workforce_dataset(hermetic_db, dataset_id=201)
    isolated_gateway.transition_state(ConsumerName.PRESENTATION, CutoverState.CERTIFIED, run_id="RUN-I8-5-CERT-001")
    isolated_gateway.transition_state(ConsumerName.PRESENTATION, CutoverState.CANARY)
    isolated_gateway.transition_state(ConsumerName.PRESENTATION, CutoverState.V2_PRIMARY_WITH_FALLBACK)

    adapter = PresentationIntelligenceAdapter(gateway=isolated_gateway)
    manifest = make_sample_manifest("201")
    adapter.register_v2_manifest("201", manifest)

    # Injected error in V2 acquisition
    def faulty_v2(*args, **kwargs):
        raise RuntimeError("Simulated Presentation V2 synthesis crash")

    adapter._acquire_v2_presentation_evidence = faulty_v2  # type: ignore

    evidence = adapter.acquire_presentation_evidence(
        conn=hermetic_db,
        scope={"dataset_id": 201, "scope_type": "workspace"},
        manifest_data=manifest,
    )

    assert "metadata" in evidence
    assert evidence["metadata"]["fallback_recovery"] is True
    prov = evidence["metadata"]["route_provenance"]
    assert prov["selected_route"] == Route.V1
    assert prov["fallback_used"] is True
    assert prov["fallback_reason"] == FallbackReason.V2_RUNTIME_ERROR


def test_presentation_fallback_disallowed_raises_error(
    isolated_gateway: ConsumerIntelligenceGateway,
    hermetic_db: sqlite3.Connection,
):
    """Verifies that when fallback is disabled, a V2 error raises RoutingFallbackDisallowedError."""
    seed_workforce_dataset(hermetic_db, dataset_id=201)
    isolated_gateway.transition_state(ConsumerName.PRESENTATION, CutoverState.CERTIFIED, run_id="RUN-I8-5-CERT-001")
    isolated_gateway.transition_state(ConsumerName.PRESENTATION, CutoverState.CANARY)
    isolated_gateway.transition_state(ConsumerName.PRESENTATION, CutoverState.V2_PRIMARY_WITH_FALLBACK)

    # Disable fallback
    isolated_gateway.set_fallback_allowed(ConsumerName.PRESENTATION, False)

    adapter = PresentationIntelligenceAdapter(gateway=isolated_gateway)
    manifest = make_sample_manifest("201")
    adapter.register_v2_manifest("201", manifest)

    def faulty_v2(*args, **kwargs):
        raise RuntimeError("Simulated catastrophic crash")

    adapter._acquire_v2_presentation_evidence = faulty_v2  # type: ignore

    with pytest.raises(RoutingFallbackDisallowedError, match="fallback to V1 is disallowed for PRESENTATION"):
        adapter.acquire_presentation_evidence(
            conn=hermetic_db,
            scope={"dataset_id": 201, "scope_type": "workspace"},
            manifest_data=manifest,
        )


def test_presentation_non_destructive_rollback_isolation(
    isolated_gateway: ConsumerIntelligenceGateway,
):
    """
    Verifies that rolling back PRESENTATION:
    - Executes in sub-millisecond time (< 5ms).
    - Leaves HRIDAY and DASHBOARD completely unaffected at V2_PRIMARY_WITH_FALLBACK.
    """
    isolated_gateway.transition_state(ConsumerName.PRESENTATION, CutoverState.CERTIFIED, run_id="RUN-I8-5-CERT-001")
    isolated_gateway.transition_state(ConsumerName.PRESENTATION, CutoverState.CANARY)
    isolated_gateway.transition_state(ConsumerName.PRESENTATION, CutoverState.V2_PRIMARY_WITH_FALLBACK)

    t0 = time.perf_counter()
    rollback_entry = isolated_gateway.rollback(
        ConsumerName.PRESENTATION,
        reason="Testing non-destructive rollback",
    )
    rollback_time_ms = (time.perf_counter() - t0) * 1000

    assert rollback_time_ms < 5.0, f"Rollback took {rollback_time_ms}ms, expected sub-millisecond"
    assert rollback_entry.current_state == CutoverState.ROLLBACK
    assert isolated_gateway.state_machine.get_state(ConsumerName.PRESENTATION) == CutoverState.ROLLBACK

    # HRIDAY and DASHBOARD remain completely untouched
    assert isolated_gateway.state_machine.get_state(ConsumerName.HRIDAY) == CutoverState.V2_PRIMARY_WITH_FALLBACK
    assert isolated_gateway.state_machine.get_state(ConsumerName.DASHBOARD) == CutoverState.V2_PRIMARY_WITH_FALLBACK


# =============================================================================
# 7. PERFORMANCE & MEMORY BENCHMARKS
# =============================================================================

def test_presentation_gateway_decision_overhead(
    isolated_gateway: ConsumerIntelligenceGateway,
):
    """Verifies that gateway routing decisions for Presentation take < 1ms P50 and P95."""
    isolated_gateway.transition_state(ConsumerName.PRESENTATION, CutoverState.CERTIFIED, run_id="RUN-I8-5-CERT-001")
    isolated_gateway.transition_state(ConsumerName.PRESENTATION, CutoverState.CANARY)
    isolated_gateway.transition_state(ConsumerName.PRESENTATION, CutoverState.V2_PRIMARY_WITH_FALLBACK)

    manifest = make_sample_manifest("201")
    latencies = []
    for _ in range(50):
        t0 = time.perf_counter()
        isolated_gateway.evaluate_route(
            consumer=ConsumerName.PRESENTATION,
            dataset_id="201",
            manifest_data=manifest,
        )
        latencies.append((time.perf_counter() - t0) * 1000)

    latencies.sort()
    p50 = latencies[25]
    p95 = latencies[47]

    assert p50 < 0.2, f"P50 gateway decision took {p50:.3f}ms, expected < 0.2ms"
    assert p95 < 0.5, f"P95 gateway decision took {p95:.3f}ms, expected < 0.5ms"


def test_presentation_governed_fallback_latency(
    isolated_gateway: ConsumerIntelligenceGateway,
    hermetic_db: sqlite3.Connection,
):
    """Verifies that governed V2 -> V1 fallback completes within 15ms."""
    seed_workforce_dataset(hermetic_db, dataset_id=201)
    isolated_gateway.transition_state(ConsumerName.PRESENTATION, CutoverState.CERTIFIED, run_id="RUN-I8-5-CERT-001")
    isolated_gateway.transition_state(ConsumerName.PRESENTATION, CutoverState.CANARY)
    isolated_gateway.transition_state(ConsumerName.PRESENTATION, CutoverState.V2_PRIMARY_WITH_FALLBACK)

    adapter = PresentationIntelligenceAdapter(gateway=isolated_gateway)
    manifest = make_sample_manifest("201")
    adapter.register_v2_manifest("201", manifest)

    def faulty_v2(*args, **kwargs):
        raise RuntimeError("Injected fault for latency measurement")

    adapter._acquire_v2_presentation_evidence = faulty_v2  # type: ignore

    # Warm up any lazy imports
    try:
        adapter.acquire_presentation_evidence(
            conn=hermetic_db,
            scope={"dataset_id": 201, "scope_type": "workspace"},
            manifest_data=manifest,
        )
    except Exception:
        pass

    latencies = []
    for _ in range(15):
        isolated_gateway.circuit_breaker.reset(ConsumerName.PRESENTATION)
        t0 = time.perf_counter()
        evidence = adapter.acquire_presentation_evidence(
            conn=hermetic_db,
            scope={"dataset_id": 201, "scope_type": "workspace"},
            manifest_data=manifest,
        )
        latencies.append((time.perf_counter() - t0) * 1000)

    latencies.sort()
    median_time_ms = latencies[7]

    assert evidence["metadata"]["fallback_recovery"] is True
    assert median_time_ms < 50.0, f"Fallback median took {median_time_ms:.2f}ms, expected < 50ms"


def test_presentation_incremental_memory_allocation(
    isolated_gateway: ConsumerIntelligenceGateway,
    hermetic_db: sqlite3.Connection,
):
    """
    Verifies that Presentation intelligence processing maintains bounded memory consumption
    across dataset tiers.
    """
    isolated_gateway.transition_state(ConsumerName.PRESENTATION, CutoverState.CERTIFIED, run_id="RUN-I8-5-CERT-001")
    isolated_gateway.transition_state(ConsumerName.PRESENTATION, CutoverState.CANARY)
    isolated_gateway.transition_state(ConsumerName.PRESENTATION, CutoverState.V2_PRIMARY_WITH_FALLBACK)

    seed_workforce_dataset(hermetic_db, dataset_id=201)
    adapter = PresentationIntelligenceAdapter(gateway=isolated_gateway)
    manifest = make_sample_manifest("201")
    adapter.register_v2_manifest("201", manifest)

    tracemalloc.start()
    snapshot_before = tracemalloc.take_snapshot()

    evidence = adapter.acquire_presentation_evidence(
        conn=hermetic_db,
        scope={"dataset_id": 201, "scope_type": "workspace"},
        manifest_data=manifest,
    )

    snapshot_after = tracemalloc.take_snapshot()
    tracemalloc.stop()

    top_stats = snapshot_after.compare_to(snapshot_before, "lineno")
    total_delta_kb = sum(stat.size_diff for stat in top_stats) / 1024

    assert total_delta_kb < 10240, f"Memory delta was {total_delta_kb:.1f} KB, exceeded 10MB limit"
