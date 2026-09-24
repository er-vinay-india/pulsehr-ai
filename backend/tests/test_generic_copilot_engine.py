"""Tests for Phase 5: Grounded Conversational Q&A / Drill-Down Engine.

Verifies interactive query execution across arbitrary datasets:
1. Surprise Me / Top Findings Query -> ranked facts & chart
2. Entity Drilldown Query -> specific fact matching target entity
3. Interpretation / "Why" Query -> non-causal explanation with citations & follow-ups
4. Ambiguous Column Query -> disclaims unknown business meaning
"""

import pytest
import pandas as pd

from app.services.data_engine.semantic_classifier import SemanticClassifier
from app.services.copilot.generic_copilot_engine import GenericCopilotEngine
from app.services.copilot.copilot_models import GroundedAnswer


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


def test_surprise_me_query(sales_df):
    """Verifies that 'surprise me' returns top ranked facts and a chart."""
    profile = SemanticClassifier.profile_dataset(sales_df, "Sales")
    answer = GenericCopilotEngine.answer_query(sales_df, profile, "Surprise me with the top findings")

    assert isinstance(answer, GroundedAnswer)
    assert answer.intent == "SURPRISE_ME"
    assert len(answer.cited_facts) >= 1
    assert "FACT-" in answer.answer_markdown
    assert answer.recommended_chart is not None
    assert len(answer.followup_questions) >= 1


def test_entity_drilldown_query(manufacturing_df):
    """Verifies targeted drilldown on Machine M-01."""
    profile = SemanticClassifier.profile_dataset(manufacturing_df, "Manufacturing")
    answer = GenericCopilotEngine.answer_query(manufacturing_df, profile, "What is the scrap rate for Machine M-01?")

    assert isinstance(answer, GroundedAnswer)
    assert answer.intent == "ENTITY_DRILLDOWN"
    assert len(answer.cited_facts) >= 1
    assert "FACT-" in answer.answer_markdown
    assert answer.recommended_chart is not None


def test_interpretation_why_query(manufacturing_df):
    """Verifies 'why' question returns evidence-grounded non-causal interpretation."""
    profile = SemanticClassifier.profile_dataset(manufacturing_df, "Manufacturing")
    answer = GenericCopilotEngine.answer_query(manufacturing_df, profile, "Why is scrap rate higher during Night shift?")

    assert isinstance(answer, GroundedAnswer)
    assert answer.intent == "INTERPRETATION"
    assert "Observation" in answer.answer_markdown
    assert "Interpretation" in answer.answer_markdown
    assert answer.audit_passed is True
    assert len(answer.followup_questions) >= 1


def test_ambiguous_column_query(ambiguous_df):
    """Verifies query about ambiguous column col_b disclaims business interpretation."""
    profile = SemanticClassifier.profile_dataset(ambiguous_df, "Masked Telemetry")
    answer = GenericCopilotEngine.answer_query(ambiguous_df, profile, "What is the meaning of col_b?")

    assert isinstance(answer, GroundedAnswer)
    assert answer.intent == "AMBIGUITY"
    assert "business meaning cannot be determined" in answer.answer_markdown
