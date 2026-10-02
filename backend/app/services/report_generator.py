"""Executive report and presentation generator service."""

import datetime
import logging
from html import escape
from pathlib import Path
from uuid import uuid4
from pptx import Presentation
from pptx.util import Inches

from ..core import config
from .pptx import (
    C_BG,
    C_CARD,
    C_CARD_BORDER,
    C_BRAND,
    C_ACCENT,
    C_TEXT_LIGHT,
    C_TEXT_MUTED,
    C_SUCCESS,
    C_DANGER,
    ChartExportError,
    hex_to_rgb,
    set_slide_background,
    add_header,
    _save_deck,
    _render_footer,
    _render_title_cover_slide,
    _render_title_hero_slide,
    _render_kpi_summary_slide,
    _render_chart_narrative_slide,
    _render_comparison_split_slide,
    _render_table_detail_slide,
    _render_full_chart_takeaway_slide,
    _render_two_charts_slide,
    _render_action_plan_slide,
    _render_generic_slide,
    _table_slide,
)

logger = logging.getLogger(__name__)

__all__ = [
    "ChartExportError",
    "export_spec_to_pptx",
    "export_spec_to_pdf",
    "generate_pptx_presentation",
    "generate_calculation_presentation",
    "generate_html_executive_report",
    "config",
]


def _new_deck():
    prs = Presentation()
    prs.slide_width = Inches(13.333)
    prs.slide_height = Inches(7.5)
    return prs


def _number(value):
    return 'No data' if value is None else f'{value:,.6g}'


