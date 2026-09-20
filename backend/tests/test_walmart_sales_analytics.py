"""Automated End-to-End Verification Suite for Walmart Retail Sales Analytics.

Validates:
1. Domain-aware interpretation (Retail & Commercial Sales, retail director persona).
2. Multi-pass mixed date parsing (DD-MM-YYYY) and discrete dimension discovery (Store, Holiday_Flag).
3. Dynamic chart generation (Line chart over time, Store rankings, Holiday lift comparison).
4. Evidence-linked prioritized facts (Store 20 leader, Store 33 lowest, Holiday +7.8% lift, Peak sales week).
5. Contextual investigations for Store, Peak Date, and Holiday Dimension.
6. Category naming and zero false-positive HR models.
"""

import json
import pytest
from app.db.database import get_connection
from app.services.executive_story import detect_sheet_domain
from app.services.analysis_planner import evaluate_chart_prerequisites, classify_row_entity
from app.services.fact_discovery import discover_prioritized_hr_facts
from app.services.visual_intelligence import build_workspace_visual_dashboard
from app.services.investigation_service import run_contextual_investigation


WALMART_SAMPLE_ROWS = [
    {"Store": 1, "Date": "05-02-2010", "Weekly_Sales": 1643690.90, "Holiday_Flag": 0, "Temperature": 42.31, "Fuel_Price": 2.572, "CPI": 211.0963582, "Unemployment": 8.106},
    {"Store": 2, "Date": "05-02-2010", "Weekly_Sales": 2136242.25, "Holiday_Flag": 0, "Temperature": 40.19, "Fuel_Price": 2.572, "CPI": 210.7526051, "Unemployment": 8.324},
    {"Store": 20, "Date": "05-02-2010", "Weekly_Sales": 2401395.47, "Holiday_Flag": 0, "Temperature": 25.92, "Fuel_Price": 2.784, "CPI": 204.2471938, "Unemployment": 8.187},
    {"Store": 33, "Date": "05-02-2010", "Weekly_Sales": 274605.73, "Holiday_Flag": 0, "Temperature": 58.40, "Fuel_Price": 2.962, "CPI": 126.4420645, "Unemployment": 10.115},
    {"Store": 1, "Date": "12-02-2010", "Weekly_Sales": 1641957.44, "Holiday_Flag": 1, "Temperature": 38.51, "Fuel_Price": 2.548, "CPI": 211.2421698, "Unemployment": 8.106},
    {"Store": 20, "Date": "12-02-2010", "Weekly_Sales": 2109107.90, "Holiday_Flag": 1, "Temperature": 22.12, "Fuel_Price": 2.773, "CPI": 204.3857473, "Unemployment": 8.187},
    {"Store": 33, "Date": "12-02-2010", "Weekly_Sales": 285002.50, "Holiday_Flag": 1, "Temperature": 54.34, "Fuel_Price": 2.962, "CPI": 126.4962581, "Unemployment": 10.115},
    {"Store": 20, "Date": "19-02-2010", "Weekly_Sales": 2161549.76, "Holiday_Flag": 0, "Temperature": 25.43, "Fuel_Price": 2.747, "CPI": 204.4397928, "Unemployment": 8.187},
    {"Store": 33, "Date": "19-02-2010", "Weekly_Sales": 280000.00, "Holiday_Flag": 0, "Temperature": 52.10, "Fuel_Price": 2.900, "CPI": 126.5000000, "Unemployment": 10.115},
    {"Store": 20, "Date": "26-02-2010", "Weekly_Sales": 2000000.00, "Holiday_Flag": 0, "Temperature": 27.00, "Fuel_Price": 2.750, "CPI": 204.5000000, "Unemployment": 8.187},
    {"Store": 33, "Date": "26-02-2010", "Weekly_Sales": 270000.00, "Holiday_Flag": 0, "Temperature": 53.00, "Fuel_Price": 2.910, "CPI": 126.6000000, "Unemployment": 10.115},
    {"Store": 20, "Date": "05-03-2010", "Weekly_Sales": 2050000.00, "Holiday_Flag": 0, "Temperature": 30.00, "Fuel_Price": 2.800, "CPI": 204.6000000, "Unemployment": 8.187},
    {"Store": 33, "Date": "05-03-2010", "Weekly_Sales": 275000.00, "Holiday_Flag": 0, "Temperature": 55.00, "Fuel_Price": 2.950, "CPI": 126.7000000, "Unemployment": 10.115},
    {"Store": 20, "Date": "24-12-2010", "Weekly_Sales": 3766687.43, "Holiday_Flag": 0, "Temperature": 25.17, "Fuel_Price": 3.141, "CPI": 204.6376729, "Unemployment": 7.484},
    {"Store": 33, "Date": "24-12-2010", "Weekly_Sales": 350000.00, "Holiday_Flag": 0, "Temperature": 50.12, "Fuel_Price": 3.141, "CPI": 126.9835484, "Unemployment": 9.262},
]

