"""
HighView Ingestion V2 — Phase I7 Governed Reranker
Stage 11: Multi-Namespace Hybrid Retrieval

Core Invariants:
1. Deterministic governed reranking without LLM calls.
2. Authority boost prioritizes validated semantic definitions and EVID-backed findings over raw matches.
3. Reliability-aware: higher AnalyticalReliability ranks higher, but low-reliability findings are never hidden if they are the only valid match.
4. Ambiguity preservation: competing definitions under the same name are never silently merged.
5. Deterministic tie-breaking by (score desc, document_id asc).
"""

from typing import Sequence
from pydantic import BaseModel, ConfigDict, Field

from app.services.ingestion_v2.retrieval.namespaces import (
    AuthorityClass,
    QueryIntent,
)
from app.services.ingestion_v2.retrieval.documents import RetrievalDocument
from app.services.ingestion_v2.retrieval.intent_router import QueryIntentResult


class RankedCandidate(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    document: RetrievalDocument
    final_score: float
    rank: int
    rrf_score: float
    authority_boost: float
    reliability_boost: float
    is_ambiguous: bool = False
    ambiguity_candidates: list[str] = Field(default_factory=list)


class GovernedReranker:
    """
    Reranks candidate retrieval documents using governed rules, authority tiers,
    intent alignment, and statistical reliability.
    """

    def rerank(
        self,
        candidates: Sequence[tuple[RetrievalDocument, float]],  # (doc, rrf_score)
        intent_result: QueryIntentResult,
        top_k: int = 10,
    ) -> list[RankedCandidate]:
        if not candidates or top_k <= 0:
            return []

        scored_items: list[dict] = []

        # Check for ambiguity in metric names (e.g., two distinct formulas for "Conversion Rate")
        metric_name_to_docs: dict[str, list[RetrievalDocument]] = {}
        for doc, _ in candidates:
            if doc.artifact_type == "metric":
                m_name = doc.structured_metadata.get("metric_name", "").casefold()
                if m_name:
                    metric_name_to_docs.setdefault(m_name, []).append(doc)

        ambiguous_metrics: dict[str, list[str]] = {}
        for m_name, doc_list in metric_name_to_docs.items():
            distinct_formulas = {d.structured_metadata.get("formula") for d in doc_list}
            if len(distinct_formulas) > 1:
                ambiguous_metrics[m_name] = [d.artifact_id for d in doc_list]

        for doc, rrf_score in candidates:
            # 1. Base Score from Rank Fusion
            base_score = rrf_score

            # 2. Namespace Intent Alignment Weight
            ns_val = doc.namespace.value
            ns_weight = intent_result.namespace_weights.get(ns_val, 0.5)

            # 3. Authority Boost
            auth_val = doc.authority_class.value
            auth_boost = intent_result.suggested_authority_boost.get(auth_val, 1.0)

            # Extra Authority Invariant:
            # For METRIC_LOOKUP: validated MetricDefinition strictly outranks raw schema column
            if intent_result.intent == QueryIntent.METRIC_LOOKUP and doc.artifact_type == "metric":
                auth_boost *= 1.5

            # For ANALYTICAL_FINDING_LOOKUP: EVID-backed finding outranks generic family description
            if intent_result.intent == QueryIntent.ANALYTICAL_FINDING_LOOKUP and doc.artifact_type == "analytical_finding":
                auth_boost *= 1.5

            # 4. Statistical Reliability Boost for Analytical Evidence
            rel_boost = 1.0
            if doc.authority_class == AuthorityClass.ANALYTICAL_EVIDENCE:
                rel = doc.structured_metadata.get("reliability", "HIGH")
                if rel == "HIGH":
                    rel_boost = 1.2
                elif rel == "MEDIUM":
                    rel_boost = 1.1
                else:
                    rel_boost = 1.0  # LOW reliability is not penalized to zero; remains visible

            # Combined score: RRF * namespace_weight * authority_boost * reliability_boost
            final_score = base_score * ns_weight * auth_boost * rel_boost

            # Ambiguity check
            is_ambig = False
            ambig_list: list[str] = []
            if doc.artifact_type == "metric":
                m_name = doc.structured_metadata.get("metric_name", "").casefold()
                if m_name in ambiguous_metrics:
                    is_ambig = True
                    ambig_list = ambiguous_metrics[m_name]

            scored_items.append({
                "document": doc,
                "final_score": round(final_score, 6),
                "rrf_score": round(rrf_score, 6),
                "authority_boost": round(auth_boost, 2),
                "reliability_boost": round(rel_boost, 2),
                "is_ambiguous": is_ambig,
                "ambiguity_candidates": ambig_list,
            })

        # Deterministic tie-breaking: final_score desc, document_id asc
        scored_items.sort(key=lambda x: (-x["final_score"], x["document"].document_id))

        results: list[RankedCandidate] = []
        for rank_idx, item in enumerate(scored_items[:top_k], start=1):
            results.append(
                RankedCandidate(
                    document=item["document"],
                    final_score=item["final_score"],
                    rank=rank_idx,
                    rrf_score=item["rrf_score"],
                    authority_boost=item["authority_boost"],
                    reliability_boost=item["reliability_boost"],
                    is_ambiguous=item["is_ambiguous"],
                    ambiguity_candidates=item["ambiguity_candidates"],
                )
            )

        return results
