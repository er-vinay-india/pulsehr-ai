import React, { useEffect, useState } from 'react';
import { getSheets, getSheetRows, getJoinedRows } from '../api/client';

export default function DataExplorerPage() {
  const [catalog, setCatalog] = useState({ sheets: [], relationships: [] });
  const [selected, setSelected] = useState('');
  const [relation, setRelation] = useState('');
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState('');
  const [data, setData] = useState(null);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const refresh = () => getSheets().then(r => { setCatalog(r); setSelected(current => r.sheets.some(s => String(s.id) === current) ? current : String(r.sheets[r.sheets.length - 1]?.id || '')); setRelation(''); setPage(1); }).catch(e => setError(e.message));
  useEffect(() => { refresh(); }, []);
  useEffect(() => {
    if (!selected) { setData(null); return; }
    let active = true;
    setLoading(true); setError('');
    (relation ? getJoinedRows(relation, page) : getSheetRows(selected, page, search)).then(r => { if (active) setData(r); }).catch(e => { if (active) { setError(e.message); setData(null); } }).finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [selected, relation, page, search]);
  const link = catalog.relationships.find(r => String(r.id) === relation);
  const left = catalog.sheets.find(s => s.id === link?.left_sheet);
  const right = catalog.sheets.find(s => s.id === link?.right_sheet);
  const columns = relation ? [...(left?.columns || []).map(c => `left.${c}`), ...(right?.columns || []).map(c => `right.${c}`)] : data?.columns || [];
  const rows = (data?.rows || []).map(row => relation ? { number: `${row.left_row} ↔ ${row.right_row}`, values: Object.fromEntries([...Object.entries(row.left).map(([k,v]) => [`left.${k}`,v]), ...Object.entries(row.right).map(([k,v]) => [`right.${k}`,v])]) } : { number: row.row_number, values: row.values });
  return <div className="explorer-page">
    <h2>All sheets explorer</h2><p className="subtitle">Original rows from every uploaded file and sheet, with source-preserving joins.</p>
    <div className="filters-toolbar">
      <label>Sheet <select value={selected} onChange={e => { setSelected(e.target.value); setRelation(''); setPage(1); setSearch(''); }}><option value="">Choose a sheet</option>{catalog.sheets.map(s => <option key={s.id} value={s.id}>{s.original_name} / {s.name} ({s.row_count} rows)</option>)}</select></label>
      <label>Related view <select value={relation} onChange={e => { setRelation(e.target.value); setPage(1); setSearch(''); }}><option value="">Original sheet</option>{catalog.relationships.filter(r => r.status === 'linked' && [r.left_sheet, r.right_sheet].includes(Number(selected))).map(r => <option key={r.id} value={r.id}>{r.left_file} [{r.left_column}] ↔ {r.right_file} [{r.right_column}]</option>)}</select></label>
      {!relation && <label>Search <input value={search} onChange={e => { setSearch(e.target.value); setPage(1); }} placeholder="Search all column values" /></label>}
      <button className="btn-secondary" onClick={refresh}>Refresh</button>
    </div>
    {link && <p>Inner join: left = {left?.original_name} / {left?.name}; right = {right?.original_name} / {right?.name}. {link.cardinality}. Values match after trimming whitespace and ignoring case. Unmatched rows remain in their original sheets. Joined measures may repeat.</p>}
    {error && <p role="alert">{error}</p>}
    {!catalog.sheets.length && <p>No sheets available. Upload a CSV or Excel workbook.</p>}
    {loading ? <p>Loading rows…</p> : data && <><p>{data.total} {relation ? 'matching row pairs' : 'rows'} · Page {page} of {data.pages}</p><div className="table-container"><table><thead><tr><th>Source row</th>{columns.map(c => <th key={c}>{c}</th>)}</tr></thead><tbody>{rows.map((row,i) => <tr key={i}><td>{row.number}</td>{columns.map(c => <td key={c}>{String(row.values[c] ?? '—')}</td>)}</tr>)}</tbody></table></div><div className="table-pagination"><button className="btn-secondary" disabled={page <= 1} onClick={() => setPage(p => p-1)}>Previous</button><button className="btn-secondary" disabled={page >= data.pages} onClick={() => setPage(p => p+1)}>Next</button></div></>}
  </div>;
}
