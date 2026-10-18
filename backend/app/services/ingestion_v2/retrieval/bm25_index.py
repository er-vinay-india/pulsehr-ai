"""
HighView Ingestion V2 — Phase I7 BM25 Lexical Index
Stage 11: Multi-Namespace Hybrid Retrieval

Core Invariants:
1. Lexical retrieval preserves namespace filters.
2. Supports exact metric names, aliases, column names, business terminology, and IDs.
3. Deterministic scoring with stable tie-breaking by (score desc, document_id asc).
4. Zero mutation of live production search state.
"""

import re
from typing import Sequence
from rank_bm25 import BM25Plus
from pydantic import BaseModel, ConfigDict

from app.services.ingestion_v2.retrieval.namespaces import RetrievalNamespace
from app.services.ingestion_v2.retrieval.documents import RetrievalDocument

STOP_WORDS = {
    "a", "an", "the", "is", "are", "was", "were", "what", "how", "many", "much",
    "who", "which", "in", "on", "of", "for", "to", "and", "or", "me", "tell", "about",
    "please", "give", "show", "can", "does", "do", "find"
}


def tokenize(text: str) -> list[str]:
    """
    Normalizes and tokenizes text for lexical retrieval.
    Preserves tokens with underscores, dashes, numbers, units, and identifiers.
    """
    clean_text = text.casefold()
    tokens = re.findall(r"\b[a-z0-9]+(?:[_-][a-z0-9]+)*\b", clean_text)
    return [t for t in tokens if t not in STOP_WORDS and len(t) > 0]


class LexicalSearchResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    document: RetrievalDocument
    score: float
    rank: int


class MultiNamespaceBM25Index:
    """
    Namespace-partitioned BM25 index over RetrievalDocument collections.
    """

    def __init__(self, documents: Sequence[RetrievalDocument], index_version: str = "v1"):
        self.index_version = index_version
        self._documents = list(documents)
        self._doc_by_id = {d.document_id: d for d in self._documents}

        # Partition documents by namespace
        self._ns_docs: dict[RetrievalNamespace, list[RetrievalDocument]] = {}
        self._ns_corpus: dict[RetrievalNamespace, list[list[str]]] = {}
        self._ns_bm25: dict[RetrievalNamespace, BM25Plus | None] = {}

        for ns in RetrievalNamespace:
            docs = [d for d in self._documents if d.namespace == ns]
            self._ns_docs[ns] = docs
            corpus = [tokenize(d.text_for_retrieval) for d in docs]
            self._ns_corpus[ns] = corpus
            if corpus and any(len(c) > 0 for c in corpus):
                self._ns_bm25[ns] = BM25Plus(corpus)
            else:
                self._ns_bm25[ns] = None

    @property
    def total_documents(self) -> int:
        return len(self._documents)

    def search(
        self,
        query: str,
        namespaces: Sequence[RetrievalNamespace] | None = None,
        top_k: int = 10,
    ) -> list[LexicalSearchResult]:
        """
        Executes BM25 search across requested namespaces (or all if None).
        Returns candidates ranked by score desc, with deterministic tie-breaking.
        """
        tokens = tokenize(query)
        if not tokens or top_k <= 0:
            return []

        target_namespaces = list(namespaces) if namespaces else list(RetrievalNamespace)
        raw_candidates: list[tuple[RetrievalDocument, float]] = []

        query_anchors = set(tokens)

        for ns in target_namespaces:
            bm25 = self._ns_bm25.get(ns)
            docs = self._ns_docs.get(ns, [])
            corpus = self._ns_corpus.get(ns, [])
            if not bm25 or not docs:
                continue

            scores = bm25.get_scores(tokens)

            for idx, doc in enumerate(docs):
                doc_tokens = corpus[idx]
                # Require actual token overlap to avoid BM25Plus nonzero baseline artifact
                if not query_anchors.intersection(doc_tokens):
                    continue

                score = float(scores[idx])
                if score > 0.0:
                    raw_candidates.append((doc, score))

        # Deterministic sort: score desc, document_id asc
        raw_candidates.sort(key=lambda item: (-item[1], item[0].document_id))

        results: list[LexicalSearchResult] = []
        for rank_idx, (doc, score) in enumerate(raw_candidates[:top_k], start=1):
            results.append(
                LexicalSearchResult(
                    document=doc,
                    score=round(score, 4),
                    rank=rank_idx,
                )
            )

        return results
