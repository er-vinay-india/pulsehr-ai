"""Product Track 2.1 Regression Tests: Executive Dashboard Data Integrity & Content Correctness.

Verifies the 4 critical P0 integrity fixes:
1. DEF-T2-01: Cross-domain summary leak prevention (Strategy 2 retail check strictly domain-governed).
2. DEF-T2-02: Screen-reader accessibility utility definition (.sr-only / .visually-hidden in CSS).
3. DEF-T2-03: Sentence subject integrity, grammatical completeness, and dangling-token pruning.
4. DEF-T2-04: Environmental visual/narrative leader parity (Delhi 210 µg/m³ peak across chart and story).
"""
import re
from pathlib import Path
import pytest

from app.services.adaptive_dashboard.semantic_visual_compression import (
    SemanticVisualCompressionLayer,
    VisualMicrocopy,
)
from app.services.adaptive_dashboard.contracts import (
    SemanticContract,
    SourceManifest,
    GlanceSpec,
    ExplainSpec,
    InspectSpec,
    EvidenceResult,
)
from app.services.adaptive_dashboard.legacy_elements import (
    build_segment_disparity_element,
    build_decision_focus_element,
)
from app.services.adaptive_dashboard import run_adaptive_dashboard


@pytest.fixture(scope="function", autouse=True)
def seed_benchmark_datasets():
    """Ensure benchmark datasets (99770, 99771, 99772) are available in test db."""
    from app.db.database import get_connection
    real_db = Path(__file__).resolve().parents[1] / "data" / "db" / "pulsehr.sqlite3"
    with get_connection() as conn:
        has_99770 = conn.execute("SELECT 1 FROM dataset_uploads WHERE id = 99770").fetchone()
        if not has_99770 and real_db.exists():
            conn.execute(f'ATTACH DATABASE "{real_db}" AS real_source')
            conn.execute("INSERT OR REPLACE INTO dataset_uploads (id, filename, original_name, file_type, display_name) SELECT id, filename, original_name, file_type, display_name FROM real_source.dataset_uploads WHERE id IN (99770, 99771, 99772)")
            conn.execute("INSERT OR REPLACE INTO sheets (id, dataset_id, name, display_name, columns_json, profile_json, row_count) SELECT id, dataset_id, name, display_name, columns_json, profile_json, row_count FROM real_source.sheets WHERE dataset_id IN (99770, 99771, 99772)")
            conn.execute("INSERT OR REPLACE INTO sheet_rows (id, sheet_id, row_index, data_json) SELECT id, sheet_id, row_index, data_json FROM real_source.sheet_rows WHERE sheet_id IN (SELECT id FROM real_source.sheets WHERE dataset_id IN (99770, 99771, 99772))")
            try:
                conn.execute("INSERT OR REPLACE INTO sheet_relationships SELECT * FROM real_source.sheet_relationships WHERE left_sheet_id IN (SELECT id FROM real_source.sheets WHERE dataset_id IN (99770, 99771, 99772))")
            except Exception:
                pass
            conn.commit()
            conn.execute("DETACH DATABASE real_source")


