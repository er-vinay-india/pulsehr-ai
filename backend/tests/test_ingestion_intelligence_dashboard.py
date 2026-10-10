"""Tests for Ingestion Intelligence -> Visual-First Dashboard Integration.

Verifies:
1. test_dimension_measure_creates_groupby_opportunity
2. test_temporal_measure_creates_trend_opportunity
3. test_semantic_groups_reduce_candidate_relationships
4. test_high_confidence_cross_group_key_is_preserved
5. test_invalid_many_to_many_relationship_not_visualized
6. test_temporal_lag_relationship_can_generate_candidate
7. test_high_effect_relationship_can_reach_dashboard
8. test_low_value_relationship_is_suppressed
9. test_categorical_factor_generates_segment_visual
10. test_ingestion_metric_grain_reaches_visual_decision_engine
11. test_domain_capability_blocks_invalid_opportunity
12. test_cross_domain_acceptance_retail_and_workforce
"""
from __future__ import annotations

import json
import pytest

from app.db.database import get_connection
from app.services.adaptive_dashboard.dataset_orchestrator import (
    SheetContext,
    run_dataset_intelligence,
)
from app.services.adaptive_dashboard.domain_governance import (
    DatasetDomain,
    DomainCapabilityGate,
)
from app.services.adaptive_dashboard.opportunity_planner import (
    AnalyticalOpportunity,
    AnalyticalOpportunityPlanner,
    AnalyticalOpportunityScore,
    AnalyticalOpportunityType,
)
from app.services.adaptive_dashboard.visual_decision import (
    ChartType,
    VisualDecisionEngine,
)


@pytest.fixture
def test_retail_dataset():
    """Sets up a retail sales dataset with Store, Weekly_Sales, Date, Fuel_Price in SQLite."""
    conn = get_connection()
    ds_id = 8801
    conn.execute(
        "INSERT OR REPLACE INTO dataset_uploads (id, filename, original_name, display_name, file_type, sheet_count, row_count) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (ds_id, "walmart_sales.csv", "Walmart Sales Q4.csv", "Walmart Weekly Sales", "csv", 1, 100),
    )

    cols = ["Store", "Weekly_Sales", "Date", "Fuel_Price", "CPI", "Unemployment", "Department"]
    profiles = [
        {"column": "Store", "semantic_role": "DIMENSION", "physical_type": "string", "cardinality": 10},
        {"column": "Weekly_Sales", "semantic_role": "MEASURE", "physical_type": "float", "unit": "usd", "metric_grain": "store × week"},
        {"column": "Date", "semantic_role": "TIME", "physical_type": "string", "temporal_grain": "week"},
        {"column": "Fuel_Price", "semantic_role": "MEASURE", "physical_type": "float", "unit": "usd"},
        {"column": "CPI", "semantic_role": "MEASURE", "physical_type": "float", "unit": "index"},
        {"column": "Unemployment", "semantic_role": "MEASURE", "physical_type": "float", "unit": "percent"},
        {"column": "Department", "semantic_role": "DIMENSION", "physical_type": "string", "cardinality": 5},
    ]

    enrichment = {
        "semantic_groups": [
            {"group_id": "G1", "group_name": "SALES", "columns": ["Weekly_Sales"]},
            {"group_id": "G2", "group_name": "ORGANIZATION", "columns": ["Store", "Department"]},
            {"group_id": "G3", "group_name": "TIME", "columns": ["Date"]},
            {"group_id": "G4", "group_name": "ECONOMIC_FACTORS", "columns": ["Fuel_Price", "CPI", "Unemployment"]},
        ]
    }

    conn.execute(
        "INSERT OR REPLACE INTO sheets (id, dataset_id, name, display_name, columns_json, profile_json, enrichment_json, row_count) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (88011, ds_id, "Sales", "Weekly Store Sales", json.dumps(cols), json.dumps(profiles), json.dumps(enrichment), 100),
    )

    # Insert sample records into sheet_rows
    conn.execute("DELETE FROM sheet_rows WHERE sheet_id = 88011")
    for r_idx in range(20):
        store_id = f"Store {1 + (r_idx % 4)}"
        rec = {
            "Store": store_id,
            "Weekly_Sales": 20000.0 + (r_idx * 500),
            "Date": f"2026-W{40 + (r_idx % 5)}",
            "Fuel_Price": 3.45 + (r_idx * 0.05),
            "CPI": 210.0 + r_idx,
            "Unemployment": 6.5,
            "Department": "Grocery" if r_idx % 2 == 0 else "Apparel",
        }
        conn.execute(
            "INSERT INTO sheet_rows (sheet_id, row_index, data_json) VALUES (?, ?, ?)",
            (88011, r_idx, json.dumps(rec)),
        )

    conn.commit()
    conn.close()
    return ds_id


