import datetime
from pathlib import Path
from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.dml.color import RGBColor

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

def set_slide_background(slide):
    background = slide.background
    fill = background.fill
    fill.solid()
    fill.fore_color.rgb = C_BG

def add_header(slide, title_text: str, category_text: str = "PULSEHR AI · WORKFORCE INTELLIGENCE"):
    # Category tag
    tag_box = slide.shapes.add_textbox(Inches(0.8), Inches(0.5), Inches(11.7), Inches(0.3))
    tf_tag = tag_box.text_frame
    tf_tag.word_wrap = True
    p_tag = tf_tag.paragraphs[0]
    p_tag.text = category_text.upper()
    p_tag.font.size = Pt(11)
    p_tag.font.bold = True
    p_tag.font.color.rgb = C_BRAND

    # Main Title
    title_box = slide.shapes.add_textbox(Inches(0.8), Inches(0.8), Inches(11.7), Inches(0.7))
    tf_title = title_box.text_frame
    tf_title.word_wrap = True
    p_title = tf_title.paragraphs[0]
    p_title.text = title_text
    p_title.font.size = Pt(24)
    p_title.font.bold = True
    p_title.font.color.rgb = C_TEXT_LIGHT

def _save_deck(prs) -> Path:
    from uuid import uuid4
    out_path = config.EXPORTS_DIR / f"pulsehr_presentation_{uuid4().hex}.pptx"
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
