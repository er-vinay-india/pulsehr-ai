from __future__ import annotations

from enum import Enum
from typing import Any
from pydantic import BaseModel, Field


class MemoryType(str, Enum):
    """Explicit semantic memory categories for presentation intelligence."""
    PRESENTATION_DECK = "PRESENTATION_DECK"
    SLIDE = "SLIDE"
    BUSINESS_FINDING = "BUSINESS_FINDING"
    DATASET_PROFILE = "DATASET_PROFILE"
    EVIDENCE = "EVIDENCE"
    USER_INSTRUCTION = "USER_INSTRUCTION"
    BRAND_GUIDELINE = "BRAND_GUIDELINE"
    THEME_PREFERENCE = "THEME_PREFERENCE"
    WORKSPACE_CONTEXT = "WORKSPACE_CONTEXT"
    REPORT_SUMMARY = "REPORT_SUMMARY"
    DOMAIN_KNOWLEDGE = "DOMAIN_KNOWLEDGE"
    LIMITATION = "LIMITATION"
    RECOMMENDATION = "RECOMMENDATION"


class EvidenceStatus(str, Enum):
    """Distinguishes current empirical evidence from historical or background context."""
    CURRENT = "current"
    HISTORICAL = "historical"
    CONTEXTUAL = "contextual"


class MemoryRecord(BaseModel):
    """Core memory record persisted in presentation memory vector store."""
    memory_id: str
    memory_type: MemoryType
    text: str
    embedding: list[float] | None = None
    source_id: str
    source_type: str
    deck_id: str | None = None
    slide_id: str | None = None
    dataset_id: int | None = None
    sheet_id: int | None = None
    workspace_id: str | None = None
    domain: str | None = None
    audience: str | None = None
    theme: str | None = None
    evidence_status: EvidenceStatus = EvidenceStatus.HISTORICAL
    content_hash: str
    provenance: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: str
    updated_at: str


class SearchResult(BaseModel):
    """Ranked memory search result returned by retrieval service."""
    memory_id: str
    memory_type: MemoryType
    score: float
    semantic_score: float
    text: str
    source_id: str
    deck_id: str | None = None
    slide_id: str | None = None
    evidence_status: str = "historical"
    provenance: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)


class SimilarPresentationResult(BaseModel):
    """Summary of a past similar presentation deck retrieved for structural guidance."""
    deck_id: str
    title: str
    similarity_score: float
    domain: str | None = None
    audience: str | None = None
    theme_id: str | None = None
    slide_count: int = 0
    created_at: str | None = None
    key_findings: list[str] = Field(default_factory=list)
    semantic_summary: str = ""
    provenance: dict[str, Any] = Field(default_factory=dict)


class RetrievalContext(BaseModel):
    """Structured context package returned to the presentation pipeline."""
    query: str
    total_candidates: int = 0
    results: list[SearchResult] = Field(default_factory=list)
    historical_decks: list[SimilarPresentationResult] = Field(default_factory=list)
    context_budget_used_chars: int = 0
    estimated_tokens: int = 0
    embedding_model_used: str = "nomic-embed-text:latest"
    status: str = "success"  # "success" | "degraded" | "empty"
