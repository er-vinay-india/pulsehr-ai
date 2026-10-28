"""Visual Selection Providers — Deterministic and AI-Assisted.

Evaluates data shape profiles, existing rendered visual assets, and candidate sets
to produce validated VisualSelectionDecisions with structured reason codes.

Core Invariants:
1. "Same visual first, editability second": Trustworthy existing visuals from
   Dashboard/Data Explorer are ALWAYS reused deterministically before calling AI.
2. AI-assisted selection chooses ONLY among candidates produced by
   VisualCandidateGenerator and verified in CHART_CAPABILITY_REGISTRY.
3. The model can NEVER invent chart families.
4. Immediate deterministic fallback on any validation failure, timeout, or invalid family.
"""
from __future__ import annotations

import json
import logging
from abc import ABC, abstractmethod
from typing import Any, Optional

from ....core import config
from ...gateway.contracts import AIRequest, AITaskType, ReasoningLevel
from ...gateway.model_gateway import ModelGateway, extract_json_payload
from ..content_models import PresentationContentItem, VisualCompleteness, VisualStrategy
from ..presentation_visual_spec import CHART_CAPABILITY_REGISTRY, VisualFamily
from .normalization import normalize_to_visual_family
from .selection_models import (
    DataShapeProfile,
    VisualSelectionDecision,
    VisualSelectionSource,
)
from .validator import VisualSelectionValidationError, VisualSelectionValidator

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are HighView Visual Selection Intelligence, an executive analytical visual design expert.
Your job is to select the single best visual representation (VisualFamily) to communicate empirical evidence on an executive presentation slide.

