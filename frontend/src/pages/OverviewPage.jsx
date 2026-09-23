import React, { useEffect, useState } from 'react';
import {
  getOverviewBase,
  getOverviewVisuals,
  getOverviewStory,
  getOverviewRelational,
  refreshOverviewStory
} from '../api/client';
import ExecutiveStoryCard from '../components/ExecutiveStoryCard';
import DecisionBrief from '../components/DecisionBrief';
import VisualAnalyticsPanel from '../components/VisualAnalyticsPanel';
import RelationalInsightCard from '../components/RelationalInsightCard';
import AiQualityAuditModal from '../components/AiQualityAuditModal';
import LinkedFactsColumn from '../components/LinkedFactsColumn';
import InvestigationDrawer from '../components/InvestigationDrawer';
import {
  StorySkeletonLoader,
  VisualsSkeletonLoader,
  RelationalSkeletonLoader
} from '../components/OverviewSkeletons';
import ExecutiveHeroCockpit from '../components/overview/ExecutiveHeroCockpit';
import ErrorBoundary from '../components/common/ErrorBoundary';
import {
  ChevronDown,
  ChevronUp,
  FileSpreadsheet,
  Activity,
  Layers,
  Sparkles,
  ArrowRight
} from 'lucide-react';
import { formatDisplayLabel } from '../utils/displayFormatters';

function SheetCatalogCard({ sheet }) {
  const [isExpanded, setIsExpanded] = useState(false);
  const columns = sheet.columns || [];
  const MAX_INITIAL_CHIPS = 12;
  const hasMore = columns.length > MAX_INITIAL_CHIPS;
  const visibleColumns = isExpanded ? columns : columns.slice(0, MAX_INITIAL_CHIPS);
  const remainingCount = columns.length - MAX_INITIAL_CHIPS;

  return (
    <div className="sheet-summary-card">
      <div className="sheet-card-header">
        <div className="sheet-name-group">
          <FileSpreadsheet size={16} color="var(--accent)" />
          <strong>{sheet.display_name || sheet.name}</strong>
          {sheet.original_name && (sheet.display_name || sheet.name) !== sheet.original_name && (
            <span className="source-file-badge" title={sheet.original_name}>
              {sheet.original_name}
            </span>
          )}
        </div>
        <div className="sheet-meta-badges">
          <span className="row-count-badge">
            {Number(sheet.row_count || 0).toLocaleString()} rows · {columns.length} columns
          </span>
        </div>
      </div>
      <div className="sheet-columns-chip-list">
        {visibleColumns.map((col) => (
          <span key={col} className="col-chip" title={col}>
            {formatDisplayLabel(col)}
          </span>
        ))}
        {hasMore && (
          <button
            type="button"
            className="btn-toggle-chips"
            onClick={() => setIsExpanded((prev) => !prev)}
            aria-expanded={isExpanded}
          >
            {isExpanded ? (
              <>
                Show fewer <ChevronUp size={12} />
              </>
            ) : (
              <>
                +{remainingCount} more columns <ChevronDown size={12} />
              </>
            )}
          </button>
        )}
      </div>
    </div>
  );
}