def test_dimension_measure_creates_groupby_opportunity(test_retail_dataset):
    """1. Numerical measure (Weekly_Sales) + categorical dimension (Store) creates Group-by ranking opportunity."""
    sheet = SheetContext(
        sheet_id=88011,
        sheet_name="Sales",
        row_count=100,
        col_count=7,
        entity_type="sales_record",
        columns=["Store", "Weekly_Sales", "Date", "Fuel_Price", "CPI", "Unemployment", "Department"],
    )

    opps, tracker = AnalyticalOpportunityPlanner.plan_opportunities(
        dataset_id=test_retail_dataset,
        sheets=[sheet],
        dataset_name="Walmart Weekly Sales",
    )

    # Must contain a MEASURE_BY_DIMENSION opportunity for Weekly_Sales by Store
    store_sales_opp = next(
        (o for o in opps if o.opportunity_type == AnalyticalOpportunityType.MEASURE_BY_DIMENSION
         and o.primary_measure == "Weekly_Sales" and o.primary_dimension == "Store"),
        None,
    )

    assert store_sales_opp is not None
    assert store_sales_opp.statistical_intent == "ranking"
    assert store_sales_opp.target_visual_archetype == "RANKING_STORY"
    assert store_sales_opp.score.total_score > 0.70
    assert "Weekly Sales by Store" in store_sales_opp.title


def test_temporal_measure_creates_trend_opportunity(test_retail_dataset):
    """2. Numerical measure (Weekly_Sales) + temporal dimension (Date) creates Trend opportunity."""
    sheet = SheetContext(
        sheet_id=88011,
        sheet_name="Sales",
        row_count=100,
        col_count=7,
        entity_type="sales_record",
        columns=["Store", "Weekly_Sales", "Date", "Fuel_Price", "CPI", "Unemployment", "Department"],
    )

    opps, tracker = AnalyticalOpportunityPlanner.plan_opportunities(
        dataset_id=test_retail_dataset,
        sheets=[sheet],
        dataset_name="Walmart Weekly Sales",
    )

    trend_opp = next(
        (o for o in opps if o.opportunity_type == AnalyticalOpportunityType.MEASURE_BY_TIME
         and o.primary_measure == "Weekly_Sales" and o.primary_dimension == "Date"),
        None,
    )

    assert trend_opp is not None
    assert trend_opp.statistical_intent == "trend"
    assert trend_opp.target_visual_archetype == "TREND_STORY"
    assert trend_opp.score.temporal_relevance >= 0.90


def test_semantic_groups_reduce_candidate_relationships(test_retail_dataset):
    """3. Semantic groups reduce brute-force cartesian pairs (N*(N-1)/2)."""
    sheet = SheetContext(
        sheet_id=88011,
        sheet_name="Sales",
        row_count=100,
        col_count=7,
        entity_type="sales_record",
        columns=["Store", "Weekly_Sales", "Date", "Fuel_Price", "CPI", "Unemployment", "Department"],
    )

    opps, tracker = AnalyticalOpportunityPlanner.plan_opportunities(
        dataset_id=test_retail_dataset,
        sheets=[sheet],
        dataset_name="Walmart Weekly Sales",
    )

    assert tracker.raw_possible_relationships == 21  # 7 * 6 / 2
    assert tracker.eligible_group_relationships < tracker.raw_possible_relationships
    assert tracker.reduction_ratio >= 40.0  # Significant combinatorial noise eliminated


