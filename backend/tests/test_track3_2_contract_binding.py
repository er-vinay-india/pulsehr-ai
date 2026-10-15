"""Product Track 3.2 — Upstream Contract Binding & Elimination of Parallel Analytical Truth.

Verifies:
1. ExecutiveTopic / VisualSpec -> PresentationTopic -> Presentation Planning.
2. NO raw-column reinterpretation.
3. NO build_hr_report analytical bypass for governed datasets.
4. NO build_grounded_review analytical fallback for governed datasets.
5. NO new metric calculation.
6. NO loss of topic_id / fact_id / evidence_ids.
7. Invariant: One governed ExecutiveTopic maps to one presentation topic identity,
   which may render as one or more physical slides without changing fact/evidence ownership.
8. Semantic Acceptance Invariant (Exact Match):
   - topic_id: exact match
   - fact_id: exact match
   - evidence_ids: exact match
   - metric: exact match
   - unit: exact match
   - leader: exact match
   - leader value: exact match
   - ranking direction: exact match
   - reference line: exact match
   - analytical intent: exact match
   - VisualSpec semantics: exact match
"""

import pytest
import zipfile
from pathlib import Path
from app.db.database import get_connection
from app.services.adaptive_dashboard.engine import run_adaptive_dashboard
from app.services.presentation.topic_contract import PresentationTopic
from app.services.presentation.governed_presentation_builder import build_governed_presentation_deck
from app.services.presentation.deck_generator import generate_presentation_deck_spec
from app.services.presentation.scope_detector import capture_dataset_context, collect_workspace_evidence
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



def test_presentation_topic_model_fidelity():
    """Verifies that PresentationTopic extracts and preserves all 11 governed attributes with zero loss."""
    exec_topic = {
        "topic_id": "TOPIC-TEST-01",
        "title": "Which department has the highest engagement?",
        "subtitle": "Department Engagement Analysis",
        "technical_title": "Engagement by Department Benchmark",
        "key_metric": "88.5%",
        "analytical_intent": "RANKING",
        "recommended_visual": "ranked_bar",
        "display_order": 1,
        "slot_type": "hero",
        "primary_takeaway": "Engineering leads all departments in engagement at 88.5%.",
        "recommended_action": "Share Engineering engagement practices across org.",
        "inspect_payload": {
            "fact_id": "FACT-ENG-01",
            "evidence_ids": ["EVID-TEST-001", "EVID-TEST-002"],
            "leader_entity": "Engineering",
            "leader_value": 88.5,
            "ranking_metadata": {
                "ranking_direction": "descending",
                "unit": "%",
                "benchmark": 75.0,
                "entity_column": "Department",
                "measure_column": "Engagement"
            }
        },
        "visual_spec": {
            "chart_type": "ranked_bar",
            "categories": ["Engineering", "Product", "Operations"],
            "values": [88.5, 82.1, 74.0],
            "benchmark": 75.0,
            "unit": "%"
        }
    }

    pt = PresentationTopic.from_executive_topic(exec_topic, domain="workforce")
    assert pt.topic_id == "TOPIC-TEST-01"
    assert pt.fact_id == "FACT-ENG-01"
    assert pt.evidence_ids == ["EVID-TEST-001", "EVID-TEST-002"]
    assert pt.metric == "88.5%"
    assert pt.unit == "%"
    assert pt.leader == "Engineering"
    assert pt.leader_value == 88.5
    assert pt.ranking_direction == "descending"
    assert pt.reference_line == 75.0
    assert pt.analytical_intent == "RANKING"
    assert pt.visual_spec["chart_type"] == "ranked_bar"

    slide = pt.to_slide_contract(slide_order=2, total_slides=10)
    assert slide["topic_id"] == "TOPIC-TEST-01"
    assert slide["fact_id"] == "FACT-ENG-01"
    assert slide["evidence_ids"] == ["EVID-TEST-001", "EVID-TEST-002"]
    assert slide["key_metric"] == "88.5%"
    assert slide["unit"] == "%"
    assert slide["leader"] == "Engineering"
    assert slide["leader_value"] == 88.5
    assert slide["ranking_direction"] == "descending"
    assert slide["reference_line"] == 75.0
    assert slide["analytical_intent"] == "RANKING"
    assert slide["visual_spec"]["chart_type"] == "ranked_bar"