export default function OverviewPage({ onNavigateTab, onScopeChange }) {
  // Chunk 1: Base Catalog & Scope Metadata (< 20ms)
  const [baseData, setBaseData] = useState(null);
  const [loadingBase, setLoadingBase] = useState(true);
  const [baseError, setBaseError] = useState('');

  // Scope selection (null = Cross-Sheet Global, number = specific sheet)
  const [selectedSheetId, setSelectedSheetId] = useState(null);

  // Chunk 2: Industrial Visual Intelligence Dashboard (~95ms)
  const [visualsData, setVisualsData] = useState(null);
  const [loadingVisuals, setLoadingVisuals] = useState(true);
  const [visualsError, setVisualsError] = useState('');

  // Chunk 3: AI Executive Story & Quality Audit (Async AI Generation)
  const [storyData, setStoryData] = useState(null);
  const [loadingStory, setLoadingStory] = useState(true);
  const [storyError, setStoryError] = useState('');
  const [isRefreshingStory, setIsRefreshingStory] = useState(false);

  // Chunk 4: Cross-Sheet Relational Story & Talent Quadrants (Async Relational Analysis)
  const [relationalData, setRelationalData] = useState(null);
  const [loadingRelational, setLoadingRelational] = useState(true);
  const [relationalError, setRelationalError] = useState('');

  // Investigation Drawer Context
  const [investigationTarget, setInvestigationTarget] = useState(null);

  // Modal & Expandable Accordion State
  const [showAuditModal, setShowAuditModal] = useState(false);
  const [showNarrativeAccordion, setShowNarrativeAccordion] = useState(false);

  // --------------------------------------------------------------------------
  // Chunk Fetchers
  // --------------------------------------------------------------------------
  const fetchBase = async () => {
    try {
      setLoadingBase(true);
      const res = await getOverviewBase();
      setBaseData(res);
      setBaseError('');
      if (!res.sheets || res.sheets.length === 0) {
        setLoadingStory(false);
        setLoadingVisuals(false);
        setLoadingRelational(false);
        setStoryData(null);
        setVisualsData(null);
        setRelationalData(null);
      }
    } catch (e) {
      setBaseError(e.message);
    } finally {
      setLoadingBase(false);
    }
  };

  const fetchVisuals = async (sheetId) => {
    try {
      setLoadingVisuals(true);
      setVisualsError('');
      const res = await getOverviewVisuals(sheetId);
      const vd = res.visual_dashboard;
      if (vd && vd.total_visualizations > 0) {
        setVisualsData(vd);
      } else {
        setVisualsData(null);
      }
    } catch (e) {
      setVisualsError(e.message);
    } finally {
      setLoadingVisuals(false);
    }
  };

  const fetchStory = async (sheetId) => {
    try {
      setLoadingStory(true);
      setStoryError('');
      const res = await getOverviewStory(sheetId);
      if (res.empty || !res.executive_story) {
        setStoryData(null);
      } else {
        setStoryData(res);
      }
    } catch (e) {
      setStoryError(e.message);
    } finally {
      setLoadingStory(false);
    }
  };

  const fetchRelational = async () => {
    try {
      setLoadingRelational(true);
      setRelationalError('');
      const res = await getOverviewRelational();
      if (res.relational_story) {
        setRelationalData(res.relational_story);
      } else {
        setRelationalData(null);
      }
    } catch (e) {
      setRelationalError(e.message);
    } finally {
      setLoadingRelational(false);
    }
  };

  // Initial mount: Launch all 4 chunks concurrently in parallel
  useEffect(() => {
    fetchBase();
    fetchVisuals(null);
    fetchStory(null);
    fetchRelational();
  }, []);

  // Scope switch: Only re-trigger scoped chunks (visuals + story) without blanking the page
  const handleSelectSheet = (sheetId) => {
    setSelectedSheetId(sheetId);
    fetchVisuals(sheetId);
    fetchStory(sheetId);
  };

  // Manual refresh for the AI executive story
  const handleRefreshStory = async () => {
    setIsRefreshingStory(true);
    try {
      const refreshed = await refreshOverviewStory(selectedSheetId);
      setStoryData({
        executive_story: refreshed.executive_story,
        evaluation: refreshed.evaluation,
        charts: refreshed.charts,
        forecast: refreshed.forecast,
        story_meta: refreshed.story_meta
      });
      if (refreshed.visual_dashboard) {
        setVisualsData(refreshed.visual_dashboard);
      }
      if (refreshed.relational_story) {
        setRelationalData(refreshed.relational_story);
      }
    } catch (err) {
      console.error('Failed to refresh executive story:', err);
    } finally {
      setIsRefreshingStory(false);
    }
  };

  // Focus chart anchor interaction
  const handleFocusChart = (chartId) => {
    const el = document.getElementById(chartId);
    if (el) {
      el.scrollIntoView({ behavior: 'smooth', block: 'center' });
      el.classList.add('chart-focus-highlight');
      setTimeout(() => el.classList.remove('chart-focus-highlight'), 2400);
    }
  };

  const fmt = (n) =>
    n == null ? 'Not available' : Number(n).toLocaleString(undefined, { maximumFractionDigits: 3 });

  const hasSheets = Boolean(baseData?.sheets && baseData.sheets.length > 0);
  const displayedSheets =
    selectedSheetId !== null && baseData?.sheets
      ? baseData.sheets.filter((s) => s.id === selectedSheetId)
      : baseData?.sheets || [];

  const selectedSheet =
    selectedSheetId !== null
      ? (baseData?.sheets_list?.find((s) => s.id === selectedSheetId) ||
         baseData?.sheets?.find((s) => s.id === selectedSheetId) ||
         null)
      : null;

  return (
    <div className="overview-page">
      {/* 1. Compact Top Workspace Header & Scope Filters */}
      <div className="compact-workspace-header">
        <div className="workspace-title-block">
          <div className="title-row">
            <h2>Executive Overview</h2>
            <span className="status-live-badge">
              <span className="live-dot" />
              <span>Uploaded sources</span>
            </span>
          </div>
          <p className="workspace-sub-note">
            Evidence-Based Visual Analytics & Decision Intelligence across active workspace data.
          </p>
        </div>

        <div className="header-actions-group">
          {storyData?.story_meta?.model && (
            <span className="model-chip" title="Active local LLM engine">
              Model: {storyData.story_meta.model}
            </span>
          )}
        </div>
      </div>

      {baseError && <p role="alert" className="error-banner">{baseError}</p>}

      {/* 2. Empty Workspace Banner when all data is deleted */}
      {!loadingBase && baseData && !hasSheets && (
        <div className="card-panel empty-workspace-panel" style={{ marginTop: '1.5rem', textAlign: 'center', padding: '3.5rem 1.5rem' }}>
          <div style={{ fontSize: '2.5rem', marginBottom: '1rem' }}>🗂️</div>
          <h3 style={{ fontSize: '1.35rem', marginBottom: '0.5rem', color: 'var(--fg-primary)' }}>Workspace is Empty</h3>
          <p style={{ color: 'var(--fg-secondary)', maxWidth: 520, margin: '0 auto 1.5rem auto', lineHeight: 1.5 }}>
            All previous sheets, records, and cached stories have been cleaned up. Upload a CSV or Excel workbook in the Ingestion Studio to discover supported comparisons, relationships, and evidence-backed findings.
          </p>
          <button className="btn-primary" onClick={() => onNavigateTab('ingestion')}>
            Upload a Spreadsheet
          </button>
        </div>
      )}

      {/* 2.5 Executive Hero Visual Cockpit */}
      {hasSheets && (
        <ErrorBoundary title="Executive Hero Cockpit Error">
          <ExecutiveHeroCockpit
            baseData={baseData}
            selectedSheet={selectedSheet}
            findingsCount={visualsData?.prioritized_facts?.length || 4}
            healthScore={storyData?.evaluation?.factual_accuracy_score || 86}
            onLaunchBriefing={() => onNavigateTab('presentations')}
            onOpenDeckStudio={() => onNavigateTab('presentations')}
            onExplore={() => onNavigateTab('explorer')}
          />
        </ErrorBoundary>
      )}

      {/* 3. Sheet Scope Selector Bar */}
      {hasSheets && (
        <div className="sheet-selector-bar">
          <span className="sheet-tab-label">Analytics Scope:</span>
          <button
            className={`sheet-tab-btn ${selectedSheetId === null ? 'active' : ''}`}
            onClick={() => handleSelectSheet(null)}
          >
            <span>Cross-Sheet Global View</span>
            <span className="tab-domain-tag">Consolidated</span>
          </button>
          {baseData?.sheets_list?.map((s) => (
            <button
              key={s.id}
              className={`sheet-tab-btn ${selectedSheetId === s.id ? 'active' : ''}`}
              onClick={() => handleSelectSheet(s.id)}
            >
              <span>{s.display_name || s.original_name || s.name}</span>
              <span className="tab-domain-tag">{s.domain}</span>
            </button>
          ))}
        </div>
      )}

      {hasSheets && (
        <ErrorBoundary title="Executive Decision Brief Error">
          <DecisionBrief
            sheetId={selectedSheetId}
            onExplore={() => onNavigateTab('explorer')}
            onSnapshotLoaded={(snapshot, sid) => {
              const primarySheet = baseData?.sheets?.find((s) => s.id === sid) || baseData?.sheets?.[0];
              onScopeChange?.({
                datasetId: primarySheet?.dataset_id || null,
                sheetId: sid || primarySheet?.id || null,
                snapshotId: snapshot
              });
            }}
          />
        </ErrorBoundary>
      )}

      <details className="overview-existing-analysis">
        <summary>Explore existing charts, models & source catalogue</summary>
      {/* 4. PRIMARY CHART-FIRST CANVAS: 2/3 Charts + 1/3 Prioritized Facts (Above the Fold) */}
      {hasSheets && (
        <div className="overview-primary-split">
          {/* Main Visual Intelligence Area (~2/3 Width) */}
          <main className="overview-charts-main" id="main-content">
            {loadingVisuals ? (
              <VisualsSkeletonLoader isScoped={selectedSheetId !== null} />
            ) : visualsError ? (
              <div className="card-panel error-notice">
                <p>Could not load visual dashboard: {visualsError}</p>
                <button className="btn-secondary" onClick={() => fetchVisuals(selectedSheetId)}>Retry Visuals</button>
              </div>
            ) : visualsData ? (
              <VisualAnalyticsPanel
                visualDashboard={visualsData}
                charts={storyData?.charts}
                forecast={storyData?.forecast}
                selectedSheetId={selectedSheetId}
                onInvestigate={(target) => setInvestigationTarget(target)}
              />
            ) : null}
          </main>

          {/* Prioritized Facts Sidebar (~1/3 Width) */}
          <div className="overview-facts-sidebar">
            <LinkedFactsColumn
              facts={visualsData?.prioritized_facts || []}
              onInvestigate={(target) => setInvestigationTarget(target)}
              onFocusChart={handleFocusChart}
            />
          </div>
        </div>
      )}

      {/* 5. Compact Workspace Catalog KPI Strip */}
      {hasSheets && (
        <div className="kpi-grid compact-kpi-strip" style={{ marginTop: '1.5rem' }}>
          {[
            ['Active Datasets', baseData.stats?.datasets],
            ['Source Sheets', baseData.stats?.sheets],
            ['Source Records', baseData.stats?.rows],
            ['Verified Key Relationships', baseData.stats?.linked_relationships]
          ].map(([label, value]) => (
            <div className="kpi-card compact-card" key={label}>
              <div className="kpi-label">{label}</div>
              <div className="kpi-value">{fmt(value)}</div>
            </div>
          ))}
        </div>
      )}

      {/* 6. Workspace relationships are shown only in workspace scope. */}
      {hasSheets && selectedSheetId === null && (
        <div style={{ marginTop: '1.5rem' }}>
          {loadingRelational ? (
            <RelationalSkeletonLoader />
          ) : relationalError ? (
            <div className="card-panel error-notice">
              <p>Could not load relational insights: {relationalError}</p>
              <button className="btn-secondary" onClick={fetchRelational}>Retry Relational</button>
            </div>
          ) : relationalData ? (
            <RelationalInsightCard
              relationalStory={relationalData}
              onNavigateTab={onNavigateTab}
            />
          ) : null}
        </div>
      )}

      {/* 7. Expandable Full AI Executive Narrative & Quality Audit Accordion */}
      {hasSheets && storyData?.executive_story && (
        <div className="narrative-accordion-card card-panel" style={{ marginTop: '1.5rem' }}>
          <div
            className="accordion-header"
            onClick={() => setShowNarrativeAccordion(!showNarrativeAccordion)}
            role="button"
            tabIndex={0}
            onKeyDown={(e) => e.key === 'Enter' && setShowNarrativeAccordion(!showNarrativeAccordion)}
            aria-expanded={showNarrativeAccordion}
          >
            <div className="accordion-title-group">
              <Sparkles size={16} color="var(--accent)" />
              <span className="accordion-title">Consolidated Executive Story & Model Quality Audit</span>
              <span className="accordion-meta-badge">
                {storyData.evaluation?.factual_accuracy_score != null
                  ? `${storyData.evaluation.factual_accuracy_score}% Verified Accuracy`
                  : 'Factual Audit'}
              </span>
            </div>
            <div className="accordion-toggle-icon">
              {showNarrativeAccordion ? <ChevronUp size={18} /> : <ChevronDown size={18} />}
            </div>
          </div>

          {showNarrativeAccordion && (
            <div className="accordion-content-body">
              <ExecutiveStoryCard
                story={storyData.executive_story}
                evaluation={storyData.evaluation}
                meta={storyData.story_meta}
                onRefresh={handleRefreshStory}
                isRefreshing={isRefreshingStory}
                onOpenAudit={() => setShowAuditModal(true)}
              />
            </div>
          )}
        </div>
      )}

      {/* 8. Technical Diagnostics Link Strip */}
      {hasSheets && (
        <div className="card-panel" style={{ marginTop: '1.5rem', display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '1rem' }}>
          <div>
            <h3 style={{ margin: 0, color: '#f8fafc' }}>Technical Diagnostics & Column Schema Profiling</h3>
            <p className="subtitle" style={{ margin: '4px 0 0 0' }}>
              Inspect deterministic column classifications, Spearman rank correlations, uniqueness ratios, and relational join links in Data Explorer.
            </p>
          </div>
          <button className="btn-secondary" onClick={() => onNavigateTab('explorer')}>
            Open Technical Explorer <ArrowRight size={13} style={{ marginLeft: 4 }} />
          </button>
        </div>
      )}

      </details>

      {/* 9. Modal for AI Quality Fact-Checking Audit */}
      {showAuditModal && storyData?.evaluation && (
        <AiQualityAuditModal
          evaluation={storyData.evaluation}
          onClose={() => setShowAuditModal(false)}
        />
      )}

      {/* 10. Reusable Contextual Evidence Investigation Drawer */}
      {investigationTarget && (
        <InvestigationDrawer
          investigationTarget={investigationTarget}
          onClose={() => setInvestigationTarget(null)}
          onDrillDown={(newTarget) => setInvestigationTarget(newTarget)}
        />
      )}
    </div>
  );
}
