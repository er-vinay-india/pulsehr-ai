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
  Layers,
  ChevronDown,
  ChevronUp,
  Sparkles
} from 'lucide-react';
import Select from '../components/common/Select';
import Popover from '../components/common/Popover';
import { useTheme } from '../context/ThemeContext';
import { getThemeTokens } from '../theme/tokens';
import DataExplorerNavigation from '../components/explorer/DataExplorerNavigation';
import OverviewExplorer from '../components/explorer/OverviewExplorer';
import RankingsExplorer from '../components/explorer/RankingsExplorer';
import TrendsExplorer from '../components/explorer/TrendsExplorer';
import RelationshipsExplorer from '../components/explorer/RelationshipsExplorer';
import DistributionsExplorer from '../components/explorer/DistributionsExplorer';
import EvidenceExplorer from '../components/explorer/EvidenceExplorer';
import TechnicalExplorer from '../components/explorer/TechnicalExplorer';

export function getCombinedUrlParam(key) {
  const searchParams = new URLSearchParams(window.location.search);
  const val = searchParams.get(key);
  if (val != null) return val;
  if (window.location.hash.includes('?')) {
    const hashQuery = window.location.hash.split('?')[1];
    const hashParams = new URLSearchParams(hashQuery);
    return hashParams.get(key);
  }
  return null;
}

