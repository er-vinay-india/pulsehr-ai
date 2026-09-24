"""Comprehensive benchmarks and unit tests for the layered local AI architecture:
- Pluggable DecisionEngine (Rules & Embeddings)
- ModelRouter & ModelManager (task routing & confidence escalation)
- InsightRegistry (stable FACT-XXX provenance tracking & brief caching)
- Deterministic visual selection & LLM call elimination
"""

import time
import pytest
from unittest.mock import patch, MagicMock

from app.core.models_config import ModelRole, get_role_config
from app.services.decision_engine.base import DecisionResult
from app.services.decision_engine.rule_engine import RuleDecisionEngine
from app.services.decision_engine.embedding_engine import EmbeddingDecisionEngine, cosine_similarity
from app.services.decision_engine.factory import get_decision_engine
from app.services.gateway.model_router import ModelRouter
from app.services.gateway.model_manager import model_manager
from app.services.insight_registry import insight_registry
from app.routers.decision_brief import assign_deterministic_visuals


def test_rule_decision_engine_classification():
    """Verifies that RuleDecisionEngine instantly (<1ms) classifies contextual business queries."""
    engine = RuleDecisionEngine()

    t0 = time.perf_counter()
    res1 = engine.classify("give me 3 good points from this report")
    elapsed_ms = (time.perf_counter() - t0) * 1000

    assert elapsed_ms < 5.0, f"Classification took {elapsed_ms}ms, expected < 5ms"
    assert res1.intent == "summary_positives"
    assert res1.confidence >= 0.90
    assert res1.extracted_entities.get("count") == 3
    assert res1.reasoning_required is False
    assert res1.suggested_role is None  # Pure deterministic

    # Test main concerns
    res2 = engine.classify("what are the main problems facing our teams?")
    assert res2.intent == "summary_concerns"
    assert res2.confidence >= 0.90
    assert res2.reasoning_required is False

    # Test actions
    res3 = engine.classify("what should we do next?")
    assert res3.intent == "summary_actions"
    assert res3.confidence >= 0.90

    # Test ranking queries
    res4 = engine.classify("which department is worst?")
    assert res4.intent == "ranking_lowest"
    assert res4.confidence >= 0.90

    # Test correlation queries (requires reasoning)
    res5 = engine.classify("does overtime cause employee attrition?")
    assert res5.intent == "correlation"
    assert res5.confidence >= 0.85
    assert res5.reasoning_required is True
    assert res5.suggested_role == "ANALYST"

    # Test metadata queries
    res6 = engine.classify("list columns and available sheets")
    assert res6.intent == "metadata_lookup"
    assert res6.suggested_role == "FAST"


def test_embedding_decision_engine_fallback():
    """Verifies that EmbeddingDecisionEngine falls back to RuleDecisionEngine when Ollama is offline."""
    engine = EmbeddingDecisionEngine(embedding_model="nomic-embed-text:latest")
    
    with patch("httpx.Client.post", side_effect=Exception("Ollama offline")):
        res = engine.classify("give me 3 good points")
        assert res.intent == "summary_positives"
        assert res.metadata.get("vector_fallback_used") is True


def test_embedding_decision_engine_similarity():
    """Verifies cosine similarity computation and mock vector classification."""
    v1 = [1.0, 0.0, 0.0]
    v2 = [1.0, 0.0, 0.0]
    v3 = [0.0, 1.0, 0.0]
    assert cosine_similarity(v1, v2) == 1.0
    assert cosine_similarity(v1, v3) == 0.0

    engine = EmbeddingDecisionEngine()
    # Mock embedding response
    with patch.object(engine, "_get_embedding") as mock_emb:
        # Return identical mock vector for query and prototype
        mock_emb.return_value = [0.5, 0.5, 0.5]
        res = engine.classify("what are the main problems and risks?")
        assert res.confidence >= 0.70
        assert res.engine_name == "embedding_engine"


def test_decision_engine_factory():
    """Verifies factory switches correctly between rules and embedding engines."""
    engine_rules = get_decision_engine("rules")
    assert isinstance(engine_rules, RuleDecisionEngine)

    engine_embed = get_decision_engine("embedding")
    assert isinstance(engine_embed, EmbeddingDecisionEngine)


