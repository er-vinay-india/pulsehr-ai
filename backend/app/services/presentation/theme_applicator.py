"""HighView Presentation Studio — PPT-L7 Theme Applicator.

Applies resolved ThemeDefinition styles in-place to an instantiated PowerPoint
presentation (.pptx) using high-level python-pptx APIs. Strictly preserves
existing geometry, coordinates, box dimensions, font sizes, content, object
identities, and DrawingML editability.
"""

from __future__ import annotations

import logging
from typing import Any, Optional

import pptx
from pptx.dml.color import RGBColor

from app.services.presentation.layout_models import ResolvedDeckLayout
from app.services.presentation.render_models import RenderManifest
from app.services.presentation.theme_engine import (
    ChartStyleResolver,
    StyleTokenResolver,
    TableStyleResolver,
    TextStyleResolver,
)
from app.services.presentation.theme_models import (
    AccessibilityAuditResult,
    ChartSeriesStyleOutcome,
    ObjectStyleOutcome,
    SlideStyleOutcome,
    StyleManifest,
    StyleRole,
    TableStyleOutcome,
    ThemeDefinition,
    compute_style_manifest_fingerprint,
)
from app.services.presentation.visual.visual_validator import parse_hex_color

logger = logging.getLogger(__name__)


def _hex_to_rgb(hex_code: str) -> RGBColor:
    r, g, b = parse_hex_color(hex_code)
    return RGBColor(r, g, b)


def _determine_style_role(
    object_name: str,
    zone_id: str,
    metadata: Optional[dict[str, Any]] = None,
) -> StyleRole:
    """Maps semantic object identity and zone to a concrete StyleRole."""
    name_upper = object_name.upper()
    zone_upper = zone_id.upper()

    if "__VALUE" in name_upper or "KPI_VALUE" in name_upper:
        return StyleRole.KPI_VALUE
    if "__UNIT" in name_upper:
        return StyleRole.KPI_UNIT
    if "__LABEL" in name_upper or "KPI_LABEL" in name_upper:
        return StyleRole.KPI_LABEL
    if "HEADER" in zone_upper or "TITLE" in name_upper:
        if "SUBTITLE" in name_upper or "SUB_HEADLINE" in name_upper:
            return StyleRole.SUBTITLE
        return StyleRole.TITLE
    if "FOOTER" in zone_upper:
        if "PAGE" in name_upper or "NUMBER" in name_upper:
            return StyleRole.PAGE_NUMBER
        return StyleRole.FOOTNOTE
    if "TABLE" in name_upper:
        return StyleRole.TABLE_BODY
    if "CHART" in name_upper:
        return StyleRole.CHART_SERIES
    if "CAPTION" in name_upper:
        return StyleRole.CAPTION

    return StyleRole.BODY


