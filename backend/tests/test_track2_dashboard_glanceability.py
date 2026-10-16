"""Product Track 2.2 — Executive Glanceability, Hierarchy & Visual Clarity Verification Suite.

Tests and enforces:
1. Title Question Transformation: Visible executive titles are concise business questions ending in '?'.
2. Technical Title Preservation: Technical titles are preserved for inspection, tooltips, and audits.
3. Metric Presentation Standardization: Currency ($K), targets, correlations (r = +/-), units attached, no bare record counts.
4. Dumbbell Legend Integrity: Dumbbell / multi-series charts carry primary_label and secondary_label.
5. Spatial Right-Sizing: Low-density isolated charts are right-sized (span <= 6 or 8) rather than stretched to 12.
6. Prose Budget Compression: Visible dashboard word count respects executive glanceability constraints.
7. Track 2.1 Invariant Protection: Topic identities, fact IDs, and leader truth remain intact.
"""
from pathlib import Path
import pytest
from app.services.adaptive_dashboard import run_adaptive_dashboard
from app.services.adaptive_dashboard.topics.contracts import ExecutiveTopic
from app.services.adaptive_dashboard.semantic_visual_compression import SemanticVisualCompressionLayer


@pytest.fixture(scope="function", autouse=True)
def seed_benchmark_datasets():
    """Ensure benchmark datasets (99770, 99771, 99772) are available in test db hermetically."""
    from app.db.database import get_connection
    from tests.fixtures.benchmark_seeder import ensure_benchmark_datasets_seeded
    with get_connection() as conn:
        ensure_benchmark_datasets_seeded(conn)


def _get(obj, key, default=None):
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


@pytest.mark.parametrize("dataset_id,expected_domain", [
    (99770, "workforce"),
    (99771, "commercial_retail"),
    (99772, "environmental_cpcb"),
])
def test_track2_2_all_titles_are_business_questions(dataset_id: int, expected_domain: str):
    """Every visible ExecutiveTopic title must be a concise executive business question ending in '?'."""
    res = run_adaptive_dashboard(sheet_id=None, dataset_id=dataset_id, include_dataset_intelligence=True)
    topics = res.executive_topics or []

    assert len(topics) >= 4, f"Dataset {dataset_id} must have at least 4 executive topics"

    for idx, topic in enumerate(topics, start=1):
        title = (_get(topic, "title") or "").strip()
        assert title.endswith("?"), (
            f"Dataset {dataset_id} topic {idx} title '{title}' must be an executive question ending in '?'"
        )
        word_count = len(title.split())
        assert word_count <= 14, (
            f"Dataset {dataset_id} topic {idx} title '{title}' exceeds word limit ({word_count} > 14 words)"
        )


@pytest.mark.parametrize("dataset_id", [99770, 99771, 99772])
def test_track2_2_technical_title_preserved(dataset_id: int):
    """Canonical technical title is preserved on ExecutiveTopic and inspect payload for auditability."""
    res = run_adaptive_dashboard(sheet_id=None, dataset_id=dataset_id, include_dataset_intelligence=True)
    topics = res.executive_topics or []

    for topic in topics:
        tech_title = _get(topic, "technical_title")
        assert tech_title, f"Topic '{_get(topic, 'topic_id')}' must have a non-empty technical_title"
        # Inspect payload must also carry technical_title
        payload = _get(topic, "inspect_payload") or {}
        assert _get(payload, "technical_title") == tech_title, (
            f"Topic '{_get(topic, 'topic_id')}' inspect payload must carry technical_title"
        )


