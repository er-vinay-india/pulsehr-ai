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

    raw_type = (chart_info.get("chart_type") or chart_info.get("type") or "column").lower()
    if raw_type == "breakdown_tree" or chart_info.get("tree_data"):
        return _render_native_breakdown_tree(slide, chart_info, x, y, cx, cy, colors)
    if raw_type == "waterfall" or chart_info.get("waterfall_steps"):
        return _render_native_waterfall(slide, chart_info, x, y, cx, cy, colors, theme_palette)

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
        chart.has_legend = len(series_list) > 1
        if chart.has_legend:
            chart.legend.position = XL_LEGEND_POSITION.TOP
            chart.legend.include_in_layout = False
            chart.legend.font.color.rgb = colors["secondary"]
            chart.legend.font.size = Pt(14)
        chart.font.color.rgb = colors["secondary"]
        chart.font.size = Pt(14)
        chart.has_title = True
        chart.chart_title.text_frame.text = chart_info.get('title') or series_list[0].get('name') or 'Recorded values'
        for paragraph in chart.chart_title.text_frame.paragraphs:
            paragraph.font.color.rgb = colors['primary']
            paragraph.font.size = Pt(18)
        chart.plots[0].has_data_labels = True
        chart.plots[0].data_labels.font.color.rgb = colors['primary']
        chart.plots[0].data_labels.font.size = Pt(14)
        count_unit = chart_info.get('unit') in {'rows', 'count', 'employees', 'personnel'}
        largest = max(abs(v) for series in series_list for v in series['values'])
        number_format = '0.0,,"M"' if largest >= 1_000_000 else ('0' if count_unit else '0.00')
        chart.plots[0].data_labels.number_format = number_format
        chart.plots[0].data_labels.position = XL_DATA_LABEL_POSITION.ABOVE if xl_type == XL_CHART_TYPE.LINE else XL_DATA_LABEL_POSITION.OUTSIDE_END
        if xl_type in (XL_CHART_TYPE.PIE, XL_CHART_TYPE.DOUGHNUT):
            chart.plots[0].data_labels.show_category_name = True
            chart.plots[0].data_labels.show_percentage = True
            chart.plots[0].data_labels.show_value = True
        if chart.has_legend:
            chart.legend.font.color.rgb = colors["secondary"]
            chart.legend.font.size = Pt(14)
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
            if xl_type == XL_CHART_TYPE.BAR_CLUSTERED:
                chart.category_axis.reverse_order = True
            for axis in (chart.category_axis, chart.value_axis):
                axis.tick_labels.font.color.rgb = colors["secondary"]
                axis.tick_labels.font.size = Pt(14)
                axis.tick_labels.number_format = number_format
                axis.tick_labels.number_format_is_linked = False
                axis.format.line.color.rgb = colors["card_border"]
                if axis.has_major_gridlines:
                    axis.major_gridlines.format.line.color.rgb = colors["card_border"]
            if count_unit and largest <= 10:
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
    p_head.font.size = Pt(14)
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
            bp.font.size = Pt(14)
            bp.font.bold = True
            bp.font.color.rgb = colors["primary"] if cnt > 0 else colors["secondary"]

            if title:
                bp2 = bcell.text_frame.add_paragraph()
                bp2.text = title
                bp2.font.size = Pt(7.5)
                bp2.font.color.rgb = colors["secondary"]