def test_t2_01_retail_disparity_strategy_strict_domain_isolation():
    """Verify that Strategy 2 (Store sales density disparity) ONLY executes for commercial_retail domain."""
    # Synthetic contract with Location and PM10 (non-retail domain, dept_col=None)
    manifest = SourceManifest(
        sheet_id=101,
        dataset_id=201,
        file_name="environmental_air_quality.xlsx",
        sheet_name="Annual_AQI_Monitoring",
        row_count=100,
        col_count=4,
        snapshot="env_snap_test_123",
        display_name="Annual AQI Monitoring",
    )
    env_contract = SemanticContract(
        layout="long_tabular",
        entity_type="monitoring_station",
        entity_identifiers=["Location"],
        primary_measure="PM10",
        grain_description="Station-level pollutant observation",
        domain="demographics_public",
        verification_basis="Automated classification",
    )

    rows = [
        {"Location": "Station A", "PM10": 195.0, "SO2": 22.0, "NO2": 45.0},
        {"Location": "Station B", "PM10": 210.0, "SO2": 18.0, "NO2": 32.0},
        {"Location": "Station C", "PM10": 140.0, "SO2": 15.0, "NO2": 28.0},
        {"Location": "Station D", "PM10": 85.0, "SO2": 12.0, "NO2": 22.0},
    ]

    quinary = build_segment_disparity_element(
        manifest=manifest,
        contract=env_contract,
        rows=rows,
    )

    assert quinary is not None
    # Must NOT be retail concept
    assert "retail" not in quinary.business_concept.lower()
    assert "store" not in quinary.dimension_name.lower()
    assert quinary.unit != "$"
    assert "/wk" not in quinary.formatted_spread


def test_t2_01_retail_decision_focus_strict_domain_isolation():
    """Verify that retail decision focus is never generated for non-retail datasets."""
    manifest = SourceManifest(
        sheet_id=101,
        dataset_id=201,
        file_name="environmental_air_quality.xlsx",
        sheet_name="Annual_AQI_Monitoring",
        row_count=100,
        col_count=4,
        snapshot="env_snap_test_123",
        display_name="Annual AQI Monitoring",
    )
    env_contract = SemanticContract(
        layout="long_tabular",
        entity_type="monitoring_station",
        entity_identifiers=["Location"],
        primary_measure="PM10",
        grain_description="Station-level pollutant observation",
        domain="demographics_public",
        verification_basis="Automated classification",
    )

    rows = [
        {"Location": "Station A", "PM10": 195.0},
        {"Location": "Station B", "PM10": 210.0},
    ]

    quinary = build_segment_disparity_element(
        manifest=manifest,
        contract=env_contract,
        rows=rows,
    )

    decision = build_decision_focus_element(
        manifest=manifest,
        contract=env_contract,
        rows=rows,
        quinary_element=quinary,
    )

    assert decision is not None
    assert "retail" not in decision.business_concept.lower()
    assert decision.unit != "$"
    assert "store" not in decision.subject_type.lower()


def test_t2_02_css_sr_only_utility_is_defined():
    """Verify that .sr-only and .visually-hidden rules are defined with proper CSS rules."""
    repo_root = Path(__file__).resolve().parent.parent.parent
    base_scss = repo_root / "frontend" / "src" / "styles" / "_base.scss"
    assert base_scss.exists(), f"Could not find {base_scss}"

    css_content = base_scss.read_text(encoding="utf-8")
    assert ".sr-only" in css_content
    assert ".visually-hidden" in css_content
    assert "position: absolute !important" in css_content
    assert "clip: rect(0, 0, 0, 0) !important" in css_content
    assert "overflow: hidden !important" in css_content


def test_t2_03_compression_preserves_sentence_subjects():
    """Verify that semantic compression never strips grammatical sentence subjects."""
    # Case 1: Attendance policy benchmark
    takeaway_policy = "Core departments meet or exceed the 15-day hybrid attendance benchmark."
    micro_policy = SemanticVisualCompressionLayer.compress_topic(
        title="Workforce Attendance vs Governed Policy Benchmark",
        takeaway=takeaway_policy,
        intent="TARGET_VS_ACTUAL",
        domain="workforce",
    )
    assert micro_policy.short_finding.startswith("Core departments"), (
        f"Subject 'Core departments' was stripped: {micro_policy.short_finding}"
    )
    assert micro_policy.short_finding.endswith(".")
    assert len(micro_policy.short_finding.split()) <= 12

    # Case 2: Relationship operational dependency
    takeaway_rel = "Observed operational dependency (r = -0.44) between presence and approved leaves."
    micro_rel = SemanticVisualCompressionLayer.compress_topic(
        title="Attendance vs Leaves Association",
        takeaway=takeaway_rel,
        intent="RELATIONSHIP",
        domain="workforce",
    )
    assert micro_rel.short_finding.startswith("Observed operational dependency") or micro_rel.short_finding.startswith("Operational dependency"), (
        f"Subject was mangled: {micro_rel.short_finding}"
    )
    assert not micro_rel.short_finding.startswith("operational dependency (r"), "Initial capitalization was lost"
    assert micro_rel.short_finding.endswith(".")
    assert len(micro_rel.short_finding.split()) <= 12


