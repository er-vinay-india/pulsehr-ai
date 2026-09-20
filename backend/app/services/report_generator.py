import datetime
from pathlib import Path
import re
from uuid import uuid4
from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN
from pptx.enum.shapes import MSO_SHAPE
from pptx.chart.data import CategoryChartData
from pptx.enum.chart import XL_CHART_TYPE, XL_LEGEND_POSITION

from ..core import config
from ..db.database import get_connection
from .display_formatters import format_display_label

# Executive Theme Palette (matching web UI)
C_BG = RGBColor(23, 20, 18)          # --surface #171412
C_CARD = RGBColor(32, 27, 24)        # --surface-card #201b18
C_CARD_BORDER = RGBColor(61, 54, 47) # --border #3d362f
C_BRAND = RGBColor(255, 138, 98)     # --brand-500 #ff8a62
C_ACCENT = RGBColor(126, 231, 217)   # --accent-500 #7ee7d9
C_TEXT_LIGHT = RGBColor(255, 249, 242) # --fg-primary #fff9f2
C_TEXT_MUTED = RGBColor(190, 178, 166) # --fg-secondary
C_SUCCESS = RGBColor(142, 240, 200)  # --emerald-tier
C_DANGER = RGBColor(255, 140, 160)   # --rose-tier

def hex_to_rgb(hex_str: str, default: RGBColor = RGBColor(255, 255, 255)) -> RGBColor:
    try:
        clean = hex_str.lstrip('#')
        return RGBColor(int(clean[0:2], 16), int(clean[2:4], 16), int(clean[4:6], 16))
    except Exception:
        return default

def add_styled_text_runs(paragraph, text: str, font_size: int = 12, default_color: RGBColor = C_TEXT_LIGHT, base_bold: bool = False):
    """Splits markdown bold syntax (**bold**) into styled PowerPoint runs, eliminating raw asterisks."""
    if not text:
        return
    parts = re.split(r'(\*\*[^\*]+\*\*)', str(text))
    for part in parts:
        if not part:
            continue
        run = paragraph.add_run()
        if part.startswith('**') and part.endswith('**'):
            run.text = part[2:-2]
            run.font.bold = True
        else:
            run.text = part
            run.font.bold = base_bold
        run.font.size = Pt(font_size)
        run.font.color.rgb = default_color

def set_slide_background(slide, bg_color: RGBColor = C_BG):
    background = slide.background
    fill = background.fill
    fill.solid()
    fill.fore_color.rgb = bg_color

def add_header(slide, title_text: str, category_text: str = "PULSE ANALYTICS · EXECUTIVE REVIEW", brand_color: RGBColor = C_BRAND, title_color: RGBColor = C_TEXT_LIGHT):
    # Category tag
    tag_box = slide.shapes.add_textbox(Inches(0.8), Inches(0.4), Inches(11.7), Inches(0.35))
    tf_tag = tag_box.text_frame
    tf_tag.word_wrap = True
    p_tag = tf_tag.paragraphs[0]
    p_tag.text = str(category_text).upper()
    p_tag.font.size = Pt(10)
    p_tag.font.bold = True
    p_tag.font.color.rgb = brand_color

    # Main Title
    title_box = slide.shapes.add_textbox(Inches(0.8), Inches(0.75), Inches(11.7), Inches(0.8))
    tf_title = title_box.text_frame
    tf_title.word_wrap = True
    p_title = tf_title.paragraphs[0]
    p_title.text = str(title_text)
    p_title.font.size = Pt(22)
    p_title.font.bold = True
    p_title.font.color.rgb = title_color

def _save_deck(prs) -> Path:
    out_path = config.EXPORTS_DIR / f"pulsehr_presentation_{uuid4().hex}.pptx"
    prs.save(str(out_path))
    return out_path

