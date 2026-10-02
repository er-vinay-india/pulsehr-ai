"""PowerPoint (PPTX) Structural Parity Adapter for Phase 4.

Maps canonical VisualSpecification contracts into PowerPoint-compatible slide dictionaries
matching the existing PresentationDeckSpec v2.0 format, ensuring structural parity
between web rendering and exported PPTX presentations.
"""

from __future__ import annotations

from typing import Any
from ..chart_models import ChartFamily, ChartSpec
from ..design_tokens import SlideDesignTokens
from ..visual_models import VisualSpecification


class PPTXAdapter:
    """Transforms a canonical VisualSpecification into a PPTX-ready slide definition."""

    @classmethod
    def to_pptx_slide_dict(
        cls,
        spec: VisualSpecification,
        tokens: SlideDesignTokens
    ) -> dict[str, Any]:
        """Maps VisualSpecification to the canonical PresentationDeckSpec slide representation."""
        layout_name = spec.layout.family.value.lower()
        if spec.layout.variant:
            # Map canonical family to legacy slide dictionary layout for exporter compatibility
            if spec.layout.family.value == "TITLE_HERO":
                layout_name = "title_hero" if spec.layout.variant != "title_cover" else "title_cover"
            elif spec.layout.family.value == "KPI_GRID":
                layout_name = "kpi_summary"
            elif spec.layout.family.value == "CHART_INSIGHT":
                layout_name = "chart_narrative"
            elif spec.layout.family.value == "CHART_FULL":
                layout_name = "full_chart_takeaway"
            elif spec.layout.family.value == "DUAL_CHART":
                layout_name = "two_charts"
            elif spec.layout.family.value == "COMPARISON":
                layout_name = "comparison_split"
            elif spec.layout.family.value == "ACTION_PLAN":
                layout_name = "action_plan"
            elif spec.layout.family.value == "TABLE":
                layout_name = "table_detail"

        # Transform chart spec to standard exporter chart dictionary
        chart_dict = None
        if spec.chart_spec:
            cs = spec.chart_spec
            chart_type_str = "bar"
            if "line" in cs.family.value:
                chart_type_str = "line"
            elif "donut" in cs.family.value or "pie" in cs.family.value:
                chart_type_str = "donut"

            chart_dict = {
                "chart_type": chart_type_str,
                "title": cs.title or spec.headline,
                "subtitle": cs.subtitle or spec.subtitle,
                "categories": cs.categories,
                "series": [
                    {"name": s.name, "values": s.data}
                    for s in cs.series
                ]
            }

        # Build metrics list
        metrics_list = []
        for k in spec.kpis:
            metrics_list.append({
                "label": k.get("label", "Metric"),
                "value": str(k.get("value", "0")),
                "subtext": k.get("subtext", ""),
                "evidence_id": k.get("evidence_id", "EVID-EXEC-01")
            })

        # Base slide dictionary
        slide_dict: dict[str, Any] = {
            "slide_index": spec.sequence_number,
            "title": spec.headline,
            "subtitle": spec.subtitle,
            "category": spec.visual_story.primary_message or "Executive Briefing",
            "layout": layout_name,
            "narrative": "\n".join(spec.insights) if spec.insights else spec.visual_story.primary_message,
            "takeaway": spec.visual_story.primary_message,
            "metrics": metrics_list if metrics_list else None,
            "chart": chart_dict,
            "table_data": spec.table_data,
            "structured_proposals": spec.structured_proposals if spec.structured_proposals else None,
            "speaker_notes": spec.speaker_notes,
            "evidence_id": spec.source_footer.evidence_citation or "EVID-EXEC-01",
            "source_label": spec.source_footer.dataset_label,
            "metadata": {
                "canonical_family": spec.layout.family.value,
                "layout_variant": spec.layout.variant,
                "visual_family": spec.primary_visual.visual_family,
                "chart_selection_reason": spec.chart_selection_reason,
                "theme_id": tokens.theme_id
            }
        }

        return slide_dict

    @classmethod
    def export_deck(
        cls,
        specs: list[VisualSpecification],
        theme_id: str = "bold_signal",
        deck_title: str = "Executive Presentation"
    ) -> Any:
        """Exports a list of VisualSpecification slides directly to a native PPTX file."""
        import time
        from ..design_tokens import normalize_slide_theme
        from ....report_generator import export_spec_to_pptx

        tokens = normalize_slide_theme(theme_id)
        slides_data = [cls.to_pptx_slide_dict(s, tokens) for s in specs]
        deck_spec = {
            "id": f"deck_{int(time.time())}",
            "spec_version": "2.0",
            "metadata": {
                "title": deck_title,
                "theme_id": theme_id,
            },
            "slides": slides_data
        }
        return export_spec_to_pptx(deck_spec)
