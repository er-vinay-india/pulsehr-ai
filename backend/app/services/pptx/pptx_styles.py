"""PowerPoint styling, themes, colors, and common shape utilities."""

import re
from pathlib import Path
from uuid import uuid4
from pptx.util import Inches, Pt
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN

from ...core import config


class ChartExportError(RuntimeError):
    """Raised when native PowerPoint chart export fails due to invalid specs or rendering error."""
    pass


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


def _render_footer(slide, slide_data, colors, slide_num: int = 1, total_slides: int = 1):
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
        parts.append("Partial Year Data (< 330 days)")
    if limitations:
        parts.append(f"Scope: {limitations}")
    if not parts:
        parts.append("PulseHR Analytics · Verified Deterministic Data Engine")
    
    footer_box = slide.shapes.add_textbox(Inches(0.8), Inches(6.82), Inches(9.6), Inches(0.35))
    tf = footer_box.text_frame
    tf.word_wrap = True
    p = tf.paragraphs[0]
    p.text = " | ".join(parts)[:150]
    p.font.size = Pt(8.5)
    p.font.color.rgb = colors["secondary"]

    # Page Number Box
    page_box = slide.shapes.add_textbox(Inches(10.6), Inches(6.82), Inches(1.9), Inches(0.35))
    ptf = page_box.text_frame
    pp = ptf.paragraphs[0]
    pp.alignment = PP_ALIGN.RIGHT
    pp.text = f"Slide {slide_num} of {total_slides}"
    pp.font.size = Pt(8.5)
    pp.font.color.rgb = colors["secondary"]