def _render_native_breakdown_tree(slide, chart_info: dict, x, y, cx, cy, colors: dict):
    """Renders a native styled breakdown tree for multi-factor disparities in PowerPoint."""
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
    p_head.text = chart_info.get("title", "Breakdown Tree Decomposition")
    p_head.font.size = Pt(13)
    p_head.font.bold = True
    p_head.font.color.rgb = colors["accent"]

    tree_data = chart_info.get("tree_data") or {}
    root_name = tree_data.get("name", "Overall Baseline")
    root_val = tree_data.get("value", "—")
    root_n = tree_data.get("sample_size", "")
    unit = tree_data.get("unit") or chart_info.get("unit") or ""

    children = tree_data.get("children", [])
    child1 = children[0] if children else {}
    c1_name = child1.get("name", "Dimension 1")
    c1_val = child1.get("value", "—")
    c1_n = child1.get("sample_size", "")

    leaves = child1.get("children", [])
    leaf = leaves[0] if leaves else {}
    leaf_name = leaf.get("name", "Target Cohort")
    leaf_val = leaf.get("value", "—")
    leaf_n = leaf.get("sample_size", "")
    leaf_sev = leaf.get("severity", "warning")

    node_w = Inches(1.8)
    node_h = Inches(1.8)
    node_y = y + Inches(0.65)

    # 1. Root Box
    b1 = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, x + Inches(0.3), node_y, node_w, node_h)
    b1.fill.solid()
    b1.fill.fore_color.rgb = colors["bg"]
    b1.line.color.rgb = colors["brand"]
    b1.line.width = Pt(1)
    tf1 = b1.text_frame
    tf1.word_wrap = True
    p1_0 = tf1.paragraphs[0]
    p1_0.text = "ORGANIZATION"
    p1_0.font.size = Pt(8.5)
    p1_0.font.bold = True
    p1_0.font.color.rgb = colors["secondary"]
    p1_1 = tf1.add_paragraph()
    p1_1.text = str(root_name)
    p1_1.font.size = Pt(10)
    p1_1.font.bold = True
    p1_1.font.color.rgb = colors["primary"]
    p1_2 = tf1.add_paragraph()
    p1_2.text = f"{root_val} {unit}".strip()
    p1_2.font.size = Pt(14)
    p1_2.font.bold = True
    p1_2.font.color.rgb = colors["brand"]
    if root_n:
        p1_3 = tf1.add_paragraph()
        p1_3.text = f"n = {root_n}"
        p1_3.font.size = Pt(8.5)
        p1_3.font.color.rgb = colors["secondary"]

    # Connector 1
    c_arr1 = slide.shapes.add_shape(MSO_SHAPE.RIGHT_ARROW, x + Inches(2.15), node_y + Inches(0.75), Inches(0.25), Inches(0.3))
    c_arr1.fill.solid()
    c_arr1.fill.fore_color.rgb = colors["brand"]
    c_arr1.line.fill.background()

    # 2. Child 1 Box
    b2 = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, x + Inches(2.45), node_y, node_w, node_h)
    b2.fill.solid()
    b2.fill.fore_color.rgb = colors["bg"]
    b2.line.color.rgb = colors["card_border"]
    b2.line.width = Pt(1)
    tf2 = b2.text_frame
    tf2.word_wrap = True
    p2_0 = tf2.paragraphs[0]
    p2_0.text = "PRIMARY FACTOR"
    p2_0.font.size = Pt(8.5)
    p2_0.font.bold = True
    p2_0.font.color.rgb = colors["secondary"]
    p2_1 = tf2.add_paragraph()
    p2_1.text = str(c1_name)
    p2_1.font.size = Pt(10)
    p2_1.font.bold = True
    p2_1.font.color.rgb = colors["primary"]
    p2_2 = tf2.add_paragraph()
    p2_2.text = f"{c1_val} {unit}".strip()
    p2_2.font.size = Pt(14)
    p2_2.font.bold = True
    p2_2.font.color.rgb = colors["primary"]
    if c1_n:
        p2_3 = tf2.add_paragraph()
        p2_3.text = f"n = {c1_n}"
        p2_3.font.size = Pt(8.5)
        p2_3.font.color.rgb = colors["secondary"]

    # Connector 2
    c_arr2 = slide.shapes.add_shape(MSO_SHAPE.RIGHT_ARROW, x + Inches(4.3), node_y + Inches(0.75), Inches(0.25), Inches(0.3))
    c_arr2.fill.solid()
    c_arr2.fill.fore_color.rgb = hex_to_rgb("#ef4444") if leaf_sev == "critical" else colors["brand"]
    c_arr2.line.fill.background()

    # 3. Disparity Leaf Box (Highlighted)
    leaf_w = Inches(2.0)
    b3 = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, x + Inches(4.6), node_y, leaf_w, node_h)
    b3.fill.solid()
    b3.fill.fore_color.rgb = colors["bg"]
    b3.line.color.rgb = hex_to_rgb("#ef4444") if leaf_sev == "critical" else hex_to_rgb("#f59e0b")
    b3.line.width = Pt(2)
    tf3 = b3.text_frame
    tf3.word_wrap = True
    p3_0 = tf3.paragraphs[0]
    p3_0.text = "DISPARITY OUTLIER"
    p3_0.font.size = Pt(8.5)
    p3_0.font.bold = True
    p3_0.font.color.rgb = hex_to_rgb("#ef4444") if leaf_sev == "critical" else hex_to_rgb("#f59e0b")
    p3_1 = tf3.add_paragraph()
    p3_1.text = str(leaf_name)
    p3_1.font.size = Pt(10)
    p3_1.font.bold = True
    p3_1.font.color.rgb = colors["primary"]
    p3_2 = tf3.add_paragraph()
    p3_2.text = f"{leaf_val} {unit}".strip()
    p3_2.font.size = Pt(14)
    p3_2.font.bold = True
    p3_2.font.color.rgb = hex_to_rgb("#ef4444") if leaf_sev == "critical" else hex_to_rgb("#f59e0b")
    if leaf_n:
        p3_3 = tf3.add_paragraph()
        p3_3.text = f"n = {leaf_n} (Target Segment)"
        p3_3.font.size = Pt(8.5)
        p3_3.font.color.rgb = colors["secondary"]

    # Bottom Impact Banner if impact card is available
    impact = chart_info.get("impact_card")
    if impact:
        imp_box = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, x + Inches(0.3), y + Inches(2.6), cx - Inches(0.6), Inches(1.5))
        imp_box.fill.solid()
        imp_box.fill.fore_color.rgb = colors["bg"]
        imp_box.line.color.rgb = hex_to_rgb("#ef4444") if str(impact.get("risk_level", "")).upper() == "CRITICAL" else colors["card_border"]
        imp_box.line.width = Pt(1)
        itf = imp_box.text_frame
        itf.word_wrap = True
        itf.margin_left = Inches(0.2)
        itf.margin_top = Inches(0.12)
        ip0 = itf.paragraphs[0]
        ip0.text = f"EXECUTIVE BUSINESS IMPACT: {impact.get('formatted_amount', '')} ({impact.get('primary_metric', '')})".upper()
        ip0.font.size = Pt(9.5)
        ip0.font.bold = True
        ip0.font.color.rgb = hex_to_rgb("#ef4444") if str(impact.get("risk_level", "")).upper() == "CRITICAL" else colors["accent"]
        ip1 = itf.add_paragraph()
        ip1.text = str(impact.get("headline", ""))
        ip1.font.size = Pt(10)
        ip1.font.color.rgb = colors["primary"]
        if impact.get("formula_explanation"):
            ip2 = itf.add_paragraph()
            ip2.text = f"Basis: {impact.get('formula_explanation')}"
            ip2.font.size = Pt(8)
            ip2.font.color.rgb = colors["secondary"]