def test_t2_03_truncate_words_prunes_dangling_tokens():
    """Verify that truncate_words does not end on trailing prepositions or conjunctions."""
    text = "The quick brown fox jumps over the lazy dog and into the deep dark woods"
    truncated = SemanticVisualCompressionLayer.truncate_words(text, max_words=10, suffix=".")
    # 10 words is: "The quick brown fox jumps over the lazy dog and"
    # "and" must be pruned!
    assert not truncated.endswith("and."), f"Ended with dangling 'and': {truncated}"
    assert truncated.endswith("dog.")


def test_t2_03_semicolon_clause_compression():
    """Verify that compound sentences with semicolons preserve the clean primary clause."""
    compound = "Store 1 and Store 2 exceed target quota; Store 3 and 4 lag by up to $4.5K."
    micro = SemanticVisualCompressionLayer.compress_topic(
        title="Store Performance vs Monthly Quota Target",
        takeaway=compound,
        intent="TARGET_VS_ACTUAL",
        domain="retail",
    )
    assert micro.short_finding == "Store 1 and Store 2 exceed target quota."
    assert len(micro.short_finding.split()) <= 12


def test_t2_04_environmental_pm10_leader_consistency():
    """Verify that environmental PM10 ranking and podium topics agree on Delhi as #1 peak at 210 µg/m³."""
    res = run_adaptive_dashboard(sheet_id=None, dataset_id=99772, include_dataset_intelligence=True)
    topics = res.executive_topics

    def _get(obj, key, default=None):
        if isinstance(obj, dict):
            return obj.get(key, default)
        return getattr(obj, key, default)

    ranking_topic = next((t for t in topics if "PM10 Particulate Concentration Ranking" in (_get(t, "technical_title", "") or _get(t, "title", ""))), None)
    podium_topic = next((t for t in topics if "PM10 Non-Attainment Urban Hotspots" in (_get(t, "technical_title", "") or _get(t, "title", "")) or "Top 3" in (_get(t, "technical_title", "") or _get(t, "title", ""))), None)

    assert ranking_topic is not None, "PM10 ranking topic not found in environmental dashboard"
    assert podium_topic is not None, "PM10 podium topic not found in environmental dashboard"

    ranking_vspec = _get(ranking_topic, "visual_spec", {})
    podium_vspec = _get(podium_topic, "visual_spec", {})
    ranking_micro = _get(ranking_topic, "visual_microcopy", {})

    # Both must identify Delhi as the leader
    assert _get(ranking_vspec, "categories")[0] == "Delhi"
    assert _get(ranking_vspec, "values")[0] == 210.0
    primary_num = _get(ranking_micro, "primary_number", "") or _get(ranking_topic, "key_metric", "")
    assert "210" in primary_num
    assert "Delhi" in _get(ranking_topic, "primary_takeaway", "")
    assert "Delhi" in _get(ranking_micro, "short_finding", "")

    assert _get(podium_vspec, "categories")[0] == "Delhi"
    assert _get(podium_vspec, "values")[0] == 210.0
    assert "Delhi" in _get(podium_topic, "primary_takeaway", "")

    # Neither should claim Brynihat or Jharia is peak or #1
    assert not _get(ranking_topic, "primary_takeaway", "").startswith("Brynihat and Jharia record peak")