CRITICAL INVARIANTS:
1. You MUST select strictly ONE visual family from the provided ALLOWED CANDIDATES list.
2. You can NEVER invent chart types, visual families, coordinates, layout dimensions, fonts, or colors.
3. Every candidate in the allowed list has already been pre-screened against HighView capabilities and data shape compatibility.
4. Output MUST be valid JSON adhering to the specified schema.
"""


class VisualSelectionProvider(ABC):
    """Abstract interface for slide visual selection intelligence providers."""

    @abstractmethod
    def select_visual(
        self,
        content_id: str,
        profile: DataShapeProfile,
        candidates: list[VisualFamily],
        analytical_intent: Optional[str] = None,
        content_item: Optional[PresentationContentItem] = None,
        metadata: Optional[dict[str, Any]] = None,
    ) -> VisualSelectionDecision:
        """Selects the optimal VisualFamily and reuse strategy for a content item."""
        raise NotImplementedError


class DeterministicVisualSelectionProvider(VisualSelectionProvider):
    """Rule-based, deterministic visual selection engine enforcing 'same visual first, editability second'."""

    def select_visual(
        self,
        content_id: str,
        profile: DataShapeProfile,
        candidates: list[VisualFamily],
        analytical_intent: Optional[str] = None,
        content_item: Optional[PresentationContentItem] = None,
        metadata: Optional[dict[str, Any]] = None,
    ) -> VisualSelectionDecision:
        """Deterministically selects the optimal VisualFamily and reuse strategy."""
        return self._select_visual_internal(
            content_id=content_id,
            profile=profile,
            candidates=candidates,
            analytical_intent=analytical_intent,
            content_item=content_item,
            metadata=metadata,
        )

    @classmethod
    def _select_visual_internal(
        cls,
        content_id: str,
        profile: DataShapeProfile,
        candidates: list[VisualFamily],
        analytical_intent: Optional[str] = None,
        content_item: Optional[PresentationContentItem] = None,
        metadata: Optional[dict[str, Any]] = None,
    ) -> VisualSelectionDecision:
        intent_upper = (analytical_intent or "").strip().upper()

        # STEP 1: Existing Visual Reuse must run before derivation
        if profile.has_existing_visual and profile.source_surface in ("dashboard", "data_explorer"):
            norm_family = normalize_to_visual_family(profile.existing_visual_type, default=None)
            if norm_family is not None and norm_family in CHART_CAPABILITY_REGISTRY:
                return VisualSelectionDecision(
                    content_id=content_id,
                    selected_visual_family=norm_family,
                    selected_visual_variant="standard",
                    reuse_strategy=VisualStrategy.REUSE_EXISTING,
                    visual_completeness=VisualCompleteness.COMPLETE_VISUAL,
                    source_visual_id=profile.existing_visual_id,
                    reason_codes=["SOURCE_VISUAL_REUSED", "SAME_VISUAL_PRIORITY"],
                    confidence=1.0,
                    decision_source=VisualSelectionSource.REUSE_EXISTING,
                    candidate_families=candidates,
                    diagnostic_notes=f"Reused existing visual '{profile.existing_visual_id}' ({norm_family.value}) from {profile.source_surface}",
                )
            else:
                logger.info(
                    "Existing visual '%s' with type '%s' is unrecognized/unsupported by canonical registry; delegating to deterministic data-shape candidate generation and selection",
                    profile.existing_visual_id, profile.existing_visual_type
                )

        # STEP 2: Deterministic Derivation from candidates
        selected_family: VisualFamily = candidates[0] if candidates else VisualFamily.BAR
        reason_codes: list[str] = []
        variant = "standard"

        if profile.is_scenario:
            if VisualFamily.SCENARIO_CARD in candidates:
                selected_family = VisualFamily.SCENARIO_CARD
                reason_codes.append("SCENARIO_POLICY_CARD")
            elif VisualFamily.DUMBBELL in candidates:
                selected_family = VisualFamily.DUMBBELL
                reason_codes.append("SCENARIO_DUMBBELL_COMPARISON")

        elif profile.is_geographic:
            if VisualFamily.CHOROPLETH in candidates:
                selected_family = VisualFamily.CHOROPLETH
                reason_codes.append("GEO_VISUAL_PRESERVED")
            else:
                selected_family = VisualFamily.MAP
                reason_codes.append("GEO_MAP_PRIMARY")

        elif profile.continuous_dimension_count >= 2 or "SCATTER" in intent_upper:
            selected_family = VisualFamily.SCATTER
            reason_codes.append("TWO_CONTINUOUS_CORRELATION")

        elif profile.is_distribution or "DISPERSION" in intent_upper:
            selected_family = VisualFamily.BOX_PLOT
            reason_codes.append("DISTRIBUTION_WITH_OUTLIERS")

        elif profile.has_before_after or profile.has_actual_target or (profile.has_benchmark and profile.metric_count >= 2):
            if VisualFamily.DUMBBELL in candidates:
                selected_family = VisualFamily.DUMBBELL
                reason_codes.append("TWO_MEASURE_COMPARISON")
            elif VisualFamily.VARIANCE_BAR in candidates:
                selected_family = VisualFamily.VARIANCE_BAR
                reason_codes.append("VARIANCE_BAR_COMPARISON")
            else:
                selected_family = VisualFamily.GROUPED_BAR
                reason_codes.append("GROUPED_BAR_COMPARISON")

        elif profile.is_temporal or "TREND" in intent_upper:
            selected_family = VisualFamily.LINE
            reason_codes.append("TIME_SERIES_PRIMARY")

        elif profile.is_ranked or "RANK" in intent_upper:
            if profile.category_count <= 3 and VisualFamily.PODIUM_TOP_3 in candidates and "TOP_3" in intent_upper:
                selected_family = VisualFamily.PODIUM_TOP_3
                reason_codes.append("TOP_3_PODIUM_HIGHLIGHT")
            elif profile.max_label_length > 12 or profile.category_count > 5:
                selected_family = VisualFamily.HORIZONTAL_BAR
                reason_codes.append("RANKING_WITH_LONG_LABELS")
            else:
                selected_family = VisualFamily.RANKED_BAR
                reason_codes.append("RANKING_BAR_ORDERED")

        elif profile.is_record_detail or profile.column_count > 5:
            selected_family = VisualFamily.DATA_TABLE
            reason_codes.append("EXACT_DETAIL_REQUIRES_TABLE")

        elif profile.metric_count == 1 and profile.category_count <= 1:
            selected_family = VisualFamily.KPI_CARD
            reason_codes.append("HERO_KPI_SUMMARY")

        else:
            if profile.max_label_length > 12:
                selected_family = VisualFamily.HORIZONTAL_BAR
                reason_codes.append("HORIZONTAL_BAR_LABEL_FIT")
            elif profile.metric_count > 1:
                selected_family = VisualFamily.GROUPED_BAR
                reason_codes.append("GROUPED_BAR_MULTI_SERIES")
            else:
                selected_family = VisualFamily.BAR
                reason_codes.append("STANDARD_CATEGORICAL_COLUMN")

        completeness = (
            VisualCompleteness.DETAIL_VISUAL
            if selected_family == VisualFamily.DATA_TABLE and profile.is_record_detail
            else VisualCompleteness.COMPLETE_VISUAL
        )

        decision = VisualSelectionDecision(
            content_id=content_id,
            selected_visual_family=selected_family,
            selected_visual_variant=variant,
            reuse_strategy=VisualStrategy.PRESENTATION_RECOMMENDATION,
            visual_completeness=completeness,
            source_visual_id=None,
            reason_codes=reason_codes,
            confidence=1.0,
            decision_source=VisualSelectionSource.DETERMINISTIC_SELECTION,
            candidate_families=candidates,
            diagnostic_notes=f"Deterministic selection: {selected_family.value} based on data shape",
        )

        # STEP 3: Strict Validation & Fallback Safeguard
        errors = VisualSelectionValidator.validate(decision, profile, candidates)
        if errors:
            logger.warning("Visual selection validation failed for %s (%s). Activating deterministic fallback.", content_id, errors)
            fallback_family = VisualFamily.DATA_TABLE if profile.column_count > 3 else VisualFamily.BAR
            if profile.is_scenario:
                fallback_family = VisualFamily.SCENARIO_CARD

            decision = VisualSelectionDecision(
                content_id=content_id,
                selected_visual_family=fallback_family,
                selected_visual_variant="standard",
                reuse_strategy=VisualStrategy.PRESENTATION_RECOMMENDATION,
                visual_completeness=VisualCompleteness.COMPLETE_VISUAL,
                source_visual_id=None,
                reason_codes=["FALLBACK_APPLIED", f"VALIDATION_REPAIR:{fallback_family.value}"],
                confidence=0.8,
                decision_source=VisualSelectionSource.DETERMINISTIC_FALLBACK,
                candidate_families=candidates,
                diagnostic_notes=f"Fallback applied due to validation issues: {'; '.join(errors)}",
            )

        return decision


class AIVisualSelectionProvider(VisualSelectionProvider):
    """AI-powered Visual Selection Intelligence provider.

    Constrains the model to choose strictly among already-validated candidates
    generated by VisualCandidateGenerator and verified in CHART_CAPABILITY_REGISTRY.

    Core Invariants:
    1. The model can NEVER invent chart families.
    2. The model can ONLY choose among the provided `candidates`.
    3. Trustworthy source visuals (dashboard / data_explorer) are ALWAYS reused
       deterministically before calling AI ("same visual first, editability second").
    4. If candidates count is <= 1, AI call is bypassed (single valid choice).
    5. If AI model fails, hallucinates, returns an invalid family, or times out,
       it immediately falls back to DeterministicVisualSelectionProvider.
    """

    def __init__(
        self,
        use_ai: bool = True,
        deterministic_fallback: Optional[DeterministicVisualSelectionProvider] = None,
        confidence_threshold: Optional[float] = None,
    ):
        self.use_ai = use_ai
        self.fallback_provider = deterministic_fallback or DeterministicVisualSelectionProvider()
        self.confidence_threshold = (
            confidence_threshold
            if confidence_threshold is not None
            else config.PRESENTATION_VISUAL_SELECTION_CONFIDENCE_THRESHOLD
        )

    def select_visual(
        self,
        content_id: str,
        profile: DataShapeProfile,
        candidates: list[VisualFamily],
        analytical_intent: Optional[str] = None,
        content_item: Optional[PresentationContentItem] = None,
        metadata: Optional[dict[str, Any]] = None,
    ) -> VisualSelectionDecision:
        if not self.use_ai:
            return self.fallback_provider.select_visual(
                content_id=content_id,
                profile=profile,
                candidates=candidates,
                analytical_intent=analytical_intent,
                content_item=content_item,
                metadata=metadata,
            )

        # Invariant 1: "Same visual first" - Reusable source visuals bypass AI entirely
        if profile.has_existing_visual and profile.source_surface in ("dashboard", "data_explorer"):
            norm_family = normalize_to_visual_family(profile.existing_visual_type, default=None)
            if norm_family is not None and norm_family in CHART_CAPABILITY_REGISTRY:
                return self.fallback_provider.select_visual(
                    content_id=content_id,
                    profile=profile,
                    candidates=candidates,
                    analytical_intent=analytical_intent,
                    content_item=content_item,
                    metadata=metadata,
                )

        # Invariant 2: If candidates count <= 1, single valid candidate needs no LLM arbitration
        if len(candidates) <= 1:
            return self.fallback_provider.select_visual(
                content_id=content_id,
                profile=profile,
                candidates=candidates,
                analytical_intent=analytical_intent,
                content_item=content_item,
                metadata=metadata,
            )

        # Invariant 3: AI selects strictly among the provided candidates
        try:
            return self._call_ai_selection(
                content_id=content_id,
                profile=profile,
                candidates=candidates,
                analytical_intent=analytical_intent,
                content_item=content_item,
                metadata=metadata,
            )
        except Exception as exc:
            logger.warning(
                "AI visual selection failed for content_id %s (%s); activating deterministic fallback",
                content_id,
                exc,
            )
            fallback_dec = self.fallback_provider.select_visual(
                content_id=content_id,
                profile=profile,
                candidates=candidates,
                analytical_intent=analytical_intent,
                content_item=content_item,
                metadata=metadata,
            )
            fallback_dec.decision_source = VisualSelectionSource.DETERMINISTIC_FALLBACK
            fallback_dec.reason_codes.append(f"AI_FALLBACK:{type(exc).__name__}")
            fallback_dec.diagnostic_notes = f"Deterministic fallback applied due to AI selection failure: {exc}"
            return fallback_dec

    def _call_ai_selection(
        self,
        content_id: str,
        profile: DataShapeProfile,
        candidates: list[VisualFamily],
        analytical_intent: Optional[str] = None,
        content_item: Optional[PresentationContentItem] = None,
        metadata: Optional[dict[str, Any]] = None,
    ) -> VisualSelectionDecision:
        metadata = metadata or {}
        mock_resp = metadata.get("mock_ai_response")

        if mock_resp is not None:
            if isinstance(mock_resp, str):
                raw_json = extract_json_payload(mock_resp)
                data = json.loads(raw_json)
            elif isinstance(mock_resp, dict):
                data = mock_resp
            else:
                raise ValueError(f"Invalid mock response: {mock_resp}")
        else:
            prompt = self._build_ai_prompt(
                content_id=content_id,
                profile=profile,
                candidates=candidates,
                analytical_intent=analytical_intent,
                content_item=content_item,
            )
            req = AIRequest(
                prompt=prompt,
                system_prompt=SYSTEM_PROMPT,
                task_type=AITaskType.PRESENTATION_VISUAL_SELECTION,
                reasoning_level=ReasoningLevel.LOW,
                max_latency_ms=10000.0,
                deterministic_fallback=None,
            )
            res = ModelGateway.predict(req)
            if not res.success or not res.raw_text:
                raise RuntimeError(f"ModelGateway prediction failed: {res.execution_record.error_message if res.execution_record else 'Empty response'}")
            raw_json = extract_json_payload(res.raw_text)
            data = json.loads(raw_json)

        # 1. Enforce exact candidate identity (ZERO normalization for AI outputs)
        # Normalization is reserved exclusively for messy legacy source metadata.
        # AI output must strictly match an exact member of the supplied candidates list.
        raw_chosen = data.get("selected_visual_family")
        if not raw_chosen or not isinstance(raw_chosen, str):
            raise VisualSelectionValidationError(
                f"AI returned invalid or missing selected_visual_family: {raw_chosen!r}"
            )

        candidate_map = {c.value: c for c in candidates}
        # Exact string match in candidate set (reject aliases like 'area', 'column', 'bubble_map')
        if raw_chosen not in candidate_map:
            raise VisualSelectionValidationError(
                f"AI returned '{raw_chosen}' which is not an exact member of the allowed candidate set: {list(candidate_map.keys())}"
            )

        # Exact parse as VisualFamily enum
        try:
            chosen_family = VisualFamily(raw_chosen)
        except ValueError as exc:
            raise VisualSelectionValidationError(
                f"AI returned '{raw_chosen}' which cannot be parsed as a canonical VisualFamily: {exc}"
            ) from exc

        # Exact membership in candidates list (enum identity)
        if chosen_family not in candidates:
            raise VisualSelectionValidationError(
                f"AI selected family '{chosen_family.value}' is not in candidates list: {[c.value for c in candidates]}"
            )

        # Exact membership in capability registry
        if chosen_family not in CHART_CAPABILITY_REGISTRY:
            raise VisualSelectionValidationError(
                f"AI selected family '{chosen_family.value}' is not supported in CHART_CAPABILITY_REGISTRY"
            )

        # 2. Confidence threshold check
        conf = float(data.get("confidence", 0.9))
        if conf < self.confidence_threshold:
            raise VisualSelectionValidationError(
                f"AI visual selection confidence ({conf:.2f}) below threshold ({self.confidence_threshold:.2f})"
            )

        variant = str(data.get("selected_visual_variant", "standard"))
        raw_reasons = data.get("reason_codes", ["AI_VISUAL_SELECTION"])
        reason_codes = [str(r) for r in raw_reasons]
        notes = str(data.get("diagnostic_notes", f"AI selected {chosen_family.value} from candidates"))

        completeness = (
            VisualCompleteness.DETAIL_VISUAL
            if chosen_family == VisualFamily.DATA_TABLE and profile.is_record_detail
            else VisualCompleteness.COMPLETE_VISUAL
        )

        decision = VisualSelectionDecision(
            content_id=content_id,
            selected_visual_family=chosen_family,
            selected_visual_variant=variant,
            reuse_strategy=VisualStrategy.PRESENTATION_RECOMMENDATION,
            visual_completeness=completeness,
            source_visual_id=None,
            reason_codes=reason_codes,
            confidence=conf,
            decision_source=VisualSelectionSource.AI_MODEL,
            candidate_families=candidates,
            diagnostic_notes=notes,
        )

        # 5. Strict semantic validation
        validation_errors = VisualSelectionValidator.validate(decision, profile, candidates)
        if validation_errors:
            raise VisualSelectionValidationError(
                f"AI visual selection failed validation checks: {'; '.join(validation_errors)}"
            )

        return decision

    @classmethod
    def _build_ai_prompt(
        cls,
        content_id: str,
        profile: DataShapeProfile,
        candidates: list[VisualFamily],
        analytical_intent: Optional[str] = None,
        content_item: Optional[PresentationContentItem] = None,
    ) -> str:
        allowed_list = [c.value for c in candidates]
        title = getattr(content_item, "title", "") if content_item else ""
        subtitle = getattr(content_item, "subtitle", "") if content_item else ""
        takeaway = getattr(content_item, "narrative_takeaway", "") if content_item else ""
        metric_name = getattr(content_item, "metric_name", "") if content_item else ""
        metric_value = getattr(content_item, "metric_value", "") if content_item else ""
        topic = getattr(content_item, "topic_category", "") if content_item else (analytical_intent or "")

        candidate_desc_lines = []
        for c in candidates:
            if c in CHART_CAPABILITY_REGISTRY:
                candidate_desc_lines.append(f"- '{c.value}': {CHART_CAPABILITY_REGISTRY[c].studio_renderer}")

        return f"""### Task: Visual Family Selection for Slide Evidence

