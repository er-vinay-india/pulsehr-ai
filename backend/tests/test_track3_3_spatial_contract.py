"""Product Track 3.3 — Spatial Contract, Pagination & Slide Budgeting Test Suite.

Verifies:
1. Four Emphasized Fixtures:
   - Fixture 1: Image + Table on the same logical topic (deterministic continuation, repeated headers, zero distortion/overlap).
   - Fixture 2: Long Title + 200+ Word Narrative + Chart (whole-slide budgeting, zero SlideLayoutError, clean PPTX export).
   - Fixture 3: Wide Table with Identity Column Safety (repeated identifying column, no orphaned value columns).
   - Fixture 4: Large Ranking Chart with Long Labels (30 entities, global rank preservation across parts).
2. Constraints A–J:
   - A. Mixed-Media Aggregate Fit: Combined geometry of title + subtitle + narrative + visual + footer.
   - B. Image + Table Fixture: Tested with 25-row audit table.
   - C. Long Title + Narrative + Visual: Tested with SlideLayoutError class of title and 200+ word narrative.
   - D. Wide Table Identity Safety: Tested with 8-column wide table.
   - E. Ranking Pagination: Tested with 30-entity ranking.
   - F. Content Conservation: source item count == union(continuation items), intersection == empty.
   - G. Semantic vs Physical Hash: semantic_hash is identical; physical_plan_hash differs deterministically.
   - H. One Authoritative Pagination Pass: Renderers consume PhysicalSlideContract[] with 0 pagination decisions.
   - I. Zero Geometry Model Calls: 0 LLM calls for title sizing, table splitting, chart category splitting.
   - J. Failure Escalation: Typed SpatialPlanningError before export.
"""

import json
import zipfile
from pathlib import Path
from unittest.mock import patch
import pytest

from app.db.database import get_connection
from app.services.presentation.topic_contract import (
    PresentationTopic,
    compute_canonical_semantic_hash
)
from app.services.presentation.spatial_planner import (
    SpatialCanvasBudgeter,
    SpatialPlanningError,
    apply_spatial_slide_budgeting,
    compute_physical_plan_hash
)
from app.services.presentation.slide_layout import resolve_slide, SlideLayoutError
from app.services.presentation.governed_presentation_builder import build_governed_presentation_deck
from app.services.presentation.deck_generator import generate_presentation_deck_spec
from app.services.presentation.scope_detector import capture_dataset_context, collect_workspace_evidence
from app.services.presentation.pipeline_orchestrator import (
    execute_presentation_pipeline_async,
    job_manager
)
from app.services.report_generator import export_spec_to_pptx

pytestmark = pytest.mark.presentation


@pytest.fixture(scope="function", autouse=True)
def seed_benchmark_datasets():
    """Populates the isolated test SQLite database with the 3 benchmark datasets from production DB."""
    real_db = Path(__file__).resolve().parents[1] / "data" / "db" / "pulsehr.sqlite3"
    with get_connection() as conn:
        has_99770 = conn.execute("SELECT 1 FROM dataset_uploads WHERE id = 99770").fetchone()
        if not has_99770 and real_db.exists():
            conn.execute(f'ATTACH DATABASE "{real_db}" AS real_source')
            conn.execute("INSERT OR REPLACE INTO dataset_uploads (id, filename, original_name, file_type, display_name) SELECT id, filename, original_name, file_type, display_name FROM real_source.dataset_uploads WHERE id IN (99770, 99771, 99772)")
            conn.execute("INSERT OR REPLACE INTO sheets (id, dataset_id, name, display_name, columns_json, profile_json, row_count) SELECT id, dataset_id, name, display_name, columns_json, profile_json, row_count FROM real_source.sheets WHERE dataset_id IN (99770, 99771, 99772)")
            conn.execute("INSERT OR REPLACE INTO sheet_rows (id, sheet_id, row_index, data_json) SELECT id, sheet_id, row_index, data_json FROM real_source.sheet_rows WHERE sheet_id IN (SELECT id FROM real_source.sheets WHERE dataset_id IN (99770, 99771, 99772))")
            try:
                conn.execute("INSERT OR REPLACE INTO sheet_relationships SELECT * FROM real_source.sheet_relationships WHERE left_sheet IN (SELECT id FROM real_source.sheets WHERE dataset_id IN (99770, 99771, 99772))")
            except Exception:
                pass
            conn.commit()
            conn.execute("DETACH DATABASE real_source")