def test_high_confidence_cross_group_key_is_preserved(test_retail_dataset):
    """4. High-confidence cross-sheet relationship (join_confidence >= 0.85) is preserved."""
    conn = get_connection()
    conn.execute(
        """
        INSERT OR REPLACE INTO sheet_relationships
        (id, left_sheet, right_sheet, left_column, right_column, method, status, cardinality, matching_keys, matching_pairs, similarity, reason)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (991, 88011, 88011, "Store", "Store", "exact", "verified", "one-to-many", 10, 50, 0.95, "Verified store join"),
    )
    conn.commit()
    conn.close()

    sheet = SheetContext(
        sheet_id=88011,
        sheet_name="Sales",
        row_count=100,
        col_count=7,
        entity_type="sales_record",
        columns=["Store", "Weekly_Sales", "Date", "Fuel_Price", "CPI", "Unemployment", "Department"],
    )

    opps, tracker = AnalyticalOpportunityPlanner.plan_opportunities(
        dataset_id=test_retail_dataset,
        sheets=[sheet],
        dataset_name="Walmart Weekly Sales",
    )

    cross_opp = next(
        (o for o in opps if o.opportunity_type == AnalyticalOpportunityType.CROSS_SHEET_RELATIONSHIP),
        None,
    )
    assert cross_opp is not None
    assert cross_opp.join_confidence >= 0.90
    assert cross_opp.score.cross_sheet_value >= 0.90


def test_invalid_many_to_many_relationship_not_visualized(test_retail_dataset):
    """5. Invariant: Invalid many-to-many join relationship is suppressed from direct visual opportunity."""
    conn = get_connection()
    conn.execute(
        """
        INSERT OR REPLACE INTO sheet_relationships
        (id, left_sheet, right_sheet, left_column, right_column, method, status, cardinality, matching_keys, matching_pairs, similarity, reason)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (992, 88011, 88011, "Date", "Date", "vector", "suggested", "many-to-many", 5, 250, 0.72, "Many to many fanout risk"),
    )
    conn.commit()
    conn.close()

    sheet = SheetContext(
        sheet_id=88011,
        sheet_name="Sales",
        row_count=100,
        col_count=7,
        entity_type="sales_record",
        columns=["Store", "Weekly_Sales", "Date", "Fuel_Price", "CPI", "Unemployment", "Department"],
    )

    opps, tracker = AnalyticalOpportunityPlanner.plan_opportunities(
        dataset_id=test_retail_dataset,
        sheets=[sheet],
        dataset_name="Walmart Weekly Sales",
    )

    m2m_opp = next(
        (o for o in opps if o.relationship_id == "REL-992"),
        None,
    )
    assert m2m_opp is None  # Suppressed


def test_temporal_lag_relationship_can_generate_candidate(test_retail_dataset):
    """6. Economic factor (Fuel_Price) vs Weekly_Sales can generate association candidate."""
    sheet = SheetContext(
        sheet_id=88011,
        sheet_name="Sales",
        row_count=100,
        col_count=7,
        entity_type="sales_record",
        columns=["Store", "Weekly_Sales", "Date", "Fuel_Price", "CPI", "Unemployment", "Department"],
    )

    opps, tracker = AnalyticalOpportunityPlanner.plan_opportunities(
        dataset_id=test_retail_dataset,
        sheets=[sheet],
        dataset_name="Walmart Weekly Sales",
    )

    econ_sales_opp = next(
        (o for o in opps if o.opportunity_type == AnalyticalOpportunityType.MEASURE_BY_MEASURE
         and (("Fuel_Price" in (o.primary_measure, o.secondary_measure)) or ("CPI" in (o.primary_measure, o.secondary_measure)))),
        None,
    )
    assert econ_sales_opp is not None
    assert econ_sales_opp.target_visual_archetype == "RELATIONSHIP_STORY"


def test_high_effect_relationship_can_reach_dashboard(test_retail_dataset):
    """7. High effect size and business impact reaches the executive dashboard candidate pool."""
    sheet = SheetContext(
        sheet_id=88011,
        sheet_name="Sales",
        row_count=100,
        col_count=7,
        entity_type="sales_record",
        columns=["Store", "Weekly_Sales", "Date", "Fuel_Price", "CPI", "Unemployment", "Department"],
    )

    resp = run_dataset_intelligence(test_retail_dataset)
    assert len(resp.selected_dashboard_insights) > 0
    assert len(resp.analytical_opportunities) > 0
    assert resp.relationship_reduction.get("reduction_ratio", 0) > 0