def export_spec_to_pptx(deck_spec: dict) -> Path:
    if deck_spec.get("metadata", {}).get("deck_style") == "decision_brief":
        from .presentation.decision_deck import verify_decision_deck
        if verify_decision_deck(deck_spec, deck_spec.get("evidence_ledger", []))["status"] != "PASSED":
            raise ValueError("Decision brief changed after evidence verification. Regenerate the brief before export.")
    prs = _new_deck()
    from .presentation.visual.design_tokens import slide_theme_preset
    theme = slide_theme_preset({**(deck_spec.get("theme") or {}), "id": (deck_spec.get("theme") or {}).get("id") or deck_spec.get("metadata", {}).get("theme_id")})
    colors = {
        "bg": hex_to_rgb(theme["bg_color"]),
        "card_bg": hex_to_rgb(theme["card_bg"]),
        "card_border": hex_to_rgb(theme["card_border"]),
        "primary": hex_to_rgb(theme["primary_text"]),
        "secondary": hex_to_rgb(theme["secondary_text"]),
        "brand": hex_to_rgb(theme["brand_color"]),
        "accent": hex_to_rgb(theme["accent_color"]),
        "success": hex_to_rgb(theme["success_color"]),
        "danger": hex_to_rgb(theme["danger_color"]),
    }

    slides = deck_spec.get("slides", [])
    if any(s.get("layout") == "title_cover" or s.get("stable_slide_id") == "slide_title_cover" for s in slides[1:]):
        from .presentation.presentation_reorderer import reorder_presentation_slides
        deck_title = (deck_spec.get("metadata") or {}).get("title") or deck_spec.get("title", "")
        slides = reorder_presentation_slides(slides, deck_title=deck_title)
        deck_spec["slides"] = slides
    total_slides = len(slides)
    for idx, slide_data in enumerate(slides):
        slide = prs.slides.add_slide(prs.slide_layouts[6])
        set_slide_background(slide, colors["bg"])
        try:
            from .presentation.photo_background import add_photo_background
            add_photo_background(slide, slide_data, prs.slide_width, prs.slide_height, theme)
        except Exception as photo_err:
            logger.warning(f"Could not apply slide photo background: {photo_err}")
        layout = slide_data.get("layout", "chart_narrative")
        if layout == "title_cover":
            _render_title_cover_slide(slide, slide_data, colors)
        else:
            add_header(
                slide,
                slide_data.get("title", ""),
                slide_data.get("category", "EXECUTIVE REVIEW"),
                brand_color=colors["brand"],
                title_color=colors["primary"]
            )
            if layout == "title_hero":
                _render_title_hero_slide(slide, slide_data, colors)
            elif layout == "kpi_summary":
                _render_kpi_summary_slide(slide, slide_data, colors)
            elif layout == "chart_narrative":
                _render_chart_narrative_slide(slide, slide_data, colors, theme_palette=theme.get("chart_palette"))
            elif layout == "full_chart_takeaway":
                _render_full_chart_takeaway_slide(slide, slide_data, colors, theme_palette=theme.get("chart_palette"))
            elif layout == "two_charts":
                _render_two_charts_slide(slide, slide_data, colors, theme_palette=theme.get("chart_palette"))
            elif layout in ("action_plan", "initiative_detail"):
                _render_action_plan_slide(slide, slide_data, colors)
            elif layout in ("comparison_split", "methodology_panel"):
                _render_comparison_split_slide(slide, slide_data, colors)
            elif layout == "table_detail":
                _render_table_detail_slide(slide, slide_data, colors)
            else:
                _render_generic_slide(slide, slide_data, colors)

        from pptx.oxml.xmlchemy import OxmlElement
        for shape in slide.shapes:
            if not shape.has_table:
                continue
            for row in shape.table.rows:
                for cell in row.cells:
                    properties = cell._tc.get_or_add_tcPr()
                    for edge in ("lnL", "lnR", "lnT", "lnB"):
                        for existing in properties.findall(f"{{http://schemas.openxmlformats.org/drawingml/2006/main}}{edge}"):
                            properties.remove(existing)
                        line = OxmlElement(f"a:{edge}")
                        line.set("w", "12700")
                        fill = OxmlElement("a:solidFill")
                        color = OxmlElement("a:srgbClr")
                        color.set("val", str(colors["card_border"]))
                        fill.append(color)
                        line.append(fill)
                        properties.append(line)

        # Apply technical export accessibility: assign meaningful names and alt text descriptions
        for shape in slide.shapes:
            try:
                c_nv_pr = None
                for elem in shape._element.iter():
                    if elem.tag.endswith("cNvPr"):
                        c_nv_pr = elem
                        break
                if shape.has_table:
                    shape.name = f"Data Table: {slide_data.get('title', 'Table')[:35]}"
                    if c_nv_pr is not None:
                        c_nv_pr.set('title', f"Data Table: {slide_data.get('title', 'Table')[:35]}")
                        c_nv_pr.set('descr', f"Empirical data table supporting slide: {slide_data.get('title', '')}")
                elif shape.has_chart:
                    shape.name = f"Chart: {slide_data.get('title', 'Chart')[:35]}"
                    if c_nv_pr is not None:
                        c_nv_pr.set('title', f"Chart: {slide_data.get('title', 'Chart')[:35]}")
                        c_nv_pr.set('descr', f"Analytical chart visualization for slide: {slide_data.get('title', '')}")
            except Exception:
                pass

        _render_footer(slide, slide_data, colors, slide_num=idx + 1, total_slides=total_slides)

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
        valid_profiles = [p for p in sheet['profiles'] if p.get('nonempty', 0) > 0]
        metrics = [[p['column'] + (f" ({p['unit']})" if p.get('unit') else ''), p['nonempty'], p['missing'], _number(p.get('numeric', {}).get('mean'))] for p in valid_profiles]
        if not metrics:
            metrics = [['No complete columns available', 0, sheet['row_count'], '—']]
        for start in range(0, max(1, len(metrics)), 8):
            _table_slide(prs, sheet['name'][:65], ['Column', 'Present', 'Missing', 'Mean'], metrics[start:start+8],
                         f"Source: {sheet['original_name']} / {sheet['name']}. {sheet['row_count']} rows. Excludes 100% null columns.")
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
    from .sheet_catalog import overview
    data = overview()
    sections = []
    for sheet in data['sheets']:
        valid_profiles = [p for p in sheet['profiles'] if p.get('nonempty', 0) > 0]
        rows = ''.join(f"<tr><td>{escape(p['column'])}</td><td>{p['nonempty']}</td><td>{p['missing']}</td><td>{_number(p.get('numeric', {}).get('mean'))}</td></tr>" for p in valid_profiles)
        sections.append(f"<h2>{escape(sheet['original_name'])} / {escape(sheet['name'])}</h2><p>{sheet['row_count']} source rows (excludes 100% null columns)</p><table><tr><th>Column</th><th>Present</th><th>Missing</th><th>Mean</th></tr>{rows or '<tr><td colspan=\"4\">No non-empty columns found.</td></tr>'}</table>")
    return '<!doctype html><html><head><title>HighView Executive Report</title><style>body{font-family:Arial;padding:32px}table{border-collapse:collapse;width:100%}td,th{border:1px solid #ccc;padding:8px;text-align:left}</style></head><body><h1>HighView · Clarity From Every Sheet. · Powered by HRIDAY</h1><p>' + escape(data['note']) + '</p>' + (''.join(sections) or '<p>No sheets uploaded.</p>') + '</body></html>'


