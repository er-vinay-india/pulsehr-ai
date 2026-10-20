"""Presentation Content Contracts & UserVisibleContentPolicy (PPT-L1).

Defines the core content contracts that establish the non-negotiable boundary:
    CONTENT TRUTH != PRESENTATION NARRATIVE

PresentationContentPackage contains authoritative, audited empirical facts, verified
numerical metrics, data table partitions, and governed visual specs.
UserVisibleContentPolicy guarantees that internal pipeline jargon (SDR, JoinPlan,
EVID-..., SHA-256 checksums, control plane IDs) never leak into presentation text.
"""

from __future__ import annotations

from enum import Enum
import re
from typing import Any
from pydantic import BaseModel, Field


class ContentRole(str, Enum):
    """Semantic role of a content item within the deck narrative."""
    PRIMARY_HERO = "PRIMARY_HERO"
    STRATEGIC_KPI = "STRATEGIC_KPI"
    KEY_FINDING = "KEY_FINDING"
    EXPLORATORY_TABLE = "EXPLORATORY_TABLE"
    ACTION_INITIATIVE = "ACTION_INITIATIVE"
    RISK_ANOMALY = "RISK_ANOMALY"


class ContentKind(str, Enum):
    """Physical visualization or artifact format for the content."""
    CHART = "chart"
    TABLE = "table"
    KPI_METRIC = "kpi_metric"
    NARRATIVE_INSIGHT = "narrative_insight"
    MAP = "map"
    IMAGE = "image"
    VIDEO = "video"


class PresentationContentItem(BaseModel):
    """Audited, self-contained unit of empirical presentation content."""
    content_id: str = Field(description="Unique stable content identity, e.g. CONTENT-001")
    kind: ContentKind = Field(description="Content visual type (chart, table, kpi, etc.)")
    role: ContentRole = Field(description="Narrative role (hero, kpi, key finding, etc.)")
    topic_category: str = Field(description="Business topic category, e.g. Regional Growth")
    title: str = Field(description="Business presentation headline")
    subtitle: str | None = Field(default=None, description="Optional presentation subtitle")
    
    # Ranking metrics (0.0 to 1.0)
    importance_score: float = Field(default=0.5, ge=0.0, le=1.0)
    decision_relevance: float = Field(default=0.5, ge=0.0, le=1.0)
    novelty_score: float = Field(default=0.5, ge=0.0, le=1.0)
    visual_suitability: float = Field(default=0.5, ge=0.0, le=1.0)
    redundancy_score: float = Field(default=0.0, ge=0.0, le=1.0)
    composite_score: float = Field(default=0.0)

    # Narrative payload (Executive insight)
    narrative_takeaway: str = Field(default="", description="Natural language executive takeaway")
    supporting_bullets: list[str] = Field(default_factory=list, description="Structured supporting bullet points")

    # Visual / Data payloads
    visual_spec: dict[str, Any] | None = Field(default=None, description="Governed visual specification")
    table_data: list[dict[str, Any]] | None = Field(default=None, description="Governed tabular data partition")
    metric_value: str | None = Field(default=None, description="Formatted KPI string, e.g. '1.21B' or '17.7%'")
    metric_label: str | None = Field(default=None, description="Business metric label")
    media_url: str | None = Field(default=None, description="URL for image/video media")
    poster_image_url: str | None = Field(default=None, description="High-DPI poster image for static fallback")

    # Governed provenance (strictly isolated from user-visible presentation text)
    evidence_ids: list[str] = Field(default_factory=list)
    fact_id: str | None = None
    source_dataset_id: int | str | None = None
    source_sheet_name: str | None = None
    dimension_name: str | None = None
    metric_name: str | None = None
    unit: str | None = None
    grain: str | None = None
    denominator: str | None = None


