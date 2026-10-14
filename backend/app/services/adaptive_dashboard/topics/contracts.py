"""Analytical Story & ExecutiveTopic Contracts (Phase G5.5).

Defines strongly typed contracts for analytical story assembly and immutable ExecutiveTopic creation:
- TopicIdentitySeed: Pure deterministic input for semantic topic identity derivation.
- TopicIdentityFactory: Pure function deriving stable, non-monotonic topic identifiers.
- ExecutiveTopicDraft: Pre-assembly specification bundling verified narrative, bound evidence, and semantic intent.
- ExecutiveTopic: The immutable Level-1 executive decision topic.
"""
from __future__ import annotations

import hashlib
from typing import Any, Literal
from pydantic import BaseModel, ConfigDict, Field


class TopicIdentitySeed(BaseModel):
    """Pure, immutable seed for deterministic semantic topic identification.
    
    Guarantees that topic identity represents semantic ownership, not construction or execution order.
    """
    model_config = ConfigDict(frozen=True, extra="ignore")

    dataset_id: int | str
    dataset_version: int = 1
    domain: str = "general"
    analytical_intent: str
    entity_grain: str | None = None
    metric_family: str = "general"
    measure_ids: list[str] = Field(default_factory=list)
    dimension_ids: list[str] = Field(default_factory=list)
    opportunity_id: str | None = None

    @property
    def semantic_topic_key(self) -> str:
        """Version-independent semantic key identifying logical topic across dataset versions."""
        grain_suffix = f":{self.entity_grain.lower()}" if self.entity_grain else ""
        return f"{self.domain.lower()}:{self.analytical_intent.lower()}{grain_suffix}:{self.metric_family.lower()}"


class TopicIdentityFactory:
    """Pure functional factory for generating deterministic, semantic topic IDs.

    Guarantees:
    - Pure function: zero global state, zero counters, zero threads/sequence coupling.
    - Dataset scoped: distinct datasets yield distinct topic IDs.
    - Version scoped: distinct versions yield distinct topic IDs.
    - Ordering invariant: portfolio order does not affect topic ID.
    - Insertion invariant: inserting adjacent topics does not shift existing IDs.
    """

    @staticmethod
    def create_topic_id(seed: TopicIdentitySeed) -> str:
        """Derives a deterministic, version-scoped semantic topic ID."""
        canonical_parts = [
            f"ds:{seed.dataset_id}",
            f"v:{seed.dataset_version}",
            f"dom:{seed.domain.lower().strip()}",
            f"intent:{seed.analytical_intent.upper().strip()}",
            f"grain:{(seed.entity_grain or '').upper().strip()}",
            f"fam:{seed.metric_family.lower().strip()}",
            f"meas:{sorted(m.lower().strip() for m in seed.measure_ids if m)}",
            f"dim:{sorted(d.lower().strip() for d in seed.dimension_ids if d)}",
            f"opp:{(seed.opportunity_id or '').strip()}",
        ]
        canonical_str = "|".join(canonical_parts)
        digest = hashlib.sha256(canonical_str.encode("utf-8")).hexdigest()[:8]
        return f"TOPIC-{digest}"


class TopicIdGenerator:
    """Backward-compatible utility and integer index formatter."""

    @staticmethod
    def format_id(index: int) -> str:
        """Returns zero-padded index topic identifier (for legacy callers)."""
        return f"TOPIC-{int(index):03d}"

    @staticmethod
    def parse_index(topic_id: str) -> int:
        """Extracts integer sequence if identifier has numeric suffix."""
        if topic_id.startswith("TOPIC-"):
            raw = topic_id.split("-")[1]
            if raw.isdigit():
                return int(raw)
        return 0


