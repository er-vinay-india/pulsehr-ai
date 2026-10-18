"""
HighView Ingestion V2 — Phase I7 Retrieval Manifest & Invalidation
Stage 11: Multi-Namespace Hybrid Retrieval

Core Invariants:
1. Manifest binds strictly to dataset_id, dataset_version, source_fingerprint, and semantic_graph_fingerprint.
2. Manifest fingerprint is deterministic and stable across timestamps and execution run_ids.
3. Index staleness is cleanly detected across any upstream artifact change.
"""

import hashlib
import json
from typing import Sequence
from pydantic import BaseModel, ConfigDict, Field

from app.services.ingestion_v2.retrieval.namespaces import RetrievalNamespace
from app.services.ingestion_v2.retrieval.documents import RetrievalDocument


def compute_manifest_fingerprint(
    dataset_id: str,
    dataset_version: str,
    source_fingerprint: str,
    semantic_graph_fingerprint: str | None,
    document_fingerprints: Sequence[str],
    embedding_model: str,
    bm25_version: str,
    vector_version: str,
    analytical_profile_fingerprint: str | None = None,
    embedding_model_version: str = "v1.5",
    normalization_policy: str = "l2",
) -> str:
    """
    Computes a deterministic SHA-256 fingerprint for the entire multi-namespace retrieval manifest.
    Excludes volatile fields like created_at, run_id, and filesystem paths.
    """
    payload = {
        "dataset_id": str(dataset_id),
        "dataset_version": str(dataset_version),
        "source_fingerprint": str(source_fingerprint),
        "semantic_graph_fingerprint": str(semantic_graph_fingerprint or ""),
        "analytical_profile_fingerprint": str(analytical_profile_fingerprint or ""),
        "document_fingerprints": sorted(document_fingerprints),
        "embedding_model": embedding_model,
        "embedding_model_version": embedding_model_version,
        "normalization_policy": normalization_policy,
        "bm25_version": bm25_version,
        "vector_version": vector_version,
    }
    canonical_json = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()


class MultiNamespaceRetrievalManifest(BaseModel):
    """
    Stage 11 Contract: Complete multi-namespace retrieval index manifest.
    """
    model_config = ConfigDict(extra="forbid", frozen=True)

    stage_name: str = "retrieval_indexing"
    dataset_id: str
    dataset_version: str
    source_fingerprint: str
    semantic_graph_fingerprint: str | None = None
    analytical_profile_fingerprint: str | None = None
    embedding_model: str = "nomic-embed-text:latest"
    embedding_model_id: str = "nomic-embed-text"
    embedding_model_version: str = "v1.5"
    normalization_policy: str = "l2"
    embedding_dimension: int = 768
    bm25_index_version: str = "v1"
    vector_index_version: str = "v1"
    documents: list[RetrievalDocument] = Field(default_factory=list)
    namespace_counts: dict[str, int] = Field(default_factory=dict)
    manifest_fingerprint: str

    @classmethod
    def create(
        cls,
        dataset_id: str,
        dataset_version: str,
        source_fingerprint: str,
        documents: Sequence[RetrievalDocument],
        semantic_graph_fingerprint: str | None = None,
        analytical_profile_fingerprint: str | None = None,
        embedding_model: str = "nomic-embed-text:latest",
        embedding_model_id: str = "nomic-embed-text",
        embedding_model_version: str = "v1.5",
        normalization_policy: str = "l2",
        embedding_dimension: int = 768,
        bm25_index_version: str = "v1",
        vector_index_version: str = "v1",
    ) -> "MultiNamespaceRetrievalManifest":
        ns_counts: dict[str, int] = {}
        doc_fps: list[str] = []
        for d in documents:
            ns_key = d.namespace.value
            ns_counts[ns_key] = ns_counts.get(ns_key, 0) + 1
            doc_fps.append(d.content_fingerprint)

        manifest_fp = compute_manifest_fingerprint(
            dataset_id=dataset_id,
            dataset_version=dataset_version,
            source_fingerprint=source_fingerprint,
            semantic_graph_fingerprint=semantic_graph_fingerprint,
            document_fingerprints=doc_fps,
            embedding_model=embedding_model,
            bm25_version=bm25_index_version,
            vector_version=vector_index_version,
            analytical_profile_fingerprint=analytical_profile_fingerprint,
            embedding_model_version=embedding_model_version,
            normalization_policy=normalization_policy,
        )

        return cls(
            dataset_id=str(dataset_id),
            dataset_version=str(dataset_version),
            source_fingerprint=source_fingerprint,
            semantic_graph_fingerprint=semantic_graph_fingerprint,
            analytical_profile_fingerprint=analytical_profile_fingerprint,
            embedding_model=embedding_model,
            embedding_model_id=embedding_model_id,
            embedding_model_version=embedding_model_version,
            normalization_policy=normalization_policy,
            embedding_dimension=embedding_dimension,
            bm25_index_version=bm25_index_version,
            vector_index_version=vector_index_version,
            documents=list(documents),
            namespace_counts=ns_counts,
            manifest_fingerprint=manifest_fp,
        )

    def is_stale(
        self,
        current_dataset_version: str,
        current_source_fingerprint: str,
        current_semantic_graph_fingerprint: str | None = None,
        current_analytical_profile_fingerprint: str | None = None,
        current_embedding_model: str | None = None,
        current_embedding_model_version: str | None = None,
        current_normalization_policy: str | None = None,
    ) -> bool:
        """
        Detects whether this index manifest is stale compared to live artifact states.
        """
        if self.dataset_version != str(current_dataset_version):
            return True
        if self.source_fingerprint != str(current_source_fingerprint):
            return True
        if current_semantic_graph_fingerprint and self.semantic_graph_fingerprint != str(current_semantic_graph_fingerprint):
            return True
        if current_analytical_profile_fingerprint and self.analytical_profile_fingerprint != str(current_analytical_profile_fingerprint):
            return True
        if current_embedding_model and self.embedding_model != current_embedding_model:
            return True
        if current_embedding_model_version and self.embedding_model_version != current_embedding_model_version:
            return True
        if current_normalization_policy and self.normalization_policy != current_normalization_policy:
            return True
        return False