class PresentationContentPackage(BaseModel):
    """Governed content package emitted by PresentationContentHub for StoryPlanner."""
    package_id: str
    dataset_name: str
    domain: str
    items: list[PresentationContentItem] = Field(default_factory=list)
    available_topics: list[str] = Field(default_factory=list)
    global_kpis: list[PresentationContentItem] = Field(default_factory=list)
    content_fingerprint: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)

    def compute_fingerprint(self) -> str:
        """Computes a deterministic SHA-256 fingerprint over the canonical content payload."""
        import hashlib
        import json
        
        canonical_items = []
        for it in sorted(self.items, key=lambda x: x.content_id):
            canonical_items.append({
                "id": it.content_id,
                "kind": it.kind.value,
                "role": it.role.value,
                "title": it.title,
                "subtitle": it.subtitle,
                "metric_label": it.metric_label,
                "metric_value": it.metric_value,
                "takeaway": it.narrative_takeaway,
                "bullets": it.supporting_bullets,
                "dimension": it.dimension_name,
                "metric": it.metric_name,
                "unit": it.unit,
                "grain": it.grain,
                "denominator": it.denominator,
                "composite_score": it.composite_score,
            })
        
        canonical_kpis = []
        for it in sorted(self.global_kpis, key=lambda x: x.content_id):
            canonical_kpis.append({
                "id": it.content_id,
                "label": it.metric_label,
                "value": it.metric_value,
                "unit": it.unit,
            })

        payload = {
            "dataset": self.dataset_name,
            "domain": self.domain,
            "items": canonical_items,
            "kpis": canonical_kpis,
            "topics": sorted(self.available_topics),
        }
        serialized = json.dumps(payload, sort_keys=True, ensure_ascii=True)
        return hashlib.sha256(serialized.encode("utf-8")).hexdigest()

    def package_serialized_size_bytes(self) -> int:
        """Returns the serialized JSON byte size of the package."""
        import json
        return len(json.dumps(self.model_dump(), ensure_ascii=True).encode("utf-8"))