def test_t2_04_synthetic_ranking_dataset_a_differing_order():
    """Verify that synthetic dataset A (A=12, B=31, C=20) ranks once with B=31 as leader across visual and narrative."""
    from app.services.adaptive_dashboard.story_builder import AnalyticalStoryBuilder
    from app.services.adaptive_dashboard.composition_planner import ExecutiveCompositionPlanner
    from app.services.adaptive_dashboard.evidence.contracts import EvidenceGraph

    # Synthetic Dataset A: Categories with values A=12, B=31, C=20
    gov_metrics = {
        "dataset_id": 99901,
        "hero": {
            "categories": ["Store A", "Store B", "Store C"],
            "values": [12.0, 31.0, 20.0],
            "measure_column": "Weekly Sales",
            "unit": "USD",
            "benchmark": 15.0,
        },
    }

    stories = AnalyticalStoryBuilder.build_stories(
        evidence_graph=EvidenceGraph(sheet_id=1, snapshot="snap_syn_a", nodes=[]),
        domain="environmental_air",
        dataset_name="Synthetic Dataset A",
        gov_metrics=gov_metrics,
    )

    ranking_story = next((s for s in stories if s.intent == "RANKING" and s.tokens.get("chart_archetype") == "ranked_bar"), None)
    assert ranking_story is not None, "Ranking story was not generated"

    # Analytical layer ranks once: Store B (31) must be first
    assert ranking_story.tokens["categories"][0] == "Store B"
    assert ranking_story.tokens["values"][0] == 31.0
    assert ranking_story.tokens["leader_entity"] == "Store B"
    assert ranking_story.tokens["leader_value"] == 31.0
    assert "Store B leads" in ranking_story.takeaway

    topics = ExecutiveCompositionPlanner.plan_from_stories(
        stories=stories,
        dataset_name="Synthetic Dataset A",
        dataset_id=99901,
        gov_metrics=gov_metrics,
    )
    ranking_topic = next((t for t in topics if t.analytical_intent == "RANKING"), None)
    assert ranking_topic is not None, "Ranking topic not planned"

    v_spec = ranking_topic.visual_spec
    micro = ranking_topic.visual_microcopy

    # Identity-level parity: visual rank #1 == narrative leader == primary number == bound fact
    assert v_spec["categories"][0] == "Store B"
    assert v_spec["values"][0] == 31.0
    assert v_spec["leader_entity"] == "Store B"
    assert "Store B" in ranking_topic.primary_takeaway
    assert "Store B" in micro.short_finding
    assert "31" in (micro.primary_number or ranking_topic.key_metric)
    assert v_spec["fact_id"] == ranking_topic.inspect_payload.get("fact_id")


