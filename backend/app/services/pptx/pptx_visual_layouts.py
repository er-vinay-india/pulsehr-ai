"""Visual, chart, and table slide layout renderers for PowerPoint presentations."""

from pptx.util import Inches, Pt
from pptx.enum.shapes import MSO_SHAPE

from ..display_formatters import format_display_label
from .pptx_styles import (
    C_CARD,
    C_BRAND,
    C_TEXT_LIGHT,
    C_TEXT_MUTED,
    ChartExportError,
    add_styled_text_runs,
    set_slide_background,
    add_header,
)
from .pptx_charts import _add_native_chart_shape, _render_native_9box_matrix


def _render_chart_narrative_slide(slide, slide_data, colors, theme_palette=None):
    left_card = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(0.8), Inches(1.8), Inches(4.7), Inches(4.8))
    left_card.fill.solid()
    left_card.fill.fore_color.rgb = colors["card_bg"]
    left_card.line.color.rgb = colors["card_border"]
    left_card.line.width = Pt(1)

    tf = left_card.text_frame
    tf.word_wrap = True
    tf.margin_left = Inches(0.25)
    tf.margin_right = Inches(0.25)
    tf.margin_top = Inches(0.25)

    p0 = tf.paragraphs[0]
    p0.text = slide_data.get("subtitle", "")
    p0.font.size = Pt(12)
    p0.font.bold = True
    p0.font.color.rgb = colors["accent"]
    p0.space_after = Pt(8)

    narrative = slide_data.get("narrative", "")
    if narrative:
        p_narr = tf.add_paragraph()
        add_styled_text_runs(p_narr, narrative, font_size=10, default_color=colors["primary"])
        p_narr.space_after = Pt(10)

    bullets = slide_data.get("bullets", [])
    for b in bullets[:3]:
        p_b = tf.add_paragraph()
        p_b.space_after = Pt(6)
        r_d = p_b.add_run()
        r_d.text = "• "
        r_d.font.color.rgb = colors["brand"]
        r_d.font.bold = True
        add_styled_text_runs(p_b, b, font_size=10, default_color=colors["secondary"])

    metrics = slide_data.get("metrics", [])
    if metrics:
        p_sp = tf.add_paragraph()
        p_sp.space_after = Pt(6)
        for m in metrics[:2]:
            pm = tf.add_paragraph()
            pm.space_after = Pt(2)
            rv = pm.add_run()
            rv.text = f"{m.get('label')}: {m.get('value')} "
            rv.font.bold = True
            rv.font.size = Pt(11)
            rv.font.color.rgb = colors["brand"]
            rs = pm.add_run()
            rs.text = f"({m.get('subtext')})"
            rs.font.size = Pt(9)
            rs.font.color.rgb = colors["secondary"]

    chart_info = slide_data.get("chart")
    talent_9box = slide_data.get("talent_9box_data")
    if not chart_info and talent_9box:
        _render_native_9box_matrix(slide, talent_9box, Inches(5.8), Inches(1.8), Inches(6.7), Inches(4.8), colors)
        return

    if not chart_info:
        raise ChartExportError(
            f"Slide '{slide_data.get('title', 'Untitled')}' specifies layout 'chart_narrative' but contains no chart specification."
        )
    _add_native_chart_shape(slide, chart_info, Inches(5.8), Inches(1.8), Inches(6.7), Inches(4.8), colors, theme_palette=theme_palette)


def _render_table_detail_slide(slide, slide_data, colors):
    table_info = slide_data.get("table", {})
    headers = table_info.get("headers", ["Entity", "Metric", "Value", "Status"])
    rows = table_info.get("rows", [])[:10]

    narrative_box = slide.shapes.add_textbox(Inches(0.8), Inches(1.65), Inches(11.7), Inches(0.8))
    tf = narrative_box.text_frame
    tf.word_wrap = True
    p0 = tf.paragraphs[0]
    p0.text = slide_data.get("subtitle", "Governance & Verification Records")
    p0.font.size = Pt(12)
    p0.font.bold = True
    p0.font.color.rgb = colors["accent"]
    p0.space_after = Pt(4)

    if slide_data.get("narrative"):
        pn = tf.add_paragraph()
        add_styled_text_runs(pn, slide_data["narrative"], font_size=10, default_color=colors["secondary"])

    if headers and rows:
        num_rows = len(rows) + 1
        num_cols = len(headers)
        row_h = 0.38
        table_h = row_h * num_rows
        table_shape = slide.shapes.add_table(num_rows, num_cols, Inches(0.8), Inches(2.6), Inches(11.7), Inches(table_h))
        table = table_shape.table

        display_headers = [format_display_label(h) for h in headers]
        all_data = [display_headers, *rows]

        for ri, rvals in enumerate(all_data):
            for ci in range(num_cols):
                val = rvals[ci] if ci < len(rvals) else ""
                cell = table.cell(ri, ci)
                cell.fill.solid()
                cell.fill.fore_color.rgb = colors["card_bg"]
                p = cell.text_frame.paragraphs[0]
                p.text = str(val)
                p.font.size = Pt(10)
                if ri == 0:
                    p.font.bold = True
                    p.font.color.rgb = colors["brand"]
                else:
                    p.font.color.rgb = colors["primary"]


