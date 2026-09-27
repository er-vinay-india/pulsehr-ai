"""Presentation Memory, Semantic Retrieval & Context Intelligence (Phase 1)."""

from .memory_models import (
    MemoryType,
    EvidenceStatus,
    MemoryRecord,
    SearchResult,
    SimilarPresentationResult,
    RetrievalContext,
)
from .embedding_service import NomicEmbeddingService, embedding_service
from .memory_store import PresentationMemoryStore, memory_store
from .memory_indexer import PresentationMemoryIndexer, memory_indexer
from .retrieval_service import PresentationRetrievalService, presentation_retrieval_service
from .memory_provenance import (
    build_deck_provenance,
    build_slide_provenance,
    build_dataset_provenance,
    format_provenance_citation,
)

__all__ = [
    "MemoryType",
    "EvidenceStatus",
    "MemoryRecord",
    "SearchResult",
    "SimilarPresentationResult",
    "RetrievalContext",
    "NomicEmbeddingService",
    "embedding_service",
    "PresentationMemoryStore",
    "memory_store",
    "PresentationMemoryIndexer",
    "memory_indexer",
    "PresentationRetrievalService",
    "presentation_retrieval_service",
    "build_deck_provenance",
    "build_slide_provenance",
    "build_dataset_provenance",
    "format_provenance_citation",
]
