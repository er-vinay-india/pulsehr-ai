"""
HighView Ingestion V2 — Phase I7 Retrieval Service Package
Stage 11: Multi-Namespace Hybrid Retrieval, Graph-Aware Search & Governed Context Assembly
"""

from app.services.ingestion_v2.retrieval.namespaces import (
    RetrievalNamespace,
    AuthorityClass,
    QueryIntent,
)
from app.services.ingestion_v2.retrieval.documents import (
    RetrievalDocument,
    compute_document_fingerprint,
)
from app.services.ingestion_v2.retrieval.document_builder import (
    RetrievalDocumentBuilder,
)
from app.services.ingestion_v2.retrieval.manifest import (
    MultiNamespaceRetrievalManifest,
    compute_manifest_fingerprint,
)
from app.services.ingestion_v2.retrieval.bm25_index import (
    MultiNamespaceBM25Index,
    LexicalSearchResult,
)
from app.services.ingestion_v2.retrieval.vector_index import (
    MultiNamespaceVectorIndex,
    VectorSearchResult,
    VectorIndexStatus,
    cosine_similarity,
)
from app.services.ingestion_v2.retrieval.graph_retriever import (
    GraphRetriever,
    GraphExpansionResult,
)
from app.services.ingestion_v2.retrieval.intent_router import (
    QueryIntentRouter,
    QueryIntentResult,
)
from app.services.ingestion_v2.retrieval.reranker import (
    GovernedReranker,
    RankedCandidate,
)
from app.services.ingestion_v2.retrieval.hybrid_retriever import (
    HybridRetriever,
    HybridRetrievalResult,
)
from app.services.ingestion_v2.retrieval.context_assembler import (
    ContextAssembler,
    GovernedContextPackage,
)

__all__ = [
    "RetrievalNamespace",
    "AuthorityClass",
    "QueryIntent",
    "RetrievalDocument",
    "compute_document_fingerprint",
    "RetrievalDocumentBuilder",
    "MultiNamespaceRetrievalManifest",
    "compute_manifest_fingerprint",
    "MultiNamespaceBM25Index",
    "LexicalSearchResult",
    "MultiNamespaceVectorIndex",
    "VectorSearchResult",
    "VectorIndexStatus",
    "cosine_similarity",
    "GraphRetriever",
    "GraphExpansionResult",
    "QueryIntentRouter",
    "QueryIntentResult",
    "GovernedReranker",
    "RankedCandidate",
    "HybridRetriever",
    "HybridRetrievalResult",
    "ContextAssembler",
    "GovernedContextPackage",
]
