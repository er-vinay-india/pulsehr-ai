"""Slide layout renderers for PowerPoint presentations.

Modular renderers are organized into:
- pptx_card_layouts: Hero, KPI, action plan, and split comparison slides
- pptx_visual_layouts: Charts, dual charts, takeaways, and table slides
"""

from .pptx_card_layouts import (
    _render_title_hero_slide,
    _render_kpi_summary_slide,
    _render_comparison_split_slide,
    _render_action_plan_slide,
    _render_generic_slide,
)
from .pptx_visual_layouts import (
    _render_chart_narrative_slide,
    _render_table_detail_slide,
    _render_full_chart_takeaway_slide,
    _render_two_charts_slide,
    _table_slide,
)

__all__ = [
    "_render_title_hero_slide",
    "_render_kpi_summary_slide",
    "_render_chart_narrative_slide",
    "_render_comparison_split_slide",
    "_render_table_detail_slide",
    "_render_full_chart_takeaway_slide",
    "_render_two_charts_slide",
    "_render_action_plan_slide",
    "_render_generic_slide",
    "_table_slide",
]