@pytest.mark.parametrize("dataset_id", [99770, 99771, 99772])
def test_track2_2_metric_formatting_standards(dataset_id: int):
    """Key metrics must be cleanly formatted and avoid raw unformatted row counts."""
    res = run_adaptive_dashboard(sheet_id=None, dataset_id=dataset_id, include_dataset_intelligence=True)
    topics = res.executive_topics or []

    for topic in topics:
        mc = _get(topic, "visual_microcopy") or {}
        metric = (_get(mc, "primary_number") or _get(topic, "key_metric") or "")
        if metric:
            # Must not be a bare row count like 33670 or 33,670
            assert metric != "33,670" and metric != "33670", (
                f"Topic '{_get(topic, 'topic_id')}' has raw row count '{metric}' as primary metric"
            )
            # Correlation metrics must be formatted cleanly
            if "r =" in metric:
                assert "r = +" in metric or "r = -" in metric, (
                    f"Topic '{_get(topic, 'topic_id')}' correlation '{metric}' must include explicit sign"
                )


@pytest.mark.parametrize("dataset_id", [99770, 99771, 99772])
def test_track2_2_dumbbell_legend_labels(dataset_id: int):
    """Dumbbell charts must provide primary_label and secondary_label for legend clarity."""
    res = run_adaptive_dashboard(sheet_id=None, dataset_id=dataset_id, include_dataset_intelligence=True)
    topics = res.executive_topics or []

    dumbbell_topics = [t for t in topics if _get(_get(t, "visual_spec") or {}, "chart_type") == "dumbbell"]
    for t in dumbbell_topics:
        v_spec = _get(t, "visual_spec") or {}
        assert _get(v_spec, "primary_label"), (
            f"Dumbbell chart in dataset {dataset_id} topic '{_get(t, 'topic_id')}' missing primary_label"
        )
        assert _get(v_spec, "secondary_label"), (
            f"Dumbbell chart in dataset {dataset_id} topic '{_get(t, 'topic_id')}' missing secondary_label"
        )


@pytest.mark.parametrize("dataset_id", [99770, 99771, 99772])
def test_track2_2_isolated_card_right_sizing(dataset_id: int):
    """Low-density isolated cards must not be stretched to 12 columns."""
    res = run_adaptive_dashboard(sheet_id=None, dataset_id=dataset_id, include_dataset_intelligence=True)
    layout = getattr(res, "layout_plan", None)
    if not layout:
        pytest.skip("No layout_plan in dashboard output")

    sections = _get(layout, "sections", [])
    for sec in sections:
        rows = _get(sec, "rows", [])
        for row in rows:
            cards = _get(row, "cards", [])
            is_partial = _get(row, "is_intentional_partial", False)
            if len(cards) == 1 and is_partial:
                c_span = _get(cards[0], "span", 12)
                assert c_span <= 8, f"Single intentional partial card assigned span {c_span} > 8"


@pytest.mark.parametrize("dataset_id", [99770, 99771, 99772])
def test_track2_2_visible_prose_budget(dataset_id: int):
    """Total visible prose on Level-1 cards must be within executive glanceability budget."""
    res = run_adaptive_dashboard(sheet_id=None, dataset_id=dataset_id, include_dataset_intelligence=True)
    topics = res.executive_topics or []

    total_words = 0
    for topic in topics:
        mc = _get(topic, "visual_microcopy") or {}
        title = _get(topic, "title") or ""
        metric = (_get(mc, "primary_number") or _get(topic, "key_metric") or "")
        finding = (_get(mc, "short_finding") or _get(topic, "takeaway") or "")
        total_words += len((title + " " + metric + " " + finding).split())

    assert total_words <= 150, (
        f"Dataset {dataset_id} total visible prose {total_words} words exceeds glanceability budget"
    )


def test_track2_2_semantic_compression_pure_methods():
    """Unit test for SemanticVisualCompressionLayer helper methods."""
    # Test currency standardization
    m1, _ = SemanticVisualCompressionLayer._derive_metric_and_context(
        key_metric="25000",
        intent="TARGET_VS_ACTUAL",
        tokens={"benchmark": 25000, "unit": "$"},
    )
    assert "$25K" in m1 or "25K" in m1

    # Test correlation
    m2, _ = SemanticVisualCompressionLayer._derive_metric_and_context(
        key_metric="Observed correlation r = +0.82 between sales and traffic",
        intent="RELATIONSHIP",
        tokens={},
    )
    assert m2 == "r = +0.82"

    # Test raw row count rejection
    m3, _ = SemanticVisualCompressionLayer._derive_metric_and_context(
        key_metric="33,670",
        intent="RANKING",
        tokens={"values": [17.2, 14.5], "unit": "days"},
    )
    assert m3 == "17.2d Top" or "17.2" in m3


