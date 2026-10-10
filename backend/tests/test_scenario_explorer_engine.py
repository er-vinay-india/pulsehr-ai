"""Test Suite for Phase 10: Executive Scenario Explorer Engine.

Verifies:
1. Users manipulate GOVERNED BUSINESS LEVERS ONLY (required office days/week, leave exemption ratio, department overrides).
2. Absolute separation: EVID-xxx (observed truth) vs SCEN-xxx (simulated outcome).
3. Every scenario displays: Baseline, Scenario, Delta, Assumptions, Confidence, Affected Population.
4. Deterministic computation: identical parameters produce identical results.
5. Zero contamination / mutation of underlying SQLite tables or Evidence Graph.
"""
from __future__ import annotations

import json
import sqlite3
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services.adaptive_dashboard.scenario_engine import (
    DepartmentScenarioImpact,
    DeterministicScenarioEngine,
    GovernedScenarioCard,
    GovernedScenarioParameters,
    ScenarioClassification,
)


@pytest.fixture
def mock_scenario_db():
    """In-memory SQLite database with controlled department records for deterministic test assertions."""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute(
        """
        CREATE TABLE sheets (
            id INTEGER PRIMARY KEY,
            dataset_id INTEGER,
            name TEXT,
            columns_json TEXT,
            row_count INTEGER
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE sheet_rows (
            sheet_id INTEGER,
            row_index INTEGER,
            data_json TEXT
        )
        """
    )

    ds_id = 9101
    sheet_id = 91011
    cols = ["Employee ID", "Department", "Total Attendance", "Approved Leaves"]
    conn.execute(
        "INSERT INTO sheets VALUES (?, ?, ?, ?, ?)",
        (sheet_id, ds_id, "WFO_Test", json.dumps(cols), 4),
    )

    # E1: Ops (Att=16, Leave=1) -> Base target = 14d -> COMPLIANT (16 >= 14)
    # E2: Ops (Att=12, Leave=0) -> Base target = 15d -> NON-COMPLIANT (12 < 15)
    # E3: Design (Att=10, Leave=2) -> Base target = 13d -> NON-COMPLIANT (10 < 13)
    # E4: Design (Att=9, Leave=0) -> Base target = 15d -> NON-COMPLIANT (9 < 15)
    rows = [
        {"Employee ID": "E1", "Department": "Operations", "Total Attendance": 16.0, "Approved Leaves": 1.0},
        {"Employee ID": "E2", "Department": "Operations", "Total Attendance": 12.0, "Approved Leaves": 0.0},
        {"Employee ID": "E3", "Department": "Design", "Total Attendance": 10.0, "Approved Leaves": 2.0},
        {"Employee ID": "E4", "Department": "Design", "Total Attendance": 9.0, "Approved Leaves": 0.0},
    ]
    for idx, r in enumerate(rows, start=1):
        conn.execute("INSERT INTO sheet_rows VALUES (?, ?, ?)", (sheet_id, idx, json.dumps(r)))
    conn.commit()
    yield conn, ds_id
    conn.close()


def test_governed_business_levers_only(mock_scenario_db):
    """Verify that only governed levers (days/week, leave credit ratio, department targets)

    alter the simulation deterministically.
    """
    conn, ds_id = mock_scenario_db

    # Baseline: 3 days/week, 1.0 exemption ratio
    # Targets:
    # E1 (16d att, 1d leave): req = max(0, 15 - 1) = 14d -> Compliant
    # E2 (12d att, 0d leave): req = max(0, 15 - 0) = 15d -> Non-compliant
    # E3 (10d att, 2d leave): req = max(0, 15 - 2) = 13d -> Non-compliant
    # E4 (9d att, 0d leave):  req = max(0, 15 - 0) = 15d -> Non-compliant
    # Baseline compliance = 1/4 = 25.0%

    base_card = DeterministicScenarioEngine.simulate_scenario(
        dataset_id=ds_id,
        params=GovernedScenarioParameters(days_per_week=3.0, leave_exemption_ratio=1.0),
        conn=conn,
    )
    assert base_card.baseline_compliance == 25.0
    assert base_card.projected_compliance == 25.0
    assert base_card.delta_compliance_pts == 0.0

    # Lever 1: Shift required days/week from 3 -> 2
    # New target baseline: 5 weeks * 2 days = 10 days
    # E1: req = 10 - 1 = 9d -> Compliant (16 >= 9)
    # E2: req = 10 - 0 = 10d -> Compliant (12 >= 10)
    # E3: req = 10 - 2 = 8d -> Compliant (10 >= 8)
    # E4: req = 10 - 0 = 10d -> Non-compliant (9 < 10)
    # Projected compliance = 3/4 = 75.0% (+50.0 pts delta)
    scen_2d = DeterministicScenarioEngine.simulate_scenario(
        dataset_id=ds_id,
        params=GovernedScenarioParameters(days_per_week=2.0, leave_exemption_ratio=1.0),
        scenario_code="SCEN-001",
        conn=conn,
    )
    assert scen_2d.baseline_compliance == 25.0
    assert scen_2d.projected_compliance == 75.0
    assert scen_2d.delta_compliance_pts == +50.0


