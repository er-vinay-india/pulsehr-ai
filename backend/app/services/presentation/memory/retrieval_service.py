from __future__ import annotations

import datetime
import logging
import re
from typing import Any, Sequence

from ....core import config
from .memory_models import (
    MemoryType,
    SearchResult,
    SimilarPresentationResult,
    RetrievalContext,
    EvidenceStatus,
)
from .embedding_service import embedding_service
from .memory_store import memory_store

logger = logging.getLogger(__name__)


class PresentationRetrievalService:
    """Provides semantic retrieval, hybrid ranking, context budgeting, and deduplication for presentation intelligence."""

    def __init__(self, store=None, embedder=None):
        self.store = store or memory_store
        self.embedder = embedder or embedding_service

    @staticmethod
    def _estimate_tokens(text: str) -> int:
        """Rough estimation of token count (~4 characters per token)."""
        return max(1, len(text) // 4)

    @staticmethod
    def _is_duplicate_or_near_identical(text: str, selected_texts: Sequence[str], threshold: float = 0.75) -> bool:
        """Simple Jaccard word-set similarity check to suppress duplicate narrative chunks."""
        words_new = set(re.findall(r"\w+", text.lower()))
        if not words_new:
            return False
        for existing in selected_texts:
            words_exist = set(re.findall(r"\w+", existing.lower()))
            if not words_exist:
                continue
            intersection = len(words_new & words_exist)
            union = len(words_new | words_exist)
            if union > 0 and (intersection / union) >= threshold:
                return True
        return False

    def retrieve_presentation_context(
        self,
        query: str,
        workspace_id: str | None = None,
        dataset_ids: list[int] | None = None,
        domain: str | None = None,
        audience: str | None = None,
        memory_types: list[str | MemoryType] | None = None,
        top_k: int | None = None,
        max_context_items: int | None = None,
        max_total_chars: int | None = None,
        max_results_per_source: int = 2,
    ) -> RetrievalContext:
        """Retrieves and ranks relevant presentation memories with strict context budgeting and provenance."""
        if not config.PRESENTATION_MEMORY_ENABLED:
            logger.debug("Presentation memory is disabled via config.")
            return RetrievalContext(query=query, status="disabled")

        clean_query = (query or "").strip()
        if not clean_query:
            return RetrievalContext(query="", status="empty")

        top_k_val = top_k or config.PRESENTATION_MEMORY_TOP_K
        max_items = max_context_items or config.PRESENTATION_MEMORY_MAX_CONTEXT_ITEMS
        max_chars = max_total_chars or config.PRESENTATION_MEMORY_MAX_TOTAL_CHARS

        try:
            # 1. Embed user query using Nomic
            query_vec = self.embedder.embed_text(clean_query)
            if not query_vec:
                logger.warning("Could not obtain embedding for query; returning degraded retrieval context.")
                return RetrievalContext(query=clean_query, status="degraded")

            # 2. Vector search in local store
            raw_candidates = self.store.search_vector(
                query_vector=query_vec,
                memory_types=memory_types,
                domain=domain,
                audience=audience,
                workspace_id=workspace_id,
                dataset_ids=dataset_ids,
                top_k=top_k_val * 2,  # Fetch wider candidate pool for hybrid re-ranking
            )

            if not raw_candidates:
                return RetrievalContext(query=clean_query, total_candidates=0, status="empty")

            # 3. Hybrid Re-Ranking & Scoring
            scored_candidates: list[SearchResult] = []
            now_dt = datetime.datetime.now(datetime.timezone.utc)

            for cand in raw_candidates:
                score = cand.semantic_score

                # Metadata Relevance Boosts
                cand_domain = cand.provenance.get("domain") or cand.metadata.get("domain")
                if domain and cand_domain and (domain.lower() in cand_domain.lower() or cand_domain.lower() in domain.lower()):
                    score += 0.12

                cand_aud = cand.provenance.get("audience") or cand.metadata.get("audience")
                if audience and cand_aud and (audience.lower() in cand_aud.lower() or cand_aud.lower() in audience.lower()):
                    score += 0.08

                if workspace_id and cand.provenance.get("workspace_id") == workspace_id:
                    score += 0.15

                # Recency Weight (up to +0.05 for items created within 30 days)
                created_str = cand.provenance.get("created_at") or cand.metadata.get("created_at")
                if created_str:
                    try:
                        c_dt = datetime.datetime.fromisoformat(created_str.replace("Z", "+00:00"))
                        age_days = max(0, (now_dt - c_dt).days)
                        recency_boost = max(0.0, 0.05 * (1.0 - min(1.0, age_days / 60.0)))
                        score += recency_boost
                    except Exception:
                        pass

                # Cap score at 1.0
                cand.score = round(min(1.0, score), 4)
                # Ensure evidence status is strictly non-current
                cand.evidence_status = "historical" if cand.memory_type != MemoryType.DATASET_PROFILE else "contextual"
                scored_candidates.append(cand)

            scored_candidates.sort(key=lambda x: x.score, reverse=True)

            # 4. Context Budgeting & Deduplication
            selected_results: list[SearchResult] = []
            selected_texts: list[str] = []
            source_counts: dict[str, int] = {}
            current_chars = 0

            for cand in scored_candidates:
                if len(selected_results) >= max_items:
                    break

                # Source capping
                src_key = cand.deck_id or cand.source_id
                if source_counts.get(src_key, 0) >= max_results_per_source:
                    continue

                # Near-duplicate suppression
                if self._is_duplicate_or_near_identical(cand.text, selected_texts):
                    continue

                chunk_len = len(cand.text)
                if current_chars + chunk_len > max_chars and selected_results:
                    # Exceeds character budget; stop adding
                    continue

                selected_results.append(cand)
                selected_texts.append(cand.text)
                source_counts[src_key] = source_counts.get(src_key, 0) + 1
                current_chars += chunk_len

            # 5. Extract Historical Presentation Decks
            seen_deck_ids = set()
            similar_decks: list[SimilarPresentationResult] = []
            for r in selected_results:
                d_id = r.deck_id
                if d_id and d_id not in seen_deck_ids:
                    seen_deck_ids.add(d_id)
                    prov = r.provenance
                    similar_decks.append(
                        SimilarPresentationResult(
                            deck_id=d_id,
                            title=prov.get("deck_title", "Historical Presentation"),
                            similarity_score=r.score,
                            domain=prov.get("domain"),
                            audience=prov.get("audience"),
                            theme_id=prov.get("theme_id"),
                            slide_count=prov.get("total_slides", 0),
                            created_at=prov.get("created_at"),
                            semantic_summary=r.text[:220] + "...",
                            provenance=prov
                        )
                    )

            total_est_tokens = sum(self._estimate_tokens(r.text) for r in selected_results)

            return RetrievalContext(
                query=clean_query,
                total_candidates=len(raw_candidates),
                results=selected_results,
                historical_decks=similar_decks,
                context_budget_used_chars=current_chars,
                estimated_tokens=total_est_tokens,
                embedding_model_used=config.PRESENTATION_EMBEDDING_MODEL,
                status="success"
            )

        except Exception as exc:
            logger.warning(f"Presentation memory retrieval encountered an error: {exc}", exc_info=True)
            return RetrievalContext(query=clean_query, status="degraded")

    def find_similar_presentations(
        self,
        query: str,
        domain: str | None = None,
        audience: str | None = None,
        top_k: int = 5,
    ) -> list[SimilarPresentationResult]:
        """Convenience method to retrieve similar historical decks for presentation planning."""
        res = self.retrieve_presentation_context(
            query=query,
            domain=domain,
            audience=audience,
            memory_types=[MemoryType.PRESENTATION_DECK],
            top_k=top_k,
            max_results_per_source=1
        )
        return res.historical_decks


# Global singleton
presentation_retrieval_service = PresentationRetrievalService()
