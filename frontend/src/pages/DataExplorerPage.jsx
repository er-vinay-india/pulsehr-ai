import React, { useEffect, useState, useMemo } from 'react';
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
  bulkDeleteDatasets,
  getDatasetDownloadUrl
} from '../api/client';
import DataTable from '../components/DataTable';
import DeleteConsentModal from '../components/ingestion/DeleteConsentModal';
import EnrichmentReviewCard from '../components/ingestion/EnrichmentReviewCard';
import DataCompletenessChips from '../components/eda/DataCompletenessChips';
import {
  FileSpreadsheet,
  Download,
  Trash2,
  GitMerge,
  Search,
  Layers,
  ChevronDown,
  ChevronUp,
  Sparkles
} from 'lucide-react';
import VisualEdaDashboard from '../components/eda/VisualEdaDashboard';
import Select from '../components/common/Select';
import Popover from '../components/common/Popover';

export default function DataExplorerPage() {
  const [catalog, setCatalog] = useState({ sheets: [], relationships: [] });
  const [showEnrichmentReview, setShowEnrichmentReview] = useState(false);
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
  const [selectedWorkbookIds, setSelectedWorkbookIds] = useState([]);
  const [catalogLoading, setCatalogLoading] = useState(true);
  const [catalogLoaded, setCatalogLoaded] = useState(false);
  const [deleteError, setDeleteError] = useState('');
  const [notice, setNotice] = useState('');


  const refresh = async () => {
    setCatalogLoading(true);
    try {
      const [sheets, workbooks, derived, correlations] = await Promise.all([
        getSheets(), listDatasets(), getDerivedTables(), getCrossSheetCorrelations()
      ]);
      setError('');
      setCatalog(sheets);
      setDatasets(workbooks.datasets || []);
      setDerivedTables(derived.derived_tables || []);
      setCrossCorrelations(correlations.correlations || []);
      setSelectedWorkbookIds(ids => ids.filter(id => (workbooks.datasets || []).some(d => d.id === id)));
      setSelected(current => {
        const params = new URLSearchParams(window.location.search);
        const urlSheet = params.get('sheet_id');
        const next = sheets.sheets.some(s => String(s.id) === current) ? current
          : sheets.sheets.some(s => String(s.id) === urlSheet) ? urlSheet
          : String(sheets.sheets[sheets.sheets.length - 1]?.id || '');
        if (next) params.set('sheet_id', next); else params.delete('sheet_id');
        window.history.replaceState(null, '', `${window.location.pathname}${params.size ? '?' + params : ''}${window.location.hash}`);
        return next;
      });
      setSelectedDerivedId(current => (derived.derived_tables || []).some(d => String(d.id) === current) ? current : '');
      setRelation('');
      setPage(1);
      setCatalogLoaded(true);
      return true;
    } catch (err) {
      setError(`Could not refresh workbooks. ${err.message}`);
      return false;
    } finally {
      setCatalogLoading(false);
    }
  };

  const handlePromptSingleDelete = dataset => {
    if (!dataset) return;
    setDatasetToDelete(dataset);
    setDeleteConsent(false);
    setDeleteError('');
  };

  const handlePromptBulkDelete = () => {
    const targets = datasets.filter(d => selectedWorkbookIds.includes(d.id));
    if (!targets.length) return;
    setShowWorkspaceDrawer(false);
    setDatasetToDelete({ isBulk: true, datasets: targets });
    setDeleteConsent(false);
    setDeleteError('');
  };

  const handleConfirmDelete = async () => {
    if (!datasetToDelete || !deleteConsent || deleting) return;
    setDeleting(true);
    setDeleteError('');
    try {
      const result = datasetToDelete.isBulk
        ? await bulkDeleteDatasets(datasetToDelete.datasets.map(d => d.id))
        : await deleteDataset(datasetToDelete.id);
      const params = new URLSearchParams(window.location.search);
      params.delete('sheet_id'); params.delete('derived_id');
      window.history.replaceState(null, '', `${window.location.pathname}${params.size ? '?' + params : ''}${window.location.hash}`);
      setSelected(''); setSelectedDerivedId(''); setRelation('');
      setData(null); setEdaReport(null); setCrossCorrelations([]);
      setSearch(''); setPage(1); setLoading(false); setLoadingEda(false);
      setShowEnrichmentReview(false); setError('');
      window.dispatchEvent(new CustomEvent('workbooks-deleted', { detail: result }));
      if (result.cleanup_pending) {
        setDatasetToDelete(current => ({ ...current, cleanupPending: true }));
        setDeleteError('The workbooks are removed from the workspace, but stored file cleanup is incomplete. Retry cleanup to finish.');
      } else {
        setDatasetToDelete(null); setDeleteConsent(false);
        setNotice('Workbooks deleted. Their sheets, generated tables, saved presentations and stored files have been cleaned up.');
      }
      await refresh();
    } catch (err) {
      setDeleteError(err.message);
    } finally {
      setDeleting(false);
    }
  };

  useEffect(() => { refresh(); }, []);

  // Fetch Table Rows (Supports Curated, Raw, Joined, or Derived)
  useEffect(() => {
    if (!catalogLoaded || (!selected && !selectedDerivedId)) {
      setLoading(false);
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
  }, [selected, selectedDerivedId, relation, page, search, viewMode, dataVersion, catalogLoaded]);

  // Fetch EDA Report when in 'eda' mode or when selected sheet changes
  useEffect(() => {
    if (!catalogLoaded || !selected) { setEdaReport(null); setLoadingEda(false); return; }

    let active = true;
    if (viewMode === 'eda') setLoadingEda(true);

    getSheetEdaReport(selected)
      .then(async (rep) => {
        if (!active) return;
        setEdaReport(rep);
        // Lazy analysis can rebuild generated views after source deletion.
        const [derived, correlations] = await Promise.all([getDerivedTables(), getCrossSheetCorrelations()]);
        if (active) {
          setDerivedTables(derived.derived_tables || []);
          setCrossCorrelations(correlations.correlations || []);
        }
      })
      .catch((err) => {
        if (active) { setEdaReport(null); setError(`Could not load sheet analysis. ${err.message}`); }
      })
      .finally(() => {
        if (active) setLoadingEda(false);
      });

    return () => {
      active = false;
    };
  }, [selected, viewMode, catalogLoaded]);

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
  const activeDataset = datasets.find((d) => Number(d.id) === Number(selectedSheet?.dataset_id));
  const enrichment = activeDataset?.enrichment;
  const derivedFeatCount = enrichment?.derived_features_count || enrichment?.derived_features?.length || 0;
  const link = catalog.relationships.find((r) => String(r.id) === relation);
  const left = catalog.sheets.find((s) => s.id === link?.left_sheet);
  const right = catalog.sheets.find((s) => s.id === link?.right_sheet);

  // Compute comprehensive completeness, missing values, and data type breakdown metrics
  const dataHealth = useMemo(() => {
    if (!selectedSheet) return null;

    const summary = edaReport?.summary;
    const profiles = selectedSheet.profiles || [];
    const colDiags = edaReport?.column_diagnostics || {};

    const totalRows = summary?.total_rows ?? selectedSheet.row_count ?? 0;
    const totalCols = summary?.total_columns ?? selectedSheet.columns?.length ?? 0;
    const totalCells = summary?.total_cells ?? ((totalRows * totalCols) || 1);

    // Total missing / null cells
    const totalNullCells = summary?.total_null_cells ?? selectedSheet.completeness?.total_missing ?? profiles.reduce((acc, p) => acc + (p.missing || 0), 0);
    const nullPct = summary?.null_cells_pct ?? (totalCells > 0 ? Number(((totalNullCells / totalCells) * 100).toFixed(1)) : 0);
    const completenessPct = summary?.completeness_pct ?? (totalCells > 0 ? Number((100 - nullPct).toFixed(1)) : 100);

    // Incomplete rows count
    const incompleteRows = summary?.incomplete_rows_count ?? (profiles.length > 0 ? Math.min(totalRows, Math.max(...profiles.map(p => p.missing || 0), 0)) : 0);
    const incompleteRowsPct = summary?.incomplete_rows_pct ?? (totalRows > 0 ? Number(((incompleteRows / totalRows) * 100).toFixed(1)) : 0);

    // Columns with missing values
    let colsWithNulls = summary?.columns_with_nulls;
    if (!colsWithNulls || colsWithNulls.length === 0) {
      if (Object.keys(colDiags).length > 0) {
        colsWithNulls = Object.values(colDiags)
          .filter(d => (d.null_count || 0) > 0)
          .map(d => ({
            column: d.column,
            null_count: d.null_count,
            null_percentage: d.null_percentage,
            inferred_type: d.inferred_type
          }));
      } else {
        colsWithNulls = profiles
          .filter(p => (p.missing || 0) > 0)
          .map(p => ({
            column: p.column,
            null_count: p.missing,
            null_percentage: p.null_percentage,
            inferred_type: p.numeric ? 'numeric' : 'categorical'
          }));
      }
    }

    // Data types breakdown
    let typeBreakdown = summary?.data_types_breakdown;
    if (!typeBreakdown) {
      if (Object.keys(colDiags).length > 0) {
        typeBreakdown = { numeric: 0, categorical: 0, datetime: 0, identifier: 0, boolean: 0 };
        Object.values(colDiags).forEach(d => {
          const t = d.inferred_type || 'categorical';
          if (t.startsWith('numeric')) typeBreakdown.numeric++;
          else if (t.includes('date') || t.includes('time')) typeBreakdown.datetime++;
          else if (t.includes('id')) typeBreakdown.identifier++;
          else typeBreakdown.categorical++;
        });
      } else if (selectedSheet.completeness?.data_types_breakdown) {
        typeBreakdown = selectedSheet.completeness.data_types_breakdown;
      } else {
        const numCount = profiles.filter(p => p.numeric).length;
        const dateCount = profiles.filter(p => /date|time|period|year|month/i.test(p.column)).length;
        typeBreakdown = {
          numeric: numCount,
          categorical: Math.max(0, totalCols - numCount - dateCount),
          datetime: dateCount
        };
      }
    }

    // Column list for detail inspection cards
    const columnList = Object.keys(colDiags).length > 0
      ? Object.values(colDiags)
      : profiles.map(p => ({
          column: p.column,
          inferred_type: p.numeric ? 'numeric' : (/date|time|period|year|month/i.test(p.column) ? 'datetime' : 'categorical'),
          null_count: p.missing || 0,
          null_percentage: p.null_percentage || 0,
          distinct_count: p.distinct
        }));

    const healthScore = edaReport?.health_score ?? (totalNullCells === 0 ? 100 : Math.max(20, Math.round(100 - nullPct * 2)));

    return {
      totalRows,
      totalCols,
      totalCells,
      totalNullCells,
      nullPct,
      completenessPct,
      incompleteRows,
      incompleteRowsPct,
      colsWithNulls: colsWithNulls || [],
      typeBreakdown: typeBreakdown || {},
      healthScore,
      isClean: totalNullCells === 0,
      columnList
    };
  }, [selectedSheet, edaReport]);

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
      {/* Standardized Page Top Section */}
      <header className="page-top-header explorer-page-header">
        <div className="page-title-row">
          <div className="page-title-group">
            <h1 className="page-heading">Data Explorer</h1>
            <p className="page-description">
              Dual-version tabular inspection (Raw vs. Post-EDA Curated), correlation discovery, and predictive analytics.
            </p>
          </div>

          {/* View Mode Toggle */}
          {catalog.sheets.length > 0 && <div className="view-mode-pill-toggle" role="tablist" aria-label="Explorer View Modes">
            <button
              type="button"
              role="tab"
              aria-selected={viewMode === 'table'}
              className={`toggle-btn ${viewMode === 'table' ? 'active' : ''}`}
              onClick={() => setViewMode('table')}
            >
              <span className="explorer-mode-long">📋 Data Table</span>
              <span className="explorer-mode-short">Data Table</span>
            </button>
            <button
              type="button"
              role="tab"
              aria-selected={viewMode === 'eda'}
              className={`toggle-btn ${viewMode === 'eda' ? 'active' : ''}`}
              onClick={() => setViewMode('eda')}
            >
              <span className="explorer-mode-long">🔬 Exploratory Data Analysis & Predictive Analytics</span>
              <span className="explorer-mode-short">Insights & Trends</span>
            </button>
          </div>}
        </div>

        {/* Unified Command & Filter Toolbar */}
        {catalog.sheets.length > 0 && <div className="explorer-compact-toolbar page-command-bar">
        {/* Left Controls: Sheet, Derived View, Table Version, Search */}
        <div className="explorer-toolbar-left" style={{ display: 'flex', alignItems: 'center', gap: '0.65rem', flexWrap: 'wrap', flex: 1, minWidth: 0 }}>
          {/* Sheet Selector */}
          <Select
            value={selected}
            disabled={!!selectedDerivedId}
            aria-label="Select spreadsheet sheet"
            placeholder="Select a sheet..."
            icon={<FileSpreadsheet size={16} color="var(--brand-400)" />}
            options={[
              { value: "", label: "Select a sheet..." },
              ...catalog.sheets.map((s) => ({
                value: s.id,
                label: `${s.display_name || s.original_name}${s.name && s.name !== 'Sheet1' ? ` · ${s.name}` : ''} (${s.row_count} rows)`
              }))
            ]}
            onChange={(e) => {
              setSelected(e.target.value);
              setSelectedDerivedId('');
              setRelation('');
              setPage(1);
              setSearch('');
            }}
            triggerStyle={{
              minWidth: '220px',
              maxWidth: '380px'
            }}
          />

          {/* Derived Views Dropdown (if present) */}
          {derivedTables.length > 0 && (
            <Select
              value={selectedDerivedId}
              aria-label="Select derived table or relational join"
              placeholder="Single Sheet"
              icon={<GitMerge size={14} color="#ffb089" />}
              options={[
                { value: "", label: "Single Sheet" },
                ...derivedTables.map((dt) => {
                  const isRollup = dt.join_keys?.type === 'scientific_enrichment_rollup';
                  return {
                    value: dt.id,
                    label: `${isRollup ? '📊 ' : '🔗 '}${dt.display_name} (${dt.row_count} rows)`
                  };
                })
              ]}
              onChange={(e) => {
                setSelectedDerivedId(e.target.value);
                setRelation('');
                setPage(1);
              }}
              triggerStyle={{
                minWidth: '180px',
                maxWidth: '300px'
              }}
            />
          )}

          {/* Scientific Enrichment Toggle Button */}
          {enrichment && derivedFeatCount > 0 && (
            <button
              type="button"
              onClick={() => setShowEnrichmentReview((prev) => !prev)}
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: '6px',
                background: showEnrichmentReview ? 'rgba(224, 86, 36, 0.22)' : 'rgba(224, 86, 36, 0.08)',
                border: '1px solid rgba(224, 86, 36, 0.4)',
                borderRadius: '8px',
                padding: '0 10px',
                minHeight: '38px',
                color: 'var(--brand-400)',
                fontSize: '0.82rem',
                fontWeight: 600,
                cursor: 'pointer'
              }}
              title="Toggle discovery inspection: semantic groups, discovered formulas, derived features, and analytical tables"
            >
              <Sparkles size={14} />
              <span>+{derivedFeatCount} Scientific Features</span>
              {showEnrichmentReview ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
            </button>
          )}

          {/* Table-specific Mode Controls: Version Pill + Search */}
          {viewMode === 'table' && !selectedDerivedId && (
            <>
              <div
                className="version-pill-group"
                role="radiogroup"
                aria-label="Table Data Version"
                style={{
                  display: 'inline-flex',
                  background: 'var(--hv-bg-inset, #F1F5F9)',
                  border: '1px solid var(--hv-border-strong, #CBD5E1)',
                  borderRadius: '7px',
                  padding: '2px',
                  gap: '2px'
                }}
              >
                <button
                  type="button"
                  role="radio"
                  aria-checked={dataVersion === 'curated'}
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
                    fontWeight: 600,
                    cursor: 'pointer'
                  }}
                >
                  ✨ Curated
                </button>
                <button
                  type="button"
                  role="radio"
                  aria-checked={dataVersion === 'raw'}
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
                    fontWeight: 600,
                    cursor: 'pointer'
                  }}
                >
                  📋 Raw
                </button>
              </div>

              {/* Table Search Input */}
              <div
                className="compact-search-wrap"
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
        <div className="explorer-toolbar-right" style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', flexShrink: 0, flexWrap: 'wrap' }}>
          {/* Minimal Workspace Files Indicator / Radix Popover */}
          {datasets.length > 0 && (
            <Popover
              open={showWorkspaceDrawer}
              onOpenChange={setShowWorkspaceDrawer}
              trigger={
                <button
                  type="button"
                  className="btn-secondary"
                  aria-expanded={showWorkspaceDrawer}
                  aria-controls="workspace-workbooks-menu"
                  style={{
                    display: 'inline-flex',
                    alignItems: 'center',
                    gap: '5px',
                    padding: '0.35rem 0.65rem',
                    fontSize: '0.78rem',
                    minHeight: '38px',
                    borderRadius: '8px'
                  }}
                  title="View workbooks currently in workspace"
                >
                  <Layers size={13} color="var(--brand-400)" />
                  <span>Manage {datasets.length} workbook{datasets.length > 1 ? 's' : ''}</span>
                  <ChevronDown size={12} style={{ transform: showWorkspaceDrawer ? 'rotate(180deg)' : 'none', transition: 'transform 0.2s' }} />
                </button>
              }
            >
              <div
                id="workspace-workbooks-menu"
                className="workspace-workbooks-menu"
                style={{ width: '320px', fontSize: '0.82rem' }}
              >
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px', paddingBottom: '6px', borderBottom: '1px solid var(--border-subtle)' }}>
                  <strong style={{ color: 'var(--fg-primary)', fontSize: '0.8rem' }}>Manage workbooks</strong>
                  <span style={{ fontSize: '0.72rem', color: 'var(--fg-muted)' }}>{datasets.length} file(s)</span>
                </div>
                <label className="workbook-select-all">
                  <input type="checkbox" aria-label="Select all workbooks" disabled={deleting}
                    checked={datasets.length > 0 && selectedWorkbookIds.length === datasets.length}
                    onChange={e => setSelectedWorkbookIds(e.target.checked ? datasets.map(d => d.id) : [])} />
                  Select all workbooks
                </label>
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
                      <input id={`workbook-select-${d.id}`} type="checkbox" aria-label={`Select ${d.original_name}`} disabled={deleting}
                        checked={selectedWorkbookIds.includes(d.id)}
                        onChange={e => setSelectedWorkbookIds(ids => e.target.checked ? [...ids, d.id] : ids.filter(id => id !== d.id))} />
                      <label htmlFor={`workbook-select-${d.id}`} style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', flex: 1, cursor: 'pointer' }}>
                        <div style={{ fontWeight: 600, color: 'var(--fg-primary)', fontSize: '0.8rem' }}>{d.original_name}</div>
                        <div style={{ fontSize: '0.72rem', color: 'var(--fg-muted)' }}>{d.row_count} rows · {d.sheet_count} sheet(s)</div>
                      </label>
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
                <div className="workbook-selection-footer">
                  <span aria-live="polite">{selectedWorkbookIds.length} selected</span>
                  <button type="button" className="btn-danger-confirm" disabled={!selectedWorkbookIds.length || deleting}
                    onClick={handlePromptBulkDelete}>Delete selected ({selectedWorkbookIds.length})</button>
                </div>
              </div>
            </Popover>
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
          {activeDataset && (
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
              title="Delete active workbook and all its sheets"
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
              <span>Delete workbook</span>
            </button>
          )}
        </div>
      </div>}
      </header>

      {notice && <div className="explorer-feedback" role="status">{notice}</div>}
      {catalogLoading && <div className="explorer-loading" role="status">Loading workbooks…</div>}
      {!catalogLoading && !catalogLoaded && <section className="explorer-empty-state">
        <div className="explorer-empty-icon"><FileSpreadsheet size={28} /></div>
        <h2>Workbooks couldn’t be loaded</h2>
        <p>Check that the server is available, then try again.</p>
        <button type="button" className="btn-primary" onClick={refresh}>Try again</button>
      </section>}
      {!catalogLoading && catalogLoaded && catalog.sheets.length === 0 && <section className="explorer-empty-state" aria-labelledby="explorer-empty-title">
        <div className="explorer-empty-icon"><FileSpreadsheet size={28} /></div>
        <h2 id="explorer-empty-title">No workbooks yet</h2>
        <p>Upload a CSV or Excel workbook to explore its records and insights.</p>
        <button type="button" className="btn-primary" onClick={() => { window.location.hash = 'upload'; }}>
          Upload spreadsheet
        </button>
        <span className="explorer-empty-hint">CSV, XLS and XLSX supported</span>
      </section>}

      {/* Prominent Data Completeness, Missing Values & Data Types Highlight Chips */}
      {selectedSheet && !selectedDerivedId && dataHealth && (
        <DataCompletenessChips
          dataHealth={dataHealth}
          sheetName={selectedSheet.display_name || selectedSheet.original_name || selectedSheet.name}
          onReupload={() => { window.location.hash = 'upload'; }}
        />
      )}

      {/* Collapsible Scientific Enrichment Review Panel */}
      {showEnrichmentReview && enrichment && (
        <div style={{ marginBottom: '1.25rem' }}>
          <EnrichmentReviewCard enrichment={enrichment} />
        </div>
      )}

      {error && (
        <div className="alert-box alert-error" style={{ marginBottom: '1rem' }}>
          <span>{error}</span>
        </div>
      )}

      {/* VIEW 1: DATA TABLE INSPECTION */}
      {catalogLoaded && catalog.sheets.length > 0 && viewMode === 'table' && (
        <>
          {selectedDerivedId && activeDerivedTable && (
            <div
              style={{
                background: activeDerivedTable.join_keys?.type === 'scientific_enrichment_rollup'
                  ? 'rgba(16, 185, 129, 0.08)'
                  : 'rgba(255, 176, 137, 0.1)',
                border: activeDerivedTable.join_keys?.type === 'scientific_enrichment_rollup'
                  ? '1px solid rgba(16, 185, 129, 0.3)'
                  : '1px solid rgba(255, 176, 137, 0.3)',
                borderRadius: '8px',
                padding: '0.6rem 0.9rem',
                marginBottom: '0.75rem',
                fontSize: '0.85rem',
                color: 'var(--fg-primary)',
                display: 'flex',
                alignItems: 'center',
                gap: '0.5rem'
              }}
            >
              <GitMerge size={16} color={activeDerivedTable.join_keys?.type === 'scientific_enrichment_rollup' ? 'var(--emerald-tier)' : '#ffb089'} />
              <span>
                <strong>
                  {activeDerivedTable.join_keys?.type === 'scientific_enrichment_rollup'
                    ? 'Synthesized Analytical Rollup Table:'
                    : 'Synthesized Cross-Sheet View:'}
                </strong>{' '}
                {activeDerivedTable.description}
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
              searchQuery={search}
              onSearchChange={setSearch}
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
      {catalogLoaded && catalog.sheets.length > 0 && viewMode === 'eda' && (
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
        error={deleteError}
        onClose={() => { if (!deleting) setDatasetToDelete(null); }}
        onConfirmDelete={handleConfirmDelete}
      />
    </div>
  );
}