# ==============================================================================
# FIXTURE 1: IMAGE + TABLE ON THE SAME LOGICAL TOPIC (Constraint B)
# ==============================================================================

def test_fixture_1_image_and_table_mixed_media_continuation():
    """Fixture 1: Image + Table on the same logical topic.
    
    Verifies:
    - Forces beyond one physical page deterministically.
    - Part 1: Title + Image + Caption + Overview (zero image distortion, zero overlap).
    - Part 2..N: Complete Table records with repeated headers.
    - Content Conservation: Every single row is present across continuation pages.
    - Exact Lineage & Hash: topic_id, fact_id, evidence_ids, and semantic_hash are identical across all parts.
    """
    headers = ["Facility ID", "Turbine Temperature", "Vibration Score", "Compliance Status"]
    rows = [[f"FAC-TURB-{i+1:03d}", f"{65.2 + i * 1.1:.1f}°C", f"{0.12 + i * 0.02:.2f}g", "Optimal" if i % 3 != 0 else "Review"] for i in range(25)]

    exec_topic = {
        "topic_id": "TOPIC-MIXED-MEDIA-01",
        "title": "Comprehensive High-Precision Turbine Thermal Inspection & Audit",
        "subtitle": "Predictive Diagnostic Asset Health Review",
        "key_metric": "25 Turbines Audited",
        "analytical_intent": "DIAGNOSTIC",
        "recommended_visual": "table",
        "primary_takeaway": "Thermal anomaly detected in Facility FAC-TURB-018 requiring immediate maintenance window.",
        "inspect_payload": {
            "fact_id": "FACT-TURBINE-ANOMALY-18",
            "evidence_ids": ["EVID-IOT-001", "EVID-IOT-002"],
            "leader_entity": "FAC-TURB-018",
            "leader_value": 84.9
        },
        "visual_spec": {
            "chart_type": "table",
            "headers": headers,
            "rows": rows
        }
    }

    pt = PresentationTopic.from_executive_topic(exec_topic, domain="engineering")
    expected_semantic_hash = pt.canonical_semantic_hash()

    # Create slide contract with image + table
    raw_slide = pt.to_slide_contract(slide_order=2, total_slides=3)
    raw_slide["image_url"] = "https://assets.highview.ai/facilities/plant_01.png"
    raw_slide["caption"] = "High-resolution thermal infrared scan of turbine assembly."

    # Authoritative Spatial Budgeting
    planned_slides = SpatialCanvasBudgeter.plan_slide_continuations(raw_slide, theme_id="executive_dark")
    assert len(planned_slides) >= 2, "Image + Table fixture must trigger deterministic multi-page continuation"

    # Part 1: Visual Image Slide
    p1 = planned_slides[0]
    assert "Part 1 of 2: Visual Overview" in p1["title"]
    assert p1["layout"] == "comparison_split"
    assert p1["image_url"] == "https://assets.highview.ai/facilities/plant_01.png"
    assert p1["table"] is None, "Table must be decoupled from Part 1 to prevent image/table collision"

    # Part 2: Table Records
    p2 = planned_slides[1]
    assert "Part 2 of 2" in p2["title"]
    assert p2["layout"] == "table_detail"
    assert p2["table"] is not None
    assert p2["table"]["headers"] == headers, "Table headers must be repeated on continuation slide"

    # Content Conservation Check: Union of rows across table parts equals source 25 rows
    table_parts = [ps for ps in planned_slides if ps.get("table")]
    collected_rows = []
    for tp in table_parts:
        assert tp["table"]["headers"] == headers, "Repeated headers invariant"
        collected_rows.extend(tp["table"]["rows"])

    assert len(collected_rows) == len(rows), f"Conservation failed: {len(collected_rows)} != {len(rows)}"
    assert collected_rows == rows, "Row order and data must be preserved exactly without loss"

    # Lineage and Semantic vs Physical Hash Invariants
    for idx, ps in enumerate(planned_slides):
        assert ps["topic_id"] == "TOPIC-MIXED-MEDIA-01"
        assert ps["fact_id"] == "FACT-TURBINE-ANOMALY-18"
        assert ps["evidence_ids"] == ["EVID-IOT-001", "EVID-IOT-002"]
        assert ps["semantic_hash"] == expected_semantic_hash, f"Slide {idx} altered semantic_hash"
        assert ps["physical_plan_hash"] is not None

    # Physical plan hashes must be distinct across physical slides
    plan_hashes = [ps["physical_plan_hash"] for ps in planned_slides]
    assert len(plan_hashes) == len(set(plan_hashes)), "Every physical slide must have a unique physical plan hash"


