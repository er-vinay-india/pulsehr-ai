"""Unit tests for Governed Semantic Catalog, Evidence Graph, and Insight Ranker."""
from __future__ import annotations

import pytest

from app.services.adaptive_dashboard.contracts import UnifiedFinding
from app.services.adaptive_dashboard.evidence_graph import (
    EvidenceGraph,
    EvidenceItem,
    findings_to_evidence_graph,
)
from app.services.adaptive_dashboard.insight_ranker import (
    InsightRankingEngine,
    RankedInsight,
)
from app.services.adaptive_dashboard.semantic_catalog import (
    BusinessPolicy,
    PolicyThreshold,
    SemanticCatalog,
    SemanticDimension,
    SemanticMetric,
    infer_semantic_catalog,
)


def test_infer_semantic_catalog_workforce():
    """Verify semantic catalog correctly infers metrics, directions, dimensions and time grains."""
    columns = ["employee_id", "department", "attendance_days", "attrition_rate", "salary_usd", "recorded_month"]
    dtypes = {
        "employee_id": "string",
        "department": "string",
        "attendance_days": "float",
        "attrition_rate": "float",
        "salary_usd": "float",
        "recorded_month": "string",
    }

    catalog = infer_semantic_catalog(
        sheet_id=101,
        sheet_name="Workforce Monthly Attendance",
        columns=columns,
        dtypes=dtypes,
    )

    assert catalog.sheet_id == 101
    assert catalog.primary_key == "employee_id"
    assert catalog.time_column == "recorded_month"
    assert catalog.time_grain == "monthly"

    # Verify metrics
    att_metric = catalog.get_metric("attendance_days")
    assert att_metric is not None
    assert att_metric.unit == "days"
    assert att_metric.direction == "higher_is_better"

    attr_metric = catalog.get_metric("attrition_rate")
    assert attr_metric is not None
    assert attr_metric.unit == "%"
    assert attr_metric.direction == "lower_is_better"

    sal_metric = catalog.get_metric("salary_usd")
    assert sal_metric is not None
    assert sal_metric.unit == "$"

    # Verify dimensions
    dept_dim = catalog.get_dimension("department")
    assert dept_dim is not None
    assert dept_dim.data_type == "categorical"


def test_findings_to_evidence_graph_and_hydration():
    """Verify UnifiedFindings convert to governed EVID nodes and deterministic template hydration works."""
    findings = [
        UnifiedFinding(
            finding_id="f1",
            recipe_id="recipe_s09_segment_disparity",
            calculation_id="calc_01",
            definition_id="def_01",
            source_sheet_ids=[101],
            source_scope=["July Attendance"],
            snapshot="snap_abc123",
            status="available",
            short_business_title="Operations & Infrastructure",
            typed_value=17.23,
            formatted_value="17.23 days",
            unit="days",
            population_or_exposure="26 employees",
            comparison_and_effect="+42.4% vs company baseline",
            evidence_bound_observation="Operations averaged 17.23 days across 26 employees.",
            one_next_check_or_action="Review shift logs.",
            allowed_claim_level="descriptive_fact",
            analytical_subject="workforce",
            decision_category="segment_disparity",
            rank_score=95.0,
        ),
        UnifiedFinding(
            finding_id="f2",
            recipe_id="recipe_s01_scheduled_obligations",
            calculation_id="calc_02",
            definition_id="def_02",
            source_sheet_ids=[101],
            source_scope=["July Attendance"],
            snapshot="snap_abc123",
            status="available",
            short_business_title="Unexcused Absence Gap",
            typed_value=4.8,
            formatted_value="4.8%",
            unit="%",
            population_or_exposure="120 employees",
            comparison_and_effect="+1.2% vs target limit",
            evidence_bound_observation="Unexcused absence reached 4.8% of scheduled days.",
            one_next_check_or_action="Audit leave requests.",
            allowed_claim_level="policy_exposure",
            analytical_subject="workforce",
            decision_category="policy_gap",
            rank_score=90.0,
        ),
    ]

    graph = findings_to_evidence_graph(findings, sheet_id=101, snapshot="snap_abc123")
    assert len(graph.nodes) == 2

    node1 = graph.get_by_id("EVID-001")
    assert node1 is not None
    assert node1.evidence_id == "EVID-001"
    assert node1.subject == "Operations & Infrastructure"
    assert node1.value == 17.23
    assert node1.difference_pct == 42.4
    assert node1.population == 26
    assert node1.causal_classification == "OBSERVED"
    assert node1.claim_type == "segment_difference"

    node2 = graph.get_by_id("EVID-002")
    assert node2 is not None
    assert node2.causal_classification == "HYPOTHESIS"  # mapped from policy_exposure

    # Verify zero-hallucination hydration
    template = "{subject} recorded {value} {unit}, which is {difference_pct}% above baseline across {population}."
    hydrated = graph.hydrate_template(template, ["EVID-001"])
    assert "Operations & Infrastructure recorded 17.23 days" in hydrated
    assert "42.4% above baseline across 26" in hydrated


def test_insight_ranking_engine_prioritization():
    """Verify multi-factor scoring ranks high-impact, high-magnitude evidence first."""
    nodes = [
        EvidenceItem(
            evidence_id="EVID-001",
            claim_type="segment_difference",
            subject="Operations",
            metric="attendance",
            value=17.23,
            formatted_value="17.23 days",
            comparison_value=12.10,
            difference_pct=42.4,
            population=26,
            source_table="curated_rows",
            calculation="SUM/COUNT",
            confidence="HIGH",
            causal_classification="OBSERVED",
            provenance="snap_1",
            limitations=[],
        ),
        EvidenceItem(
            evidence_id="EVID-002",
            claim_type="general_fact",
            subject="All Employees",
            metric="headcount",
            value=120,
            formatted_value="120",
            difference_pct=None,
            population=120,
            source_table="curated_rows",
            calculation="COUNT(*)",
            confidence="HIGH",
            causal_classification="OBSERVED",
            provenance="snap_1",
            limitations=[],
        ),
        EvidenceItem(
            evidence_id="EVID-003",
            claim_type="capacity_gap",
            subject="Customer Support",
            metric="overtime_deficit",
            value=350.0,
            formatted_value="350 hrs",
            comparison_value=50.0,
            difference_pct=600.0,
            population=40,
            source_table="curated_rows",
            calculation="GAP",
            confidence="HIGH",
            causal_classification="OBSERVED",
            provenance="snap_1",
            limitations=[],
        ),
    ]

    graph = EvidenceGraph(sheet_id=101, snapshot="snap_1", nodes=nodes)
    ranker = InsightRankingEngine()
    ranked = ranker.rank_graph(graph, top_n=5)

    assert len(ranked) == 3
    # Capacity gap with massive magnitude should rank #1 as hero
    assert ranked[0].evidence.evidence_id == "EVID-003"
    assert ranked[0].suggested_role == "hero"
    assert ranked[0].composite_score > ranked[1].composite_score

    # Segment difference should rank #2
    assert ranked[1].evidence.evidence_id == "EVID-001"
    assert ranked[1].suggested_role == "primary_comparator"

    # General headcount fact should rank #3
    assert ranked[2].evidence.evidence_id == "EVID-002"
    assert ranked[2].suggested_role == "supporting"
