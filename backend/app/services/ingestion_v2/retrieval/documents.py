"""
HighView Ingestion V2 — Phase I7 Retrieval Documents
Stage 11: Multi-Namespace Hybrid Retrieval

Core Invariants:
1. text_for_retrieval is strictly a search representation.
2. Canonical structured_metadata is the authoritative source of truth.
3. Content fingerprint excludes volatile fields (timestamp, run_id, build time).
4. Same semantic artifact -> identical content fingerprint.
"""

import hashlib
import json
from typing import Any
from pydantic import BaseModel, ConfigDict, Field

from app.services.ingestion_v2.retrieval.namespaces import AuthorityClass, RetrievalNamespace


def compute_document_fingerprint(
    namespace: RetrievalNamespace,
    artifact_type: str,
    artifact_id: str,
    dataset_version: str,
    semantic_graph_version: str | None,
    text_for_retrieval: str,
    structured_metadata: dict[str, Any],
) -> str:
    """
    Computes a deterministic SHA-256 fingerprint for a retrieval document.
    Volatile keys (timestamp, run_id, build time, latency) are strictly excluded.
    """
    volatile_keys = {
        "timestamp",
        "created_at",
        "run_id",
        "build_time",
        "latency_ms",
        "execution_time",
        "index_build_timestamp",
    }
    cleaned_metadata = {
        k: v for k, v in structured_metadata.items() if k not in volatile_keys
    }

    payload = {
        "namespace": namespace.value,
        "artifact_type": artifact_type,
        "artifact_id": artifact_id,
        "dataset_version": dataset_version,
        "semantic_graph_version": semantic_graph_version or "",
        "text_for_retrieval": " ".join(text_for_retrieval.split()),
        "structured_metadata": cleaned_metadata,
    }
    canonical_json = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()


class RetrievalDocument(BaseModel):
    """
    Unified typed retrieval document across all four namespaces.
    Retains full canonical provenance, evidence links, and structured metadata.
    """
    model_config = ConfigDict(extra="forbid", frozen=True)

    document_id: str
    namespace: RetrievalNamespace
    authority_class: AuthorityClass
    dataset_id: str
    dataset_version: str
    source_fingerprint: str
    semantic_graph_version: str | None = None
    artifact_type: str
    artifact_id: str
    text_for_retrieval: str
    structured_metadata: dict[str, Any] = Field(default_factory=dict)
    provenance_refs: list[str] = Field(default_factory=list)
    evidence_refs: list[str] = Field(default_factory=list)
    content_fingerprint: str
    index_version: str = "v1"

    @classmethod
    def create(
        cls,
        document_id: str,
        namespace: RetrievalNamespace,
        authority_class: AuthorityClass,
        dataset_id: str,
        dataset_version: str,
        source_fingerprint: str,
        artifact_type: str,
        artifact_id: str,
        text_for_retrieval: str,
        structured_metadata: dict[str, Any],
        provenance_refs: list[str] | None = None,
        evidence_refs: list[str] | None = None,
        semantic_graph_version: str | None = None,
        index_version: str = "v1",
    ) -> "RetrievalDocument":
        fingerprint = compute_document_fingerprint(
            namespace=namespace,
            artifact_type=artifact_type,
            artifact_id=artifact_id,
            dataset_version=dataset_version,
            semantic_graph_version=semantic_graph_version,
            text_for_retrieval=text_for_retrieval,
            structured_metadata=structured_metadata,
        )
        return cls(
            document_id=document_id,
            namespace=namespace,
            authority_class=authority_class,
            dataset_id=str(dataset_id),
            dataset_version=str(dataset_version),
            source_fingerprint=source_fingerprint,
            semantic_graph_version=semantic_graph_version,
            artifact_type=artifact_type,
            artifact_id=artifact_id,
            text_for_retrieval=text_for_retrieval.strip(),
            structured_metadata=structured_metadata,
            provenance_refs=provenance_refs or [],
            evidence_refs=evidence_refs or [],
            content_fingerprint=fingerprint,
            index_version=index_version,
        )
