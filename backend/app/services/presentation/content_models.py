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
from typing import Any, Literal
from pydantic import BaseModel, Field, model_validator


class VisualStrategy(str, Enum):
    """Typed visual reuse strategy for presentation content."""
    REUSE_EXISTING = "REUSE_EXISTING"
    PRESENTATION_RECOMMENDATION = "PRESENTATION_RECOMMENDATION"


class VisualCompleteness(str, Enum):
    """Semantic completeness of an analytical visual representation.
    
    COMPLETE_VISUAL communicates the full analytical relationship on a single slide.
    DETAIL_VISUAL provides detailed partition/tabular breakdown.
    """
    COMPLETE_VISUAL = "COMPLETE_VISUAL"
    DETAIL_VISUAL = "DETAIL_VISUAL"


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
    visual_id: str | None = Field(default=None, description="Stable identifier of the source visual (e.g. topic_id or visual UUID)")
    source_surface: Literal["dashboard", "data_explorer"] | str = Field(default="dashboard", description="Originating analytical surface")
    visual_strategy: VisualStrategy = Field(default=VisualStrategy.PRESENTATION_RECOMMENDATION, description="Visual strategy: REUSE_EXISTING or PRESENTATION_RECOMMENDATION")
    visual_completeness: VisualCompleteness = Field(default=VisualCompleteness.COMPLETE_VISUAL, description="Visual completeness: COMPLETE_VISUAL communicates full relationship; DETAIL_VISUAL provides slice/tabular depth")
    visual_type: str | None = Field(default=None, description="Visual spec type (e.g. choropleth, scatter, box_plot, etc.)")
    source_data_reference: dict[str, Any] | str | None = Field(default=None, description="Pointer to source dataset, sheet, metric, and dimension")
    kind: ContentKind = Field(description="Content visual type (chart, table, kpi, etc.)")
    role: ContentRole = Field(description="Narrative role (hero, kpi, key finding, etc.)")
    topic_category: str = Field(description="Business topic category, e.g. Regional Growth")
    title: str = Field(description="Business presentation headline")
    subtitle: str | None = Field(default=None, description="Optional presentation subtitle")
    takeaway: str = Field(default="", description="Executive takeaway summary")
    
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
    presentation_visual_spec: Any = Field(default=None, description="Authoritative PresentationVisualSpec instance or dump")
    table_data: list[dict[str, Any]] | None = Field(default=None, description="Governed tabular data partition")
    metric_value: str | None = Field(default=None, description="Formatted KPI string, e.g. '1.21B' or '17.7%'")
    metric_label: str | None = Field(default=None, description="Business metric label")
    media_url: str | None = Field(default=None, description="URL for image/video media")
    poster_image_url: str | None = Field(default=None, description="High-DPI poster image for static fallback")

    # Governed provenance (strictly isolated from user-visible presentation text)
    evidence_ids: list[str] = Field(default_factory=list)
    fact_id: str | None = None
    topic_id: str | None = None
    semantic_hash: str | None = None
    source_dataset_id: int | str | None = None
    source_sheet_name: str | None = None
    dimension_name: str | None = None
    metric_name: str | None = None
    unit: str | None = None
    grain: str | None = None
    denominator: str | None = None

    @model_validator(mode="before")
    @classmethod
    def sync_item_attributes(cls, data: Any) -> Any:
        if isinstance(data, dict):
            # 1. Sync takeaway and narrative_takeaway
            if not data.get("takeaway") and data.get("narrative_takeaway"):
                data["takeaway"] = data["narrative_takeaway"]
            elif not data.get("narrative_takeaway") and data.get("takeaway"):
                data["narrative_takeaway"] = data["takeaway"]
            # 2. Derive visual_type and visual_id from visual_spec if missing
            v_spec = data.get("visual_spec") or {}
            if isinstance(v_spec, dict):
                if not data.get("visual_id"):
                    data["visual_id"] = v_spec.get("topic_id") or data.get("content_id")
                if not data.get("visual_type"):
                    data["visual_type"] = v_spec.get("chart_type") or v_spec.get("map_type") or v_spec.get("visual_morphology")
            elif not data.get("visual_type") and data.get("kind"):
                data["visual_type"] = data["kind"].value if isinstance(data["kind"], Enum) else str(data["kind"])

            # 3. Determine visual_strategy per Stage 2 rule:
            # if visual_spec exists (or table_data for tables) AND visual_id exists AND source_surface in ("dashboard", "data_explorer"):
            #     visual_strategy = REUSE_EXISTING
            # otherwise:
            #     visual_strategy = PRESENTATION_RECOMMENDATION
            if not data.get("visual_strategy"):
                has_spec = bool(data.get("visual_spec") or data.get("table_data") or data.get("visual_type") == "table")
                has_vid = bool(data.get("visual_id"))
                surf = str(data.get("source_surface") or "").lower()
                if has_spec and has_vid and surf in ("dashboard", "data_explorer"):
                    data["visual_strategy"] = VisualStrategy.REUSE_EXISTING
                else:
                    data["visual_strategy"] = VisualStrategy.PRESENTATION_RECOMMENDATION

            # 4. Determine visual_completeness per Stage 4 rule:
            # tables are DETAIL_VISUAL; analytical visuals (choropleth, box_plot, scatter, variance_bar, bullet, etc.) are COMPLETE_VISUAL
            if not data.get("visual_completeness"):
                k = data.get("kind")
                vtype = data.get("visual_type")
                role = data.get("role")
                if (
                    k == ContentKind.TABLE
                    or vtype == "table"
                    or role == ContentRole.EXPLORATORY_TABLE
                ):
                    data["visual_completeness"] = VisualCompleteness.DETAIL_VISUAL
                else:
                    data["visual_completeness"] = VisualCompleteness.COMPLETE_VISUAL
        return data


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
        re.compile(r"\b(?:per|via|backed by|verified by|grounded in|derived via|according to|from|with)\s+TOPIC-[a-zA-Z0-9_-]+\b", re.IGNORECASE),
        re.compile(r"\b(?:per|via|with|backed by|verified by|grounded in)\s+Governed\s+Topics\b", re.IGNORECASE),
        re.compile(r"\b(?:per|via|with|backed by|verified by|grounded in)\s+Complete\s+Coverage\b", re.IGNORECASE),
        re.compile(r"\b(?:per|via|with|backed by|verified by|grounded in)\s+zero\s+raw-column\s+interpolation\b", re.IGNORECASE),
        re.compile(r"\b(?:with\s+checksum|hash|checksum:?)\s+[a-f0-9]{32,64}\b", re.IGNORECASE),
        re.compile(r"\b(?:in|by|via)\s+Control\s+Plane\b", re.IGNORECASE),
        re.compile(r"\b(?:in|by|via)\s+(?:data\s+pipeline|ingestion\s+pipeline|pipeline\s+audit)\b", re.IGNORECASE),
        re.compile(r"\b(?:via|by)\s+Orchestrator\s+Task\s+ID[:\s]*[a-zA-Z0-9_-]*\b", re.IGNORECASE),
        re.compile(r"\b(?:in|during|per)\s+(?:Phase\s+\d+:\s+[a-zA-Z\s]+|evidence_audit|brief_setup|preflight_validation)\b", re.IGNORECASE),
    ]

    # Standalone internal tokens to remove without replacement
    INTERNAL_METADATA_TOKENS: list[re.Pattern[str]] = [
        re.compile(r"\bSDR(?:-[0-9]+)?\b:?", re.IGNORECASE),
        re.compile(r"\bJoinPlan\b:?", re.IGNORECASE),
        re.compile(r"\bJoinGraph\b:?", re.IGNORECASE),
        re.compile(r"\bEvidence\s+EVID-[a-zA-Z0-9_-]+\b:?", re.IGNORECASE),
        re.compile(r"\bEVID-[a-zA-Z0-9_-]+\b:?", re.IGNORECASE),
        re.compile(r"\bTopic\s+TOPIC-[a-zA-Z0-9_-]+\b:?", re.IGNORECASE),
        re.compile(r"\bTOPIC-[a-zA-Z0-9_-]+\b:?", re.IGNORECASE),
        re.compile(r"\bEvidence\s+ID:?\b", re.IGNORECASE),
        re.compile(r"\bTopic\s+ID:?\b", re.IGNORECASE),
        re.compile(r"\bGoverned\s+Topics\b:?", re.IGNORECASE),
        re.compile(r"\bGoverned\s+Boardroom\s+Strategic\s+Diagnostic\b:?", re.IGNORECASE),
        re.compile(r"\bGoverned\b:?", re.IGNORECASE),
        re.compile(r"\bComplete\s+Coverage\b:?", re.IGNORECASE),
        re.compile(r"\bzero\s+raw-column\s+interpolation\b:?", re.IGNORECASE),
        re.compile(r"\bSnapshot(?:\s+hash)?[:\s]*[a-f0-9]{4,64}\b", re.IGNORECASE),
        re.compile(r"\bSnapshot\b:?", re.IGNORECASE),
        re.compile(r"\bRecorded\s+data\b:?", re.IGNORECASE),
        re.compile(r"\b[a-f0-9]{32,64}\b", re.IGNORECASE),
        re.compile(r"\bControl\s+Plane\b", re.IGNORECASE),
        re.compile(r"\b(?:data\s+pipeline|ingestion\s+pipeline|pipeline\s+audit|\bpipeline\b)", re.IGNORECASE),
        re.compile(r"\b(?:Phase\s+\d+:\s+[a-zA-Z\s]+|evidence_audit|brief_setup|preflight_validation)\b", re.IGNORECASE),
        re.compile(r"\bOrchestrator\s+Task\s+ID:?\b", re.IGNORECASE),
        re.compile(r"\bPrompt\s+template\b", re.IGNORECASE),
        re.compile(r"\bmodel\s+internal[s]?\b", re.IGNORECASE),
    ]

    FORBIDDEN_DETECTION_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
        ("SDR reference", re.compile(r"\bSDR(?:-[0-9]+)?\b", re.IGNORECASE)),
        ("JoinPlan reference", re.compile(r"\b(?:JoinPlan|JoinGraph)\b", re.IGNORECASE)),
        ("Evidence ID", re.compile(r"\b(?:EVID-[a-zA-Z0-9_-]+|Evidence\s+ID)\b", re.IGNORECASE)),
        ("Topic ID", re.compile(r"\b(?:TOPIC-[a-zA-Z0-9_-]+|Topic\s+ID)\b", re.IGNORECASE)),
        ("Governed Topics", re.compile(r"\bGoverned\s+Topics\b", re.IGNORECASE)),
        ("Governed Boardroom Strategic Diagnostic", re.compile(r"\bGoverned\s+Boardroom\s+Strategic\s+Diagnostic\b", re.IGNORECASE)),
        ("Complete Coverage", re.compile(r"\bComplete\s+Coverage\b", re.IGNORECASE)),
        ("Zero raw-column interpolation", re.compile(r"\bzero\s+raw-column\s+interpolation\b", re.IGNORECASE)),
        ("Snapshot hash", re.compile(r"\bSnapshot(?:\s+hash)?[:\s]*[a-f0-9]{4,64}\b", re.IGNORECASE)),
        ("Artifact Checksum/Hash", re.compile(r"\b[a-f0-9]{32,64}\b", re.IGNORECASE)),
        ("Control Plane", re.compile(r"\bControl\s+Plane\b", re.IGNORECASE)),
        ("Pipeline reference", re.compile(r"\b(?:data\s+pipeline|ingestion\s+pipeline|pipeline\s+audit|\bpipeline\b)", re.IGNORECASE)),
        ("Validation Phase", re.compile(r"\b(?:Phase\s+\d+:\s+[a-zA-Z\s]+|evidence_audit|brief_setup|preflight_validation)\b", re.IGNORECASE)),
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

        # 3. Clean duplicate units (e.g. "67.2% %", "33,634,860 units units", "people/sq. km people/sq. km")
        sanitized = re.sub(r"people/sq\.?\s*km(?:\s+people/sq\.?\s*km)+", "people/sq. km", sanitized, flags=re.IGNORECASE)
        sanitized = re.sub(r"([%]|(?:\b(?:units|people/sq\.?\s*km|days|hrs|pct)\b))\s+\1", r"\1", sanitized, flags=re.IGNORECASE)
        sanitized = re.sub(r"(\bunits\b)\s+\1", r"\1", sanitized, flags=re.IGNORECASE)
        sanitized = re.sub(r"(\bpeople/sq\.?\s*km\b)\s+\1", r"\1", sanitized, flags=re.IGNORECASE)
        sanitized = re.sub(r"(%)\s+%", "%", sanitized)

        # 3b. Correct correlation interpretation thresholds (e.g. |r| < 0.1 is Negligible)
        def _fix_corr(m):
            val_str = m.group(1)
            try:
                r_f = float(val_str)
                if abs(r_f) < 0.1:
                    strength = "Negligible"
                elif abs(r_f) < 0.3:
                    strength = "Weak"
                elif abs(r_f) < 0.7:
                    strength = "Moderate"
                else:
                    strength = "Strong"
                return f"r = {val_str} ({strength} association)"
            except Exception:
                return m.group(0)

        sanitized = re.sub(r"r\s*=\s*([+-]?\d+(?:\.\d+)?)\s*\((?:Moderate|Strong|Weak|Negligible)?\s*association\)", _fix_corr, sanitized, flags=re.IGNORECASE)

        # 3c. Clean up awkward performance benchmark phrasing for non-performance/demographic data
        def _fmt_bench_num(n_str):
            try:
                clean_n = float(n_str.replace(",", ""))
                if abs(clean_n) >= 1_000_000:
                    return f"{clean_n / 1_000_000:.1f}M"
                if abs(clean_n) >= 1_000:
                    return f"{clean_n / 1_000:.1f}K"
                return f"{clean_n:,.0f}"
            except Exception:
                return n_str

        def _fix_benchmark(m):
            lead_entity = m.group(1).strip()
            bench_num = m.group(2).strip()
            fmt_b = _fmt_bench_num(bench_num)
            if any(term in lead_entity.lower() for term in ("uttar pradesh", "delhi", "state", "territory", "district", "bihar", "maharashtra")):
                return f"{lead_entity} is well above the state population benchmark of {fmt_b}."
            return f"{lead_entity} is well above the cohort benchmark of {fmt_b}."

        sanitized = re.sub(
            r"(\b[A-Z][\w\s]+?)\s+leads performance against the\s+([\d,]+(?:\.\d+)?)\s*(?:units)?\s*cohort benchmark\.?",
            _fix_benchmark,
            sanitized,
            flags=re.IGNORECASE
        )

        # 4. Clean up syntax and punctuation left by removals
        # Remove empty parentheses/brackets e.g. "()" or "[]" or "(, )" or "( )"
        sanitized = re.sub(r"\(\s*[,;\s]*\)", "", sanitized)
        sanitized = re.sub(r"\[\s*[,;\s]*\]", "", sanitized)
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
        if item.takeaway:
            item.takeaway = cls.sanitize_text(item.takeaway, allow_governance)
        if item.takeaway and not item.narrative_takeaway:
            item.narrative_takeaway = item.takeaway
        elif item.narrative_takeaway and not item.takeaway:
            item.takeaway = item.narrative_takeaway
        
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
            ("takeaway", item.takeaway),
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
