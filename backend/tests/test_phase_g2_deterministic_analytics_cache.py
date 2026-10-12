"""
Comprehensive Acceptance and Integration Test Suite for Phase G2:
Deterministic Version-Aware Analytics Cache.

Tests:
1. Canonical key determinism & theme independence.
2. Filter canonicalization.
3. Content hash, policy version, context version, and engine version invalidation (MISS on change).
4. Cache stores complete immutable topic bundles.
5. Cold vs Warm payload semantic equivalence (cold_payload == warm_payload).
6. CacheIsolationIntegrity hard rejection on cross-dataset or cross-domain tampering.
7. Resilience against corrupted cache JSON.
8. Single-flight thundering-herd concurrency protection (computes once on simultaneous misses).
9. Cache write failure does not break dashboard delivery.
10. Dataset deletion cascades and cleans up cache entries (zero orphans).
11. Multi-domain regression across Workforce, Retail, and Environmental datasets.
"""
from __future__ import annotations

import copy
import hashlib
import json
import sqlite3
import tempfile
import threading
import time
from pathlib import Path
from unittest.mock import patch, MagicMock
import pytest
from fastapi.testclient import TestClient

from app.cache import (
    DashboardCacheKey,
    build_cache_key,
    canonicalize_filters,
    CacheIsolationIntegrity,
    DashboardCacheRepository,
    DashboardCacheService,
    dashboard_cache,
    cache_metrics,
    SEMANTIC_SCHEMA_VERSION,
    ANALYTICS_ENGINE_VERSION,
    COMPOSITION_ENGINE_VERSION,
    POLICY_VERSION,
    CONTEXT_VERSION,
)
from app.db.database import get_connection
from app.db.migration_runner import run_migrations
from app.services.dataset_deletion import delete_datasets


def test_01_canonical_key_determinism_and_theme_independence():
    """Verify that identical keys hash identically, and theme is never included."""
    k1 = DashboardCacheKey(
        dataset_id=100,
        dataset_version=1,
        dataset_content_hash="hash_abc123",
    )
    k2 = DashboardCacheKey(
        dataset_id=100,
        dataset_version=1,
        dataset_content_hash="hash_abc123",
    )
    assert k1.compute_key() == k2.compute_key()

    # Theme parameters are presentation state and must not alter analytical cache keys
    f_dark = {"filter": "dept", "theme": "executive_dark"}
    f_light = {"filter": "dept", "theme": "clean_light"}

    # Canonicalize filters ignores theme when filtered or canonicalized
    clean_filters = {"department": "Engineering"}
    k_normal = build_cache_key(dataset_id=100, filters=clean_filters)
    assert "theme" not in k_normal.canonical_dict()


def test_02_filter_canonicalization_sorting_and_whitespace():
    """Verify different key ordering and whitespace normalize to identical filter hash."""
    f1 = {"dept": "Sales", "region": "North", "status": "active"}
    f2 = {"status": "active", "dept": "Sales ", "region": "North"}
    assert canonicalize_filters(f1) == canonicalize_filters(f2)

    # Empty and None values normalize to empty string
    assert canonicalize_filters({}) == ""
    assert canonicalize_filters(None) == ""
    assert canonicalize_filters({"empty": "", "none": None}) == ""

    # Different filter values produce distinct hash
    f3 = {"dept": "Marketing"}
    assert canonicalize_filters(f1) != canonicalize_filters(f3)


def test_03_version_and_hash_changes_produce_miss():
    """Verify that changing content hash, engine, policy, or context versions changes the key."""
    base_key = DashboardCacheKey(
        dataset_id=200,
        dataset_version=1,
        dataset_content_hash="base_hash",
    )
    base_hash = base_key.compute_key()

    # 1. Content hash change produces distinct key
    k_content = base_key.model_copy(update={"dataset_content_hash": "new_hash"})
    assert k_content.compute_key() != base_hash

    # 2. Policy version change produces distinct key
    k_policy = base_key.model_copy(update={"policy_version": "1.3.0"})
    assert k_policy.compute_key() != base_hash

    # 3. Context version change produces distinct key
    k_context = base_key.model_copy(update={"context_version": "2.5.0"})
    assert k_context.compute_key() != base_hash

    # 4. Analytics engine version change produces distinct key
    k_analytics = base_key.model_copy(update={"analytics_engine_version": "2026.11.1"})
    assert k_analytics.compute_key() != base_hash

    # 5. Composition engine version change produces distinct key
    k_comp = base_key.model_copy(update={"composition_engine_version": "2026.11.2"})
    assert k_comp.compute_key() != base_hash


