import React, { useEffect, useRef, useState } from 'react';
import { ArrowRight, ChevronLeft, ChevronRight, Sparkles, Presentation, X, RefreshCw, Search, Info, Download } from 'lucide-react';
import '../styles/decision-brief.scss';
import { decisionBriefHtml } from '../utils/decisionBriefExport';

const fmt = n => n == null ? 'Unavailable' : Number(n).toLocaleString(undefined, { maximumFractionDigits: 2 });

function Comparison({ data }) {
  if (!data) return <p className="decision-empty">No supported segment comparison for this sheet. Review field roles below.</p>;
  const groups = data.focus_group ? [...data.groups].sort((a,b) => Number(b.group === data.focus_group) - Number(a.group === data.focus_group)) : data.groups;
  const max = Math.max(...data.groups.map(g => Math.abs(g.value || 0)), Math.abs(data.baseline || 0), 1);
  return <div className="decision-comparison">
    <div className="decision-chart-label"><strong>{data.metric}</strong><span>Mean / valid record · baseline {fmt(data.baseline)}</span></div>
    <div className="decision-bars" role="list" aria-label={`${data.metric} by ${data.dimension}`}>
      {groups.map(g => <div className={`decision-bar-row ${g.group === data.focus_group ? 'decision-bar-focus' : ''}`}  role="listitem" key={g.group}>
        <span title={g.group}>{g.group}</span>
        <div className="decision-bar-track"><i style={{ width: `${Math.abs(g.value || 0) / max * 100}%` }} /><b>{fmt(g.value)}</b></div>
        <small>{g.used_rows} records{g.small_sample ? ' · small group' : ''}{g.missing_rows ? ` · ${g.missing_rows} unknown` : ''}</small>
      </div>)}
    </div>
    <p className="decision-footnote">Bar length represents absolute magnitude; signed values are shown. Differences describe recorded activity, not an overall performance score.</p>
  </div>;
}

function Evidence({ finding, onExplore }) {
  const d = finding.detail;
  return <details className="decision-evidence">
    <summary>Inspect calculation & evidence <Search size={13}/></summary>
    <div>
      <p>{finding.method}</p>
      <p><strong>Source:</strong> {finding.source.file} / {finding.source.sheet} · <code>{finding.id}</code></p>
      {d.total_rows != null && <p>{d.used_rows} valid records / {d.total_rows} source records.</p>}
      {d.groups && <div className="decision-table-wrap"><table><thead><tr><th>{d.dimension}</th><th>Mean</th><th>Median</th><th>Valid</th><th>Unknown</th></tr></thead><tbody>{d.groups.map(g => <tr key={g.group}><td>{g.group}</td><td>{fmt(g.value)}</td><td>{fmt(g.median)}</td><td>{g.used_rows}</td><td>{g.missing_rows}</td></tr>)}</tbody></table></div>}
      {d.within_groups && <ul>{d.within_groups.map(g=><li key={g.group}>{g.group}: ρ {fmt(g.coefficient)} ({g.paired_rows} pairs)</li>)}</ul>}
      {d.points && <div className="decision-table-wrap"><table><thead><tr><th>Month</th><th>Mean / record</th><th>Valid records</th></tr></thead><tbody>{d.points.map(p => <tr key={p.period}><td>{p.period}</td><td>{fmt(p.value)}</td><td>{p.used_rows}</td></tr>)}</tbody></table></div>}
      <button type="button" className="decision-link" onClick={onExplore}>Open source data explorer <ArrowRight size={13}/></button>
    </div>
  </details>;
}

function FindingCard({ finding, index, onExplore }) {
  return <article className={`decision-finding decision-finding--${finding.kind}`}>
    <div className="decision-card-meta"><span>{String(index + 1).padStart(2, '0')} / {finding.kind}</span><span>{finding.source.sheet}</span></div>
    <h3>{finding.title}</h3><p className="decision-observation">{finding.observation}</p>
    <p className="decision-implication">{finding.implication}</p>
    <div className="decision-action"><span>Proposed next step</span><p>{finding.action}</p><small>{finding.owner} · next operating review</small></div>
    <Evidence finding={finding} onExplore={onExplore}/>
  </article>;
}