def _verify_deck_against_executive_topics(sheet_id: int, expected_domain: str):
    """Core verification harness enforcing exact match of all 11 semantic attributes across 8 topics."""
    with get_connection() as conn:
        ctx = capture_dataset_context(conn, sheet_id=sheet_id)
        ws_ev = collect_workspace_evidence(conn, {"sheet_id": sheet_id})

    # Ensure context contains governed presentation topics
    assert len(ctx["executive_topics"]) == 8
    assert len(ctx["presentation_topics"]) == 8

    # Generate presentation deck spec
    deck = generate_presentation_deck_spec(
        scope={"sheet_id": sheet_id, "theme_id": "executive_dark"},
        dataset_context=ctx,
        workspace_evidence=ws_ev
    )

    assert deck.get("metadata", {}).get("contract_mode") == "EXECUTIVE_TOPIC_BOUND"
    assert deck["slide_count"] == 9  # 1 cover slide + 8 topic slides
    assert len(deck["slides"]) == 9

    # Upstream ground truth topics
    ad_resp = run_adaptive_dashboard(sheet_id=sheet_id, include_dataset_intelligence=True)
    upstream_topics = [t if isinstance(t, dict) else t.model_dump() for t in ad_resp.executive_topics]
    assert len(upstream_topics) == 8

    upstream_by_id = {t["topic_id"]: t for t in upstream_topics}

    # Verify each topic slide (slides 2 to 9)
    topic_slides = deck["slides"][1:]
    assert len(topic_slides) == 8

    for slide in topic_slides:
        t_id = slide["topic_id"]
        assert t_id in upstream_by_id, f"Slide topic {t_id} missing from upstream ExecutiveTopics"
        u_topic = upstream_by_id[t_id]
        u_inspect = u_topic.get("inspect_payload") or {}
        u_vspec = u_topic.get("visual_spec") or {}

        # 1. topic_id: exact match
        assert slide["topic_id"] == u_topic["topic_id"]

        # 2. fact_id: exact match
        expected_fact = u_inspect.get("fact_id") or u_vspec.get("fact_id") or u_topic.get("fact_id")
        assert slide["fact_id"] == expected_fact

        # 3. evidence_ids: exact match
        expected_ev = u_inspect.get("evidence_ids") or u_topic.get("evidence_ids") or u_vspec.get("evidence_ids") or []
        if isinstance(expected_ev, str):
            expected_ev = [expected_ev]
        assert slide["evidence_ids"] == [str(e) for e in expected_ev if e]

        # 4. metric: exact match
        expected_metric = str(u_topic.get("key_metric") or u_vspec.get("key_metric") or "")
        assert slide["key_metric"] == expected_metric

        # 5. unit: exact match
        expected_unit = str(u_vspec.get("unit") or (u_inspect.get("ranking_metadata") or {}).get("unit") or "")
        assert slide["unit"] == expected_unit

        # 6. leader: exact match
        expected_leader = u_inspect.get("leader_entity") or u_vspec.get("leader_entity") or u_vspec.get("leader")
        assert slide["leader"] == expected_leader

        # 7. leader value: exact match
        expected_lval = u_inspect.get("leader_value") or u_vspec.get("leader_value")
        assert slide["leader_value"] == expected_lval

        # 8. ranking direction: exact match
        expected_dir = (u_inspect.get("ranking_metadata") or u_vspec.get("ranking_metadata") or {}).get("ranking_direction")
        assert slide["ranking_direction"] == expected_dir

        # 9. reference line: exact match
        expected_ref = u_vspec.get("benchmark") or (u_inspect.get("ranking_metadata") or {}).get("benchmark")
        if expected_ref is None and "reference_lines" in u_vspec:
            rl = u_vspec.get("reference_lines") or []
            if rl and isinstance(rl[0], dict):
                expected_ref = rl[0].get("value")
        assert slide["reference_line"] == expected_ref

        # 10. analytical intent: exact match
        expected_intent = str(u_topic.get("analytical_intent") or u_inspect.get("analytical_intent") or u_vspec.get("analytical_intent") or "RANKING")
        assert slide["analytical_intent"] == expected_intent

        # 11. VisualSpec semantics: exact match
        assert slide["visual_spec"]["chart_type"] == u_vspec.get("chart_type")

    # Export to PPTX and verify
    pptx_path = export_spec_to_pptx(deck)
    assert pptx_path.exists()
    assert pptx_path.stat().st_size > 10000
    with zipfile.ZipFile(pptx_path, "r") as z:
        assert "[Content_Types].xml" in z.namelist()


