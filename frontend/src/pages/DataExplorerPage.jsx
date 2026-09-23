import React, { useEffect, useState } from 'react';
import {
  getSheets,
  getSheetRows,
  getJoinedRows,
  getSheetProjections
} from '../api/client';
import { formatDisplayLabel } from '../utils/displayFormatters';
import DataTable from '../components/DataTable';
import {
  FileSpreadsheet,
  Table,
  BarChart2,
  GitBranch,
  ShieldCheck,
  Search,
  Layers,
  Info,
  ChevronRight
} from 'lucide-react';
import ExecutiveHeatmapChart from '../components/charts/ExecutiveHeatmapChart';

const fmt = (n) => (n == null ? 'Unavailable' : Number(n).toLocaleString(undefined, { maximumFractionDigits: 2 }));

export default function DataExplorerPage() {
  const [catalog, setCatalog] = useState({ sheets: [], relationships: [] });
  const [selected, setSelected] = useState('');
  const [relation, setRelation] = useState('');
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState('');
  const [data, setData] = useState(null);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  // View Modes: 'table' | 'projections' | 'diagnostics'
  const [viewMode, setViewMode] = useState('table');
  const [projectionsData, setProjectionsData] = useState(null);
  const [loadingProjections, setLoadingProjections] = useState(false);
  const [hoveredSlice, setHoveredSlice] = useState(null);

  // Diagnostics State
  const [diagnosticsData, setDiagnosticsData] = useState(null);
  const [loadingDiagnostics, setLoadingDiagnostics] = useState(false);
  const [selectedMatrixCell, setSelectedMatrixCell] = useState(null);

  const refresh = () =>
    getSheets()
      .then((r) => {
        setCatalog(r);
        setSelected((current) =>
          r.sheets.some((s) => String(s.id) === current)
            ? current
            : String(r.sheets[r.sheets.length - 1]?.id || '')
        );
        setRelation('');
        setPage(1);
      })
      .catch((e) => setError(e.message));

  useEffect(() => {
    refresh();
  }, []);

  // Fetch Table Rows
  useEffect(() => {
    if (!selected) {
      setData(null);
      return;
    }
    if (viewMode !== 'table') return;

    let active = true;
    setLoading(true);
    setError('');

    (relation ? getJoinedRows(relation, page) : getSheetRows(selected, page, search))
      .then((r) => {
        if (active) setData(r);
      })
      .catch((e) => {
        if (active) {
          setError(e.message);
          setData(null);
        }
      })
      .finally(() => {
        if (active) setLoading(false);
      });

    return () => {
      active = false;
    };
  }, [selected, relation, page, search, viewMode]);

  // Fetch Projections when in 'projections' mode
  useEffect(() => {
    if (!selected || viewMode !== 'projections') return;

    let active = true;
    setLoadingProjections(true);

    getSheetProjections(selected)
      .then((res) => {
        if (active) setProjectionsData(res);
      })
      .catch((err) => {
        if (active) console.error('Error fetching sheet projections:', err);
      })
      .finally(() => {
        if (active) setLoadingProjections(false);
      });

    return () => {
      active = false;
    };
  }, [selected, viewMode]);

  // Fetch Diagnostics when in 'diagnostics' mode
  useEffect(() => {
    if (!selected || viewMode !== 'diagnostics') return;

    let active = true;
    setLoadingDiagnostics(true);

    fetch(`/api/analytics/decision-brief?sheet_id=${selected}`)
      .then((r) => (r.ok ? r.json() : null))
      .then((res) => {
        if (active && res) {
          setDiagnosticsData(res);
          setSelectedMatrixCell(null);
        }
      })
      .catch((err) => console.error('Error loading diagnostics:', err))
      .finally(() => {
        if (active) setLoadingDiagnostics(false);
      });

    return () => {
      active = false;
    };
  }, [selected, viewMode]);

  const selectedSheet = catalog.sheets.find((s) => String(s.id) === String(selected));
  const link = catalog.relationships.find((r) => String(r.id) === relation);
  const left = catalog.sheets.find((s) => s.id === link?.left_sheet);
  const right = catalog.sheets.find((s) => s.id === link?.right_sheet);
  const columns = relation
    ? [
        ...(left?.columns || []).map((c) => `left.${c}`),
        ...(right?.columns || []).map((c) => `right.${c}`)
      ]
    : data?.columns || [];
  const rows = (data?.rows || []).map((row) =>
    relation
      ? {
          number: `${row.left_row} ↔ ${row.right_row}`,
          values: Object.fromEntries([
            ...Object.entries(row.left).map(([k, v]) => [`left.${k}`, v]),
            ...Object.entries(row.right).map(([k, v]) => [`right.${k}`, v])
          ])
        }
      : { number: row.row_number, values: row.values }
  );

  const diagProfile = diagnosticsData?.profiles?.[0];
  const matrix = diagProfile?.matrix;

  return (
    <div className="explorer-page">
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'flex-start',
          flexWrap: 'wrap',
          gap: '1rem',
          marginBottom: '1rem'
        }}
      >
        <div>
          <h2>Data Explorer & Technical Workbench</h2>
          <p className="subtitle">
            Deep tabular investigation, statistical correlation matrices, and column schema profiling.
          </p>
        </div>

        {/* View Mode Toggle */}
        <div className="view-mode-pill-toggle">
          <button
            className={`toggle-btn ${viewMode === 'table' ? 'active' : ''}`}
            onClick={() => setViewMode('table')}
          >
            📋 Data Table
          </button>
          <button
            className={`toggle-btn ${viewMode === 'projections' ? 'active' : ''}`}
            onClick={() => setViewMode('projections')}
          >
            📊 Column Projections
          </button>
          <button
            className={`toggle-btn ${viewMode === 'diagnostics' ? 'active' : ''}`}
            onClick={() => setViewMode('diagnostics')}
          >
            🔬 Statistical Diagnostics & Schema
          </button>
        </div>
      </div>

      {/* Filters Toolbar */}
      <div className="filters-toolbar" style={{ marginTop: '0.5rem' }}>
        <label>
          Sheet{' '}
          <select
            value={selected}
            onChange={(e) => {
              setSelected(e.target.value);
              setRelation('');
              setPage(1);
              setSearch('');
            }}
          >
            <option value="">Choose a sheet</option>
            {catalog.sheets.map((s) => (
              <option key={s.id} value={s.id}>
                {s.display_name || s.original_name}{' '}
                {s.name && s.name !== 'Sheet1' ? `· ${s.name}` : ''} ({s.row_count} rows)
              </option>
            ))}
          </select>
        </label>

        {viewMode === 'table' && (
          <>
            <label>
              Related view{' '}
              <select
                value={relation}
                onChange={(e) => {
                  setRelation(e.target.value);
                  setPage(1);
                  setSearch('');
                }}
              >
                <option value="">Original sheet</option>
                {catalog.relationships
                  .filter(
                    (r) =>
                      r.status === 'linked' &&
                      [r.left_sheet, r.right_sheet].includes(Number(selected))
                  )
                  .map((r) => (
                    <option key={r.id} value={r.id}>
                      {r.left_file} [{r.left_column}] ↔ {r.right_file} [{r.right_column}]
                    </option>
                  ))}
              </select>
            </label>
            {!relation && (
              <label>
                Server Search{' '}
                <input
                  value={search}
                  onChange={(e) => {
                    setSearch(e.target.value);
                    setPage(1);
                  }}
                  placeholder="Search all rows in DB"
                />
              </label>
            )}
          </>
        )}

        <button className="btn-secondary" onClick={refresh}>
          Refresh
        </button>
      </div>

      {link && viewMode === 'table' && (
        <p style={{ fontSize: '0.85rem', color: 'var(--fg-secondary)', margin: '0.5rem 0' }}>
          Inner join: left = {left?.display_name || left?.original_name}; right ={' '}
          {right?.display_name || right?.original_name}. {link.cardinality}. Values match after
          trimming whitespace and ignoring case.
        </p>
      )}

      {error && (
        <p role="alert" className="error-banner">
          {error}
        </p>
      )}
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
              onPageChange={(newPage) => setPage(newPage)}
              loading={loading}
              sourceLabel={
                relation
                  ? 'relational_join'
                  : selectedSheet?.display_name || selectedSheet?.original_name || 'table'
              }
            />
          ) : loading ? (
            <p>Loading table rows...</p>
          ) : null}
        </>
      )}

      {/* VIEW 2: VISUAL PROJECTIONS VIEW */}
      {viewMode === 'projections' && (
        <div className="projections-container" style={{ marginTop: '1.5rem' }}>
          {loadingProjections ? (
            <p>Computing statistical projections and column profiles...</p>
          ) : projectionsData ? (
            <>
              {projectionsData.summary_kpis && projectionsData.summary_kpis.length > 0 && (
                <div className="kpi-grid" style={{ marginBottom: '1.5rem' }}>
                  {projectionsData.summary_kpis.map((kpi, idx) => (
                    <div key={idx} className="kpi-card">
                      <div className="kpi-label">{kpi.label}</div>
                      <div className="kpi-value">{kpi.value}</div>
                      {kpi.sub && <div className="kpi-sub">{kpi.sub}</div>}
                    </div>
                  ))}
                </div>
              )}

              <div className="visual-cards-grid">
                {projectionsData.visualizations?.map((proj) => {
                  if (proj.type === 'bar') {
                    const bars = proj.data || [];
                    const maxVal = Math.max(...bars.map((b) => b.value), 1);
                    return (
                      <div key={proj.id} className="visual-card">
                        <div className="card-title-group">
                          <h4>{proj.title}</h4>
                          <p className="card-sub">{proj.subtitle || 'Category distribution'}</p>
                        </div>
                        <div className="card-visual-body">
                          <div className="bar-chart-list">
                            {bars.map((bar, idx) => {
                              const pct = Math.min(100, Math.max(0, (bar.value / maxVal) * 100));
                              return (
                                <div key={idx} className="bar-row">
                                  <span className="bar-label" title={bar.label}>
                                    {bar.label}
                                  </span>
                                  <div className="bar-track">
                                    <div className="bar-fill" style={{ width: `${pct}%` }}>
                                      <span className="bar-val">{bar.value}</span>
                                    </div>
                                  </div>
                                </div>
                              );
                            })}
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

      {/* VIEW 3: STATISTICAL DIAGNOSTICS & SCHEMA MATRIX (Deep Technical Engine) */}
      {viewMode === 'diagnostics' && (
        <div className="diagnostics-workbench" style={{ marginTop: '1.5rem' }}>
          {loadingDiagnostics ? (
            <p>Loading statistical matrices and schema definitions...</p>
          ) : diagnosticsData && diagProfile ? (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '2rem' }}>
              {/* Section A: Spearman Correlation Matrix */}
              <div className="card-panel">
                <div className="section-title-row" style={{ marginBottom: '1rem' }}>
                  <div>
                    <h3 style={{ margin: 0, color: '#f8fafc' }}>
                      Spearman Rank Correlation Matrix
                    </h3>
                    <p className="subtitle" style={{ margin: '4px 0 0 0' }}>
                      Pairwise monotonic correlation coefficients (\(\rho\)), sample pair counts,
                      and within-group variations.
                    </p>
                  </div>
                  <span className="source-file-badge">
                    {diagProfile.measures_analyzed} Numeric Measures
                  </span>
                </div>

                {matrix && matrix.metrics.length >= 2 ? (
                  <>
                    <ExecutiveHeatmapChart
                      matrix={matrix}
                      height={320}
                      onSelectPair={(pair) => {
                        const found = matrix.pairs.find(
                          (p) =>
                            (p.x === pair.x && p.y === pair.y) ||
                            (p.x === pair.y && p.y === pair.x)
                        );
                        setSelectedMatrixCell(found || pair);
                      }}
                    />

                    {selectedMatrixCell && (
                      <div
                        className="decision-matrix-detail"
                        style={{
                          marginTop: '1rem',
                          padding: '1.25rem',
                          background: 'rgba(15, 23, 42, 0.7)',
                          borderRadius: '8px',
                          border: '1px solid rgba(255, 255, 255, 0.1)'
                        }}
                      >
                        <h4 style={{ margin: '0 0 0.5rem 0', color: '#38bdf8' }}>
                          Pair Detail: {selectedMatrixCell.x} × {selectedMatrixCell.y}
                        </h4>
                        <p style={{ margin: '0 0 0.5rem 0', color: '#e2e8f0', fontSize: '0.9rem' }}>
                          {selectedMatrixCell.excluded_reason ||
                            `Spearman Rank Correlation \u03C1 = ${fmt(selectedMatrixCell.coefficient)} across ${selectedMatrixCell.paired_rows} paired records.`}
                        </p>
                        <small style={{ color: '#94a3b8' }}>
                          Statistical note: Observational correlation does not establish causation.
                          Check group mix and sample balance.
                        </small>
                        {selectedMatrixCell.within_groups?.length > 0 && (
                          <div style={{ marginTop: '0.75rem' }}>
                            <strong style={{ fontSize: '0.8rem', color: '#cbd5e1' }}>
                              Within-group variation:
                            </strong>
                            <ul style={{ margin: '0.35rem 0 0 1.25rem', fontSize: '0.8rem', color: '#94a3b8' }}>
                              {selectedMatrixCell.within_groups.map((g) => (
                                <li key={g.group}>
                                  {g.group}: \u03C1 = {fmt(g.coefficient)} ({g.paired_rows} pairs)
                                </li>
                              ))}
                            </ul>
                          </div>
                        )}
                      </div>
                    )}
                  </>
                ) : (
                  <p className="decision-empty">
                    A relationship matrix requires at least two numeric measures.
                  </p>
                )}
              </div>

              {/* Section B: Column Structural Profiling */}
              <div className="card-panel">
                <div className="section-title-row" style={{ marginBottom: '1rem' }}>
                  <div>
                    <h3 style={{ margin: 0, color: '#f8fafc' }}>
                      Column Profiling & Semantic Roles
                    </h3>
                    <p className="subtitle" style={{ margin: '4px 0 0 0' }}>
                      Deterministic schema classifications and missing value ratios.
                    </p>
                  </div>
                </div>

                <div className="evidence-table-wrap">
                  <table className="evidence-table" style={{ width: '100%' }}>
                    <thead>
                      <tr>
                        <th>Column Name</th>
                        <th>Classified Role</th>
                        <th>Source Sheet</th>
                      </tr>
                    </thead>
                    <tbody>
                      {diagProfile.fields.map((f) => (
                        <tr key={f.column}>
                          <td>
                            <strong>{f.column}</strong>
                          </td>
                          <td>
                            <span className="col-chip" style={{ textTransform: 'capitalize' }}>
                              {f.role.replaceAll('_', ' ')}
                            </span>
                          </td>
                          <td>{diagProfile.source?.sheet}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>

              {/* Section C: Verified Relationships & Foreign Keys */}
              {catalog.relationships.length > 0 && (
                <div className="card-panel">
                  <div className="section-title-row" style={{ marginBottom: '1rem' }}>
                    <div>
                      <h3 style={{ margin: 0, color: '#f8fafc' }}>
                        Cross-Sheet Relational Join Candidates
                      </h3>
                      <p className="subtitle" style={{ margin: '4px 0 0 0' }}>
                        Verified foreign key links, join cardinality, and match statistics.
                      </p>
                    </div>
                  </div>

                  <div className="evidence-table-wrap">
                    <table className="evidence-table" style={{ width: '100%' }}>
                      <thead>
                        <tr>
                          <th>Relationship</th>
                          <th>Left Sheet & Column</th>
                          <th>Right Sheet & Column</th>
                          <th>Cardinality</th>
                          <th>Status</th>
                        </tr>
                      </thead>
                      <tbody>
                        {catalog.relationships.map((rel) => (
                          <tr key={rel.id}>
                            <td>
                              <code>#{rel.id}</code>
                            </td>
                            <td>
                              {rel.left_file} [<strong>{rel.left_column}</strong>]
                            </td>
                            <td>
                              {rel.right_file} [<strong>{rel.right_column}</strong>]
                            </td>
                            <td>{rel.cardinality || 'Unknown'}</td>
                            <td>
                              <span
                                className={`signal-kind-pill ${
                                  rel.status === 'linked' ? 'pill-standard' : 'pill-risk'
                                }`}
                              >
                                {rel.status}
                              </span>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}
            </div>
          ) : (
            <p>Select a sheet to inspect its deep statistical diagnostics.</p>
          )}
        </div>
      )}
    </div>
  );
}