function Matrix({ matrix }) {
  const [selected, setSelected] = useState(null);
  useEffect(() => setSelected(null), [matrix]);
  if (matrix.metrics.length < 2) return <p className="decision-empty">A relationship matrix needs at least two eligible numeric measures. Identifiers and derived period totals are excluded.</p>;
  const pairFor = (x, y) => matrix.pairs.find(p => p.x === x && p.y === y || p.x === y && p.y === x);
  return <>
    <div className="decision-matrix-scroll"><table className="decision-matrix"><thead><tr><th>Measures</th>{matrix.metrics.map((m,i) => <th key={m} title={m}>{i+1}</th>)}</tr></thead>
      <tbody>{matrix.metrics.map((m,i) => <tr key={m}><th><span>{i+1}</span> {m}</th>{matrix.metrics.map(n => {
        const p = pairFor(m,n); const r = p?.coefficient;
        return <td key={n}>{m === n ? <span className="decision-diagonal">—</span> : <button type="button" onClick={() => setSelected(p)} style={{background: r == null ? 'transparent' : `rgba(${r >= 0 ? '63,186,160' : '131,131,240'},${.12 + Math.abs(r)*.6})`}} aria-label={`${m} and ${n}: ${r == null ? p?.excluded_reason : `rank correlation ${fmt(r)}`}`}>{r == null ? '·' : fmt(r)}</button>}</td>;
      })}</tr>)}</tbody></table></div>
    <p className="decision-footnote">Spearman rank correlation · at least {matrix.minimum_pairs} paired records · exploratory, not causal. Select a cell for coverage.</p>
    {selected && <div className="decision-matrix-detail" role="status"><strong>{selected.x} × {selected.y}</strong><p>{selected.excluded_reason || `ρ = ${fmt(selected.coefficient)} across ${selected.paired_rows} paired records. This does not prove an intervention will improve either measure.`}</p><small>Group mix, shared time trends, and searching multiple pairs can produce apparent relationships.</small>{selected.within_groups?.length > 0 && <ul>{selected.within_groups.map(g => <li key={g.group}>{g.group}: ρ {fmt(g.coefficient)} · {g.paired_rows} paired records</li>)}</ul>}</div>}
  </>;
}

function Monthly({ trends }) {
  const [index,setIndex] = useState(0);
  const trend = trends[index] || trends[0];
  if (!trend) return <p className="decision-empty">No unambiguous row-level dates for a monthly time series. Supplied calendar-period totals, if available, appear in the comparison selector. No missing months have been invented.</p>;
  const values = trend.points.map(p=>p.value); const min=Math.min(...values); const span=Math.max(...values)-min || 1;
  const points=trend.points.map((p,i)=>`${20+i*560/Math.max(1,values.length-1)},${100-(p.value-min)/span*75}`).join(' ');
  return <><label className="decision-select-label">Monthly measure<select value={index} onChange={e=>setIndex(Number(e.target.value))}>{trends.map((t,i)=><option key={t.metric} value={i}>{t.metric}</option>)}</select></label>
    <svg className="decision-trend" viewBox="0 0 600 125" role="img" aria-label={`Monthly mean of ${trend.metric}; exact values in the table below`}><line x1="20" y1="105" x2="580" y2="105" stroke="currentColor" opacity=".2"/><polyline points={points} fill="none" stroke="#63cfb3" strokeWidth="3"/>{trend.points.map((p,i)=><circle key={p.period} cx={20+i*560/Math.max(1,values.length-1)} cy={100-(p.value-min)/span*75} r="4" fill="#63cfb3"><title>{p.period}: {fmt(p.value)}</title></circle>)}</svg>
    <div className="decision-month-chips">{trend.points.map(p=><div key={p.period}><small>{p.period}</small><strong>{fmt(p.value)}</strong><span>{p.used_rows} records</span></div>)}</div>
    <p className="decision-footnote">{trend.method} {trend.coverage_note}</p></>;
}

