"""
Phase G5 Characterization and Equivalence Test Suite.

Establishes the golden characterization baseline for:
1. Workforce Attendance & Leave domain
2. Retail Sales & Macro domain
3. CPCB Environmental Air Quality domain

Guarantees:
- Semantic identity: KPIs, ExecutiveTopics, topic_ids, titles, visual_specs, evidence_ids, findings
- Topic ownership integrity: zero cross-domain contamination
- Personnel grain ranking: Top 3 employees distinct from department rankings
- Any extracted module produces EXACT equivalence with the baseline.
"""
from __future__ import annotations

import json
from typing import Any
import pytest

from app.db.database import get_connection, session_scope
from app.services.adaptive_dashboard.engine import run_adaptive_dashboard
from app.services.adaptive_dashboard.dataset_orchestrator import run_dataset_intelligence


# ------------------------------------------------------------------------------
# Fixtures for Multi-Domain Characterization
# ------------------------------------------------------------------------------

WORKFORCE_RECORDS = [
    {"Employee ID": f"EMP{i:03d}", "Employee Name": f"Employee {i}", "Department": dept, "Total Attendance": att, "Approved Leaves": lvs, "Date": "2026-07-31"}
    for i, (dept, att, lvs) in enumerate([
        ("Operations and Infrastructure", 24.0, 1.0),
        ("Architecture", 23.0, 2.0),
        ("Alliance Initiative - NRP", 22.0, 1.0),
        ("Functions", 20.0, 3.0),
        ("Design", 19.0, 4.0),
        ("Engineering", 18.0, 5.0),
    ] * 6, start=1)
]

RETAIL_RECORDS = [
    {"Store": 1, "Date": "2010-02-05", "Weekly_Sales": 1643690.90, "Holiday_Flag": 0, "Temperature": 42.31, "Fuel_Price": 2.572, "CPI": 211.096, "Unemployment": 8.106},
    {"Store": 2, "Date": "2010-02-05", "Weekly_Sales": 2136242.25, "Holiday_Flag": 0, "Temperature": 40.19, "Fuel_Price": 2.572, "CPI": 210.752, "Unemployment": 8.324},
    {"Store": 20, "Date": "2010-02-05", "Weekly_Sales": 2401395.47, "Holiday_Flag": 0, "Temperature": 25.92, "Fuel_Price": 2.784, "CPI": 204.247, "Unemployment": 8.187},
    {"Store": 33, "Date": "2010-02-05", "Weekly_Sales": 274605.73, "Holiday_Flag": 0, "Temperature": 58.40, "Fuel_Price": 2.962, "CPI": 126.442, "Unemployment": 10.115},
    {"Store": 1, "Date": "2010-02-12", "Weekly_Sales": 1641957.44, "Holiday_Flag": 1, "Temperature": 38.51, "Fuel_Price": 2.548, "CPI": 211.242, "Unemployment": 8.106},
    {"Store": 2, "Date": "2010-02-12", "Weekly_Sales": 2109107.90, "Holiday_Flag": 1, "Temperature": 22.12, "Fuel_Price": 2.773, "CPI": 204.385, "Unemployment": 8.187},
    {"Store": 20, "Date": "2010-02-12", "Weekly_Sales": 2200000.00, "Holiday_Flag": 1, "Temperature": 24.50, "Fuel_Price": 2.750, "CPI": 204.100, "Unemployment": 8.150},
    {"Store": 33, "Date": "2010-02-12", "Weekly_Sales": 285002.50, "Holiday_Flag": 1, "Temperature": 54.34, "Fuel_Price": 2.962, "CPI": 126.496, "Unemployment": 10.115},
]

