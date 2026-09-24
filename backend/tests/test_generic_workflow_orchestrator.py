"""End-to-End Generic Workflow Orchestrator Tests (Phase 4).

Verifies full generic pipeline from arbitrary DataFrame to validated slide deck:
1. Sales / Commercial Dataset
2. Manufacturing / Operations Dataset
3. Ambiguous Masked Dataset
"""

import pytest
import pandas as pd

from app.services.reporting.workflow_orchestrator import WorkflowOrchestrator


@pytest.fixture
def sales_df():
    return pd.DataFrame({
        "order_id": [f"ORD-{i:04d}" for i in range(1, 21)],
        "order_date": [f"2024-01-{(i % 25) + 1:02d}" for i in range(1, 21)],
        "customer_id": [f"CUST-{((i % 7) + 1):03d}" for i in range(1, 21)],
        "product_category": ["Electronics", "Furniture", "Office Supplies", "Electronics"] * 5,
        "region": ["North America", "EMEA", "APAC", "LATAM"] * 5,
        "sales_amount": [f"${(i * 125.50):,.2f}" for i in range(1, 21)],
        "discount_rate": [f"{(i % 5) * 5.0}%" for i in range(1, 21)],
        "profit": [f"${((i * 45.0) - 100):,.2f}" for i in range(1, 21)],
        "is_returned": [1 if i % 6 == 0 else 0 for i in range(1, 21)]
    })


@pytest.fixture
def manufacturing_df():
    return pd.DataFrame({
        "batch_id": [f"BATCH-{i:03d}" for i in range(1, 21)],
        "timestamp": [f"2024-06-01 08:{i:02d}:00" for i in range(1, 21)],
        "machine_id": [f"M-{((i % 4) + 1):02d}" for i in range(1, 21)],
        "operator_shift": ["Day", "Night", "Day", "Night"] * 5,
        "cycle_time_sec": [42.5 + (i * 0.8) for i in range(1, 21)],
        "defect_count": [0, 1, 0, 3, 0, 2, 0, 0, 1, 4] * 2,
        "scrap_rate_pct": [0.0, 1.2, 0.0, 3.5, 0.0, 2.1, 0.0, 0.0, 1.1, 4.2] * 2,
        "passed_qa": [False if i in (4, 10, 14, 20) else True for i in range(1, 21)]
    })


@pytest.fixture
def ambiguous_df():
    return pd.DataFrame({
        "col_a": [f"A{i}" for i in range(1, 11)],
        "col_b": ["X", "Y", "X", "Z", "Y", "X", "Z", "Y", "X", "Z"],
        "value1": [10.5, 12.0, 9.2, 14.1, 11.0, 8.5, 13.4, 10.2, 12.1, 9.8],
        "flag2": [0, 1, 0, 0, 1, 0, 1, 0, 0, 1]
    })


def test_sales_generic_workflow(sales_df):
    """End-to-end execution of generic workflow on Sales data."""
    result = WorkflowOrchestrator.execute(sales_df, dataset_name="Enterprise Sales")

    assert result.status == "COMPLETED"
    assert result.semantic_profile is not None
    assert result.candidate_fact_count > 0
    assert result.ranked_fact_count > 0
    assert result.interpretation is not None
    assert result.audit_result is not None
    assert result.audit_result.all_passed is True
    assert len(result.visual_charts) >= 1

    deck = result.deck_spec
    assert "slides" in deck
    assert len(deck["slides"]) >= 2
    assert deck["slides"][0]["layout"] == "title_hero"
    # Check that at least one slide has an attached chart
    chart_slides = [s for s in deck["slides"] if "chart" in s]
    assert len(chart_slides) >= 1


def test_manufacturing_generic_workflow(manufacturing_df):
    """End-to-end execution of generic workflow on Manufacturing data."""
    result = WorkflowOrchestrator.execute(manufacturing_df, dataset_name="Plant Telemetry")

    assert result.status == "COMPLETED"
    assert result.semantic_profile.inferred_grain in ("manufacturing batch", "event / log entry", "transaction / order", "composite line item", "record")
    assert result.candidate_fact_count > 0
    assert result.audit_result.all_passed is True
    assert len(result.deck_spec["slides"]) >= 2


def test_ambiguous_generic_workflow(ambiguous_df):
    """End-to-end execution of generic workflow on Ambiguous data."""
    result = WorkflowOrchestrator.execute(ambiguous_df, dataset_name="Masked Telemetry")

    assert result.status == "COMPLETED"
    assert result.audit_result.all_passed is True
    assert len(result.deck_spec["slides"]) >= 2
