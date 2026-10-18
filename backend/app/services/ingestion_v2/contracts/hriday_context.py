"""
HighView Ingestion V2 — Phase I8.3 HRIDAY Normalized Context Contract
Stage: HRIDAY Controlled V2 Cutover
Defines the normalized context envelope consumed by HRIDAY.
Enforces epistemic boundaries: preserves canonical grains, denominators, formulas,
JoinPlans, and evidence references. Zero metric fabrication or hallucinated facts.
"""

from __future__ import annotations

from typing import Any
from pydantic import BaseModel, ConfigDict, Field

from app.services.ingestion_v2.contracts.cutover import (
    ConsumerRouteDecision,
    Route,
)


class RetrievedEvidenceItem(BaseModel):
    """Normalized evidence record from either V1 hybrid chunks or V2 multi-namespace retrieval."""
    model_config = ConfigDict(extra="forbid", frozen=True)

    evidence_id: str                      # Canonical EVID-... or V1 chunk id
    namespace: str                        # RAW_SCHEMA, SEMANTIC, RELATIONSHIP, ANALYTICAL, or V1_CHUNK
    title: str
    content: str
    relevance_score: float = 1.0
    source_sheet: str | None = None
    row_index: int | None = None
    entity_grain: str | None = None
    provenance: dict[str, Any] = Field(default_factory=dict)


class GovernedMetricContext(BaseModel):
    """Governed metric definition ensuring frozen formulas, grains, and denominators."""
    model_config = ConfigDict(extra="forbid", frozen=True)

    metric_id: str
    metric_name: str
    formula: str
    grain: str
    unit: str = ""
    denominator: str | None = None
    population: str | None = None
    source_table: str | None = None
    is_ambiguous: bool = False
    ambiguity_rationale: str | None = None


class GovernedJoinContext(BaseModel):
    """Governed join relationship ensuring SAFE execution and blocking UNSAFE / AMBIGUOUS joins."""
    model_config = ConfigDict(extra="forbid", frozen=True)

    join_plan_id: str
    left_table: str
    right_table: str
    join_type: str
    join_safety: str                      # SAFE, SAFE_WITH_PREAGGREGATION, UNSAFE, AMBIGUOUS
    requires_preaggregation: bool = False
    grain_warning: str | None = None


class HridayNormalizedContext(BaseModel):
    """
    Normalized, evidence-grounded context envelope delivered to HRIDAY reasoning.
    Acts as the single context contract regardless of whether Route.V1 or Route.V2 was resolved.
    """
    model_config = ConfigDict(extra="forbid", frozen=True)

    route_selected: Route                 # Route.V1 or Route.V2
    dataset_id: str | int | None = None
    dataset_version: str | None = None
    manifest_fingerprint: str | None = None
    semantic_graph_fingerprint: str | None = None

    evidence_items: list[RetrievedEvidenceItem] = Field(default_factory=list)
    metrics: list[GovernedMetricContext] = Field(default_factory=list)
    join_plans: list[GovernedJoinContext] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    reliability_notes: list[str] = Field(default_factory=list)

    # Formatted prompt blocks consumed directly by existing HRIDAY prompt builder
    catalog_summary_text: str = ""
    evidence_samples_json: list[dict[str, Any]] = Field(default_factory=list)
    temporal_cadence_text: str = ""
    domain_guideline_text: str = ""

    # Governed provenance
    route_decision: ConsumerRouteDecision
    telemetry: dict[str, Any] = Field(default_factory=dict)

    @property
    def is_v2(self) -> bool:
        """Returns True if Route.V2 was selected by the Gateway."""
        return self.route_selected == Route.V2

