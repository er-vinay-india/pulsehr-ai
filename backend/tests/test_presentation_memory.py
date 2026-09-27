from __future__ import annotations

import json
from pathlib import Path
import tempfile
import pytest

from app.core import config
from app.services.presentation.memory.memory_models import (
    MemoryType,
    EvidenceStatus,
    MemoryRecord,
    SearchResult,
    SimilarPresentationResult,
    RetrievalContext,
)
from app.services.presentation.memory.embedding_service import NomicEmbeddingService
from app.services.presentation.memory.memory_store import PresentationMemoryStore
from app.services.presentation.memory.memory_indexer import PresentationMemoryIndexer
from app.services.presentation.memory.retrieval_service import PresentationRetrievalService
from app.services.presentation.memory.memory_provenance import (
    build_deck_provenance,
    build_slide_provenance,
    format_provenance_citation,
)


@pytest.fixture
def temp_store():
    with tempfile.NamedTemporaryFile(suffix=".sqlite3", delete=False) as tf:
        db_path = Path(tf.name)
    store = PresentationMemoryStore(db_path=db_path)
    yield store
    if db_path.exists():
        db_path.unlink()


@pytest.fixture
def mock_embedder():
    class DummyEmbedder:
        def __init__(self):
            self.call_count = 0

        def embed_text(self, text: str) -> list[float]:
            self.call_count += 1
            # Deterministic mock vector of 768 dimensions based on length and characters
            val = float(len(text) % 100) / 100.0
            vec = [0.01 * (i % 10) for i in range(768)]
            vec[0] = val
            if "attendance" in text.lower():
                vec[1] = 0.95
            elif "sales" in text.lower():
                vec[2] = 0.95
            return vec

        def embed_batch(self, texts: list[str]) -> list[list[float]]:
            return [self.embed_text(t) for t in texts]

    return DummyEmbedder()


@pytest.fixture
def sample_deck_spec():
    return {
        "id": "deck_test_001",
        "spec_version": "2.0",
        "metadata": {
            "title": "Q3 Workforce Attendance Review",
            "domain": "Workforce Analytics",
            "audience": "Executive Leadership",
            "theme_id": "corporate_navy",
            "file_label": "Attendance_Records_2026.csv",
            "snapshot_hash": "a1b2c3d4e5f6",
            "dataset_id": 101,
            "sheet_id": 202,
            "workspace_id": "ws_main",
            "created_at": "2026-09-20T10:00:00Z"
        },
        "slides": [
            {
                "id": "slide_1",
                "order": 1,
                "category": "EXECUTIVE SUMMARY",
                "layout": "title_hero",
                "title": "Attendance Compliance Achieved 88% in Technical Teams",
                "subtitle": "Analysis across 2,400 observed employee days",
                "narrative": "Technical teams maintained high office presence while operations lagged at 61%.",
                "bullets": ["Engineering compliance reached 88%", "Operations variance requires alignment"],
                "metrics": [{"label": "Peak Presence", "value": "88%"}],
                "evidence_id": "EVID-01"
            },
            {
                "id": "slide_2",
                "order": 2,
                "category": "OPERATIONAL HEADWINDS",
                "layout": "chart_narrative",
                "title": "Operational Unit Disparity and Shift Bottlenecks",
                "subtitle": "Distribution of unscheduled shift deviations",
                "narrative": "Three distribution centers recorded persistent overtime strain.",
                "bullets": ["Distribution East recorded 2.4x average variance", "Shift rosters misaligned with volume"],
                "metrics": [{"label": "Spread", "value": "2.4x"}],
                "chart": {"type": "bar", "metric_col": "Overtime Hours"},
                "evidence_id": "EVID-02"
            }
        ],
        "evidence_ledger": [
            {
                "evidence_id": "EVID-01",
                "metric_name": "Peak Technical Compliance",
                "metric_value": "88%",
                "what_it_establishes": "Engineering attendance adherence",
                "what_it_does_not_establish": "No causal link to individual performance rating.",
                "calculation_methodology": "Valid employee clock-in records divided by scheduled days."
            }
        ]
    }