def test_t2_04_synthetic_ranking_dataset_b_differing_order():
    """Verify that synthetic dataset B (A=52, B=10, C=44) ranks once with A=52 as leader across visual and narrative."""
    from app.services.adaptive_dashboard.story_builder import AnalyticalStoryBuilder
    from app.services.adaptive_dashboard.composition_planner import ExecutiveCompositionPlanner
    from app.services.adaptive_dashboard.evidence.contracts import EvidenceGraph

    # Synthetic Dataset B: Categories with values A=52, B=10, C=44
    gov_metrics = {
        "dataset_id": 99902,
        "hero": {
            "categories": ["Location A", "Location B", "Location C"],
            "values": [52.0, 10.0, 44.0],
            "measure_column": "PM10",
            "unit": "µg/m³",
            "benchmark": 25.0,
        },
    }

    stories = AnalyticalStoryBuilder.build_stories(
        evidence_graph=EvidenceGraph(sheet_id=1, snapshot="snap_syn_b", nodes=[]),
        domain="environmental_air",
        dataset_name="Synthetic Dataset B",
        gov_metrics=gov_metrics,
    )

    ranking_story = next((s for s in stories if s.intent == "RANKING" and s.tokens.get("chart_archetype") == "ranked_bar"), None)
    assert ranking_story is not None, "Ranking story was not generated"

    # Analytical layer ranks once: Location A (52) must be first
    assert ranking_story.tokens["categories"][0] == "Location A"
    assert ranking_story.tokens["values"][0] == 52.0
    assert ranking_story.tokens["leader_entity"] == "Location A"
    assert ranking_story.tokens["leader_value"] == 52.0
    assert "Location A leads" in ranking_story.takeaway

    topics = ExecutiveCompositionPlanner.plan_from_stories(
        stories=stories,
        dataset_name="Synthetic Dataset B",
        dataset_id=99902,
        gov_metrics=gov_metrics,
    )
    ranking_topic = next((t for t in topics if t.analytical_intent == "RANKING"), None)
    assert ranking_topic is not None, "Ranking topic not planned"

    v_spec = ranking_topic.visual_spec
    micro = ranking_topic.visual_microcopy

    # Identity-level parity: visual rank #1 == narrative leader == primary number == bound fact
    assert v_spec["categories"][0] == "Location A"
    assert v_spec["values"][0] == 52.0
    assert v_spec["leader_entity"] == "Location A"
    assert "Location A" in ranking_topic.primary_takeaway
    assert "Location A" in micro.short_finding
    assert "52" in (micro.primary_number or ranking_topic.key_metric)
    assert v_spec["fact_id"] == ranking_topic.inspect_payload.get("fact_id")


def test_t2_04_ranking_leader_mismatch_fails_closed():
    """Verify that a topic with contradictory visual and narrative leaders is suppressed (fails closed)."""
    from app.services.adaptive_dashboard.dataset_isolation_integrity import TopicVisualBindingIntegrity
    from app.services.adaptive_dashboard.topics.contracts import ExecutiveTopicDraft
    from app.services.adaptive_dashboard.topics.factory import ExecutiveTopicFactory
    from app.services.adaptive_dashboard.semantic_visual_compression import VisualMicrocopy

    # Craft an invalid topic: Visual says leader is Store B, but narrative claims Store A records peak
    draft = ExecutiveTopicDraft(
        topic_id="TOPIC-SYN-FAIL-01",
        semantic_topic_key="syn_retail_ranking",
        display_order=1,
        rank=1,
        portfolio_position=1,
        dataset_id=99903,
        domain="commercial_retail",
        analytical_intent="RANKING",
        slot_type="hero",
        priority=1,
        priority_score=0.95,
        confidence=0.90,
        primary_takeaway="Store A records peak sales velocity at $50/wk.",
        takeaway="Store A records peak sales velocity at $50/wk.",
        recommended_action="Review store allocation.",
        key_metric="Top: Store A ($50/wk)",
        tokens={
            "recommended_visual": "ranked_bar",
            "fact_id": "FACT-RANK-001",
        },
        visual_microcopy=VisualMicrocopy(
            icon="bar-chart-2",
            short_title="Store Sales Ranking",
            primary_number="$50/wk",
            short_context="Top: Store A",
            short_finding="Store A records peak sales.",
            cta="View ranking",
        ),
    )
    topic = ExecutiveTopicFactory.create_topic(draft)

    # Visual spec contradicts narrative by having Store B as rank #1
    contradictory_vspec = {
        "chart_type": "ranked_bar",
        "categories": ["Store B", "Store A", "Store C"],
        "values": [65.0, 50.0, 20.0],
        "leader_entity": "Store B",
        "leader_value": 65.0,
        "is_ranking_story": True,
        "topic_id": "TOPIC-SYN-FAIL-01",
        "dataset_id": 99903,
        "domain": "commercial_retail",
        "fact_id": "FACT-RANK-001",
    }
    ExecutiveTopicFactory.bind_visual_spec(topic, contradictory_vspec)

    ok, reason = TopicVisualBindingIntegrity.evaluate(topic)
    assert not ok, "Contradictory ranking topic should have failed closed"
    assert "RANKING_LEADER_MISMATCH" in reason
    assert "Store B" in reason
    assert "Store A" in reason