def _render_footer(slide, slide_data, colors):
    sources = slide_data.get("evidence_sources", [])
    limitations = slide_data.get("limitations")
    evidence_id = slide_data.get("evidence_id")
    is_partial = slide_data.get("is_partial_year")
    parts = []
    if evidence_id:
        parts.append(f"[{evidence_id}]")
    if sources:
        parts.append(f"Evidence: {', '.join(str(s) for s in sources)}")
    if is_partial:
        parts.append("Partial Year Data")
    if limitations:
        parts.append(f"Scope: {limitations}")
    if not parts:
        parts.append("PulseHR Analytics · Verified Deterministic Data Engine")
    
    footer_box = slide.shapes.add_textbox(Inches(0.8), Inches(6.8), Inches(11.7), Inches(0.4))
    tf = footer_box.text_frame
    tf.word_wrap = True
    p = tf.paragraphs[0]
    p.text = " | ".join(parts)[:160]
    p.font.size = Pt(9)
    p.font.color.rgb = colors["secondary"]

def _render_title_hero_slide(slide, slide_data, colors):
    left_card = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(0.8), Inches(1.8), Inches(6.8), Inches(4.7))
    left_card.fill.solid()
    left_card.fill.fore_color.rgb = colors["card_bg"]
    left_card.line.color.rgb = colors["card_border"]
    left_card.line.width = Pt(1)

    tf = left_card.text_frame
    tf.word_wrap = True
    tf.margin_left = Inches(0.3)
    tf.margin_right = Inches(0.3)
    tf.margin_top = Inches(0.3)
    tf.margin_bottom = Inches(0.3)

    p0 = tf.paragraphs[0]
    p0.text = slide_data.get("subtitle", "")
    p0.font.size = Pt(14)
    p0.font.bold = True
    p0.font.color.rgb = colors["accent"]
    p0.space_after = Pt(12)

    narrative = slide_data.get("narrative", "")
    if narrative:
        p_narr = tf.add_paragraph()
        add_styled_text_runs(p_narr, narrative, font_size=11, default_color=colors["primary"])
        p_narr.space_after = Pt(12)

    bullets = slide_data.get("bullets", [])
    for b in bullets:
        p_b = tf.add_paragraph()
        p_b.space_after = Pt(8)
        run_dot = p_b.add_run()
        run_dot.text = "• "
        run_dot.font.color.rgb = colors["brand"]
        run_dot.font.size = Pt(11)
        run_dot.font.bold = True
        add_styled_text_runs(p_b, b, font_size=11, default_color=colors["secondary"])

    metrics = slide_data.get("metrics", [])
    if metrics:
        top_offset = 1.8
        card_h = 1.02
        spacing = 0.2
        for i, m in enumerate(metrics[:4]):
            m_card = slide.shapes.add_shape(
                MSO_SHAPE.ROUNDED_RECTANGLE,
                Inches(8.0), Inches(top_offset + i * (card_h + spacing)),
                Inches(4.5), Inches(card_h)
            )
            m_card.fill.solid()
            m_card.fill.fore_color.rgb = colors["card_bg"]
            m_card.line.color.rgb = colors["card_border"]
            m_card.line.width = Pt(1)

            mtf = m_card.text_frame
            mtf.word_wrap = True
            mtf.margin_left = Inches(0.25)
            mtf.margin_top = Inches(0.15)

            p_val = mtf.paragraphs[0]
            p_val.text = str(m.get("value", ""))
            p_val.font.size = Pt(20)
            p_val.font.bold = True
            p_val.font.color.rgb = colors["brand"]

            p_lbl = mtf.add_paragraph()
            p_lbl.text = f"{m.get('label', '')} · {m.get('subtext', '')}"
            p_lbl.font.size = Pt(10)
            p_lbl.font.color.rgb = colors["secondary"]