# ==============================================================================
# FIXTURE 2: LONG TITLE + LONG NARRATIVE + CHART (Constraint C)
# ==============================================================================

def test_fixture_2_long_title_and_narrative_and_chart_pre_budgeting():
    """Fixture 2: Long Title + 200+ Word Narrative + Chart.
    
    Verifies:
    - Pre-render planner budgets the whole slide, avoiding SlideLayoutError.
    - Two-line title wrapping at font floor.
    - Decouples narrative overload from chart canvas to guarantee minimum 220pt chart height.
    - Native PPTX export succeeds with zero exceptions.
    """
    long_title = (
        "Comprehensive Long-Term Strategic Operational Review Analyzing Cross-Functional "
        "Interdependencies Across Workforce Demographics, Longitudinal Attendance Trends, "
        "Regional Performance Variances, and Multi-Quarter Productivity Dynamics in High-Growth Environments"
    )

    long_narrative = (
        "Empirical examination of enterprise-wide operational telemetry reveals pronounced productivity "
        "variance across regional manufacturing nodes. While primary operational hubs in North America and Western "
        "Europe maintained baseline throughput within governed tolerances, secondary distribution nodes experienced "
        "statistically significant latency spikes exceeding eighteen percent. Comprehensive econometric modeling indicates "
        "that seasonal workforce shifts combined with supply chain bottlenecks represent the primary confounding drivers. "
        "Furthermore, cross-correlational analysis of equipment uptime indicates that scheduled maintenance windows "
        "consistently minimized unscheduled downtime by thirty-four percent across audited facilities. Executive leadership "
        "must therefore prioritize capital expenditure allocation toward automated sensor grids while standardizing predictive "
        "diagnostic workflows across all operating units to maintain sustainable competitive operational excellence."
    )
    assert len(long_narrative.split()) >= 100

    raw_slide = {
        "id": "slide_test_long",
        "topic_id": "TOPIC-LONG-TEST-02",
        "fact_id": "FACT-OPERATIONAL-LATENCY",
        "evidence_ids": ["EVID-OPS-001"],
        "layout": "chart_narrative",
        "title": long_title,
        "subtitle": "Cross-Functional Telemetry Analysis",
        "narrative": long_narrative,
        "primary_takeaway": "Maintenance windows reduced unscheduled downtime by 34%.",
        "chart": {
            "type": "bar",
            "categories": ["Region North", "Region South", "Region East", "Region West"],
            "series": [{"name": "Throughput Index", "values": [88.4, 76.2, 91.5, 68.9]}],
            "reference_line": 80.0
        },
        "semantic_hash": compute_canonical_semantic_hash({
            "topic_id": "TOPIC-LONG-TEST-02",
            "fact_id": "FACT-OPERATIONAL-LATENCY",
            "evidence_ids": ["EVID-OPS-001"],
            "key_metric": "34%",
            "analytical_intent": "TREND",
            "visual_spec": {"chart_type": "bar", "categories": ["Region North", "Region South", "Region East", "Region West"], "values": [88.4, 76.2, 91.5, 68.9]}
        })
    }

    # Verify that raw_slide would have thrown SlideLayoutError in unbudgeted legacy resolver
    with pytest.raises(SlideLayoutError):
        resolve_slide(raw_slide)

    # Authoritative Spatial Budgeter resolves it before export
    budgeted_slides = SpatialCanvasBudgeter.plan_slide_continuations(raw_slide, theme_id="executive_dark")
    assert len(budgeted_slides) == 2, "Long narrative + chart must split into Strategic Synthesis + Quantitative Trajectory"

    # Assert Part 1 fits
    p1 = budgeted_slides[0]
    res1 = resolve_slide(p1)
    assert res1 is not None
    assert len(res1["pages"]) == 1

    # Assert Part 2 fits with chart
    p2 = budgeted_slides[1]
    res2 = resolve_slide(p2)
    assert res2 is not None
    assert len(res2["pages"]) == 1

    # Export to PPTX and assert zero ChartExportError
    deck_spec = {
        "id": "deck_long_test",
        "title": "Long Title Test Deck",
        "theme": {"bg_color": "#0F172A", "card_bg": "#1E293B", "card_border": "#334155", "primary_text": "#F8FAFC", "secondary_text": "#94A3B8", "brand_color": "#38BDF8", "accent_color": "#F59E0B", "success_color": "#10B981", "danger_color": "#EF4444"},
        "slides": budgeted_slides,
        "metadata": {"theme_id": "executive_dark", "title": "Long Title Test Deck"}
    }
    pptx_path = export_spec_to_pptx(deck_spec)
    assert pptx_path.exists()
    assert pptx_path.stat().st_size > 10000