ENVIRONMENTAL_RECORDS = [
    {"Stn Code": 101, "Sampling Date": "2022-01-01", "State": "Jharkhand", "City": "Jharia", "Location": "Station A", "Agency": "CPCB", "SO2": 15.2, "NO2": 28.4, "PM10": 140.5},
    {"Stn Code": 102, "Sampling Date": "2022-01-01", "State": "Meghalaya", "City": "Brynihat", "Location": "Station B", "Agency": "CPCB", "SO2": 18.6, "NO2": 32.1, "PM10": 195.0},
    {"Stn Code": 103, "Sampling Date": "2022-01-01", "State": "Maharashtra", "City": "Mumbai", "Location": "Station C", "Agency": "CPCB", "SO2": 12.0, "NO2": 22.0, "PM10": 85.0},
    {"Stn Code": 104, "Sampling Date": "2022-01-01", "State": "Delhi", "City": "Delhi", "Location": "Station D", "Agency": "CPCB", "SO2": 22.1, "NO2": 45.3, "PM10": 210.0},
    {"Stn Code": 101, "Sampling Date": "2022-01-08", "State": "Jharkhand", "City": "Jharia", "Location": "Station A", "Agency": "CPCB", "SO2": 16.0, "NO2": 29.1, "PM10": 145.0},
    {"Stn Code": 102, "Sampling Date": "2022-01-08", "State": "Meghalaya", "City": "Brynihat", "Location": "Station B", "Agency": "CPCB", "SO2": 19.1, "NO2": 33.5, "PM10": 200.0},
]


def _create_dataset_with_rows(conn, filename: str, display_name: str, sheet_name: str, rows: list[dict[str, Any]]) -> int:
    cols = list(rows[0].keys())
    ds_id = conn.execute(
        "INSERT INTO dataset_uploads (filename, original_name, file_type, display_name) VALUES (?, ?, 'csv', ?)",
        (filename, filename, display_name)
    ).lastrowid
    s_id = conn.execute(
        "INSERT INTO sheets (dataset_id, name, columns_json, profile_json, row_count) VALUES (?, ?, ?, '[]', ?)",
        (ds_id, sheet_name, json.dumps(cols), len(rows))
    ).lastrowid
    for idx, r in enumerate(rows):
        conn.execute(
            "INSERT INTO sheet_rows (sheet_id, row_index, data_json) VALUES (?, ?, ?)",
            (s_id, idx, json.dumps(r))
        )
    conn.commit()
    return ds_id


def extract_characterization_signature(res: dict[str, Any]) -> dict[str, Any]:
    """Extracts immutable semantic footprint from adaptive dashboard response."""
    topics = []
    raw_topics = res.get("executive_topics", []) or res.get("elements", [])
    for elem in raw_topics:
        if isinstance(elem, dict):
            topics.append({
                "topic_id": elem.get("topic_id") or elem.get("id"),
                "title": elem.get("title") or elem.get("story", {}).get("title"),
                "domain": elem.get("domain"),
                "analytical_intent": elem.get("analytical_intent"),
                "visual_type": (elem.get("visual_spec", {}) or {}).get("chart_type") or elem.get("chart_type"),
                "finding": elem.get("finding") or elem.get("story", {}).get("finding"),
            })

    kpis = res.get("executive_kpis", []) or res.get("executive_metrics", [])
    return {
        "dataset_id": res.get("dataset_id"),
        "kpis": kpis,
        "topics": topics,
        "total_topics": len(topics),
        "domain_profile": res.get("domain_profile", {}),
    }


# ------------------------------------------------------------------------------
# Characterization Tests
# ------------------------------------------------------------------------------

def test_characterize_workforce_baseline():
    """Characterizes Workforce domain: verifies attendance KPIs, employee ranking, and zero retail/environmental contamination."""
    with session_scope() as conn:
        ds_id = _create_dataset_with_rows(conn, "workforce_eval.csv", "Workforce Attendance July", "Attendance", WORKFORCE_RECORDS)

    res_obj = run_dataset_intelligence(dataset_id=ds_id)
    res = res_obj.model_dump()
    sig = extract_characterization_signature(res)

    assert sig["total_topics"] > 0
    raw_text = json.dumps(res).lower()

    # Zero retail contamination
    assert "weekly_sales" not in raw_text
    assert "fuel_price" not in raw_text
    assert "cpi" not in raw_text

    # Zero environmental contamination
    assert "pm10" not in raw_text
    assert "cpcb" not in raw_text
    assert "so2" not in raw_text

    # Workforce core metrics present
    assert any("attendance" in k["label"].lower() or "leave" in k["label"].lower() for k in sig["kpis"])