def _render_native_waterfall(slide, chart_info: dict, x, y, cx, cy, colors: dict, theme_palette: list[str] | None = None):
    """Renders a native styled variance waterfall bridge in PowerPoint."""
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
    p_head.text = chart_info.get("title", "Variance Waterfall Attribution")
    p_head.font.size = Pt(13)
    p_head.font.bold = True
    p_head.font.color.rgb = colors["accent"]

    steps = chart_info.get("waterfall_steps") or []
    if not steps:
        chart_info_copy = dict(chart_info)
        chart_info_copy["chart_type"] = "column"
        return _add_native_chart_shape(slide, chart_info_copy, x, y, cx, cy, colors, theme_palette)

    unit = chart_info.get("unit", "")
    n_steps = len(steps)
    step_w = (cx - Inches(0.6) - Inches(0.15 * max(1, n_steps - 1))) / max(1, n_steps)
    step_y = y + Inches(0.65)
    step_h = Inches(2.0)

    for idx, s in enumerate(steps):
        sx = x + Inches(0.3) + idx * (step_w + Inches(0.15))
        stype = s.get("type", "increase")
        sval = s.get("value", 0.0)
        slabel = s.get("label", f"Step {idx+1}")

        b = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, sx, step_y, step_w, step_h)
        b.fill.solid()
        b.fill.fore_color.rgb = colors["bg"]

        if stype == "total":
            b.line.color.rgb = colors["brand"]
            accent_col = colors["brand"]
        elif stype == "decrease" or sval < 0:
            b.line.color.rgb = hex_to_rgb("#10b981")
            accent_col = hex_to_rgb("#10b981")
        else:
            b.line.color.rgb = hex_to_rgb("#ef4444")
            accent_col = hex_to_rgb("#ef4444")
        b.line.width = Pt(1.5)

        btf = b.text_frame
        btf.word_wrap = True
        bp0 = btf.paragraphs[0]
        bp0.text = slabel.upper()
        bp0.font.size = Pt(8)
        bp0.font.bold = True
        bp0.font.color.rgb = colors["secondary"]

        bp1 = btf.add_paragraph()
        bp1.space_before = Pt(6)
        val_str = f"{unit}{sval:,.1f}" if unit == "$" else f"{sval:,.1f} {unit}".strip()
        bp1.text = val_str
        bp1.font.size = Pt(13)
        bp1.font.bold = True
        bp1.font.color.rgb = accent_col

        bp2 = btf.add_paragraph()
        bp2.space_before = Pt(3)
        bp2.text = f"Type: {stype.capitalize()}"
        bp2.font.size = Pt(7.5)
        bp2.font.color.rgb = colors["secondary"]

    # Bottom Impact Banner if impact card is available
    impact = chart_info.get("impact_card")
    if impact:
        imp_box = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, x + Inches(0.3), y + Inches(2.8), cx - Inches(0.6), Inches(1.4))
        imp_box.fill.solid()
        imp_box.fill.fore_color.rgb = colors["bg"]
        imp_box.line.color.rgb = hex_to_rgb("#ef4444") if str(impact.get("risk_level", "")).upper() == "CRITICAL" else colors["card_border"]
        imp_box.line.width = Pt(1)
        itf = imp_box.text_frame
        itf.word_wrap = True
        itf.margin_left = Inches(0.2)
        itf.margin_top = Inches(0.1)
        ip0 = itf.paragraphs[0]
        ip0.text = f"REALIZED BUSINESS IMPACT: {impact.get('formatted_amount', '')}".upper()
        ip0.font.size = Pt(9.5)
        ip0.font.bold = True
        ip0.font.color.rgb = hex_to_rgb("#ef4444") if str(impact.get("risk_level", "")).upper() == "CRITICAL" else colors["accent"]
        ip1 = itf.add_paragraph()
        ip1.text = str(impact.get("headline", ""))
        ip1.font.size = Pt(9.5)
        ip1.font.color.rgb = colors["primary"]
