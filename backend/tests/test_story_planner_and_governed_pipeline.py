import json
import pytest

from app.db.database import get_connection
from app.services.adaptive_dashboard.contracts import UnifiedFinding
from app.services.adaptive_dashboard.evidence_graph import findings_to_evidence_graph
from app.services.adaptive_dashboard.insight_ranker import InsightRankingEngine
from app.services.adaptive_dashboard.story_planner import GroundedClaim, StoryPlan, StoryPlanner


@pytest.fixture
def seeded_attendance_sheet():
    """Seeds a wide attendance sheet (100 individuals, 10 dates) into the isolated test DB."""
    conn = get_connection()
    conn.execute(
        "INSERT INTO dataset_uploads (id, filename, original_name, display_name, file_type) VALUES (?, ?, ?, ?, ?)",
        (1, "attendance.csv", "Employee Attendance Logs.csv", "Daily Attendance Logs", "csv"),
    )
    cols = ["Date"] + [f"Person_{i}" for i in range(100)]
    conn.execute(
        "INSERT INTO sheets (id, dataset_id, name, display_name, columns_json, profile_json, row_count) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (1, 1, "Sheet1", "Daily Attendance Logs", json.dumps(cols), "[]", 10),
    )
    for row_idx in range(10):
        row_data = {"Date": f"2024-01-{row_idx+1:02d}"}
        for i in range(100):
            row_data[f"Person_{i}"] = "08:45-16:45"
        conn.execute(
            "INSERT INTO sheet_rows (sheet_id, row_index, data_json) VALUES (?, ?, ?)",
            (1, row_idx, json.dumps(row_data)),
        )
    conn.commit()
    conn.close()
    return 1


def test_story_planner_generates_grounded_narrative():
    """Verify StoryPlanner binds narrative claims to EVID nodes with zero hallucinations."""
    findings = [
        UnifiedFinding(
            finding_id="f1",
            recipe_id="recipe_s09_segment_disparity",
            calculation_id="calc_s09_01",
            definition_id="def_s09",
            source_sheet_ids=[42],
            source_scope=["Executive Summary"],
            snapshot="snap_42",
            status="available",
            short_business_title="Operations & Logistics",
            typed_value=17.23,
            formatted_value="17.23 days",
            unit="days",
            population_or_exposure="26 employees",
            comparison_and_effect="+42.4% vs company baseline",
            evidence_bound_observation="Operations led office presence at 17.23 days.",
            one_next_check_or_action="Review facility access logs.",
            allowed_claim_level="descriptive_fact",
            analytical_subject="workforce",
            decision_category="segment_disparity",
            rank_score=98.0,
        ),
        UnifiedFinding(
            finding_id="f2",
            recipe_id="recipe_s14_capacity_demand",
            calculation_id="calc_s14_01",
            definition_id="def_s14",
            source_sheet_ids=[42],
            source_scope=["Executive Summary"],
            snapshot="snap_42",
            status="available",
            short_business_title="Customer Service Overtime Deficit",
            typed_value=320.0,
            formatted_value="320 hours",
            unit="hours",
            population_or_exposure="45 employees",
            comparison_and_effect="+18.5% over capacity envelope",
            evidence_bound_observation="Staffing capacity fell short of incoming surge.",
            one_next_check_or_action="Authorize temporary contractor allocation.",
            allowed_claim_level="policy_exposure",
            analytical_subject="operations",
            decision_category="capacity_gap",
            rank_score=94.0,
        ),
    ]

    graph = findings_to_evidence_graph(findings, sheet_id=42, snapshot="snap_42")
    ranker = InsightRankingEngine()
    ranked = ranker.rank_graph(graph, top_n=5)

    story = StoryPlanner.plan_story(graph, ranked, domain="workforce_hr")

    assert story.hero_evidence_id in ("EVID-001", "EVID-002")
    assert len(story.claims) >= 1
    assert story.visual_intent is not None

    # Check causal classification and token hydration on hero claim
    hero_claim = story.claims[0]
    assert hero_claim.evidence_ids[0] == story.hero_evidence_id
    assert hero_claim.causal_type in ("OBSERVED", "HYPOTHESIS")
    assert "{" not in hero_claim.rendered_text  # All placeholders must be hydrated
    assert "}" not in hero_claim.rendered_text
    assert hero_claim.strategic_implication is not None
    assert hero_claim.recommended_action is not None


def test_story_planner_handles_empty_graph():
    """Verify graceful fallback for empty evidence graph."""
    from app.services.adaptive_dashboard.evidence_graph import EvidenceGraph

    empty_graph = EvidenceGraph(sheet_id=99, snapshot="snap_empty", nodes=[])
    story = StoryPlanner.plan_story(empty_graph, [], domain="general_tabular")

    assert story.narrative_angle == "Operational Baseline Overview"
    assert story.hero_evidence_id == "none"
    assert len(story.claims) == 0


def test_live_engine_governed_pipeline_integration(seeded_attendance_sheet):
    """Verify that run_adaptive_dashboard automatically populates semantic catalog, evidence graph (EVID-xxx), and story plan."""
    from app.services.adaptive_dashboard.engine import run_adaptive_dashboard

    res = run_adaptive_dashboard(sheet_id=seeded_attendance_sheet)
    assert res.run_status == "ready"

    # 1. Semantic Catalog
    assert res.semantic_catalog is not None
    assert res.semantic_catalog["sheet_id"] == seeded_attendance_sheet
    assert "metrics" in res.semantic_catalog
    assert "dimensions" in res.semantic_catalog

    # 2. Governed Evidence Graph
    assert res.evidence_graph is not None
    assert "nodes" in res.evidence_graph
    nodes = res.evidence_graph["nodes"]
    assert len(nodes) > 0
    for node in nodes:
        assert node["evidence_id"].startswith("EVID-")
        assert node["causal_classification"] in ("OBSERVED", "ASSOCIATED", "INFERRED", "HYPOTHESIS")
        assert "provenance" in node
        assert "calculation" in node

    # 3. AI Story Plan
    assert res.story_plan is not None
    assert "narrative_angle" in res.story_plan
    assert "claims" in res.story_plan
    claims = res.story_plan["claims"]
    assert len(claims) > 0
    for claim in claims:
        assert claim["claim_id"].startswith("CLM-")
        assert len(claim["evidence_ids"]) > 0
        assert claim["evidence_ids"][0].startswith("EVID-")
        assert "{" not in claim["rendered_text"]
        assert "}" not in claim["rendered_text"]