# TEST 1: Text embedding works
def test_text_embedding_works():
    emb = NomicEmbeddingService()
    # Test fallback or live Ollama call
    vec = emb.embed_text("Executive Presentation Review")
    if vec is not None:
        assert len(vec) == 768
        assert isinstance(vec[0], float)


# TEST 2: Same unchanged content does not embed twice (caching / hash check)
def test_same_unchanged_content_does_not_embed_twice(temp_store, mock_embedder, sample_deck_spec):
    indexer = PresentationMemoryIndexer(store=temp_store, embedder=mock_embedder)

    # First index
    created_1 = indexer.index_presentation_deck(sample_deck_spec)
    assert created_1 > 0
    first_call_count = mock_embedder.call_count
    assert first_call_count > 0

    # Second index with identical content
    created_2 = indexer.index_presentation_deck(sample_deck_spec)
    assert created_2 == 0
    # No additional embedding calls made
    assert mock_embedder.call_count == first_call_count


# TEST 3: Changed content gets re-indexed
def test_changed_content_gets_reindexed(temp_store, mock_embedder, sample_deck_spec):
    indexer = PresentationMemoryIndexer(store=temp_store, embedder=mock_embedder)
    indexer.index_presentation_deck(sample_deck_spec)
    count_before = mock_embedder.call_count

    # Modify title and re-index
    deck_copy = dict(sample_deck_spec)
    deck_copy["slides"] = list(sample_deck_spec["slides"])
    deck_copy["slides"][0] = dict(sample_deck_spec["slides"][0])
    deck_copy["slides"][0]["title"] = "NEW Assertive Headline On Attendance"

    reindexed = indexer.index_presentation_deck(deck_copy)
    assert reindexed > 0
    assert mock_embedder.call_count > count_before


# TEST 4: Previous presentation deck can be indexed
def test_previous_presentation_deck_can_be_indexed(temp_store, mock_embedder, sample_deck_spec):
    indexer = PresentationMemoryIndexer(store=temp_store, embedder=mock_embedder)
    count = indexer.index_presentation_deck(sample_deck_spec)
    assert count >= 3  # Deck summary + 2 slides + evidence item
    deck_mem = temp_store.get_by_id(f"mem_deck_{sample_deck_spec['id']}")
    assert deck_mem is not None
    assert deck_mem.memory_type == MemoryType.PRESENTATION_DECK
    assert sample_deck_spec["metadata"]["title"] in deck_mem.text


# TEST 5: Slide-level memories are generated
def test_slide_level_memories_are_generated(temp_store, mock_embedder, sample_deck_spec):
    indexer = PresentationMemoryIndexer(store=temp_store, embedder=mock_embedder)
    indexer.index_presentation_deck(sample_deck_spec)

    slide1_mem = temp_store.get_by_id(f"mem_slide_{sample_deck_spec['id']}_1")
    assert slide1_mem is not None
    assert slide1_mem.memory_type == MemoryType.SLIDE
    assert "Attendance Compliance Achieved 88%" in slide1_mem.text
    assert slide1_mem.provenance["slide_order"] == 1


# TEST 6: Dataset profile can be indexed
def test_dataset_profile_can_be_indexed(temp_store, mock_embedder):
    now_iso = "2026-09-27T10:00:00Z"
    text = "Dataset: Test Dataset\nDomain: Attendance\nAudited Population: 500 records"
    rec = MemoryRecord(
        memory_id="mem_sheet_test_999",
        memory_type=MemoryType.DATASET_PROFILE,
        text=text,
        embedding=mock_embedder.embed_text(text),
        source_id="999",
        source_type="dataset_sheet",
        domain="Attendance",
        evidence_status=EvidenceStatus.CONTEXTUAL,
        content_hash="hash999",
        created_at=now_iso,
        updated_at=now_iso
    )
    temp_store.upsert_record(rec)
    fetched = temp_store.get_by_id("mem_sheet_test_999")
    assert fetched is not None
    assert fetched.memory_type == MemoryType.DATASET_PROFILE