class ExecutiveTopicDraft(BaseModel):
    """Pre-assembly draft bundling narrative, bound evidence, and semantic identity."""
    model_config = ConfigDict(extra="ignore")

    topic_id: str
    semantic_topic_key: str = ""
    display_order: int = 1
    rank: int = 1
    portfolio_position: int = 1
    dataset_id: int | None = None
    dataset_version: int = 1
    domain: str = "general"
    analytical_intent: str = "RANKING"
    entity_grain: str | None = None
    semantic_family: str = "general"
    periods: list[str] = Field(default_factory=list)
    dimensions: list[str] = Field(default_factory=list)
    slot_type: Literal["hero", "supporting", "risk_anomaly", "action_scenario"] = "supporting"
    priority: int = 1
    priority_score: float = 0.5
    confidence: float = 0.90
    business_value: float = 0.5
    statistical_significance: float = 0.5
    recommended_action: str = ""
    key_metric: str = ""
    narrative: dict[str, Any] = Field(default_factory=dict)
    evidence_binding: dict[str, Any] | None = None
    evidence_ids: list[str] = Field(default_factory=list)
    provenance_ids: list[str] = Field(default_factory=list)
    tokens: dict[str, Any] = Field(default_factory=dict)
    source_opportunity_id: str = ""
    inspect_payload: dict[str, Any] = Field(default_factory=dict)
    visual_microcopy: Any | None = None
    spatial_placement: Any | None = None


class ExecutiveTopic(BaseModel):
    """Executive analytical topic synthesizing multiple related candidate insights into a unified visual story.

    Guarantees:
    - Immutable semantic identity, narrative, and evidence.
    - Presentation order is explicitly tracked via display_order, completely distinct from topic_id.
    """
    model_config = ConfigDict(extra="ignore")

    topic_id: str
    semantic_topic_key: str = ""
    display_order: int = 1
    rank: int = 1
    portfolio_position: int = 1
    title: str
    subtitle: str = ""
    slot_type: Literal["hero", "supporting", "risk_anomaly", "action_scenario"] = "supporting"
    dataset_id: int | None = None
    domain: str = "general"
    insight_ids: list[str] = Field(default_factory=list)
    metric_family: str = "general"
    periods: list[str] = Field(default_factory=list)
    dimensions: list[str] = Field(default_factory=list)
    recommended_visual: str = "ranked_bar"
    layout_hint: str = "MEDIUM"
    primary_takeaway: str = ""
    takeaway: str = ""
    recommended_action: str = ""
    evidence_ids: list[str] = Field(default_factory=list)
    evidence_ref: str = ""
    priority: int = 1
    key_metric: str = ""
    analytical_intent: str = "RANKING"
    visual_spec: dict[str, Any] = Field(default_factory=dict)
    inspect_payload: dict[str, Any] = Field(default_factory=dict)
    source_opportunity_id: str = ""
    renderable_series_count: int = 1
    rendered_mark_count: int = 1
    selected_or_suppressed: str = "SELECTED"
    suppression_reason: str | None = None
    visual_microcopy: Any | None = None
    spatial_placement: Any | None = None
    priority_score: float = 0.5
    confidence: float = 0.90

    def __setattr__(self, name: str, value: Any) -> None:
        """Protects semantic identity and composition boundaries from downstream mutation."""
        spatial_layout_fields = {
            "spatial_placement",
            "row",
            "column",
            "span",
            "height",
        }
        if name in spatial_layout_fields and value is not None:
            raise AttributeError(
                f"COMPOSITION_MUTATION_VIOLATION: Spatial layout field '{name}' cannot be assigned to ExecutiveTopic('{getattr(self, 'topic_id', '')}'). "
                f"Composition layout must be planned separately via DashboardLayoutPlan and CompositionItem."
            )

        immutable_semantic_fields = {
            "topic_id",
            "semantic_topic_key",
            "analytical_intent",
            "domain",
            "dataset_id",
            "evidence_ids",
        }
        if name in immutable_semantic_fields and hasattr(self, name):
            cur = getattr(self, name)
            if cur is not None and cur != value:
                raise AttributeError(
                    f"IMMUTABILITY_VIOLATION: Semantic field '{name}' on ExecutiveTopic('{self.topic_id}') is immutable."
                )
        super().__setattr__(name, value)
