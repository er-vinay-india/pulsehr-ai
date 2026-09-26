import React, { useEffect, useState } from 'react';
import {
  getSheets,
  getSheetRows,
  getJoinedRows,
  getSheetEdaReport,
  getDerivedTables,
  getDerivedTableRows,
  getCrossSheetCorrelations,
  runEdaPipeline,
  listDatasets,
  deleteDataset,
  getDatasetDownloadUrl
} from '../api/client';
import DataTable from '../components/DataTable';
import DeleteConsentModal from '../components/ingestion/DeleteConsentModal';
import {
  FileSpreadsheet,
  Download,
  Trash2,
  GitMerge,
  Search,
  Layers,
  ChevronDown
} from 'lucide-react';
import VisualEdaDashboard from '../components/eda/VisualEdaDashboard';

export default function DataExplorerPage() {
  const [catalog, setCatalog] = useState({ sheets: [], relationships: [] });
  const [selected, setSelected] = useState(() => {
    const params = new URLSearchParams(window.location.search);
    return params.get('sheet_id') || '';
  });
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

  // View Modes: 'table' | 'eda'
  const [viewMode, setViewMode] = useState(() => {
    const params = new URLSearchParams(window.location.search);
    const v = params.get('view');
    return v === 'eda' || v === 'projections' || v === 'diagnostics' ? 'eda' : 'table';
  });

  // EDA State
  const [edaReport, setEdaReport] = useState(null);
  const [loadingEda, setLoadingEda] = useState(false);
  const [isRerunningEda, setIsRerunningEda] = useState(false);
  const [crossCorrelations, setCrossCorrelations] = useState([]);

  // Minimal Workspace Datasets & Deletion State
  const [datasets, setDatasets] = useState([]);
  const [datasetToDelete, setDatasetToDelete] = useState(null);
  const [deleteConsent, setDeleteConsent] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [showWorkspaceDrawer, setShowWorkspaceDrawer] = useState(false);

  const refresh = () => {
    getSheets()
      .then((r) => {
        setCatalog(r);
        setSelected((current) => {
          const params = new URLSearchParams(window.location.search);
          const urlSheet = params.get('sheet_id');
          if (urlSheet && r.sheets.some((s) => String(s.id) === urlSheet)) {
            return urlSheet;
          }
          return r.sheets.some((s) => String(s.id) === current)
            ? current
            : String(r.sheets[r.sheets.length - 1]?.id || '');
        });
        setRelation('');
        setPage(1);
      })
      .catch((e) => setError(e.message));

    listDatasets()
      .then((res) => {
        setDatasets(res.datasets || []);
      })
      .catch(() => {});

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

  const handlePromptSingleDelete = (dataset) => {
    if (!dataset) return;
    setDatasetToDelete(dataset);
    setDeleteConsent(false);
  };

  const handleConfirmDelete = async () => {
    if (!datasetToDelete || !deleteConsent || deleting) return;
    setDeleting(true);
    try {
      await deleteDataset(datasetToDelete.id);
      const deletedDatasetId = datasetToDelete.id;
      setDatasetToDelete(null);
      setDeleteConsent(false);
      refresh();

      if (selectedSheet && Number(selectedSheet.dataset_id) === Number(deletedDatasetId)) {
        setSelected('');
      }
    } catch (err) {
      setError('Failed to delete dataset: ' + err.message);
    } finally {
      setDeleting(false);
    }
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
  const activeDataset = datasets.find((d) => d.id === selectedSheet?.dataset_id);
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

  return (
    <div className="explorer-page">
      {/* 1. Header & Primary View Mode Pill Switcher */}
      <div
        className="explorer-hero-bar"
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          flexWrap: 'wrap',
          gap: '1rem',
          marginBottom: '1rem'
        }}
      >
        <div>
          <h2 style={{ fontSize: '1.5rem', margin: 0, letterSpacing: '-0.025em' }}>Data Explorer & Workbench</h2>
          <p className="subtitle" style={{ margin: '4px 0 0', fontSize: '0.85rem' }}>
            Dual-version tabular inspection (Raw vs. Post-EDA Curated), correlation discovery, and predictive analytics.
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
            🔬 Exploratory Data Analysis & Predictive Analytics
          </button>
        </div>
      </div>

      {/* 2. Unified, Compact Command & Filter Bar */}
      <div
        className="explorer-compact-toolbar"
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          flexWrap: 'wrap',
          gap: '0.75rem',
          background: 'var(--surface-card)',
          border: '1px solid var(--border)',
          borderRadius: '12px',
          padding: '0.65rem 1rem',
          marginBottom: '1.25rem'
        }}
      >
        {/* Left Controls: Sheet, Derived View, Table Version, Search */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.65rem', flexWrap: 'wrap', flex: 1, minWidth: 0 }}>
          {/* Sheet Selector */}
          <div
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: '6px',
              background: 'var(--surface-inset)',
              border: '1px solid var(--border-subtle)',
              borderRadius: '8px',
              padding: '0 8px',
              minHeight: '38px'
            }}
          >
            <FileSpreadsheet size={16} color="var(--brand-400)" style={{ flexShrink: 0 }} />
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
              style={{
                background: 'transparent',
                border: 'none',
                color: 'var(--fg-primary)',
                fontSize: '0.85rem',
                minHeight: '36px',
                padding: '0 4px',
                cursor: 'pointer'
              }}
            >
              <option value="">Select a sheet...</option>
              {catalog.sheets.map((s) => (
                <option key={s.id} value={s.id}>
                  {s.display_name || s.original_name}{' '}
                  {s.name && s.name !== 'Sheet1' ? `· ${s.name}` : ''} ({s.row_count} rows)
                </option>
              ))}
            </select>
          </div>

          {/* Derived Views Dropdown (if present) */}
          {derivedTables.length > 0 && (
            <div
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: '6px',
                background: 'var(--surface-inset)',
                border: '1px solid var(--border-subtle)',
                borderRadius: '8px',
                padding: '0 8px',
                minHeight: '38px'
              }}
            >
              <GitMerge size={14} color="#ffb089" style={{ flexShrink: 0 }} />
              <select
                value={selectedDerivedId}
                onChange={(e) => {
                  setSelectedDerivedId(e.target.value);
                  setRelation('');
                  setPage(1);
                }}
                style={{
                  background: 'transparent',
                  border: 'none',
                  color: 'var(--fg-primary)',
                  fontSize: '0.82rem',
                  minHeight: '36px',
                  padding: '0 4px',
                  cursor: 'pointer'
                }}
              >
                <option value="">Single Sheet</option>
                {derivedTables.map((dt) => (
                  <option key={dt.id} value={dt.id}>
                    🔗 {dt.display_name} ({dt.row_count} rows)
                  </option>
                ))}
              </select>
            </div>
          )}

          {/* Table-specific Mode Controls: Version Pill + Search */}
          {viewMode === 'table' && !selectedDerivedId && (
            <>
              <div
                className="version-pill-group"
                style={{
                  display: 'inline-flex',
                  background: 'rgba(0, 0, 0, 0.25)',
                  border: '1px solid var(--border-subtle)',
                  borderRadius: '7px',
                  padding: '2px',
                  gap: '2px'
                }}
              >
                <button
                  type="button"
                  className={`version-pill ${dataVersion === 'curated' ? 'active' : ''}`}
                  onClick={() => {
                    setDataVersion('curated');
                    setPage(1);
                  }}
                  style={{
                    padding: '4px 10px',
                    fontSize: '0.78rem',
                    border: 'none',
                    borderRadius: '5px',
                    background: dataVersion === 'curated' ? 'var(--brand-500)' : 'transparent',
                    color: dataVersion === 'curated' ? '#100e0c' : 'var(--fg-secondary)',
                    fontWeight: 600,
                    cursor: 'pointer'
                  }}
                >
                  ✨ Curated
                </button>
                <button
                  type="button"
                  className={`version-pill ${dataVersion === 'raw' ? 'active' : ''}`}
                  onClick={() => {
                    setDataVersion('raw');
                    setPage(1);
                  }}
                  style={{
                    padding: '4px 10px',
                    fontSize: '0.78rem',
                    border: 'none',
                    borderRadius: '5px',
                    background: dataVersion === 'raw' ? 'var(--brand-500)' : 'transparent',
                    color: dataVersion === 'raw' ? '#100e0c' : 'var(--fg-secondary)',
                    fontWeight: 600,
                    cursor: 'pointer'
                  }}
                >
                  📋 Raw
                </button>
              </div>

              {/* Table Search Input */}
              <div
                style={{
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: '6px',
                  background: 'var(--surface-inset)',
                  border: '1px solid var(--border-subtle)',
                  borderRadius: '8px',
                  padding: '0 8px',
                  minHeight: '38px',
                  flex: '1 1 140px',
                  maxWidth: '220px'
                }}
              >
                <Search size={14} color="var(--fg-muted)" />
                <input
                  type="text"
                  placeholder="Filter rows..."
                  value={search}
                  onChange={(e) => {
                    setSearch(e.target.value);
                    setPage(1);
                  }}
                  style={{
                    background: 'transparent',
                    border: 'none',
                    color: 'var(--fg-primary)',
                    fontSize: '0.82rem',
                    padding: '0',
                    minHeight: 'auto',
                    width: '100%'
                  }}
                />
              </div>
            </>
          )}
        </div>

        {/* Right Actions: Minimal Workspace Overview, Download, Minimal Delete */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', flexShrink: 0 }}>
          {/* Minimal Workspace Files Indicator / Popover Toggle */}
          {datasets.length > 0 && (
            <div style={{ position: 'relative' }}>
              <button
                type="button"
                className="btn-secondary"
                onClick={() => setShowWorkspaceDrawer((prev) => !prev)}
                style={{
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: '5px',
                  padding: '0.35rem 0.65rem',
                  fontSize: '0.78rem',
                  minHeight: '34px',
                  borderRadius: '8px'
                }}
                title="View workbooks currently in workspace"
              >
                <Layers size={13} color="var(--brand-400)" />
                <span>{datasets.length} Workbook{datasets.length > 1 ? 's' : ''}</span>
                <ChevronDown size={12} style={{ transform: showWorkspaceDrawer ? 'rotate(180deg)' : 'none', transition: 'transform 0.2s' }} />
              </button>

              {/* Compact Workspace Dropdown Menu */}
              {showWorkspaceDrawer && (
                <div
                  style={{
                    position: 'absolute',
                    top: 'calc(100% + 6px)',
                    right: 0,
                    zIndex: 100,
                    width: '320px',
                    background: '#1c1815',
                    border: '1px solid var(--border)',
                    borderRadius: '10px',
                    padding: '0.75rem',
                    boxShadow: '0 8px 24px rgba(0,0,0,0.5)',
                    fontSize: '0.82rem'
                  }}
                >
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px', paddingBottom: '6px', borderBottom: '1px solid var(--border-subtle)' }}>
                    <strong style={{ color: '#fff9f2', fontSize: '0.8rem' }}>Workspace Workbooks</strong>
                    <span style={{ fontSize: '0.72rem', color: 'var(--fg-muted)' }}>{datasets.length} file(s)</span>
                  </div>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '6px', maxHeight: '200px', overflowY: 'auto' }}>
                    {datasets.map((d) => (
                      <div
                        key={d.id}
                        style={{
                          display: 'flex',
                          alignItems: 'center',
                          justifyContent: 'space-between',
                          gap: '8px',
                          padding: '6px 8px',
                          borderRadius: '6px',
                          background: d.id === selectedSheet?.dataset_id ? 'rgba(255, 176, 137, 0.08)' : 'transparent',
                          border: d.id === selectedSheet?.dataset_id ? '1px solid rgba(255, 176, 137, 0.25)' : '1px solid transparent'
                        }}
                      >
                        <div style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                          <div style={{ fontWeight: 600, color: '#fff9f2', fontSize: '0.8rem' }}>{d.original_name}</div>
                          <div style={{ fontSize: '0.72rem', color: 'var(--fg-muted)' }}>{d.row_count} rows · {d.sheet_count} sheet(s)</div>
                        </div>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '4px', flexShrink: 0 }}>
                          <a
                            href={getDatasetDownloadUrl(d.id)}
                            download={d.original_name}
                            className="btn-icon-subtle"
                            title="Download workbook"
                            style={{ color: 'var(--fg-secondary)', padding: '4px', display: 'flex' }}
                          >
                            <Download size={13} />
                          </a>
                          <button
                            type="button"
                            onClick={() => {
                              setShowWorkspaceDrawer(false);
                              handlePromptSingleDelete(d);
                            }}
                            className="btn-icon-subtle"
                            title="Delete this workbook"
                            style={{ color: 'var(--rose-tier)', padding: '4px', display: 'flex', background: 'none', border: 'none', cursor: 'pointer' }}
                          >
                            <Trash2 size={13} />
                          </button>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}

          {/* Download Active Workbook */}
          {activeDataset && (
            <a
              href={getDatasetDownloadUrl(activeDataset.id)}
              download={activeDataset.original_name}
              className="btn-secondary"
              title="Download active spreadsheet file"
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: '5px',
                padding: '0.35rem 0.65rem',
                fontSize: '0.78rem',
                minHeight: '34px',
                borderRadius: '8px',
                textDecoration: 'none'
              }}
            >
              <Download size={13} />
              <span>Download</span>
            </a>
          )}

          {/* Minimal Delete Button: Discrete & Non-Intrusive */}
          {selectedSheet && (
            <button
              type="button"
              className="btn-minimal-delete"
              onClick={() => {
                const target = activeDataset || {
                  id: selectedSheet.dataset_id,
                  original_name: selectedSheet.original_name || selectedSheet.display_name || 'Selected Dataset',
                  row_count: selectedSheet.row_count,
                  sheet_count: 1
                };
                handlePromptSingleDelete(target);
              }}
              title="Delete active dataset from workspace"
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: '5px',
                padding: '0.35rem 0.65rem',
                fontSize: '0.78rem',
                minHeight: '34px',
                borderRadius: '8px',
                background: 'rgba(255, 107, 129, 0.08)',
                border: '1px solid rgba(255, 107, 129, 0.25)',
                color: 'var(--rose-tier)',
                cursor: 'pointer',
                transition: 'all 0.2s ease'
              }}
            >
              <Trash2 size={13} />
              <span>Delete</span>
            </button>
          )}
        </div>
      </div>

      {error && (
        <div className="alert-box alert-error" style={{ marginBottom: '1rem' }}>
          <span>{error}</span>
        </div>
      )}

      {/* VIEW 1: DATA TABLE INSPECTION */}
      {viewMode === 'table' && (
        <>
          {selectedDerivedId && activeDerivedTable && (
            <div
              style={{
                background: 'rgba(255, 176, 137, 0.1)',
                border: '1px solid rgba(255, 176, 137, 0.3)',
                borderRadius: '8px',
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

      {/* VIEW 2: EXPLORATORY DATA ANALYSIS (EDA) & PREDICTIVE ANALYTICS SUITE */}
      {viewMode === 'eda' && (
        <VisualEdaDashboard
          edaReport={edaReport}
          loadingEda={loadingEda}
          isRerunningEda={isRerunningEda}
          onRerunEda={handleRerunEda}
          onExploreDerivedTable={(derivedId) => {
            setSelectedDerivedId(derivedId);
            setViewMode('table');
          }}
        />
      )}

      {/* Safe Consent Check Modal for Dataset Deletion */}
      <DeleteConsentModal
        datasetToDelete={datasetToDelete}
        deleteConsent={deleteConsent}
        setDeleteConsent={setDeleteConsent}
        deleting={deleting}
        onClose={() => setDatasetToDelete(null)}
        onConfirmDelete={handleConfirmDelete}
      />
    </div>
  );
}