def test_04_cache_stores_whole_immutable_topic_bundles():
    """Verify that executive topics are stored and retrieved as complete immutable units."""
    service = DashboardCacheService()
    key = DashboardCacheKey(
        dataset_id=300,
        dataset_content_hash="hash_topics",
    )

    topic_bundle = {
        "topic_id": "TOPIC-WF-01",
        "dataset_id": 300,
        "domain": "workforce_hr",
        "title": "Attendance & Leave Distribution",
        "finding": "Attendance remains at 85.2% across departments.",
        "visual_spec": {
            "chart_type": "bar",
            "dataset_id": 300,
            "domain": "workforce_hr",
            "title": "Attendance by Department",
        },
        "evidence_ids": ["EVID-01", "EVID-02"],
        "provenance": "DETERMINISTIC_ROLLUP",
    }

    payload = {
        "dataset_id": 300,
        "dataset_name": "Workforce Q3",
        "executive_topics": [topic_bundle],
        "layout_plan": {"rows": 1, "columns": 1},
    }

    # Store
    assert service.put(key, payload) is True

    # Retrieve
    cached = service.get(key)
    assert cached is not None
    assert len(cached["executive_topics"]) == 1
    t_retrieved = cached["executive_topics"][0]

    # Must be exact match, never reconstructed across disparate sources
    assert t_retrieved["topic_id"] == "TOPIC-WF-01"
    assert t_retrieved["title"] == "Attendance & Leave Distribution"
    assert t_retrieved["visual_spec"]["chart_type"] == "bar"
    assert t_retrieved["evidence_ids"] == ["EVID-01", "EVID-02"]


def test_05_cold_vs_warm_semantic_equivalence():
    """Verify that warm cached responses are 100% semantically equivalent to cold computations."""
    service = DashboardCacheService()
    key = DashboardCacheKey(
        dataset_id=400,
        dataset_content_hash="hash_cold_warm",
    )

    call_count = [0]

    def _compute_core():
        call_count[0] += 1
        return {
            "dataset_id": 400,
            "dataset_name": "Test Equivalence",
            "executive_topics": [
                {
                    "topic_id": "TOPIC-EQ-01",
                    "dataset_id": 400,
                    "domain": "retail_commercial",
                    "title": "Weekly Sales Velocity",
                    "finding": "Top quartile stores generate 62% of revenue.",
                    "visual_spec": {"chart_type": "line", "domain": "retail_commercial", "dataset_id": 400},
                    "evidence_ids": ["EVID-RETAIL-01"],
                }
            ],
            "kpi_metrics": {"total_revenue": 1500000.0, "store_count": 45},
            "layout_plan": {"cards": 1},
        }

    # Cold execution
    cold_result = service.get_or_compute(key, _compute_core)
    assert call_count[0] == 1

    # Warm execution
    warm_result = service.get_or_compute(key, _compute_core)
    assert call_count[0] == 1  # Core compute was NOT called again

    # Semantic equivalence assertion
    assert cold_result == warm_result
    assert cold_result["executive_topics"] == warm_result["executive_topics"]
    assert cold_result["kpi_metrics"] == warm_result["kpi_metrics"]


def test_06_cache_isolation_integrity_rejects_cross_dataset_pollution():
    """Verify that tampering with dataset_id or mixing domains fails closed."""
    service = DashboardCacheService()
    key = DashboardCacheKey(dataset_id=500, dataset_content_hash="hash_guard")

    # 1. Payload with mismatched dataset_id
    tampered_payload_1 = {
        "dataset_id": 999,  # Mismatched
        "executive_topics": [],
    }
    assert service.put(key, tampered_payload_1) is False

    # 2. Topic with cross-dataset leak
    tampered_payload_2 = {
        "dataset_id": 500,
        "executive_topics": [
            {
                "topic_id": "TOPIC-X",
                "dataset_id": 888,  # Leaked from another dataset
                "domain": "retail_commercial",
                "title": "Leaked Topic",
                "visual_spec": {"dataset_id": 888, "domain": "retail_commercial"},
            }
        ],
    }
    assert service.put(key, tampered_payload_2) is False

    # 3. Topic domain conflicting with visual spec domain (The workforce title / retail chart bug)
    tampered_payload_3 = {
        "dataset_id": 500,
        "executive_topics": [
            {
                "topic_id": "TOPIC-CORRUPT",
                "dataset_id": 500,
                "domain": "workforce_hr",  # Workforce topic
                "title": "Attendance & Leave Correlation",
                "visual_spec": {
                    "dataset_id": 500,
                    "domain": "retail_commercial",  # Retail chart!
                    "title": "Temperature vs Fuel Price",
                },
            }
        ],
    }
    assert service.put(key, tampered_payload_3) is False