class UserVisibleContentPolicy:
    """Enforces boardroom-ready language and purges internal governance metadata.
    
    Principles:
    1. Normal Business Decks: OMIT internal architecture metadata entirely.
       Do NOT invent replacement business phrases or semantic euphemisms
       (e.g., do NOT replace 'SDR' with 'Strategic Diagnostic' or 'JoinPlan' with 'Relational Model').
       Remove internal metadata and reconstruct clean business sentences from the underlying
       factual content.
    2. Technical Architecture Decks: PRESERVE authentic technical terminology verbatim
       (e.g., SDR, JoinPlan, EVID, RAG architecture, evidence ledger, pipeline audit).
       Never alter or rename requested technical words.
    3. Semantic Substitutions that alter meaning: ZERO (0).
    """

    EXEMPT_PATTERNS = [
        re.compile(r"technical\s+architecture", re.IGNORECASE),
        re.compile(r"data\s+pipeline\s+governance", re.IGNORECASE),
        re.compile(r"internal\s+data\s+engineering", re.IGNORECASE),
        re.compile(r"\barchitecture\s+audit\b", re.IGNORECASE),
        re.compile(r"\bgovernance\s+review\b", re.IGNORECASE),
        re.compile(r"\brag\s+architecture\b", re.IGNORECASE),
        re.compile(r"\bevidence\s+architecture\b", re.IGNORECASE),
        re.compile(r"\bjoinplan\s+audit\b", re.IGNORECASE),
        re.compile(r"\bsdr\s+audit\b", re.IGNORECASE),
    ]

    # Prepositional / relational phrases wrapping internal metadata to strip cleanly
    INTERNAL_METADATA_PHRASES: list[re.Pattern[str]] = [
        re.compile(r"\b(?:per|via|backed by|verified by|grounded in|derived via|according to|from)\s+SDR(?:-[0-9]+)?\b", re.IGNORECASE),
        re.compile(r"\b(?:per|via|backed by|verified by|grounded in|derived via|according to|from)\s+JoinPlan\b", re.IGNORECASE),
        re.compile(r"\b(?:per|via|backed by|verified by|grounded in|derived via|according to|from)\s+JoinGraph\b", re.IGNORECASE),
        re.compile(r"\b(?:per|via|backed by|verified by|grounded in|derived via|according to|from|with)\s+EVID-[a-zA-Z0-9_-]+\b", re.IGNORECASE),
        re.compile(r"\b(?:with\s+checksum|hash|checksum:?)\s+[a-f0-9]{32,64}\b", re.IGNORECASE),
        re.compile(r"\b(?:in|by|via)\s+Control\s+Plane\b", re.IGNORECASE),
        re.compile(r"\b(?:via|by)\s+Orchestrator\s+Task\s+ID[:\s]*[a-zA-Z0-9_-]*\b", re.IGNORECASE),
    ]

    # Standalone internal tokens to remove without replacement
    INTERNAL_METADATA_TOKENS: list[re.Pattern[str]] = [
        re.compile(r"\bSDR(?:-[0-9]+)?\b:?", re.IGNORECASE),
        re.compile(r"\bJoinPlan\b:?", re.IGNORECASE),
        re.compile(r"\bJoinGraph\b:?", re.IGNORECASE),
        re.compile(r"\bEVID-[a-zA-Z0-9_-]+\b:?", re.IGNORECASE),
        re.compile(r"\bEvidence\s+ID:?\b", re.IGNORECASE),
        re.compile(r"\b[a-f0-9]{32,64}\b", re.IGNORECASE),
        re.compile(r"\bControl\s+Plane\b", re.IGNORECASE),
        re.compile(r"\bOrchestrator\s+Task\s+ID:?\b", re.IGNORECASE),
        re.compile(r"\bPrompt\s+template\b", re.IGNORECASE),
        re.compile(r"\bmodel\s+internal[s]?\b", re.IGNORECASE),
    ]

    FORBIDDEN_DETECTION_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
        ("SDR reference", re.compile(r"\bSDR(?:-[0-9]+)?\b", re.IGNORECASE)),
        ("JoinPlan reference", re.compile(r"\bJoinPlan\b", re.IGNORECASE)),
        ("JoinGraph reference", re.compile(r"\bJoinGraph\b", re.IGNORECASE)),
        ("Evidence ID", re.compile(r"\bEVID-[a-zA-Z0-9_-]+\b", re.IGNORECASE)),
        ("Evidence ID label", re.compile(r"\bEvidence\s+ID\b", re.IGNORECASE)),
        ("Artifact Checksum/Hash", re.compile(r"\b[a-f0-9]{32,64}\b", re.IGNORECASE)),
        ("Control Plane", re.compile(r"\bControl\s+Plane\b", re.IGNORECASE)),
        ("Orchestrator Task ID", re.compile(r"\bOrchestrator\s+Task\s+ID\b", re.IGNORECASE)),
        ("Prompt template", re.compile(r"\bPrompt\s+template\b", re.IGNORECASE)),
    ]

    @classmethod
    def is_governance_exempt(cls, objective: str | None, instructions: str | None = None) -> bool:
        """Checks if the user explicitly requested a technical governance or architecture presentation."""
        combined = f"{objective or ''} {instructions or ''}".strip()
        if not combined:
            return False
        return any(pattern.search(combined) for pattern in cls.EXEMPT_PATTERNS)

    @classmethod
    def detect_violations(cls, text: str, allow_governance: bool = False) -> list[str]:
        """Detects any internal governance terms that violate user-facing policy."""
        if allow_governance or not text:
            return []
        violations = []
        for name, pattern in cls.FORBIDDEN_DETECTION_PATTERNS:
            matches = pattern.findall(text)
            if matches:
                violations.append(f"{name}: {', '.join(matches[:3])}")
        return violations

    @classmethod
    def sanitize_text(cls, text: str, allow_governance: bool = False) -> str:
        """Sanitizes text by omitting internal architecture metadata rather than euphemizing it.
        
        When allow_governance is True (technical decks), terms are preserved accurately.
        When allow_governance is False (business decks), terms are removed completely.
        """
        if allow_governance or not text:
            return text or ""

        sanitized = text

        # 1. Strip contextual phrases with prepositions first
        for phrase_pat in cls.INTERNAL_METADATA_PHRASES:
            sanitized = phrase_pat.sub("", sanitized)

        # 2. Strip standalone internal tokens
        for token_pat in cls.INTERNAL_METADATA_TOKENS:
            sanitized = token_pat.sub("", sanitized)

        # 3. Clean up syntax and punctuation left by removals
        # Remove empty parentheses/brackets e.g. "()" or "[]" or "( )"
        sanitized = re.sub(r"\(\s*\)", "", sanitized)
        sanitized = re.sub(r"\[\s*\]", "", sanitized)
        # Collapse multiple spaces / tabs
        sanitized = re.sub(r"[ \t]+", " ", sanitized)
        # Clean hanging prepositions before punctuation e.g. "with ." or "via ."
        sanitized = re.sub(r"\b(?:per|via|with|backed by|from|in)\s*([.,;])", r"\1", sanitized, flags=re.IGNORECASE)
        # Clean double punctuation e.g. ", ," or ".. " or " ,"
        sanitized = re.sub(r",\s*,+", ",", sanitized)
        sanitized = re.sub(r"\s+([.,;:!?])", r"\1", sanitized)
        sanitized = re.sub(r"\.+", ".", sanitized)
        sanitized = re.sub(r"^[:\s,.-]+", "", sanitized)
        sanitized = re.sub(r"[:\s,.-]+$", "", sanitized)

        return sanitized.strip()

    @classmethod
    def sanitize_content_item(
        cls,
        item: PresentationContentItem,
        allow_governance: bool = False
    ) -> PresentationContentItem:
        """Sanitizes all user-visible presentation text fields of a content item."""
        if allow_governance:
            return item

        item.title = cls.sanitize_text(item.title, allow_governance) or item.title
        if item.subtitle:
            cleaned_sub = cls.sanitize_text(item.subtitle, allow_governance)
            item.subtitle = cleaned_sub if cleaned_sub else None
        if item.narrative_takeaway:
            item.narrative_takeaway = cls.sanitize_text(item.narrative_takeaway, allow_governance)
        
        clean_bullets = []
        for b in item.supporting_bullets:
            cb = cls.sanitize_text(b, allow_governance)
            if cb:
                clean_bullets.append(cb)
        item.supporting_bullets = clean_bullets

        if item.metric_label:
            cleaned_lbl = cls.sanitize_text(item.metric_label, allow_governance)
            item.metric_label = cleaned_lbl if cleaned_lbl else item.metric_name or "Metric"
        if item.metric_value:
            item.metric_value = cls.sanitize_text(item.metric_value, allow_governance)

        return item

    @classmethod
    def validate_content_item(
        cls,
        item: PresentationContentItem,
        allow_governance: bool = False
    ) -> list[str]:
        """Validates all user-visible fields and returns any policy violations."""
        if allow_governance:
            return []
        violations = []
        for field_name, value in [
            ("title", item.title),
            ("subtitle", item.subtitle),
            ("narrative_takeaway", item.narrative_takeaway),
            ("metric_label", item.metric_label),
            ("metric_value", item.metric_value),
        ]:
            if value:
                v = cls.detect_violations(value, allow_governance)
                if v:
                    violations.append(f"Field '{field_name}' violated policy ({'; '.join(v)})")
        for idx, bullet in enumerate(item.supporting_bullets):
            v = cls.detect_violations(bullet, allow_governance)
            if v:
                violations.append(f"Bullet #{idx+1} violated policy ({'; '.join(v)})")
        return violations
