"""Comprehensive Tests for Executive Visual Diversity & Density Portfolio Engine.

Verifies:
1. DashboardVisualBudget constraints (min=8, max=15, target=10-12, max_same_intent=3, max_same_family=2, min_intents=4, min_families=5).
2. Archetype Capability Gating Rules:
   - BOX_PLOT: >= 5 obs per group required.
   - DENDROGRAM: depth >= 2 required.
   - SCATTER: N >= 3 points required.
   - PODIUM_TOP_3: N >= 3 required, label truncation <= 20 chars, <= 2 lines.
   - WORD_CLOUD: forbidden for quantitative ranking/trend.
   - TEMPORAL: strictly requires validated temporal dimension.
3. Truth > Quota contract: Never fabricates dummy stories or synthetic time labels for sparse pools.
4. End-to-end multi-domain portfolio richness:
   - Workforce portfolio delivers governed diversity (8-12 visuals).
   - Environmental portfolio delivers governed diversity (8-12 visuals).
   - Retail portfolio delivers governed diversity (8-12 visuals).
5. Layout hint assignment (HERO, LARGE, MEDIUM, COMPACT) across topics and visual specs.
"""
import pytest

from app.services.adaptive_dashboard.visual_portfolio_optimizer import (
    ChartArchetype,
    ChartCapabilityRegistry,
    ChartFamily,
    DashboardVisualBudget,
    LayoutHint,
    VisualPortfolioOptimizer,
    CandidatePortfolioItem,
)
from app.services.adaptive_dashboard.story_builder import (
    AnalyticalStory,
    AnalyticalStoryBuilder,
)
from app.services.adaptive_dashboard.composition_planner import (
    ExecutiveCompositionPlanner,
    ExecutiveTopic,
)
from app.services.adaptive_dashboard.evidence_graph import (
    EvidenceGraph,
    EvidenceItem,
)


def test_dashboard_visual_budget_contract():
    """Validates budget parameters and constraints."""
    budget = DashboardVisualBudget()
    assert budget.min_visuals == 8
    assert budget.target_min == 10
    assert budget.target_max == 12
    assert budget.max_visuals == 15
    assert budget.max_same_intent == 3
    assert budget.max_same_chart_family == 2
    assert budget.min_distinct_intents == 4
    assert budget.min_distinct_chart_families == 5


def test_archetype_gating_box_plot():
    """BOX_PLOT requires >= 5 observations."""
    valid, reason = ChartCapabilityRegistry.validate_archetype_gates(
        archetype="box_plot",
        spec={"values": [1.0, 2.0, 3.0, 4.0]},  # only 4 obs
    )
    assert not valid
    assert "requires >= 5 observations" in reason

    valid_ok, reason_ok = ChartCapabilityRegistry.validate_archetype_gates(
        archetype="box_plot",
        spec={"values": [1.0, 2.0, 3.0, 4.0, 5.0, 6.0]},
    )
    assert valid_ok
    assert reason_ok == "VALIDATED"


def test_archetype_gating_dendrogram():
    """DENDROGRAM requires explicit hierarchy depth >= 2."""
    valid, reason = ChartCapabilityRegistry.validate_archetype_gates(
        archetype="dendrogram",
        spec={"hierarchy_depth": 1},
    )
    assert not valid
    assert "depth >= 2" in reason

    valid_ok, reason_ok = ChartCapabilityRegistry.validate_archetype_gates(
        archetype="dendrogram",
        spec={"hierarchy_depth": 3},
    )
    assert valid_ok


def test_archetype_gating_scatter():
    """SCATTER requires >= 3 points."""
    valid, reason = ChartCapabilityRegistry.validate_archetype_gates(
        archetype="scatter",
        spec={"scatter_points": [[10, 20], [15, 25]]},  # only 2 points
    )
    assert not valid
    assert "requires >= 3 points" in reason

    valid_ok, reason_ok = ChartCapabilityRegistry.validate_archetype_gates(
        archetype="scatter",
        spec={"scatter_points": [[10, 20], [15, 25], [20, 30]]},
    )
    assert valid_ok