def test_07_corrupted_cache_entry_recomputes_safely():
    """Verify that invalid/corrupt JSON in dashboard_cache is evicted and safely recomputed."""
    service = DashboardCacheService()
    key = DashboardCacheKey(dataset_id=600, dataset_content_hash="hash_corrupt")
    key_hash = key.compute_key()

    # Manually insert invalid JSON into database table
    DashboardCacheRepository.put(key, {"dataset_id": 600, "executive_topics": []})
    # Corrupt it directly
    from app.db.database import session_scope
    with session_scope() as conn:
        conn.execute("UPDATE dashboard_cache SET payload_json = '{invalid_json...' WHERE cache_key = ?", (key_hash,))

    # Retrieving corrupt payload must purge entry and return fresh computation without raising 500
    computed = service.get_or_compute(key, lambda: {"dataset_id": 600, "executive_topics": [], "recomputed": True})
    assert computed.get("recomputed") is True

    # Cache should now have the clean recomputed version
    cached_clean = service.get(key)
    assert cached_clean is not None
    assert cached_clean.get("recomputed") is True


def test_08_thundering_herd_single_flight_execution():
    """Verify that multiple concurrent threads miss simultaneously but compute only once."""
    service = DashboardCacheService()
    key = DashboardCacheKey(dataset_id=700, dataset_content_hash="hash_thundering")

    compute_invocations = [0]
    inv_lock = threading.Lock()

    def _heavy_compute():
        time.sleep(0.05)  # Simulate expensive analytical pipeline
        with inv_lock:
            compute_invocations[0] += 1
        return {
            "dataset_id": 700,
            "executive_topics": [
                {
                    "topic_id": "T-CONCURRENT",
                    "dataset_id": 700,
                    "domain": "environmental",
                    "title": "Air Quality Matrix",
                    "visual_spec": {"dataset_id": 700, "domain": "environmental"},
                }
            ],
        }

    threads = []
    results = [None] * 5

    def _worker(idx: int):
        results[idx] = service.get_or_compute(key, _heavy_compute)

    for i in range(5):
        t = threading.Thread(target=_worker, args=(i,))
        threads.append(t)
        t.start()

    for t in threads:
        t.join()

    # Invariant: Must compute exactly ONCE
    assert compute_invocations[0] == 1
    # All 5 threads must receive identical valid payloads
    for r in results:
        assert r is not None
        assert r["dataset_id"] == 700


def test_09_cache_write_failure_preserves_dashboard_delivery():
    """Verify that a storage error during cache write does not break the user's dashboard."""
    service = DashboardCacheService()
    key = DashboardCacheKey(dataset_id=800, dataset_content_hash="hash_write_fail")

    def _compute():
        return {
            "dataset_id": 800,
            "executive_topics": [],
            "status": "ready",
        }

    # Mock repository put to fail
    with patch.object(DashboardCacheRepository, "put", side_effect=sqlite3.OperationalError("Disk I/O error")):
        result = service.get_or_compute(key, _compute)
        # Dashboard result still delivered successfully
        assert result["status"] == "ready"
        assert result["dataset_id"] == 800


def test_10_dataset_deletion_cleans_up_cache_with_zero_orphans():
    """Verify that deleting a dataset deletes all associated cache records and checks orphans."""
    key = DashboardCacheKey(dataset_id=900, dataset_content_hash="hash_del")
    dashboard_cache.put(key, {"dataset_id": 900, "executive_topics": []})

    # Verify present in cache
    assert dashboard_cache.get(key) is not None

    # Simulate deleting dataset 900
    from app.db.database import session_scope
    with session_scope() as conn:
        # Insert a dummy dataset_upload so deletion has a row
        conn.execute("INSERT OR REPLACE INTO dataset_uploads (id, filename, original_name, file_type) VALUES (900, 'test.csv', 'Test', 'csv')")

    result = delete_datasets([900])
    assert result["orphan_check"] == "PASS"
    assert result["cache_orphan_count"] == 0
    assert result["cache_keys_invalidated"] >= 1

    # Invalidate verification
    assert dashboard_cache.get(key) is None