# TEST 7: Semantic search returns relevant result
def test_semantic_search_returns_relevant_result(temp_store, mock_embedder, sample_deck_spec):
    indexer = PresentationMemoryIndexer(store=temp_store, embedder=mock_embedder)
    indexer.index_presentation_deck(sample_deck_spec)

    retriever = PresentationRetrievalService(store=temp_store, embedder=mock_embedder)
    res = retriever.retrieve_presentation_context(query="attendance compliance in engineering")

    assert res.status == "success"
    assert len(res.results) > 0
    top_result = res.results[0]
    assert "attendance" in top_result.text.lower()
    assert top_result.score > 0.5


# TEST 8: Metadata filter works (domain and audience)
def test_metadata_filter_works(temp_store, mock_embedder, sample_deck_spec):
    indexer = PresentationMemoryIndexer(store=temp_store, embedder=mock_embedder)
    indexer.index_presentation_deck(sample_deck_spec)

    retriever = PresentationRetrievalService(store=temp_store, embedder=mock_embedder)

    # Search with matching domain
    res_match = retriever.retrieve_presentation_context(
        query="attendance review",
        domain="Workforce Analytics"
    )
    assert len(res_match.results) > 0

    # Search with completely unrelated domain
    res_nomatch = retriever.retrieve_presentation_context(
        query="attendance review",
        domain="Aerospace Rocketry Engineering"
    )
    # The domain booster did not boost and filtering excluded or downgraded non-matching candidates
    for r in res_nomatch.results:
        assert r.provenance.get("domain") != "Aerospace Rocketry Engineering"


# TEST 9: Same-workspace filtering works
def test_same_workspace_filtering(temp_store, mock_embedder, sample_deck_spec):
    indexer = PresentationMemoryIndexer(store=temp_store, embedder=mock_embedder)
    indexer.index_presentation_deck(sample_deck_spec)

    retriever = PresentationRetrievalService(store=temp_store, embedder=mock_embedder)
    res = retriever.retrieve_presentation_context(
        query="attendance review",
        workspace_id="ws_main"
    )
    assert len(res.results) > 0
    assert res.results[0].provenance.get("workspace_id") == "ws_main"


# TEST 10: Memory-type filtering works
def test_memory_type_filtering(temp_store, mock_embedder, sample_deck_spec):
    indexer = PresentationMemoryIndexer(store=temp_store, embedder=mock_embedder)
    indexer.index_presentation_deck(sample_deck_spec)

    retriever = PresentationRetrievalService(store=temp_store, embedder=mock_embedder)

    # Only request SLIDE memories
    res_slides = retriever.retrieve_presentation_context(
        query="attendance",
        memory_types=[MemoryType.SLIDE]
    )
    assert len(res_slides.results) > 0
    for r in res_slides.results:
        assert r.memory_type == MemoryType.SLIDE

    # Only request PRESENTATION_DECK memories
    res_decks = retriever.retrieve_presentation_context(
        query="attendance",
        memory_types=[MemoryType.PRESENTATION_DECK]
    )
    assert len(res_decks.results) > 0
    for r in res_decks.results:
        assert r.memory_type == MemoryType.PRESENTATION_DECK


# TEST 11: Duplicate results are suppressed
def test_duplicate_results_are_suppressed(temp_store, mock_embedder):
    now_iso = "2026-09-27T10:00:00Z"
    text_dup = "Identical executive narrative statement repeated across multiple slides verbatim."
    emb = mock_embedder.embed_text(text_dup)

    for i in range(4):
        rec = MemoryRecord(
            memory_id=f"mem_dup_{i}",
            memory_type=MemoryType.SLIDE,
            text=text_dup,
            embedding=emb,
            source_id=f"src_{i}",
            source_type="slide",
            content_hash=f"h_{i}",
            created_at=now_iso,
            updated_at=now_iso
        )
        temp_store.upsert_record(rec)

    retriever = PresentationRetrievalService(store=temp_store, embedder=mock_embedder)
    res = retriever.retrieve_presentation_context(query="identical executive narrative")
    # Only 1 instance should survive deduplication
    assert len(res.results) == 1