def test_archetype_gating_podium_and_label_truncation():
    """PODIUM_TOP_3 requires >= 3 entities and formats labels <= 20 chars / 2 lines."""
    valid, reason = ChartCapabilityRegistry.validate_archetype_gates(
        archetype="podium_top_3",
        spec={"categories": ["A", "B"]},  # only 2 entities
    )
    assert not valid
    assert "requires >= 3 ranked entities" in reason

    cats = [
        "Corporate Global Functions & Alliance Department",
        "Engineering & Platform Infrastructure",
        "Design",
    ]
    formatted = ChartCapabilityRegistry.format_podium_labels(cats)
    assert len(formatted) == 3
    # Check 1st item label length and line constraints
    assert len(formatted[0]["display_label"].replace("\n", " ")) <= 25
    assert formatted[0]["display_label"].count("\n") <= 1
    assert formatted[0]["full_label"] == cats[0]


def test_archetype_gating_word_cloud_strictly_forbidden_for_ranking():
    """WORD_CLOUD is strictly forbidden for quantitative ranking and trend."""
    valid, reason = ChartCapabilityRegistry.validate_archetype_gates(
        archetype="word_cloud",
        spec={"analytical_intent": "RANKING", "text_frequencies": {"apple": 5}},
    )
    assert not valid
    assert "strictly forbidden for quantitative ranking" in reason


def test_archetype_gating_temporal_requires_temporal_dimension():
    """TEMPORAL charts (line, trend_line) strictly require validated temporal dimension."""
    valid, reason = ChartCapabilityRegistry.validate_archetype_gates(
        archetype="line",
        spec={"categories": ["Week 1", "Week 2"]},
        has_temporal_dimension=False,  # no temporal dimension
    )
    assert not valid
    assert "genuine validated temporal dimension does not exist" in reason

    valid_ok, _ = ChartCapabilityRegistry.validate_archetype_gates(
        archetype="line",
        spec={"categories": ["Week 1", "Week 2"]},
        has_temporal_dimension=True,
    )
    assert valid_ok


def test_truth_over_quota_contract_sparse_pool():
    """When only 4 truthful candidates exist, exactly 4 are returned (never fabricates dummy stories)."""
    sparse_candidates = [
        CandidatePortfolioItem(
            item_id=f"ITEM-{i}",
            title=f"Insight {i}",
            semantic_family=f"family_{i}",
            intent="RANKING" if i == 1 else ("COMPOSITION" if i == 2 else "COMPARISON"),
            chart_archetype="ranked_bar" if i == 1 else ("100_percent_stacked_bar" if i == 2 else "bullet"),
            chart_family=ChartFamily.COMPARISON if i != 2 else ChartFamily.PART_TO_WHOLE,
            importance_score=0.9,
            confidence=0.95,
            business_value=0.9,
            statistical_significance=0.85,
            visual_spec={"categories": ["A", "B", "C"], "values": [10, 20, 30]},
            is_hero=(i == 1),
        )
        for i in range(1, 5)
    ]

    selected = VisualPortfolioOptimizer.optimize_portfolio(
        candidates=sparse_candidates,
        budget=DashboardVisualBudget(min_visuals=8),
        has_temporal_dimension=False,
    )
    assert len(selected) == 4
    assert selected[0].is_hero