def test_low_value_relationship_is_suppressed(test_retail_dataset):
    """8. Relationships with low confidence (< 0.70) are suppressed."""
    conn = get_connection()
    conn.execute(
        """
        INSERT OR REPLACE INTO sheet_relationships
        (id, left_sheet, right_sheet, left_column, right_column, method, status, cardinality, matching_keys, matching_pairs, similarity, reason)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (993, 88011, 88011, "Department", "Department", "exact", "candidate", "one-to-many", 1, 2, 0.45, "Low similarity match"),
    )
    conn.commit()
    conn.close()

    sheet = SheetContext(
        sheet_id=88011,
        sheet_name="Sales",
        row_count=100,
        col_count=7,
        entity_type="sales_record",
        columns=["Store", "Weekly_Sales", "Date", "Fuel_Price", "CPI", "Unemployment", "Department"],
    )

    opps, tracker = AnalyticalOpportunityPlanner.plan_opportunities(
        dataset_id=test_retail_dataset,
        sheets=[sheet],
        dataset_name="Walmart Weekly Sales",
    )

    low_opp = next((o for o in opps if o.relationship_id == "REL-993"), None)
    assert low_opp is None


def test_categorical_factor_generates_segment_visual(test_retail_dataset):
    """9. Categorical factor (Department) generates ranked segment visual."""
    sheet = SheetContext(
        sheet_id=88011,
        sheet_name="Sales",
        row_count=100,
        col_count=7,
        entity_type="sales_record",
        columns=["Store", "Weekly_Sales", "Date", "Fuel_Price", "CPI", "Unemployment", "Department"],
    )

    opps, _ = AnalyticalOpportunityPlanner.plan_opportunities(
        dataset_id=test_retail_dataset,
        sheets=[sheet],
        dataset_name="Walmart Weekly Sales",
    )

    dept_sales = next(
        (o for o in opps if o.primary_measure == "Weekly_Sales" and o.primary_dimension == "Department"),
        None,
    )
    assert dept_sales is not None
    assert dept_sales.target_visual_archetype == "RANKING_STORY"


def test_ingestion_metric_grain_reaches_visual_decision_engine():
    """10. Ingestion metric grain (employee × working_day) and unit reach VisualDecisionEngine."""
    decision = VisualDecisionEngine.decide_visual(
        visual_id="VIS-INGESTION-GRAIN",
        question_text="How was workforce capacity distributed across departments?",
        primary_dimension="department",
        measures=["office_attendance", "approved_leave", "remaining_attendance_gap"],
        provided_units={
            "office_attendance": "employee_day",
            "approved_leave": "employee_day",
            "remaining_attendance_gap": "employee_day",
        },
        denominator_metric="expected_capacity_employee_days",
        denominator_value=160.0,
        residual_component="remaining_attendance_gap",
        series_data={
            "office_attendance": [136.0],
            "approved_leave": [19.0],
            "remaining_attendance_gap": [5.0],
        },
    )

    assert decision["status"] == "VALIDATED"
    audit = decision["audit"]
    assert audit["metric_grain"] == "employee × working_day"
    assert "employee_day" in audit["metric_units"]
    assert audit["selected_chart"] == "100_percent_stacked_bar"


def test_domain_capability_blocks_invalid_opportunity():
    """11. DomainCapabilityGate isolation: Retail dataset with 'Department' column NEVER generates workforce attendance analyses."""
    domain_prof = DomainCapabilityGate.resolve_domain(
        columns=["Store", "Weekly_Sales", "Date", "Fuel_Price", "Department"],
        dataset_name="Walmart Sales",
    )
    assert domain_prof.domain == DatasetDomain.RETAIL_SALES

    is_entitled = AnalyticalOpportunityPlanner._is_entitled_for_domain(
        col1="attendance_rate",
        col2="Department",
        domain_profile=domain_prof,
    )
    assert is_entitled is False  # Blocked cross-domain leakage


def test_cross_domain_acceptance_retail_and_workforce(test_retail_dataset):
    """12. Cross-domain test: Retail dataset produces commercial topics; Workforce produces attendance topics."""
    # 1. Retail
    retail_resp = run_dataset_intelligence(test_retail_dataset)
    assert retail_resp.domain_profile.get("domain") == DatasetDomain.RETAIL_SALES.value
    # No workforce terms in retail topics
    retail_titles = " ".join(t.get("title", "") for t in retail_resp.executive_topics).lower()
    assert "attendance rate" not in retail_titles
    assert "approved leave" not in retail_titles

    # 2. Workforce (Dataset 999 or 99750)
    conn = get_connection()
    wf_row = conn.execute("SELECT id FROM dataset_uploads WHERE original_name LIKE '%attendance%' OR original_name LIKE '%workforce%' LIMIT 1").fetchone()
    conn.close()
    if wf_row:
        wf_resp = run_dataset_intelligence(wf_row[0])
        assert wf_resp.domain_profile.get("domain") == DatasetDomain.WORKFORCE.value
        wf_titles = " ".join(t.get("title", "") for t in wf_resp.executive_topics).lower()
        assert "fuel_price" not in wf_titles
