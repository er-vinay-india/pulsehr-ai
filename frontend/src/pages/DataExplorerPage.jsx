import React, { useEffect, useState } from 'react';
import { getSheets, getSheetRows, getJoinedRows, getSheetProjections } from '../api/client';
import { formatDisplayLabel } from '../utils/displayFormatters';
import DataTable from '../components/DataTable';

export default function DataExplorerPage() {
  const [catalog, setCatalog] = useState({ sheets: [], relationships: [] });
  const [selected, setSelected] = useState('');
  const [relation, setRelation] = useState('');
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState('');
  const [data, setData] = useState(null);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  // New View Mode State: 'table' vs 'projections'
  const [viewMode, setViewMode] = useState('table');
  const [projectionsData, setProjectionsData] = useState(null);
  const [loadingProjections, setLoadingProjections] = useState(false);
  const [hoveredBar, setHoveredBar] = useState(null);
  const [hoveredSlice, setHoveredSlice] = useState(null);

  const refresh = () => getSheets().then(r => {
    setCatalog(r);
    setSelected(current => r.sheets.some(s => String(s.id) === current) ? current : String(r.sheets[r.sheets.length - 1]?.id || ''));
    setRelation('');
    setPage(1);
  }).catch(e => setError(e.message));

  useEffect(() => { refresh(); }, []);

  // Fetch Table Rows
  useEffect(() => {
    if (!selected) { setData(null); return; }
    if (viewMode !== 'table') return;

    let active = true;
    setLoading(true);
    setError('');

    (relation ? getJoinedRows(relation, page) : getSheetRows(selected, page, search))
      .then(r => { if (active) setData(r); })
      .catch(e => { if (active) { setError(e.message); setData(null); } })
      .finally(() => { if (active) setLoading(false); });

    return () => { active = false; };
  }, [selected, relation, page, search, viewMode]);

  // Fetch Projections when in 'projections' mode
  useEffect(() => {
    if (!selected || viewMode !== 'projections') return;

    let active = true;
    setLoadingProjections(true);

    getSheetProjections(selected)
      .then(res => { if (active) setProjectionsData(res); })
      .catch(err => { if (active) console.error('Error fetching sheet projections:', err); })
      .finally(() => { if (active) setLoadingProjections(false); });

    return () => { active = false; };
  }, [selected, viewMode]);

  const selectedSheet = catalog.sheets.find(s => String(s.id) === String(selected));
  const link = catalog.relationships.find(r => String(r.id) === relation);
  const left = catalog.sheets.find(s => s.id === link?.left_sheet);
  const right = catalog.sheets.find(s => s.id === link?.right_sheet);
  const columns = relation
    ? [...(left?.columns || []).map(c => `left.${c}`), ...(right?.columns || []).map(c => `right.${c}`)]
    : data?.columns || [];
  const rows = (data?.rows || []).map(row => relation
    ? { number: `${row.left_row} ↔ ${row.right_row}`, values: Object.fromEntries([...Object.entries(row.left).map(([k,v]) => [`left.${k}`,v]), ...Object.entries(row.right).map(([k,v]) => [`right.${k}`,v])]) }
    : { number: row.row_number, values: row.values });

  return (
    <div className="explorer-page">
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: '1rem' }}>
        <div>
          <h2>Data Explorer & Sheet Projections</h2>
          <p className="subtitle">Inspect original tabular rows, column summary metrics, and direct data extract projections.</p>
        </div>

        {/* View Mode Toggle */}
        <div className="view-mode-pill-toggle">
          <button
            className={`toggle-btn ${viewMode === 'table' ? 'active' : ''}`}
            onClick={() => setViewMode('table')}
          >
            📋 Interactive Data Table
          </button>
          <button
            className={`toggle-btn ${viewMode === 'projections' ? 'active' : ''}`}
            onClick={() => setViewMode('projections')}
          >
            📊 Sheet Visual Projections & Column Profiles
          </button>
        </div>
      </div>

      {/* Filters Toolbar */}
      <div className="filters-toolbar" style={{ marginTop: '1rem' }}>
        <label>
          Sheet{' '}
          <select value={selected} onChange={e => { setSelected(e.target.value); setRelation(''); setPage(1); setSearch(''); }}>
            <option value="">Choose a sheet</option>
            {catalog.sheets.map(s => (
              <option key={s.id} value={s.id}>
                {s.display_name || s.original_name} {s.name && s.name !== 'Sheet1' ? `· ${s.name}` : ''} ({s.row_count} rows)
              </option>
            ))}
          </select>
        </label>

        {viewMode === 'table' && (
          <>
            <label>
              Related view{' '}
              <select value={relation} onChange={e => { setRelation(e.target.value); setPage(1); setSearch(''); }}>
                <option value="">Original sheet</option>
                {catalog.relationships.filter(r => r.status === 'linked' && [r.left_sheet, r.right_sheet].includes(Number(selected))).map(r => (
                  <option key={r.id} value={r.id}>{r.left_file} [{r.left_column}] ↔ {r.right_file} [{r.right_column}]</option>
                ))}
              </select>
            </label>
            {!relation && (
              <label>
                Server Search{' '}
                <input value={search} onChange={e => { setSearch(e.target.value); setPage(1); }} placeholder="Search all rows in DB" />
              </label>
            )}
          </>
        )}

        <button className="btn-secondary" onClick={refresh}>Refresh</button>
      </div>

      {link && viewMode === 'table' && (
        <p style={{ fontSize: '0.85rem', color: 'var(--fg-secondary)', margin: '0.5rem 0' }}>
          Inner join: left = {left?.display_name || left?.original_name}; right = {right?.display_name || right?.original_name}. {link.cardinality}. Values match after trimming whitespace and ignoring case. Unmatched rows remain in their original sheets.
        </p>
      )}

      {error && <p role="alert" className="error-banner">{error}</p>}
      {!catalog.sheets.length && <p>No sheets available. Upload a CSV or Excel workbook.</p>}

      {/* VIEW 1: INTERACTIVE DATA TABLE VIEW */}
      {viewMode === 'table' && (
        <>
          {data ? (
            <DataTable
              columns={columns}
              rows={rows}
              totalRows={data.total}
              serverPage={page}
              serverTotalPages={data.pages}
              onPageChange={newPage => setPage(newPage)}
              loading={loading}
              sourceLabel={relation ? 'relational_join' : (selectedSheet?.display_name || selectedSheet?.original_name || 'table')}
            />
          ) : loading ? (
            <p className="loading-state">Loading rows…</p>
          ) : null}
        </>
      )}

      {/* VIEW 2: SHEET VISUAL PROJECTIONS & COLUMN PROFILES */}
      {viewMode === 'projections' && (
        <div className="sheet-projections-container" style={{ marginTop: '1.25rem' }}>
          {loadingProjections ? (
            <p className="loading-state">Computing sheet projections and column profiles…</p>
          ) : projectionsData ? (
            <>
              {/* Sheet Summary Bar */}
              <div className="sheet-summary-banner">
                <div>
                  <h3>{selectedSheet?.display_name || projectionsData.original_name} {projectionsData.sheet_name && projectionsData.sheet_name !== 'Sheet1' ? `(${projectionsData.sheet_name})` : ''}</h3>
                  <p className="subtitle">{projectionsData.row_count} total records · {projectionsData.col_count} columns profiled</p>
                </div>
              </div>

              {/* Column Summary Statistics Grid */}
              <h4 style={{ margin: '1.25rem 0 0.75rem 0', fontSize: '0.95rem', color: 'var(--fg-primary)' }}>
                Column Profiles & Summary Statistics
              </h4>
              <div className="column-profiles-kpi-grid">
                {projectionsData.column_stats?.map((col) => (
                  <div key={col.column} className="kpi-card column-stat-card">
                    <div className="kpi-label" title={`Source field: ${col.column}`}>
                      {col.display_name || formatDisplayLabel(col.column)}
                    </div>
                    {col.is_numeric ? (
                      <>
                        <div className="kpi-value" style={{ fontSize: '1.25rem' }}>
                          Mean: {col.mean} {col.unit}
                        </div>
                        <div className="stat-sub">
                          Spread: {col.min} to {col.max} {col.unit} · Median: {col.median}
                        </div>
                      </>
                    ) : (
                      <>
                        <div className="kpi-value" style={{ fontSize: '1.25rem' }}>
                          {col.distinct} distinct values
                        </div>
                        <div className="stat-sub">
                          {col.nonempty} recorded · {col.missing} missing
                        </div>
                      </>
                    )}
                  </div>
                ))}
              </div>

              {/* Direct Data Extract Visual Charts */}
              <h4 style={{ margin: '1.75rem 0 0.75rem 0', fontSize: '0.95rem', color: 'var(--fg-primary)' }}>
                Direct Data Extract Charts (Averages, Ratings, Overtime, Distributions)
              </h4>
              <div className="visual-dashboard-grid" style={{ marginTop: '0.5rem' }}>
                {projectionsData.projections?.map((proj) => {
                  if (proj.type === 'bar') {
                    const bars = proj.bars || [];
                    const maxVal = Math.max(...bars.map(b => b.value || 0), 1);
                    const svgW = 540;
                    const svgH = 200;
                    const margin = { top: 22, right: 20, bottom: 40, left: 45 };
                    const innerW = svgW - margin.left - margin.right;
                    const innerH = svgH - margin.top - margin.bottom;
                    const slotW = innerW / Math.max(bars.length, 1);
                    const barW = Math.min(32, slotW * 0.55);

                    return (
                      <div key={proj.id} className="visual-card">
                        <div className="card-title-group">
                          <h4>{proj.title}</h4>
                          <p className="card-sub">Direct data extract grouped by {formatDisplayLabel(proj.category_col)} ({proj.unit || 'value'})</p>
                        </div>
                        <div className="card-visual-body">
                          <div className="chart-svg-wrap">
                            <svg viewBox={`0 0 ${svgW} ${svgH}`} className="responsive-svg">
                              {[0, 0.25, 0.5, 0.75, 1].map((ratio) => {
                                const y = margin.top + innerH * (1 - ratio);
                                const val = Math.round(maxVal * ratio);
                                return (
                                  <g key={ratio}>
                                    <line x1={margin.left} y1={y} x2={svgW - margin.right} y2={y} stroke="var(--border-color, #334155)" strokeDasharray="3 3" opacity={0.3} />
                                    <text x={margin.left - 6} y={y + 3} textAnchor="end" fontSize="9" fill="var(--text-muted, #94a3b8)">{val}</text>
                                  </g>
                                );
                              })}
                              {bars.map((b, idx) => {
                                const h = Math.max(3, (b.value / maxVal) * innerH);
                                const x = margin.left + idx * slotW + (slotW - barW) / 2;
                                const y = margin.top + innerH - h;
                                const isHov = hoveredBar === `${proj.id}-${idx}`;
                                return (
                                  <g key={idx} onMouseEnter={() => setHoveredBar(`${proj.id}-${idx}`)} onMouseLeave={() => setHoveredBar(null)} style={{ cursor: 'pointer' }}>
                                    <rect x={x} y={y} width={barW} height={h} rx="3" fill={isHov ? '#38bdf8' : '#0ea5e9'} opacity={isHov ? 1 : 0.85} />
                                    <text x={x + barW / 2} y={y - 5} textAnchor="middle" fontSize="10" fontWeight="600" fill={isHov ? '#ffffff' : 'var(--text-muted, #94a3b8)'}>{b.value}</text>
                                    <text x={x + barW / 2} y={svgH - 12} textAnchor="middle" fontSize="10" fill={isHov ? '#ffffff' : 'var(--text-muted, #94a3b8)'}>
                                      {b.label.length > 9 ? `${b.label.slice(0, 8)}…` : b.label}
                                    </text>
                                  </g>
                                );
                              })}
                            </svg>
                          </div>
                        </div>
                      </div>
                    );
                  }

                  if (proj.type === 'donut') {
                    const slices = proj.slices || [];
                    const total = proj.total || 1;
                    const size = 180;
                    const radius = 78;
                    const innerRadius = 48;
                    const center = size / 2;
                    let cumulativeAngle = -Math.PI / 2;

                    const arcs = slices.map((slice) => {
                      const angle = total > 0 ? (slice.count / total) * (2 * Math.PI) : 0;
                      const start = cumulativeAngle;
                      const end = cumulativeAngle + angle;
                      cumulativeAngle += angle;

                      const x1 = center + radius * Math.cos(start);
                      const y1 = center + radius * Math.sin(start);
                      const x2 = center + radius * Math.cos(end);
                      const y2 = center + radius * Math.sin(end);

                      const ix1 = center + innerRadius * Math.cos(end);
                      const iy1 = center + innerRadius * Math.sin(end);
                      const ix2 = center + innerRadius * Math.cos(start);
                      const iy2 = center + innerRadius * Math.sin(start);

                      const largeArc = angle > Math.PI ? 1 : 0;
                      const path = total > 0 && slice.count > 0 ? `
                        M ${x1} ${y1}
                        A ${radius} ${radius} 0 ${largeArc} 1 ${x2} ${y2}
                        L ${ix1} ${iy1}
                        A ${innerRadius} ${innerRadius} 0 ${largeArc} 0 ${ix2} ${iy2}
                        Z
                      ` : '';

                      return { ...slice, path };
                    });

                    return (
                      <div key={proj.id} className="visual-card">
                        <div className="card-title-group">
                          <h4>{proj.title}</h4>
                          <p className="card-sub">Discrete distribution ({total} total records)</p>
                        </div>
                        <div className="card-visual-body">
                          <div className="donut-layout">
                            <div className="donut-svg-wrap">
                              <svg viewBox={`0 0 ${size} ${size}`} className="donut-svg">
                                {arcs.map((arc, idx) => (
                                  <path
                                    key={idx}
                                    d={arc.path}
                                    fill={arc.color}
                                    stroke="var(--bg-card, #0f172a)"
                                    strokeWidth="2"
                                    opacity={hoveredSlice === `${proj.id}-${idx}` ? 1 : 0.88}
                                    onMouseEnter={() => setHoveredSlice(`${proj.id}-${idx}`)}
                                    onMouseLeave={() => setHoveredSlice(null)}
                                    style={{ cursor: 'pointer' }}
                                  />
                                ))}
                                <text x={center} y={center - 2} textAnchor="middle" fontSize="16" fontWeight="700" fill="var(--text-bright, #fff)">{total}</text>
                                <text x={center} y={center + 14} textAnchor="middle" fontSize="9" fill="var(--text-muted, #94a3b8)">Records</text>
                              </svg>
                            </div>
                            <div className="donut-legend">
                              {slices.map((slice, idx) => (
                                <div key={idx} className="legend-item">
                                  <span className="legend-dot" style={{ backgroundColor: slice.color }} />
                                  <span className="legend-label">{slice.label}</span>
                                  <span className="legend-count">{slice.count}</span>
                                  <span className="legend-pct">({slice.pct}%)</span>
                                </div>
                              ))}
                            </div>
                          </div>
                        </div>
                      </div>
                    );
                  }

                  return null;
                })}
              </div>
            </>
          ) : (
            <p>Select a sheet to view its visual projections and column statistics.</p>
          )}
        </div>
      )}
    </div>
  );
}
