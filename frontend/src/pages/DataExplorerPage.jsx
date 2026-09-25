import React, { useEffect, useState } from 'react';
import {
  getSheets,
  getSheetRows,
  getJoinedRows,
  getSheetProjections,
  getSheetEdaReport,
  getDerivedTables,
  getDerivedTableRows,
  getCrossSheetCorrelations,
  runEdaPipeline
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
  ChevronRight,
  Sparkles,
  RefreshCw,
  GitMerge,
  AlertTriangle,
  CheckCircle2,
  TrendingDown,
  TrendingUp,
  ArrowRight
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

  // Data Version State: 'curated' (Post-EDA normalized) | 'raw' (Original values)
  const [dataVersion, setDataVersion] = useState('curated');

  // Derived Tables State
  const [derivedTables, setDerivedTables] = useState([]);
  const [selectedDerivedId, setSelectedDerivedId] = useState(() => {
    const params = new URLSearchParams(window.location.search);
    return params.get('derived_id') || '';
  });

  // View Modes: 'table' | 'eda' | 'projections' | 'diagnostics'
  const [viewMode, setViewMode] = useState(() => {
    const params = new URLSearchParams(window.location.search);
    const v = params.get('view');
    return ['table', 'eda', 'projections', 'diagnostics'].includes(v) ? v : 'table';
  });
  const [projectionsData, setProjectionsData] = useState(null);
  const [loadingProjections, setLoadingProjections] = useState(false);
  const [hoveredSlice, setHoveredSlice] = useState(null);

  // Diagnostics State
  const [diagnosticsData, setDiagnosticsData] = useState(null);
  const [loadingDiagnostics, setLoadingDiagnostics] = useState(false);
  const [selectedMatrixCell, setSelectedMatrixCell] = useState(null);

  // EDA State
  const [edaReport, setEdaReport] = useState(null);
  const [loadingEda, setLoadingEda] = useState(false);
  const [isRerunningEda, setIsRerunningEda] = useState(false);
  const [crossCorrelations, setCrossCorrelations] = useState([]);

  const refresh = () => {
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

    getDerivedTables()
      .then((res) => {
        setDerivedTables(res.derived_tables || []);
      })
      .catch(() => {});

    getCrossSheetCorrelations()
      .then((res) => {
        setCrossCorrelations(res.correlations || []);
      })
      .catch(() => {});
  };

  useEffect(() => {
    refresh();
  }, []);

  // Fetch Table Rows (Supports Curated, Raw, Joined, or Derived)
  useEffect(() => {
    if (!selected && !selectedDerivedId) {
      setData(null);
      return;
    }
    if (viewMode !== 'table') return;

    let active = true;
    setLoading(true);
    setError('');

    const fetchPromise = selectedDerivedId
      ? getDerivedTableRows(selectedDerivedId, page, search)
      : relation
      ? getJoinedRows(relation, page)
      : getSheetRows(selected, page, search, dataVersion);

    fetchPromise
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
  }, [selected, selectedDerivedId, relation, page, search, viewMode, dataVersion]);

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

  // Fetch EDA Report when in 'eda' mode or when selected sheet changes
  useEffect(() => {
    if (!selected) return;

    let active = true;
    if (viewMode === 'eda') setLoadingEda(true);

    getSheetEdaReport(selected)
      .then((rep) => {
        if (active) setEdaReport(rep);
      })
      .catch((err) => {
        if (active) console.error('Error loading EDA report:', err);
      })
      .finally(() => {
        if (active) setLoadingEda(false);
      });

    return () => {
      active = false;
    };
  }, [selected, viewMode]);

  const handleRerunEda = () => {
    setIsRerunningEda(true);
    runEdaPipeline()
      .then(() => {
        refresh();
        if (selected) {
          return getSheetEdaReport(selected).then((rep) => setEdaReport(rep));
        }
      })
      .catch((err) => console.error('Failed to rerun EDA:', err))
      .finally(() => setIsRerunningEda(false));
  };

  const selectedSheet = catalog.sheets.find((s) => String(s.id) === String(selected));
  const link = catalog.relationships.find((r) => String(r.id) === relation);
  const left = catalog.sheets.find((s) => s.id === link?.left_sheet);
  const right = catalog.sheets.find((s) => s.id === link?.right_sheet);

  const activeDerivedTable = derivedTables.find((dt) => String(dt.id) === String(selectedDerivedId));

  const columns = selectedDerivedId
    ? activeDerivedTable?.columns || data?.columns || []
    : relation
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
      : {
          number: row.row_number,
          values: row.values,
          anomalies: row.anomalies || []
        }
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
            Dual-version tabular inspection (Raw vs. Post-EDA Curated), cross-sheet correlation discovery, and deep schema profiling.
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
            className={`toggle-btn ${viewMode === 'eda' ? 'active' : ''}`}
            onClick={() => setViewMode('eda')}
          >
            🔬 Exploratory Data Analysis (EDA)
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
            📐 Statistical Diagnostics
          </button>
        </div>
      </div>

      {/* Filters Toolbar */}
      <div className="filters-toolbar" style={{ marginTop: '0.5rem' }}>
        <label>
          Sheet{' '}
          <select
            value={selected}
            disabled={!!selectedDerivedId}
            onChange={(e) => {
              setSelected(e.target.value);
              setSelectedDerivedId('');
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

        {viewMode === 'table' && !selectedDerivedId && (
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

      {link && viewMode === 'table' && !selectedDerivedId && (
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

      {/* VIEW 1: INTERACTIVE DATA TABLE VIEW (WITH DUAL VERSION TOGGLE) */}
      {viewMode === 'table' && (
        <>
          {/* Dual Version & Derived Views Toggle Bar */}
          <div className="table-version-toggle-bar">
            <div className="version-pills">
              <button
                className={`version-pill ${dataVersion === 'curated' && !selectedDerivedId ? 'active' : ''}`}
                onClick={() => {
                  setSelectedDerivedId('');
                  setDataVersion('curated');
                  setPage(1);
                }}
              >
                ✨ Post-EDA (Normalized & Curated)
              </button>
              <button
                className={`version-pill ${dataVersion === 'raw' && !selectedDerivedId ? 'active' : ''}`}
                onClick={() => {
                  setSelectedDerivedId('');
                  setDataVersion('raw');
                  setPage(1);
                }}
              >
                📋 Raw Ingested Data
              </button>
            </div>

            {/* Derived Views Dropdown */}
            {derivedTables.length > 0 && (
              <div className="derived-views-picker">
                <span>Synthesized View:</span>
                <select
                  value={selectedDerivedId}
                  onChange={(e) => {
                    setSelectedDerivedId(e.target.value);
                    setRelation('');
                    setPage(1);
                  }}
                >
                  <option value="">Single Sheet View</option>
                  {derivedTables.map((dt) => (
                    <option key={dt.id} value={dt.id}>
                      🔗 {dt.display_name} ({dt.row_count} rows)
                    </option>
                  ))}
                </select>
                {selectedDerivedId && (
                  <button
                    className="btn-secondary"
                    style={{ padding: '0.2rem 0.5rem', fontSize: '0.75rem' }}
                    onClick={() => {
                      setSelectedDerivedId('');
                      setPage(1);
                    }}
                  >
                    Reset
                  </button>
                )}
              </div>
            )}
          </div>

          {selectedDerivedId && activeDerivedTable && (
            <div
              style={{
                background: 'rgba(255, 176, 137, 0.1)',
                border: '1px solid rgba(255, 176, 137, 0.3)',
                borderRadius: '6px',
                padding: '0.6rem 0.9rem',
                marginBottom: '0.75rem',
                fontSize: '0.85rem',
                color: '#fff9f2',
                display: 'flex',
                alignItems: 'center',
                gap: '0.5rem'
              }}
            >
              <GitMerge size={16} color="#ffb089" />
              <span>
                <strong>Synthesized Cross-Sheet View:</strong> {activeDerivedTable.description}
              </span>
            </div>
          )}

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
                selectedDerivedId
                  ? activeDerivedTable?.display_name || 'derived_view'
                  : relation
                  ? 'relational_join'
                  : `${selectedSheet?.display_name || selectedSheet?.original_name || 'table'} [${dataVersion.toUpperCase()}]`
              }
            />
          ) : loading ? (
            <p>Loading table rows...</p>
          ) : null}
        </>
      )}

      {/* VIEW 2: EXPLORATORY DATA ANALYSIS (EDA) REPORT VIEW */}
      {viewMode === 'eda' && (
        <div className="eda-dashboard">
          {loadingEda ? (
            <p>Generating and loading Exploratory Data Analysis report...</p>
          ) : edaReport ? (
            <>
              {/* Card 1: Data Health & Cleanliness Score */}
              <div className="eda-hero-card">
                <div className="eda-score-box">
                  <div
                    className={`score-circle ${
                      edaReport.health_score >= 90
                        ? 'score-excellent'
                        : edaReport.health_score >= 70
                        ? 'score-good'
                        : 'score-attention'
                    }`}
                  >
                    <span>{edaReport.health_score}%</span>
                    <span className="score-label">Health</span>
                  </div>
                  <div className="score-text">
                    <h3>{edaReport.sheet_name}</h3>
                    <p>Cleanliness score derived from missingness, outliers, and normalization hygiene.</p>
                    <span
                      className={`status-badge ${
                        edaReport.health_score >= 90
                          ? 'status-excellent'
                          : edaReport.health_score >= 70
                          ? 'status-good'
                          : 'status-attention'
                      }`}
                    >
                      {edaReport.health_status}
                    </span>
                  </div>
                </div>

                <div className="eda-summary-chips">
                  <div className="summary-chip">
                    <div className="chip-label">Rows Ingested</div>
                    <div className="chip-val">{edaReport.summary.total_rows}</div>
                  </div>
                  <div className="summary-chip">
                    <div className="chip-label">Columns</div>
                    <div className="chip-val">{edaReport.summary.total_columns}</div>
                  </div>
                  <div className="summary-chip">
                    <div className="chip-label">Normalized Cells</div>
                    <div className="chip-val val-accent">{edaReport.summary.total_normalized_cells}</div>
                  </div>
                  <div className="summary-chip">
                    <div className="chip-label">Null Cells</div>
                    <div className="chip-val">{edaReport.summary.total_null_cells}</div>
                  </div>
                  <div className="summary-chip">
                    <div className="chip-label">Anomalies</div>
                    <div className="chip-val val-warning">{edaReport.summary.total_anomalies}</div>
                  </div>
                </div>

                <button
                  className="btn-rerun-eda"
                  onClick={handleRerunEda}
                  disabled={isRerunningEda}
                >
                  {isRerunningEda ? 'Recomputing...' : 'Re-run EDA Pipeline'}
                </button>
              </div>

              {/* Card 2: Recommendations Banner */}
              {edaReport.recommendations && edaReport.recommendations.length > 0 && (
                <div className="eda-recs-card">
                  <h4>
                    <Sparkles size={16} />
                    EDA Analytical Insights & Next Steps
                  </h4>
                  <ul>
                    {edaReport.recommendations.map((rec, idx) => (
                      <li key={idx}>{rec}</li>
                    ))}
                  </ul>
                </div>
              )}

              {/* Card 3: Multi-Sheet Cross-Table Intelligence */}
              <div className="eda-section-card">
                <div className="section-header">
                  <h3>
                    <GitBranch size={18} color="#ffb089" />
                    Multi-Sheet Cross-Table Intelligence & Correlations
                  </h3>
                  <p>
                    Automatic entity matching, foreign key integrity checks, and inter-sheet metric correlations.
                  </p>
                </div>

                {/* Entity Links */}
                {edaReport.cross_sheet_intelligence.entity_links.length > 0 ? (
                  <>
                    <h4 style={{ color: '#c9bdb0', fontSize: '0.85rem', marginBottom: '0.6rem' }}>
                      Discovered Entity Linkages
                    </h4>
                    <div className="eda-links-grid">
                      {edaReport.cross_sheet_intelligence.entity_links.map((link, idx) => (
                        <div key={idx} className="link-tile">
                          <div className="link-title">
                            <span>{link.left_sheet_name}</span>
                            <ArrowRight size={14} color="#a89f94" />
                            <span>{link.right_sheet_name}</span>
                          </div>
                          <div className="link-meta">
                            <span className="badge-pill">
                              {link.left_column} ↔ {link.right_column}
                            </span>
                            <span className="badge-cardinality">{link.cardinality} cardinality</span>
                            <span className="badge-cardinality">{link.matching_keys} matches ({link.coverage_pct}%)</span>
                          </div>
                        </div>
                      ))}
                    </div>
                  </>
                ) : (
                  <p style={{ color: '#a89f94', fontSize: '0.85rem' }}>
                    No cross-sheet links detected for this sheet yet. Upload complementary sheets to activate multi-sheet discovery.
                  </p>
                )}

                {/* Cross-Sheet Correlations */}
                {edaReport.cross_sheet_intelligence.correlations.length > 0 && (
                  <>
                    <h4 style={{ color: '#c9bdb0', fontSize: '0.85rem', marginBottom: '0.6rem', marginTop: '1rem' }}>
                      Cross-Sheet Statistical Correlations ($p &lt; 0.05$)
                    </h4>
                    <div className="eda-correlations-grid">
                      {edaReport.cross_sheet_intelligence.correlations.map((corr, idx) => (
                        <div key={idx} className="correlation-tile">
                          <div className="corr-top-row">
                            <div className="corr-metrics">
                              {corr.left_metric} ↔ {corr.right_metric}
                            </div>
                            <span
                              className={`corr-badge ${
                                corr.direction === 'negative' ? 'negative' : 'positive'
                              }`}
                            >
                              {corr.strength.toUpperCase()} {corr.direction.toUpperCase()} (r = {corr.pearson_r})
                            </span>
                          </div>
                          <div className="corr-sheets-label">
                            {corr.left_sheet_name} vs. {corr.right_sheet_name} · N = {corr.sample_size} entities
                          </div>
                          <div className="corr-narrative">{corr.narrative}</div>
                        </div>
                      ))}
                    </div>
                  </>
                )}

                {/* Derived Tables Shortcut */}
                {edaReport.cross_sheet_intelligence.derived_tables.length > 0 && (
                  <div
                    style={{
                      marginTop: '1.25rem',
                      background: 'rgba(255, 176, 137, 0.08)',
                      border: '1px solid rgba(255, 176, 137, 0.25)',
                      borderRadius: '8px',
                      padding: '0.85rem 1.1rem',
                      display: 'flex',
                      justifyContent: 'space-between',
                      alignItems: 'center',
                      flexWrap: 'wrap',
                      gap: '0.75rem'
                    }}
                  >
                    <div>
                      <strong style={{ color: '#ffb089' }}>Synthesized Derived Tables Available:</strong>
                      <p style={{ margin: '3px 0 0 0', fontSize: '0.82rem', color: '#e5dacd' }}>
                        {edaReport.cross_sheet_intelligence.derived_tables.map((d) => d.display_name).join(', ')}
                      </p>
                    </div>
                    <button
                      className="btn-secondary"
                      onClick={() => {
                        const firstDerived = edaReport.cross_sheet_intelligence.derived_tables[0];
                        if (firstDerived) {
                          setSelectedDerivedId(firstDerived.id);
                          setViewMode('table');
                        }
                      }}
                    >
                      Explore Synthesized Table →
                    </button>
                  </div>
                )}
              </div>

              {/* Card 4: Transformation Audit Trail */}
              <div className="eda-section-card">
                <div className="section-header">
                  <h3>
                    <ShieldCheck size={18} color="#2ed573" />
                    Data Cleaning & Normalization Audit Trail
                  </h3>
                  <p>
                    Source-preserving transformations performed during the EDA phase prior to downstream projection pipelines.
                  </p>
                </div>

                <div className="eda-table-container">
                  <table className="eda-data-grid">
                    <thead>
                      <tr>
                        <th>Target Column</th>
                        <th>Inferred Semantic Type</th>
                        <th>Standardized Format / Unit</th>
                        <th>Cells Coerced</th>
                        <th>Transformation Rule Applied</th>
                      </tr>
                    </thead>
                    <tbody>
                      {edaReport.transformations_log && edaReport.transformations_log.length > 0 ? (
                        edaReport.transformations_log.map((t, idx) => {
                          const diag = edaReport.column_diagnostics[t.column] || {};
                          return (
                            <tr key={idx}>
                              <td>
                                <strong>{t.column}</strong>
                              </td>
                              <td className="type-cell">{t.inferred_type}</td>
                              <td>{diag.unit ? `Unit: ${diag.unit}` : 'Standard numeric / string'}</td>
                              <td className="stat-cell">{t.cells_transformed} cells</td>
                              <td>{t.transformation}</td>
                            </tr>
                          );
                        })
                      ) : (
                        <tr>
                          <td colSpan={5} style={{ textAlign: 'center', color: '#a89f94', padding: '1rem' }}>
                            All column values in this sheet are already in canonical format; no type coercions required.
                          </td>
                        </tr>
                      )}
                    </tbody>
                  </table>
                </div>
              </div>

              {/* Card 5: Column Diagnostics & Outlier Inspector */}
              <div className="eda-section-card">
                <div className="section-header">
                  <h3>
                    <Table size={18} color="#ffb089" />
                    Column Diagnostics & Statistical Distributions
                  </h3>
                  <p>
                    Null distribution, unique cardinality, interquartile range (IQR) bounds, and outlier detection.
                  </p>
                </div>

                <div className="eda-table-container">
                  <table className="eda-data-grid">
                    <thead>
                      <tr>
                        <th>Column Name</th>
                        <th>Type</th>
                        <th>Missing Values</th>
                        <th>Imputation Strategy</th>
                        <th>Distinct Values</th>
                        <th>Distribution (Min / Max / Mean / Median)</th>
                        <th>Outliers Flagged</th>
                      </tr>
                    </thead>
                    <tbody>
                      {Object.values(edaReport.column_diagnostics || {}).map((col, idx) => (
                        <tr key={idx}>
                          <td>
                            <strong>{col.column}</strong>
                          </td>
                          <td className="type-cell">{col.inferred_type}</td>
                          <td className="stat-cell">
                            {col.null_count} ({col.null_percentage}%)
                          </td>
                          <td className="stat-cell">
                            {col.imputation ? (
                              <div style={{ fontSize: "0.82rem", color: "var(--brand-300)" }}>
                                <span style={{ padding: "2px 6px", background: "rgba(99, 102, 241, 0.15)", borderRadius: "4px", fontWeight: 600 }}>
                                  {col.imputation.strategy.toUpperCase()} → {String(col.imputation.recommended_value)}
                                </span>
                                <div style={{ fontSize: "0.74rem", opacity: 0.8, marginTop: "4px", maxWidth: "250px", lineHeight: 1.25 }}>
                                  {col.imputation.rationale}
                                </div>
                              </div>
                            ) : (
                              <span style={{ color: "#2ed573", fontSize: "0.82rem" }}>✓ Complete</span>
                            )}
                          </td>
                          <td className="stat-cell">{col.distinct_count}</td>
                          <td className="stat-cell">
                            {col.min != null
                              ? `${col.min} / ${col.max} · μ: ${col.mean} (med: ${col.median})`
                              : '—'}
                          </td>
                          <td>
                            {col.outlier_count > 0 ? (
                              <span style={{ color: '#ff6b81', fontWeight: 600 }}>
                                ⚠️ {col.outlier_count} outliers (e.g. {col.outliers.map((o) => o.value).join(', ')})
                              </span>
                            ) : (
                              <span style={{ color: '#2ed573' }}>✓ Normal</span>
                            )}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            </>
          ) : (
            <p>Select a sheet to inspect its Exploratory Data Analysis report.</p>
          )}
        </div>
      )}

      {/* VIEW 3: VISUAL PROJECTIONS VIEW */}
      {viewMode === 'projections' && (
        <div className="projections-container">
          {loadingProjections ? (
            <p>Analyzing column projections...</p>
          ) : projectionsData?.projections ? (
            <div className="projections-grid">
              {projectionsData.projections.map((p, idx) => (
                <div key={idx} className="projection-card">
                  <div className="projection-header">
                    <h4>{formatDisplayLabel(p.column)}</h4>
                    <span className="type-badge">{p.type}</span>
                  </div>

                  {p.type === 'categorical' && (
                    <div className="bar-breakdown">
                      {p.categories?.map((c, cIdx) => (
                        <div key={cIdx} className="bar-row">
                          <span className="bar-label">{c.value}</span>
                          <div className="bar-track">
                            <div className="bar-fill" style={{ width: `${c.percentage}%` }} />
                          </div>
                          <span className="bar-count">
                            {c.count} ({c.percentage}%)
                          </span>
                        </div>
                      ))}
                    </div>
                  )}

                  {p.type === 'numeric' && (
                    <div className="numeric-stats">
                      <div className="stat-row">
                        <span>Min:</span> <strong>{fmt(p.min)}</strong>
                      </div>
                      <div className="stat-row">
                        <span>Max:</span> <strong>{fmt(p.max)}</strong>
                      </div>
                      <div className="stat-row">
                        <span>Mean:</span> <strong>{fmt(p.mean)}</strong>
                      </div>
                      <div className="stat-row">
                        <span>Median:</span> <strong>{fmt(p.median)}</strong>
                      </div>
                      <div className="stat-row">
                        <span>Std Dev:</span> <strong>{fmt(p.std)}</strong>
                      </div>
                    </div>
                  )}

                  {p.type === 'timeline' && (
                    <div className="timeline-stats">
                      <div className="stat-row">
                        <span>From:</span> <strong>{p.min_date}</strong>
                      </div>
                      <div className="stat-row">
                        <span>To:</span> <strong>{p.max_date}</strong>
                      </div>
                      <div className="stat-row">
                        <span>Observations:</span> <strong>{p.observations}</strong>
                      </div>
                    </div>
                  )}
                </div>
              ))}
            </div>
          ) : (
            <p>Select a sheet to view projections.</p>
          )}
        </div>
      )}

      {/* VIEW 4: STATISTICAL DIAGNOSTICS & SCHEMA VIEW */}
      {viewMode === 'diagnostics' && (
        <div className="diagnostics-container">
          {loadingDiagnostics ? (
            <p>Loading statistical diagnostics...</p>
          ) : diagnosticsData ? (
            <div className="diagnostics-content">
              {/* Section A: Statistical Heatmap Matrix */}
              {matrix?.matrix?.length > 0 && (
                <div className="card-panel" style={{ marginBottom: '1.5rem' }}>
                  <div className="section-title-row">
                    <div>
                      <h3 style={{ margin: 0, color: '#f8fafc' }}>
                        Statistical Correlation & Association Matrix
                      </h3>
                      <p className="subtitle" style={{ margin: '4px 0 0 0' }}>
                        Pearson correlation for numeric metrics; Cramér's V for categorical dimensions.
                      </p>
                    </div>
                  </div>

                  <div style={{ marginTop: '1rem' }}>
                    <ExecutiveHeatmapChart
                      matrix={matrix.matrix}
                      columns={matrix.columns}
                      onCellClick={(cell) => setSelectedMatrixCell(cell)}
                    />
                  </div>

                  {selectedMatrixCell && (
                    <div
                      style={{
                        marginTop: '1rem',
                        padding: '0.85rem',
                        borderRadius: '6px',
                        background: 'rgba(255, 255, 255, 0.05)',
                        border: '1px solid var(--border)'
                      }}
                    >
                      <h4 style={{ margin: '0 0 0.5rem 0', color: 'var(--accent)' }}>
                        Association Insight: {selectedMatrixCell.x} ↔ {selectedMatrixCell.y}
                      </h4>
                      <p style={{ margin: 0, fontSize: '0.9rem' }}>
                        Coefficient value: <strong>{selectedMatrixCell.value}</strong> ({selectedMatrixCell.metric_type}).
                      </p>
                    </div>
                  )}
                </div>
              )}

              {/* Section B: Column Profiles & Missing Values */}
              <div className="card-panel" style={{ marginBottom: '1.5rem' }}>
                <div className="section-title-row" style={{ marginBottom: '1rem' }}>
                  <div>
                    <h3 style={{ margin: 0, color: '#f8fafc' }}>Column Profiles & Schema Attributes</h3>
                    <p className="subtitle" style={{ margin: '4px 0 0 0' }}>
                      Detailed missingness counts, cardinality, and data types.
                    </p>
                  </div>
                </div>

                <div className="evidence-table-wrap">
                  <table className="evidence-table" style={{ width: '100%' }}>
                    <thead>
                      <tr>
                        <th>Column Name</th>
                        <th>Inferred Type</th>
                        <th>Missingness</th>
                        <th>Distinct Values</th>
                        <th>Summary Stats</th>
                      </tr>
                    </thead>
                    <tbody>
                      {diagProfile?.column_details?.map((c, idx) => (
                        <tr key={idx}>
                          <td>
                            <strong>{c.column_name}</strong>
                          </td>
                          <td>
                            <span className="type-badge">{c.inferred_type}</span>
                          </td>
                          <td>
                            {c.missing_count} ({c.missing_percentage}%)
                          </td>
                          <td>{c.distinct_count}</td>
                          <td>
                            {c.min != null
                              ? `Min: ${c.min}, Max: ${c.max}, Mean: ${c.mean}`
                              : 'Categorical / ID'}
                          </td>
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