function BriefPresentation({ data, onClose, onExplore }) {
  const ref=useRef(null); const [page,setPage]=useState(0);
  const pages=data.findings;
  useEffect(()=>{const dialog=ref.current; dialog.showModal(); return ()=>dialog.close();},[]);
  const f=pages[page];
  return <dialog ref={ref} className="decision-presentation" onCancel={onClose} onKeyDown={e=>{if(e.target.tagName==='SELECT' || e.target.tagName==='INPUT')return;if(e.key==='ArrowRight')setPage(p=>Math.min(p+1,pages.length-1));if(e.key==='ArrowLeft')setPage(p=>Math.max(0,p-1));}}>
    <header><span>Leadership briefing · {data.snapshot}</span><button onClick={onClose} aria-label="Close presentation"><X size={22}/></button></header>
    <div className="decision-slide"><div className="decision-eyebrow">{f.kind} / {f.source.file}</div><h1>{f.title}</h1><p className="decision-slide-stat">{f.observation}</p>
      <div className="decision-slide-grid"><section>{f.detail.groups ? <Comparison data={{metric:f.metric,...f.detail}}/> : <><h2>What this means</h2><p>{f.implication}</p><p>{f.method}</p></>}</section><aside><span className="decision-eyebrow">Proposed action</span><h2>{f.action}</h2><p>{f.owner} · next operating review</p><hr/><p>{f.implication}</p></aside></div>
      <footer>{f.source.sheet} · {f.id} · Source-scale measurements; no causal conclusion</footer>
    </div>
    <nav aria-label="Presentation navigation"><button onClick={()=>setPage(p=>Math.max(0,p-1))} disabled={page===0}><ChevronLeft size={18}/>Previous</button><span>{page+1} / {pages.length}</span><button onClick={()=>setPage(p=>Math.min(p+1,pages.length-1))} disabled={page===pages.length-1}>Next<ChevronRight size={18}/></button></nav>
  </dialog>;
}

