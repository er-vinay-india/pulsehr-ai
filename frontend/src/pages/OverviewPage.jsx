import React, { useEffect, useState } from 'react';
import {
  getOverviewBase,
  getOverviewVisuals,
  getOverviewStory,
  getOverviewRelational,
  refreshOverviewStory
} from '../api/client';
import ExecutiveStoryCard from '../components/ExecutiveStoryCard';
import VisualAnalyticsPanel from '../components/VisualAnalyticsPanel';
import RelationalInsightCard from '../components/RelationalInsightCard';
import AiQualityAuditModal from '../components/AiQualityAuditModal';
import {
  StorySkeletonLoader,
  VisualsSkeletonLoader,
  RelationalSkeletonLoader
} from '../components/OverviewSkeletons';

export default function OverviewPage({ onNavigateTab }) {
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

  // Modal State
  const [showAuditModal, setShowAuditModal] = useState(false);

  // --------------------------------------------------------------------------
  // Chunk Fetchers
  // --------------------------------------------------------------------------
  const fetchBase = async () => {
    try {
      setLoadingBase(true);
      const res = await getOverviewBase();
      setBaseData(res);
      setBaseError('');
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
      setVisualsData(res.visual_dashboard);
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
      setStoryData(res);
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
      setRelationalData(res.relational_story);
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

  const fmt = (n) =>
    n == null ? 'Not available' : Number(n).toLocaleString(undefined, { maximumFractionDigits: 3 });

  const displayedSheets =
    selectedSheetId !== null && baseData?.sheets
      ? baseData.sheets.filter((s) => s.id === selectedSheetId)
      : baseData?.sheets || [];

  return (
    <div className="overview-page">
      {/* 1. Top Executive Banner (Always present immediately) */}
      <div className="executive-banner">
        <div className="banner-content">
          <h2>Executive Overview</h2>
          <p>Live AI-synthesized intelligence and multi-measure forecasting across your uploaded workforce sheets.</p>
        </div>
        <button className="btn-primary" onClick={() => onNavigateTab('copilot')}>
          Ask AI Copilot
        </button>
      </div>

      {baseError && <p role="alert" className="error-banner">{baseError}</p>}

      {/* 2. Sheet Scope Selector Bar (Renders as soon as Base arrives in ~15ms) */}
      {loadingBase ? (
        <div className="sheet-selector-bar" style={{ opacity: 0.7 }}>
          <span className="sheet-tab-label">Analytics Scope:</span>
          <div className="shimmer-box" style={{ width: 140, height: 30, borderRadius: 20 }} />
          <div className="shimmer-box" style={{ width: 180, height: 30, borderRadius: 20 }} />
        </div>
      ) : (
        baseData?.sheets_list && baseData.sheets_list.length > 0 && (
          <div className="sheet-selector-bar">
            <span className="sheet-tab-label">Analytics Scope:</span>
            <button
              className={`sheet-tab-btn ${selectedSheetId === null ? 'active' : ''}`}
              onClick={() => handleSelectSheet(null)}
            >
              <span>Cross-Sheet Global View</span>
              <span className="tab-domain-tag">Consolidated</span>
            </button>
            {baseData.sheets_list.map((s) => (
              <button
                key={s.id}
                className={`sheet-tab-btn ${selectedSheetId === s.id ? 'active' : ''}`}
                onClick={() => handleSelectSheet(s.id)}
              >
                <span>{s.original_name || s.name}</span>
                <span className="tab-domain-tag">{s.domain}</span>
              </button>
            ))}
          </div>
        )
      )}

      {/* 3. Base KPI Grid (Renders immediately with Base data) */}
      {loadingBase ? (
        <div className="kpi-grid">
          {[1, 2, 3, 4].map((i) => (
            <div className="kpi-card" key={i}>
              <div className="shimmer-box" style={{ width: '60%', height: 14, borderRadius: 4, marginBottom: 8 }} />
              <div className="shimmer-box" style={{ width: '40%', height: 28, borderRadius: 4 }} />
            </div>
          ))}
        </div>
      ) : (
        baseData && (
          <>
            <div className="kpi-grid">
              {[
                ['Datasets', baseData.stats?.datasets],
                ['Sheets', baseData.stats?.sheets],
                ['Source rows', baseData.stats?.rows],
                ['Exact key relationships', baseData.stats?.linked_relationships]
              ].map(([label, value]) => (
                <div className="kpi-card" key={label}>
                  <div className="kpi-label">{label}</div>
                  <div className="kpi-value">{fmt(value)}</div>
                </div>
              ))}
            </div>
            {baseData.note && <p className="subtitle">{baseData.note}</p>}
          </>
        )
      )}

      {/* 4. CHUNK 2: AI Executive Story & Quality Audit Card */}
      {loadingStory ? (
        <StorySkeletonLoader isScoped={selectedSheetId !== null} />
      ) : storyError ? (
        <div className="card-panel error-notice" style={{ marginTop: '1.25rem' }}>
          <p>Could not load executive story: {storyError}</p>
          <button className="btn-secondary" onClick={() => fetchStory(selectedSheetId)}>Retry Story</button>
        </div>
      ) : storyData?.executive_story ? (
        <ExecutiveStoryCard
          story={storyData.executive_story}
          evaluation={storyData.evaluation}
          meta={storyData.story_meta}
          onRefresh={handleRefreshStory}
          isRefreshing={isRefreshingStory}
          onOpenAudit={() => setShowAuditModal(true)}
        />
      ) : null}

      {/* 5. CHUNK 3: Visual Analytics & Industrial Models Dashboard */}
      {loadingVisuals ? (
        <VisualsSkeletonLoader isScoped={selectedSheetId !== null} />
      ) : visualsError ? (
        <div className="card-panel error-notice" style={{ marginTop: '1.25rem' }}>
          <p>Could not load visual dashboard: {visualsError}</p>
          <button className="btn-secondary" onClick={() => fetchVisuals(selectedSheetId)}>Retry Visuals</button>
        </div>
      ) : visualsData ? (
        <VisualAnalyticsPanel
          visualDashboard={visualsData}
          charts={storyData?.charts}
          forecast={storyData?.forecast}
          selectedSheetId={selectedSheetId}
        />
      ) : null}

      {/* 6. CHUNK 4: Cross-Sheet Relational Story & Talent Quadrants */}
      {loadingRelational ? (
        <RelationalSkeletonLoader />
      ) : relationalError ? (
        <div className="card-panel error-notice" style={{ marginTop: '1.25rem' }}>
          <p>Could not load relational insights: {relationalError}</p>
          <button className="btn-secondary" onClick={fetchRelational}>Retry Relational Analysis</button>
        </div>
      ) : relationalData ? (
        <RelationalInsightCard relationalData={relationalData} />
      ) : null}

      {/* 7. Upload Prompt when no sheets are in catalog */}
      {!loadingBase && baseData && !baseData.sheets?.length && (
        <div className="card-panel" style={{ marginTop: '20px' }}>
          <h3>Start with your data</h3>
          <p>Upload a CSV or Excel workbook to populate this overview.</p>
          <button className="btn-primary" onClick={() => onNavigateTab('ingestion')}>
            Upload a sheet
          </button>
        </div>
      )}

      {/* 8. Per-Sheet Column Profiles (From Base Data) */}
      {!loadingBase && displayedSheets.length > 0 && (
        <div style={{ marginTop: 20 }}>
          {selectedSheetId !== null && (
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.75rem' }}>
              <span style={{ fontSize: '0.85rem', color: 'var(--fg-secondary)' }}>
                Showing profile for focused sheet ({displayedSheets[0]?.original_name || 'Selected Sheet'}).
              </span>
              <button
                className="btn-secondary"
                style={{ fontSize: '0.75rem', padding: '0.2rem 0.6rem' }}
                onClick={() => handleSelectSheet(null)}
              >
                Show all sheets
              </button>
            </div>
          )}

          {[...displayedSheets].reverse().map((sheet) => (
            <div className="card-panel" key={sheet.id} style={{ marginBottom: 20 }}>
              <div className="panel-header">
                <div>
                  <h3>{sheet.original_name} / {sheet.name}</h3>
                  <p className="panel-sub">{sheet.row_count} rows · {sheet.columns?.length || 0} columns</p>
                </div>
                <button className="btn-secondary" onClick={() => onNavigateTab('explorer')}>
                  Explore sheet data
                </button>
              </div>

              <div className="kpi-grid">
                {sheet.profiles?.filter((p) => p.numeric).slice(0, 4).map((p) => (
                  <div className="kpi-card" key={p.column}>
                    <div className="kpi-label">Mean {p.column}{p.unit ? ` (${p.unit})` : ''}</div>
                    <div className="kpi-value">{fmt(p.numeric.mean)}</div>
                    <small>{p.nonempty} recorded values</small>
                  </div>
                ))}
              </div>

              <details>
                <summary>All {sheet.columns?.length || 0} column profiles</summary>
                <div className="table-container">
                  <table>
                    <thead>
                      <tr>
                        <th>Column</th>
                        <th>Present</th>
                        <th>Missing</th>
                        <th>Distinct values</th>
                        <th>Mean</th>
                        <th>Minimum</th>
                        <th>Maximum</th>
                      </tr>
                    </thead>
                    <tbody>
                      {sheet.profiles?.map((p) => (
                        <tr key={p.column}>
                          <td>{p.column}</td>
                          <td>{p.nonempty}</td>
                          <td>{p.missing}</td>
                          <td>{p.distinct}</td>
                          <td>{p.numeric ? fmt(p.numeric.mean) : '—'}</td>
                          <td>{p.numeric ? fmt(p.numeric.min) : '—'}</td>
                          <td>{p.numeric ? fmt(p.numeric.max) : '—'}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </details>
            </div>
          ))}
        </div>
      )}

      {/* 9. Connected Information Summary (From Base Data) */}
      {!loadingBase && baseData?.relationships && (
        <div className="card-panel" style={{ marginTop: 20 }}>
          <h3>Connected information</h3>
          {!baseData.relationships.length && (
            <p>No shared keys found yet. Upload a related sheet to connect records.</p>
          )}
          {baseData.relationships.map((r) => (
            <p key={r.id}>
              <strong>
                {r.left_file} / {r.left_name} [{r.left_column}] ↔ {r.right_file} / {r.right_name} [{r.right_column}]
              </strong>
              <br />
              {r.status === 'linked' ? 'Exact join available' : 'Suggested relationship'} · {r.cardinality} · {r.matching_keys} shared values · {r.matching_pairs} matching row pairs
              <br />
              <small>{r.reason}</small>
            </p>
          ))}
        </div>
      )}

      {/* AI Quality Audit Matrix Modal */}
      <AiQualityAuditModal
        isOpen={showAuditModal}
        onClose={() => setShowAuditModal(false)}
        evaluation={storyData?.evaluation}
        modelName={storyData?.story_meta?.model}
      />
    </div>
  );
}