class ThemeApplicator:
    """Applies theme colors, typography families, and styling to PowerPoint presentations."""

    def __init__(self, theme: ThemeDefinition):
        self.theme = theme
        self.token_resolver = StyleTokenResolver(theme)
        self.text_resolver = TextStyleResolver(self.token_resolver)
        self.table_resolver = TableStyleResolver(self.token_resolver)
        self.chart_resolver = ChartStyleResolver(self.token_resolver)

    def apply_theme(
        self,
        prs: pptx.presentation.Presentation,
        render_manifest: RenderManifest,
        resolved_deck: Optional[ResolvedDeckLayout] = None,
        overrides: Optional[dict[str, Any]] = None,
    ) -> tuple[pptx.presentation.Presentation, StyleManifest]:
        """Applies theme styling to presentation in-place.

        Returns (styled_prs, style_manifest).
        """
        all_object_styles: list[ObjectStyleOutcome] = []
        all_chart_styles: list[ChartSeriesStyleOutcome] = []
        all_table_styles: list[TableStyleOutcome] = []
        all_slide_styles: list[SlideStyleOutcome] = []
        all_audits: list[AccessibilityAuditResult] = []
        all_warnings: list[str] = []

        slide_bg_hex = self.theme.palette.background
        bg_rgb = _hex_to_rgb(slide_bg_hex)

        rendered_slides = {r.slide_index: r for r in render_manifest.slides}
        resolved_slides = {idx: s for idx, s in enumerate(resolved_deck.slides)} if resolved_deck else {}

        for slide_idx, slide in enumerate(prs.slides):
            rendered_record = rendered_slides.get(slide_idx)
            resolved_slide = resolved_slides.get(slide_idx)
            phys_id = rendered_record.physical_slide_id if rendered_record else f"SLIDE_{slide_idx + 1}"

            # 1. Apply Slide Background
            try:
                slide.background.fill.solid()
                slide.background.fill.fore_color.rgb = bg_rgb
            except Exception as e:
                all_warnings.append(f"Could not set background for slide {slide_idx + 1}: {e}")

            # Check if this is a title slide
            is_title_slide = False
            if resolved_slide and resolved_slide.metadata.get("layout_family") == "TITLE":
                is_title_slide = True

            styled_count_for_slide = 0

            # 2. Iterate through shapes
            for shape in slide.shapes:
                shape_name = shape.name or f"SHAPE_{shape.shape_id}"
                
                # Retrieve rendered object record if available
                matching_record = None
                if rendered_record:
                    for obj_rec in rendered_record.objects:
                        if obj_rec.object_name == shape_name or obj_rec.object_id in shape_name:
                            matching_record = obj_rec
                            break

                object_id = matching_record.object_id if matching_record else shape_name
                zone_id = matching_record.zone_id if matching_record else "ZONE_MAIN"

                # A. Handle Native Text
                if shape.has_text_frame:
                    style_role = _determine_style_role(shape_name, zone_id)
                    style_res, audits, warnings = self.text_resolver.resolve_text_style(
                        style_role=style_role,
                        bg_hex=slide_bg_hex,
                        target_id=object_id,
                        is_title_slide=is_title_slide,
                    )
                    all_audits.extend(audits)
                    all_warnings.extend(warnings)

                    font_name = style_res["font_family"]
                    font_rgb = _hex_to_rgb(style_res["font_color_hex"])
                    bold = style_res["bold"]
                    italic = style_res["italic"]

                    # Apply to runs while leaving font size untouched
                    for p in shape.text_frame.paragraphs:
                        if not p.runs and p.text:
                            # Apply directly to paragraph font
                            p.font.name = font_name
                            p.font.bold = bold
                            p.font.italic = italic
                            p.font.color.rgb = font_rgb
                        for r in p.runs:
                            r.font.name = font_name
                            r.font.bold = bold
                            r.font.italic = italic
                            r.font.color.rgb = font_rgb

                    all_object_styles.append(
                        ObjectStyleOutcome(
                            object_id=object_id,
                            object_name=shape_name,
                            style_role=style_role,
                            font_family=font_name,
                            font_weight="bold" if bold else "normal",
                            font_color_hex=style_res["font_color_hex"],
                            contrast_ratio=audits[0].contrast_ratio if audits else None,
                            resolved_tokens={"font_color": style_res["font_color_hex"]},
                            warnings=warnings,
                        )
                    )
                    styled_count_for_slide += 1

                # B. Handle Native Table
                elif shape.has_table:
                    tbl = shape.table
                    style_res, audits, warnings = self.table_resolver.resolve_table_style(
                        table_object_id=object_id,
                        slide_bg_hex=slide_bg_hex,
                    )
                    all_audits.extend(audits)
                    all_warnings.extend(warnings)

                    header_fill_rgb = _hex_to_rgb(style_res["header_fill_hex"])
                    header_text_rgb = _hex_to_rgb(style_res["header_text_hex"])
                    body_text_rgb = _hex_to_rgb(style_res["body_text_hex"])
                    font_name = style_res["font_family"]

                    # Header row (row 0)
                    if len(tbl.rows) > 0:
                        for cell in tbl.rows[0].cells:
                            cell.fill.solid()
                            cell.fill.fore_color.rgb = header_fill_rgb
                            for p in cell.text_frame.paragraphs:
                                p.font.name = font_name
                                p.font.bold = True
                                p.font.color.rgb = header_text_rgb
                                for r in p.runs:
                                    r.font.name = font_name
                                    r.font.bold = True
                                    r.font.color.rgb = header_text_rgb

                    # Body rows
                    for r_idx in range(1, len(tbl.rows)):
                        row = tbl.rows[r_idx]
                        for cell in row.cells:
                            for p in cell.text_frame.paragraphs:
                                p.font.name = font_name
                                p.font.color.rgb = body_text_rgb
                                for r in p.runs:
                                    r.font.name = font_name
                                    r.font.color.rgb = body_text_rgb

                    all_table_styles.append(
                        TableStyleOutcome(
                            object_id=object_id,
                            header_fill_hex=style_res["header_fill_hex"],
                            header_text_hex=style_res["header_text_hex"],
                            body_text_hex=style_res["body_text_hex"],
                            alt_row_fill_hex=style_res["alt_row_fill_hex"],
                            border_color_hex=style_res["border_color_hex"],
                            header_contrast=style_res["header_contrast"],
                            body_contrast=style_res["body_contrast"],
                        )
                    )
                    all_object_styles.append(
                        ObjectStyleOutcome(
                            object_id=object_id,
                            object_name=shape_name,
                            style_role=StyleRole.TABLE_BODY,
                            font_family=font_name,
                            fill_color_hex=style_res["header_fill_hex"],
                            stroke_color_hex=style_res["border_color_hex"],
                            contrast_ratio=style_res["header_contrast"],
                            resolved_tokens={
                                "header_fill": style_res["header_fill_hex"],
                                "header_text": style_res["header_text_hex"],
                                "body_text": style_res["body_text_hex"],
                            },
                        )
                    )
                    styled_count_for_slide += 1

                # C. Handle Native Chart
                elif shape.has_chart:
                    chart = shape.chart
                    # Style series
                    for s_idx, series in enumerate(chart.series):
                        series_name = getattr(series, "name", f"Series_{s_idx + 1}")
                        series_color = self.chart_resolver.resolve_series_color(
                            series_name=str(series_name),
                            series_index=s_idx,
                        )
                        series_rgb = _hex_to_rgb(series_color)
                        try:
                            series.format.fill.solid()
                            series.format.fill.fore_color.rgb = series_rgb
                        except Exception as e:
                            all_warnings.append(f"Could not style chart series '{series_name}': {e}")

                        all_chart_styles.append(
                            ChartSeriesStyleOutcome(
                                series_index=s_idx,
                                series_name=str(series_name),
                                color_hex=series_color,
                                token_used=f"CATEGORICAL_{s_idx}",
                            )
                        )

                    # Style chart chrome (axes/labels)
                    chrome_style, chrome_audits = self.chart_resolver.resolve_chart_chrome(slide_bg_hex)
                    all_audits.extend(chrome_audits)
                    self._apply_chart_chrome(chart, chrome_style, all_warnings)

                    all_object_styles.append(
                        ObjectStyleOutcome(
                            object_id=object_id,
                            object_name=shape_name,
                            style_role=StyleRole.CHART_SERIES,
                            font_family=chrome_style["font_family"],
                            fill_color_hex=self.theme.chart_palette.categorical[0] if self.theme.chart_palette.categorical else None,
                            stroke_color_hex=chrome_style["axis_color_hex"],
                            contrast_ratio=chrome_audits[0].contrast_ratio if chrome_audits else None,
                            resolved_tokens={"axis_color": chrome_style["axis_color_hex"]},
                        )
                    )
                    styled_count_for_slide += 1

                # D. Image / Map Picture (Preserve truthful raster, style frame if applicable)
                else:
                    all_object_styles.append(
                        ObjectStyleOutcome(
                            object_id=object_id,
                            object_name=shape_name,
                            style_role=StyleRole.CARD_SURFACE,
                            stroke_color_hex=self.theme.border_tokens.subtle,
                            resolved_tokens={"border_color": self.theme.border_tokens.subtle},
                        )
                    )
                    styled_count_for_slide += 1

            all_slide_styles.append(
                SlideStyleOutcome(
                    slide_index=slide_idx,
                    physical_slide_id=phys_id,
                    background_fill_hex=slide_bg_hex,
                    background_mode=self.theme.mode.value,
                    styled_object_count=styled_count_for_slide,
                )
            )

        manifest = StyleManifest(
            theme_id=self.theme.theme_id,
            theme_version=self.theme.version,
            mode=self.theme.mode,
            slide_styles=all_slide_styles,
            object_styles=all_object_styles,
            chart_series_styles=all_chart_styles,
            table_styles=all_table_styles,
            accessibility_results=all_audits,
            warnings=all_warnings,
            stats={
                "slides_styled": len(prs.slides),
                "objects_styled": len(all_object_styles),
                "chart_series_styled": len(all_chart_styles),
                "tables_styled": len(all_table_styles),
                "accessibility_checks": len(all_audits),
                "warnings_count": len(all_warnings),
            },
        )
        manifest.style_fingerprint = compute_style_manifest_fingerprint(manifest)
        return prs, manifest

    def _apply_chart_chrome(
        self,
        chart: Any,
        chrome_style: dict[str, Any],
        all_warnings: list[str],
    ) -> None:
        """Applies axis line, ticks, gridlines, legend, and plot area styling to a native chart."""
        try:
            tick_hex = chrome_style.get("tick_text_color_hex") or chrome_style.get("label_color_hex")
            tick_rgb = _hex_to_rgb(tick_hex) if tick_hex else None

            axis_line_hex = chrome_style.get("axis_line_color_hex") or chrome_style.get("axis_color_hex")
            axis_line_rgb = _hex_to_rgb(axis_line_hex) if axis_line_hex else None

            grid_hex = chrome_style.get("grid_color_hex")
            grid_rgb = _hex_to_rgb(grid_hex) if grid_hex else None

            axis_title_hex = chrome_style.get("axis_title_color_hex") or tick_hex
            axis_title_rgb = _hex_to_rgb(axis_title_hex) if axis_title_hex else None

            legend_hex = chrome_style.get("legend_text_color_hex") or tick_hex
            legend_rgb = _hex_to_rgb(legend_hex) if legend_hex else None

            data_label_hex = chrome_style.get("data_label_color_hex") or tick_hex
            data_label_rgb = _hex_to_rgb(data_label_hex) if data_label_hex else None

            # 1. Axis styling (Category and Value axes)
            for axis_name in ("category_axis", "value_axis"):
                axis = getattr(chart, axis_name, None)
                if axis is None:
                    continue
                try:
                    if axis_line_rgb:
                        axis.format.line.color.rgb = axis_line_rgb
                except Exception as e:
                    logger.debug("Could not style %s line: %s", axis_name, e)
                try:
                    if tick_rgb and hasattr(axis, "tick_labels") and axis.tick_labels:
                        axis.tick_labels.font.color.rgb = tick_rgb
                except Exception as e:
                    logger.debug("Could not style %s tick labels: %s", axis_name, e)
                try:
                    if grid_rgb and getattr(axis, "has_major_gridlines", False):
                        axis.major_gridlines.format.line.color.rgb = grid_rgb
                except Exception as e:
                    logger.debug("Could not style %s major gridlines: %s", axis_name, e)
                try:
                    if axis_title_rgb and getattr(axis, "has_title", False) and axis.axis_title.has_text_frame:
                        for p in axis.axis_title.text_frame.paragraphs:
                            p.font.color.rgb = axis_title_rgb
                except Exception as e:
                    logger.debug("Could not style %s title: %s", axis_name, e)

            # 2. Legend styling
            if getattr(chart, "has_legend", False) and chart.legend is not None:
                try:
                    if legend_rgb and hasattr(chart.legend, "font") and chart.legend.font:
                        chart.legend.font.color.rgb = legend_rgb
                except Exception as e:
                    logger.debug("Could not style chart legend font: %s", e)

            # 3. Data labels
            try:
                for plot in getattr(chart, "plots", []):
                    if getattr(plot, "has_data_labels", False) and plot.data_labels is not None:
                        if data_label_rgb and hasattr(plot.data_labels, "font") and plot.data_labels.font:
                            plot.data_labels.font.color.rgb = data_label_rgb
            except Exception as e:
                logger.debug("Could not style chart data labels: %s", e)

            # 4. Explicit plot area / chart space fill (prevents Office default white box on dark themes)
            plot_bg_hex = chrome_style.get("plot_bg_hex")
            if plot_bg_hex:
                try:
                    from pptx.oxml.xmlchemy import OxmlElement
                    from pptx.dml.fill import FillFormat
                    plot_bg_rgb = _hex_to_rgb(plot_bg_hex)
                    chart_space = getattr(chart, "_chartSpace", None)
                    if chart_space is not None:
                        plot_area = getattr(chart_space, "plotArea", None)
                        for element in (chart_space, plot_area):
                            if element is None:
                                continue
                            sp_pr = OxmlElement("c:spPr")
                            fill = FillFormat.from_fill_parent(sp_pr)
                            fill.solid()
                            fill.fore_color.rgb = plot_bg_rgb
                            if element is chart_space:
                                element.insert_element_before(
                                    sp_pr,
                                    "c:txPr",
                                    "c:externalData",
                                    "c:printSettings",
                                    "c:userShapes",
                                    "c:extLst",
                                )
                            else:
                                element.insert_element_before(sp_pr, "c:extLst")
                except Exception as e:
                    logger.debug("Could not set chart plot area background: %s", e)
        except Exception as e:
            all_warnings.append(f"Failed to style chart chrome: {e}")
