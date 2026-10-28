"""Visual Selection Decision Validator.

Enforces strict semantic integrity, capability compatibility, and ground-truth
grounding before a visual selection decision can generate a canonical VisualSpec.
"""
from __future__ import annotations

import logging
from ..presentation_visual_spec import CHART_CAPABILITY_REGISTRY, VisualFamily
from .selection_models import DataShapeProfile, VisualSelectionDecision
from ..content_models import VisualStrategy

logger = logging.getLogger(__name__)


class VisualSelectionValidationError(ValueError):
    """Raised when a VisualSelectionDecision fails semantic integrity checks."""
    pass


class VisualSelectionValidator:
    """Validates VisualSelectionDecisions against data shape constraints and capability registries."""

    @classmethod
    def validate(
        cls,
        decision: VisualSelectionDecision,
        profile: DataShapeProfile,
        valid_candidates: list[VisualFamily]
    ) -> list[str]:
        """Validates a visual selection decision, returning a list of validation error messages."""
        errors: list[str] = []

        # 1. Family must belong to VisualFamily enum and be supported in capability registry
        if not isinstance(decision.selected_visual_family, VisualFamily):
            errors.append(f"Selected visual family '{decision.selected_visual_family}' is not a canonical VisualFamily enum member")
        elif decision.selected_visual_family not in CHART_CAPABILITY_REGISTRY:
            errors.append(f"Visual family '{decision.selected_visual_family}' is not registered in CHART_CAPABILITY_REGISTRY")

        # 2. Family must belong to the valid candidates generated for this data shape
        if decision.selected_visual_family not in valid_candidates:
            # Allow fallback if explicitly flagged
            if "FALLBACK_APPLIED" not in decision.reason_codes:
                errors.append(
                    f"Selected family '{decision.selected_visual_family}' is not in valid candidate set: {[f.value for f in valid_candidates]}"
                )

        # 3. Existing Visual Reuse verification
        if decision.reuse_strategy == VisualStrategy.REUSE_EXISTING:
            if not profile.has_existing_visual:
                errors.append("reuse_strategy is REUSE_EXISTING but DataShapeProfile indicates no existing visual asset")
            if not decision.source_visual_id:
                errors.append("reuse_strategy is REUSE_EXISTING but source_visual_id is missing")

        # 4. Scenario safety invariant: SCEN-* must never be mapped to standard observed visual
        if profile.is_scenario:
            allowed_scenario_families = (
                VisualFamily.SCENARIO_CARD,
                VisualFamily.DUMBBELL,
                VisualFamily.VARIANCE_BAR,
                VisualFamily.DATA_TABLE,
            )
            if decision.selected_visual_family not in allowed_scenario_families:
                errors.append(
                    f"Scenario content '{profile.content_id}' cannot be represented by non-scenario family '{decision.selected_visual_family.value}'"
                )

        # 5. Continuous variable shape check for SCATTER / CORRELATION
        if decision.selected_visual_family in (VisualFamily.SCATTER, VisualFamily.CORRELATION):
            if profile.continuous_dimension_count < 2 and not profile.has_existing_visual:
                errors.append("SCATTER requires at least 2 continuous numerical variables")

        # 6. Geographic shape check for CHOROPLETH / MAP
        if decision.selected_visual_family in (VisualFamily.CHOROPLETH, VisualFamily.MAP):
            if not profile.is_geographic and not profile.has_existing_visual:
                errors.append("CHOROPLETH requires verified geographic entities (districts, states, regions)")

        return errors