def test_model_router_task_dispatch():
    """Verifies ModelRouter assigns appropriate ModelRoles according to workload."""
    # Fast Edge tasks
    assert ModelRouter.route_task("sheet_naming") == ModelRole.FAST
    assert ModelRouter.route_task("metadata") == ModelRole.FAST
    assert ModelRouter.route_task("quick") == ModelRole.FAST

    # Writer tasks
    assert ModelRouter.route_task("presentation") == ModelRole.WRITER
    assert ModelRouter.route_task("narrative") == ModelRole.WRITER

    # Reasoner tasks
    assert ModelRouter.route_task("root_cause") == ModelRole.REASONER
    assert ModelRouter.route_task("deep_reasoning") == ModelRole.REASONER

    # Analyst tasks
    assert ModelRouter.route_task("analysis") == ModelRole.ANALYST
    assert ModelRouter.route_task("ranking") == ModelRole.ANALYST

    # Latency priority override
    assert ModelRouter.route_task("narrative", latency_priority=True) == ModelRole.FAST
    assert ModelRouter.route_task("analysis", latency_priority=True) == ModelRole.FAST


def test_model_router_confidence_escalation():
    """Verifies confidence-based escalation from FAST -> ANALYST -> REASONER."""
    # Low confidence on FAST escalates to ANALYST
    esc1 = ModelRouter.should_escalate(ModelRole.FAST, confidence=0.55, valid_schema=True)
    assert esc1 == ModelRole.ANALYST

    # Schema invalidation on FAST escalates to ANALYST
    esc2 = ModelRouter.should_escalate(ModelRole.FAST, confidence=0.90, valid_schema=False)
    assert esc2 == ModelRole.ANALYST

    # High confidence on FAST does not escalate
    esc3 = ModelRouter.should_escalate(ModelRole.FAST, confidence=0.85, valid_schema=True)
    assert esc3 is None

    # Very low confidence on ANALYST escalates to REASONER
    esc4 = ModelRouter.should_escalate(ModelRole.ANALYST, confidence=0.40, valid_schema=True)
    assert esc4 == ModelRole.REASONER

    # Normal confidence on ANALYST does not escalate
    esc5 = ModelRouter.should_escalate(ModelRole.ANALYST, confidence=0.75, valid_schema=True)
    assert esc5 is None


def test_model_manager_stats():
    """Verifies model_manager records execution latency and calculates averages."""
    model_manager.record_execution("phi4-mini:latest", 240.0, success=True)
    model_manager.record_execution("phi4-mini:latest", 260.0, success=True)
    stats = model_manager.get_stats()

    assert "phi4-mini:latest" in stats
    assert stats["phi4-mini:latest"]["invocations"] >= 2
    assert 240.0 <= stats["phi4-mini:latest"]["avg_duration_ms"] <= 260.0


def test_insight_registry_fact_provenance():
    """Verifies cryptographic snapshot fact registration, stable FACT-XXX IDs, and retrieval."""
    test_snapshot = "snap-test-hash-1234"
    findings = [
        {
            "id": "item_1",
            "kind": "comparison",
            "title": "Engineering: Attendance is above baseline",
            "metric": "Attendance_Rate",
            "observation": "94.2% vs 88.0% baseline",
            "implication": "Leading department",
            "action": "Maintain practices",
            "detail": {"gap": 6.2},
            "priority_score": 2.1
        },
        {
            "id": "item_2",
            "kind": "movement",
            "title": "Weekly Sales changed in 2023-08",
            "metric": "Weekly_Sales",
            "observation": "$45,000 to $52,000",
            "implication": "Seasonal lift",
            "action": "Ensure inventory",
            "detail": {"change": 7000},
            "priority_score": 1.8
        }
    ]

    registered = insight_registry.register_findings(test_snapshot, findings)
    assert len(registered) == 2
    assert registered[0]["fact_id"] == "FACT-001"
    assert registered[1]["fact_id"] == "FACT-002"
    assert registered[0]["snapshot_id"] == test_snapshot

    # Retrieve single fact
    fact1 = insight_registry.get_fact(test_snapshot, "FACT-001")
    assert fact1 is not None
    assert fact1["metric"] == "Attendance_Rate"
    assert fact1["kind"] == "comparison"

    # Verify fact reference
    assert insight_registry.verify_fact_reference(test_snapshot, "FACT-001") is True
    assert insight_registry.verify_fact_reference(test_snapshot, "FACT-999") is False

    # Brief caching
    insight_registry.set_cached_brief("test_cache_key", {"status": "ok", "snapshot": test_snapshot})
    assert insight_registry.get_cached_brief("test_cache_key") == {"status": "ok", "snapshot": test_snapshot}
    insight_registry.invalidate_cache()
    assert insight_registry.get_cached_brief("test_cache_key") is None


