import React, { useState } from 'react';
import MarkdownView from './MarkdownView';
import ChartEvidenceHeader from './analytics/ChartEvidenceHeader';
import Talent9BoxMatrix from './analytics/Talent9BoxMatrix';
import BradfordFactorChart from './analytics/BradfordFactorChart';
import BurnoutStrainChart from './analytics/BurnoutStrainChart';
import ElasticityChart from './analytics/ElasticityChart';
import ComparativeBarChart from './analytics/ComparativeBarChart';
import DynamicBarChart from './analytics/DynamicBarChart';
import DynamicLineChart from './analytics/DynamicLineChart';
import DynamicDonutChart from './analytics/DynamicDonutChart';
import ForecastChart from './analytics/ForecastChart';

// Re-export modular components for convenience
export {
  ChartEvidenceHeader,
  Talent9BoxMatrix,
  BradfordFactorChart,
  BurnoutStrainChart,
  ElasticityChart,
  ComparativeBarChart,
  DynamicBarChart,
  DynamicLineChart,
  DynamicDonutChart,
  ForecastChart
};

// ============================================================================
// MAIN VISUAL ANALYTICS PANEL COMPONENT (EXECUTIVE OVERVIEW)
// ============================================================================
export default function VisualAnalyticsPanel({
  visualDashboard,
  charts,
  forecast,
  selectedSheetId,
  onInvestigate
}) {
  const [activeCategory, setActiveCategory] = useState('All');

  if (visualDashboard && visualDashboard.visualizations?.length > 0) {
    const allVis = visualDashboard.visualizations;
    const categories = visualDashboard.categories || ['All'];
    const catCounts = visualDashboard.category_counts || {};

    const filteredVis = activeCategory === 'All'
      ? allVis
      : allVis.filter((v) => v.category === activeCategory);

    return (
      <div className="visual-analytics-panel">
        <div className="section-title-row">
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem', flexWrap: 'wrap' }}>
              <h3>Primary Visual Intelligence & Analytics</h3>
              <span className="badge-ai-count">{allVis.length} Visualizations Ready</span>
            </div>
            <p className="subtitle">
              Dynamic, evidence-backed charts profiling trends, performance distribution, and operational patterns.
            </p>
          </div>
        </div>

        {/* Category Filter Pills */}
        <div className="dashboard-filter-bar">
          <span className="filter-label">Filter View:</span>
          {categories.map((cat) => {
            const count = catCounts[cat] || (cat === 'All' ? allVis.length : 0);
            return (
              <button
                key={cat}
                className={`dashboard-filter-pill ${activeCategory === cat ? 'active' : ''}`}
                onClick={() => setActiveCategory(cat)}
              >
                <span>{cat}</span>
                <span className="pill-count-chip">{count}</span>
              </button>
            );
          })}
        </div>

        {/* Multi-Chart Gallery Grid */}
        <div className="visual-dashboard-grid">
          {filteredVis.map((v) => {
            const isCrossSheet = v.category === 'Cross-Sheet Intelligence';

            return (
              <div key={v.id} id={v.id} className={`visual-card ${isCrossSheet ? 'card-cross-sheet' : ''}`}>
                {/* Standard Evidence Header Identification */}
                <ChartEvidenceHeader visualization={v} onInvestigate={onInvestigate} />

                {/* Card Top Badges */}
                <div className="card-top-badges">
                  <span className={`sheet-source-badge ${isCrossSheet ? 'badge-cross-accent' : ''}`}>
                    {v.chart_type === 'talent_9box' && '🎯 '}
                    {v.chart_type === 'bradford_factor' && '⚠️ '}
                    {v.chart_type === 'burnout_strain' && '🔥 '}
                    {v.chart_type === 'elasticity' && '📐 '}
                    {v.chart_type === 'comparative_bar' && '🔗 '}
                    {v.chart_type === 'forecast' && '📈 '}
                    {v.chart_type === 'bar' && '📊 '}
                    {v.chart_type === 'donut' && '🍩 '}
                    {v.chart_type === 'line' && '📈 '}
                    {v.sheet_badge}
                  </span>
                  <span className="category-pill-badge">{v.category}</span>
                  <span className="type-pill-badge">
                    {v.chart_type === 'talent_9box' && '9-Box Matrix'}
                    {v.chart_type === 'bradford_factor' && 'Disruption Index'}
                    {v.chart_type === 'burnout_strain' && 'Strain Gauge'}
                    {v.chart_type === 'elasticity' && 'OLS Regression'}
                    {v.chart_type === 'comparative_bar' && 'Grouped Comparative'}
                    {v.chart_type === 'forecast' && 'Longitudinal Trajectory'}
                    {v.chart_type === 'bar' && 'Rankings & Distribution'}
                    {v.chart_type === 'donut' && 'Parts of a Whole'}
                    {v.chart_type === 'line' && 'Sequential Trend'}
                  </span>
                </div>

                {/* Card Title & Subtitle */}
                <div className="card-title-group">
                  <h4>{v.title}</h4>
                  {v.subtitle && <p className="card-sub">{v.subtitle}</p>}
                </div>

                {/* Card Visual Body */}
                <div className="card-visual-body">
                  {v.chart_type === 'talent_9box' && (
                    <Talent9BoxMatrix data={v.talent_9box_data} onInvestigate={onInvestigate} />
                  )}
                  {v.chart_type === 'bradford_factor' && (
                    <BradfordFactorChart data={v.bradford_data} onInvestigate={onInvestigate} />
                  )}
                  {v.chart_type === 'burnout_strain' && (
                    <BurnoutStrainChart data={v.burnout_data} onInvestigate={onInvestigate} />
                  )}
                  {v.chart_type === 'elasticity' && (
                    <ElasticityChart data={v.elasticity_data} onInvestigate={onInvestigate} />
                  )}
                  {v.chart_type === 'comparative_bar' && (
                    <ComparativeBarChart data={v.comparative_data} onInvestigate={onInvestigate} />
                  )}
                  {v.chart_type === 'forecast' && (
                    <ForecastChart data={v.forecast_data} onInvestigate={onInvestigate} />
                  )}
                  {v.chart_type === 'bar' && (
                    <DynamicBarChart visualization={v} onInvestigate={onInvestigate} />
                  )}
                  {v.chart_type === 'donut' && (
                    <DynamicDonutChart data={v.donut_data} onInvestigate={onInvestigate} metricName={v.measured_metric} />
                  )}
                  {v.chart_type === 'line' && (
                    <DynamicLineChart visualization={v} onInvestigate={onInvestigate} />
                  )}
                </div>

                {/* AI Strategic Takeaway Banner */}
                {v.ai_insight && (
                  <div className="chart-ai-insight-banner">
                    <div className="insight-header">
                      <span className="insight-icon">💡</span>
                      <span className="insight-title">Strategic Observation</span>
                    </div>
                    <div className="insight-content">
                      <MarkdownView content={v.ai_insight} />
                    </div>
                  </div>
                )}

                {/* Stats Pills Row */}
                {v.stats_pills && v.stats_pills.length > 0 && (
                  <div className="card-stats-row">
                    {v.stats_pills.map((pill, pIdx) => (
                      <div key={pIdx} className="stat-pill-chip">
                        <span className="stat-pill-label">{pill.label}:</span>
                        <span className="stat-pill-value">{pill.value}</span>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </div>
    );
  }

  return null;
}