def _render_kpi_summary_slide(slide, slide_data, colors):
    narrative_box = slide.shapes.add_textbox(Inches(0.8), Inches(1.7), Inches(11.7), Inches(0.9))
    tf_n = narrative_box.text_frame
    tf_n.word_wrap = True
    p_sub = tf_n.paragraphs[0]
    p_sub.text = slide_data.get("subtitle", "")
    p_sub.font.size = Pt(13)
    p_sub.font.bold = True
    p_sub.font.color.rgb = colors["accent"]
    p_sub.space_after = Pt(4)

    if slide_data.get("narrative"):
        p_desc = tf_n.add_paragraph()
        add_styled_text_runs(p_desc, slide_data["narrative"], font_size=11, default_color=colors["primary"])

    metrics = slide_data.get("metrics", [])
    num_metrics = min(4, len(metrics))
    if num_metrics > 0:
        total_w = 11.7
        spacing = 0.25
        card_w = (total_w - (num_metrics - 1) * spacing) / num_metrics
        for i, m in enumerate(metrics[:num_metrics]):
            x = 0.8 + i * (card_w + spacing)
            card = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(x), Inches(2.8), Inches(card_w), Inches(2.2))
            card.fill.solid()
            card.fill.fore_color.rgb = colors["card_bg"]
            card.line.color.rgb = colors["card_border"]
            card.line.width = Pt(1)

            ctf = card.text_frame
            ctf.word_wrap = True
            ctf.margin_left = Inches(0.2)
            ctf.margin_right = Inches(0.2)
            ctf.margin_top = Inches(0.2)

            p_lbl = ctf.paragraphs[0]
            p_lbl.text = str(m.get("label", "")).upper()
            p_lbl.font.size = Pt(9)
            p_lbl.font.bold = True
            p_lbl.font.color.rgb = colors["brand"]
            p_lbl.space_after = Pt(6)

            p_val = ctf.add_paragraph()
            p_val.text = str(m.get("value", ""))
            p_val.font.size = Pt(22)
            p_val.font.bold = True
            p_val.font.color.rgb = colors["primary"]
            p_val.space_after = Pt(6)

            p_sub = ctf.add_paragraph()
            p_sub.text = str(m.get("subtext", ""))
            p_sub.font.size = Pt(9)
            p_sub.font.color.rgb = colors["secondary"]

    bullets = slide_data.get("bullets", [])
    if bullets:
        bot_card = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(0.8), Inches(5.2), Inches(11.7), Inches(1.4))
        bot_card.fill.solid()
        bot_card.fill.fore_color.rgb = colors["card_bg"]
        bot_card.line.color.rgb = colors["card_border"]
        bot_card.line.width = Pt(1)

        btf = bot_card.text_frame
        btf.word_wrap = True
        btf.margin_left = Inches(0.25)
        btf.margin_top = Inches(0.15)
        p_hd = btf.paragraphs[0]
        p_hd.text = "KEY TAKEAWAYS & EMPIRICAL THRESHOLDS"
        p_hd.font.size = Pt(9)
        p_hd.font.bold = True
        p_hd.font.color.rgb = colors["accent"]
        p_hd.space_after = Pt(4)

        for b in bullets[:2]:
            pb = btf.add_paragraph()
            pb.space_after = Pt(4)
            run_dot = pb.add_run()
            run_dot.text = "• "
            run_dot.font.color.rgb = colors["brand"]
            add_styled_text_runs(pb, b, font_size=10, default_color=colors["secondary"])