### Evidence Context
- Content ID: {content_id}
- Topic: {topic}
- Title: {title}
- Takeaway / Subtitle: {takeaway or subtitle}
- Metric: {metric_name} ({metric_value})

### Grounded Data Shape
- Is Temporal / Chronological: {profile.is_temporal}
- Is Geographic: {profile.is_geographic}
- Is Scenario / Counterfactual: {profile.is_scenario}
- Is Ranked: {profile.is_ranked}
- Is Distribution / Dispersion: {profile.is_distribution}
- Category Count: {profile.category_count}
- Metric Count: {profile.metric_count}
- Continuous Dimensions: {profile.continuous_dimension_count}
- Has Benchmark Target: {profile.has_benchmark}
- Has Before/After Comparison: {profile.has_before_after}

### ALLOWED CANDIDATES (You MUST choose strictly from this list)
{json.dumps(allowed_list)}

### Candidate Capabilities:
{chr(10).join(candidate_desc_lines)}

Select the single best candidate from the allowed list above. Respond with a JSON object:
{{
  "selected_visual_family": "<one of the exact candidate names above>",
  "selected_visual_variant": "standard",
  "reason_codes": ["<concise_code_1>", "<concise_code_2>"],
  "confidence": 0.95,
  "diagnostic_notes": "<1-2 sentence analytical justification>"
}}
"""