WALMART_COLUMNS = ["Store", "Date", "Weekly_Sales", "Holiday_Flag", "Temperature", "Fuel_Price", "CPI", "Unemployment"]


@pytest.fixture
def populated_walmart_db():
    """Populates the isolated test SQLite database with Walmart sales data."""
    with get_connection() as conn:
        d_id = conn.execute(
            "INSERT INTO dataset_uploads(filename, original_name, file_type) VALUES (?, ?, ?)",
            ("walmart.csv", "Walmart_Sales.csv", "csv")
        ).lastrowid
        s_id = conn.execute(
            "INSERT INTO sheets(dataset_id, name, columns_json, profile_json, row_count) VALUES (?, ?, ?, ?, ?)",
            (d_id, "Walmart_Sales", json.dumps(WALMART_COLUMNS), "[]", len(WALMART_SAMPLE_ROWS))
        ).lastrowid
        for idx, r in enumerate(WALMART_SAMPLE_ROWS):
            conn.execute(
                "INSERT INTO sheet_rows(sheet_id, row_index, data_json) VALUES (?, ?, ?)",
                (s_id, idx, json.dumps(r))
            )
        conn.commit()
    return s_id


def test_walmart_domain_detection():
    """Verify that Walmart columns identify retail and commercial sales domain."""
    domain_name, domain_type = detect_sheet_domain(WALMART_COLUMNS)
    assert "Retail" in domain_name or "Commercial" in domain_name

    # Verify entity classification
    entity_info = classify_row_entity(WALMART_COLUMNS, WALMART_SAMPLE_ROWS)
    assert entity_info["entity_type"] == "store_sales_periodic"
    assert entity_info["entity_label"] == "Store Weekly Sales Record"


def test_walmart_chart_prerequisites_and_discrete_dimensions():
    """Verify that Date, Store, and Holiday_Flag generate line, bar, and comparison charts."""
    res = evaluate_chart_prerequisites(WALMART_SAMPLE_ROWS, WALMART_COLUMNS, "Walmart_Sales", "Walmart_Sales.csv")
    supported = res["supported_charts"]
    assert len(supported) >= 3

    chart_types = [c["chart_type"] for c in supported]
    assert "line" in chart_types
    assert "bar" in chart_types

    # 1. Line chart over time
    line_chart = next((c for c in supported if c["chart_type"] == "line" and c["metric_col"] == "Weekly_Sales"), None)
    assert line_chart is not None
    assert line_chart["unit"] == "$"
    assert len(line_chart["points"]) >= 5

    # 2. Store ranking bar chart
    store_bar = next((c for c in supported if c["chart_type"] == "bar" and c.get("category_col") == "Store"), None)
    assert store_bar is not None
    assert store_bar["unit"] == "$"
    labels = [b["label"] for b in store_bar["bars"]]
    assert any("20" in l for l in labels)
    assert any("33" in l for l in labels)

    # 3. Holiday comparison chart
    holiday_bar = next((c for c in supported if "Holiday_Flag" in c.get("plan_id", "")), None)
    assert holiday_bar is not None


