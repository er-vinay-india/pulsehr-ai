"""
HighView Ingestion V2 — Phase I7 Hybrid Multi-Namespace Retriever
Stage 11: Multi-Namespace Hybrid Retrieval

Core Invariants:
1. Multi-namespace candidate retrieval combining BM25, Vector similarity, and Graph proximity.
2. Uses Reciprocal Rank Fusion (RRF) instead of uncalibrated raw score addition.
3. Offline / degraded graceful fallback: BM25 + Graph operates cleanly if vector is unavailable.
4. Preserves dataset isolation: strictly scoped to authorized dataset_id.
5. Zero LLM calls (0).
"""

from typing import Sequence
from pydantic import BaseModel, ConfigDict, Field

from app.services.ingestion_v2.retrieval.namespaces import RetrievalNamespace
from app.services.ingestion_v2.retrieval.documents import RetrievalDocument
from app.services.ingestion_v2.retrieval.bm25_index import MultiNamespaceBM25Index
from app.services.ingestion_v2.retrieval.vector_index import MultiNamespaceVectorIndex
from app.services.ingestion_v2.retrieval.graph_retriever import GraphRetriever, GraphExpansionResult
from app.services.ingestion_v2.retrieval.intent_router import QueryIntentRouter, QueryIntentResult
from app.services.ingestion_v2.retrieval.reranker import GovernedReranker, RankedCandidate


class HybridRetrievalResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    query: str
    dataset_id: str
    intent_result: QueryIntentResult
    ranked_candidates: list[RankedCandidate]
    graph_expansion: GraphExpansionResult | None = None
    telemetry: dict[str, str | int | float | bool] = Field(default_factory=dict)


class HybridRetriever:
    """
    Coordinates multi-namespace candidate retrieval across BM25, Vector, and Graph channels.
    """

    def __init__(
        self,
        bm25_index: MultiNamespaceBM25Index,
        vector_index: MultiNamespaceVectorIndex,
        graph_retriever: GraphRetriever | None = None,
        intent_router: QueryIntentRouter | None = None,
        reranker: GovernedReranker | None = None,
    ):
        self.bm25_index = bm25_index
        self.vector_index = vector_index
        self.graph_retriever = graph_retriever
        self.intent_router = intent_router or QueryIntentRouter()
        self.reranker = reranker or GovernedReranker()

    def retrieve(
        self,
        query: str,
        dataset_id: str | None = None,
        top_k: int = 10,
        allowed_namespaces: Sequence[RetrievalNamespace] | None = None,
    ) -> HybridRetrievalResult:
        # 1. Intent Routing
        intent_res = self.intent_router.route_query(query)

        target_namespaces = intent_res.target_namespaces
        if allowed_namespaces:
            target_namespaces = [ns for ns in target_namespaces if ns in allowed_namespaces]
            if not target_namespaces:
                target_namespaces = list(allowed_namespaces)

        # 2. Lexical Channel (BM25)
        bm25_results = self.bm25_index.search(
            query=query,
            namespaces=target_namespaces,
            top_k=top_k * 3,
        )

        # 3. Vector Channel (VectorIndex)
        vector_results = self.vector_index.search(
            query=query,
            namespaces=target_namespaces,
            top_k=top_k * 3,
        )

        # 4. Reciprocal Rank Fusion (RRF)
        # RRF(d) = sum( 1 / (60 + rank_i) )
        doc_map: dict[str, RetrievalDocument] = {}
        rrf_scores: dict[str, float] = {}

        for item in bm25_results:
            d = item.document
            # Enforce dataset isolation if dataset_id provided
            if dataset_id is not None and str(d.dataset_id) != str(dataset_id):
                continue
            doc_map[d.document_id] = d
            rrf_scores[d.document_id] = rrf_scores.get(d.document_id, 0.0) + (1.0 / (60.0 + item.rank))

        for v_item in vector_results:
            d = v_item.document
            if dataset_id is not None and str(d.dataset_id) != str(dataset_id):
                continue
            doc_map[d.document_id] = d
            rrf_scores[d.document_id] = rrf_scores.get(d.document_id, 0.0) + (1.0 / (60.0 + v_item.rank))

        # 5. Graph Neighborhood Expansion
        graph_res: GraphExpansionResult | None = None
        if self.graph_retriever and intent_res.requires_graph_expansion and doc_map:
            # Pick top candidate artifact IDs as seeds
            sorted_initial = sorted(rrf_scores.items(), key=lambda x: -x[1])[:3]
            seeds = [doc_map[doc_id].artifact_id for doc_id, _ in sorted_initial]
            graph_res = self.graph_retriever.expand_neighborhood(seeds)

            # Boost candidates whose artifact_id is in expanded neighborhood
            expanded_set = set(graph_res.expanded_node_ids)
            for doc_id, doc in doc_map.items():
                if doc.artifact_id in expanded_set:
                    rrf_scores[doc_id] += 0.01  # Governed graph proximity bonus

        # Prepare candidates for reranking
        candidates = [(doc_map[doc_id], rrf_scores[doc_id]) for doc_id in rrf_scores]

        # 6. Governed Reranking
        ranked_candidates = self.reranker.rerank(
            candidates=candidates,
            intent_result=intent_res,
            top_k=top_k,
        )

        telemetry = {
            "bm25_hits": len(bm25_results),
            "vector_hits": len(vector_results),
            "vector_status": self.vector_index.status,
            "graph_expanded_nodes": len(graph_res.expanded_node_ids) if graph_res else 0,
            "llm_calls": 0,
            "embedding_query_calls": self.vector_index.embedding_query_calls,
        }

        return HybridRetrievalResult(
            query=query,
            dataset_id=str(dataset_id or ""),
            intent_result=intent_res,
            ranked_candidates=ranked_candidates,
            graph_expansion=graph_res,
            telemetry=telemetry,
        )
