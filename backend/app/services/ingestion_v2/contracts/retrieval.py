"""
HighView Ingestion V2 — Retrieval Indexing Contract
Stage 11: Multi-Namespace Retrieval Indexing
Boundary: Isolated retrieval index manifests.
Rule: Retrieval is partitioned into distinct namespaces to prevent cross-domain contamination.
Vectorization indexes pre-existing semantic truth; it NEVER creates semantic truth.
"""

from enum import Enum
from pydantic import BaseModel, ConfigDict, Field
from app.services.ingestion_v2.contracts.base import IngestionContractBase


class RetrievalNamespace(str, Enum):
    RAW_SCHEMA = "RAW_SCHEMA"          # Physical tables, columns, sheets
    SEMANTIC = "SEMANTIC"              # Entities, business roles, concepts
    RELATIONSHIP = "RELATIONSHIP"      # Validated joins, grain bridges
    ANALYTICAL = "ANALYTICAL"          # Derived metrics, EDA-B findings, outliers


class IndexedDocumentRef(BaseModel):
    """
    Reference to an indexed retrieval unit.
    """
    model_config = ConfigDict(extra="forbid", frozen=True)

    document_id: str
    namespace: RetrievalNamespace
    entity_id: str
    content_hash: str
    token_count: int
    embedding_model: str
    evidence_ref: str | None = None


class MultiNamespaceRetrievalManifest(IngestionContractBase):
    """
    Stage 11 Contract: Multi-Namespace Retrieval Index Manifest.
    """
    stage_name: str = "retrieval_indexing"

    index_id: str
    embedding_dimension: int
    embedding_model: str
    documents: list[IndexedDocumentRef] = Field(default_factory=list)
    namespace_counts: dict[str, int] = Field(default_factory=dict)