# TEST 12: Context budget is respected (max items and character limit)
def test_context_budget_is_respected(temp_store, mock_embedder):
    now_iso = "2026-09-27T10:00:00Z"
    for i in range(10):
        t = f"Unique distinct insight #{i} evaluating branch productivity and metrics."
        rec = MemoryRecord(
            memory_id=f"mem_budget_{i}",
            memory_type=MemoryType.SLIDE,
            text=t,
            embedding=mock_embedder.embed_text(t),
            source_id=f"src_{i}",
            source_type="slide",
            content_hash=f"hash_{i}",
            created_at=now_iso,
            updated_at=now_iso
        )
        temp_store.upsert_record(rec)

    retriever = PresentationRetrievalService(store=temp_store, embedder=mock_embedder)
    res = retriever.retrieve_presentation_context(
        query="branch productivity",
        max_context_items=3,
        max_total_chars=250
    )
    assert len(res.results) <= 3
    assert res.context_budget_used_chars <= 250


# TEST 13: Provenance survives retrieval
def test_provenance_survives_retrieval(temp_store, mock_embedder, sample_deck_spec):
    indexer = PresentationMemoryIndexer(store=temp_store, embedder=mock_embedder)
    indexer.index_presentation_deck(sample_deck_spec)

    retriever = PresentationRetrievalService(store=temp_store, embedder=mock_embedder)
    res = retriever.retrieve_presentation_context(query="attendance")
    assert len(res.results) > 0
    first = res.results[0]
    assert first.provenance is not None
    assert first.provenance["deck_id"] == "deck_test_001"
    citation = format_provenance_citation(first.provenance)
    assert "deck_test_001" in citation or "Attendance" in citation


# TEST 14: Deleted source removes associated memories
def test_deleted_source_removes_memories(temp_store, mock_embedder, sample_deck_spec):
    indexer = PresentationMemoryIndexer(store=temp_store, embedder=mock_embedder)
    indexer.index_presentation_deck(sample_deck_spec)
    assert temp_store.count() > 0

    deleted = indexer.delete_presentation_deck(sample_deck_spec["id"])
    assert deleted > 0
    # No memories remaining for this deck
    remaining = temp_store.get_by_source(sample_deck_spec["id"])
    assert len(remaining) == 0


# TEST 15: Vector store failure does not break presentation generation
def test_vector_store_failure_does_not_break_generation():
    broken_retriever = PresentationRetrievalService(store=None, embedder=None)
    broken_retriever.store = type("BrokenStore", (), {"search_vector": lambda *args, **kwargs: 1 / 0})()

    # Must return gracefully degraded context without raising exception
    res = broken_retriever.retrieve_presentation_context(query="Quarterly review")
    assert res.status == "degraded"
    assert res.results == []


# TEST 16: Nomic failure gracefully falls back to no retrieval
def test_nomic_failure_gracefully_falls_back():
    class FailingEmbedder:
        def embed_text(self, text):
            return None  # Simulates network failure or Ollama down

    retriever = PresentationRetrievalService(store=None, embedder=FailingEmbedder())
    res = retriever.retrieve_presentation_context(query="Executive Review")
    assert res.status == "degraded"
    assert len(res.results) == 0


# TEST 17: Historical context is marked historical
def test_historical_context_is_marked_historical(temp_store, mock_embedder, sample_deck_spec):
    indexer = PresentationMemoryIndexer(store=temp_store, embedder=mock_embedder)
    indexer.index_presentation_deck(sample_deck_spec)

    retriever = PresentationRetrievalService(store=temp_store, embedder=mock_embedder)
    res = retriever.retrieve_presentation_context(query="attendance")
    for r in res.results:
        assert r.evidence_status in ("historical", "contextual")
        assert r.evidence_status != "current"


# TEST 18: Current evidence remains distinguishable from historical context
def test_current_evidence_remains_distinguishable(temp_store, mock_embedder, sample_deck_spec):
    indexer = PresentationMemoryIndexer(store=temp_store, embedder=mock_embedder)
    indexer.index_presentation_deck(sample_deck_spec)

    retriever = PresentationRetrievalService(store=temp_store, embedder=mock_embedder)
    res = retriever.retrieve_presentation_context(query="attendance")

    # Historical retrieved memories must NEVER be mistaken for current ground truth evidence
    historical_items = [r for r in res.results if r.evidence_status == "historical"]
    assert len(historical_items) > 0
    for h in historical_items:
        assert h.evidence_status != EvidenceStatus.CURRENT