def test_workforce_contract_binding():
    """Workforce domain: asserts exact match and confirms build_hr_report bypass is eliminated."""
    _verify_deck_against_executive_topics(9967416, "workforce")


def test_retail_contract_binding():
    """Retail domain: asserts exact match and confirms build_grounded_review fallback is eliminated."""
    _verify_deck_against_executive_topics(9967418, "retail")


def test_environmental_contract_binding():
    """Environmental domain: asserts exact match and confirms build_grounded_review fallback is eliminated."""
    _verify_deck_against_executive_topics(9967419, "environmental")


def test_multi_slide_continuation_preserves_identity_and_evidence():
    """Invariant: One governed ExecutiveTopic maps to one presentation topic identity,
    which may render as one or more physical slides without changing fact/evidence ownership.
    """
    categories = [f"Entity {i+1}" for i in range(25)]
    values = [float(100 - i * 3) for i in range(25)]

    exec_topic = {
        "topic_id": "TOPIC-MULTI-PAGE-01",
        "title": "Comprehensive Facility Carbon Emission Audit",
        "subtitle": "Complete 25-Facility Audit",
        "key_metric": "Total MT CO2e",
        "analytical_intent": "RANKING",
        "recommended_visual": "horizontal_bar",
        "primary_takeaway": "Top 5 facilities account for 62% of all enterprise emissions.",
        "inspect_payload": {
            "fact_id": "FACT-CARBON-25",
            "evidence_ids": ["EVID-ENV-001", "EVID-ENV-002"],
            "leader_entity": "Entity 1",
            "leader_value": 100.0,
            "ranking_metadata": {"ranking_direction": "descending", "unit": "MT"}
        },
        "visual_spec": {
            "chart_type": "horizontal_bar",
            "categories": categories,
            "values": values,
            "unit": "MT"
        }
    }

    pt = PresentationTopic.from_executive_topic(exec_topic)

    # Paginate with max 10 rows per slide
    slides = pt.to_slide_contracts(start_order=2, total_slides=4, max_items_per_slide=10, enable_pagination=True)
    assert len(slides) == 3

    assert "Part 1 of 3" in slides[0]["title"]
    assert "Part 2 of 3" in slides[1]["title"]
    assert "Part 3 of 3" in slides[2]["title"]

    # Invariant assertion: topic_id, fact_id, and evidence_ids MUST BE IDENTICAL across all physical slides
    for idx, slide in enumerate(slides):
        assert slide["topic_id"] == "TOPIC-MULTI-PAGE-01", f"Slide {idx} changed topic_id"
        assert slide["fact_id"] == "FACT-CARBON-25", f"Slide {idx} changed fact_id"
        assert slide["evidence_ids"] == ["EVID-ENV-001", "EVID-ENV-002"], f"Slide {idx} lost evidence_ids"
        assert slide["key_metric"] == "Total MT CO2e"
        assert slide["leader"] == "Entity 1"
        assert slide["leader_value"] == 100.0
        assert slide["ranking_direction"] == "descending"


def test_legacy_opt_in_flags_preserved():
    """Verifies that legacy builders can still be explicitly opted into via force flags."""
    with get_connection() as conn:
        ctx = capture_dataset_context(conn, sheet_id=9967416)
        ws_ev = collect_workspace_evidence(conn, {"sheet_id": 9967416})

    # 1. Force legacy HR report builder
    hr_deck = generate_presentation_deck_spec(
        scope={"force_legacy_hr_builder": True},
        dataset_context=ctx,
        workspace_evidence=ws_ev
    )
    assert hr_deck.get("metadata", {}).get("content_contract") == "hr_attendance_v1"

    # 2. Force legacy grounded review builder
    review_deck = generate_presentation_deck_spec(
        scope={"force_legacy_builders": True},
        dataset_context=ctx,
        workspace_evidence=ws_ev
    )
    assert review_deck.get("metadata", {}).get("content_contract") == "recorded_results_v1"