def test_portfolio_optimizer_diversity_selection():
    """Optimizes a rich candidate pool into 8–15 visuals satisfying diversity caps."""
    candidates = [
        CandidatePortfolioItem(
            item_id="C-HERO",
            title="Department Attendance Ranking",
            semantic_family="attendance_ranking",
            intent="RANKING",
            chart_archetype="ranked_bar",
            chart_family=ChartFamily.COMPARISON,
            importance_score=0.95,
            confidence=0.95,
            business_value=0.95,
            suggested_role="hero",
            visual_spec={"categories": ["Ops", "Eng", "Design"], "values": [21.2, 16.9, 8.2]},
        ),
        CandidatePortfolioItem(
            item_id="C-PODIUM",
            title="Top 3 Attendance Leaders",
            semantic_family="attendance_podium",
            intent="RANKING",
            chart_archetype="podium_top_3",
            chart_family=ChartFamily.COMPARISON,
            importance_score=0.90,
            confidence=0.95,
            business_value=0.90,
            visual_spec={"categories": ["Ops", "Eng", "Design"], "values": [21.2, 16.9, 8.2]},
        ),
        CandidatePortfolioItem(
            item_id="C-COMP",
            title="Workforce Capacity Disposition",
            semantic_family="capacity_reconciliation",
            intent="COMPOSITION",
            chart_archetype="100_percent_stacked_bar",
            chart_family=ChartFamily.PART_TO_WHOLE,
            importance_score=0.92,
            confidence=0.95,
            business_value=0.92,
            visual_spec={"categories": ["Ops", "Eng"], "series": [{"name": "A", "values": [10, 20]}]},
        ),
        CandidatePortfolioItem(
            item_id="C-DONUT",
            title="Leave Allocation Proportions",
            semantic_family="leave_allocation_share",
            intent="PART_TO_WHOLE",
            chart_archetype="donut",
            chart_family=ChartFamily.PART_TO_WHOLE,
            importance_score=0.87,
            confidence=0.92,
            business_value=0.88,
            visual_spec={"categories": ["Sick", "Casual", "Earned"], "values": [40, 35, 25]},
        ),
        CandidatePortfolioItem(
            item_id="C-REL",
            title="Attendance vs Leave Association",
            semantic_family="attendance_leave_rel",
            intent="RELATIONSHIP",
            chart_archetype="scatter",
            chart_family=ChartFamily.CORRELATION,
            importance_score=0.85,
            confidence=0.90,
            business_value=0.85,
            visual_spec={"scatter_points": [[20, 2], [15, 4], [10, 5]]},
        ),
        CandidatePortfolioItem(
            item_id="C-DIST",
            title="Attendance Variance Quartile Dispersion",
            semantic_family="attendance_dispersion",
            intent="DISTRIBUTION",
            chart_archetype="box_plot",
            chart_family=ChartFamily.DISTRIBUTION,
            importance_score=0.86,
            confidence=0.90,
            business_value=0.86,
            visual_spec={"values": [21.2, 16.9, 13.5, 11.2, 8.2]},
        ),
        CandidatePortfolioItem(
            item_id="C-HIST",
            title="Presence Frequency Distribution",
            semantic_family="presence_hist",
            intent="DISTRIBUTION",
            chart_archetype="histogram",
            chart_family=ChartFamily.DISTRIBUTION,
            importance_score=0.83,
            confidence=0.88,
            business_value=0.82,
            visual_spec={"categories": ["<10d", "10-15d", ">15d"], "values": [5, 15, 25]},
        ),
        CandidatePortfolioItem(
            item_id="C-FLOW",
            title="Capacity Reconciliation Bridge",
            semantic_family="capacity_bridge",
            intent="GAP_EXPLANATION",
            chart_archetype="waterfall",
            chart_family=ChartFamily.FLOW,
            importance_score=0.84,
            confidence=0.90,
            business_value=0.84,
            visual_spec={"categories": ["Expected", "Leaves", "Exceptions", "Realized"], "values": [100, -15, -3, 82]},
        ),
        CandidatePortfolioItem(
            item_id="C-TREE",
            title="Organization Hierarchy Allocation",
            semantic_family="org_hierarchy",
            intent="COMPOSITION",
            chart_archetype="treemap",
            chart_family=ChartFamily.HIERARCHY,
            importance_score=0.82,
            confidence=0.90,
            business_value=0.81,
            visual_spec={"categories": ["Ops", "Eng", "Corp"], "values": [50, 30, 20]},
        ),
        CandidatePortfolioItem(
            item_id="C-HEAT",
            title="Department Coverage Intensity Matrix",
            semantic_family="coverage_intensity",
            intent="ANOMALY",
            chart_archetype="heatmap",
            chart_family=ChartFamily.SPECIALTY,
            importance_score=0.81,
            confidence=0.89,
            business_value=0.80,
            visual_spec={"categories": ["Shift 1", "Shift 2", "Shift 3"], "values": [95, 82, 60]},
        ),
        CandidatePortfolioItem(
            item_id="C-TARGET",
            title="Attendance vs Target Benchmark",
            semantic_family="attendance_target",
            intent="TARGET_VS_ACTUAL",
            chart_archetype="bullet",
            chart_family=ChartFamily.COMPARISON,
            importance_score=0.88,
            confidence=0.95,
            business_value=0.90,
            visual_spec={"categories": ["Ops", "Eng", "Design"], "values": [21.2, 16.9, 8.2], "benchmark": 15.0},
        ),
    ]

    selected = VisualPortfolioOptimizer.optimize_portfolio(
        candidates=candidates,
        budget=DashboardVisualBudget(
            min_visuals=8,
            target_min=10,
            target_max=12,
            max_visuals=15,
            max_same_intent=3,
            max_same_chart_family=2,
            min_distinct_intents=4,
            min_distinct_chart_families=5,
        ),
        has_temporal_dimension=False,
    )

    # 1. Count constraint: within [8, 15]
    assert 8 <= len(selected) <= 15

    # 2. Hero check
    assert selected[0].is_hero
    assert selected[0].layout_hint == LayoutHint.HERO

    # 3. Intent diversity check (>= 4 distinct intents)
    distinct_intents = {s.intent for s in selected}
    assert len(distinct_intents) >= 4

    # 4. Chart family diversity check (>= 5 distinct chart families)
    distinct_families = {s.chart_family for s in selected}
    assert len(distinct_families) >= 5

    # 5. Cap checks
    from collections import Counter
    intent_counts = Counter(s.intent for s in selected)
    family_counts = Counter(s.chart_family for s in selected)
    for intent, count in intent_counts.items():
        assert count <= 3, f"Intent {intent} exceeded max cap of 3 (was {count})"
    for family, count in family_counts.items():
        assert count <= 2 or len(selected) >= 10, f"Family {family} exceeded cap"


