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
  runEdaPipeline,
  listDatasets,
  deleteDataset,
  bulkDeleteDatasets,
  deleteAllDatasets
} from '../api/client';
import { formatDisplayLabel } from '../utils/displayFormatters';
import DataTable from '../components/DataTable';
import DatasetListCard from '../components/ingestion/DatasetListCard';
import DeleteConsentModal from '../components/ingestion/DeleteConsentModal';
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
  ArrowRight,
  Trash2,
  CheckSquare,
  Square
} from 'lucide-react';
import VisualEdaDashboard from '../components/eda/VisualEdaDashboard';

const fmt = (n) => (n == null ? 'Unavailable' : Number(n).toLocaleString(undefined, { maximumFractionDigits: 2 }));

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

  // View Modes: 'table' | 'eda' (Column Projections and Diagnostics unified into EDA)
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

  // Workspace Datasets & Deletion State
  const [datasets, setDatasets] = useState([]);
  const [selectedDatasetIds, setSelectedDatasetIds] = useState([]);
  const [datasetToDelete, setDatasetToDelete] = useState(null);
  const [deleteConsent, setDeleteConsent] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [showDatasetManager, setShowDatasetManager] = useState(true);

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

  const handleToggleSelectDataset = (id) => {
    setSelectedDatasetIds((prev) =>
      prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id]
    );
  };

  const handleToggleSelectAll = () => {
    if (selectedDatasetIds.length === datasets.length) {
      setSelectedDatasetIds([]);
    } else {
      setSelectedDatasetIds(datasets.map((d) => d.id));
    }
  };

  const handlePromptSingleDelete = (dataset) => {
    setDatasetToDelete(dataset);
    setDeleteConsent(false);
  };

  const handlePromptBulkDelete = () => {
    const targets = datasets.filter((d) => selectedDatasetIds.includes(d.id));
    if (!targets.length) return;
    setDatasetToDelete({ isBulk: true, isAll: false, datasets: targets });
    setDeleteConsent(false);
  };

  const handlePromptDeleteAll = () => {
    if (!datasets.length) return;
    setDatasetToDelete({ isBulk: true, isAll: true, datasets });
    setDeleteConsent(false);
  };

  const handleConfirmDelete = async () => {
    if (!datasetToDelete || !deleteConsent || deleting) return;
    setDeleting(true);
    try {
      if (datasetToDelete.isBulk) {
        if (datasetToDelete.isAll) {
          await deleteAllDatasets();
        } else {
          await bulkDeleteDatasets(datasetToDelete.datasets.map((d) => d.id));
        }
      } else {
        await deleteDataset(datasetToDelete.id);
      }

      const deletedIds = datasetToDelete.isBulk
        ? datasetToDelete.datasets.map((d) => d.id)
        : [datasetToDelete.id];

      setSelectedDatasetIds((prev) => prev.filter((id) => !deletedIds.includes(id)));
      setDatasetToDelete(null);
      setDeleteConsent(false);
      refresh();

      if (deletedIds.includes(Number(selectedSheet?.dataset_id))) {
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
            🔬 Exploratory Data Analysis & Predictive Analytics
          </button>
        </div>
      </div>

      {/* Workspace Datasets Registry & Management Panel */}
      <div className="card-panel datasets-workspace-manager" style={{ marginTop: '0.75rem', marginBottom: '1.25rem' }}>
        <div
          className="panel-header"
          style={{
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            flexWrap: 'wrap',
            gap: '0.75rem'
          }}
        >
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <Layers size={18} color="var(--brand-400)" />
              <h3 style={{ margin: 0, fontSize: '1.05rem', color: 'var(--fg-primary)' }}>
                Workspace Datasets ({datasets.length})
              </h3>
            </div>
            <p className="panel-sub" style={{ margin: '2px 0 0', fontSize: '0.8rem', color: 'var(--fg-secondary)' }}>
              Manage uploaded CSV & Excel workbooks, download sources, and execute single or bulk dataset deletion.
            </p>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', flexWrap: 'wrap' }}>
            {selectedDatasetIds.length > 0 && (
              <button
                type="button"
                className="btn-danger-confirm"
                style={{
                  padding: '0.4rem 0.8rem',
                  fontSize: '0.8rem',
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: '6px'
                }}
                onClick={handlePromptBulkDelete}
              >
                <Trash2 size={14} />
                <span>Delete Selected ({selectedDatasetIds.length})</span>
              </button>
            )}

            {datasets.length > 0 && (
              <button
                type="button"
                className="btn-secondary"
                style={{
                  padding: '0.4rem 0.8rem',
                  fontSize: '0.8rem',
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: '6px',
                  color: 'var(--rose-tier)',
                  borderColor: 'rgba(255, 180, 190, 0.3)'
                }}
                onClick={handlePromptDeleteAll}
              >
                <Trash2 size={14} />
                <span>Delete All</span>
              </button>
            )}

            <button
              type="button"
              className="btn-secondary"
              style={{ padding: '0.4rem 0.75rem', fontSize: '0.8rem' }}
              onClick={() => setShowDatasetManager((prev) => !prev)}
            >
              {showDatasetManager ? 'Collapse Files ▲' : `View Files (${datasets.length}) ▼`}
            </button>
          </div>
        </div>

        {showDatasetManager && (
          <div style={{ marginTop: '1rem' }}>
            {datasets.length > 1 && (
              <div
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  padding: '0.5rem 0.75rem',
                  background: 'rgba(255, 255, 255, 0.02)',
                  border: '1px solid var(--border-subtle)',
                  borderRadius: '6px',
                  marginBottom: '0.75rem',
                  fontSize: '0.8rem'
                }}
              >
                <label style={{ display: 'flex', alignItems: 'center', gap: '8px', cursor: 'pointer', userSelect: 'none' }}>
                  <input
                    type="checkbox"
                    checked={datasets.length > 0 && selectedDatasetIds.length === datasets.length}
                    onChange={handleToggleSelectAll}
                    style={{ width: '16px', height: '16px', cursor: 'pointer', accentColor: '#f43f5e' }}
                  />
                  <span>Select All ({datasets.length} files)</span>
                </label>
                {selectedDatasetIds.length > 0 && (
                  <span style={{ color: 'var(--fg-muted)' }}>
                    {selectedDatasetIds.length} of {datasets.length} selected
                  </span>
                )}
              </div>
            )}

            {datasets.length === 0 ? (
              <p style={{ color: 'var(--fg-muted)', fontSize: '0.85rem', margin: '0.5rem 0' }}>
                No datasets currently in workspace. Use the &ldquo;Upload Data&rdquo; button in the top right to upload a CSV or Excel spreadsheet.
              </p>
            ) : (
              <div className="dataset-list">
                {datasets.map((ds) => (
                  <DatasetListCard
                    key={ds.id}
                    dataset={ds}
                    onPromptDelete={handlePromptSingleDelete}
                    isSelected={selectedDatasetIds.includes(ds.id)}
                    onToggleSelect={handleToggleSelectDataset}
                  />
                ))}
              </div>
            )}
          </div>
        )}
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

        {selectedSheet && !selectedDerivedId && (
          <button
            type="button"
            className="btn-secondary"
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: '6px',
              color: 'var(--rose-tier)',
              borderColor: 'rgba(255, 180, 190, 0.3)',
              background: 'rgba(255, 180, 190, 0.08)',
              padding: '0.4rem 0.75rem',
              cursor: 'pointer'
            }}
            onClick={() => {
              const ds = datasets.find((d) => d.id === selectedSheet.dataset_id);
              if (ds) {
                handlePromptSingleDelete(ds);
              } else {
                handlePromptSingleDelete({
                  id: selectedSheet.dataset_id,
                  original_name: selectedSheet.original_name || selectedSheet.display_name || 'Selected Dataset',
                  row_count: selectedSheet.row_count,
                  file_type: 'csv',
                  sheet_count: 1
                });
              }
            }}
            title={`Delete dataset for '${selectedSheet.display_name || selectedSheet.name}'`}
          >
            <Trash2 size={14} color="var(--rose-tier)" />
            <span>Delete Sheet</span>
          </button>
        )}

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

      {/* Consent Check Modal for Single or Bulk Deletion */}
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
