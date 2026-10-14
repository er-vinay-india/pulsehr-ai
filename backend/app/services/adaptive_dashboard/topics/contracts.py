"""Analytical Story & ExecutiveTopic Contracts (Phase G5.5).

Defines strongly typed contracts for analytical story assembly and immutable ExecutiveTopic creation:
- TopicIdGenerator: Canonical topic identifier generator (TOPIC-001, etc.).
- ExecutiveTopicDraft: Pre-assembly specification bundling verified narrative, bound evidence, and semantic intent.
- ExecutiveTopic: The immutable Level-1 executive decision topic.
"""
from __future__ import annotations

from typing import Any, Literal
from pydantic import BaseModel, ConfigDict, Field


class TopicIdGenerator:
    """Generates canonical, monotonic topic identifiers (e.g. TOPIC-001)."""

    @staticmethod
    def format_id(index: int) -> str:
        """Returns zero-padded canonical topic identifier."""
        return f"TOPIC-{int(index):03d}"

    @staticmethod
    def parse_index(topic_id: str) -> int:
        """Extracts integer sequence from canonical identifier."""
        if topic_id.startswith("TOPIC-"):
            try:
                return int(topic_id.split("-")[1])
            except (IndexError, ValueError):
                pass
        return 0


class ExecutiveTopicDraft(BaseModel):
    """Pre-assembly draft bundling narrative, bound evidence, and semantic identity."""
    model_config = ConfigDict(extra="ignore")

    topic_id: str
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
    """Executive analytical topic synthesizing multiple related candidate insights into a unified visual story."""
    model_config = ConfigDict(extra="ignore")

    topic_id: str
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
