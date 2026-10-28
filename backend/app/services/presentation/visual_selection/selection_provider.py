"""Deterministic Visual Selection Provider.

Evaluates data shape profiles, existing rendered visual assets, and candidate sets
to produce validated VisualSelectionDecisions with structured reason codes.
"""
from __future__ import annotations

import logging
from typing import Optional
from ..presentation_visual_spec import CHART_CAPABILITY_REGISTRY, VisualFamily
from ..content_models import VisualCompleteness, VisualStrategy
from .selection_models import DataShapeProfile, VisualSelectionDecision, VisualSelectionSource
from .normalization import normalize_to_visual_family
from .validator import VisualSelectionValidator

logger = logging.getLogger(__name__)


class DeterministicVisualSelectionProvider:
    """Rule-based, deterministic visual selection engine enforcing 'same visual first, editability second'."""

    @classmethod
    def select_visual(
        cls,
        content_id: str,
        profile: DataShapeProfile,
        candidates: list[VisualFamily],
        analytical_intent: Optional[str] = None
    ) -> VisualSelectionDecision:
        """Deterministically selects the optimal VisualFamily and reuse strategy."""
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
            # Conservative fallback
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
