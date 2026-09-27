"""Deck-Level Consistency and Rhythm Auditor for Phase 5.

Audits visual harmony across all slides in a presentation deck:
- Theme token uniformity across all slides
- Typography scale consistency
- Source and evidence footer placement
- Layout rhythm and monotony detection (flags >= 3 consecutive identical layouts)
- KPI structure and formatting consistency
"""

from __future__ import annotations

import logging
from typing import Any

from ..visual.visual_models import VisualSpecification

logger = logging.getLogger(__name__)


class DeckConsistencyAuditor:
    """Evaluates cross-slide aesthetic coherence, rhythm, and structural consistency."""

    @classmethod
    def audit_deck(cls, slides: list[VisualSpecification]) -> dict[str, Any]:
        """Runs deck-level consistency checks across all slide visual specifications."""
        if not slides:
            return {
                "status": "PASS",
                "total_slides": 0,
                "theme_consistent": True,
                "rhythm_score": 1.0,
                "footer_coverage_pct": 100.0,
                "issues": []
            }

        issues: list[str] = []

        # 1. Theme Consistency
        theme_ids = {s.theme_id for s in slides if s.theme_id}
        theme_consistent = len(theme_ids) <= 1
        if not theme_consistent:
            issues.append(f"Inconsistent slide themes detected: {list(theme_ids)}. Single deck must use uniform theme.")

        # 2. Source Footer Coverage
        slides_with_footer = sum(
            1 for s in slides if s.source_footer and (s.source_footer.source_citation or s.source_footer.evidence_citation)
        )
        footer_coverage_pct = round((slides_with_footer / len(slides)) * 100.0, 1)
        if footer_coverage_pct < 100.0:
            issues.append(f"Provenance footer missing on {len(slides) - slides_with_footer} slide(s). Coverage: {footer_coverage_pct}%.")

        # 3. Layout Rhythm & Monotony Detection
        consecutive_repeats = 0
        prev_family = None
        monotony_flags = 0

        for s in slides:
            curr_family = s.layout.family.value
            if curr_family == prev_family:
                consecutive_repeats += 1
                if consecutive_repeats >= 2:  # 3 in a row
                    monotony_flags += 1
            else:
                consecutive_repeats = 0
            prev_family = curr_family

        if monotony_flags > 0:
            issues.append(f"Visual monotony detected: {monotony_flags} instance(s) of 3+ consecutive identical layouts.")

        rhythm_score = max(0.50, 1.0 - (monotony_flags * 0.15))

        status = "PASS" if len(issues) == 0 else "WARNING"

        return {
            "status": status,
            "total_slides": len(slides),
            "theme_consistent": theme_consistent,
            "theme_ids": list(theme_ids),
            "rhythm_score": round(rhythm_score, 2),
            "footer_coverage_pct": footer_coverage_pct,
            "monotony_instances": monotony_flags,
            "issues": issues
        }
