"""Visual Intelligence Engine for Phase 4.

The central visual intelligence layer that consumes execution artifacts (SlideExecutionPackage
from IBM Granite 4.0 or SlidePlan from Qwen 3.5), selects optimal visual representations,
constructs canonical VisualSpecification contracts, enforces WCAG accessibility standards,
and prepares renderer-neutral visual contracts.
"""

from __future__ import annotations

import datetime
import logging
from typing import Any

from .chart_models import (
    ChartFamily,
    ChartFormatting,
    ChartSeries,
    ChartSpec,
)
from .chart_selector import ChartSelector
from .design_tokens import SlideDesignTokens, normalize_slide_theme
from .diagram_models import (
    DiagramConnection,
    DiagramFamily,
    DiagramNode,
    DiagramSpec,
    MatrixFamily,
    MatrixQuadrant,
    MatrixSpec,
)
from .layout_registry import LayoutFamily, LayoutRegistry, LayoutSpec
from .layout_selector import LayoutSelector
from .visual_models import (
    PrimaryVisualDescriptor,
    SourceFooterSpec,
    TransitionType,
    VisualSpecification,
    VisualStory,
)
from .visual_validator import VisualValidator

logger = logging.getLogger(__name__)


class VisualIntelligenceEngine:
    """Central engine for synthesizing canonical VisualSpecifications from presentation execution artifacts."""

    def __init__(self, chart_selector: ChartSelector | None = None):
        self.chart_selector = chart_selector or ChartSelector()
        self.layout_selector = LayoutSelector()
        self.validator = VisualValidator()

    def process_slide(
        self,
        slide_package_or_dict: Any,
        theme_id: str = "bold_signal",
        sequence_number: int = 1,
        total_slides: int = 6
    ) -> VisualSpecification:
        """Processes a single slide package or dictionary and returns a canonical VisualSpecification."""
        tokens = normalize_slide_theme(theme_id)

        # 1. Unpack fields uniformly
        if hasattr(slide_package_or_dict, "headline"):
            headline = slide_package_or_dict.headline
            subtitle = getattr(slide_package_or_dict, "subtitle", "")
            seq_num = getattr(slide_package_or_dict, "sequence_number", sequence_number)
            content = getattr(slide_package_or_dict, "resolved_content", {})
            bullets = content.get("bullet_points", []) if isinstance(content, dict) else []
            key_msg = content.get("key_message", "") if isinstance(content, dict) else ""
            metrics = getattr(slide_package_or_dict, "resolved_metrics", [])
            chart_data = getattr(slide_package_or_dict, "chart_data", None)
            table_data = getattr(slide_package_or_dict, "table_data", None)
            v_intent = getattr(slide_package_or_dict, "visual_intent", {})
            v_type = v_intent.get("visual_type", "none") if isinstance(v_intent, dict) else "none"
            speaker_notes = getattr(slide_package_or_dict, "speaker_notes", "")
            raw_layout = getattr(slide_package_or_dict, "layout", None)
            ev_list = getattr(slide_package_or_dict, "resolved_evidence", [])
            ev_citation = ev_list[0].get("evidence_id", "EVID-EXEC-01") if ev_list else "EVID-EXEC-01"
            proposals = None
        else:
            # Plain dict
            d = slide_package_or_dict
            headline = d.get("title", d.get("headline", "Executive Briefing"))
            subtitle = d.get("subtitle", "")
            seq_num = d.get("order", d.get("sequence_number", sequence_number))
            bullets = d.get("bullets", [])
            key_msg = d.get("narrative", d.get("takeaway", ""))
            metrics = d.get("metrics") or []
            chart_data = d.get("chart")
            table_data = d.get("table") or d.get("table_data")
            v_type = d.get("visual_hook", "none")
            speaker_notes = d.get("notes", d.get("speaker_notes", ""))
            raw_layout = d.get("layout")
            ev_citation = d.get("evidence_id", "EVID-EXEC-01")
            proposals = d.get("structured_proposals")

        # 2. Layout Resolution
        metric_count = len(metrics) if metrics else 0
        has_chart = bool(chart_data)
        has_table = bool(table_data)

        if raw_layout:
            layout_spec = LayoutRegistry.get_canonical_layout(raw_layout)
        else:
            fam, variant = self.layout_selector.select_layout(
                slide_purpose="title" if seq_num == 1 else "content",
                visual_type=v_type,
                num_metrics=metric_count,
                has_chart=has_chart,
                has_table=has_table
            )
            layout_spec = LayoutRegistry.get_canonical_layout(fam)
            layout_spec.variant = variant

        # 3. Chart Resolution & ChartSpec Synthesis
        chart_spec = None
        chart_selection_reason = ""

        if chart_data:
            # Determine or map family
            c_type = chart_data.get("chart_type", "bar").lower()
            if "line" in c_type:
                target_fam = ChartFamily.LINE
            elif "donut" in c_type or "pie" in c_type:
                target_fam = ChartFamily.DONUT
            elif "area" in c_type:
                target_fam = ChartFamily.AREA
            elif "radar" in c_type:
                target_fam = ChartFamily.RADAR
            elif "scatter" in c_type:
                target_fam = ChartFamily.SCATTER
            elif "waterfall" in c_type:
                target_fam = ChartFamily.WATERFALL
            elif "sankey" in c_type:
                target_fam = ChartFamily.SANKEY
            elif "treemap" in c_type:
                target_fam = ChartFamily.TREEMAP
            else:
                target_fam = ChartFamily.BAR_VERTICAL

            # Extract series and categories
            cats = chart_data.get("categories", [])
            raw_series = chart_data.get("series", [])
            built_series = []

            for s in raw_series:
                if isinstance(s, dict):
                    built_series.append(
                        ChartSeries(
                            name=str(s.get("name", "Metric")),
                            data=s.get("values", s.get("data", [])),
                            stack=s.get("stack")
                        )
                    )

            if not built_series and chart_data.get("values"):
                built_series.append(
                    ChartSeries(
                        name="Value",
                        data=chart_data.get("values", [])
                    )
                )

            chart_spec = ChartSpec(
                chart_id=f"chart-{seq_num}",
                family=target_fam,
                title=chart_data.get("title", ""),
                subtitle=chart_data.get("subtitle", ""),
                categories=[str(c) for c in cats],
                series=built_series,
                formatting=ChartFormatting(
                    show_legend=len(built_series) > 1,
                    show_grid=True
                )
            )
            # Guardrail check
            chart_spec.validate_guardrails()
            chart_selection_reason = f"Explicitly mapped from execution chart data '{c_type}'"

        # 4. Diagram / Matrix Synthesis
        diagram_spec = None
        matrix_spec = None

        # Native model renderers use the supplied model data. A layout request
        # alone cannot establish talent cohorts, completion states or dates.

        # 5. Visual Story & Primary Visual Descriptor
        v_family_str = "CHART" if chart_spec else ("MATRIX" if matrix_spec else ("DIAGRAM" if diagram_spec else ("TABLE" if table_data else "TEXT")))
        primary_visual = PrimaryVisualDescriptor(
            visual_type=chart_spec.family.value if chart_spec else (matrix_spec.family.value if matrix_spec else v_type),
            visual_family=v_family_str,
            aspect_ratio="16:9" if layout_spec.family == LayoutFamily.CHART_FULL else "4:3",
            title=headline
        )

        visual_story = VisualStory(
            intent=v_type,
            primary_message=key_msg or headline,
            takeaway=key_msg,
            audience_focus="Executive Decision Makers"
        )

        # 6. Content Budgets & Insights
        budget = LayoutRegistry.get_budget(layout_spec.family)
        insights = bullets[:budget.max_insights] if bullets else ([key_msg] if key_msg else [])

        # 7. Source & Footer
        source_footer = SourceFooterSpec(
            dataset_label=slide_package_or_dict.get("source_label", "") if isinstance(slide_package_or_dict, dict) else "",
            source_citation="Recorded data",
            evidence_citation=ev_citation or "",
            slide_counter_text=f"{seq_num} / {total_slides}",
            confidentiality_label="CONFIDENTIAL - FOR INTERNAL USE ONLY"
        )

        # 8. Contrast & Budget Validation
        a11y_report = self.validator.validate_contrast(tokens)
        budget_validation = self.validator.validate_content_budget(
            headline=headline,
            body_text=" ".join(insights),
            insights=insights,
            budget=budget,
            table_row_count=len(table_data.get("rows", [])) if table_data else 0
        )

        return VisualSpecification(
            slide_id=getattr(slide_package_or_dict, "slide_id", "") or (slide_package_or_dict.get("id", f"slide_{seq_num}") if isinstance(slide_package_or_dict, dict) else f"slide_{seq_num}"),
            sequence_number=seq_num,
            headline=headline,
            subtitle=subtitle,
            theme_id=theme_id,
            visual_story=visual_story,
            layout=layout_spec,
            kpis=metrics or [],
            primary_visual=primary_visual,
            chart_spec=chart_spec,
            matrix_spec=matrix_spec,
            diagram_spec=diagram_spec,
            insights=insights,
            table_data=table_data,
            structured_proposals=proposals,
            speaker_notes=speaker_notes,
            source_footer=source_footer,
            design_tokens=tokens,
            accessibility_report=a11y_report,
            budget_validation=budget_validation,
            chart_selection_reason=chart_selection_reason,
            generated_at=datetime.datetime.now(datetime.timezone.utc).isoformat()
        )