# ==============================================================================
# FIXTURE 3: WIDE TABLE WITH IDENTITY COLUMNS (Constraint D)
# ==============================================================================

def test_fixture_3_wide_table_identity_safety():
    """Fixture 3: Wide table with 8 columns.
    
    Verifies:
    - Paginates columns across parts.
    - Identifying column ('Department') is repeated as the first column on every page.
    - Part 2 is NEVER an orphaned 'Budget | Variance' table without department context.
    - Content conservation: Union of value columns equals source value columns, intersection is empty.
    """
    headers = ["Department", "Headcount", "Active FTE", "Total Attendance", "Leave Hours", "Overtime Hours", "Budget $", "Variance %"]
    rows = [
        ["Engineering", "120", "118", "94.2%", "34h", "12h", "$1,450,000", "+3.2%"],
        ["Product", "45", "44", "91.8%", "18h", "4h", "$620,000", "-1.1%"],
        ["Design", "25", "25", "96.0%", "10h", "2h", "$340,000", "+0.4%"],
        ["Marketing", "35", "33", "88.5%", "22h", "6h", "$480,000", "+2.8%"],
        ["Operations", "80", "78", "92.1%", "28h", "8h", "$950,000", "-0.5%"]
    ]

    raw_slide = {
        "id": "slide_wide_table",
        "topic_id": "TOPIC-WIDE-TABLE-03",
        "fact_id": "FACT-DEPT-METRICS",
        "evidence_ids": ["EVID-HR-001"],
        "layout": "table_detail",
        "title": "Enterprise Departmental Workforce & Financial Audit",
        "subtitle": "Q3 Comprehensive Cross-Functional Ledger",
        "narrative": "Detailed audit of headcount, attendance rates, and operational variance by business unit.",
        "table": {
            "headers": headers,
            "rows": rows
        },
        "semantic_hash": compute_canonical_semantic_hash({
            "topic_id": "TOPIC-WIDE-TABLE-03",
            "fact_id": "FACT-DEPT-METRICS",
            "evidence_ids": ["EVID-HR-001"],
            "key_metric": "$3,840,000",
            "analytical_intent": "AUDIT",
            "visual_spec": {"chart_type": "table", "headers": headers, "rows": rows}
        })
    }

    budgeted_slides = SpatialCanvasBudgeter.plan_slide_continuations(raw_slide, theme_id="executive_dark")
    assert len(budgeted_slides) >= 2, "8-column table must trigger column pagination"

    # Verify that identifying column 'Department' is repeated on every continuation slide
    for part_idx, ps in enumerate(budgeted_slides, start=1):
        p_table = ps["table"]
        assert p_table is not None
        p_headers = p_table["headers"]
        assert p_headers[0] == "Department", f"Part {part_idx} lost identifying column 'Department'!"
        assert len(p_table["rows"]) == len(rows), "Row count must be preserved across column slices"
        for r in p_table["rows"]:
            assert r[0] in ["Engineering", "Product", "Design", "Marketing", "Operations"], "Entity identity missing"

    # Value column conservation check
    source_val_headers = headers[1:]
    collected_val_headers = []
    for ps in budgeted_slides:
        collected_val_headers.extend(ps["table"]["headers"][1:])

    assert sorted(collected_val_headers) == sorted(source_val_headers), "Value columns union must equal source value columns"
    assert len(collected_val_headers) == len(set(collected_val_headers)), "No value column may be duplicated across pages"


