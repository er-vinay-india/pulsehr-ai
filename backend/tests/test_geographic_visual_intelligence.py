"""Comprehensive Test Suite for HighView Geographic & Demographic Visual Intelligence.

Verifies:
1. Governed geographic eligibility: Only datasets with verified geographic dimensions recommend maps.
2. 0 maps generated without governed geo dimension.
3. 0 maps using unsafe cross-sheet relationship.
4. 0 ambiguous locations auto-plotted.
5. Grain-aware map selection:
   - Country grain -> World map / country choropleth
   - State/province grain -> State map / choropleth
   - City / lat-lon grain -> Point / bubble map
6. Metric-aware selection:
   - Normalized measure (rate, ratio, percentage, density) -> Choropleth
   - Absolute volume (headcount, revenue, count) -> Bubble map / ranked table
7. Low coverage (< 50% or < 3 locations) blocks or downgrades map.
8. Lineage preservation: OBSERVED vs DERIVED lineage.
9. Map + Ranked DataTable integration.
10. Exact P0 Database Invariant: size and SHA-256 unmutated.
"""
import hashlib
from pathlib import Path
import pytest

from app.services.adaptive_dashboard.visual_decision import (
    AnalyticalIntent,
    AudienceType,
    ChartType,
    VisualDecisionEngine,
    VisualQuestionBuilder,
    VisualSemanticValidator,
)
from app.services.adaptive_dashboard.visuals import (
    VisualCapabilityRegistry,
    ChartFamily,
    VisualMorphology,
)
from app.services.adaptive_dashboard.story_builder import AnalyticalStoryBuilder


def test_geographic_capability_registry():
    """Confirms map, choropleth, bubble_map, point_map are registered in GEOSPATIAL family."""
    assert VisualCapabilityRegistry.is_supported("map")
    assert VisualCapabilityRegistry.is_supported("choropleth")
    assert VisualCapabilityRegistry.is_supported("bubble_map")
    assert VisualCapabilityRegistry.is_supported("point_map")

    assert VisualCapabilityRegistry.get_family("choropleth") == ChartFamily.GEOSPATIAL
    assert VisualCapabilityRegistry.get_family("bubble_map") == ChartFamily.GEOSPATIAL
    assert VisualCapabilityRegistry.get_morphology("choropleth") == VisualMorphology.GEOSPATIAL
    assert VisualCapabilityRegistry.get_morphology("bubble_map") == VisualMorphology.GEOSPATIAL


def test_world_country_choropleth_selection():
    """Country-level data with normalized rate selects CHOROPLETH."""
    decision = VisualDecisionEngine.decide_visual(
        visual_id="VIS-GEO-WORLD-001",
        question_text="How does compliance rate vary across operating countries?",
        primary_dimension="country",
        measures=["compliance_rate"],
        dimension_cardinality=12,
        is_geographic_dimension=True,
        geo_level="COUNTRY",
        geo_scope="world",
        provided_units={"compliance_rate": "%"},
    )
    assert decision["status"] == "VALIDATED"
    assert decision["analytical_intent"] == "GEOSPATIAL"
    assert decision["chart_type"] == "choropleth"
    assert decision["archetype_id"] == "GEOSPATIAL_STORY"


def test_state_level_choropleth_selection():
    """State-level data with decadal population growth rate selects CHOROPLETH."""
    decision = VisualDecisionEngine.decide_visual(
        visual_id="VIS-GEO-INDIA-001",
        question_text="What is the decadal population growth rate across Indian states?",
        primary_dimension="state",
        measures=["decadal_growth_rate"],
        dimension_cardinality=28,
        is_geographic_dimension=True,
        geo_level="STATE",
        geo_scope="india",
        provided_units={"decadal_growth_rate": "%"},
    )
    assert decision["status"] == "VALIDATED"
    assert decision["analytical_intent"] == "GEOSPATIAL"
    assert decision["chart_type"] == "choropleth"


def test_city_point_bubble_map_selection():
    """City-level data with absolute employee counts selects BUBBLE_MAP."""
    decision = VisualDecisionEngine.decide_visual(
        visual_id="VIS-GEO-CITY-001",
        question_text="How is total employee headcount distributed across branch cities?",
        primary_dimension="city",
        measures=["employee_count"],
        dimension_cardinality=15,
        is_geographic_dimension=True,
        geo_level="CITY",
        geo_scope="india",
        provided_units={"employee_count": "headcount"},
    )
    assert decision["status"] == "VALIDATED"
    assert decision["analytical_intent"] == "GEOSPATIAL"
    assert decision["chart_type"] in ("bubble_map", "map")


