"""ExecutiveTopic Factory (Phase G5.5).

The single, authoritative builder that turns verified narrative, bound evidence,
and semantic identity into an immutable ExecutiveTopic.

Guarantees:
1. Assembly strictly by identity, never by positional array zip.
2. Narrative and evidence topic_ids must match draft topic_id.
3. VisualSpec binding validates that visual_spec.topic_id == topic.topic_id.
4. Zero calculation of facts, zero creation of evidence, zero chart selection mechanics.
"""
from __future__ import annotations

import logging
from typing import Any

from .contracts import ExecutiveTopic, ExecutiveTopicDraft, TopicIdGenerator
from .integrity import StoryAssemblyIntegrity, StoryAssemblyIntegrityError

logger = logging.getLogger(__name__)


class ExecutiveTopicFactory:
    """Factory creating immutable ExecutiveTopic instances from verified drafts."""

    @classmethod
    def create_topic(cls, draft: ExecutiveTopicDraft) -> ExecutiveTopic:
        """Assembles an ExecutiveTopic from a verified draft."""
        topic_id = draft.topic_id or TopicIdGenerator.format_id(draft.priority)

        # 1. Validate identity alignment
        StoryAssemblyIntegrity.assert_identity_alignment(
            topic_id=topic_id,
            narrative=draft.narrative,
            evidence_binding=draft.evidence_binding,
        )

        # 2. Extract narrative fields
        narrative = draft.narrative or {}
        if hasattr(narrative, "model_dump"):
            narrative = narrative.model_dump()
        elif hasattr(narrative, "__dict__"):
            narrative = narrative.__dict__

        title = narrative.get("title") or draft.tokens.get("title") or f"Executive Topic {draft.priority}"
        subtitle = narrative.get("subtitle") or narrative.get("business_question") or draft.tokens.get("subtitle") or ""
        finding = narrative.get("finding") or narrative.get("takeaway") or draft.tokens.get("finding") or ""
        takeaway = narrative.get("takeaway") or finding
        recommended_action = narrative.get("recommended_action") or draft.recommended_action or ""

        # 3. Extract evidence and provenance identifiers
        evidence_ids = list(draft.evidence_ids)
        if draft.evidence_binding:
            eb = draft.evidence_binding
            if hasattr(eb, "evidence_id"):
                evidence_ids.append(eb.evidence_id)
            elif isinstance(eb, dict) and eb.get("evidence_id"):
                evidence_ids.append(eb["evidence_id"])
            elif isinstance(eb, dict) and eb.get("evidence_ids"):
                evidence_ids.extend(eb["evidence_ids"])

        evidence_ids = list(dict.fromkeys(evidence_ids))  # deduplicate preserving order
        evidence_ref = evidence_ids[0] if evidence_ids else ""

        # 4. Construct inspect payload
        inspect_payload = dict(draft.inspect_payload)
        inspect_payload.update({
            "topic_id": topic_id,
            "title": title,
            "business_question": subtitle,
            "primary_takeaway": takeaway,
            "recommended_action": recommended_action,
            "analytical_intent": draft.analytical_intent,
            "evidence_ids": evidence_ids,
        })

        return ExecutiveTopic(
            topic_id=topic_id,
            semantic_topic_key=draft.semantic_topic_key,
            display_order=draft.display_order,
            rank=draft.rank,
            portfolio_position=draft.portfolio_position,
            title=title,
            subtitle=subtitle,
            slot_type=draft.slot_type,
            dataset_id=draft.dataset_id,
            domain=draft.domain,
            insight_ids=draft.tokens.get("insight_ids", []),
            metric_family=draft.semantic_family,
            periods=draft.periods,
            dimensions=draft.dimensions,
            recommended_visual=draft.tokens.get("recommended_visual", "ranked_bar"),
            layout_hint=draft.tokens.get("layout_hint", "MEDIUM"),
            primary_takeaway=takeaway,
            takeaway=takeaway,
            recommended_action=recommended_action,
            evidence_ids=evidence_ids,
            evidence_ref=evidence_ref,
            priority=draft.priority,
            key_metric=draft.key_metric,
            analytical_intent=draft.analytical_intent,
            visual_spec=dict(draft.tokens.get("visual_spec", {})),
            inspect_payload=inspect_payload,
            source_opportunity_id=draft.source_opportunity_id,
            renderable_series_count=max(1, draft.tokens.get("renderable_series_count", 1)),
            rendered_mark_count=max(1, draft.tokens.get("rendered_mark_count", 1)),
            selected_or_suppressed="SELECTED",
            suppression_reason=None,
            visual_microcopy=draft.visual_microcopy,
            spatial_placement=draft.spatial_placement,
            priority_score=draft.priority_score,
            confidence=draft.confidence,
        )

    @classmethod
    def bind_visual_spec(
        cls,
        topic: ExecutiveTopic,
        visual_spec: Any,
    ) -> ExecutiveTopic:
        """Binds a semantic VisualSpec to an ExecutiveTopic, validating topic identity match."""
        if hasattr(visual_spec, "to_dict"):
            v_dict = visual_spec.to_dict()
        elif isinstance(visual_spec, dict):
            v_dict = dict(visual_spec)
        else:
            v_dict = dict(getattr(visual_spec, "__dict__", {}))

        # Enforce strict topic identity alignment
        StoryAssemblyIntegrity.assert_identity_alignment(
            topic_id=topic.topic_id,
            visual_spec=v_dict,
        )

        v_dict["topic_id"] = topic.topic_id
        topic.visual_spec = v_dict
        return topic

    @classmethod
    def assemble_portfolio_with_visuals(
        cls,
        drafts: list[ExecutiveTopicDraft],
        visual_specs_by_id: dict[str, Any],
    ) -> list[ExecutiveTopic]:
        """Assembles a portfolio of ExecutiveTopics and binds visual specs strictly by topic identity."""
        StoryAssemblyIntegrity.assert_no_positional_binding(drafts, visual_specs_by_id)

        assembled: list[ExecutiveTopic] = []
        for draft in drafts:
            topic = cls.create_topic(draft)
            v_spec = visual_specs_by_id[draft.topic_id]
            cls.bind_visual_spec(topic, v_spec)
            assembled.append(topic)

        return assembled
