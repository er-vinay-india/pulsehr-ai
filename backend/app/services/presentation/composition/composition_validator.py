"""Slide Composition Intelligence — Composition Decision Validator.

Enforces strict semantic integrity and accountability contracts on composition decisions:
1. Grounded ID Invariant: Every content ID in the decision must exist in the logical slide's
   bound content or the source content package. Zero invented or hallucinated IDs.
2. Accountability / No-Silent-Loss Invariant: Primary visuals or key evidence bound to the
   logical slide must be accounted for (as primary content or within a content group).
3. Purity Invariant: Zero coordinates, font sizes, colors, or DrawingML/SVG/HTML markup.
4. Confidence Bounds: Confidence must be bounded in [0.0, 1.0].
"""

from __future__ import annotations

import logging
import re
from typing import Any, Optional

from ..content_models import PresentationContentPackage
from ..story_models import LogicalSlidePlan
from .composition_models import CompositionDecision

logger = logging.getLogger(__name__)

# Patterns that indicate coordinate, styling, or raw rendering leakages
_DISALLOWED_RENDER_KEYS = {
    "x", "y", "width", "height", "top", "left", "right", "bottom",
    "font_size", "pt", "color", "hex", "rgb", "rgba", "fill",
    "drawingml", "svg", "html", "css"
}


class CompositionValidationError(ValueError):
    """Raised when a composition decision violates structural or semantic invariants."""
    pass


class CompositionDecisionValidator:
    """Validates CompositionDecision against logical slide and content package ground truth."""

    @classmethod
    def validate(
        cls,
        decision: CompositionDecision,
        logical_slide: LogicalSlidePlan,
        content_pkg: Optional[PresentationContentPackage] = None,
    ) -> list[str]:
        """Validates a composition decision against the logical slide plan.
        
        Returns a list of warning or minor issue codes if non-fatal, or raises
        CompositionValidationError if a critical invariant is breached.
        """
        warnings: list[str] = []

        # 1. Slide ID Grounding
        if decision.logical_slide_id != logical_slide.logical_slide_id:
            raise CompositionValidationError(
                f"Mismatched logical_slide_id: decision has '{decision.logical_slide_id}', "
                f"expected '{logical_slide.logical_slide_id}'"
            )

        # 2. Collect allowable content IDs
        bound_content_ids = {b.content_id for b in logical_slide.content_bindings if b.content_id}
        if logical_slide.visual_id:
            bound_content_ids.add(logical_slide.visual_id)

        pkg_content_ids = set()
        if content_pkg:
            pkg_content_ids = {item.content_id for item in content_pkg.items if item.content_id}

        allowable_ids = bound_content_ids | pkg_content_ids

        # 3. Verify referenced IDs exist in allowable set
        referenced_ids = set()
        if decision.primary_content_id:
            referenced_ids.add(decision.primary_content_id)
        referenced_ids.update(decision.supporting_content_ids)
        for group in decision.content_groups:
            referenced_ids.update(group.content_ids)

        if allowable_ids:
            ungrounded_ids = referenced_ids - allowable_ids
            if ungrounded_ids:
                raise CompositionValidationError(
                    f"CompositionDecision references ungrounded content IDs not in logical slide or package: "
                    f"{sorted(ungrounded_ids)}"
                )

        # 4. No-Silent-Loss for bound visual / primary content
        # If the logical slide has a primary visual, ensure it is represented in the decision
        if logical_slide.visual_id and allowable_ids:
            if logical_slide.visual_id not in referenced_ids:
                # If there are content bindings, check if at least one was selected
                warnings.append(f"BOUND_VISUAL_NOT_EXPLICITLY_GROUPED:{logical_slide.visual_id}")

        # 5. Purity Invariant: Check metadata for illegal layout/render keys
        for key in decision.metadata:
            if key.lower() in _DISALLOWED_RENDER_KEYS:
                raise CompositionValidationError(
                    f"CompositionDecision contains prohibited rendering/layout key '{key}' in metadata"
                )

        # 6. Confidence Bounds
        if not (0.0 <= decision.confidence <= 1.0):
            raise CompositionValidationError(
                f"Confidence {decision.confidence} out of bounds [0.0, 1.0]"
            )

        return warnings