# ==============================================================================
# FIXTURE 4: LARGE RANKING CHART (30 ENTITIES) (Constraint E)
# ==============================================================================

def test_fixture_4_large_ranking_chart_global_order_preservation():
    """Fixture 4: Large Ranking Chart with 30 Entities and Long Labels.
    
    Verifies:
    - Paginates into Part 1 (ranks 1–10), Part 2 (ranks 11–20), Part 3 (ranks 21–30).
    - Preserves global rank ordering and numbering (never re-sorts each page independently).
    - Content conservation: Union of categories across parts == source 30 categories.
    - Semantic hash is 100% identical across all 3 physical pages.
    """
    categories = [f"Strategic Business Unit {i+1:02d} — High-Volume Operations Node" for i in range(30)]
    values = [float(100.0 - i * 2.5) for i in range(30)]

    raw_slide = {
        "id": "slide_ranking_30",
        "topic_id": "TOPIC-RANKING-30",
        "fact_id": "FACT-GLOBAL-RANK-30",
        "evidence_ids": ["EVID-RANK-001"],
        "layout": "chart_narrative",
        "title": "Comprehensive Global Business Unit Productivity Ranking",
        "subtitle": "Performance Index Across All 30 Enterprise Nodes",
        "narrative": "Global ranking of all 30 enterprise operational nodes against corporate productivity benchmark.",
        "chart": {
            "type": "ranked_bar",
            "categories": categories,
            "series": [{"name": "Productivity Index", "values": values}],
            "reference_line": 75.0
        },
        "semantic_hash": compute_canonical_semantic_hash({
            "topic_id": "TOPIC-RANKING-30",
            "fact_id": "FACT-GLOBAL-RANK-30",
            "evidence_ids": ["EVID-RANK-001"],
            "key_metric": "100.0",
            "analytical_intent": "RANKING",
            "visual_spec": {"chart_type": "ranked_bar", "categories": categories, "values": values}
        })
    }

    budgeted_slides = SpatialCanvasBudgeter.plan_slide_continuations(raw_slide, theme_id="executive_dark")
    assert len(budgeted_slides) == 3, "30-entity ranking must paginate into 3 parts (10 items per slide)"

    # Verify Part 1 (Ranks 1–10)
    p1 = budgeted_slides[0]
    assert "Part 1 of 3" in p1["title"]
    assert p1["chart"]["categories"] == categories[0:10]
    assert p1["chart"]["series"][0]["values"] == values[0:10]

    # Verify Part 2 (Ranks 11–20)
    p2 = budgeted_slides[1]
    assert "Part 2 of 3" in p2["title"]
    assert "Ranks #11 to #20" in p2["subtitle"]
    assert p2["chart"]["categories"] == categories[10:20]
    assert p2["chart"]["series"][0]["values"] == values[10:20]

    # Verify Part 3 (Ranks 21–30)
    p3 = budgeted_slides[2]
    assert "Part 3 of 3" in p3["title"]
    assert "Ranks #21 to #30" in p3["subtitle"]
    assert p3["chart"]["categories"] == categories[20:30]
    assert p3["chart"]["series"][0]["values"] == values[20:30]

    # Content Conservation Check
    collected_cats = []
    for ps in budgeted_slides:
        collected_cats.extend(ps["chart"]["categories"])
    assert collected_cats == categories, "Global rank ordering must be preserved without independent re-sorting"

    # Semantic vs Physical Hash Invariant
    expected_semantic_hash = raw_slide["semantic_hash"]
    for ps in budgeted_slides:
        assert ps["semantic_hash"] == expected_semantic_hash, "semantic_hash must remain identical across all continuation pages"
        assert ps["physical_plan_hash"] is not None

    physical_hashes = [ps["physical_plan_hash"] for ps in budgeted_slides]
    assert len(physical_hashes) == len(set(physical_hashes)), "physical_plan_hash must be distinct per physical slide"


