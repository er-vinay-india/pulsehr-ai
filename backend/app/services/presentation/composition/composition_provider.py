"""Slide Composition Intelligence — Composition Providers.

Provides deterministic and AI-powered composition engines that make semantic
composition decisions before spatial layout and geometry generation.
"""

from __future__ import annotations

import json
import logging
import re
from abc import ABC, abstractmethod
from typing import Any, Optional

from app.core.models_config import ModelRole
from ...gateway.contracts import AIRequest, AITaskType, ReasoningLevel
from ...gateway.model_gateway import ModelGateway, extract_json_payload
from ..content_models import ContentKind, PresentationContentPackage
from ..story_models import LogicalSlidePlan, StructuralRole
from .composition_models import (
    DEFAULT_COMPOSITION_CONFIDENCE_THRESHOLD,
    CompositionArchetype,
    CompositionContentGroup,
    CompositionContentRole,
    CompositionDecision,
    CompositionDecisionSource,
    CompositionFailureTelemetry,
    DensityIntent,
    LabelSimplificationIntent,
    NarrativePlacementIntent,
    SplitIntent,
    VisualPriority,
)
from .composition_validator import CompositionDecisionValidator, CompositionValidationError

logger = logging.getLogger(__name__)

FAILURE_CORPUS_PATH = "backend/data/composition_tuning/failure_corpus.jsonl"


def _record_failure_telemetry(telemetry: CompositionFailureTelemetry) -> None:
    """Appends audited failure telemetry to the candidate curation corpus for iterative LoRA tuning."""
    try:
        import os
        os.makedirs(os.path.dirname(FAILURE_CORPUS_PATH), exist_ok=True)
        with open(FAILURE_CORPUS_PATH, "a", encoding="utf-8") as f:
            f.write(json.dumps(telemetry.model_dump()) + "\n")
    except Exception as err:
        logger.debug("Failed to append to composition failure corpus: %s", err)


def _to_human_label(name: str) -> str:
    """Converts snake_case or technical identifiers to Title Case display labels."""
    cleaned = re.sub(r"[_\-]+", " ", name).strip()
    return cleaned.title()


class CompositionProvider(ABC):
    """Abstract interface for slide composition intelligence providers."""

    @abstractmethod
    def compose_slide(
        self,
        logical_slide: LogicalSlidePlan,
        content_pkg: Optional[PresentationContentPackage] = None,
        metadata: Optional[dict[str, Any]] = None,
    ) -> CompositionDecision:
        """Generates a structured composition decision for a single logical slide."""
        pass