def _add_native_chart_shape(slide, chart_info, x, y, cx, cy, colors):
    raw_type = (chart_info.get("chart_type") or chart_info.get("type") or "column").lower()
    if raw_type in ("bar", "horizontal_bar"):
        xl_type = XL_CHART_TYPE.BAR_CLUSTERED
    elif raw_type in ("line", "area"):
        xl_type = XL_CHART_TYPE.LINE
    elif raw_type in ("donut", "doughnut", "pie"):
        xl_type = XL_CHART_TYPE.DOUGHNUT
    else:
        xl_type = XL_CHART_TYPE.COLUMN_CLUSTERED

    cdata = CategoryChartData()
    categories = [str(c) for c in chart_info.get("categories", [])]
    if not categories:
        categories = ["Category 1", "Category 2"]
    cdata.categories = categories

    series_list = chart_info.get("series", [])
    if not series_list:
        series_list = [{"name": "Value", "values": [0.0] * len(categories)}]

    for s in series_list:
        s_name = s.get("name", "Metric")
        s_vals = []
        for v in s.get("values", []):
            try:
                s_vals.append(float(v) if v is not None else 0.0)
            except Exception:
                s_vals.append(0.0)
        while len(s_vals) < len(categories):
            s_vals.append(0.0)
        cdata.add_series(s_name, s_vals[:len(categories)])

    try:
        chart_shape = slide.shapes.add_chart(xl_type, x, y, cx, cy, cdata)
        chart = chart_shape.chart
        chart.has_legend = True
        chart.legend.position = XL_LEGEND_POSITION.TOP
        chart.legend.include_in_layout = False
    except Exception:
        card = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, x, y, cx, cy)
        card.fill.solid()
        card.fill.fore_color.rgb = colors["card_bg"]
        card.line.color.rgb = colors["card_border"]
        tf = card.text_frame
        p = tf.paragraphs[0]
        p.text = f"Chart: {chart_info.get('title', 'Data View')}"
        p.font.size = Pt(14)
        p.font.color.rgb = colors["brand"]

def _render_chart_narrative_slide(slide, slide_data, colors):
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
    if chart_info:
        _add_native_chart_shape(slide, chart_info, Inches(5.8), Inches(1.8), Inches(6.7), Inches(4.8), colors)

def _render_comparison_split_slide(slide, slide_data, colors):
    left_card = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(0.8), Inches(1.8), Inches(6.5), Inches(4.8))
    left_card.fill.solid()
    left_card.fill.fore_color.rgb = colors["card_bg"]
    left_card.line.color.rgb = colors["card_border"]
    left_card.line.width = Pt(1)

    tf = left_card.text_frame
    tf.word_wrap = True
    tf.margin_left = Inches(0.3)
    tf.margin_right = Inches(0.3)
    tf.margin_top = Inches(0.25)

    p0 = tf.paragraphs[0]
    p0.text = slide_data.get("subtitle", "Strategic Action Plan")
    p0.font.size = Pt(13)
    p0.font.bold = True
    p0.font.color.rgb = colors["accent"]
    p0.space_after = Pt(8)

    narrative = slide_data.get("narrative", "")
    if narrative:
        pn = tf.add_paragraph()
        add_styled_text_runs(pn, narrative, font_size=11, default_color=colors["primary"])
        pn.space_after = Pt(12)

    bullets = slide_data.get("bullets", [])
    for b in bullets:
        pb = tf.add_paragraph()
        pb.space_after = Pt(8)
        rd = pb.add_run()
        rd.text = "• "
        rd.font.color.rgb = colors["brand"]
        rd.font.bold = True
        add_styled_text_runs(pb, b, font_size=10, default_color=colors["secondary"])

    metrics = slide_data.get("metrics", [])
    if not metrics:
        metrics = [
            {"label": "Priority 1", "value": "Operational Alignment", "subtext": "Immediate focus"},
            {"label": "Priority 2", "value": "Variance Mitigation", "subtext": "Quarterly milestone"},
            {"label": "Priority 3", "value": "Continuous Tracking", "subtext": "Automated governance"}
        ]
    top_offset = 1.8
    card_h = 1.45
    spacing = 0.2
    for i, m in enumerate(metrics[:3]):
        card = slide.shapes.add_shape(
            MSO_SHAPE.ROUNDED_RECTANGLE,
            Inches(7.6), Inches(top_offset + i * (card_h + spacing)),
            Inches(4.9), Inches(card_h)
        )
        card.fill.solid()
        card.fill.fore_color.rgb = colors["card_bg"]
        card.line.color.rgb = colors["card_border"]
        card.line.width = Pt(1)

        ctf = card.text_frame
        ctf.word_wrap = True
        ctf.margin_left = Inches(0.25)
        ctf.margin_top = Inches(0.18)

        pl = ctf.paragraphs[0]
        pl.text = str(m.get("label", f"Priority {i+1}")).upper()
        pl.font.size = Pt(10)
        pl.font.bold = True
        pl.font.color.rgb = colors["accent"]
        pl.space_after = Pt(4)

        pv = ctf.add_paragraph()
        pv.text = str(m.get("value", ""))
        pv.font.size = Pt(16)
        pv.font.bold = True
        pv.font.color.rgb = colors["brand"]
        pv.space_after = Pt(3)

        ps = ctf.add_paragraph()
        ps.text = str(m.get("subtext", ""))
        ps.font.size = Pt(10)
        ps.font.color.rgb = colors["secondary"]

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

