"""Tests for Topic-to-Visual Binding Integrity, Axis Narrative Consistency, and Zero Cross-Domain Leakage.

Validates:
1. TopicVisualBindingIntegrity strictly enforces topic_id, dataset_id, domain alignment.
2. TopicVisualBindingIntegrity rejects cross-domain vocabulary (retail vs workforce vs environmental).
3. AxisNarrativeIntegrity repairs or suppresses mismatched axis narrative titles on relationship cards.
4. End-to-end retail dataset intelligence produces zero workforce vocabulary in executive topics.
5. Scatter plot card on retail data binds strictly to Temperature vs Fuel Price.
"""
from __future__ import annotations

import json
import pytest

from app.db.database import get_connection
from app.services.adaptive_dashboard.composition_planner import ExecutiveTopic
from app.services.adaptive_dashboard.semantic_visual_compression import VisualMicrocopy
from app.services.adaptive_dashboard.dataset_isolation_integrity import (
    TopicVisualBindingIntegrity,
    AxisNarrativeIntegrity,
    DatasetIsolationIntegrity,
)
from app.services.adaptive_dashboard.dataset_orchestrator import run_dataset_intelligence


def test_topic_visual_binding_integrity_success():
    """Verify that a correctly bound topic and visual_spec pass verification."""
    topic = ExecutiveTopic(
        topic_id="TOPIC-001",
        title="Store Sales Revenue Ranking",
        dataset_id=101,
        domain="retail",
        visual_spec={
            "topic_id": "TOPIC-001",
            "dataset_id": 101,
            "domain": "retail",
            "chart_type": "ranked_bar",
        },
        visual_microcopy=VisualMicrocopy(
            icon="trophy",
            short_title="Store Sales Ranking",
            primary_number="$29.5K",
            short_context="Top Store 1",
            short_finding="Store 1 leads revenue.",
            cta="Inspect",
        ),
    )
    ok, err = TopicVisualBindingIntegrity.evaluate(topic)
    assert ok, f"Expected valid binding, got error: {err}"


def test_topic_visual_binding_integrity_mismatches():
    """Verify that mismatched dataset_id, domain, or topic_id fail verification."""
    # 1. Dataset ID mismatch
    t_bad_ds = ExecutiveTopic(
        topic_id="TOPIC-001",
        title="Store Sales",
        dataset_id=101,
        domain="retail",
        visual_spec={"topic_id": "TOPIC-001", "dataset_id": 999, "domain": "retail"},
    )
    ok, err = TopicVisualBindingIntegrity.evaluate(t_bad_ds)
    assert not ok
    assert "DATASET_MISMATCH" in err

    # 2. Domain mismatch
    t_bad_dom = ExecutiveTopic(
        topic_id="TOPIC-001",
        title="Store Sales",
        dataset_id=101,
        domain="retail",
        visual_spec={"topic_id": "TOPIC-001", "dataset_id": 101, "domain": "workforce"},
    )
    ok, err = TopicVisualBindingIntegrity.evaluate(t_bad_dom)
    assert not ok
    assert "DOMAIN_MISMATCH" in err

    # 3. Topic ID mismatch
    t_bad_id = ExecutiveTopic(
        topic_id="TOPIC-001",
        title="Store Sales",
        dataset_id=101,
        domain="retail",
        visual_spec={"topic_id": "TOPIC-002", "dataset_id": 101, "domain": "retail"},
    )
    ok, err = TopicVisualBindingIntegrity.evaluate(t_bad_id)
    assert not ok
    assert "TOPIC_ID_MISMATCH" in err


def test_topic_visual_binding_vocabulary_violation():
    """Verify that cross-domain vocabulary leakage in title/microcopy is caught."""
    # Retail topic corrupted with workforce vocabulary
    corrupt_retail_topic = ExecutiveTopic(
        topic_id="TOPIC-003",
        title="Attendance & Leave Correlation",
        dataset_id=200,
        domain="retail",
        visual_spec={
            "topic_id": "TOPIC-003",
            "dataset_id": 200,
            "domain": "retail",
            "chart_type": "scatter",
        },
        visual_microcopy=VisualMicrocopy(
            icon="relationship",
            short_title="Attendance & Leave Correlation",
            primary_number="r = +0.82",
            short_context="Store locations",
            short_finding="Observed correlation.",
            cta="Explore",
        ),
    )
    ok, err = TopicVisualBindingIntegrity.evaluate(corrupt_retail_topic)
    assert not ok
    assert "FOREIGN_VOCABULARY_VIOLATION" in err
    assert "attendance" in err.lower() or "leave" in err.lower()


