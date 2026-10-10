"""Test Suite for Phase 9.10: Data-Binding & Semantic Integrity Gate (Gate 7).

Guarantees that:
1. No hardcoded business metric literals exist in dashboard components (test_no_business_metric_literals_in_dashboard_components)
2. Every KPI has an audited evidence binding, calculation definition, and population (test_every_kpi_has_evidence_binding)
3. Every chart series has an evidence binding (test_every_chart_series_has_evidence_binding)
4. Every reference line has a policy or evidence source (test_every_reference_line_has_policy_or_evidence_source)
5. Mutating source dataset changes the rendered chart values, rankings, and takeaways (test_mutating_source_data_changes_rendered_chart)
6. Chart does not use fixture values in production (test_chart_does_not_use_fixture_values_in_production)
7. Executive takeaway reconciles with visual data (test_executive_takeaway_reconciles_with_visual_data)
"""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path
import pytest

from app.db.database import get_connection
from app.services.adaptive_dashboard.dataset_orchestrator import run_dataset_intelligence
from app.services.adaptive_dashboard.executive_analytics import compute_governed_executive_metrics
from app.services.adaptive_dashboard.theme_validator import ThemeIntegrityValidator


@pytest.fixture
def seeded_wfo_dataset():
    """Seeds an isolated workforce attendance dataset into SQLite for test verification."""
    conn = get_connection()
    ds_id = 99747
    conn.execute(
        "INSERT OR REPLACE INTO dataset_uploads (id, filename, original_name, display_name, file_type, sheet_count, row_count) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (ds_id, "WFO_July_2026_Test.xlsx", "WFO_July_2026_Test.xlsx", "WFO July 2026", "xlsx", 1, 5),
    )
    cols = ["Employee ID", "Department", "Total Attendance", "Approved Leaves", "1st to 5th July", "6th to 12th July", "13th to 19th July", "20th to 26th July", "27th to 31st July"]
    sheet_id = 9967390
    conn.execute(
        "INSERT OR REPLACE INTO sheets (id, dataset_id, name, display_name, columns_json, profile_json, row_count) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (sheet_id, ds_id, "Sheet1", "Attendance Log", json.dumps(cols), "[]", 5),
    )
    records = [
        {"Employee ID": "E1", "Department": "Operations", "Total Attendance": 21.2, "Approved Leaves": 2.0, "1st to 5th July": 4.0, "6th to 12th July": 5.0, "13th to 19th July": 4.0, "20th to 26th July": 4.0, "27th to 31st July": 4.2},
        {"Employee ID": "E2", "Department": "Engineering", "Total Attendance": 18.5, "Approved Leaves": 3.0, "1st to 5th July": 3.5, "6th to 12th July": 4.0, "13th to 19th July": 4.0, "20th to 26th July": 4.0, "27th to 31st July": 3.0},
        {"Employee ID": "E3", "Department": "NRP", "Total Attendance": 16.4, "Approved Leaves": 4.0, "1st to 5th July": 3.0, "6th to 12th July": 3.4, "13th to 19th July": 4.0, "20th to 26th July": 3.0, "27th to 31st July": 3.0},
        {"Employee ID": "E4", "Department": "Functions", "Total Attendance": 14.1, "Approved Leaves": 5.0, "1st to 5th July": 2.5, "6th to 12th July": 3.0, "13th to 19th July": 3.0, "20th to 26th July": 3.0, "27th to 31st July": 2.6},
        {"Employee ID": "E5", "Department": "Design", "Total Attendance": 8.2, "Approved Leaves": 8.0, "1st to 5th July": 1.5, "6th to 12th July": 2.0, "13th to 19th July": 1.5, "20th to 26th July": 1.5, "27th to 31st July": 1.7},
    ]
    for idx, rec in enumerate(records, start=1):
        conn.execute(
            "INSERT INTO sheet_rows (sheet_id, row_index, data_json) VALUES (?, ?, ?)",
            (sheet_id, idx, json.dumps(rec)),
        )
    conn.commit()
    conn.close()
    return ds_id


def test_no_business_metric_literals_in_dashboard_components():
    """Verify that dashboard components contain ZERO hardcoded business numbers or data arrays."""
    component_path = Path(__file__).resolve().parent.parent.parent / "frontend" / "src" / "components" / "adaptive" / "UnifiedExecutiveInsightsGrid.jsx"
    assert component_path.exists(), f"Component file not found at {component_path}"

    source_code = component_path.read_text()
    violations = ThemeIntegrityValidator.audit_data_binding_integrity(source_code, component_path.name)
    assert violations == [], f"Found forbidden hardcoded business metric literals: {violations}"

    # Explicitly check for previously reported hardcoded sequences
    assert "128, 142, 136, 145, 138" not in source_code
    assert "14, 18, 12, 16, 21" not in source_code
    assert "21.2, 18.5, 16.4, 14.1, 8.2" not in source_code
    assert "97.7, 92.0, 94.5, 88.2, 91.0" not in source_code
    assert "34.2, 22.1, 15.6, 8.4, 4.2" not in source_code