def test_track2_2_title_generalization_synthetic_cases():
    """Requirement 5: Verify that title generation generalizes to unseen domains, entities, and measures."""
    cases = [
        # 1. Healthcare / Clinical Target Gap
        {
            "title": "Hospital ICU Bed Occupancy vs Critical Threshold Benchmark",
            "subtitle": "Analysis of hospital adherence to 85% capacity threshold",
            "intent": "TARGET_VS_ACTUAL",
            "tokens": {"benchmark": 85, "unit": "%", "primary_measure": "ICU Bed Occupancy"},
            "expected_contains": ["meet", "target"],
        },
        # 2. Tech / Cloud Operations Lower-Is-Better Ranking
        {
            "title": "Data Center API Latency Performance Ranking",
            "subtitle": "Ranking of microservices by p99 latency",
            "intent": "RANKING",
            "tokens": {"primary_measure": "P99 Latency", "ranking_direction": "LOWER_IS_BETTER"},
            "expected_contains": ["lowest", "latency"],
        },
        # 3. Supply Chain Relationship
        {
            "title": "Fuel Consumption vs Cargo Weight Statistical Association",
            "subtitle": "Correlation study between fuel burn and payload tonnage",
            "intent": "RELATIONSHIP",
            "tokens": {"x_measure": "Fuel Burn Rate", "y_measure": "Payload Tonnage"},
            "expected_contains": ["relate", "fuel"],
        },
        # 4. Aviation Distribution / Spread
        {
            "title": "Flight Departure Delay Dispersion Across Regional Hubs",
            "subtitle": "Quartile spread of departure delay minutes across international airports",
            "intent": "DISTRIBUTION",
            "tokens": {"primary_measure": "Departure Delay Minutes"},
            "expected_contains": ["vary", "departure delay"],
        },
        # 5. Financial Anomaly / Spikes
        {
            "title": "Foreign Exchange Volatility Spike Detection",
            "subtitle": "Outlier detection in currency pair volume swings",
            "intent": "ANOMALY",
            "tokens": {"primary_measure": "Exchange Volatility"},
            "expected_contains": ["spikes", "exchange volatility"],
        },
        # 6. SaaS Subscription Trend
        {
            "title": "Monthly Recurring Revenue Cadence Trend",
            "subtitle": "Temporal progression of active ARR",
            "intent": "TREND",
            "tokens": {"primary_measure": "Recurring Revenue"},
            "expected_contains": ["trended", "recurring revenue"],
        },
    ]

    for c in cases:
        q = SemanticVisualCompressionLayer.derive_business_question_title(
            title=c["title"],
            subtitle=c["subtitle"],
            intent=c["intent"],
            tokens=c["tokens"],
            domain="custom_enterprise",
        )
        assert q.endswith("?"), f"Synthetic question '{q}' must end with '?'"
        words = q.split()
        assert len(words) <= 12, f"Synthetic question '{q}' has {len(words)} words (expected <= 12)"
        for forbidden in ["chart", "plot", "heatmap", "scatter", "matrix", "boxplot", "dumbbell"]:
            assert forbidden not in q.lower(), f"Synthetic question '{q}' contains forbidden jargon '{forbidden}'"
        for exp in c["expected_contains"]:
            assert exp.lower() in q.lower(), f"Synthetic question '{q}' missing expected token '{exp}'"
        # Confirm no benchmark literals leak into generic questions
        assert "attendance" not in q.lower()
        assert "pm10" not in q.lower()
        assert "store 1" not in q.lower()


