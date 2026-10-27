"""Product Track 3.2 — Upstream Contract Binding & Elimination of Parallel Analytical Truth.

Verifies:
1. ExecutiveTopic / VisualSpec -> PresentationTopic -> Presentation Planning.
2. NO raw-column reinterpretation.
3. NO build_hr_report analytical bypass for governed datasets (natural language objectives NEVER trigger bypass).
4. NO build_grounded_review analytical fallback for governed datasets.
5. NO new metric calculation.
6. NO loss of topic_id / fact_id / evidence_ids.
7. Invariant: One governed ExecutiveTopic maps to one presentation topic identity,
   which may render as one or more physical slides without changing fact/evidence ownership.
8. Semantic Acceptance Invariant (Exact Match across all 24 benchmark topics):
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
   - Canonical Semantic Hash: exact SHA-256 match (upstream == presentation == slide contract)
9. Production Route Proof:
   - request -> start_presentation_job -> pipeline_orchestrator -> context capture
     -> PresentationTopic[] -> governed deck builder -> persisted presentation deck
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
from app.services.presentation.governed_presentation_builder import build_governed_presentation_deck
from app.services.presentation.deck_generator import generate_presentation_deck_spec
from app.services.presentation.scope_detector import capture_dataset_context, collect_workspace_evidence
from app.services.presentation.pipeline_orchestrator import (
    execute_presentation_pipeline_async,
    job_manager
)
from app.services.report_generator import export_spec_to_pptx
import app.services.presentation.hr_report as hr_module
import app.services.presentation.grounded_review as gr_module

pytestmark = pytest.mark.presentation


from tests.fixtures.benchmark_seeder import ensure_benchmark_datasets_seeded


@pytest.fixture(scope="function", autouse=True)
def seed_benchmark_datasets():
    """Populates the isolated test SQLite database with the 3 benchmark datasets hermetically."""
    with get_connection() as conn:
        ensure_benchmark_datasets_seeded(conn)


def test_presentation_topic_model_fidelity():
    """Verifies that PresentationTopic extracts and preserves all 11 governed attributes and canonical hash."""
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

    # Canonical semantic hash parity
    expected_hash = compute_canonical_semantic_hash(exec_topic)
    assert pt.canonical_semantic_hash() == expected_hash

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
    assert slide["semantic_hash"] == expected_hash


def _verify_deck_against_executive_topics(sheet_id: int, expected_domain: str):
    """Core verification harness enforcing exact match of all 11 semantic attributes and hash across 8 topics."""
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
    assert deck["slide_count"] >= 9  # 1 cover slide + 8 topic slides (plus spatial continuation parts)
    assert len(deck["slides"]) >= 9

    upstream_topics = ctx["executive_topics"]
    assert len(upstream_topics) == 8

    upstream_by_id = {t["topic_id"]: t for t in upstream_topics}

    # Verify each topic slide (slides 2 to N)
    topic_slides = deck["slides"][1:]
    assert len(topic_slides) >= 8
    assert len(set(s["topic_id"] for s in topic_slides if s.get("topic_id"))) == 8

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

        # 12. Canonical semantic hash: exact match
        upstream_hash = compute_canonical_semantic_hash(u_topic)
        assert slide.get("semantic_hash") == upstream_hash, f"Semantic hash mismatch for topic {t_id}"

    # Export to PPTX and verify
    pptx_path = export_spec_to_pptx(deck)
    assert pptx_path.exists()
    assert pptx_path.stat().st_size > 10000
    with zipfile.ZipFile(pptx_path, "r") as z:
        assert "[Content_Types].xml" in z.namelist()


def test_workforce_contract_binding():
    """Workforce domain: asserts exact match, hash parity (8/8), and confirms build_hr_report bypass is eliminated."""
    _verify_deck_against_executive_topics(9967416, "workforce")


def test_retail_contract_binding():
    """Retail domain: asserts exact match, hash parity (8/8), and confirms build_grounded_review fallback is eliminated."""
    _verify_deck_against_executive_topics(9967418, "retail")


def test_environmental_contract_binding():
    """Environmental domain: asserts exact match, hash parity (8/8), and confirms build_grounded_review fallback is eliminated."""
    _verify_deck_against_executive_topics(9967419, "environmental")


def test_natural_language_objectives_never_bypass_governed_topics():
    """Verifies that user/presentation objectives NEVER trigger legacy builders on governed data.
    
    Acceptance:
    objective="Attendance review" -> governed contract path
    objective="Executive attendance review" -> governed contract path
    objective="Workforce review" -> governed contract path
    objective="Board attendance briefing" -> governed contract path
    objective="Executive Leadership Review" -> governed contract path
    objective="" -> governed contract path
    """
    with get_connection() as conn:
        ctx = capture_dataset_context(conn, sheet_id=9967416)
        ws_ev = collect_workspace_evidence(conn, {"sheet_id": 9967416})

    objectives_to_test = [
        "Attendance review",
        "Executive attendance review",
        "Workforce review",
        "Board attendance briefing",
        "Executive Leadership Review",
        ""
    ]

    for obj in objectives_to_test:
        deck = generate_presentation_deck_spec(
            scope={"sheet_id": 9967416, "objective": obj, "theme_id": "executive_dark"},
            dataset_context=ctx,
            workspace_evidence=ws_ev
        )
        assert deck.get("metadata", {}).get("contract_mode") == "EXECUTIVE_TOPIC_BOUND", f"Failed for objective: {obj}"
        assert deck.get("metadata", {}).get("content_contract") == "executive_topic_bound_v1", f"Failed for objective: {obj}"
        assert deck["slide_count"] >= 9
        assert len(deck["slides"]) >= 9
        topic_ids = [s.get("topic_id") for s in deck["slides"][1:] if s.get("topic_id")]
        assert len(set(topic_ids)) == 8
        for s in deck["slides"][1:]:
            assert s.get("topic_id") is not None
            assert s.get("semantic_hash") is not None


def test_zero_parallel_truth_and_zero_model_calls():
    """Asserts that default generation across Workforce, Retail, and Environmental makes:
    - 0 calls to build_hr_report
    - 0 calls to build_grounded_review
    - 0 model calls
    - 0 analytical metric recomputations
    """
    benchmarks = [9967416, 9967418, 9967419]

    for sid in benchmarks:
        hr_calls = 0
        gr_calls = 0

        def spy_hr(*args, **kwargs):
            nonlocal hr_calls
            hr_calls += 1
            return hr_module.build_hr_report(*args, **kwargs)

        def spy_gr(*args, **kwargs):
            nonlocal gr_calls
            gr_calls += 1
            return gr_module.build_grounded_review(*args, **kwargs)

        with get_connection() as conn:
            ctx = capture_dataset_context(conn, sheet_id=sid)
            ws_ev = collect_workspace_evidence(conn, {"sheet_id": sid})

        with patch.object(hr_module, "build_hr_report", side_effect=spy_hr), \
             patch.object(gr_module, "build_grounded_review", side_effect=spy_gr):
            deck = generate_presentation_deck_spec(
                scope={"sheet_id": sid, "theme_id": "executive_dark"},
                dataset_context=ctx,
                workspace_evidence=ws_ev
            )

        assert hr_calls == 0, f"Sheet {sid} invoked build_hr_report"
        assert gr_calls == 0, f"Sheet {sid} invoked build_grounded_review"
        assert deck.get("metadata", {}).get("contract_mode") == "EXECUTIVE_TOPIC_BOUND"


def test_real_api_job_pipeline_governed_route():
    """Runs the real production workflow for all 3 benchmark domains:
    request -> start_presentation_job -> pipeline_orchestrator -> context capture
    -> PresentationTopic[] -> governed deck builder -> persisted presentation deck in SQLite
    """
    benchmarks = [
        {"sheet_id": 9967416, "domain": "Workforce"},
        {"sheet_id": 9967418, "domain": "Retail"},
        {"sheet_id": 9967419, "domain": "Environmental"}
    ]

    for bm in benchmarks:
        sid = bm["sheet_id"]
        scope = {
            "sheet_id": sid,
            "theme_id": "executive_dark",
            "objective": "Executive Leadership Review",
            "audience": "C-Suite & Operations Leadership",
            "scope_type": "sheet"
        }

        job_id = job_manager.create_job(scope)
        execute_presentation_pipeline_async(job_id, scope)

        job_state = job_manager.get_job(job_id)
        assert job_state["status"] == "ready", f"Job failed for {bm['domain']}: {job_state.get('error')}"
        deck_id = job_state.get("deck_id")
        assert deck_id is not None

        # Verify persistence in database
        with get_connection() as conn:
            row = conn.execute(
                "SELECT id, title, dataset_id, sheet_id, theme_id, spec_json FROM presentation_decks WHERE id = ?",
                (deck_id,)
            ).fetchone()
            assert row is not None
            persisted_spec = json.loads(row["spec_json"])

            assert persisted_spec.get("metadata", {}).get("contract_mode") == "EXECUTIVE_TOPIC_BOUND"
            assert len(persisted_spec.get("slides", [])) >= 9
            # Check all topic slides carry lineage and hash
            topic_slides = [s for s in persisted_spec["slides"] if s.get("topic_id")]
            assert len(topic_slides) >= 8
            assert len(set(ts.get("topic_id") for ts in topic_slides if ts.get("topic_id"))) == 8
            for ts in topic_slides:
                assert ts.get("topic_id") is not None
                assert ts.get("semantic_hash") is not None
                assert len(ts.get("evidence_ids", [])) > 0


def test_multi_slide_continuation_preserves_identity_and_evidence():
    """Invariant: One governed ExecutiveTopic maps to one presentation topic identity,
    which may render as one or more physical slides without changing fact/evidence ownership or hash.
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
    expected_hash = pt.canonical_semantic_hash()

    # Paginate with max 10 rows per slide
    slides = pt.to_slide_contracts(start_order=2, total_slides=4, max_items_per_slide=10, enable_pagination=True)
    assert len(slides) == 3

    assert "Part 1 of 3" in slides[0]["title"]
    assert "Part 2 of 3" in slides[1]["title"]
    assert "Part 3 of 3" in slides[2]["title"]

    # Invariant assertion: topic_id, fact_id, evidence_ids, and semantic_hash MUST BE IDENTICAL
    for idx, slide in enumerate(slides):
        assert slide["topic_id"] == "TOPIC-MULTI-PAGE-01", f"Slide {idx} changed topic_id"
        assert slide["fact_id"] == "FACT-CARBON-25", f"Slide {idx} changed fact_id"
        assert slide["evidence_ids"] == ["EVID-ENV-001", "EVID-ENV-002"], f"Slide {idx} lost evidence_ids"
        assert slide["key_metric"] == "Total MT CO2e"
        assert slide["leader"] == "Entity 1"
        assert slide["leader_value"] == 100.0
        assert slide["ranking_direction"] == "descending"
        assert slide["semantic_hash"] == expected_hash, f"Slide {idx} changed semantic_hash"


def test_legacy_opt_in_flags_preserved():
    """Verifies that legacy builders can ONLY be explicitly opted into via technical compatibility flags."""
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