class DeterministicCompositionProvider(CompositionProvider):
    """Rule-based, deterministic composition provider.
    
    Serves as the zero-token baseline and rock-solid fallback whenever AI inference
    is disabled, times out, or fails validation.
    """

    def compose_slide(
        self,
        logical_slide: LogicalSlidePlan,
        content_pkg: Optional[PresentationContentPackage] = None,
        metadata: Optional[dict[str, Any]] = None,
    ) -> CompositionDecision:
        metadata = metadata or {}
        role_str = (
            logical_slide.structural_role.value
            if hasattr(logical_slide.structural_role, "value")
            else str(logical_slide.structural_role)
        ).upper()

        visual_type = (logical_slide.visual_type or "").lower()
        bound_ids = [b.content_id for b in logical_slide.content_bindings if b.content_id]
        if logical_slide.visual_id and logical_slide.visual_id not in bound_ids:
            bound_ids.insert(0, logical_slide.visual_id)

        # 1. Determine Archetype
        archetype = self._resolve_archetype(role_str, visual_type, logical_slide)

        # 2. Determine Density Intent
        density = DensityIntent.BALANCED
        if archetype == CompositionArchetype.TABLE_DEEP_DIVE:
            density = DensityIntent.DENSE
        elif archetype in (CompositionArchetype.TITLE_COVER, CompositionArchetype.CLOSING_SUMMARY):
            density = DensityIntent.SPARSE

        # 3. Determine Visual Priority
        v_priority = VisualPriority.PRIMARY
        if archetype == CompositionArchetype.TITLE_COVER:
            v_priority = VisualPriority.REFERENCE
        elif archetype in (CompositionArchetype.MULTI_INSIGHT, CompositionArchetype.EXECUTIVE_SYNTHESIS):
            v_priority = VisualPriority.SECONDARY

        # 4. Determine Narrative Placement
        narrative_placement = NarrativePlacementIntent.BESIDE_VISUAL
        if archetype in (CompositionArchetype.TITLE_COVER, CompositionArchetype.KPI_GRID):
            narrative_placement = NarrativePlacementIntent.BELOW_VISUAL
        elif archetype == CompositionArchetype.TABLE_DEEP_DIVE:
            narrative_placement = NarrativePlacementIntent.ABOVE_VISUAL
        elif archetype == CompositionArchetype.CLOSING_SUMMARY:
            narrative_placement = NarrativePlacementIntent.BESIDE_VISUAL

        # 5. Determine Split Intent
        if not logical_slide.allow_split or archetype in (CompositionArchetype.TITLE_COVER, CompositionArchetype.CLOSING_SUMMARY):
            split_intent = SplitIntent.NO_SPLIT
        elif archetype in (CompositionArchetype.TABLE_DEEP_DIVE, CompositionArchetype.OUTLIER_SUMMARY) or len(bound_ids) > 4:
            split_intent = SplitIntent.PREFER_SPLIT
        else:
            split_intent = SplitIntent.SPLIT_IF_REQUIRED

        # 6. Group Content Items
        content_groups, primary_id, supporting_ids = self._group_content(
            logical_slide=logical_slide,
            bound_ids=bound_ids,
            archetype=archetype,
            content_pkg=content_pkg,
        )

        # 7. Label Simplification Intent (detect technical labels)
        label_intents = self._detect_label_simplifications(logical_slide, content_pkg)

        reason_codes = [
            f"ROLE_{role_str}",
            f"ARCHETYPE_{archetype.value}",
            f"DENSITY_{density.value}",
        ]
        if visual_type:
            reason_codes.append(f"VTYPE_{visual_type.upper()}")

        decision = CompositionDecision(
            logical_slide_id=logical_slide.logical_slide_id,
            composition_archetype=archetype,
            content_groups=content_groups,
            primary_content_id=primary_id,
            visual_priority=v_priority,
            density_intent=density,
            narrative_placement=narrative_placement,
            supporting_content_ids=supporting_ids,
            split_intent=split_intent,
            label_intents=label_intents,
            reason_codes=reason_codes,
            confidence=1.0,
            decision_source=CompositionDecisionSource.DETERMINISTIC_FALLBACK,
            diagnostic_rationale=f"Deterministic mapping based on structural role {role_str} and visual type {visual_type}",
            metadata={"rule_engine": "v1_deterministic"},
        )

        return decision

    def _resolve_archetype(
        self,
        role_str: str,
        visual_type: str,
        logical_slide: LogicalSlidePlan,
    ) -> CompositionArchetype:
        """Maps structural role and visual metadata to domain-neutral CompositionArchetype."""
        if any(w in role_str for w in ["TITLE", "COVER"]):
            return CompositionArchetype.TITLE_COVER
        if any(w in role_str for w in ["KPI", "METRIC"]):
            return CompositionArchetype.KPI_GRID
        if any(w in role_str for w in ["GEOGRAPHIC", "DISTRIBUTION", "COHORT"]):
            return CompositionArchetype.DISTRIBUTION
        if any(w in role_str for w in ["CORRELATION"]):
            return CompositionArchetype.CORRELATION
        if any(w in role_str for w in ["RANKING", "VARIANCE"]):
            return CompositionArchetype.RANKING
        if any(w in role_str for w in ["BENCHMARK", "COMPARISON"]):
            return CompositionArchetype.COMPARISON
        if any(w in role_str for w in ["OUTLIER", "EDA"]):
            return CompositionArchetype.OUTLIER_SUMMARY
        if any(w in role_str for w in ["TABLE", "DATA_EXPLORER", "DETAIL", "DEEP_DIVE"]):
            return CompositionArchetype.TABLE_DEEP_DIVE
        if any(w in role_str for w in ["EXECUTIVE_SUMMARY", "SYNTHESIS"]):
            return CompositionArchetype.EXECUTIVE_SYNTHESIS
        if any(w in role_str for w in ["CLOSING", "NEXT_STEP", "SIGN_OFF", "ACTION"]):
            return CompositionArchetype.CLOSING_SUMMARY
        if any(w in role_str for w in ["HERO", "DIAGNOSTIC", "THEMATIC"]):
            return CompositionArchetype.VISUAL_WITH_INSIGHT

        # Inspect visual type fallback
        if visual_type == "table":
            return CompositionArchetype.TABLE_DEEP_DIVE
        if visual_type in ("scatter", "scatter_plot", "bubble"):
            return CompositionArchetype.CORRELATION
        if visual_type in ("bar", "bar_chart", "horizontal_bar", "treemap"):
            return CompositionArchetype.RANKING
        if visual_type in ("choropleth", "map"):
            return CompositionArchetype.DISTRIBUTION
        if visual_type in ("kpi", "scorecard", "metric"):
            return CompositionArchetype.KPI_GRID
        if visual_type:
            return CompositionArchetype.VISUAL_WITH_INSIGHT

        return CompositionArchetype.MULTI_INSIGHT

    def _group_content(
        self,
        logical_slide: LogicalSlidePlan,
        bound_ids: list[str],
        archetype: CompositionArchetype,
        content_pkg: Optional[PresentationContentPackage] = None,
    ) -> tuple[list[CompositionContentGroup], Optional[str], list[str]]:
        """Separates bound content items into semantic visual groups."""
        if not bound_ids:
            return [], None, []

        primary_id: Optional[str] = None
        supporting_ids: list[str] = []
        groups: list[CompositionContentGroup] = []

        visual_id = logical_slide.visual_id
        if visual_id and visual_id in bound_ids:
            primary_id = visual_id
            supporting_ids = [cid for cid in bound_ids if cid != visual_id]
        else:
            primary_id = bound_ids[0]
            supporting_ids = bound_ids[1:]

        # Map to roles
        if archetype == CompositionArchetype.KPI_GRID:
            groups.append(
                CompositionContentGroup(
                    role=CompositionContentRole.PRIMARY_VISUAL,
                    content_ids=bound_ids,
                )
            )
        elif archetype == CompositionArchetype.TABLE_DEEP_DIVE:
            groups.append(
                CompositionContentGroup(
                    role=CompositionContentRole.REFERENCE_DATA,
                    content_ids=[primary_id] if primary_id else bound_ids[:1],
                )
            )
            if supporting_ids:
                groups.append(
                    CompositionContentGroup(
                        role=CompositionContentRole.SUPPORTING_INSIGHT,
                        content_ids=supporting_ids,
                    )
                )
        else:
            if primary_id:
                groups.append(
                    CompositionContentGroup(
                        role=CompositionContentRole.PRIMARY_VISUAL,
                        content_ids=[primary_id],
                    )
                )
            if supporting_ids:
                groups.append(
                    CompositionContentGroup(
                        role=CompositionContentRole.SUPPORTING_INSIGHT,
                        content_ids=supporting_ids,
                    )
                )

        return groups, primary_id, supporting_ids

    def _detect_label_simplifications(
        self,
        logical_slide: LogicalSlidePlan,
        content_pkg: Optional[PresentationContentPackage] = None,
    ) -> list[LabelSimplificationIntent]:
        """Scans slide metadata and bound items for technical identifiers needing simplification."""
        intents: list[LabelSimplificationIntent] = []
        seen: set[str] = set()

        candidates = [logical_slide.semantic_topic, logical_slide.headline]
        if logical_slide.visual_spec and isinstance(logical_slide.visual_spec, dict):
            for k in ("x_axis", "y_axis", "metric", "dimension", "title"):
                val = logical_slide.visual_spec.get(k)
                if isinstance(val, str):
                    candidates.append(val)

        for raw in candidates:
            if not raw or raw in seen:
                continue
            if "_" in raw or raw.isupper() or any(term in raw.lower() for term in ["pct_", "avg_", "_score", "_id"]):
                human = _to_human_label(raw)
                if human.lower() != raw.lower():
                    seen.add(raw)
                    intents.append(
                        LabelSimplificationIntent(
                            source_label=raw,
                            display_intent="human_readable_short",
                            suggested_display_text=human,
                        )
                    )

        return intents


