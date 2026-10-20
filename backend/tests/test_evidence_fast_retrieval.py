"""Unit and regression tests for Evidence & Lineage Fast Retrieval Optimization."""

import hashlib
import json
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.db.database import get_connection, init_db
from app.services.evidence.evidence_retrieval import (
    get_targeted_evidence,
    get_targeted_lineage,
    get_targeted_source_context,
    get_paginated_related_evidence,
)

P0_EXPECTED_SHA = "1561d64eeae26f4d30926371740d6ca9dc41eb6ea7c537281763b7d5aabd9496"


@pytest.fixture(autouse=True)
def seed_test_database():
    """Initializes the isolated test DB and seeds sheet 9967451 with sample rows."""
    conn = get_connection()
    try:
        init_db(conn)
        # Create dataset upload and sheet
        conn.execute(
            """
            INSERT OR REPLACE INTO dataset_uploads (id, filename, original_name, file_type, row_count, col_count)
            VALUES (99795, 'test.csv', 'test.csv', 'csv', 10, 3)
            """
        )
        cols = ["Category", "India/State/Union Territory", "Population 2011"]
        conn.execute(
            """
            INSERT OR REPLACE INTO sheets (id, dataset_id, name, display_name, columns_json, profile_json, row_count)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                9967451,
                99795,
                "Sheet1",
                "India State Population Data",
                json.dumps(cols),
                json.dumps({"snapshot_hash": "0bf1405d"}),
                10,
            ),
        )

        # Insert 10 sample rows
        for i in range(10):
            row_dict = {
                "Category": "State" if i > 0 else "India",
                "India/State/Union Territory": f"State_{i}",
                "Population 2011": 1000000 * (i + 1),
            }
            conn.execute(
                "INSERT INTO sheet_rows (sheet_id, row_index, data_json) VALUES (?, ?, ?)",
                (9967451, i, json.dumps(row_dict)),
            )
        conn.commit()
    finally:
        conn.close()


@pytest.fixture
def client():
    return TestClient(app)


def test_targeted_evidence_service():
    """Verify that get_targeted_evidence returns small, bounded payload with verified grain and status."""
    conn = get_connection()
    try:
        ev = get_targeted_evidence(
            conn,
            evidence_id="EVID-S9967451-EVID-002",
            dataset_id=99795,
            sheet_id=9967451,
            topic_id="TOPIC-6fbddfb2",
        )
        assert ev is not None
        assert ev["evidence_id"] == "EVID-S9967451-EVID-002"
        assert ev["status"] == "VERIFIED"
        assert ev["confidence"] in ("HIGH", "MEDIUM")
        assert ev["grain"] is not None
        assert ev["has_lineage"] is True
        assert ev["has_source_context"] is True
        assert ev["related_evidence_count"] > 0
        assert "Tail Burden" in ev["title"] or "recipe_s12" in ev["metric_name"]

        # Payload size bounding check (< 1.5 KB serialized)
        payload_bytes = len(json.dumps(ev).encode("utf-8"))
        assert payload_bytes < 1500, f"Targeted evidence payload {payload_bytes} exceeds 1.5 KB limit"
    finally:
        conn.close()


def test_targeted_lineage_service():
    """Verify that get_targeted_lineage returns bounded 4-step lineage trace on demand."""
    conn = get_connection()
    try:
        lin = get_targeted_lineage(
            conn,
            evidence_id="EVID-S9967451-EVID-002",
            sheet_id=9967451,
        )
        assert lin["evidence_id"] == "EVID-S9967451-EVID-002"
        assert lin["verified"] is True
        assert len(lin["steps"]) == 4
        assert len(lin["downstream_consumers"]) >= 3

        # Payload size bounding check (< 2 KB serialized)
        payload_bytes = len(json.dumps(lin).encode("utf-8"))
        assert payload_bytes < 2000, f"Lineage payload {payload_bytes} exceeds 2 KB limit"
    finally:
        conn.close()


def test_targeted_source_context_service():
    """Verify that get_targeted_source_context returns bounded rows (never whole sheet)."""
    conn = get_connection()
    try:
        src = get_targeted_source_context(
            conn,
            evidence_id="EVID-S9967451-EVID-002",
            sheet_id=9967451,
            limit=10,
        )
        assert src["evidence_id"] == "EVID-S9967451-EVID-002"
        assert len(src["rows"]) == 10
        assert len(src["columns"]) > 0
        assert src["total_rows"] == 10
    finally:
        conn.close()


def test_paginated_related_evidence_service():
    """Verify that get_paginated_related_evidence bounds page size to 25 and supports server-side pagination."""
    conn = get_connection()
    try:
        res_p1 = get_paginated_related_evidence(
            conn,
            sheet_id=9967451,
            page=1,
            limit=25,
        )
        assert len(res_p1["items"]) <= 25
        assert res_p1["total"] > 0
        assert res_p1["page"] == 1
        assert res_p1["limit"] == 25
        assert "has_next" in res_p1
        assert "has_previous" in res_p1

        # Test search filter
        search_res = get_paginated_related_evidence(
            conn,
            sheet_id=9967451,
            search="Population",
        )
        assert len(search_res["items"]) > 0
    finally:
        conn.close()


def test_targeted_evidence_api_endpoints(client):
    """Verify HTTP API contracts for targeted evidence retrieval and server-side pagination."""
    # 1. Targeted evidence
    r = client.get("/api/analytics/overview/evidence/EVID-S9967451-EVID-002?dataset_id=99795&sheet_id=9967451&topic_id=TOPIC-6fbddfb2")
    assert r.status_code == 200
    data = r.json()
    assert data["evidence_id"] == "EVID-S9967451-EVID-002"
    assert data["status"] == "VERIFIED"

    # 2. Lineage
    r_lin = client.get("/api/analytics/overview/evidence/EVID-S9967451-EVID-002/lineage?sheet_id=9967451")
    assert r_lin.status_code == 200
    lin_data = r_lin.json()
    assert len(lin_data["steps"]) == 4

    # 3. Source Context
    r_src = client.get("/api/analytics/overview/evidence/EVID-S9967451-EVID-002/source-context?sheet_id=9967451&limit=5")
    assert r_src.status_code == 200
    src_data = r_src.json()
    assert len(src_data["rows"]) == 5

    # 4. Paginated evidence (Page 1)
    r_p1 = client.get("/api/analytics/overview/evidence?sheet_id=9967451&page=1&limit=25")
    assert r_p1.status_code == 200
    p1_data = r_p1.json()
    assert len(p1_data["items"]) <= 25
    assert p1_data["page"] == 1
    assert p1_data["limit"] == 25
    assert "total" in p1_data
    assert "total_pages" in p1_data
    assert "has_next" in p1_data
    assert "has_previous" in p1_data
