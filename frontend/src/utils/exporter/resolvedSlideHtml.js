import { escapeHtml, generateSvgChartHtml } from './exportFormatter.js';

// Uses the server's export geometry; never truncates checklist items or table rows.
export function buildResolvedSlideHtml(slide, index, total, theme, plan, part = 0, background = '') {
  const box = block => `position:absolute;left:${block.x}px;top:${block.y}px;width:${block.width}px;height:${block.height}px;`;
  const blocks = (plan.pages || [plan.blocks])[part];
  const content = blocks.map(block => {
    if (block.kind === 'checklist') return `<div style="${box(block)}display:flex;gap:10px;align-items:flex-start;font-size:${block.size}px;line-height:1.22;">
      <span aria-hidden="true" style="width:${block.icon_size}px;height:${block.icon_size}px;margin-top:2px;flex-shrink:0;border:2px solid currentColor;border-radius:50%;display:flex;align-items:center;justify-content:center;font:700 22px/1 Arial;">✓</span>
      <div style="min-width:0;flex:1;">${block.title ? `<strong style="display:block;font-size:${block.title_size}px;margin-bottom:${block.text ? 8 : 0}px;">${escapeHtml(block.title)}</strong>` : ''}${block.text ? `<p style="margin:0;white-space:pre-wrap;">${escapeHtml(block.text)}</p>` : ''}</div></div>`;
    if (block.kind === 'chart') return `<div style="${box(block)}">${generateSvgChartHtml(block.chart, theme.chart_palette, theme.brand_color, theme)}</div>`;
    if (block.kind === 'table') return `<div style="${box(block)}"><table style="width:100%;border-collapse:collapse;table-layout:fixed;font-size:${block.size}px;line-height:1.22;">
      <colgroup>${block.column_widths.map(w => `<col style="width:${100*w/block.width}%;">`).join('')}</colgroup>
      ${[block.headers, ...block.rows].map((row, r) => `<tr style="height:${block.row_heights[r]}px;">${block.headers.map((_, c) => `<${r ? 'td' : 'th'} style="padding:8px;border:1px solid ${theme.card_border};background:${theme.card_bg};vertical-align:top;text-align:left;white-space:pre-wrap;overflow-wrap:anywhere;">${escapeHtml(String(row[c] ?? ''))}</${r ? 'td' : 'th'}>`).join('')}</tr>`).join('')}</table></div>`;
    return `<${block.field === 'title' ? 'h2' : 'p'} style="${box(block)}margin:0;font-size:${block.size}px;font-family:${escapeHtml(block.font || 'Arial')};font-weight:${block.bold ? 700 : 400};line-height:1.22;color:${theme[block.role]};white-space:pre-wrap;">${escapeHtml(block.text)}</${block.field === 'title' ? 'h2' : 'p'}>`;
  }).join('');
  return `<section class="slide ${index === 0 ? 'active visible' : ''}" data-index="${index}" style="background:${theme.bg_color};color:${theme.primary_text};${background ? `background-image:url('${escapeHtml(background)}');background-size:100% 100%;` : ''}">
    <div style="position:relative;width:${plan.width}px;height:${plan.height}px;transform:scale(2);transform-origin:top left;font-family:${theme.font_body};">${content}
      <div style="position:absolute;left:762px;top:510px;width:150px;font-size:11px;text-align:right;">Slide ${slide.order || index+1} of ${total}${plan.pages.length > 1 ? ` · ${part+1}/${plan.pages.length}` : ''}</div>
    </div></section>`;
}