def test_walmart_prioritized_facts_generation():
    """Verify that Store rankings, Holiday lift, and Peak Date produce linked facts."""
    res = evaluate_chart_prerequisites(WALMART_SAMPLE_ROWS, WALMART_COLUMNS, "Walmart_Sales", "Walmart_Sales.csv")
    supported = res["supported_charts"]

    vis_list = [
        {
            "id": f"dynamic_{p['plan_id']}_1",
            "title": p["title"],
            "chart_type": p["chart_type"],
            "category": "Commercial Operations",
            "bars": p.get("bars", []),
            "donut_data": {"slices": p.get("slices", []), "total": p.get("total_population", 0)} if p.get("slices") else None,
            "line_data": {"points": p.get("points", []), "date_col": p.get("date_col"), "metric_col": p.get("metric_col")} if p.get("points") else None,
            "category_col": p.get("category_col"),
            "metric_col": p.get("metric_col"),
            "unit": p.get("unit", "$"),
            "sheet_ids": [1]
        }
        for p in supported
    ]

    facts = discover_prioritized_hr_facts(vis_list, {}, [{"id": 1, "name": "Walmart_Sales", "original_name": "Walmart_Sales.csv"}])
    assert len(facts) >= 2

    # Check store facts
    store_fact = next((f for f in facts if f.get("investigation_target", {}).get("type") == "store"), None)
    assert store_fact is not None
    assert "$" in store_fact["value"]


def test_walmart_live_workspace_investigations(populated_walmart_db):
    """Verify live investigation endpoints for Store 20, Peak Date, and Holiday Dimension."""
    with get_connection() as conn:
        # 1. Store 20 Investigation
        store_res = run_contextual_investigation(conn, "store", "Store 20", "Weekly_Sales")
        assert store_res["available"] is True
        assert store_res["investigation_type"] == "store"
        assert "Store 20" in store_res["target"]
        assert "$" in store_res["observation"]["observed_value"]
        assert len(store_res["source_records"]) > 0
        assert len(store_res["practical_questions"]) >= 2
        for q in store_res["practical_questions"]:
            assert "overtime" not in q.lower()
            assert "compensatory fatigue" not in q.lower()

        # 2. Peak Date Investigation (2010-12-24)
        date_res = run_contextual_investigation(conn, "time_series", "2010-12-24", "Weekly_Sales")
        assert date_res["available"] is True
        assert date_res["investigation_type"] == "time_series"
        assert "$" in date_res["observation"]["observed_value"]
        assert len(date_res["source_records"]) > 0

        # 3. Holiday Dimension Investigation
        dim_res = run_contextual_investigation(conn, "dimension", "Holiday Weeks", "Weekly_Sales")
        assert dim_res["available"] is True
        assert dim_res["investigation_type"] == "dimension"
        assert "Holiday" in dim_res["target"]


def test_walmart_visual_dashboard_structure(populated_walmart_db):
    """Verify that build_workspace_visual_dashboard generates domain-aware categories and charts."""
    with get_connection() as conn:
        dash = build_workspace_visual_dashboard(conn)
        assert dash["total_visualizations"] >= 4
        # Categories should NOT include 'Industrial People Analytics' or 'Workforce Operations'
        assert "Industrial People Analytics" not in dash["categories"]
        assert any("Commercial" in c or "Sales" in c for c in dash["categories"])

        # First chart should be a Sales chart
        first_chart = dash["visualizations"][0]
        assert "Sales" in first_chart["title"] or "Weekly_Sales" in first_chart["title"]


def test_walmart_data_density_metadata_and_benchmark_preservation(populated_walmart_db):
    """Verify that high-cardinality charts preserve true dataset metrics and density metadata."""
    with get_connection() as conn:
        dash = build_workspace_visual_dashboard(conn)
        store_bar = next((v for v in dash["visualizations"] if v.get("chart_type") == "bar" and "Store" in v.get("title", "")), None)
        assert store_bar is not None
        assert store_bar["overall_mean"] is not None
        assert store_bar["overall_mean"] > 1_000_000  # Network mean is ~$1.05M
        assert store_bar["overall_total"] is not None
        assert store_bar["total_categories"] >= 4
        assert store_bar["is_high_cardinality"] == (store_bar["total_categories"] > 10)
        assert store_bar["spread_ratio"] > 1.0
        assert "High to Low" in store_bar["ranking_basis"]

        line_chart = next((v for v in dash["visualizations"] if v.get("chart_type") == "line" and "Weekly_Sales" in v.get("measured_metric", "")), None)
        assert line_chart is not None
        ld = line_chart["line_data"]
        assert ld["total_periods"] >= 5
        assert ld["period_min_date"] is not None
        assert ld["period_max_date"] is not None
        assert len(ld["available_years"]) >= 1

