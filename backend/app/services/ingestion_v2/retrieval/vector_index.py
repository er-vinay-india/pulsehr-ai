"""
HighView Ingestion V2 — Phase I7 Vector Index & Embedding Telemetry
Stage 11: Multi-Namespace Hybrid Retrieval

Core Invariants:
1. RETRIEVAL FINDS CANDIDATES. RETRIEVAL DOES NOT ESTABLISH TRUTH.
2. Two columns with high vector similarity must NEVER create a relationship.
3. Explicit separation of LLM calls (0) vs embedding calls.
4. Deterministic content-fingerprint caching prevents redundant embeddings.
5. Offline / unavailable graceful degradation: falls back to BM25 + graph.
"""

import math
from typing import Callable, Sequence
from pydantic import BaseModel, ConfigDict, Field

from app.services.ingestion_v2.retrieval.namespaces import RetrievalNamespace
from app.services.ingestion_v2.retrieval.documents import RetrievalDocument


def cosine_similarity(v1: Sequence[float], v2: Sequence[float]) -> float:
    """Computes cosine similarity between two numeric vectors."""
    if len(v1) != len(v2) or not v1:
        return 0.0
    dot = sum(a * b for a, b in zip(v1, v2))
    norm1 = math.sqrt(sum(a * a for a, b in zip(v1, v1)))
    norm2 = math.sqrt(sum(b * b for a, b in zip(v2, v2)))
    if norm1 == 0.0 or norm2 == 0.0:
        return 0.0
    return dot / (norm1 * norm2)


class VectorSearchResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    document: RetrievalDocument
    similarity: float
    rank: int


class VectorIndexStatus(str):
    AVAILABLE = "AVAILABLE"
    UNAVAILABLE = "VECTOR_INDEX_UNAVAILABLE"
    EMPTY = "EMPTY"


class MultiNamespaceVectorIndex:
    """
    Namespace-partitioned vector index with embedding cache and explicit telemetry.
    """

    def __init__(
        self,
        embedding_model: str = "nomic-embed-text:latest",
        embedding_dim: int = 768,
        embedding_provider: Callable[[list[str]], list[list[float]]] | None = None,
        index_version: str = "v1",
    ):
        self.embedding_model = embedding_model
        self.embedding_dim = embedding_dim
        self.index_version = index_version
        self._provider = embedding_provider

        # Storage
        self._documents: list[RetrievalDocument] = []
        self._doc_by_id: dict[str, RetrievalDocument] = {}
        self._vectors: dict[str, list[float]] = {}  # doc_id -> vector

        # Global Embedding Cache: key = content_fingerprint:model:index_version
        self._embedding_cache: dict[str, list[float]] = {}

        # Explicit Telemetry
        self.llm_calls: int = 0
        self.embedding_document_calls: int = 0
        self.embedding_query_calls: int = 0
        self.embedding_cache_hits: int = 0
        self.status: str = VectorIndexStatus.EMPTY

    def _get_cache_key(self, content_fingerprint: str) -> str:
        return f"{content_fingerprint}:{self.embedding_model}:{self.index_version}"

    def build_index(self, documents: Sequence[RetrievalDocument]) -> str:
        """
        Indexes documents by computing or retrieving embeddings from cache.
        Degrades gracefully if embedding provider is unavailable.
        """
        self._documents = list(documents)
        self._doc_by_id = {d.document_id: d for d in self._documents}
        self._vectors.clear()

        if not self._documents:
            self.status = VectorIndexStatus.EMPTY
            return self.status

        # If no provider given, attempt to use system sheet_catalog.model_embeddings
        provider = self._provider
        if provider is None:
            try:
                from app.services.sheet_catalog import model_embeddings
                provider = model_embeddings
            except Exception:
                provider = None

        if provider is None:
            self.status = VectorIndexStatus.UNAVAILABLE
            return self.status

        # Identify documents needing embedding vs cached
        docs_to_embed: list[RetrievalDocument] = []
        texts_to_embed: list[str] = []

        for doc in self._documents:
            c_key = self._get_cache_key(doc.content_fingerprint)
            if c_key in self._embedding_cache:
                self._vectors[doc.document_id] = self._embedding_cache[c_key]
                self.embedding_cache_hits += 1
            else:
                docs_to_embed.append(doc)
                texts_to_embed.append(doc.text_for_retrieval)

        if texts_to_embed:
            try:
                computed_vectors = provider(texts_to_embed)
                if not computed_vectors or len(computed_vectors) != len(texts_to_embed):
                    # Provider returned empty (offline) or mismatched
                    if not self._vectors:
                        self.status = VectorIndexStatus.UNAVAILABLE
                        return self.status
                else:
                    self.embedding_document_calls += len(texts_to_embed)
                    for doc, vec in zip(docs_to_embed, computed_vectors):
                        self._vectors[doc.document_id] = vec
                        c_key = self._get_cache_key(doc.content_fingerprint)
                        self._embedding_cache[c_key] = vec
            except Exception:
                if not self._vectors:
                    self.status = VectorIndexStatus.UNAVAILABLE
                    return self.status

        self.status = VectorIndexStatus.AVAILABLE if self._vectors else VectorIndexStatus.UNAVAILABLE
        return self.status

    def search(
        self,
        query: str,
        namespaces: Sequence[RetrievalNamespace] | None = None,
        top_k: int = 10,
    ) -> list[VectorSearchResult]:
        """
        Performs vector similarity search across requested namespaces.
        Returns empty list gracefully if index is unavailable or empty.
        """
        if self.status != VectorIndexStatus.AVAILABLE or not self._vectors or top_k <= 0:
            return []

        # Get query embedding
        provider = self._provider
        if provider is None:
            try:
                from app.services.sheet_catalog import model_embeddings
                provider = model_embeddings
            except Exception:
                provider = None

        if provider is None:
            return []

        try:
            q_vecs = provider([query])
            if not q_vecs or len(q_vecs) != 1:
                return []
            query_vector = q_vecs[0]
            self.embedding_query_calls += 1
        except Exception:
            return []

        target_namespaces = set(namespaces) if namespaces else set(RetrievalNamespace)
        candidates: list[tuple[RetrievalDocument, float]] = []

        for doc_id, doc_vector in self._vectors.items():
            doc = self._doc_by_id.get(doc_id)
            if not doc or doc.namespace not in target_namespaces:
                continue

            sim = cosine_similarity(query_vector, doc_vector)
            candidates.append((doc, sim))

        # Deterministic sort: similarity desc, document_id asc
        candidates.sort(key=lambda item: (-item[1], item[0].document_id))

        results: list[VectorSearchResult] = []
        for rank_idx, (doc, sim) in enumerate(candidates[:top_k], start=1):
            results.append(
                VectorSearchResult(
                    document=doc,
                    similarity=round(sim, 4),
                    rank=rank_idx,
                )
            )

        return results
