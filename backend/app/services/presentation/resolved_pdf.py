"""PDF adapter for the same resolved geometry used by the studio and PPTX."""
from math import ceil, isfinite
from xml.sax.saxutils import escape
from reportlab.lib.colors import HexColor
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfgen.canvas import Canvas
from reportlab.platypus import Paragraph, Table, TableStyle
from reportlab.graphics.shapes import Drawing
from reportlab.graphics.charts.piecharts import Pie
from reportlab.graphics.charts.doughnut import Doughnut
from reportlab.graphics import renderPDF

from .slide_layout import GEOMETRY, resolve_slide
from .visual.design_tokens import slide_theme_preset


def export_resolved_pdf(deck, output, *, canvas=None, page_offset=0, total=None):
    theme = slide_theme_preset(deck.get('theme') or deck.get('metadata', {}).get('theme_id'))
    owns_canvas = canvas is None
    canvas = canvas or Canvas(str(output), pagesize=(960, 540))
    canvas.setTitle(deck.get('metadata', {}).get('title') or 'HighView presentation')

    def paragraph(value, width, size, color='primary_text', bold=False):
        text = escape(str(value or '')).replace('\n', '<br/>')
        return Paragraph(text, ParagraphStyle('slide', fontName='Helvetica-Bold' if bold else 'Helvetica',
                         fontSize=size, leading=size*GEOMETRY['type']['line_height'], textColor=HexColor(theme[color])))

    def label(value, x, y, size=14, align='left', color='primary_text'):
        canvas.setFont('Helvetica', size)
        canvas.setFillColor(HexColor(theme[color]))
        getattr(canvas, {'left': 'drawString', 'right': 'drawRightString', 'center': 'drawCentredString'}[align])(x, y, str(value))

    def formatted(value):
        return f'{value/1e6:.1f}M' if abs(value) >= 1e6 else f'{value:,.2f}'.rstrip('0').rstrip('.') if value != int(value) else f'{value:,.0f}'

    def chart(block):
        data = block['chart']
        categories, series = data.get('categories') or [], data.get('series') or []
        values = [v for s in series for v in s.get('values', [])]
        if not categories or not series or any(len(s.get('values', [])) != len(categories) for s in series) or any(not isinstance(v, (int, float)) or not isfinite(v) for v in values):
            raise ValueError('Chart categories and recorded numeric values must match.')
        x, top, w, h = block['x'], 540-block['y'], block['width'], block['height']
        kind = str(data.get('chart_type') or data.get('type') or 'column').lower()
        label(data.get('title') or series[0].get('name') or '', x+w/2, top-19, 18, 'center')
        if kind in ('pie', 'donut', 'doughnut'):
            if len(series) != 1 or min(values) < 0 or sum(values) <= 0:
                raise ValueError('Composition charts need one positive recorded series.')
            drawing = Drawing(w, h-30)
            pie = Doughnut() if kind != 'pie' else Pie()
            diameter = min(w*.43, h-65)
            pie.x, pie.y, pie.width, pie.height = 8, (h-40-diameter)/2, diameter, diameter
            pie.data = values
            # A value key keeps text on the slide background, never on a bright
            # wedge where the foreground contrast would depend on its colour.
            pie.labels = [''] * len(values)
            pie.slices.fontName, pie.slices.fontSize = 'Helvetica', 14
            pie.slices.fontColor = HexColor(theme['primary_text'])
            for i in range(len(values)):
                pie.slices[i].fillColor = HexColor(theme['chart_palette'][i % len(theme['chart_palette'])])
                pie.slices[i].strokeColor = HexColor(theme['bg_color'])
            drawing.add(pie)
            renderPDF.draw(drawing, canvas, x, top-h)
            yy = top-65
            for i, (category, value) in enumerate(zip(categories, values)):
                detail = paragraph(f'{category}: {formatted(value)} ({100*value/sum(values):.1f}%)', w*.48, 16)
                _, detail_height = detail.wrap(w*.48, h)
                if yy-detail_height < top-h+12:
                    raise ValueError('Composition labels need a separate chart or fewer grouped categories.')
                canvas.setFillColor(HexColor(theme['chart_palette'][i % len(theme['chart_palette'])]))
                canvas.rect(x+w*.49, yy-13, 10, 10, fill=1, stroke=0)
                detail.drawOn(canvas, x+w*.49+18, yy-detail_height)
                yy -= detail_height+15
            return
        horizontal = kind in ('bar', 'horizontal_bar')
        low, high = min(0, min(values)), max(0, max(values))
        span = max(high-low, 1)
        left, bottom = x+(130 if horizontal else 85), top-h+30
        pw, ph = w-(205 if horizontal else 120), h-82
        canvas.setStrokeColor(HexColor(theme['card_border']))
        for tick in range(5):
            v = low+span*tick/4
            if horizontal:
                xx = left+pw*tick/4
                canvas.line(xx, bottom, xx, bottom+ph)
                label(formatted(v), xx, bottom-19, 12, 'center', 'secondary_text')
            else:
                yy = bottom+ph*tick/4
                canvas.line(left, yy, left+pw, yy)
                label(formatted(v), left-8, yy-4, 12, 'right', 'secondary_text')
        points = []
        step = (ph if horizontal else pw)/len(categories)
        for j, s in enumerate(series):
            color = HexColor(theme['chart_palette'][j % len(theme['chart_palette'])])
            points = []
            for i, (category, value) in enumerate(zip(categories, s['values'])):
                canvas.setFillColor(color)
                canvas.setStrokeColor(color)
                if horizontal:
                    yy = bottom+ph-(i+.5)*step
                    zero, end = left+(0-low)/span*pw, left+(value-low)/span*pw
                    bh = min(30, step*.65/len(series))
                    yy += (j-(len(series)-1)/2)*bh
                    canvas.rect(min(zero, end), yy-bh/2, abs(end-zero), bh, fill=1, stroke=0)
                    label(formatted(value), max(zero, end)+5, yy-4, 14)
                    if j == 0:
                        label(category, left-8, bottom+ph-(i+.5)*step-4, 14, 'right', 'secondary_text')
                else:
                    xx, yy = left+(i+.5)*step, bottom+(value-low)/span*ph
                    zero = bottom+(0-low)/span*ph
                    if kind in ('line', 'area'):
                        points.append((xx, yy))
                        canvas.circle(xx, yy, 3, fill=1, stroke=0)
                    else:
                        bw = step*.65/len(series)
                        xx += (j-(len(series)-1)/2)*bw
                        canvas.rect(xx-bw/2, min(zero, yy), bw, abs(yy-zero), fill=1, stroke=0)
                    label(formatted(value), xx, yy+7, 14, 'center')
                    if j == 0:
                        label(category, left+(i+.5)*step, bottom-19, 14, 'center', 'secondary_text')
            if points:
                canvas.setStrokeColor(color)
                canvas.setLineWidth(2)
                for a, b in zip(points, points[1:]):
                    canvas.line(*a, *b)
        if len(series) > 1:
            label(' / '.join(s.get('name', '') for s in series), x+w/2, top-38, 12, 'center', 'secondary_text')

    slides = deck.get('slides') or []
    for index, slide in enumerate(slides, 1):
        plan = resolve_slide(slide)
        if plan is None:
            raise ValueError(f"PDF layout '{slide.get('layout')}' needs a supported readable layout.")
        for part, blocks in enumerate(plan['pages'], 1):
            canvas.setFillColor(HexColor(theme['bg_color']))
            canvas.rect(0, 0, 960, 540, fill=1, stroke=0)
            for block in blocks:
                if block['kind'] == 'chart':
                    chart(block)
                elif block['kind'] == 'text':
                    p = paragraph(block['text'], block['width'], block['size'], block['role'], block['bold'])
                    _, height = p.wrap(block['width'], block['height'])
                    if height > block['height']+1:
                        raise ValueError('Text exceeds the resolved PDF region; split the content before export.')
                    p.drawOn(canvas, block['x'], 540-block['y']-height)
                else:
                    rows = [[paragraph(cell, block['column_widths'][ci]-16, block['size'], 'brand_color' if ri == 0 else 'primary_text', ri == 0)
                             for ci, cell in enumerate(row)] for ri, row in enumerate([block['headers'], *block['rows']])]
                    table = Table(rows, colWidths=block['column_widths'], rowHeights=block['row_heights'])
                    table.setStyle(TableStyle([('BACKGROUND', (0, 0), (-1, -1), HexColor(theme['card_bg'])),
                      ('GRID', (0, 0), (-1, -1), .75, HexColor(theme['card_border'])), ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                      ('LEFTPADDING', (0, 0), (-1, -1), 8), ('RIGHTPADDING', (0, 0), (-1, -1), 8),
                      ('TOPPADDING', (0, 0), (-1, -1), 8), ('BOTTOMPADDING', (0, 0), (-1, -1), 8)]))
                    table.wrap(block['width'], block['height'])
                    table.drawOn(canvas, block['x'], 540-block['y']-block['height'])
            page = f'Slide {index+page_offset} of {total or len(slides)}'
            if len(plan['pages']) > 1:
                page += f" · {part}/{len(plan['pages'])}"
            label(page, 912, 19, 11, 'right', 'secondary_text')
            canvas.showPage()
    if owns_canvas:
        canvas.save()
    return output