def test_non_geographic_dataset_never_recommends_map():
    """Non-geographic dimension (department, week, id) NEVER selects map (0 maps without geo dimension)."""
    # Department ranking
    dept_decision = VisualDecisionEngine.decide_visual(
        visual_id="VIS-DEPT-TEST",
        question_text="How does attendance compare across departments?",
        primary_dimension="department",
        measures=["office_days"],
        dimension_cardinality=6,
        is_geographic_dimension=False,
        provided_units={"office_days": "employee_day"},
    )
    assert dept_decision["status"] == "VALIDATED"
    assert dept_decision["chart_type"] != "choropleth"
    assert dept_decision["chart_type"] != "map"
    assert dept_decision["chart_type"] != "bubble_map"
    assert dept_decision["chart_type"] == "horizontal_bar"

    # Weekly sales trend
    trend_decision = VisualDecisionEngine.decide_visual(
        visual_id="VIS-TREND-TEST",
        question_text="How have sales trended across weekly reporting cycles?",
        primary_dimension="reporting_week",
        measures=["sales"],
        dimension_cardinality=12,
        is_temporal_dimension=True,
        is_geographic_dimension=False,
        provided_units={"sales": "usd"},
    )
    assert trend_decision["chart_type"] == "line"


def test_ambiguous_locations_blocked():
    """Ambiguous geographic entities without disambiguation are BLOCKED (0 ambiguous locations auto-plotted)."""
    question = VisualQuestionBuilder.build_question(
        question_text="What is revenue across Springfield locations?",
        primary_dimension="location",
        measures=["revenue"],
        dimension_cardinality=4,
        is_geographic_dimension=True,
        has_ambiguous_locations=True,  # Springfield without state context
        provided_units={"revenue": "usd"},
    )
    is_valid, block_reason = VisualSemanticValidator.validate_visual_plan(
        question=question,
        selected_chart=ChartType.CHOROPLETH,
        title="Springfield Revenue",
        takeaway="Revenue across Springfield sites.",
    )
    assert not is_valid
    assert "AMBIGUOUS_GEOGRAPHY" in block_reason


def test_unsafe_relationship_blocked():
    """Cross-sheet geographic visualization without authorized JoinPlan is BLOCKED (0 maps using unsafe relationships)."""
    question = VisualQuestionBuilder.build_question(
        question_text="What is attendance by city across unconnected sheets?",
        primary_dimension="city",
        measures=["attendance"],
        dimension_cardinality=8,
        is_geographic_dimension=True,
        is_unsafe_relationship=True,  # Missing validated foreign key
        provided_units={"attendance": "employee_day"},
    )
    is_valid, block_reason = VisualSemanticValidator.validate_visual_plan(
        question=question,
        selected_chart=ChartType.MAP,
        title="Unsafe City Attendance",
        takeaway="City attendance across unlinked sheets.",
    )
    assert not is_valid
    assert "UNSAFE_RELATIONSHIP" in block_reason


def test_low_coverage_downgrades_or_blocks_map():
    """Geographic coverage below 50% blocks map recommendation."""
    question = VisualQuestionBuilder.build_question(
        question_text="What is compliance by state with poor coverage?",
        primary_dimension="state",
        measures=["compliance"],
        dimension_cardinality=10,
        is_geographic_dimension=True,
        geographic_coverage=0.35,  # Only 35% resolved
        provided_units={"compliance": "%"},
    )
    is_valid, block_reason = VisualSemanticValidator.validate_visual_plan(
        question=question,
        selected_chart=ChartType.CHOROPLETH,
        title="Low Coverage State Compliance",
        takeaway="Compliance across sparsely resolved states.",
    )
    assert not is_valid
    assert "LOW_GEOGRAPHIC_COVERAGE" in block_reason