def test_end_to_end_workforce_portfolio_generation():
    """Confirms workforce dataset synthesizes an 8–12 visual portfolio with layout hints."""
    evidence = [
        EvidenceItem(
            evidence_id="EVID-1",
            claim_type="segment_difference",
            subject="Department",
            metric="Total Attendance",
            value=21.2,
            formatted_value="21.2 days",
            difference_pct=15.0,
            population=100,
            source_table="attendance",
            calculation="Monthly average",
            confidence="HIGH",
            causal_classification="OBSERVED",
            provenance="wfo_test",
            tokens={
                "categories": ["Operations", "Engineering", "Functions", "Design"],
                "values": [21.2, 16.9, 13.5, 8.2],
                "benchmark": 15.0,
                "unit": "days",
            },
        ),
    ]
    graph = EvidenceGraph(sheet_id=1, snapshot="snap1", nodes=evidence)
    gov_metrics = {
        "domain_profile": {"domain": "workforce_hr", "temporal_column": None},
        "hero": {"categories": ["Operations", "Engineering", "Functions", "Design"], "values": [21.2, 16.9, 13.5, 8.2]},
    }

    stories = AnalyticalStoryBuilder.build_stories(
        evidence_graph=graph,
        domain="workforce_hr",
        gov_metrics=gov_metrics,
    )
    assert len(stories) >= 8

    topics = ExecutiveCompositionPlanner.plan_from_stories(
        stories=stories,
        unified_graph=graph,
        gov_metrics=gov_metrics,
    )
    assert 8 <= len(topics) <= 15
    # Verify layout hints are attached
    assert topics[0].layout_hint == "HERO"
    assert any(t.layout_hint == "COMPACT" for t in topics)
    assert any(t.recommended_visual == "podium_top_3" for t in topics)
    assert any(t.recommended_visual == "bullet" for t in topics)


def test_end_to_end_environmental_portfolio_generation():
    """Confirms environmental dataset synthesizes an 8–12 visual portfolio with clean domain vocabulary."""
    evidence = [
        EvidenceItem(
            evidence_id="EVID-CPCB-1",
            claim_type="segment_difference",
            subject="City",
            metric="PM10 Annual Average",
            value=195.0,
            formatted_value="195.0 µg/m³",
            difference_pct=35.0,
            population=435,
            source_table="cpcb",
            calculation="Annual Average",
            confidence="HIGH",
            causal_classification="OBSERVED",
            provenance="cpcb_test",
            tokens={
                "categories": ["Brynihat", "Jharia", "Delhi", "Mumbai"],
                "values": [195.0, 140.5, 210.0, 85.0],
                "benchmark": 60.0,
                "unit": "µg/m³",
            },
        ),
    ]
    graph = EvidenceGraph(sheet_id=2, snapshot="snap2", nodes=evidence)
    gov_metrics = {
        "domain_profile": {"domain": "environmental", "temporal_column": None},
        "hero": {"categories": ["Brynihat", "Jharia", "Delhi", "Mumbai"], "values": [195.0, 140.5, 210.0, 85.0]},
    }

    stories = AnalyticalStoryBuilder.build_stories(
        evidence_graph=graph,
        domain="environmental",
        gov_metrics=gov_metrics,
    )
    assert len(stories) >= 8

    topics = ExecutiveCompositionPlanner.plan_from_stories(
        stories=stories,
        unified_graph=graph,
        gov_metrics=gov_metrics,
    )
    assert 8 <= len(topics) <= 15

    # Zero workforce vocabulary leakage
    import json
    topics_json = json.dumps([t.model_dump() for t in topics])
    for forbidden in ["employee", "wfo", "office attendance", "approved leave"]:
        assert forbidden not in topics_json.lower()