def test_t2_04_ranking_fact_id_mismatch_fails_closed():
    """Verify that a topic with discordant fact identities between visual and narrative fails closed."""
    from app.services.adaptive_dashboard.dataset_isolation_integrity import TopicVisualBindingIntegrity
    from app.services.adaptive_dashboard.topics.contracts import ExecutiveTopicDraft
    from app.services.adaptive_dashboard.topics.factory import ExecutiveTopicFactory

    draft = ExecutiveTopicDraft(
        topic_id="TOPIC-SYN-FAIL-02",
        semantic_topic_key="syn_env_ranking",
        display_order=1,
        rank=1,
        portfolio_position=1,
        dataset_id=99904,
        domain="environmental_air",
        analytical_intent="RANKING",
        slot_type="hero",
        priority=1,
        priority_score=0.95,
        confidence=0.90,
        primary_takeaway="Delhi leads particulate severity with 210 µg/m³ PM10.",
        takeaway="Delhi leads particulate severity with 210 µg/m³ PM10.",
        key_metric="210 µg/m³ peak",
        tokens={
            "fact_id": "FACT-RANK-PM10-DELHI-001",
        },
    )
    topic = ExecutiveTopicFactory.create_topic(draft)

    vspec = {
        "chart_type": "ranked_bar",
        "categories": ["Delhi", "Brynihat", "Jharia"],
        "values": [210.0, 195.0, 140.0],
        "leader_entity": "Delhi",
        "leader_value": 210.0,
        "is_ranking_story": True,
        "topic_id": "TOPIC-SYN-FAIL-02",
        "dataset_id": 99904,
        "domain": "environmental_air",
        "fact_id": "FACT-RANK-PM10-MUMBAI-999",  # Discordant fact_id
    }
    ExecutiveTopicFactory.bind_visual_spec(topic, vspec)

    ok, reason = TopicVisualBindingIntegrity.evaluate(topic)
    assert not ok, "Discordant fact_id topic should have failed closed"
    assert "RANKING_FACT_ID_MISMATCH" in reason


def test_t2_04_cache_invalidation_version_policy():
    """Verify that cache key generation embeds bumped engine versions and naturally invalidates stale cache."""
    from app.cache.contracts import (
        DashboardCacheKey,
        COMPOSITION_ENGINE_VERSION,
        ANALYTICS_ENGINE_VERSION,
    )
    from app.services.adaptive_dashboard.engine import ENGINE_VERSION

    # Verify bumped versions
    assert COMPOSITION_ENGINE_VERSION >= "2026.10.3"
    assert ENGINE_VERSION >= "5.7.1"

    key_v1 = DashboardCacheKey(
        dataset_id=99772,
        dataset_version=1,
        dataset_content_hash="hash_abc",
        semantic_schema_version="7",
        context_version="2.4.0",
        policy_version="1.2.0",
        analytics_engine_version=ANALYTICS_ENGINE_VERSION,
        composition_engine_version="2026.10.2",  # Old version
        filter_hash="none",
        tenant_id="default",
        cache_type="dashboard",
    )

    key_v2 = DashboardCacheKey(
        dataset_id=99772,
        dataset_version=1,
        dataset_content_hash="hash_abc",
        semantic_schema_version="7",
        context_version="2.4.0",
        policy_version="1.2.0",
        analytics_engine_version=ANALYTICS_ENGINE_VERSION,
        composition_engine_version=COMPOSITION_ENGINE_VERSION,  # Current bumped version
        filter_hash="none",
        tenant_id="default",
        cache_type="dashboard",
    )

    # Cache keys must strictly differ, guaranteeing automatic invalidation without manual SQL DELETE
    assert key_v1.compute_key() != key_v2.compute_key()