def export_spec_to_pdf(deck_spec: dict) -> Path:
    """Exports a PresentationDeckSpec to a landscape 16:9 PDF executive presentation."""
    from reportlab.lib import colors
    from reportlab.pdfgen import canvas

    deck_id = deck_spec.get("id") or str(uuid4())[:8]
    config.EXPORTS_DIR.mkdir(parents=True, exist_ok=True)
    pdf_path = config.EXPORTS_DIR / f"presentation_{deck_id}.pdf"

    # 16:9 aspect ratio: 960 x 540 points
    page_width = 960.0
    page_height = 540.0

    c = canvas.Canvas(str(pdf_path), pagesize=(page_width, page_height))
    slides = deck_spec.get("slides", [])
    if any(s.get("layout") == "title_cover" or s.get("stable_slide_id") == "slide_title_cover" for s in slides[1:]):
        from .presentation.presentation_reorderer import reorder_presentation_slides
        deck_title = (deck_spec.get("metadata") or {}).get("title") or deck_spec.get("title", "")
        slides = reorder_presentation_slides(slides, deck_title=deck_title)
        deck_spec["slides"] = slides

    for idx, slide in enumerate(slides):
        # Dark executive slide background
        c.setFillColor(colors.HexColor("#0B0F19"))
        c.rect(0, 0, page_width, page_height, stroke=0, fill=1)

        title = slide.get("title", f"Slide {idx + 1}")
        category = slide.get("category", "Executive Briefing")

        # Category eyebrow
        c.setFillColor(colors.HexColor("#3B82F6"))
        c.setFont("Helvetica-Bold", 10)
        c.drawString(48, page_height - 40, category.upper())

        # Title
        c.setFillColor(colors.HexColor("#F8FAFC"))
        c.setFont("Helvetica-Bold", 18)
        title_display = title[:90] + ("..." if len(title) > 90 else "")
        c.drawString(48, page_height - 68, title_display)

        # Subtitle / Key Takeaway
        subtitle = slide.get("subtitle") or slide.get("key_message") or slide.get("takeaway") or ""
        if subtitle:
            c.setFillColor(colors.HexColor("#94A3B8"))
            c.setFont("Helvetica", 11)
            c.drawString(48, page_height - 88, subtitle[:120])

        # Header divider rule
        c.setStrokeColor(colors.HexColor("#1E293B"))
        c.setLineWidth(1)
        c.line(48, page_height - 100, page_width - 48, page_height - 100)

        # Bullets
        y = page_height - 132
        bullets = slide.get("content", {}).get("bullets") or slide.get("bullet_points") or []
        if isinstance(bullets, list) and bullets:
            c.setFont("Helvetica", 11)
            c.setFillColor(colors.HexColor("#E2E8F0"))
            for b in bullets[:5]:
                bullet_text = str(b).strip()
                c.drawString(56, y, f"•  {bullet_text[:110]}")
                y -= 24

        # Metrics cards
        metrics = slide.get("metrics", [])
        if isinstance(metrics, list) and metrics:
            card_x = 48
            card_y = max(60, y - 60)
            card_w = min(180, (page_width - 96 - (len(metrics) - 1) * 16) / max(1, len(metrics)))
            for m in metrics[:4]:
                c.setFillColor(colors.HexColor("#111827"))
                c.setStrokeColor(colors.HexColor("#1F2937"))
                c.roundRect(card_x, card_y, card_w, 54, 4, stroke=1, fill=1)

                label = str(m.get("label", "Metric"))[:22]
                val = str(m.get("value", "—"))[:18]
                c.setFillColor(colors.HexColor("#94A3B8"))
                c.setFont("Helvetica", 8)
                c.drawString(card_x + 10, card_y + 36, label)
                c.setFillColor(colors.HexColor("#F8FAFC"))
                c.setFont("Helvetica-Bold", 14)
                c.drawString(card_x + 10, card_y + 16, val)
                card_x += card_w + 16

        # Footer metadata
        c.setFillColor(colors.HexColor("#64748B"))
        c.setFont("Helvetica", 8)
        c.drawString(48, 24, "HighView Executive Intelligence · Confidential")
        c.drawRightString(page_width - 48, 24, f"{idx + 1} / {len(slides)}")

        c.showPage()

    c.save()
    return pdf_path