def _render_generic_slide(slide, slide_data, colors):
    card = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(0.8), Inches(1.8), Inches(11.7), Inches(4.8))
    card.fill.solid()
    card.fill.fore_color.rgb = colors["card_bg"]
    card.line.color.rgb = colors["card_border"]
    card.line.width = Pt(1)

    tf = card.text_frame
    tf.word_wrap = True
    tf.margin_left = Inches(0.3)
    tf.margin_top = Inches(0.3)

    p0 = tf.paragraphs[0]
    p0.text = slide_data.get("subtitle", "")
    p0.font.size = Pt(14)
    p0.font.bold = True
    p0.font.color.rgb = colors["accent"]
    p0.space_after = Pt(10)

    if slide_data.get("narrative"):
        pn = tf.add_paragraph()
        add_styled_text_runs(pn, slide_data["narrative"], font_size=11, default_color=colors["primary"])
        pn.space_after = Pt(12)

    for b in slide_data.get("bullets", []):
        pb = tf.add_paragraph()
        pb.space_after = Pt(6)
        rd = pb.add_run()
        rd.text = "• "
        rd.font.color.rgb = colors["brand"]
        add_styled_text_runs(pb, b, font_size=11, default_color=colors["secondary"])

def export_spec_to_pptx(deck_spec: dict) -> Path:
    prs = _new_deck()
    theme = deck_spec.get("theme", {})
    colors = {
        "bg": hex_to_rgb(theme.get("bg_color", "#171412"), C_BG),
        "card_bg": hex_to_rgb(theme.get("card_bg", "#201b18"), C_CARD),
        "card_border": hex_to_rgb(theme.get("card_border", "#3d362f"), C_CARD_BORDER),
        "primary": hex_to_rgb(theme.get("primary_text", "#fff9f2"), C_TEXT_LIGHT),
        "secondary": hex_to_rgb(theme.get("secondary_text", "#beb2a6"), C_TEXT_MUTED),
        "brand": hex_to_rgb(theme.get("brand_color", "#ff8a62"), C_BRAND),
        "accent": hex_to_rgb(theme.get("accent_color", "#7ee7d9"), C_ACCENT),
        "success": hex_to_rgb(theme.get("success_color", "#8ef0c8"), C_SUCCESS),
        "danger": hex_to_rgb(theme.get("danger_color", "#ff8ca0"), C_DANGER),
    }

    slides = deck_spec.get("slides", [])
    for slide_data in slides:
        slide = prs.slides.add_slide(prs.slide_layouts[6])
        set_slide_background(slide, colors["bg"])
        add_header(
            slide,
            slide_data.get("title", ""),
            slide_data.get("category", "EXECUTIVE REVIEW"),
            brand_color=colors["brand"],
            title_color=colors["primary"]
        )

        layout = slide_data.get("layout", "chart_narrative")
        if layout == "title_hero":
            _render_title_hero_slide(slide, slide_data, colors)
        elif layout == "kpi_summary":
            _render_kpi_summary_slide(slide, slide_data, colors)
        elif layout == "chart_narrative":
            _render_chart_narrative_slide(slide, slide_data, colors)
        elif layout == "comparison_split":
            _render_comparison_split_slide(slide, slide_data, colors)
        elif layout == "table_detail":
            _render_table_detail_slide(slide, slide_data, colors)
        else:
            _render_generic_slide(slide, slide_data, colors)

        _render_footer(slide, slide_data, colors)

        if slide_data.get("speaker_notes"):
            try:
                notes_slide = slide.notes_slide
                tf = notes_slide.notes_text_frame
                tf.text = str(slide_data["speaker_notes"])
            except Exception:
                pass

    deck_id = deck_spec.get("id", uuid4().hex)
    out_path = config.EXPORTS_DIR / f"presentation_{deck_id}.pptx"
    prs.save(str(out_path))
    return out_path


