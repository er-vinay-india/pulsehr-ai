import React, { useEffect, useRef, useState } from 'react';
import { formatValue, formatFullValue, metricUnit } from '../components/charts/chartOptions';
import { findingTitle, findingAction, groupLabel, visualKey } from '../utils/reportPresentation';
import DataChart from '../components/charts/DataChart';
import ErrorBoundary from '../components/common/ErrorBoundary';
import VoiceoverPlayer from '../components/VoiceoverPlayer';
import '../styles/leadership-report.scss';

async function read(url, options = {}) {
  const r = await fetch(url, options);
  if (!r.ok) throw new Error(r.status === 409 ? 'The source changed. Refresh to use the latest evidence.' : 'Analysis is temporarily unavailable. Retry or inspect your uploaded data.');
  return r.json();
}
function CompactNumber({ value, unit = '' }) {
  return <span tabIndex={0} title={formatFullValue(value, unit)} aria-label={formatFullValue(value, unit)}>{formatValue(value, unit)}</span>;
}
function ReportText({ text = '' }) {
  // Format quantities in prose, leaving dates, identifiers and small numbers intact.
  return String(text).split(/(-?\d{1,3}(?:,\d{3})+(?:\.\d+)?|-?\d{5,}(?:\.\d+)?)/g).map((part, i) =>
    /^-?\d[\d,]*(?:\.\d+)?$/.test(part) ? <CompactNumber key={i} value={Number(part.replaceAll(',', ''))}/> : part);
}
function RelativeGap({ finding }) {
  const d = finding.detail || {};
  const group = d.groups?.find(g => g.group === d.focus_group);
  if (!group || !Number.isFinite(group.value) || !Number.isFinite(d.baseline) || d.baseline <= 0) return null;
  const gap = (group.value - d.baseline) / d.baseline * 100;
  return <p><CompactNumber value={Math.abs(gap)} unit="%"/> {gap < 0 ? 'below' : 'above'} the sheet average <small>(relative difference)</small></p>;
}
function Evidence({ finding: f }) {
  const d = f.detail || {};
  return <details><summary>Evidence & calculation</summary><p>{f.method}</p><p>{f.source?.file} · {f.source?.sheet}</p><p>{d.paired_rows != null ? `${d.paired_rows} paired observations` : ''}</p>{(d.groups || d.points)?.length > 0 && <div className="report-table"><table><thead><tr><th>Group / period</th><th>Value</th><th>Observations</th></tr></thead><tbody>{(d.groups || d.points).map((v, i) => <tr key={i}><td>{v.group != null ? groupLabel(d.dimension_label || d.dimension, v.group) : v.period}</td><td><CompactNumber value={v.value} unit={metricUnit(f.metric || '', f.unit)}/></td><td><CompactNumber value={v.used_rows ?? v.n}/></td></tr>)}</tbody></table></div>}{d.coefficient != null && <p>Rank correlation: {d.coefficient}. This does not establish causation.</p>}<details><summary>Technical details</summary><pre>{JSON.stringify(d, null, 2)}</pre></details></details>;
}
function Finding({ finding: f, chart, sharedChartId }) {
  const d = f.detail || {};
  const items = chart === 'line' ? d.points?.map(p => ({ label: p.period, value: p.value })) : d.groups?.map(g => ({ label: g.display_label || g.group, value: g.value }));
  return <article id={`finding-${f.id}`} className="leadership-finding"><div className="report-eyebrow">{f.source?.file} · {f.source?.sheet} · source {f.source?.sheet_id} · {f.kind}</div><h2>{findingTitle(f)}</h2>{d.groups?.length > 0 && <p className="report-eyebrow">{d.dimension_label || d.dimension} · alphabetical order</p>}<p className="report-observation"><ReportText text={f.observation}/></p><RelativeGap finding={f}/>
    {!sharedChartId && items?.length > 0 && chart !== 'table' && <ErrorBoundary fallback={<p>Chart unavailable. The evidence and finding remain available below.</p>}><DataChart items={items} type={chart} metric={f.metric_label || f.metric} baseline={chart === 'dot' ? d.baseline : undefined} height={280}/></ErrorBoundary>}
    {sharedChartId && <button onClick={() => document.getElementById(`finding-${sharedChartId}`)?.scrollIntoView({ behavior: 'smooth', block: 'start' })}>View shared comparison ↑</button>}
    <p><ReportText text={f.implication}/></p><div className="report-action"><strong>Recommended next step</strong><p><ReportText text={findingAction(f)}/></p><span>Suggested owner: {f.owner || 'Business owner'}</span></div><Evidence finding={f}/></article>;
}
export default function LeadershipReportPage({ onNavigateTab, onScopeChange }) {
  const [brief, setBrief] = useState(null), [sheets, setSheets] = useState([]), [sheet, setSheet] = useState('');
  const [audience, setAudience] = useState('CEO'), [intent, setIntent] = useState('What needs attention and what should we do next?');
  const [plan, setPlan] = useState(null), [loading, setLoading] = useState(true), [planning, setPlanning] = useState(false), [error, setError] = useState(''), [revision, setRevision] = useState(0);
  const generation = useRef(0);
  useEffect(() => { const controller = new AbortController(); read('/api/analytics/overview/base', { signal: controller.signal }).then(b => setSheets(b.sheets || [])).catch(() => {}); return () => controller.abort(); }, []);
  useEffect(() => {
    const controller = new AbortController(); const id = ++generation.current;
    setLoading(true); setBrief(null); setPlan(null); setPlanning(false); setError('');
    const timer = setTimeout(() => controller.abort(), 30000);
    read(`/api/analytics/decision-brief/report-evidence?audience=${encodeURIComponent(audience)}${sheet ? `&sheet_id=${sheet}` : ''}`, { signal: controller.signal }).then(b => {
      if (id !== generation.current) return;
      setBrief(b); onScopeChange?.({ sheetId: sheet ? Number(sheet) : null, datasetId: null, snapshotId: b.snapshot });
    }).catch(e => { if (id === generation.current) setError(e.name === 'AbortError' ? 'Analysis took too long. Retry or open your source data.' : e.message); }).finally(() => { clearTimeout(timer); if (id === generation.current) setLoading(false); });
    return () => { ++generation.current; clearTimeout(timer); controller.abort(); };
  }, [sheet, revision]);
  useEffect(() => {
    if (!brief || brief.empty) return;
    const controller = new AbortController(); const id = generation.current;
    let active = true;
    setPlanning(true); setPlan(null);
    const timer = setTimeout(() => controller.abort(), 16000);
    read('/api/analytics/decision-brief/report-plan', { method: 'POST', headers: { 'Content-Type': 'application/json' }, signal: controller.signal, body: JSON.stringify({ sheet_id: sheet ? Number(sheet) : null, snapshot: brief.snapshot, audience, intent }) }).then(p => { if (active && id === generation.current && !controller.signal.aborted) setPlan(p); }).catch(e => { if (active && id === generation.current) setError(e.name === 'AbortError' ? 'AI selection timed out. Computed evidence is retained below.' : e.message); }).finally(() => { clearTimeout(timer); if (active && id === generation.current) setPlanning(false); });
    return () => { active = false; clearTimeout(timer); controller.abort(); };
  }, [brief]);
  const findings = brief?.findings || [];
  const byId = new Map(findings.map(f => [f.id, f]));
  const sections = plan?.sections || findings.map(f => ({ id: f.id, chart: f.detail?.points?.length ? 'line' : f.detail?.groups?.length ? 'dot' : 'table' }));
  const remaining = findings.filter(f => !sections.some(s => s.id === f.id));
  const chartOwners = new Map();
  const sharedCharts = new Map();
  for (const f of [...sections.map(s => byId.get(s.id)).filter(Boolean), ...remaining]) {
    if (!f.detail?.groups?.length && !f.detail?.points?.length) continue;
    const key = visualKey(f.source, f.metric, f.detail);
    if (chartOwners.has(key)) sharedCharts.set(f.id, chartOwners.get(key));
    else chartOwners.set(key, f.id);
  }
  const extraViews = (brief?.profiles || []).flatMap(p => [
    ...(p.comparisons || []).map(c => ({ source: p.source, data: c, type: 'dot' })),
    ...(p.trends || []).map(t => ({ source: p.source, data: t, type: 'line' })),
  ]).filter(v => {
    const key = visualKey(v.source, v.data.metric, v.data);
    if (chartOwners.has(key)) return false;
    chartOwners.set(key, true);
    return true;
  });
  return <div className="leadership-report"><header className="report-heading"><div><div className="report-eyebrow">LEADERSHIP REPORT</div><h1>From evidence to action.</h1><p>A report shaped around your question, with the numbers behind every finding.</p></div><button onClick={() => onNavigateTab('overview')}>Reference overview ↗</button></header>
    <form className="report-controls" onSubmit={e => { e.preventDefault(); setRevision(r => r + 1); }}><label>Decision maker<select value={audience} onChange={e => setAudience(e.target.value)}>{['CEO', 'HR head', 'Sales manager', 'Marketing head', 'IT manager'].map(a => <option key={a}>{a}</option>)}</select></label><label>Source<select value={sheet} onChange={e => setSheet(e.target.value)}><option value="">All sources · analyzed separately</option>{sheets.map(s => <option key={s.id} value={s.id}>{s.display_name || s.name} · source {s.id}</option>)}</select></label><label className="report-question">What do you need to decide?<input maxLength={1000} value={intent} onChange={e => setIntent(e.target.value)} required /></label><button type="submit" disabled={loading || planning}>{loading ? 'Analyzing…' : planning ? 'Selecting report…' : 'Build report'}</button></form>
    <p role="status" aria-live="polite">{loading ? 'Comparing groups, changes over time, and relationships…' : planning ? 'Evidence is ready below. AI is selecting findings for your question…' : plan?.message || 'Showing computed evidence. AI selection is unavailable; you can still review the findings.'}</p>
    {error && <p role="alert">{error} <button onClick={() => setRevision(r => r + 1)}>Retry</button></p>}
    {!loading && (!brief || brief.empty) && <section className="report-empty"><h2>{brief?.empty ? 'Start with your business data' : 'Your sources are still available'}</h2><p>Upload a spreadsheet with named measures, groups and dates to support comparisons and trends.</p><button onClick={() => onNavigateTab('ingestion')}>Open uploads</button><button onClick={() => onNavigateTab('explorer')}>Inspect data</button></section>}
    {brief && !brief.empty && <><VoiceoverPlayer identity={`${brief.snapshot}-${plan?.mode}`} text={sections.map(s => byId.get(s.id)).filter(Boolean).map(f => `${findingTitle(f)}. ${f.observation}. ${f.implication}. Proposed next step: ${findingAction(f)}`).join('\n')}/>
      {!findings.length && <section className="report-empty"><h2>No supported business conclusion yet</h2><p>The available data did not meet the checks for a finding. Review the coverage below before making a decision.</p></section>}
      {sections.length > 0 && <h2>{plan?.mode === 'ai' ? 'Your decision briefing' : 'What the evidence shows'}</h2>}
      {sections.length > 0 && <ol className="report-highlights" aria-label="Key points">{sections.slice(0, 3).map(s => { const f = byId.get(s.id); return f && <li key={s.id}><strong>{findingTitle(f)}</strong><button onClick={() => document.getElementById(`finding-${f.id}`)?.scrollIntoView({ behavior: 'smooth', block: 'start' })}>View evidence ↓</button></li>; })}</ol>}
      <div className="report-findings">{sections.map(s => byId.has(s.id) && <Finding key={s.id} finding={byId.get(s.id)} chart={s.chart} sharedChartId={sharedCharts.get(s.id)}/>)}</div>
      {remaining.length > 0 && <section><h2>Additional evidence</h2><p>These findings are not selected as answers to your question.</p><div className="report-findings">{remaining.map(f => <Finding key={f.id} finding={f} chart={f.detail?.points ? 'line' : 'dot'} sharedChartId={sharedCharts.get(f.id)}/>)}</div></section>}
      {extraViews.length > 0 && <section><h2>More comparisons</h2><p>Additional views not already charted above. Sources remain separate.</p><div className="report-findings">{extraViews.map(({ source, data: c, type }) => <article className="leadership-finding" key={visualKey(source, c.metric, c)}><div className="report-eyebrow">{source.file} · {source.sheet} · source {source.sheet_id}</div><h2>{c.metric_label || c.metric} {type === 'line' ? 'over time' : `by ${c.dimension_label || c.dimension}`}</h2><ErrorBoundary><DataChart type={type} items={type === 'line' ? (c.points || []).map(v => ({ label: v.period, value: v.value })) : (c.groups || []).map(g => ({ label: g.display_label || g.group, value: g.value }))} metric={c.metric_label || c.metric} baseline={c.baseline}/></ErrorBoundary><p>{c.method} {c.coverage_note}</p></article>)}</div></section>}
      <section className="report-coverage"><h2>What this report can—and cannot—tell you</h2><p>The question guides selection; it does not guarantee the uploaded data can answer it. Findings describe measured differences and associations, not causes or automatic performance ratings.</p>{brief.profiles?.map(p => <div key={p.source.sheet_id}><h3>{p.source.sheet} · {p.domain}</h3><ul>{p.limitations?.map(l => <li key={l}>{l}</li>)}</ul></div>)}<button onClick={() => onNavigateTab('explorer')}>Explore source data ↗</button></section></>}
  </div>;
}