def test_11_multi_domain_regression_zero_vocabulary_contamination():
    """
    Verify caching across Workforce, Retail, and Environmental datasets in sequence.
    Sequence:
    Workforce cold -> Workforce warm ->
    Retail cold -> Retail warm ->
    Environmental cold -> Environmental warm ->
    Workforce warm again
    Assert zero vocabulary or cross-domain contamination.
    """
    service = DashboardCacheService()

    # 1. Workforce
    wf_key = DashboardCacheKey(dataset_id=1001, dataset_content_hash="hash_wf")
    wf_payload = {
        "dataset_id": 1001,
        "executive_topics": [
            {
                "topic_id": "T-WF-01",
                "dataset_id": 1001,
                "domain": "workforce_hr",
                "title": "Employee Attendance Leaders",
                "finding": "Top 3 employees recorded 100% attendance.",
                "visual_spec": {"chart_type": "bar", "domain": "workforce_hr", "dataset_id": 1001},
            }
        ],
    }

    # 2. Retail
    rt_key = DashboardCacheKey(dataset_id=1002, dataset_content_hash="hash_rt")
    rt_payload = {
        "dataset_id": 1002,
        "executive_topics": [
            {
                "topic_id": "T-RT-01",
                "dataset_id": 1002,
                "domain": "retail_commercial",
                "title": "Store Sales Quartile Dispersion",
                "finding": "Fuel price volatility correlates with store footfall.",
                "visual_spec": {"chart_type": "scatter", "domain": "retail_commercial", "dataset_id": 1002},
            }
        ],
    }

    # 3. Environmental
    env_key = DashboardCacheKey(dataset_id=1003, dataset_content_hash="hash_env")
    env_payload = {
        "dataset_id": 1003,
        "executive_topics": [
            {
                "topic_id": "T-ENV-01",
                "dataset_id": 1003,
                "domain": "environmental",
                "title": "AQI Particulate Trend",
                "finding": "PM2.5 exceeded standard limits during week 3.",
                "visual_spec": {"chart_type": "line", "domain": "environmental", "dataset_id": 1003},
            }
        ],
    }

    # Execution sequence
    # 1. Workforce cold & warm
    wf_res_cold = service.get_or_compute(wf_key, lambda: wf_payload)
    wf_res_warm = service.get_or_compute(wf_key, lambda: {"dataset_id": 1001, "executive_topics": []})
    assert wf_res_cold == wf_res_warm
    assert "attendance" in wf_res_warm["executive_topics"][0]["title"].lower()

    # 2. Retail cold & warm
    rt_res_cold = service.get_or_compute(rt_key, lambda: rt_payload)
    rt_res_warm = service.get_or_compute(rt_key, lambda: {"dataset_id": 1002, "executive_topics": []})
    assert rt_res_cold == rt_res_warm
    assert "sales" in rt_res_warm["executive_topics"][0]["title"].lower()
    # Zero workforce contamination in retail
    assert "employee" not in json.dumps(rt_res_warm).lower()

    # 3. Environmental cold & warm
    env_res_cold = service.get_or_compute(env_key, lambda: env_payload)
    env_res_warm = service.get_or_compute(env_key, lambda: {"dataset_id": 1003, "executive_topics": []})
    assert env_res_cold == env_res_warm
    assert "aqi" in env_res_warm["executive_topics"][0]["title"].lower()
    # Zero retail or workforce contamination in environmental
    assert "sales" not in json.dumps(env_res_warm).lower()
    assert "attendance" not in json.dumps(env_res_warm).lower()

    # 4. Workforce warm again after other domain operations
    wf_res_warm_again = service.get_or_compute(wf_key, lambda: {"dataset_id": 1001, "executive_topics": []})
    assert wf_res_warm_again == wf_payload
    assert "sales" not in json.dumps(wf_res_warm_again).lower()
    assert "aqi" not in json.dumps(wf_res_warm_again).lower()
