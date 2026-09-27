"""Auto-Layout Selector for Phase 4.

Intelligently evaluates slide intent, metric volume, visual complexity,
content density, and audience seniority to select the optimal canonical LayoutFamily.
"""

from __future__ import annotations

import logging
from typing import Any
from .layout_registry import LayoutFamily, layout_registry

logger = logging.getLogger(__name__)


class LayoutSelector:
    """Selects the canonical layout family and variant best suited for given slide content."""

    @classmethod
    def select_layout(
        cls,
        slide_purpose: str,
        visual_type: str,
        num_metrics: int = 0,
        has_chart: bool = False,
        has_table: bool = False,
        has_matrix: bool = False,
        has_process: bool = False,
        has_timeline: bool = False,
        has_proposals: bool = False,
        audience_seniority: str = "C_SUITE",
        content_density: str = "medium"
    ) -> tuple[LayoutFamily, str]:
        """Returns the optimal (LayoutFamily, variant) tuple based on empirical content attributes."""
        purpose_lower = (slide_purpose or "").lower()
        v_type_lower = (visual_type or "").lower()

        # 1. Title / Cover / Executive Hero
        if "title" in purpose_lower or "cover" in purpose_lower or "hero" in purpose_lower:
            return (LayoutFamily.TITLE_HERO, "hero_centered")

        # 2. Strategic Proposals / Commitments / Action Plan
        if has_proposals or "action" in purpose_lower or "initiative" in purpose_lower or "roadmap" in purpose_lower:
            if "roadmap" in purpose_lower:
                return (LayoutFamily.ROADMAP, "quarterly_swimlanes")
            return (LayoutFamily.ACTION_PLAN, "initiative_proposals")

        # 3. Two-axis Matrix / Quadrant Classification
        if has_matrix or "matrix" in v_type_lower or "9box" in v_type_lower or "quad" in v_type_lower:
            if "risk" in purpose_lower or "burnout" in purpose_lower:
                return (LayoutFamily.RISK_MATRIX, "impact_vs_likelihood")
            return (LayoutFamily.MATRIX, "talent_9box" if "talent" in v_type_lower else "two_by_two")

        # 4. Tabular Data / Audit Evidence
        if has_table or "table" in v_type_lower or "raci" in purpose_lower or "ledger" in purpose_lower:
            if "raci" in purpose_lower:
                return (LayoutFamily.TABLE, "raci_matrix")
            return (LayoutFamily.TABLE, "bounded_financial_table")

        # 5. Process / Workflow Progression
        if has_process or "process" in purpose_lower or "workflow" in purpose_lower or "funnel" in v_type_lower:
            return (LayoutFamily.PROCESS, "linear_chevron_flow")

        # 6. Timeline / Milestones / Chronological Horizon
        if has_timeline or "timeline" in purpose_lower or "milestone" in purpose_lower:
            return (LayoutFamily.TIMELINE, "horizontal_milestones")

        # 7. Architecture / System Topology
        if "architecture" in purpose_lower or "system" in purpose_lower or "infrastructure" in purpose_lower:
            return (LayoutFamily.ARCHITECTURE, "layered_system_stack")

        # 8. Comparison / Two-column Split
        if "comparison" in purpose_lower or "versus" in purpose_lower or "vs" in purpose_lower or "split" in v_type_lower:
            return (LayoutFamily.COMPARISON, "two_column_split")

        # 9. Pure KPI Dashboard (e.g. 3-6 standalone metrics)
        if num_metrics >= 3 and not has_chart:
            return (LayoutFamily.KPI_GRID, "quad_kpi" if num_metrics >= 4 else "three_col_kpi")

        # 10. Chart-driven Insight
        if has_chart or "chart" in v_type_lower:
            if content_density == "low" or "focus" in purpose_lower:
                return (LayoutFamily.CHART_FULL, "full_bleed_takeaway_top")
            elif "dual" in v_type_lower or "two" in v_type_lower:
                return (LayoutFamily.DUAL_CHART, "side_by_side")
            else:
                return (LayoutFamily.CHART_INSIGHT, "chart_left_insight_right")

        # 11. Concluding / Summary
        if "conclusion" in purpose_lower or "summary" in purpose_lower or "close" in purpose_lower:
            return (LayoutFamily.SUMMARY_CLOSE, "next_steps_and_qa")

        # Default fallback: Chart Insight
        return (LayoutFamily.CHART_INSIGHT, "chart_left_insight_right")