def _new_deck():
    prs = Presentation()
    prs.slide_width = Inches(13.333)
    prs.slide_height = Inches(7.5)
    return prs


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


def _number(value):
    return 'No data' if value is None else f'{value:,.6g}'


def generate_pptx_presentation() -> Path:
    from .sheet_catalog import overview
    data = overview()
    if not data['sheets']:
        raise ValueError('Upload a sheet before generating a report.')
    prs = _new_deck()
    stamp = f"Generated {datetime.datetime.now():%Y-%m-%d %H:%M}. Source rows are not unique employees."
    _table_slide(prs, 'Uploaded data overview', ['Metric', 'Value'], [
        ['Datasets', data['stats']['datasets']], ['Sheets', data['stats']['sheets']],
        ['Source rows', data['stats']['rows']], ['Exact key relationships', data['stats']['linked_relationships']],
    ], stamp)
    for sheet in data['sheets']:
        metrics = [[p['column'] + (f" ({p['unit']})" if p.get('unit') else ''), p['nonempty'], p['missing'], _number(p.get('numeric', {}).get('mean'))] for p in sheet['profiles']]
        for start in range(0, max(1, len(metrics)), 8):
            _table_slide(prs, sheet['name'][:65], ['Column', 'Present', 'Missing', 'Mean'], metrics[start:start+8],
                         f"Source: {sheet['original_name']} / {sheet['name']}. {sheet['row_count']} rows. Means use numeric, nonmissing cells only.")
    return _save_deck(prs)


def generate_calculation_presentation(result: dict) -> Path:
    prs = _new_deck()
    rows = [[item['group'], _number(item['value']), item['used_rows'], item['missing_rows']] for item in result['results']]
    stamp = f"Source: {result['source']}. Selected {result['matched_rows']} of {result['source_rows']} rows. {result['note']}"
    for start in range(0, max(1, len(rows)), 8):
        _table_slide(prs, f"{result['operation'].title()}: {result['column'] or 'row count'}", ['Group', 'Value', 'Rows used', 'Missing'], rows[start:start+8], stamp)
    _table_slide(prs, 'Calculation scope', ['Setting', 'Value'], [
        ['Source', result['source']], ['Operation', result['operation']],
        ['Column', result['column'] or 'Rows'], ['Group by', result['group_by'] or 'None'],
        ['Filter column', result['filter_column'] or 'None'], ['Filter value', result['filter_value'] or 'None'],
    ], 'Calculated locally from complete source data.')
    return _save_deck(prs)


def generate_html_executive_report() -> str:
    from html import escape
    from .sheet_catalog import overview
    data = overview()
    sections = []
    for sheet in data['sheets']:
        rows = ''.join(f"<tr><td>{escape(p['column'])}</td><td>{p['nonempty']}</td><td>{p['missing']}</td><td>{_number(p.get('numeric', {}).get('mean'))}</td></tr>" for p in sheet['profiles'])
        sections.append(f"<h2>{escape(sheet['original_name'])} / {escape(sheet['name'])}</h2><p>{sheet['row_count']} source rows</p><table><tr><th>Column</th><th>Present</th><th>Missing</th><th>Mean</th></tr>{rows}</table>")
    return '<!doctype html><html><head><title>PulseHR AI Report</title><style>body{font-family:Arial;padding:32px}table{border-collapse:collapse;width:100%}td,th{border:1px solid #ccc;padding:8px;text-align:left}</style></head><body><h1>PulseHR AI · Uploaded data report</h1><p>' + escape(data['note']) + '</p>' + (''.join(sections) or '<p>No sheets uploaded.</p>') + '</body></html>'