def test_dataset_99795_dashboard_contract(tmp_path):
    """Verifies that dataset 99795 executive dashboard satisfies all metric & visual contracts:
    1. Population = 1,210,854,977 (1.21B), no double counting.
    2. Growth Rate = 17.7%, non-additive, not summed.
    3. Density = 368 people/sq. km, non-additive, not summed.
    4. Zero synthetic interaction features in KPIs.
    5. Primary visual is India Choropleth map of Population Density across 36 territories.
    """
    from app.services.adaptive_dashboard.executive_analytics import compute_governed_executive_metrics
    from app.services.adaptive_dashboard.story_builder import AnalyticalStoryBuilder
    import shutil
    import sqlite3

    baseline_path = Path(__file__).resolve().parent.parent / "data" / "db_backups_safety" / "pulsehr.sqlite3.pristine_i8_3_baseline"
    test_db_copy = tmp_path / "dataset_99795_test.sqlite3"
    shutil.copy2(baseline_path, test_db_copy)

    conn = sqlite3.connect(test_db_copy)
    conn.row_factory = sqlite3.Row
    try:
        gov_metrics = compute_governed_executive_metrics(99795, conn=conn)
        kpis = gov_metrics.get("kpis", [])
        kpi_map = {k["label"]: k for k in kpis}

        # Verify no synthetic features
        for label in kpi_map.keys():
            assert "interact_" not in label.lower()
            assert "_by_" not in label.lower()

        # Verify authoritative values
        pop_kpi = kpi_map.get("Population 2011")
        assert pop_kpi is not None
        assert abs(pop_kpi["value"] - 1210854977.0) < 1.0
        assert pop_kpi["formatted_value"] == "1.21B"

        growth_kpi = kpi_map.get("Decadal Population Growth Rate")
        assert growth_kpi is not None
        assert abs(growth_kpi["value"] - 17.7) < 0.1
        assert "%" in growth_kpi["formatted_value"]

        density_kpi = kpi_map.get("Population Density")
        assert density_kpi is not None
        assert abs(density_kpi["value"] - 368.0) < 1.0
        assert "people/sq. km" in density_kpi["unit"]

        # Verify Geospatial Story
        geo_story = AnalyticalStoryBuilder._derive_governed_geographic_story(
            dataset_id=99795,
            gov_metrics=gov_metrics,
            domain="demographics",
            story_idx=1,
            conn=conn,
        )
        assert geo_story is not None
        assert geo_story.intent == "GEOSPATIAL"
        assert "Across India" in geo_story.title

        tokens = geo_story.tokens
        assert tokens.get("chart_archetype") == "choropleth"
        assert tokens.get("geo_scope") == "india"
        assert tokens.get("geo_level") == "STATE"
        assert "Density" in tokens.get("primary_measure", "")

        # Must contain exactly 36 component territories (national India excluded from map & table data)
        assert len(tokens.get("categories", [])) == 36
        assert len(tokens.get("map_data", [])) == 36
        assert len(tokens.get("table_data", [])) == 36

        # Verify first ranked territory has companion metrics
        first_tbl = tokens["table_data"][0]
        assert first_tbl["rank"] == 1
        assert "population" in first_tbl
        assert "growth" in first_tbl
        assert "density" in first_tbl
        assert first_tbl["lineage"] == "OBSERVED"

        # Verify multi-metric switching contract
        available_m = tokens.get("available_metrics", [])
        assert len(available_m) >= 3
        metric_labels = [m["label"] for m in available_m]
        assert "Population Density" in metric_labels
        assert "Population 2011" in metric_labels
        assert "Decadal Population Growth Rate" in metric_labels

        # Verify each metric has complete precomputed artifacts
        for m in available_m:
            assert m["metric_id"]
            assert m["label"]
            assert m["unit"]
            assert m["map_type"] in ("choropleth", "bubble_map")
            assert len(m["categories"]) == 36
            assert len(m["values"]) == 36
            assert len(m["map_data"]) == 36
            assert len(m["table_data"]) == 36
            assert m["takeaway"]
            assert m["key_metric"]

        # Verify accessible summary
        assert "accessible_summary" in tokens
        assert "Delhi is highest" in tokens["accessible_summary"]
    finally:
        conn.close()


def test_p0_database_invariant():
    """Verifies that pulsehr.sqlite3 file size and SHA-256 remain pristine."""
    db_path = Path(__file__).resolve().parent.parent / "data" / "db" / "pulsehr.sqlite3"
    if not db_path.exists():
        db_path = Path(__file__).resolve().parent.parent.parent / "backend" / "data" / "db" / "pulsehr.sqlite3"

    expected_size = 70385664
    expected_hash = "1561d64eeae26f4d30926371740d6ca9dc41eb6ea7c537281763b7d5aabd9496"

    actual_size = db_path.stat().st_size
    actual_hash = hashlib.sha256(db_path.read_bytes()).hexdigest()

    assert actual_size == expected_size, f"Size mismatch: expected {expected_size}, got {actual_size}"
    assert actual_hash == expected_hash, f"Hash mismatch: expected {expected_hash}, got {actual_hash}"