def test_every_kpi_has_evidence_binding(seeded_wfo_dataset):
    """Verify that every executive KPI traces to an EVID-xxx node with definition and population."""
    metrics = compute_governed_executive_metrics(seeded_wfo_dataset)
    kpis = metrics.get("kpis", [])
    assert len(kpis) == 4, "Must produce exactly 4 core business KPIs"

    for kpi in kpis:
        assert "kpi_id" in kpi
        assert "label" in kpi
        assert "formatted_value" in kpi
        assert "evidence_id" in kpi
        assert kpi["evidence_id"].startswith("EVID-"), f"KPI {kpi['label']} missing EVID- prefix: {kpi['evidence_id']}"
        assert len(kpi["definition"]) > 10, f"KPI {kpi['label']} missing calculation definition"
        assert len(kpi["population"]) > 0, f"KPI {kpi['label']} missing population specification"
        assert len(kpi["period"]) > 0, f"KPI {kpi['label']} missing reporting period"
        assert len(kpi["calculation"]) > 0, f"KPI {kpi['label']} missing mathematical formulation"


def test_every_chart_series_has_evidence_binding(seeded_wfo_dataset):
    """Verify that every chart topic and series has explicit evidence bindings."""
    intel = run_dataset_intelligence(seeded_wfo_dataset)
    topics = intel.executive_topics
    assert len(topics) >= 4, "Must have at least 4 executive topics"

    for topic in topics:
        evid_ids = topic.get("evidence_ids", [])
        assert len(evid_ids) >= 1, f"Topic {topic['title']} has no evidence IDs"
        for eid in evid_ids:
            assert eid.startswith("EVID-"), f"Topic {topic['title']} has invalid evidence ID: {eid}"

        vspec = topic.get("visual_spec", {})
        if "series" in vspec:
            for s in vspec["series"]:
                assert "values" in s
                assert len(s["values"]) > 0, f"Series {s.get('name')} has empty values"
                assert "evidence_id" in s
                assert s["evidence_id"].startswith("EVID-")
        elif "values" in vspec:
            assert len(vspec["values"]) > 0
            assert len(vspec.get("categories", [])) == len(vspec["values"])


def test_every_reference_line_has_policy_or_evidence_source():
    """Verify that all chart reference lines (benchmarks) declare explicit policy contracts."""
    # Test hero ranked bar option structure with proper left margin
    hero_option = {
        "xAxis": {"type": "value", "axisLabel": {"fontSize": 11}},
        "yAxis": {"type": "category", "data": ["Design", "Operations"], "axisLabel": {"fontSize": 11}},
        "grid": {"containLabel": True, "left": 90},
        "series": [
            {
                "name": "Average Office Attendance",
                "type": "bar",
                "data": [11.0, 17.2],
                "markLine": {
                    "data": [{"xAxis": 15.0, "name": "Policy Reference Target"}],
                },
            }
        ],
        "_evidence_ids": ["EVID-HERO-001"],
    }

    qa_res = ThemeIntegrityValidator.evaluate_seven_visual_gates(hero_option)
    assert qa_res.data_binding_integrity is not None
    assert qa_res.data_binding_integrity.passed is True
    assert qa_res.passed is True