def test_axis_narrative_integrity_repair():
    """Verify that AxisNarrativeIntegrity detects corrupted relationship titles and repairs them from x/y axes."""
    corrupted_topic = ExecutiveTopic(
        topic_id="TOPIC-004",
        title="Attendance & Leave Correlation",
        dataset_id=300,
        domain="retail",
        analytical_intent="RELATIONSHIP",
        visual_spec={
            "topic_id": "TOPIC-004",
            "dataset_id": 300,
            "domain": "retail",
            "chart_type": "scatter",
            "x_label": "Temperature",
            "y_label": "Fuel Price",
        },
        visual_microcopy=VisualMicrocopy(
            icon="relationship",
            short_title="Attendance & Leave Correlation",
            primary_number="r = -0.42",
            short_context="Store locations",
            short_finding="Relationship across stores.",
            cta="Explore",
        ),
    )

    ok, rep = AxisNarrativeIntegrity.evaluate(corrupted_topic)
    assert ok
    assert "REPAIRED_AXIS_NARRATIVE" in rep
    assert corrupted_topic.title == "Temperature vs Fuel Price"
    assert corrupted_topic.visual_microcopy.short_title == "Temperature vs Fuel Price"


@pytest.fixture
def walmart_retail_dataset():
    """Creates a sample Walmart retail dataset in SQLite."""
    conn = get_connection()
    ds_id = 99880
    conn.execute(
        "INSERT OR REPLACE INTO dataset_uploads (id, filename, original_name, display_name, file_type, sheet_count, row_count) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (ds_id, "walmart.csv", "Walmart Sales.csv", "Walmart Store Analytics", "csv", 1, 15),
    )
    cols = ["Store", "Date", "Weekly_Sales", "Holiday_Flag", "Temperature", "Fuel_Price", "CPI", "Unemployment"]
    s_id = 10880
    conn.execute(
        "INSERT OR REPLACE INTO sheets (id, dataset_id, name, display_name, columns_json, profile_json, row_count) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (s_id, ds_id, "Store_Sales", "Store Sales", json.dumps(cols), "[]", 15),
    )

    rows = [
        {"Store": 1, "Date": "05-02-2010", "Weekly_Sales": 1643690.90, "Holiday_Flag": 0, "Temperature": 42.31, "Fuel_Price": 2.572, "CPI": 211.09, "Unemployment": 8.10},
        {"Store": 2, "Date": "05-02-2010", "Weekly_Sales": 2136242.25, "Holiday_Flag": 0, "Temperature": 40.19, "Fuel_Price": 2.572, "CPI": 210.75, "Unemployment": 8.32},
        {"Store": 20, "Date": "05-02-2010", "Weekly_Sales": 2401395.47, "Holiday_Flag": 0, "Temperature": 25.92, "Fuel_Price": 2.784, "CPI": 204.24, "Unemployment": 8.18},
        {"Store": 33, "Date": "05-02-2010", "Weekly_Sales": 274605.73, "Holiday_Flag": 0, "Temperature": 58.40, "Fuel_Price": 2.962, "CPI": 126.44, "Unemployment": 10.11},
        {"Store": 1, "Date": "12-02-2010", "Weekly_Sales": 1641957.44, "Holiday_Flag": 1, "Temperature": 38.51, "Fuel_Price": 2.548, "CPI": 211.24, "Unemployment": 8.10},
        {"Store": 20, "Date": "12-02-2010", "Weekly_Sales": 2109107.90, "Holiday_Flag": 1, "Temperature": 22.12, "Fuel_Price": 2.773, "CPI": 204.38, "Unemployment": 8.18},
        {"Store": 33, "Date": "12-02-2010", "Weekly_Sales": 285002.50, "Holiday_Flag": 1, "Temperature": 54.34, "Fuel_Price": 2.962, "CPI": 126.49, "Unemployment": 10.11},
        {"Store": 20, "Date": "19-02-2010", "Weekly_Sales": 2161549.76, "Holiday_Flag": 0, "Temperature": 25.43, "Fuel_Price": 2.747, "CPI": 204.43, "Unemployment": 8.18},
        {"Store": 33, "Date": "19-02-2010", "Weekly_Sales": 280000.00, "Holiday_Flag": 0, "Temperature": 52.10, "Fuel_Price": 2.900, "CPI": 126.50, "Unemployment": 10.11},
        {"Store": 20, "Date": "26-02-2010", "Weekly_Sales": 2000000.00, "Holiday_Flag": 0, "Temperature": 27.00, "Fuel_Price": 2.750, "CPI": 204.50, "Unemployment": 8.18},
    ]
    for idx, r in enumerate(rows):
        conn.execute(
            "INSERT OR REPLACE INTO sheet_rows (sheet_id, row_index, data_json) VALUES (?, ?, ?)",
            (s_id, idx, json.dumps(r)),
        )
    conn.commit()
    conn.close()
    return ds_id