class AICompositionProvider(CompositionProvider):
    """AI-powered slide composition intelligence provider.
    
    Prompts the LLM for semantic composition decisions using AITaskType.PRESENTATION_COMPOSITION.
    Strictly validates all outputs against CompositionDecisionValidator.
    Immediately falls back to DeterministicCompositionProvider on validation error or timeout.
    """

    def __init__(
        self,
        use_ai: bool = True,
        deterministic_fallback: Optional[DeterministicCompositionProvider] = None,
        confidence_threshold: float = DEFAULT_COMPOSITION_CONFIDENCE_THRESHOLD,
    ):
        self.use_ai = use_ai
        self.fallback_provider = deterministic_fallback or DeterministicCompositionProvider()
        self.confidence_threshold = confidence_threshold

    def compose_slide(
        self,
        logical_slide: LogicalSlidePlan,
        content_pkg: Optional[PresentationContentPackage] = None,
        metadata: Optional[dict[str, Any]] = None,
    ) -> CompositionDecision:
        if not self.use_ai:
            return self.fallback_provider.compose_slide(logical_slide, content_pkg, metadata)

        try:
            decision = self._call_ai_composition(logical_slide, content_pkg, metadata)
            # Confidence threshold check
            if decision.confidence < self.confidence_threshold:
                raise CompositionValidationError(
                    f"Reported confidence ({decision.confidence:.2f}) below required threshold ({self.confidence_threshold:.2f})"
                )

            # Strict validation
            warnings = CompositionDecisionValidator.validate(decision, logical_slide, content_pkg)
            if warnings:
                decision.metadata["validation_warnings"] = warnings

            # Tag Granite provenance
            decision.metadata.setdefault("model_family", "GRANITE")
            decision.metadata.setdefault("base_model", "granite4:3b")
            decision.metadata.setdefault("adapter_name", "granite_presentation_composition_lora_v1")
            decision.metadata.setdefault("adapter_version", "v1")
            decision.metadata.setdefault("task_type", AITaskType.PRESENTATION_COMPOSITION.value)
            decision.metadata.setdefault("fallback_used", False)
            return decision
        except Exception as exc:
            err_msg = str(exc)
            logger.warning(
                "AI composition failed for logical slide %s; activating deterministic fallback: %s",
                logical_slide.logical_slide_id,
                exc,
            )
            # Classify failure
            fail_type = "MODEL_ERROR"
            if "timeout" in err_msg.lower():
                fail_type = "TIMEOUT"
            elif "confidence" in err_msg.lower():
                fail_type = "LOW_CONFIDENCE"
            elif "unknown content id" in err_msg.lower() or "hallucinat" in err_msg.lower():
                fail_type = "UNGROUNDED_ID"
            elif "validation" in err_msg.lower() or isinstance(exc, CompositionValidationError):
                fail_type = "VALIDATION_ERROR"

            telemetry = CompositionFailureTelemetry(
                logical_slide_id=logical_slide.logical_slide_id,
                input_fingerprint=logical_slide.logical_slide_id,
                failure_type=fail_type,
                model_response_valid=False,
                validation_error=err_msg,
                fallback_used=True,
            )
            _record_failure_telemetry(telemetry)

            fallback_decision = self.fallback_provider.compose_slide(logical_slide, content_pkg, metadata)
            fallback_decision.fallback_reason = f"AI failure ({fail_type}): {err_msg}"
            fallback_decision.metadata["model_family"] = "GRANITE"
            fallback_decision.metadata["fallback_used"] = True
            fallback_decision.metadata["failure_telemetry"] = telemetry.model_dump()
            return fallback_decision

    def _call_ai_composition(
        self,
        logical_slide: LogicalSlidePlan,
        content_pkg: Optional[PresentationContentPackage] = None,
        metadata: Optional[dict[str, Any]] = None,
    ) -> CompositionDecision:
        """Invokes ModelGateway with structured prompt for composition intelligence."""
        bound_items_desc = []
        for b in logical_slide.content_bindings:
            bound_items_desc.append({
                "content_id": b.content_id,
                "binding_role": b.binding_role.value if hasattr(b.binding_role, "value") else str(b.binding_role),
                "visual_type": b.visual_type or "none",
                "notes": b.notes or "",
            })

        prompt = f"""You are HighView's Slide Composition Intelligence Engine.
Your task is to make a high-level SEMANTIC COMPOSITION DECISION for the following logical presentation slide.

CRITICAL RULES:
1. Zero coordinates (x, y, width, height).
2. Zero typography measurements (pt, font size).
3. Zero colors (hex, rgb).
4. Zero DrawingML, SVG, or HTML markup.
5. Reference ONLY the valid content IDs listed below. Never hallucinate or invent new content IDs.

SLIDE CONTEXT:
- Logical Slide ID: "{logical_slide.logical_slide_id}"
- Structural Role: "{logical_slide.structural_role}"
- Semantic Topic: "{logical_slide.semantic_topic}"
- Purpose: "{logical_slide.purpose}"
- Headline: "{logical_slide.headline}"
- Key Takeaway: "{logical_slide.takeaway}"
- Primary Visual ID: "{logical_slide.visual_id or 'none'}"
- Primary Visual Type: "{logical_slide.visual_type or 'none'}"

AVAILABLE CONTENT BINDINGS:
{json.dumps(bound_items_desc, indent=2)}

VALID ARCHETYPES:
HERO_METRIC, KPI_GRID, VISUAL_HERO, VISUAL_WITH_INSIGHT, VISUAL_WITH_SUPPORTING_METRICS,
COMPARISON, RANKING, DISTRIBUTION, CORRELATION, SCENARIO, TABLE_DEEP_DIVE, OUTLIER_SUMMARY,
MULTI_INSIGHT, EXECUTIVE_SYNTHESIS, TITLE_COVER, CLOSING_SUMMARY

Return a JSON object matching this schema:
{{
  "logical_slide_id": "{logical_slide.logical_slide_id}",
  "composition_archetype": "<ONE_OF_VALID_ARCHETYPES>",
  "primary_content_id": "<content_id or null>",
  "visual_priority": "PRIMARY" | "SECONDARY" | "SUPPORTING" | "REFERENCE",
  "density_intent": "SPARSE" | "BALANCED" | "DENSE",
  "narrative_placement": "NONE" | "ABOVE_VISUAL" | "BESIDE_VISUAL" | "BELOW_VISUAL" | "CALLOUT",
  "supporting_content_ids": ["<content_id>"],
  "content_groups": [
    {{
      "role": "PRIMARY_VISUAL" | "PRIMARY_INSIGHT" | "SUPPORTING_METRICS" | "SUPPORTING_INSIGHT" | "COMPARISON_CARD" | "REFERENCE_DATA" | "CONTEXT_SUMMARY" | "CALLOUT",
      "content_ids": ["<content_id>"]
    }}
  ],
  "split_intent": "NO_SPLIT" | "SPLIT_IF_REQUIRED" | "PREFER_SPLIT",
  "reason_codes": ["<concise_code>"],
  "confidence": 0.95,
  "diagnostic_rationale": "<one sentence justification>"
}}
"""

        req = AIRequest(
            task_type=AITaskType.PRESENTATION_COMPOSITION,
            prompt=prompt,
            system_prompt="You are a specialized slide composition planning specialist. Emit only valid JSON.",
            structured_output_schema=CompositionDecision,
            reasoning_level=ReasoningLevel.LOW,
            max_latency_ms=10000.0,
            report_id=f"composition-{logical_slide.logical_slide_id}",
            step_name="slide_composition",
        )

        resp = ModelGateway.execute(req)
        if not resp.success:
            raise RuntimeError(f"ModelGateway execution failed: {resp.error}")

        raw_payload = resp.parsed or resp.raw_text
        if isinstance(raw_payload, CompositionDecision):
            raw_payload.decision_source = CompositionDecisionSource.AI_MODEL
            return raw_payload

        if isinstance(raw_payload, str):
            json_dict = extract_json_payload(raw_payload)
            if not json_dict:
                raise ValueError("Could not extract JSON from model response")
            raw_payload = json_dict

        if isinstance(raw_payload, dict):
            decision = CompositionDecision.model_validate(raw_payload)
            decision.decision_source = CompositionDecisionSource.AI_MODEL
            return decision

        raise ValueError(f"Unexpected response format from ModelGateway: {type(raw_payload)}")