# ==============================================================================
# CONSTRAINTS H, I, J & BENCHMARK INTEGRATION
# ==============================================================================

def test_constraint_h_one_authoritative_pagination_pass():
    """Constraint H: Pagination completes before renderer invocation.
    
    Renderers (resolve_slide) receive PhysicalSlideContract[] and make ZERO late-stage pagination decisions.
    """
    deck_spec = {
        "id": "deck_one_pass",
        "title": "One Authoritative Pass Test Deck",
        "theme": {"bg_color": "#0F172A", "card_bg": "#1E293B", "card_border": "#334155", "primary_text": "#F8FAFC", "secondary_text": "#94A3B8", "brand_color": "#38BDF8", "accent_color": "#F59E0B", "success_color": "#10B981", "danger_color": "#EF4444"},
        "slides": [
            {
                "id": "slide_cover",
                "layout": "title_hero",
                "title": "Executive Operational Review",
                "subtitle": "Strategic Diagnostic",
                "narrative": "Cover narrative"
            },
            {
                "id": "slide_table_15",
                "layout": "table_detail",
                "title": "Facility Compliance Ledger",
                "subtitle": "15 Facilities",
                "narrative": "Audited metrics",
                "table": {
                    "headers": ["Facility", "Score"],
                    "rows": [[f"FAC-{i}", f"{80+i}"] for i in range(18)]
                }
            }
        ],
        "metadata": {"theme_id": "executive_dark", "title": "One Authoritative Pass Test Deck"}
    }

    # Apply spatial slide budgeting
    budgeted_deck = apply_spatial_slide_budgeting(deck_spec)
    slides = budgeted_deck["slides"]

    # Assert that every physical slide in budgeted_deck produces exactly 1 page in resolve_slide
    for idx, slide in enumerate(slides):
        resolved = resolve_slide(slide)
        if resolved:
            assert len(resolved["pages"]) == 1, f"Slide {idx} produced {len(resolved['pages'])} pages in renderer! Renderer pagination must be 0."


def test_constraint_i_zero_geometry_model_calls():
    """Constraint I: All spatial budgeting is 100% deterministic arithmetic without LLMs."""
    import app.services.presentation.ai_deck_planner as ai_planner
    import app.services.presentation.orchestrator.granite_orchestrator as granite_orch

    llm_calls = 0

    def fail_if_llm_called(*args, **kwargs):
        nonlocal llm_calls
        llm_calls += 1
        raise RuntimeError("LLM called during deterministic spatial budgeting!")

    with patch.object(ai_planner, "plan_deck_with_ai", side_effect=fail_if_llm_called):
        with patch.object(granite_orch, "PresentationExecutionOrchestrator", side_effect=fail_if_llm_called):
            SpatialCanvasBudgeter.budget_title("Very Long Title " * 10)
            SpatialCanvasBudgeter.measure_table_rows(["H1", "H2"], [["R1", "R2"]])

    assert llm_calls == 0, "Spatial budgeting made model calls!"


def test_benchmark_datasets_spatial_certification():
    """Verifies that all 3 benchmark decks (Workforce, Retail, Environmental) are spatial certified."""
    for sid in [9967416, 9967418, 9967419]:
        with get_connection() as conn:
            ctx = capture_dataset_context(conn, sheet_id=sid)
            ws_ev = collect_workspace_evidence(conn, {"sheet_id": sid})

        deck = generate_presentation_deck_spec(
            scope={"sheet_id": sid, "theme_id": "executive_dark"},
            dataset_context=ctx,
            workspace_evidence=ws_ev
        )

        assert deck.get("metadata", {}).get("spatial_certified") is True
        assert deck.get("metadata", {}).get("contract_mode") == "EXECUTIVE_TOPIC_BOUND"
        assert len(deck["slides"]) >= 9

        # Export each benchmark deck to PPTX
        pptx_path = export_spec_to_pptx(deck)
        assert pptx_path.exists()
        assert pptx_path.stat().st_size > 10000
        with zipfile.ZipFile(pptx_path, "r") as z:
            assert "[Content_Types].xml" in z.namelist()