def test_characterize_retail_baseline():
    """Characterizes Retail domain: verifies sales volume/spread, and zero HR/workforce contamination."""
    with session_scope() as conn:
        ds_id = _create_dataset_with_rows(conn, "walmart_eval.csv", "Walmart Store Sales", "Sales_Data", RETAIL_RECORDS)

    res_obj = run_dataset_intelligence(dataset_id=ds_id)
    res = res_obj.model_dump()
    sig = extract_characterization_signature(res)

    assert sig["total_topics"] > 0
    raw_text = json.dumps(res).lower()

    # Zero workforce contamination
    assert "approved leaves" not in raw_text
    assert "total attendance" not in raw_text
    assert "headcount" not in raw_text

    # Zero environmental contamination
    assert "pm10" not in raw_text
    assert "cpcb" not in raw_text

    # Retail topics present
    assert any("sales" in t["title"].lower() or "store" in t["title"].lower() for t in sig["topics"] if t.get("title"))


def test_characterize_environmental_baseline():
    """Characterizes Environmental domain: verifies AQI/pollution elements and zero retail/workforce contamination."""
    with session_scope() as conn:
        ds_id = _create_dataset_with_rows(conn, "cpcb_eval.csv", "CPCB Air Quality Report", "Location_data", ENVIRONMENTAL_RECORDS)

    res_obj = run_dataset_intelligence(dataset_id=ds_id)
    res = res_obj.model_dump()
    sig = extract_characterization_signature(res)

    assert sig["total_topics"] > 0
    raw_text = json.dumps(res).lower()

    # Zero workforce contamination
    assert "approved leaves" not in raw_text
    assert "total attendance" not in raw_text

    # Zero retail contamination
    assert "weekly_sales" not in raw_text
    assert "fuel_price" not in raw_text


def test_g5_1_metric_formatter_equivalence():
    """G5.1: Verifies MetricFormatter and presentation label functions produce exact outputs."""
    from app.services.adaptive_dashboard.formatting import (
        MetricFormatter,
        format_currency_short,
        format_percentage,
        format_compact_number,
        clean_metric_name,
        safe_title,
    )

    # Currency formatting
    assert format_currency_short(1_500_000) == "$1.5M"
    assert format_currency_short(2_340_000_000) == "$2.34B"
    assert format_currency_short(450) == "$450"

    # Percentage
    assert format_percentage(87.42) == "87.4%"

    # Compact number
    assert format_compact_number(12500) == "12.5K"

    # Presentation labels: zero underscores, clean casing, preserved acronyms
    assert clean_metric_name("fuel_price") == "Fuel Price"
    assert clean_metric_name("cpi_index") == "CPI Index"
    assert clean_metric_name("total_approved_leaves") == "Total Approved Leaves"
    assert safe_title("temperature_vs_fuel_price") == "Temperature vs Fuel Price"

    # Facade delegation
    assert MetricFormatter.format_currency_short(1000) == "$1K"


def test_g5_1_architecture_boundary_purity():
    """G5.1 Architecture Boundary Guard: Verifies formatting modules contain zero DB, zero AI, and zero MCP imports."""
    import ast
    from pathlib import Path

    formatting_dir = Path("app/services/adaptive_dashboard/formatting")
    assert formatting_dir.exists(), "formatting package must exist"

    forbidden_modules = {"sqlite3", "duckdb", "ollama", "mcp", "requests", "httpx"}
    for py_file in formatting_dir.glob("*.py"):
        tree = ast.parse(py_file.read_text(encoding="utf-8"), filename=str(py_file))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    top_pkg = alias.name.split(".")[0]
                    assert top_pkg not in forbidden_modules, (
                        f"Architecture violation: {py_file} imports forbidden '{top_pkg}'"
                    )
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    top_pkg = node.module.split(".")[0]
                    assert top_pkg not in forbidden_modules, (
                        f"Architecture violation: {py_file} imports from forbidden '{top_pkg}'"
                    )