def _render_full_chart_takeaway_slide(slide, slide_data, colors, theme_palette=None):
    # Top Takeaway Card
    top_card = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(0.8), Inches(1.65), Inches(11.7), Inches(0.95))
    top_card.fill.solid()
    top_card.fill.fore_color.rgb = colors["card_bg"]
    top_card.line.color.rgb = colors["card_border"]
    top_card.line.width = Pt(1)

    tf = top_card.text_frame
    tf.word_wrap = True
    tf.margin_left = Inches(0.25)
    tf.margin_top = Inches(0.12)
    tf.margin_right = Inches(0.25)

    p0 = tf.paragraphs[0]
    p0.text = slide_data.get("subtitle", "Strategic Visual Takeaway").upper()
    p0.font.size = Pt(10)
    p0.font.bold = True
    p0.font.color.rgb = colors["accent"]
    p0.space_after = Pt(4)

    narr = slide_data.get("narrative", "")
    if narr:
        pn = tf.add_paragraph()
        add_styled_text_runs(pn, narr, font_size=11, default_color=colors["primary"])

    # Full-width Hero Chart
    chart_info = slide_data.get("chart")
    if not chart_info:
        raise ChartExportError(f"Slide '{slide_data.get('title')}' specifies 'full_chart_takeaway' but lacks chart specification.")
    _add_native_chart_shape(slide, chart_info, Inches(0.8), Inches(2.75), Inches(11.7), Inches(3.9), colors, theme_palette=theme_palette)


def _render_two_charts_slide(slide, slide_data, colors, theme_palette=None):
    # Top Takeaway Banner
    top_card = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(0.8), Inches(1.65), Inches(11.7), Inches(0.85))
    top_card.fill.solid()
    top_card.fill.fore_color.rgb = colors["card_bg"]
    top_card.line.color.rgb = colors["card_border"]
    top_card.line.width = Pt(1)

    tf = top_card.text_frame
    tf.word_wrap = True
    tf.margin_left = Inches(0.25)
    tf.margin_top = Inches(0.12)

    p0 = tf.paragraphs[0]
    p0.text = slide_data.get("subtitle", "Comparative Multi-Dimensional Evaluation").upper()
    p0.font.size = Pt(10)
    p0.font.bold = True
    p0.font.color.rgb = colors["accent"]
    p0.space_after = Pt(2)

    if slide_data.get("narrative"):
        pn = tf.add_paragraph()
        add_styled_text_runs(pn, slide_data["narrative"], font_size=10, default_color=colors["primary"])

    # Dual Charts: chart_left and chart_right
    chart_left = slide_data.get("chart_left") or slide_data.get("chart")
    chart_right = slide_data.get("chart_right")
    if not chart_right and slide_data.get("charts") and len(slide_data["charts"]) > 1:
        chart_left = slide_data["charts"][0]
        chart_right = slide_data["charts"][1]

    if not chart_left or not chart_right:
        _render_chart_narrative_slide(slide, slide_data, colors, theme_palette=theme_palette)
        return

    _add_native_chart_shape(slide, chart_left, Inches(0.8), Inches(2.65), Inches(5.7), Inches(4.0), colors, theme_palette=theme_palette)
    _add_native_chart_shape(slide, chart_right, Inches(6.8), Inches(2.65), Inches(5.7), Inches(4.0), colors, theme_palette=theme_palette)


def _table_slide(prs, title, headers, rows, source):
    """Bounded tables keep dynamically generated reports readable."""
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    set_slide_background(slide)
    add_header(slide, title, "PulseHR / Calculated workforce report")
    table = slide.shapes.add_table(len(rows) + 1, len(headers), Inches(.8), Inches(1.8), Inches(11.7), Inches(.48 * (len(rows) + 1))).table
    display_headers = [format_display_label(h) for h in headers]
    for ri, values in enumerate([display_headers, *rows]):
        for ci, value in enumerate(values):
            cell = table.cell(ri, ci)
            cell.fill.solid()
            cell.fill.fore_color.rgb = C_CARD
            p = cell.text_frame.paragraphs[0]
            p.text = str(value)
            p.font.size = Pt(12)
            p.font.bold = ri == 0
            p.font.color.rgb = C_BRAND if ri == 0 else C_TEXT_LIGHT
    footer = slide.shapes.add_textbox(Inches(.8), Inches(6.7), Inches(11.7), Inches(.6))
    footer.text_frame.word_wrap = True
    p = footer.text_frame.paragraphs[0]
    p.text = source
    p.font.size = Pt(10)
    p.font.color.rgb = C_TEXT_MUTED
    return slide
