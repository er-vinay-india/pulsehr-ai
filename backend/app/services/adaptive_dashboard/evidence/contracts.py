"""Governed Evidence and Claim Contracts.

Defines the typed representations for:
- AnalyticalFact: Raw calculated analytical statement before governance binding.
- BoundEvidence / EvidenceItem: The immutable evidence node in the evidence store.
- BoundFact: An analytical fact verified and bound to an evidence node and topic.
- EvidenceBinding: Container linking topic, dataset, and evidence graph nodes.
- StructuredClaim / GovernedAuditReport / GovernedAgentResponse: Agent claims and audits.
"""
from __future__ import annotations

import re
from typing import Any, Literal
from pydantic import BaseModel, ConfigDict, Field


class AnalyticalFact(BaseModel):
    """Raw, calculated analytical statement prior to evidence binding and governance authorization."""
    model_config = ConfigDict(extra="ignore")

    fact_id: str
    dataset_id: int
    sheet_id: int | None = None
    subject: str
    metric: str
    value: float | int | None = None
    formatted_value: str
    unit: str | None = None
    comparison_value: float | int | None = None
    difference_pct: float | None = None
    population: int = 0
    period: str | None = None
    dimension: str | None = None
    grain: str = "aggregate"  # e.g., "employee", "department", "aggregate"
    calculation_method: str = ""
    allowed_claim_level: str = "descriptive_fact"
    confidence: Literal["HIGH", "MEDIUM", "LOW"] = "HIGH"
    provenance_snapshot: str = ""
    source_table: str = "sheet_curated_rows"
    tokens: dict[str, Any] = Field(default_factory=dict)
    limitations: list[str] = Field(default_factory=list)


class BoundEvidence(BaseModel):
    """Governed evidence unit bound to immutable data calculations and provenance."""
    model_config = ConfigDict(extra="ignore")

    evidence_id: str  # e.g., "EVID-001", "EVID-HERO-99747", "CTX-POLICY-01", "SCEN-001"
    claim_type: Literal[
        "segment_difference",
        "trend_change",
        "concentration",
        "outlier",
        "distribution_skew",
        "capacity_gap",
        "backlog_aging",
        "retention_decay",
        "target_gap",
        "general_fact",
    ] = "general_fact"
    subject: str
    metric: str
    value: float | int | None = None
    formatted_value: str
    comparison_value: float | int | None = None
    formatted_comparison: str | None = None
    difference_pct: float | None = None
    population: int = 0
    period: str | None = None
    source_table: str = "sheet_curated_rows"
    calculation: str = ""
    confidence: Literal["HIGH", "MEDIUM", "LOW"] = "HIGH"
    causal_classification: Literal["OBSERVED", "ASSOCIATED", "INFERRED", "COUNTERFACTUAL", "HYPOTHESIS"] = "OBSERVED"
    sample_warning: bool = False
    provenance: str = ""
    tokens: dict[str, Any] = Field(default_factory=dict)
    supporting_evidence_ids: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)

    # Lineage and governance attributes
    dataset_id: int | None = None
    sheet_id: int | None = None
    topic_id: str | None = None
    grain: str = "aggregate"  # e.g., "employee", "department", "store", "location", "aggregate"
    namespace: Literal["EVID", "CTX", "SCEN"] = "EVID"


# Backwards-compatible alias
EvidenceItem = BoundEvidence


class UnresolvedTemplateTokenValidator:
    """Permanent QA guard preventing raw template tokens from ever reaching the UI."""

    PATTERN = re.compile(r"\{[a-zA-Z0-9_]+\}")

    @classmethod
    def validate_and_sanitize(cls, text: str, fallback: str = "") -> str:
        """Sanitizes text by eliminating any residual placeholders and cleaning whitespace."""
        if not text:
            return fallback
        if not cls.PATTERN.search(text):
            return text
        cleaned = cls.PATTERN.sub("", text).strip()
        cleaned = re.sub(r"\s+", " ", cleaned)
        cleaned = re.sub(r"\s+([.,;:!?])", r"\1", cleaned)
        return cleaned if cleaned else fallback


