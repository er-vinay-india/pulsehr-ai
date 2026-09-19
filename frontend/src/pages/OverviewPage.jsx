import React, { useEffect, useState } from 'react';
import { getAnalyticsOverview, refreshOverviewStory } from '../api/client';
import ExecutiveStoryCard from '../components/ExecutiveStoryCard';
import VisualAnalyticsPanel from '../components/VisualAnalyticsPanel';
import RelationalInsightCard from '../components/RelationalInsightCard';
import AiQualityAuditModal from '../components/AiQualityAuditModal';

export default function OverviewPage({ onNavigateTab }) {
  const [data, setData] = useState(null);
  const [error, setError] = useState('');
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [showAuditModal, setShowAuditModal] = useState(false);

  const fetchOverview = async () => {
    try {
      const res = await getAnalyticsOverview();
      setData(res);
      setError('');
    } catch (e) {
      setError(e.message);
    }
  };

  useEffect(() => {
    fetchOverview();
  }, []);

  const handleRefreshStory = async () => {
    setIsRefreshing(true);
    try {
      const refreshed = await refreshOverviewStory(data?.story_meta?.sheet_id);
      setData(prev => ({
        ...prev,
        executive_story: refreshed.executive_story,
        evaluation: refreshed.evaluation,
        charts: refreshed.charts,
        forecast: refreshed.forecast,
        relational_story: refreshed.relational_story,
        story_meta: refreshed.story_meta
      }));
    } catch (err) {
      console.error('Failed to refresh executive story:', err);
    } finally {
      setIsRefreshing(false);
    }
  };

  if (error) return <p role="alert" className="error-banner">{error}</p>;
  if (!data) return <p className="loading-state">Loading sheet analytics and AI data stories…</p>;

  const fmt = n => n == null ? 'Not available' : Number(n).toLocaleString(undefined, { maximumFractionDigits: 3 });

  return (
    <div className="overview-page">
      {/* Top Banner */}
      <div className="executive-banner">
        <div className="banner-content">
          <h2>Executive Overview</h2>
          <p>Live AI-synthesized intelligence and time-series forecasting across your uploaded sheets.</p>
        </div>
        <button className="btn-primary" onClick={() => onNavigateTab('copilot')}>
          Ask AI Copilot
        </button>
      </div>

      {/* KPI Grid */}
      <div className="kpi-grid">
        {[
          ['Datasets', data.stats.datasets],
          ['Sheets', data.stats.sheets],
          ['Source rows', data.stats.rows],
          ['Exact key relationships', data.stats.linked_relationships]
        ].map(([label, value]) => (
          <div className="kpi-card" key={label}>
            <div className="kpi-label">{label}</div>
            <div className="kpi-value">{fmt(value)}</div>
          </div>
        ))}
      </div>

      <p className="subtitle">{data.note}</p>

      {/* 1. Automated AI Data Story Card */}
      {data.executive_story && (
        <ExecutiveStoryCard
          story={data.executive_story}
          evaluation={data.evaluation}
          meta={data.story_meta}
          onRefresh={handleRefreshStory}
          isRefreshing={isRefreshing}
          onOpenAudit={() => setShowAuditModal(true)}
        />
      )}

      {/* 2. Visual Analytics (Bar Chart, Donut Chart, Time-Series Forecast) */}
      {(data.charts || data.forecast) && (
        <VisualAnalyticsPanel
          charts={data.charts}
          forecast={data.forecast}
        />
      )}

      {/* 3. Cross-Sheet Relational Story & 4-Quadrant Talent Classification */}
      {data.relational_story && (
        <RelationalInsightCard
          relationalData={data.relational_story}
        />
      )}

      {/* Upload prompt when empty */}
      {!data.sheets.length && (
        <div className="card-panel" style={{ marginTop: '20px' }}>
          <h3>Start with your data</h3>
          <p>Upload a CSV or Excel workbook to populate this overview.</p>
          <button className="btn-primary" onClick={() => onNavigateTab('ingestion')}>
            Upload a sheet
          </button>
        </div>
      )}

      {/* Per-Sheet Column Profiles */}
      {[...data.sheets].reverse().map(sheet => (
        <div className="card-panel" key={sheet.id} style={{ marginTop: 20 }}>
          <div className="panel-header">
            <div>
              <h3>{sheet.original_name} / {sheet.name}</h3>
              <p className="panel-sub">{sheet.row_count} rows · {sheet.columns.length} columns</p>
            </div>
            <button className="btn-secondary" onClick={() => onNavigateTab('explorer')}>
              Explore sheets
            </button>
          </div>

          <div className="kpi-grid">
            {sheet.profiles.filter(p => p.numeric).slice(0, 4).map(p => (
              <div className="kpi-card" key={p.column}>
                <div className="kpi-label">Mean {p.column}{p.unit ? ` (${p.unit})` : ''}</div>
                <div className="kpi-value">{fmt(p.numeric.mean)}</div>
                <small>{p.nonempty} recorded values</small>
              </div>
            ))}
          </div>

          <details>
            <summary>All {sheet.columns.length} column profiles</summary>
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
                  {sheet.profiles.map(p => (
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

      {/* Connected Information Summary */}
      <div className="card-panel" style={{ marginTop: 20 }}>
        <h3>Connected information</h3>
        {!data.relationships.length && (
          <p>No shared keys found yet. Upload a related sheet to connect records.</p>
        )}
        {data.relationships.map(r => (
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

      {/* AI Quality Audit Matrix Modal */}
      <AiQualityAuditModal
        isOpen={showAuditModal}
        onClose={() => setShowAuditModal(false)}
        evaluation={data.evaluation}
        modelName={data.story_meta?.model}
      />
    </div>
  );
}
