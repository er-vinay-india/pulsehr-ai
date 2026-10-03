"""Resolved canvas geometry shared by export adapters and the studio contract.

All coordinates and font sizes are points on a 960 x 540 canvas. Supporting
chart detail has an explicit notes disposition. Required data never gets sliced.
"""
import json
import math
import re
from pathlib import Path

GEOMETRY = json.loads((Path(__file__).parent / 'templates/layout_geometry.json').read_text())


class SlideLayoutError(ValueError):
    pass


def plain(value):
    return re.sub(r'\*\*([^*]+)\*\*', r'\1', str(value or ''))


def lines(text, width, size):
    """Conservative word-wrap estimate, mirrored by the studio resolver."""
    capacity = max(1, math.floor(width / (size * .53)))
    count = 0
    for paragraph in plain(text).split('\n'):
        used = 0
        count += 1
        for word in paragraph.split():
            if used and used + 1 + len(word) > capacity:
                count += 1
                used = 0
            used += (1 if used else 0) + len(word)
            while used > capacity:
                count += 1
                used -= capacity
    return count


def resolve_slide(slide):
    layout = slide.get('layout') or ('chart_narrative' if slide.get('chart') or slide.get('chart_data') else 'table_detail' if slide.get('table') or slide.get('table_data') else 'comparison_split')
    if layout not in GEOMETRY['supported_layouts'] or slide.get('image_url') or slide.get('talent_9box_data') or slide.get('burnout_strain_data'):
        return None
    c, t, spacing = GEOMETRY['canvas'], GEOMETRY['type'], GEOMETRY['spacing']
    x, width, bottom = c['margin'], c['width']-2*c['margin'], c['body_bottom']
    blocks, notes, continuation_tables = [], [], []

    def text(value, xx, yy, ww, size, role='primary_text', bold=False, field=None):
        if value in (None, ''):
            return yy
        value = plain(value)
        height = math.ceil(lines(value, ww, size) * size * t['line_height']) + 2
        blocks.append(dict(kind='text', text=value, x=xx, y=yy, width=ww, height=height,
                           size=size, role=role, bold=bold, field=field))
        return yy + height

    text(slide.get('category', ''), x, 20, width, t['source'], 'brand_color', True)
    y = text(slide.get('title', ''), x, 42, width, t['cover'] if layout == 'title_cover' else t['title'], bold=True, field='title') + spacing['section']
    if y > 155:
        raise SlideLayoutError('The slide title needs a shorter heading or a separate cover.')
    subtitle, narrative = slide.get('subtitle') or '', slide.get('narrative') or ''
    bullets = [plain(b.get('text', '') if isinstance(b, dict) else b) for b in (slide.get('bullets') or [])]
    metrics = slide.get('metrics') or []
    table = slide.get('table') or slide.get('table_data')
    chart = slide.get('chart') or slide.get('chart_data')
    charts = [chart] if chart else []
    if layout == 'two_charts':
        charts = [v for v in [slide.get('chart_left') or chart, slide.get('chart_right')] if v]
        if len(slide.get('charts') or []) > 1:
            charts = slide['charts']

    def supporting():
        if subtitle and subtitle != narrative:
            notes.append(plain(subtitle))
        notes.extend(bullets)
        notes.extend(f"{m.get('label', '')}: {m.get('value', '')} {m.get('unit') or ''}. {m.get('subtext') or ''}".strip() for m in metrics)

    def render_table(data, start):
        headers, rows = data.get('headers') or [], data.get('rows') or []
        if not headers or not rows:
            raise SlideLayoutError('A table needs headers and recorded rows.')
        if any(len(row) > len(headers) for row in rows):
            raise SlideLayoutError('Every table value needs a column heading; extra cells cannot be omitted.')
        weights = data.get('column_weights') or GEOMETRY['table_columns'].get(str(len(headers))) or [1/len(headers)]*len(headers)
        if len(weights) != len(headers) or any(v <= 0 for v in weights):
            raise SlideLayoutError('Table column widths do not match its headers.')
        widths = [width*v/sum(weights) for v in weights]
        # Leave room for the font ascenders/descenders used by Office and PDF
        # importers; exact CSS line boxes alone under-allocate native table rows.
        heights = [max(math.ceil(lines(str(row[i]) if i < len(row) else '', w-2*spacing['cell'], t['table'])*t['table']*t['line_height']*1.2) for i, w in enumerate(widths))+2*spacing['cell'] for row in [headers, *rows]]
        available = bottom-start
        if heights[0] >= available or any(h + heights[0] > available for h in heights[1:]):
            raise SlideLayoutError('A table row is too long for a readable slide. Shorten that row or split its fields across slides.')
        groups, current, current_heights, used = [], [], [heights[0]], heights[0]
        for row, height in zip(rows, heights[1:]):
            if current and used + height > available:
                groups.append((current, current_heights))
                current, current_heights, used = [], [heights[0]], heights[0]
            current.append(row)
            current_heights.append(height)
            used += height
        groups.append((current, current_heights))
        for part, (page_rows, page_heights) in enumerate(groups):
            block = dict(kind='table', x=x, y=start, width=width, height=sum(page_heights), size=t['table'],
                         headers=headers, rows=page_rows, column_widths=widths, row_heights=page_heights)
            if part == 0:
                blocks.append(block)
            else:
                continuation_tables.append(block)


    if charts:
        if len(charts) > 2:
            raise SlideLayoutError('Use at most two charts per slide.')
        y = text(narrative or subtitle, x, y, width, t['body'], field='narrative' if narrative else 'subtitle') + spacing['paragraph']
        if bottom-y < 230:
            raise SlideLayoutError('Shorten the chart introduction to leave room for readable labels.')
        cw = (width-spacing['section']*(len(charts)-1))/len(charts)
        for i, value in enumerate(charts):
            blocks.append(dict(kind='chart', chart=value, x=x+i*(cw+spacing['section']), y=y, width=cw, height=bottom-y))
            if value.get('aggregation_disclosure'):
                notes.append(plain(value['aggregation_disclosure']))
        supporting()
        if table:
            raise SlideLayoutError('Chart and table need separate slides so both remain readable.')
    elif table:
        y = text(narrative or subtitle, x, y, width, t['body'], field='narrative' if narrative else 'subtitle') + spacing['paragraph']
        render_table(table, y)
        supporting()
    elif layout in ('chart_narrative', 'full_chart_takeaway', 'two_charts'):
        raise SlideLayoutError(f"Layout '{layout}' contains no chart specification.")
    elif layout in ('action_plan', 'initiative_detail'):
        actions = slide.get('initiatives') or slide.get('structured_proposals') or []
        if not actions:
            actions = [{'title': b} for b in bullets]
        if not actions:
            raise SlideLayoutError('An action slide needs recorded or proposed actions.')
        def action_text(value):
            return '; '.join(map(str, value)) if isinstance(value, list) else plain(value)
        rows = [[a.get('title') or a.get('proposed_response') or a.get('response') or '',
                 '\n'.join(action_text(v) for v in [a.get('owner') or a.get('owner_role') or 'Owner to confirm', a.get('status'), a.get('due_date') or a.get('timeline')] if v),
                 '\n'.join(action_text(v) for v in [a.get('metric') or a.get('success_metric'), a.get('dependency') or a.get('dependencies')] if v) or 'To confirm'] for a in actions]
        render_table({'headers': ['Action', 'Owner / status', 'Success measure / dependency'], 'rows': rows,
                      'column_weights': [.38, .24, .38]}, y)
        notes.extend(plain(a.get('finding') or a.get('motivating_finding') or '') for a in actions)
        notes.extend(f"Priority: {a['priority']}" for a in actions if a.get('priority'))
        visible_keys = {'title', 'proposed_response', 'response', 'owner', 'owner_role', 'status', 'due_date', 'timeline', 'metric', 'success_metric', 'dependency', 'dependencies', 'finding', 'motivating_finding', 'priority'}
        notes.extend(f"{a.get('title') or 'Action'} — {key.replace('_', ' ')}: {action_text(value)}" for a in actions for key, value in a.items() if key not in visible_keys and value)
        notes.extend([subtitle, narrative, *bullets])
    else:
        if subtitle:
            y = text(subtitle, x, y, width, t['body'], 'accent_color', True, 'subtitle') + spacing['paragraph']
        if narrative:
            y = text(narrative, x, y, width, t['body'], field='narrative') + spacing['section']
        if metrics:
            if len(metrics) > 8:
                raise SlideLayoutError('Split the metrics over more slides to preserve readable values.')
            cols = min(len(metrics), 4)
            cw = (width-spacing['section']*(cols-1))/cols
            for start in range(0, len(metrics), cols):
                end = y
                for i, m in enumerate(metrics[start:start+cols]):
                    xx = x+i*(cw+spacing['section'])
                    my = text(m.get('label'), xx, y, cw, t['label'], 'brand_color', True)
                    my = text(m.get('value'), xx, my+6, cw, t['value'], bold=True)
                    my = text(m.get('subtext') or m.get('unit'), xx, my+4, cw, t['caption'], 'secondary_text')
                    end = max(end, my)
                y = end+spacing['section']
        for bullet in bullets:
            y = text('• '+bullet, x, y, width, t['body']) + spacing['paragraph']
        if y-spacing['paragraph'] > bottom:
            raise SlideLayoutError('Text exceeds the readable slide area. Split the content over more slides.')
    notes = list(dict.fromkeys(plain(n) for n in notes if n))
    source = slide.get('source_label') or ', '.join(slide.get('evidence_sources') or []) or 'HighView'
    if notes:
        source += ' · Supporting detail in notes'
    if text(source, x, c['footer_y'], width-170, t['source'], 'secondary_text') > c['height']:
        raise SlideLayoutError('The source note is too long. Use a short source label and keep full details in notes.')
    pages = [blocks] + [[table if b['kind'] == 'table' else b for b in blocks] for table in continuation_tables]
    return dict(version=GEOMETRY['version'], width=c['width'], height=c['height'], blocks=blocks, pages=pages, supporting_notes=notes)


def presenter_notes(slide, plan):
    original = str(slide.get('speaker_notes') or '')
    extra = [n for n in (plan or {}).get('supporting_notes', []) if n and n not in original]
    return '\n\n'.join(v for v in [original, '\n'.join(extra)] if v)