export default function DataExplorerPage() {
  const { isDark } = useTheme();
  const themeTokens = getThemeTokens(isDark);

  const [catalog, setCatalog] = useState({ sheets: [], relationships: [] });
  const [showEnrichmentReview, setShowEnrichmentReview] = useState(false);
  const [selected, setSelected] = useState(() => {
    return getCombinedUrlParam('sheet_id') || '';
  });
  const [relation, setRelation] = useState('');
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState('');
  const [data, setData] = useState(null);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  // Secondary Navigation Subpage State: 'overview' | 'rankings' | 'trends' | 'relationships' | 'distributions' | 'evidence' | 'technical'
  const [activeTab, setActiveTab] = useState(() => {
    const tabParam = getCombinedUrlParam('tab');
    if (tabParam && ['overview', 'rankings', 'trends', 'relationships', 'distributions', 'evidence', 'technical'].includes(tabParam)) {
      return tabParam;
    }
    // Backward compatibility for view=eda or view=table
    const v = getCombinedUrlParam('view');
    if (v === 'eda') return 'overview';
    return 'overview';
  });

  // Ranking schema & metadata state
  const [rankingSchema, setRankingSchema] = useState(null);

  // Data Version State: 'curated' (Post-EDA normalized) | 'raw' (Original values)
  const [dataVersion, setDataVersion] = useState('curated');

  // Derived Tables State
  const [derivedTables, setDerivedTables] = useState([]);
  const [selectedDerivedId, setSelectedDerivedId] = useState(() => {
    return getCombinedUrlParam('derived_id') || '';
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

  const handleTabChange = (tabId) => {
    setActiveTab(tabId);
    const params = new URLSearchParams(window.location.search);
    params.set('tab', tabId);
    window.history.replaceState(null, '', `${window.location.pathname}?${params.toString()}${window.location.hash}`);
  };

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
        const urlSheet = getCombinedUrlParam('sheet_id');
        const urlDataset = getCombinedUrlParam('dataset_id');
        let targetSheet = null;
        if (urlDataset) {
          const dsSheets = sheets.sheets.filter(s => String(s.dataset_id) === String(urlDataset));
          if (dsSheets.length > 0) {
            targetSheet = String(dsSheets[0].id);
          }
        }
        const next = targetSheet
          || (sheets.sheets.some(s => String(s.id) === current) ? current
          : sheets.sheets.some(s => String(s.id) === urlSheet) ? urlSheet
          : String(sheets.sheets[sheets.sheets.length - 1]?.id || ''));
        const params = new URLSearchParams(window.location.search);
        if (next) params.set('sheet_id', next); else params.delete('sheet_id');
        const cleanHash = window.location.hash.split('?')[0] || '#explorer';
        window.history.replaceState(null, '', `${window.location.pathname}${params.size ? '?' + params : ''}${cleanHash}`);
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

  // Fetch Table Rows (Used in Technical tab)
  useEffect(() => {
    if (!catalogLoaded || (!selected && !selectedDerivedId)) {
      setLoading(false);
      setData(null);
      return;
    }
    if (activeTab !== 'technical') return;

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
  }, [selected, selectedDerivedId, relation, page, search, activeTab, dataVersion, catalogLoaded]);

  // Fetch EDA Report for active sheet
  useEffect(() => {
    if (!catalogLoaded || !selected) { setEdaReport(null); setLoadingEda(false); return; }

    let active = true;
    setLoadingEda(true);

    getSheetEdaReport(selected)
      .then(async (rep) => {
        if (!active) return;
        setEdaReport(rep);
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
  }, [selected, catalogLoaded]);

  const selectedSheet = catalog.sheets.find((s) => String(s.id) === String(selected));
  const activeDataset = datasets.find((d) => Number(d.id) === Number(selectedSheet?.dataset_id));

  // Fetch ranking schema for active dataset
  useEffect(() => {
    const dsId = activeDataset?.id || selectedSheet?.dataset_id;
    if (!dsId) {
      setRankingSchema(null);
      return;
    }
    fetch(`/api/adaptive-dashboard/ranking/schema/${dsId}`)
      .then((r) => (r.ok ? r.json() : null))
      .then((data) => {
        if (data) setRankingSchema(data);
      })
      .catch(() => {});
  }, [activeDataset?.id, selectedSheet?.dataset_id]);

  const enrichment = activeDataset?.enrichment;
  const derivedFeatCount = enrichment?.derived_features_count || enrichment?.derived_features?.length || 0;
  const link = catalog.relationships.find((r) => String(r.id) === relation);
  const left = catalog.sheets.find((s) => s.id === link?.left_sheet);
  const right = catalog.sheets.find((s) => s.id === link?.right_sheet);

  // Compute completeness and data health
  const dataHealth = useMemo(() => {
    if (!selectedSheet) return null;

    const summary = edaReport?.summary;
    const profiles = selectedSheet.profiles || [];
    const colDiags = edaReport?.column_diagnostics || {};

    const totalRows = summary?.total_rows ?? selectedSheet.row_count ?? 0;
    const totalCols = summary?.total_columns ?? selectedSheet.columns?.length ?? 0;
    const totalCells = summary?.total_cells ?? ((totalRows * totalCols) || 1);

    const totalNullCells = summary?.total_null_cells ?? selectedSheet.completeness?.total_missing ?? profiles.reduce((acc, p) => acc + (p.missing || 0), 0);
    const nullPct = summary?.null_cells_pct ?? (totalCells > 0 ? Number(((totalNullCells / totalCells) * 100).toFixed(2)) : 0);
    const completenessPct = summary?.completeness_pct ?? (totalCells > 0 ? Number((100 - nullPct).toFixed(2)) : 100);

    const incompleteRows = summary?.incomplete_rows_count ?? (profiles.length > 0 ? Math.min(totalRows, Math.max(...profiles.map(p => p.missing || 0), 0)) : 0);
    const incompleteRowsPct = summary?.incomplete_rows_pct ?? (totalRows > 0 ? Number(((incompleteRows / totalRows) * 100).toFixed(2)) : 0);

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
      healthScore,
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

  // URL query params for initial ranking deep links (supports both ?search and #hash?query)
  const initialEntity = getCombinedUrlParam('entity') || null;
  const initialMeasure = getCombinedUrlParam('measure') || null;
  const initialRelationshipId = getCombinedUrlParam('relationship_id') || null;
  const initialTemporalFamily = getCombinedUrlParam('temporal_family') || null;
  const initialTopicId = getCombinedUrlParam('topic_id') || null;
  const initialEvidenceId = getCombinedUrlParam('evidence_id') || null;

  return (
    <div className="explorer-page">
      {/* Standardized Page Top Header */}
      <header className="page-top-header explorer-page-header">
        <div className="page-title-row">
          <div className="page-title-group">
            <h1 className="page-heading">Data Explorer</h1>
            <p className="page-description">
              Modular analytical inspection across entity rankings, temporal trends, relationships, distributions, evidence, and technical diagnostics.
            </p>
          </div>
        </div>

        {/* Unified Command & Filter Toolbar */}
        {catalog.sheets.length > 0 && (
          <div className="explorer-compact-toolbar page-command-bar" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '0.65rem' }}>
            {/* Left Controls: Sheet Selector & Derived Views */}
            <div className="explorer-toolbar-left" style={{ display: 'flex', alignItems: 'center', gap: '0.65rem', flexWrap: 'wrap', flex: 1, minWidth: 0 }}>
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

              {enrichment && derivedFeatCount > 0 && (
                <button
                  type="button"
                  onClick={() => setShowEnrichmentReview((prev) => !prev)}
                  style={{
                    display: 'inline-flex',
                    alignItems: 'center',
                    gap: '6px',
                    background: showEnrichmentReview ? 'var(--color-bg-soft-gold)' : 'var(--color-bg-subtle)',
                    border: '1px solid var(--color-border-strong)',
                    borderRadius: '8px',
                    padding: '0 10px',
                    minHeight: '38px',
                    color: 'var(--color-gold)',
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
            </div>

            {/* Right Actions: Manage Workbooks, Download, Delete */}
            <div className="explorer-toolbar-right" style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', flexShrink: 0, flexWrap: 'wrap' }}>
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
                  <div id="workspace-workbooks-menu" className="workspace-workbooks-menu" style={{ width: '320px', fontSize: '0.82rem' }}>
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
                            background: d.id === selectedSheet?.dataset_id ? 'var(--color-bg-soft-blue)' : 'transparent',
                            border: d.id === selectedSheet?.dataset_id ? '1px solid var(--color-border)' : '1px solid transparent'
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
                    background: 'var(--color-bg-soft-error)',
                    border: '1px solid var(--color-error)',
                    color: 'var(--color-error)',
                    cursor: 'pointer',
                    transition: 'all 0.2s ease'
                  }}
                >
                  <Trash2 size={13} />
                  <span>Delete workbook</span>
                </button>
              )}
            </div>
          </div>
        )}
      </header>

      {notice && <div className="explorer-feedback" role="status">{notice}</div>}
      {catalogLoading && <div className="explorer-loading" role="status">Loading workbooks…</div>}
      {!catalogLoading && !catalogLoaded && (
        <section className="explorer-empty-state">
          <div className="explorer-empty-icon"><FileSpreadsheet size={28} /></div>
          <h2>Workbooks couldn’t be loaded</h2>
          <p>Check that the server is available, then try again.</p>
          <button type="button" className="btn-primary" onClick={refresh}>Try again</button>
        </section>
      )}
      {!catalogLoading && catalogLoaded && catalog.sheets.length === 0 && (
        <section className="explorer-empty-state" aria-labelledby="explorer-empty-title">
          <div className="explorer-empty-icon"><FileSpreadsheet size={28} /></div>
          <h2 id="explorer-empty-title">No workbooks yet</h2>
          <p>Upload a CSV or Excel workbook to explore its records and insights.</p>
          <button type="button" className="btn-primary" onClick={() => { window.location.hash = 'upload'; }}>
            Upload spreadsheet
          </button>
          <span className="explorer-empty-hint">CSV, XLS and XLSX supported</span>
        </section>
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

      {/* SECONDARY SUBPAGE NAVIGATION */}
      {catalogLoaded && catalog.sheets.length > 0 && (
        <>
          <DataExplorerNavigation
            activeTab={activeTab}
            onSelectTab={handleTabChange}
            themeTokens={themeTokens}
            isDark={isDark}
          />

          {/* SUBPAGE VIEW ROUTING */}
          <div className="explorer-subpage-content" id={`explorer-panel-${activeTab}`} role="tabpanel">
            {activeTab === 'overview' && (
              <OverviewExplorer
                activeDataset={activeDataset}
                selectedSheet={selectedSheet}
                catalog={catalog}
                dataHealth={dataHealth}
                rankingSchema={rankingSchema}
                onNavigateTab={handleTabChange}
                themeTokens={themeTokens}
                isDark={isDark}
              />
            )}

            {activeTab === 'rankings' && (
              <RankingsExplorer
                datasetId={activeDataset?.id || selectedSheet?.dataset_id}
                initialEntity={initialEntity}
                initialMeasure={initialMeasure}
                themeTokens={themeTokens}
                isDark={isDark}
              />
            )}

            {activeTab === 'trends' && (
              <TrendsExplorer
                edaReport={edaReport}
                rankingSchema={rankingSchema}
                selectedSheet={selectedSheet}
                initialMeasure={initialMeasure}
                initialTemporalFamily={initialTemporalFamily}
                themeTokens={themeTokens}
                isDark={isDark}
              />
            )}

            {activeTab === 'relationships' && (
              <RelationshipsExplorer
                catalog={catalog}
                derivedTables={derivedTables}
                crossCorrelations={crossCorrelations}
                edaReport={edaReport}
                initialRelationshipId={initialRelationshipId}
                themeTokens={themeTokens}
                isDark={isDark}
                onExploreDerivedTable={(derivedId) => {
                  setSelectedDerivedId(derivedId);
                  handleTabChange('technical');
                }}
              />
            )}

            {activeTab === 'distributions' && (
              <DistributionsExplorer
                edaReport={edaReport}
                rankingSchema={rankingSchema}
                initialMeasure={initialMeasure}
                themeTokens={themeTokens}
                isDark={isDark}
              />
            )}

            {activeTab === 'evidence' && (
              <EvidenceExplorer
                sheetId={selectedSheet?.id}
                datasetId={activeDataset?.id || selectedSheet?.dataset_id}
                initialTopicId={initialTopicId}
                initialEvidenceId={initialEvidenceId}
                themeTokens={themeTokens}
                isDark={isDark}
              />
            )}

            {activeTab === 'technical' && (
              <TechnicalExplorer
                selectedSheet={selectedSheet}
                datasetId={activeDataset?.id || selectedSheet?.dataset_id}
                edaReport={edaReport}
                dataVersion={dataVersion}
                onDataVersionChange={setDataVersion}
                data={data}
                columns={columns}
                rows={rows}
                page={page}
                onPageChange={setPage}
                loading={loading}
                search={search}
                onSearchChange={setSearch}
                sourceLabel={
                  selectedDerivedId
                    ? activeDerivedTable?.display_name || 'derived_view'
                    : relation
                    ? 'relational_join'
                    : `${selectedSheet?.display_name || selectedSheet?.original_name || 'table'} [${dataVersion.toUpperCase()}]`
                }
                themeTokens={themeTokens}
                isDark={isDark}
              />
            )}
          </div>
        </>
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
