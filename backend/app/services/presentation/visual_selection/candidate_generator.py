"""Deterministic Visual Candidate Generator.

Generates small, valid, ranked candidate sets of canonical VisualFamily
options strictly derived from deterministic DataShapeProfiles and analytical metadata.
"""
from __future__ import annotations

import logging
from typing import Optional
from ..presentation_visual_spec import CHART_CAPABILITY_REGISTRY, VisualFamily
from .selection_models import DataShapeProfile

logger = logging.getLogger(__name__)


class VisualCandidateGenerator:
    """Deterministic visual candidate generator reasoned over ground-truth data shapes."""

    @classmethod
    def generate_candidates(
        cls,
        profile: DataShapeProfile,
        analytical_intent: Optional[str] = None
    ) -> list[VisualFamily]:
        """Generates a small, valid set of VisualFamily candidates based on data shape."""
        candidates: list[VisualFamily] = []
        intent_upper = (analytical_intent or "").strip().upper()

        # 1. Counterfactual or policy scenario (SCEN-*)
        if profile.is_scenario:
            candidates.extend([
                VisualFamily.SCENARIO_CARD,
                VisualFamily.DUMBBELL,
                VisualFamily.VARIANCE_BAR,
                VisualFamily.DATA_TABLE,
            ])

        # 2. Geographic entities (States, districts, territories, countries)
        elif profile.is_geographic:
            candidates.extend([
                VisualFamily.CHOROPLETH,
                VisualFamily.MAP,
                VisualFamily.RANKED_BAR,
                VisualFamily.DATA_TABLE,
            ])

        # 3. Two continuous numerical variables (Bivariate correlation / scatter)
        elif profile.continuous_dimension_count >= 2 or "SCATTER" in intent_upper or "CORRELATION" in intent_upper:
            candidates.extend([
                VisualFamily.SCATTER,
                VisualFamily.CORRELATION,
                VisualFamily.DATA_TABLE,
            ])

        # 4. Distribution / Statistical dispersion (Box plot / quartiles)
        elif profile.is_distribution or "DISPERSION" in intent_upper or "DISTRIBUTION" in intent_upper:
            candidates.extend([
                VisualFamily.BOX_PLOT,
                VisualFamily.VARIANCE_BAR,
                VisualFamily.DATA_TABLE,
            ])

        # 5. Comparable measure pairs (Actual vs Target, Before vs After, Current vs Benchmark)
        elif (
            profile.has_before_after
            or profile.has_actual_target
            or (profile.has_benchmark and profile.metric_count >= 2)
            or "COMPARISON" in intent_upper
            or "DUMBBELL" in intent_upper
        ):
            candidates.extend([
                VisualFamily.DUMBBELL,
                VisualFamily.VARIANCE_BAR,
                VisualFamily.GROUPED_BAR,
                VisualFamily.DATA_TABLE,
            ])

        # 6. Chronological / Temporal trends (Dates, weeks, months, quarters)
        elif profile.is_temporal or "TREND" in intent_upper or "TIME" in intent_upper:
            candidates.extend([
                VisualFamily.LINE,
                VisualFamily.TREND,
                VisualFamily.BAR,
                VisualFamily.DATA_TABLE,
            ])

        # 7. Ranked categories (Ordered performance metrics)
        elif profile.is_ranked or "RANK" in intent_upper:
            if profile.category_count <= 5 and profile.category_count >= 3:
                candidates.append(VisualFamily.PODIUM_TOP_3)
            candidates.extend([
                VisualFamily.RANKED_BAR,
                VisualFamily.HORIZONTAL_BAR,
                VisualFamily.DATA_TABLE,
            ])

        # 8. High row/column density or record detail
        elif profile.is_record_detail or profile.column_count > 5 or profile.row_count > 15:
            candidates.extend([
                VisualFamily.DATA_TABLE,
            ])

        # 9. Single scalar metric + benchmark or KPI
        elif profile.metric_count == 1 and profile.category_count <= 1:
            candidates.extend([
                VisualFamily.KPI_CARD,
                VisualFamily.BULLET,
            ])

        # 10. Default categorical comparison
        else:
            if profile.max_label_length > 12 or profile.category_count > 6:
                candidates.extend([
                    VisualFamily.HORIZONTAL_BAR,
                    VisualFamily.RANKED_BAR,
                    VisualFamily.BAR,
                    VisualFamily.DATA_TABLE,
                ])
            elif profile.metric_count > 1:
                candidates.extend([
                    VisualFamily.GROUPED_BAR,
                    VisualFamily.STACKED_BAR,
                    VisualFamily.DATA_TABLE,
                ])
            else:
                candidates.extend([
                    VisualFamily.BAR,
                    VisualFamily.RANKED_BAR,
                    VisualFamily.DATA_TABLE,
                ])

        # Deduplicate while preserving order and enforce canonical VisualFamily & capability registry
        filtered: list[VisualFamily] = []
        for fam in candidates:
            if isinstance(fam, VisualFamily) and fam in CHART_CAPABILITY_REGISTRY and fam not in filtered:
                filtered.append(fam)

        if not filtered:
            filtered = [VisualFamily.BAR, VisualFamily.DATA_TABLE]

        return filtered