def test_absolute_separation_of_evid_and_scen(mock_scenario_db):
    """Verify that scenario tokens (SCEN-xxx) never collide with or overwrite observed truth (EVID-xxx)."""
    conn, ds_id = mock_scenario_db

    scen_card = DeterministicScenarioEngine.simulate_scenario(
        dataset_id=ds_id,
        params=GovernedScenarioParameters(days_per_week=2.0),
        scenario_code="SCEN-001",
        conn=conn,
    )

    # Token Prefix Verification
    assert scen_card.scenario_id.startswith("SCEN-"), f"Scenario ID must start with SCEN-: {scen_card.scenario_id}"
    assert scen_card.baseline_evidence_id.startswith("EVID-"), f"Baseline link must start with EVID-: {scen_card.baseline_evidence_id}"
    assert scen_card.is_simulated is True

    # Database immutability check
    rows_count = conn.execute("SELECT count(*) FROM sheet_rows WHERE sheet_id = 91011").fetchone()[0]
    assert rows_count == 4, "Simulation must NEVER mutate sheet rows"

    # Verify no SCEN token was injected into the persistent database
    scen_in_db = conn.execute("SELECT data_json FROM sheet_rows WHERE data_json LIKE '%SCEN-%'").fetchall()
    assert len(scen_in_db) == 0, "Scenario tokens must NEVER contaminate database storage"


def test_every_scenario_displays_required_decision_metadata(mock_scenario_db):
    """Phase 10 Mandate: Every scenario MUST display:

    1. Baseline
    2. Scenario
    3. Delta
    4. Assumptions
    5. Confidence
    6. Affected population
    """
    conn, ds_id = mock_scenario_db

    scen_card = DeterministicScenarioEngine.simulate_scenario(
        dataset_id=ds_id,
        params=GovernedScenarioParameters(
            days_per_week=2.0,
            leave_exemption_ratio=1.0,
            custom_name="Flexible 2-Day Hybrid Model",
        ),
        conn=conn,
    )
    data = scen_card.to_dict()

    # 1. Baseline
    assert "baseline_policy" in data
    assert "3 days/week" in data["baseline_policy"]
    assert "baseline_compliance" in data

    # 2. Scenario
    assert "scenario_policy" in data
    assert "2 days/week" in data["scenario_policy"]
    assert "projected_compliance" in data

    # 3. Delta
    assert "delta_compliance_pts" in data
    assert data["formatted_delta"] == "+50.0 pts"

    # 4. Assumptions
    assert "assumptions" in data
    assert len(data["assumptions"]) >= 3
    assert any("leave exemption" in a.lower() for a in data["assumptions"])
    assert any("tracking periods" in a.lower() for a in data["assumptions"])

    # 5. Confidence
    assert "confidence_score" in data
    assert data["confidence_score"] >= 90.0

    # 6. Affected Population
    assert "affected_population" in data
    assert "4 eligible employees" in data["affected_population"]

    # 7. Scientific Counterfactual Semantics
    assert "counterfactual_compliance" in data
    assert "interpretation" in data
    assert "evidence_strength" in data
    assert data["evidence_strength"] == "Deterministic historical replay"
    assert "counterfactual_disclaimer" in data


def test_scientific_counterfactual_semantics_and_classification(mock_scenario_db):
    """Verify scientific semantics:
    1. Scenario classification in (POLICY_REPLAY, COUNTERFACTUAL, FORECAST, OPTIMIZATION, STRESS_TEST).
    2. Counterfactual compliance representation.
    3. Precise interpretation narrative ('would have satisfied').
    4. Evidence strength = Deterministic historical replay.
    5. Explicit non-predictive adaptation disclaimer.
    """
    conn, ds_id = mock_scenario_db
    benchmarks = DeterministicScenarioEngine.get_benchmark_scenarios(dataset_id=ds_id, conn=conn)
    assert len(benchmarks) == 4

    # SCEN-001 is POLICY_REPLAY
    b1 = benchmarks[0].to_dict()
    assert b1["scenario_type"] in [ScenarioClassification.POLICY_REPLAY.value, ScenarioClassification.COUNTERFACTUAL.value]
    assert b1["evidence_strength"] == "Deterministic historical replay"
    assert "would have satisfied" in b1["interpretation"]
    assert "does not predict behavioral adaptation" in b1["counterfactual_disclaimer"]
    assert "counterfactual_compliance" in b1
    assert b1["counterfactual_compliance"] == b1["projected_compliance"]

    # Valid classifications check
    valid_types = {e.value for e in ScenarioClassification}
    for b in benchmarks:
        assert b.scenario_type in valid_types


