import { slideBackground } from '../../../utils/slideBackground';
import React, { useEffect, useRef, useState } from 'react';
import { getSlideTheme, slideCssVariables } from '../../../theme/slideTokens.js';
import SlideChart from './SlideChart.jsx';
import '../../../styles/resolved-slides.scss';

const requests = new Map();
export function loadSlideLayout(slide, theme) {
  const themeId = getSlideTheme(theme).id;
  const key = JSON.stringify([themeId, slide]);
  if (!requests.has(key)) {
    if (requests.size >= 64) requests.delete(requests.keys().next().value);
    const request = fetch(`/api/presentations/layout-preview?theme_id=${encodeURIComponent(themeId)}`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(slide),
    }).then(async response => {
      const body = await response.json();
      if (!response.ok) throw new Error(body.detail || 'Unable to lay out this slide.');
      return body.plan;
    }).catch(error => { requests.delete(key); throw error; });
    requests.set(key, request);
  }
  return requests.get(key);
}

export function useSlideLayout(slide, theme) {
  const key = JSON.stringify([getSlideTheme(theme).id, slide]);
  const [state, setState] = useState({ key: null, plan: null, error: null });
  useEffect(() => {
    if (!slide) return;
    let current = true;
    loadSlideLayout(slide, theme).then(plan => {
      if (current) setState({ key, plan, error: null });
    }).catch(error => {
      if (current) setState({ key, plan: null, error: error.message });
    });
    return () => { current = false; };
  }, [key]);
  return state.key === key ? state : { plan: null, error: null };
}

export function ResolvedCanvas({ plan, theme, slideIndex, totalSlides, part = 0, reflow = false, isEditable = false, slide, onUpdate }) {
  const host = useRef(null);
  const [scale, setScale] = useState(1);
  useEffect(() => {
    if (reflow || !host.current) return;
    const observer = new ResizeObserver(entries => setScale(entries[0].contentRect.width / plan.width));
    observer.observe(host.current);
    return () => observer.disconnect();
  }, [plan.width, reflow]);
  const pages = plan.pages || [plan.blocks];
  const blocks = pages[part] || pages[0];
  const styles = { ...slideCssVariables(theme), ...slideBackground(slide || {}, theme), color: theme.primary_text };
  if (reflow && theme.background_asset) {
    styles.backgroundImage = 'none';
  }
  return <div ref={host} className={`resolved-slide ${reflow ? 'resolved-slide-reflow' : ''}`} data-slide-theme={theme.id} style={styles}>
    <div className="resolved-slide-canvas" style={reflow ? undefined : { width: plan.width, height: plan.height, transform: `scale(${scale})` }}>
      {blocks.map((block, index) => {
        const box = reflow ? {} : { position: 'absolute', left: block.x, top: block.y, width: block.width, height: block.height };
        if (block.kind === 'checklist') return <div key={index} className="resolved-checklist" style={{ ...box, fontSize: block.size }}>
          <span className="resolved-checklist-icon" aria-hidden="true" style={{ width: block.icon_size, height: block.icon_size }}>✓</span>
          <div>
            {block.title && <strong style={{ display: 'block', fontSize: block.title_size, marginBottom: block.text ? 8 : 0 }}>{block.title}</strong>}
            {block.text && <p style={{ margin: 0, whiteSpace: 'pre-wrap' }}>{block.text}</p>}
          </div>
        </div>;
        if (block.kind === 'chart') return <div key={index} className="resolved-chart" style={box}>
          <SlideChart chart={block.chart} theme={theme} />
          <table className="resolved-chart-data">
            <caption>{block.chart.title || 'Chart values'}{block.chart.unit ? ` (${block.chart.unit})` : ''}</caption>
            <thead><tr><th scope="col">Category</th>{block.chart.series?.map((s, i) => <th scope="col" key={i}>{s.name || `Series ${i+1}`}</th>)}</tr></thead>
            <tbody>{block.chart.categories?.map((category, r) => <tr key={r}><th scope="row">{category}</th>{block.chart.series?.map((s, i) => <td key={i}>{String((s.values || s.data || [])[r] ?? '')}</td>)}</tr>)}</tbody>
          </table>
        </div>;
        if (block.kind === 'table') return <div key={index} className="resolved-table-wrap" style={box}>
          <table aria-label={slide?.title || 'Recorded values'} style={{ fontSize: block.size }}>
            <colgroup>{block.column_widths.map((width, i) => <col key={i} style={{ width: `${100*width/block.width}%` }} />)}</colgroup>
            <thead><tr style={reflow ? undefined : { height: block.row_heights[0] }}>{block.headers.map((header, i) => <th scope="col" key={i}>{header}</th>)}</tr></thead>
            <tbody>{block.rows.map((row, r) => <tr key={r} style={reflow ? undefined : { height: block.row_heights[r+1] }}>
              {block.headers.map((_, c) => <td key={c}>{String(row[c] ?? '')}</td>)}
            </tr>)}</tbody>
          </table>
        </div>;
        const textStyle = { ...box, margin: 0, fontSize: block.size, fontFamily: block.font || undefined, lineHeight: 1.22, fontWeight: block.bold ? 700 : 400, color: reflow && block.role === 'header_text' ? theme.primary_text : theme[block.role], whiteSpace: 'pre-wrap' };
        if (isEditable && block.field && onUpdate) return <textarea key={`${slide?.id}-${index}`} aria-label={`Edit slide ${block.field}`} className="resolved-text-editor"
          defaultValue={block.text} style={textStyle} onBlur={event => {
            if (event.target.value !== block.text) onUpdate({ ...slide, [block.field]: event.target.value });
          }} />;
        return block.field === 'title' ? <h2 key={index} style={textStyle}>{block.text}</h2> : <p key={index} style={textStyle}>{block.text}</p>;
      })}
      <div className="resolved-page-number" style={reflow ? undefined : { position: 'absolute', left: 762, top: 510, width: 150, fontSize: 11 }}>
        Slide {slideIndex} of {totalSlides}{pages.length > 1 ? ` · ${part+1}/${pages.length}` : ''}
      </div>
    </div>
  </div>;
}

export default function ResolvedSlideContent(props) {
  const { plan, error } = useSlideLayout(props.slide, props.theme);
  const [part, setPart] = useState(0);
  useEffect(() => { setPart(0); }, [props.slide.id, plan]);
  const theme = getSlideTheme(props.theme);
  if (error) return <div className="resolved-layout-message" role="alert">{error}</div>;
  if (!plan) return <div className="resolved-layout-message" role="status">Laying out this slide…</div>;
  const parts = plan.pages?.length || 1;
  return <div className="resolved-slide-view">
    {parts > 1 && <nav className="resolved-table-pages" aria-label="Table continuation pages">
      <button type="button" disabled={part === 0} onClick={() => setPart(p => p-1)}>Previous page</button>
      <span aria-live="polite">Page {part+1} of {parts}</span>
      <button type="button" disabled={part >= parts-1} onClick={() => setPart(p => p+1)}>Next page</button>
    </nav>}
    <ResolvedCanvas {...props} plan={plan} theme={theme} part={part} />
  </div>;
}