class EvidenceGraph(BaseModel):
    """Governed graph of verified evidence objects for a dataset sheet."""
    model_config = ConfigDict(extra="ignore")

    sheet_id: int
    snapshot: str
    nodes: list[BoundEvidence] = Field(default_factory=list)

    def get_by_id(self, evidence_id: str) -> BoundEvidence | None:
        """Fetch node by EVID ID."""
        for item in self.nodes:
            if item.evidence_id == evidence_id:
                return item
        return None

    def get_node(self, evidence_id: str) -> BoundEvidence | None:
        """Alias for get_by_id."""
        return self.get_by_id(evidence_id)

    def add_node(self, item: BoundEvidence) -> None:
        """Add an evidence item node to the graph."""
        self.nodes.append(item)

    def find_by_subject_or_metric(self, query: str) -> list[BoundEvidence]:
        """Find evidence items matching subject or metric."""
        q = query.lower()
        return [
            item for item in self.nodes
            if q in item.subject.lower() or q in item.metric.lower()
        ]

    def hydrate_template(self, template: str, evidence_ids: list[str]) -> str:
        """Deterministically hydrates a narrative template using tokens from referenced evidence IDs."""
        if not evidence_ids:
            return UnresolvedTemplateTokenValidator.validate_and_sanitize(template)

        primary = self.get_by_id(evidence_ids[0])
        if not primary:
            return UnresolvedTemplateTokenValidator.validate_and_sanitize(template)

        token_dict: dict[str, Any] = {
            "subject": primary.subject,
            "metric": primary.metric,
            "value": primary.value,
            "formatted_value": primary.formatted_value,
            "difference_pct": f"{primary.difference_pct:+.1f}" if primary.difference_pct is not None else "0",
            "population": f"{primary.population:,}" if isinstance(primary.population, (int, float)) else str(primary.population),
            "calculation": primary.calculation,
            "confidence": primary.confidence,
            "comparison": primary.tokens.get("comparison", "organization baseline"),
            **primary.tokens,
        }

        rendered = template
        for k, v in token_dict.items():
            placeholder = f"{{{k}}}"
            if placeholder in rendered:
                rendered = rendered.replace(placeholder, str(v) if v is not None else "")
        return UnresolvedTemplateTokenValidator.validate_and_sanitize(
            rendered,
            fallback=f"{primary.subject} established at {primary.formatted_value}",
        )



class BoundFact(BaseModel):
    """Analytical fact verified and bound to an immutable evidence node and topic."""
    model_config = ConfigDict(extra="ignore")

    fact: AnalyticalFact
    evidence: BoundEvidence
    topic_id: str
    bound_at: str | None = None
    citation_tokens: dict[str, Any] = Field(default_factory=dict)


class EvidenceBinding(BaseModel):
    """Binding specification connecting a presentation topic to verified evidence nodes."""
    model_config = ConfigDict(extra="ignore")

    topic_id: str
    dataset_id: int
    primary_evidence_id: str
    supporting_evidence_ids: list[str] = Field(default_factory=list)
    bound_facts: list[BoundFact] = Field(default_factory=list)
    grain: str = "aggregate"


class StructuredClaim(BaseModel):
    """Governed atomic claim linked to verified evidence nodes."""
    model_config = ConfigDict(extra="ignore")

    claim_id: str
    claim_text: str
    evidence_ids: list[str] = Field(default_factory=list)
    causal_type: Literal["OBSERVED", "ASSOCIATED", "INFERRED", "COUNTERFACTUAL", "HYPOTHESIS", "CAUSAL"] = "OBSERVED"
    topic_id: str | None = None
    dataset_id: int | None = None


class GovernedAuditReport(BaseModel):
    """Audited telemetry report verifying response integrity."""
    model_config = ConfigDict(extra="ignore")

    grounding_validation: Literal["PASSED", "WARNING", "FAILED"]
    evidence_coverage_pct: float
    unsupported_claims_count: int
    numeric_reconciliation: Literal["PASSED", "FAILED"]
    causal_violations: list[str] = Field(default_factory=list)
    evidence_ids_cited: list[str] = Field(default_factory=list)
    scenario_ids_cited: list[str] = Field(default_factory=list)
    namespace_violations: list[str] = Field(default_factory=list)


class GovernedAgentResponse(BaseModel):
    """Authoritative structured output format for Copilot, Council, and Narrative agents."""
    model_config = ConfigDict(extra="ignore")

    answer: str
    claims: list[StructuredClaim] = Field(default_factory=list)
    audit: GovernedAuditReport
