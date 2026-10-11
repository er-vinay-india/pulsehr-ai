"""Pydantic contracts and schemas for Enterprise Knowledge & Context Fabric (Phase F).

Enforces:
1. Strict Epistemological Separation:
   - EVID-* = Empirical dataset evidence (what uploaded data proves)
   - CTX-*  = Organizational context evidence (what organizational policies, SOPs, rules say)
   - SCEN-* = Counterfactual simulated scenario projections
   - Strictly isolated namespaces: NEVER merge or conflate them.
2. Typed Context Artifacts:
   - Policy, SOP, KPI Definition, Business Rule, Threshold, Report, Presentation Archive.
3. Cryptographic Provenance:
   - Every CTX-* evidence token carries verbatim excerpt, document ID, section, and SHA-256 hash.
"""
from __future__ import annotations

import enum
import hashlib
import time
from uuid import uuid4
from typing import Any, Literal
from pydantic import BaseModel, ConfigDict, Field


class ContextArtifactType(str, enum.Enum):
    """Classification of organizational context artifacts."""
    POLICY = "POLICY"
    SOP = "SOP"
    KPI_DEFINITION = "KPI_DEFINITION"
    BUSINESS_RULE = "BUSINESS_RULE"
    THRESHOLD = "THRESHOLD"
    REPORT = "REPORT"
    PRESENTATION_ARCHIVE = "PRESENTATION_ARCHIVE"


class ContextChunk(BaseModel):
    """Individual chunk extracted from an ingested organizational document."""
    model_config = ConfigDict(extra="ignore")

    chunk_id: str = Field(default_factory=lambda: f"chk-{uuid4().hex[:8]}")
    document_id: str
    section: str = "General"
    content: str
    page_number: int | None = None
    character_count: int = 0
    token_estimate: int = 0


class ContextEvidence(BaseModel):
    """Atomic organizational evidence unit (CTX-*) extracted from Context Fabric documents."""
    model_config = ConfigDict(extra="ignore")

    context_id: str
    document_id: str
    artifact_type: ContextArtifactType
    domain: str = "workforce"  # workforce, environmental, retail, general
    title: str
    section: str
    verbatim_excerpt: str
    rule_summary: str

    metric_name: str | None = None
    operator: str | None = None  # MIN, MAX, EQUALS, TARGET, RANGE
    threshold_value: float | str | None = None
    unit: str | None = None
    department: str | None = None

    source_uri: str | None = None
    provenance_hash: str = ""
    created_at: float = Field(default_factory=time.time)

    @classmethod
    def create(
        cls,
        document_id: str,
        artifact_type: ContextArtifactType,
        title: str,
        section: str,
        verbatim_excerpt: str,
        rule_summary: str,
        domain: str = "workforce",
        metric_name: str | None = None,
        operator: str | None = None,
        threshold_value: float | str | None = None,
        unit: str | None = None,
        department: str | None = None,
        source_uri: str | None = None,
        context_id: str | None = None,
    ) -> ContextEvidence:
        hash_str = f"{document_id}:{section}:{verbatim_excerpt}"
        prov_hash = hashlib.sha256(hash_str.encode("utf-8")).hexdigest()
        cid = context_id or f"CTX-{prov_hash[:8].upper()}"

        return cls(
            context_id=cid,
            document_id=document_id,
            artifact_type=artifact_type,
            domain=domain,
            title=title,
            section=section,
            verbatim_excerpt=verbatim_excerpt,
            rule_summary=rule_summary,
            metric_name=metric_name,
            operator=operator,
            threshold_value=threshold_value,
            unit=unit,
            department=department,
            source_uri=source_uri,
            provenance_hash=prov_hash,
            created_at=time.time(),
        )


class ContextDocument(BaseModel):
    """Ingested organizational document containing policies, definitions, or business rules."""
    model_config = ConfigDict(extra="ignore")

    document_id: str = Field(default_factory=lambda: f"DOC-{uuid4().hex[:8].upper()}")
    title: str
    artifact_type: ContextArtifactType
    domain: str = "workforce"
    department: str | None = None
    dataset_id: str | int | None = None

    version: str = "v1.0"
    effective_date: str = "2026-01-01"
    status: Literal["ACTIVE", "DRAFT", "ARCHIVED", "SUPERSEDED"] = "ACTIVE"

    raw_content: str
    chunks: list[ContextChunk] = Field(default_factory=list)
    extracted_evidence: list[ContextEvidence] = Field(default_factory=list)

    source_uri: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    uploaded_at: float = Field(default_factory=time.time)


class ContextQueryResult(BaseModel):
    """Result of searching the Context Fabric."""
    model_config = ConfigDict(extra="ignore")

    query: str
    evidence_matches: list[ContextEvidence] = Field(default_factory=list)
    similarity_scores: list[float] = Field(default_factory=list)
    total_matched: int = 0
    retrieval_strategy: str = "hybrid_lexical_semantic"