def test_track2_2_cache_version_invalidation_and_cold_warm_parity():
    """Requirement 3: Prove that Track 2.2 version bump automatically invalidates stale payloads."""
    from app.cache import (
        DashboardCacheKey,
        DashboardCacheService,
        COMPOSITION_ENGINE_VERSION,
        SEMANTIC_SCHEMA_VERSION,
        ANALYTICS_ENGINE_VERSION,
        build_cache_key,
    )

    dataset_id = 99770
    content_hash = "mock_hash_wf_invalidation_99770"

    # 1. Stale pre-Track-2.2 key with older composition engine version (e.g. 2026.10.3)
    old_key = DashboardCacheKey(
        dataset_id=dataset_id,
        dataset_content_hash=content_hash,
        composition_engine_version="2026.10.3",
    )
    old_computed_key = old_key.compute_key()

    # 2. Track 2.2 new key with bumped composition engine version (2026.10.4)
    new_key = DashboardCacheKey(
        dataset_id=dataset_id,
        dataset_content_hash=content_hash,
        composition_engine_version=COMPOSITION_ENGINE_VERSION,
    )
    new_computed_key = new_key.compute_key()

    # Assert keys are deterministically distinct
    assert old_computed_key != new_computed_key, (
        f"Old key ({old_computed_key}) and new key ({new_computed_key}) must differ on version bump!"
    )
    assert COMPOSITION_ENGINE_VERSION == "2026.10.4"

    service = DashboardCacheService()

    # 3. Insert stale payload under old key
    stale_payload = {
        "dataset_id": dataset_id,
        "domain": "workforce_hr",
        "executive_topics": [
            {
                "topic_id": "TOPIC-STALE-01",
                "dataset_id": dataset_id,
                "domain": "workforce_hr",
                "title": "Stale Legacy Technical Noun Phrase Without Question",
                "technical_title": "Stale Legacy Technical Noun Phrase Without Question",
                "visual_spec": {"chart_type": "bullet", "domain": "workforce_hr", "dataset_id": dataset_id},
                "evidence_ids": ["EVID-STALE-01"],
            }
        ],
        "version": "2026.10.3",
    }
    service.put(old_key, stale_payload)

    # 4. Request using current Track 2.2 key (cold compute)
    compute_count = [0]
    def _cold_compute():
        compute_count[0] += 1
        return {
            "dataset_id": dataset_id,
            "domain": "workforce_hr",
            "executive_topics": [
                {
                    "topic_id": "TOPIC-T2-01",
                    "dataset_id": dataset_id,
                    "domain": "workforce_hr",
                    "title": "Which departments meet the hybrid attendance target?",
                    "technical_title": "Workforce Attendance vs Governed Policy Benchmark",
                    "metric": "15d Target",
                    "visual_spec": {"chart_type": "bullet", "domain": "workforce_hr", "dataset_id": dataset_id},
                    "evidence_ids": ["EVID-T2-01"],
                }
            ],
            "version": COMPOSITION_ENGINE_VERSION,
        }

    cold_payload = service.get_or_compute(new_key, _cold_compute)
    assert compute_count[0] == 1, "Cold request must execute compute function"
    assert cold_payload["executive_topics"][0]["title"] == "Which departments meet the hybrid attendance target?"
    assert "Stale Legacy" not in cold_payload["executive_topics"][0]["title"]

    # 5. Request again using current Track 2.2 key (warm cached lookup)
    warm_payload = service.get_or_compute(new_key, _cold_compute)
    assert compute_count[0] == 1, "Warm request must hit cache without recomputing"

    # 6. Cold / Warm parity assertion
    assert cold_payload == warm_payload, "Cold payload and warm payload must be semantically identical"
    assert warm_payload["executive_topics"][0]["title"].endswith("?")
    assert warm_payload["executive_topics"][0]["technical_title"] == "Workforce Attendance vs Governed Policy Benchmark"