def test_department_specific_policy_overrides(mock_scenario_db):
    """Verify that management can simulate department-specific policy targets (e.g. Design: 2d, Ops: 3d)."""
    conn, ds_id = mock_scenario_db

    # Baseline (3d all): 25.0%
    # Override: Design targets 2d/wk, Ops remains 3d/wk
    # Ops: E1 (16 >= 14 -> Compliant), E2 (12 < 15 -> Non-compliant) -> 1/2
    # Design: E3 (10 >= 8 -> Compliant), E4 (9 < 10 -> Non-compliant) -> 1/2
    # Organization total = 2/4 = 50.0% (+25.0 pts)

    custom_params = GovernedScenarioParameters(
        days_per_week=3.0,
        department_targets={"Design": 2.0},
    )
    scen = DeterministicScenarioEngine.simulate_scenario(
        dataset_id=ds_id,
        params=custom_params,
        scenario_code="SCEN-004",
        conn=conn,
    )

    assert scen.projected_compliance == 50.0
    assert scen.delta_compliance_pts == +25.0

    # Check department breakdowns
    dept_map = {d.department: d for d in scen.department_impacts}
    assert "Design" in dept_map
    assert "Operations" in dept_map
    assert dept_map["Design"].scenario_target_days == 10.0
    assert dept_map["Operations"].scenario_target_days == 15.0
    assert dept_map["Design"].projected_compliant_pct == 50.0


def test_leave_exemption_credit_ratio_lever(mock_scenario_db):
    """Verify that shifting leave credit ratio (1.0x -> 0.0x strict) reduces compliance deterministically."""
    conn, ds_id = mock_scenario_db

    # Under 0.0x ratio (zero exemption credit):
    # E1: att=16, req=15 -> Compliant
    # E2: att=12, req=15 -> Non-compliant
    # E3: att=10, req=15 -> Non-compliant (previously benefited from 2d leave credit)
    # E4: att=9,  req=15 -> Non-compliant
    # Compliance = 1/4 = 25.0%

    strict_params = GovernedScenarioParameters(
        days_per_week=3.0,
        leave_exemption_ratio=0.0,
    )
    scen = DeterministicScenarioEngine.simulate_scenario(
        dataset_id=ds_id,
        params=strict_params,
        scenario_code="SCEN-STRICT",
        conn=conn,
    )

    assert scen.projected_compliance == 25.0
    assert any("0x" in a for a in scen.assumptions)


def test_api_scenarios_endpoints():
    """Verify that FastAPI endpoints serve pre-computed benchmarks and accept simulations."""
    client = TestClient(app)

    # 1. GET /api/adaptive-dashboard/scenarios
    resp_get = client.get("/api/adaptive-dashboard/scenarios?dataset_id=99747")
    assert resp_get.status_code == 200
    data_get = resp_get.json()
    assert "governed_levers" in data_get
    assert len(data_get["governed_levers"]) >= 3
    assert "benchmark_scenarios" in data_get
    assert len(data_get["benchmark_scenarios"]) == 4

    # Verify SCEN-001 in benchmarks
    scen_1 = data_get["benchmark_scenarios"][0]
    assert scen_1["scenario_id"] == "SCEN-001"
    assert scen_1["baseline_evidence_id"].startswith("EVID-")
    assert "baseline_policy" in scen_1
    assert "scenario_policy" in scen_1
    assert "delta_compliance_pts" in scen_1
    assert "assumptions" in scen_1
    assert "confidence_score" in scen_1
    assert "affected_population" in scen_1

    # 2. POST /api/adaptive-dashboard/scenarios/simulate
    payload = {
        "dataset_id": 99747,
        "days_per_week": 2.0,
        "leave_exemption_ratio": 1.0,
        "target_compliance_threshold": 80.0,
        "period_weeks": 5.0,
    }
    resp_post = client.post("/api/adaptive-dashboard/scenarios/simulate", json=payload)
    assert resp_post.status_code == 200
    data_post = resp_post.json()
    assert data_post["scenario_id"] == "SCEN-CUSTOM"
    assert data_post["projected_compliance"] > data_post["baseline_compliance"]
    assert data_post["is_simulated"] is True