def test_deterministic_visual_assignment_latency():
    """Verifies that assign_deterministic_visuals assigns charts and icons in <5ms without LLM."""
    findings = [
        {"id": f"f_{i}", "kind": "movement", "title": f"Sales grew in Month {i}", "metric": "Sales", "observation": "up"}
        for i in range(50)
    ] + [
        {"id": f"f_c_{i}", "kind": "comparison", "title": f"Store {i} Attendance is below baseline", "metric": "Attendance", "observation": "down"}
        for i in range(50)
    ]

    t0 = time.perf_counter()
    processed = assign_deterministic_visuals(findings)
    elapsed_ms = (time.perf_counter() - t0) * 1000

    assert elapsed_ms < 5.0, f"Visual assignment took {elapsed_ms}ms, expected < 5ms"
    assert len(processed) == 100
    assert processed[0]["recommended_chart"] == "area_trend"
    assert processed[0]["icon"] in ("trending-up", "dollar-sign")
    assert processed[50]["recommended_chart"] == "comparison_bar"
    assert processed[50]["icon"] in ("alert-triangle", "users")


def test_deterministic_report_planner_latency_and_schema():
    """Verifies that ReportPlanner.plan executes deterministically in <5ms without LLMs."""
    from app.services.data_engine.profiler import DatasetProfile
    from app.services.evidence.evidence_store import EvidenceStore
    from app.services.evidence.evidence_models import Finding, FindingType, Importance
    from app.services.reporting.report_planner import ReportPlanner, ReportPlan

    store = EvidenceStore()
    store.add_finding(Finding(
        finding_id="F-001",
        type=FindingType.OUTPERFORMER,
        metric="Revenue",
        segment="North",
        segment_value=120000.0,
        overall_value=100000.0,
        difference=20000.0,
        difference_percentage_points=20.0,
        importance=Importance.HIGH,
        headline="North segment outperforms baseline by 20%",
        business_implication="Share regional best practices"
    ))
    store.add_finding(Finding(
        finding_id="F-002",
        type=FindingType.HEADWIND,
        metric="Revenue",
        segment="South",
        segment_value=75000.0,
        overall_value=100000.0,
        difference=-25000.0,
        difference_percentage_points=-25.0,
        importance=Importance.HIGH,
        headline="South segment trails baseline by 25%",
        business_implication="Urgent pricing and sales review needed"
    ))
    store.add_finding(Finding(
        finding_id="F-003",
        type=FindingType.TREND_SHIFT,
        metric="Revenue",
        difference=5000.0,
        importance=Importance.MEDIUM,
        headline="Revenue momentum shifted upward in Q3",
        business_implication="Positive trajectory"
    ))

    profile = DatasetProfile(
        dataset_name="Regional Revenue Logs",
        business_domain="Sales & Commercial",
        row_count=1500,
        column_count=8
    )

    t0 = time.perf_counter()
    plan = ReportPlanner.plan(store, profile, objective="Q3 Strategic Review")
    elapsed_ms = (time.perf_counter() - t0) * 1000

    assert elapsed_ms < 5.0, f"Deterministic planning took {elapsed_ms}ms, expected < 5ms"
    assert isinstance(plan, ReportPlan)
    assert plan.report_title == "Executive Review: Regional Revenue Logs"
    assert plan.objective == "Q3 Strategic Review"
    assert plan.executive_summary_finding_ids == ["F-001", "F-002"]
    assert len(plan.sections) >= 3

    categories = [s.category for s in plan.sections]
    assert "EXECUTIVE" in categories
    assert "STRENGTHS" in categories
    assert "HEADWINDS" in categories
    assert "RECOMMENDATIONS" in categories

    # Verify 100% valid finding IDs
    valid_ids = {"F-001", "F-002", "F-003"}
    for sec in plan.sections:
        assert all(fid in valid_ids for fid in sec.finding_ids)
        assert len(sec.finding_ids) >= 1

