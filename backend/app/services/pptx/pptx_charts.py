"""Native PowerPoint chart and 9-box matrix builders."""

import logging
import math
from pptx.util import Inches, Pt
from pptx.oxml.xmlchemy import OxmlElement
from pptx.dml.fill import FillFormat
from pptx.enum.shapes import MSO_SHAPE
from pptx.chart.data import CategoryChartData
from pptx.enum.chart import XL_CHART_TYPE, XL_LEGEND_POSITION, XL_DATA_LABEL_POSITION

from .pptx_styles import ChartExportError, hex_to_rgb

logger = logging.getLogger(__name__)


def _add_native_chart_shape(slide, chart_info: dict, x, y, cx, cy, colors: dict, theme_palette: list[str] | None = None):
    if not isinstance(chart_info, dict):
        raise ChartExportError("Chart specification must be a dictionary.")

    raw_cats = chart_info.get("categories")
    if not raw_cats or not isinstance(raw_cats, (list, tuple)) or len(raw_cats) == 0:
        raise ChartExportError(
            f"Chart '{chart_info.get('title', 'Untitled')}' has empty categories. "
            "Fabricated categories are prohibited."
        )
    categories = [str(c) for c in raw_cats]

    series_list = chart_info.get("series")
    if not series_list or not isinstance(series_list, (list, tuple)) or len(series_list) == 0:
        raise ChartExportError(
            f"Chart '{chart_info.get('title', 'Untitled')}' has no series data."
        )

    for s in series_list:
        s_name = str(s.get("name", "Metric"))
        s_vals = s.get("values")
        if s_vals is None or not isinstance(s_vals, (list, tuple)):
            raise ChartExportError(f"Series '{s_name}' has invalid or missing values.")
        if len(s_vals) != len(categories):
            raise ChartExportError(
                f"Series '{s_name}' values length ({len(s_vals)}) does not match categories length ({len(categories)}). "
                "Zero substitution or padding is prohibited."
            )
        for idx, v in enumerate(s_vals):
            if v is None or not isinstance(v, (int, float)) or not math.isfinite(v):
                raise ChartExportError(
                    f"Series '{s_name}' category '{categories[idx]}' has non-finite or null value: {v}. "
                    "Zero substitution for missing data is prohibited."
                )

    raw_type = (chart_info.get("chart_type") or chart_info.get("type") or "column").lower()
    if raw_type in ("bar", "horizontal_bar"):
        xl_type = XL_CHART_TYPE.BAR_CLUSTERED
    elif raw_type in ("line", "area"):
        xl_type = XL_CHART_TYPE.LINE
    elif raw_type in ("pie",):
        xl_type = XL_CHART_TYPE.PIE
    elif raw_type in ("donut", "doughnut"):
        xl_type = XL_CHART_TYPE.DOUGHNUT
    else:
        xl_type = XL_CHART_TYPE.COLUMN_CLUSTERED

    cdata = CategoryChartData()
    cdata.categories = categories

    for s in series_list:
        s_name = str(s.get("name", "Metric"))
        s_vals = tuple(float(v) for v in s["values"])
        cdata.add_series(s_name, s_vals)

    try:
        chart_shape = slide.shapes.add_chart(xl_type, x, y, cx, cy, cdata)
        chart = chart_shape.chart
        for element in chart._chartSpace.iter():
            if element.tag.rsplit('}', 1)[-1] in {'axId', 'crossAx'} and element.get('val'):
                value = int(element.get('val'))
                if value < 0:
                    element.set('val', str(value % (2**32)))
        chart.has_legend = True
        chart.legend.position = XL_LEGEND_POSITION.TOP
        chart.legend.include_in_layout = False
        chart.font.color.rgb = colors["secondary"]
        chart.font.size = Pt(11)
        chart.has_title = True
        chart.chart_title.text_frame.text = chart_info.get('title') or series_list[0].get('name') or 'Recorded values'
        for paragraph in chart.chart_title.text_frame.paragraphs:
            paragraph.font.color.rgb = colors['primary']
            paragraph.font.size = Pt(12)
        chart.plots[0].has_data_labels = True
        chart.plots[0].data_labels.font.color.rgb = colors['primary']
        chart.plots[0].data_labels.font.size = Pt(10)
        count_unit = chart_info.get('unit') in {'rows', 'count', 'employees', 'personnel'}
        number_format = '0' if count_unit else '0.00'
        chart.plots[0].data_labels.number_format = number_format
        chart.plots[0].data_labels.position = XL_DATA_LABEL_POSITION.ABOVE if xl_type == XL_CHART_TYPE.LINE else XL_DATA_LABEL_POSITION.OUTSIDE_END
        chart.legend.font.color.rgb = colors["secondary"]
        chart.legend.font.size = Pt(11)
        # Explicit fills prevent Office's default white chart area in dark decks.
        for element in (chart._chartSpace, chart._chartSpace.plotArea):
            sp_pr = OxmlElement("c:spPr")
            fill = FillFormat.from_fill_parent(sp_pr)
            fill.solid()
            fill.fore_color.rgb = colors["card_bg"]
            if element is chart._chartSpace:
                element.insert_element_before(sp_pr, "c:txPr", "c:externalData", "c:printSettings", "c:userShapes", "c:extLst")
            else:
                element.insert_element_before(sp_pr, "c:extLst")
        if xl_type not in (XL_CHART_TYPE.PIE, XL_CHART_TYPE.DOUGHNUT):
            for axis in (chart.category_axis, chart.value_axis):
                axis.tick_labels.font.color.rgb = colors["secondary"]
                axis.tick_labels.font.size = Pt(11)
                axis.tick_labels.number_format = number_format
                axis.tick_labels.number_format_is_linked = False
                axis.format.line.color.rgb = colors["card_border"]
                if axis.has_major_gridlines:
                    axis.major_gridlines.format.line.color.rgb = colors["card_border"]
            if count_unit:
                chart.value_axis.major_unit = 1


        if theme_palette:
            if xl_type in (XL_CHART_TYPE.PIE, XL_CHART_TYPE.DOUGHNUT):
                if chart.series and len(chart.series) > 0:
                    for p_idx, point in enumerate(chart.series[0].points):
                        c_hex = theme_palette[p_idx % len(theme_palette)]
                        try:
                            point.format.fill.solid()
                            point.format.fill.fore_color.rgb = hex_to_rgb(c_hex)
                            point.format.line.color.rgb = colors["card_bg"]
                            point.format.line.width = Pt(1.5)
                        except Exception:
                            pass
            elif xl_type == XL_CHART_TYPE.LINE:
                for s_idx, series in enumerate(chart.series):
                    c_hex = theme_palette[s_idx % len(theme_palette)]
                    try:
                        series.format.line.color.rgb = hex_to_rgb(c_hex)
                    except Exception:
                        pass
            else:
                for s_idx, series in enumerate(chart.series):
                    c_hex = theme_palette[s_idx % len(theme_palette)]
                    try:
                        series.format.fill.solid()
                        series.format.fill.fore_color.rgb = hex_to_rgb(c_hex)
                    except Exception:
                        pass
    except Exception as exc:
        logger.exception(f"python-pptx failed to create native chart: {exc}")
        raise ChartExportError(
            f"Failed to generate native PowerPoint chart '{chart_info.get('title', 'Untitled')}': {exc}"
        ) from exc


