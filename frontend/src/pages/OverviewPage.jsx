import React, { useEffect, useState } from 'react';
import { getAnalyticsOverview } from '../api/client';

export default function OverviewPage({ onNavigateTab }) {
  const [data, setData] = useState(null);
  const [error, setError] = useState('');
  useEffect(() => { getAnalyticsOverview().then(setData).catch(e => setError(e.message)); }, []);
  if (error) return <p role="alert">{error}</p>;
  if (!data) return <p>Loading sheet analytics…</p>;
  const fmt = n => n == null ? 'Not available' : Number(n).toLocaleString(undefined, { maximumFractionDigits: 3 });
  return <div className="overview-page">
    <div className="executive-banner"><div className="banner-content">
      <h2>Executive overview</h2><p>Live analysis of your uploaded sheets. Each metric retains its source.</p>
    </div><button className="btn-primary" onClick={() => onNavigateTab('copilot')}>Ask AI Copilot</button></div>
    <div className="kpi-grid">
      {[['Datasets', data.stats.datasets], ['Sheets', data.stats.sheets], ['Source rows', data.stats.rows], ['Exact key relationships', data.stats.linked_relationships]].map(([label, value]) =>
        <div className="kpi-card" key={label}><div className="kpi-label">{label}</div><div className="kpi-value">{fmt(value)}</div></div>)}
    </div>
    <p className="subtitle">{data.note}</p>
    {!data.sheets.length && <div className="card-panel"><h3>Start with your data</h3><p>Upload a CSV or Excel workbook to populate this overview.</p><button className="btn-primary" onClick={() => onNavigateTab('ingestion')}>Upload a sheet</button></div>}
    {[...data.sheets].reverse().map(sheet => <div className="card-panel" key={sheet.id} style={{ marginTop: 20 }}>
      <div className="panel-header"><div><h3>{sheet.original_name} / {sheet.name}</h3><p className="panel-sub">{sheet.row_count} rows · {sheet.columns.length} columns</p></div><button className="btn-secondary" onClick={() => onNavigateTab('explorer')}>Explore sheets</button></div>
      <div className="kpi-grid">{sheet.profiles.filter(p => p.numeric).slice(0, 4).map(p => <div className="kpi-card" key={p.column}><div className="kpi-label">Mean {p.column}{p.unit ? ` (${p.unit})` : ''}</div><div className="kpi-value">{fmt(p.numeric.mean)}</div><small>{p.nonempty} recorded values</small></div>)}</div>
      <details><summary>All {sheet.columns.length} column profiles</summary><div className="table-container"><table><thead><tr><th>Column</th><th>Present</th><th>Missing</th><th>Distinct values</th><th>Mean</th><th>Minimum</th><th>Maximum</th></tr></thead><tbody>
        {sheet.profiles.map(p => <tr key={p.column}><td>{p.column}</td><td>{p.nonempty}</td><td>{p.missing}</td><td>{p.distinct}</td><td>{p.numeric ? fmt(p.numeric.mean) : '—'}</td><td>{p.numeric ? fmt(p.numeric.min) : '—'}</td><td>{p.numeric ? fmt(p.numeric.max) : '—'}</td></tr>)}
      </tbody></table></div></details>
    </div>)}
    <div className="card-panel" style={{ marginTop: 20 }}><h3>Connected information</h3>
      {!data.relationships.length && <p>No shared keys found yet. Upload a related sheet to connect records.</p>}
      {data.relationships.map(r => <p key={r.id}><strong>{r.left_file} / {r.left_name} [{r.left_column}] ↔ {r.right_file} / {r.right_name} [{r.right_column}]</strong><br />{r.status === 'linked' ? 'Exact join available' : 'Suggested relationship'} · {r.cardinality} · {r.matching_keys} shared values · {r.matching_pairs} matching row pairs<br /><small>{r.reason}</small></p>)}
    </div>
  </div>;
}