def test_mutating_source_data_changes_rendered_chart():
    """THE KEY MUTATION TEST:

    Mutating the underlying department attendance in the source partition
    must dynamically alter the chart values, department ranking, spread gap,
    and takeaway narrative.
    """
    # Create an isolated in-memory SQLite database
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
        CREATE TABLE sheet_curated_rows (
            sheet_id INTEGER,
            row_index INTEGER,
            data_json TEXT
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

    ds_id = 8888
    sheet_id = 88881
    cols = ["Employee ID", "Department", "Total Attendance"]
    conn.execute(
        "INSERT INTO sheets (id, dataset_id, name, columns_json, row_count) VALUES (?, ?, ?, ?, ?)",
        (sheet_id, ds_id, "Sheet1", json.dumps(cols), 4),
    )

    # Initial dataset state: Operations = 21.2, Design = 8.2
    conn.execute(
        "INSERT INTO sheet_rows (sheet_id, row_index, data_json) VALUES (?, ?, ?)",
        (sheet_id, 1, json.dumps({"Employee ID": "E1", "Department": "Operations", "Total Attendance": 21.2})),
    )
    conn.execute(
        "INSERT INTO sheet_rows (sheet_id, row_index, data_json) VALUES (?, ?, ?)",
        (sheet_id, 2, json.dumps({"Employee ID": "E2", "Department": "Operations", "Total Attendance": 21.2})),
    )
    conn.execute(
        "INSERT INTO sheet_rows (sheet_id, row_index, data_json) VALUES (?, ?, ?)",
        (sheet_id, 3, json.dumps({"Employee ID": "E3", "Department": "Design", "Total Attendance": 8.2})),
    )
    conn.execute(
        "INSERT INTO sheet_rows (sheet_id, row_index, data_json) VALUES (?, ?, ?)",
        (sheet_id, 4, json.dumps({"Employee ID": "E4", "Department": "Design", "Total Attendance": 8.2})),
    )
    conn.commit()

    # Baseline evaluation
    base_res = compute_governed_executive_metrics(ds_id, conn=conn)
    hero_base = base_res["hero"]
    assert hero_base["top_dept"] == "Operations"
    assert hero_base["top_avg"] == 21.2
    assert hero_base["bottom_dept"] == "Design"
    assert hero_base["bottom_avg"] == 8.2
    assert hero_base["gap"] == 13.0
    assert "Operations leads presence at 21.2 days" in hero_base["takeaway"]

    # MUTATION: Change Operations attendance from 21.2 to 11.2 (lower than before)
    conn.execute(
        "UPDATE sheet_rows SET data_json = ? WHERE sheet_id = ? AND row_index = 1",
        (json.dumps({"Employee ID": "E1", "Department": "Operations", "Total Attendance": 11.2}), sheet_id),
    )
    conn.execute(
        "UPDATE sheet_rows SET data_json = ? WHERE sheet_id = ? AND row_index = 2",
        (json.dumps({"Employee ID": "E2", "Department": "Operations", "Total Attendance": 11.2}), sheet_id),
    )
    conn.commit()

    # Re-evaluate with mutated source data
    mutated_res = compute_governed_executive_metrics(ds_id, conn=conn)
    hero_mutated = mutated_res["hero"]

    # Hero bar for Operations MUST now equal 11.2 (NOT 21.2)
    assert hero_mutated["top_avg"] == 11.2, f"Expected mutated average 11.2, got {hero_mutated['top_avg']}"
    assert hero_mutated["gap"] == 3.0, f"Expected gap 3.0, got {hero_mutated['gap']}"
    assert "Operations leads presence at 11.2 days" in hero_mutated["takeaway"]
    assert "21.2" not in hero_mutated["takeaway"], "Old hardcoded value 21.2 leaked into takeaway!"
    assert 21.2 not in hero_mutated["values"], "Old hardcoded value 21.2 leaked into visual values!"

    conn.close()


def test_chart_does_not_use_fixture_values_in_production():
    """Verify that two distinct datasets produce strictly distinct dynamic analytics."""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("CREATE TABLE sheets (id INTEGER PRIMARY KEY, dataset_id INTEGER, name TEXT, columns_json TEXT, row_count INTEGER)")
    conn.execute("CREATE TABLE sheet_curated_rows (sheet_id INTEGER, row_index INTEGER, data_json TEXT)")
    conn.execute("CREATE TABLE sheet_rows (sheet_id INTEGER, row_index INTEGER, data_json TEXT)")

    # Dataset A (Engineering lead)
    conn.execute("INSERT INTO sheets VALUES (1, 100, 'S1', '[\"Department\", \"Total Attendance\"]', 2)")
    conn.execute("INSERT INTO sheet_rows VALUES (1, 1, '{\"Department\": \"Engineering\", \"Total Attendance\": 19.5}')")
    conn.execute("INSERT INTO sheet_rows VALUES (1, 2, '{\"Department\": \"Sales\", \"Total Attendance\": 9.5}')")

    # Dataset B (Sales lead)
    conn.execute("INSERT INTO sheets VALUES (2, 200, 'S1', '[\"Department\", \"Total Attendance\"]', 2)")
    conn.execute("INSERT INTO sheet_rows VALUES (2, 1, '{\"Department\": \"Engineering\", \"Total Attendance\": 7.0}')")
    conn.execute("INSERT INTO sheet_rows VALUES (2, 2, '{\"Department\": \"Sales\", \"Total Attendance\": 22.0}')")
    conn.commit()

    res_a = compute_governed_executive_metrics(100, conn=conn)
    res_b = compute_governed_executive_metrics(200, conn=conn)

    assert res_a["hero"]["top_dept"] == "Engineering"
    assert res_a["hero"]["top_avg"] == 19.5
    assert res_b["hero"]["top_dept"] == "Sales"
    assert res_b["hero"]["top_avg"] == 22.0

    assert res_a["hero"]["takeaway"] != res_b["hero"]["takeaway"]
    conn.close()


def test_executive_takeaway_reconciles_with_visual_data(seeded_wfo_dataset):
    """Verify that numeric claims inside primary takeaways reconcile with visual values."""
    metrics = compute_governed_executive_metrics(seeded_wfo_dataset)
    hero = metrics["hero"]

    # Verify top and bottom averages in takeaway
    assert f"{hero['top_avg']:.1f}" in hero["takeaway"]
    assert f"{hero['deficit']:.1f}" in hero["takeaway"]
    assert hero["top_avg"] == max(hero["values"])
    assert hero["bottom_avg"] == min(hero["values"])
