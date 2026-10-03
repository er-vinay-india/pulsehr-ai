"""Render all business content using the same slide tokens as PowerPoint."""
from pathlib import Path
from xml.sax.saxutils import escape

from reportlab.lib.colors import HexColor
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfgen.canvas import Canvas
from reportlab.platypus import Paragraph, Table, TableStyle

from .visual.design_tokens import slide_theme_preset


def export_pdf(deck, output: Path):
    from .slide_layout import resolve_slide
    from .resolved_pdf import export_resolved_pdf
    canvas = Canvas(str(output), pagesize=(960, 540))
    canvas.setTitle(deck.get('metadata', {}).get('title') or 'HighView presentation')
    slides = deck.get('slides') or []
    for index, slide in enumerate(slides):
        # A specialized slide must not send every ordinary table/chart back
        # through the older geometry adapter.
        adapter = export_resolved_pdf if resolve_slide(slide) else _export_legacy_pdf
        adapter({**deck, 'slides': [slide]}, output, canvas=canvas, page_offset=index, total=len(slides))
    canvas.save()
    return output


def _export_legacy_pdf(deck, output: Path, *, canvas=None, page_offset=0, total=None):
    theme = slide_theme_preset(deck.get('metadata', {}).get('theme_id') or deck.get('theme'))
    owns_canvas = canvas is None
    canvas = canvas or Canvas(str(output), pagesize=(960, 540))
    canvas.setTitle(deck.get('metadata', {}).get('title') or 'HighView presentation')

    def text(value, x, top, width, size=13, color='primary_text', bold=False):
        # Standard PDF fonts cannot encode some source punctuation. Normalize it
        # for display without changing the verified source content.
        value = str(value or '').replace('–', '-').replace('—', '-').replace('’', "'").replace('→', 'to')
        p = Paragraph(escape(value), ParagraphStyle('slide', fontName='Helvetica-Bold' if bold else 'Helvetica',
                      fontSize=size, leading=size*1.3, textColor=HexColor(theme[color])))
        _, height = p.wrap(width, 460)
        p.drawOn(canvas, x, top-height)
        return top-height

    slides = deck.get('slides') or []
    for index, slide in enumerate(slides, 1):
        canvas.setFillColor(HexColor(theme['bg_color']))
        canvas.rect(0, 0, 960, 540, fill=1, stroke=0)
        top = text(slide.get('category') or 'Business review', 40, 512, 880, 10, 'brand_color', True)
        top = text(slide.get('title'), 40, top-8, 880, 22, bold=True)
        top = text(slide.get('subtitle'), 40, top-6, 880, 12, 'secondary_text')
        top = text(slide.get('narrative'), 40, top-12, 880, 14)
        for bullet in slide.get('bullets') or slide.get('bullet_points') or (slide.get('content') or {}).get('bullets') or []:
            top = text('- '+str(bullet), 44, top-6, 872, 12)
        metrics = slide.get('metrics') or []
        if metrics:
            width = (880-12*(len(metrics)-1))/len(metrics)
            for i, metric in enumerate(metrics):
                x = 40+i*(width+12)
                canvas.setFillColor(HexColor(theme['card_bg']))
                canvas.roundRect(x, top-88, width, 78, 6, fill=1, stroke=0)
                text(metric.get('label'), x+12, top-20, width-24, 10, 'secondary_text')
                text(str(metric.get('value', ''))+' '+str(metric.get('unit') or ''), x+12, top-49, width-24, 18, bold=True)
            top -= 104
        table = slide.get('table') or slide.get('table_data')
        if table and table.get('headers'):
            rows = [table['headers'], *(table.get('rows') or [])]
            width = 880/len(table['headers'])
            data = [[Paragraph(escape(str(cell).replace('–', '-').replace('—', '-')), ParagraphStyle('cell',
                             fontName='Helvetica-Bold' if r == 0 else 'Helvetica', fontSize=11, leading=14,
                             textColor=HexColor(theme['brand_color'] if r == 0 else theme['primary_text']))) for cell in row] for r, row in enumerate(rows)]
            native_table = Table(data, colWidths=[width]*len(table['headers']))
            native_table.setStyle(TableStyle([('BACKGROUND', (0, 0), (-1, -1), HexColor(theme['card_bg'])),
                                             ('GRID', (0, 0), (-1, -1), .5, HexColor(theme['card_border'])),
                                             ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                                             ('TOPPADDING', (0, 0), (-1, -1), 9), ('BOTTOMPADDING', (0, 0), (-1, -1), 9)]))
            _, height = native_table.wrap(880, top-48)
            if height > top-48:
                raise ValueError('PDF table exceeds readable slide bounds; split the table before export.')
            native_table.drawOn(canvas, 40, top-height-8)
        chart = slide.get('chart')
        if chart:
            categories = chart.get('categories') or []
            series = chart.get('series') or []
            if not categories or not series:
                raise ValueError('Cannot export an empty PDF chart.')
            chart_top = text(chart.get('title'), 40, top-10, 880, 12, bold=True)-14
            values = [v for s in series for v in s.get('values', [])]
            if any(len(s.get('values', [])) != len(categories) for s in series):
                raise ValueError('PDF chart category and value lengths differ.')
            if any(v is None for v in values):
                raise ValueError('PDF chart contains missing values.')
            low, high = min(0, min(values)), max(0, max(values))
            scale = max(high-low, 1)
            bottom, left, width = 62, 200, 620
            height = chart_top-bottom
            if height < 80:
                raise ValueError('PDF chart exceeds readable slide bounds.')
            # Label every recorded value. This remains understandable without color.
            row_height = height/len(categories)
            for i, category in enumerate(categories):
                y = chart_top-(i+1)*row_height
                text(category, 40, y+row_height*.8, 150, 10, 'secondary_text')
                for j, s in enumerate(series):
                    value = s['values'][i]
                    bar_height = min(16, row_height*.6/len(series))
                    yy = y+j*(bar_height+2)+5
                    zero = left+(0-low)/scale*width
                    endpoint = left+(value-low)/scale*width
                    canvas.setFillColor(HexColor(theme['chart_palette'][j % len(theme['chart_palette'])]))
                    canvas.rect(min(zero, endpoint), yy, abs(endpoint-zero), bar_height, fill=1, stroke=0)
                    text(f"{value:g} {chart.get('unit') or ''}", 830, yy+bar_height+1, 92, 10)
            # Preserve the meaning of each series; the PDF uses labeled horizontal
            # bars for readability while PPTX keeps the selected editable family.
            text(' / '.join(s.get('name', '') for s in series), 200, bottom-4, 620, 10, 'secondary_text')
        text(slide.get('source_label') or 'HighView', 40, 30, 800, 9, 'secondary_text')
        canvas.setFillColor(HexColor(theme['secondary_text']))
        canvas.setFont('Helvetica', 9)
        canvas.drawRightString(920, 19, f'{index+page_offset} / {total or len(slides)}')
        canvas.showPage()
    if owns_canvas:
        canvas.save()
    return output