def _render_native_9box_matrix(slide, t9: dict, x, y, cx, cy, colors: dict):
    """Renders a native styled 3x3 table matrix for McKinsey/GE 9-Box talent analytics in PowerPoint."""
    card = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, x, y, cx, cy)
    card.fill.solid()
    card.fill.fore_color.rgb = colors["card_bg"]
    card.line.color.rgb = colors["card_border"]
    card.line.width = Pt(1)

    tf = card.text_frame
    tf.word_wrap = True
    tf.margin_left = Inches(0.2)
    tf.margin_top = Inches(0.15)
    p_head = tf.paragraphs[0]
    p_head.text = "McKinsey / GE 9-Box Strategic Talent & Risk Distribution"
    p_head.font.size = Pt(11)
    p_head.font.bold = True
    p_head.font.color.rgb = colors["accent"]

    num_rows = 4
    num_cols = 4
    tbl_shape = slide.shapes.add_table(
        num_rows, num_cols,
        x + Inches(0.2), y + Inches(0.55),
        cx - Inches(0.4), cy - Inches(0.75)
    )
    tbl = tbl_shape.table

    tbl.columns[0].width = Inches(1.3)
    for c in range(1, 4):
        tbl.columns[c].width = Inches(1.6)

    headers = ["Perf \\ Risk", "Low Risk (Stable)", "Medium Risk", "High Risk (Flight Risk)"]
    for c, h in enumerate(headers):
        cell = tbl.cell(0, c)
        cell.fill.solid()
        cell.fill.fore_color.rgb = colors["bg"]
        p = cell.text_frame.paragraphs[0]
        p.text = h
        p.font.size = Pt(8.5)
        p.font.bold = True
        p.font.color.rgb = colors["brand"] if c > 0 else colors["secondary"]

    cell_map = {}
    for item in t9.get("cells", []):
        r_lbl = str(item.get("row", "")).capitalize()
        c_lbl = str(item.get("col", "")).lower()
        if "low" in c_lbl:
            col_idx = 1
        elif "high" in c_lbl:
            col_idx = 3
        else:
            col_idx = 2
        cell_map[(r_lbl, col_idx)] = item

    row_defs = [("High", "High Output"), ("Med", "Medium Output"), ("Low", "Baseline Output")]
    for r_idx, (r_key, r_label) in enumerate(row_defs):
        row_num = r_idx + 1
        l_cell = tbl.cell(row_num, 0)
        l_cell.fill.solid()
        l_cell.fill.fore_color.rgb = colors["bg"]
        lp = l_cell.text_frame.paragraphs[0]
        lp.text = r_label
        lp.font.size = Pt(8.5)
        lp.font.bold = True
        lp.font.color.rgb = colors["accent"]

        for c_idx in range(1, 4):
            bcell = tbl.cell(row_num, c_idx)
            bcell.fill.solid()
            bcell.fill.fore_color.rgb = colors["card_bg"]
            item = cell_map.get((r_key, c_idx), {})
            cnt = item.get("count", 0)
            title = item.get("title", "")
            if len(title) > 20:
                title = title.split("(")[0].strip()
            bp = bcell.text_frame.paragraphs[0]
            bp.text = f"{cnt} Staff"
            bp.font.size = Pt(11)
            bp.font.bold = True
            bp.font.color.rgb = colors["primary"] if cnt > 0 else colors["secondary"]

            if title:
                bp2 = bcell.text_frame.add_paragraph()
                bp2.text = title
                bp2.font.size = Pt(7.5)
                bp2.font.color.rgb = colors["secondary"]