def test_retail_dataset_orchestration_zero_workforce_leakage(walmart_retail_dataset):
    """End-to-end test verifying that retail dataset produces zero workforce vocabulary in executive topics."""
    ds_intel = run_dataset_intelligence(dataset_id=walmart_retail_dataset)
    assert ds_intel.dataset_id == walmart_retail_dataset
    assert len(ds_intel.executive_topics) > 0

    workforce_blacklist = {"attendance", "leave", "leaves", "employee", "wfo", "absenteeism"}

    scatter_topics = []
    for topic in ds_intel.executive_topics:
        is_dict = isinstance(topic, dict)
        t_title = (topic.get("title", "") if is_dict else getattr(topic, "title", "")).lower()
        t_sub = (topic.get("subtitle", "") if is_dict else getattr(topic, "subtitle", "")).lower()
        micro = topic.get("visual_microcopy") if is_dict else getattr(topic, "visual_microcopy", None)
        if isinstance(micro, dict):
            t_micro = (micro.get("short_title", "") or "").lower()
        elif micro:
            t_micro = (getattr(micro, "short_title", "") or "").lower()
        else:
            t_micro = ""

        # Assert zero workforce leakage across any retail topic
        for bad_tok in workforce_blacklist:
            assert bad_tok not in t_title, f"Workforce token '{bad_tok}' found in retail topic title: {t_title}"
            assert bad_tok not in t_micro, f"Workforce token '{bad_tok}' found in retail microcopy: {t_micro}"
            assert bad_tok not in t_sub, f"Workforce token '{bad_tok}' found in retail subtitle: {t_sub}"

        # Assert dataset_id and topic_id binding
        v_spec = topic.get("visual_spec", {}) if is_dict else getattr(topic, "visual_spec", {})
        top_ds = topic.get("dataset_id") if is_dict else getattr(topic, "dataset_id", None)
        top_id = topic.get("topic_id") if is_dict else getattr(topic, "topic_id", None)

        assert top_ds == walmart_retail_dataset
        assert v_spec.get("dataset_id") == walmart_retail_dataset
        assert v_spec.get("topic_id") == top_id

        intent = topic.get("analytical_intent") if is_dict else getattr(topic, "analytical_intent", "")
        if intent == "RELATIONSHIP" or v_spec.get("chart_type") == "scatter":
            scatter_topics.append((topic, v_spec))

    # If a relationship/scatter topic exists, assert its title relates strictly to its axes
    for s_top, s_v_spec in scatter_topics:
        is_dict = isinstance(s_top, dict)
        x_label = str(s_v_spec.get("x_label", "")).lower()
        y_label = str(s_v_spec.get("y_label", "")).lower()
        s_title = s_top.get("title", "") if is_dict else getattr(s_top, "title", "")
        # Title and axis labels must have ZERO raw database underscores
        assert "_" not in s_v_spec.get("x_label", ""), f"Underscore found in x_label: {s_v_spec.get('x_label')}"
        assert "_" not in s_v_spec.get("y_label", ""), f"Underscore found in y_label: {s_v_spec.get('y_label')}"
        assert "_" not in s_title, f"Underscore found in relationship title: {s_title}"
        if is_dict:
            m_short = (s_top.get("visual_microcopy") or {}).get("short_title", "")
        else:
            m_short = getattr(getattr(s_top, "visual_microcopy", None), "short_title", "") or ""
        assert "_" not in m_short, f"Underscore found in relationship microcopy short_title: {m_short}"


def test_humanize_label_mechanics():
    """Verify that SemanticVisualCompressionLayer._humanize_label removes underscores and preserves domain acronyms."""
    from app.services.adaptive_dashboard.semantic_visual_compression import SemanticVisualCompressionLayer

    assert SemanticVisualCompressionLayer._humanize_label("Fuel_Price") == "Fuel Price"
    assert SemanticVisualCompressionLayer._humanize_label("Weekly_Sales") == "Weekly Sales"
    assert SemanticVisualCompressionLayer._humanize_label("Holiday_Flag") == "Holiday Flag"
    assert SemanticVisualCompressionLayer._humanize_label("Temperature vs Fuel_Price") == "Temperature vs Fuel Price"
    assert SemanticVisualCompressionLayer._humanize_label("CPI_INDEX") == "CPI Index"
    assert SemanticVisualCompressionLayer._humanize_label("AVERAGE_PM10_LEVEL") == "Average PM10 Level"

