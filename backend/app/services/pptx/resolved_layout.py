"""Native editable PowerPoint adapter for the resolved slide canvas."""
from pptx.util import Pt
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.enum.shapes import MSO_SHAPE

from ..presentation.slide_layout import GEOMETRY, lines
from .pptx_charts import _add_native_chart_shape
from .pptx_styles import hex_to_rgb


def render_resolved_slide(slide, plan, theme, colors, page, total):
    font = theme.get('font_body', 'Arial').split(',')[0].strip(" '\"")
    for block in plan['blocks']:
        if block['kind'] == 'chart':
            data = block['chart']
            composition = str(data.get('type') or data.get('chart_type') or '').lower() in {'pie', 'donut', 'doughnut'}
            chart_box = {**block, 'width': block['width']*.48} if composition else block
            _add_native_chart_shape(slide, data, *[Pt(chart_box[k]) for k in ('x', 'y', 'width', 'height')],
                                    colors, theme_palette=theme.get('chart_palette'))
            if composition:
                chart = slide.shapes[-1].chart
                chart.plots[0].has_data_labels = False
                values = data['series'][0]['values']
                total_value = sum(values)
                if len(data['series']) != 1 or not values or min(values) < 0 or total_value <= 0:
                    raise ValueError('Composition charts require one positive recorded series.')
                yy, width = block['y']+50, block['width']*.49-18
                for index, (category, value) in enumerate(zip(data['categories'], values)):
                    label = f'{category}: {value:,.6g} ({100*value/total_value:.1f}%)'
                    height = lines(label, width, 16)*16*1.22+4
                    if yy+height > block['y']+block['height']:
                        raise ValueError('Composition labels need fewer grouped categories or a separate slide.')
                    key_x = block['x']+block['width']*.51
                    swatch = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, Pt(key_x), Pt(yy+7), Pt(10), Pt(10))
                    swatch.fill.solid()
                    swatch.fill.fore_color.rgb = hex_to_rgb(theme['chart_palette'][index % len(theme['chart_palette'])])
                    swatch.line.fill.background()
                    shape = slide.shapes.add_textbox(Pt(key_x+18), Pt(yy), Pt(width), Pt(height))
                    shape.text_frame.margin_left = shape.text_frame.margin_right = 0
                    shape.text_frame.word_wrap = True
                    p = shape.text_frame.paragraphs[0]
                    p.text, p.font.name, p.font.size = label, font, Pt(16)
                    p.font.color.rgb = colors['primary']
                    yy += height+15
            continue
        if block['kind'] == 'table':
            shape = slide.shapes.add_table(len(block['rows'])+1, len(block['headers']),
                                          *[Pt(block[k]) for k in ('x', 'y', 'width', 'height')])
            for column, width in zip(shape.table.columns, block['column_widths']):
                column.width = Pt(width)
            for row, height in zip(shape.table.rows, block['row_heights']):
                row.height = Pt(height)
            for ri, values in enumerate([block['headers'], *block['rows']]):
                for ci, cell in enumerate(shape.table.rows[ri].cells):
                    cell.fill.solid()
                    cell.fill.fore_color.rgb = colors['card_bg']
                    cell.vertical_anchor = MSO_ANCHOR.TOP
                    cell.margin_left = cell.margin_right = cell.margin_top = cell.margin_bottom = Pt(GEOMETRY['spacing']['cell'])
                    cell.text_frame.word_wrap = True
                    p = cell.text_frame.paragraphs[0]
                    p.text = str(values[ci]) if ci < len(values) else ''
                    p.font.name, p.font.size = font, Pt(block['size'])
                    p.font.bold = ri == 0
                    p.font.color.rgb = colors['brand'] if ri == 0 else colors['primary']
                    p.space_before = p.space_after = Pt(0)
                    p.line_spacing = GEOMETRY['type']['line_height']
            continue
        shape = slide.shapes.add_textbox(*[Pt(block[k]) for k in ('x', 'y', 'width', 'height')])
        shape.name = f"Text: {block.get('field') or block['text'][:35]}"
        tf = shape.text_frame
        tf.margin_left = tf.margin_right = tf.margin_top = tf.margin_bottom = 0
        tf.vertical_anchor = MSO_ANCHOR.TOP
        tf.word_wrap = True
        p = tf.paragraphs[0]
        p.text = block['text']
        p.font.name, p.font.size = font, Pt(block['size'])
        p.font.bold = block['bold']
        p.font.color.rgb = hex_to_rgb(theme[block['role']])
        p.space_before = p.space_after = Pt(0)
        p.line_spacing = GEOMETRY['type']['line_height']
    shape = slide.shapes.add_textbox(Pt(762), Pt(GEOMETRY['canvas']['footer_y']), Pt(150), Pt(18))
    shape.text_frame.margin_left = shape.text_frame.margin_right = 0
    p = shape.text_frame.paragraphs[0]
    p.text, p.alignment = f'Slide {page} of {total}', PP_ALIGN.RIGHT
    if plan.get('parts', 1) > 1:
        p.text += f" · {plan['part']}/{plan['parts']}"
    p.font.name, p.font.size = font, Pt(GEOMETRY['type']['source'])
    p.font.color.rgb = colors['secondary']
    expected_tables = sum(b['kind'] == 'table' for b in plan['blocks'])
    expected_excel_charts = sum(
        b['kind'] == 'chart' and not (
            str(b.get('chart', {}).get('type') or b.get('chart', {}).get('chart_type') or '').lower() in {'breakdown_tree', 'waterfall'}
            or b.get('chart', {}).get('tree_data')
            or b.get('chart', {}).get('waterfall_steps')
        )
        for b in plan['blocks']
    )
    if sum(s.has_table for s in slide.shapes) != expected_tables or sum(s.has_chart for s in slide.shapes) != expected_excel_charts:
        raise ValueError('Export is missing a required chart or table.')