export default function DecisionBrief({ sheetId, onExplore }) {
  const [data,setData]=useState(null); const [error,setError]=useState(''); const [loading,setLoading]=useState(true);
  const [refresh,setRefresh]=useState(0); const [profileIndex,setProfileIndex]=useState(0); const [comparisonIndex,setComparisonIndex]=useState(0);
  const [prioritizing,setPrioritizing]=useState(false); const [present,setPresent]=useState(false);
  const request=useRef(0);
  useEffect(()=>{
    const controller=new AbortController(); const id=++request.current;
    setLoading(true);setError('');setData(null);setProfileIndex(0);setComparisonIndex(0);setPresent(false);setPrioritizing(false);
    fetch(`/api/analytics/decision-brief${sheetId != null ? `?sheet_id=${sheetId}` : ''}`,{signal:controller.signal})
      .then(async r=>{if(!r.ok)throw new Error('Could not analyze the selected source.');return r.json();})
      .then(result=>{if(id===request.current)setData(result);})
      .catch(e=>{if(e.name!=='AbortError'&&id===request.current)setError(e.message);})
      .finally(()=>{if(id===request.current)setLoading(false);});
    return ()=>controller.abort();
  },[sheetId,refresh]);
  const prioritize=async()=>{
    const id=request.current;setPrioritizing(true);
    try{const r=await fetch('/api/analytics/decision-brief/prioritize',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({sheet_id:sheetId,snapshot:data.snapshot})});if(!r.ok)throw new Error(r.status===409?'Source changed. Refresh the brief.':'Could not prioritize this brief.');const result=await r.json();if(id===request.current)setData(result);}
    catch(e){if(id===request.current)setError(e.message);}finally{if(id===request.current)setPrioritizing(false);}
  };
  const exportBrief=()=>{const blob=new Blob([decisionBriefHtml(data)],{type:'text/html;charset=utf-8'});const url=URL.createObjectURL(blob);const a=document.createElement('a');a.href=url;a.download=`executive-brief-${data.snapshot}.html`;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);};
  const download=()=>{const blob=new Blob([JSON.stringify(data,null,2)],{type:'application/json'});const url=URL.createObjectURL(blob);const a=document.createElement('a');a.href=url;a.download=`decision-brief-${data.snapshot}.json`;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);};
  if(loading)return <section className="decision-shell decision-loading" aria-busy="true"><Sparkles size={22}/><h2>Finding the story in your data</h2><p>Comparing segments, resolving periods, and checking relationships…</p></section>;
  if(!data)return <section className="decision-shell"><p role="alert">{error}</p><button className="decision-button" onClick={()=>setRefresh(x=>x+1)}>Retry analysis</button></section>;
  if(data.empty)return null;
  const profile=data.profiles[profileIndex];const comparison=profile.comparisons[comparisonIndex] || profile.comparisons[0];
  return <section className="decision-shell" aria-label="Executive decision brief">
    <header className="decision-header"><div><div className="decision-eyebrow"><span className="decision-dot"/> THE DECISION BRIEF</div><h2>What deserves your attention</h2><p>Evidence, context, and a next step — from the sheets you selected.</p></div><div className="decision-controls"><button onClick={prioritize} disabled={prioritizing||!data.findings.length}><Sparkles size={15}/>{prioritizing?'Prioritizing…':'AI prioritize'}</button><button onClick={()=>setPresent(true)} disabled={!data.findings.length}><Presentation size={15}/>Present brief</button><button onClick={exportBrief} disabled={!data.findings.length}><Download size={15}/>Export briefing</button><button aria-label="Download evidence JSON" title="Download evidence JSON" onClick={download}><Download size={16}/></button><button aria-label="Refresh decision brief" onClick={()=>setRefresh(x=>x+1)}><RefreshCw size={16}/></button></div></header>
    <div className="decision-status"><span>{data.ai_status}</span><span>{data.finding_count} supported findings · {data.profiles.length} sources analyzed separately</span></div>
    {error&&<p role="alert">{error}</p>}
    {data.findings.length ? <div className="decision-findings">{data.findings.map((f,i)=><FindingCard key={f.id} finding={f} index={i} onExplore={onExplore}/>)}</div> : <div className="decision-empty"><h3>No strong descriptive differences surfaced</h3><p>This can reflect similar groups, limited observations, or unresolved fields. Inspect the comparisons and coverage below; no issues were invented.</p></div>}
    <div className="decision-section-header"><div><div className="decision-eyebrow">EXPLORE THE EVIDENCE</div><h3>Compare, connect, investigate</h3></div><label className="decision-select-label">Source<select value={profileIndex} onChange={e=>{setProfileIndex(Number(e.target.value));setComparisonIndex(0);}}>{data.profiles.map((p,i)=><option key={p.source.sheet_id} value={i}>{p.source.file} / {p.source.sheet}</option>)}</select></label></div>
    <div className="decision-chips"><span>{profile.domain}</span><span>{profile.measures_analyzed} measures analyzed</span><span>{profile.row_count.toLocaleString()} source records</span><span>Units: source scale</span></div>
    <div className="decision-analysis-grid"><section className="decision-panel"><h3>Where the differences are</h3>{profile.comparisons.length>0&&<label className="decision-select-label">Compare<select value={comparisonIndex} onChange={e=>setComparisonIndex(Number(e.target.value))}>{profile.comparisons.map((c,i)=><option value={i} key={`${c.metric}:${c.dimension}`}>{c.metric} by {c.dimension}</option>)}</select></label>}<Comparison data={comparison}/></section><section className="decision-panel"><h3>Which measures move together</h3><Matrix matrix={profile.matrix}/></section></div>
    <section className="decision-panel decision-monthly"><h3>How the picture changes by month</h3><Monthly key={profile.source.sheet_id} trends={profile.trends}/></section>
    <details className="decision-governance"><summary><Info size={16}/>Coverage, field interpretation & boundaries</summary><ul>{profile.limitations.map(l=><li key={l}>{l}</li>)}</ul><div className="decision-field-list">{profile.fields.map(f=><span key={f.column}><strong>{f.column}</strong>{f.role.replaceAll('_',' ')}</span>)}</div><p>{data.prioritization} Snapshot: {data.snapshot}</p><button className="decision-link" onClick={onExplore}>Inspect uploaded records <ArrowRight size={14}/></button></details>
    {present&&<BriefPresentation data={data} onClose={()=>setPresent(false)} onExplore={onExplore}/>}
  </section>;
}
