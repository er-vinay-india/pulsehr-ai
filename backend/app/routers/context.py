"""API endpoints for Enterprise Knowledge & Context Fabric (Phase F).

Exposes:
- GET /api/context/documents: List registered organizational documents.
- GET /api/context/documents/{document_id}: Detailed document view with extracted CTX-* items.
- POST /api/context/documents: Ingest a new organizational document or SOP.
- GET /api/context/evidence: List registered CTX-* organizational evidence items.
- GET /api/context/evidence/{context_id}: Inspect individual CTX-* evidence and cryptographic provenance.
- GET /api/context/thresholds/{metric_name}: Retrieve authoritative threshold for a metric.
- POST /api/context/search: Hybrid search across organizational context.
"""
from __future__ import annotations

import logging
from typing import Any
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from app.context import (
    ContextArtifactType,
    ContextDocument,
    ContextEvidence,
    context_store,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/context", tags=["Context Fabric"])


class DocumentIngestRequest(BaseModel):
    title: str
    artifact_type: ContextArtifactType = ContextArtifactType.POLICY
    domain: str = "workforce"
    department: str | None = None
    dataset_id: str | int | None = None
    version: str = "v1.0"
    effective_date: str = "2026-01-01"
    raw_content: str
    source_uri: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    rules: list[dict[str, Any]] = Field(default_factory=list)


class ContextSearchRequest(BaseModel):
    query: str
    domain: str | None = None
    artifact_type: str | None = None
    department: str | None = None
    limit: int = 5


@router.get("/documents")
def list_documents(
    domain: str | None = Query(default=None),
    artifact_type: str | None = Query(default=None),
) -> list[dict[str, Any]]:
    """Lists registered organizational documents in the Context Fabric."""
    docs = context_store.list_documents(domain=domain, artifact_type=artifact_type)
    return [d.model_dump() for d in docs]


@router.get("/documents/{document_id}")
def get_document_details(document_id: str) -> dict[str, Any]:
    """Retrieves document metadata, content excerpt, and extracted CTX-* items."""
    doc = context_store.get_document(document_id)
    if not doc:
        raise HTTPException(status_code=404, detail=f"Document '{document_id}' not found.")
    return doc.model_dump()


@router.post("/documents")
def ingest_document(req: DocumentIngestRequest) -> dict[str, Any]:
    """Ingests a new policy, SOP, or business definition into the Context Fabric."""
    doc = ContextDocument(
        title=req.title,
        artifact_type=req.artifact_type,
        domain=req.domain,
        department=req.department,
        dataset_id=req.dataset_id,
        version=req.version,
        effective_date=req.effective_date,
        raw_content=req.raw_content,
        source_uri=req.source_uri,
        metadata=req.metadata,
    )

    # Convert provided rules into CTX-* evidence
    for idx, rule in enumerate(req.rules, start=1):
        ev = ContextEvidence.create(
            document_id=doc.document_id,
            artifact_type=ContextArtifactType(rule.get("artifact_type", req.artifact_type.value)),
            domain=req.domain,
            title=rule.get("title", f"{req.title} - Rule {idx}"),
            section=rule.get("section", f"Section {idx}"),
            verbatim_excerpt=rule.get("verbatim_excerpt", req.raw_content[:200]),
            rule_summary=rule.get("rule_summary", ""),
            metric_name=rule.get("metric_name"),
            operator=rule.get("operator"),
            threshold_value=rule.get("threshold_value"),
            unit=rule.get("unit"),
            department=rule.get("department", req.department),
            source_uri=req.source_uri,
        )
        doc.extracted_evidence.append(ev)

    context_store.ingest_document(doc)
    return doc.model_dump()


@router.get("/evidence")
def list_context_evidence(
    domain: str | None = Query(default=None),
) -> list[dict[str, Any]]:
    """Lists registered CTX-* organizational evidence items."""
    evidence = context_store.list_all_evidence(domain=domain)
    return [e.model_dump() for e in evidence]


@router.get("/evidence/{context_id}")
def get_context_evidence_details(context_id: str) -> dict[str, Any]:
    """Retrieves individual CTX-* evidence token with cryptographic provenance audit."""
    ev = context_store.get_evidence(context_id)
    if not ev:
        raise HTTPException(status_code=404, detail=f"Context evidence '{context_id}' not found.")
    provenance = context_store.trace_provenance(context_id)
    return {
        "evidence": ev.model_dump(),
        "provenance": provenance,
    }


@router.get("/thresholds/{metric_name}")
def get_metric_threshold(
    metric_name: str,
    department: str | None = Query(default=None),
) -> dict[str, Any]:
    """Retrieves official organizational threshold for a metric."""
    ev = context_store.get_threshold(metric_name=metric_name, department=department)
    if not ev:
        raise HTTPException(status_code=404, detail=f"No threshold registered for metric '{metric_name}'.")
    return ev.model_dump()


@router.post("/search")
def search_context_fabric(req: ContextSearchRequest) -> dict[str, Any]:
    """Executes deterministic hybrid search across Context Fabric."""
    res = context_store.search_context(
        query=req.query,
        domain=req.domain,
        artifact_type=req.artifact_type,
        department=req.department,
        limit=req.limit,
    )
    return res.model_dump()
