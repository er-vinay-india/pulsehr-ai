import React from 'react';

/**
 * Shimmering skeleton loader for the AI Executive Story Card.
 */
export function StorySkeletonLoader({ isScoped = false }) {
  return (
    <div className="card-panel executive-story-card skeleton-card">
      <div className="skeleton-header-row">
        <div className="skeleton-badge shimmer-box" style={{ width: 180, height: 26, borderRadius: 20 }} />
        <div className="skeleton-badge shimmer-box" style={{ width: 90, height: 26, borderRadius: 8 }} />
      </div>

      <div className="skeleton-status-banner">
        <span className="spinner-dot" />
        <span>
          {isScoped
            ? 'AI Copilot is profiling sheet-specific workforce dynamics & empirical benchmarks…'
            : 'AI Copilot is synthesizing cross-sheet executive narrative & verifying empirical claims…'}
        </span>
      </div>

      <div className="skeleton-body-lines">
        <div className="shimmer-box line-h" style={{ width: '96%', height: 14 }} />
        <div className="shimmer-box line-h" style={{ width: '88%', height: 14 }} />
        <div className="shimmer-box line-h" style={{ width: '92%', height: 14 }} />
        <div className="shimmer-box line-h" style={{ width: '65%', height: 14 }} />
      </div>

      <div className="skeleton-footer-row">
        <div className="shimmer-box" style={{ width: 140, height: 28, borderRadius: 14 }} />
        <div className="shimmer-box" style={{ width: 160, height: 28, borderRadius: 14 }} />
      </div>
    </div>
  );
}

/**
 * Shimmering skeleton loader for the Autonomous Visual Analytics & Industrial Models Suite.
 */
export function VisualsSkeletonLoader({ isScoped = false }) {
  return (
    <div className="card-panel visual-analytics-suite-panel skeleton-card" style={{ marginTop: '1.5rem' }}>
      <div className="visual-panel-header">
        <div className="shimmer-box" style={{ width: 240, height: 24, borderRadius: 6, marginBottom: 8 }} />
        <div className="shimmer-box" style={{ width: 380, height: 14, borderRadius: 4 }} />
      </div>

      <div className="skeleton-status-banner" style={{ margin: '1rem 0' }}>
        <span className="spinner-dot" />
        <span>
          {isScoped
            ? 'Computing sheet visual projections, 9-Box talent matrix, and trend trajectories…'
            : 'Evaluating cross-sheet elasticity, Bradford factor disruption, and workload strain diagnostics…'}
        </span>
      </div>

      {/* Pill tabs placeholder */}
      <div className="sheet-selector-bar" style={{ opacity: 0.6, marginBottom: '1.25rem' }}>
        {['All', 'Industrial Analytics', 'Risk & Burnout', 'Forecasts'].map((lbl, idx) => (
          <div key={idx} className="shimmer-box" style={{ width: 85 + idx * 15, height: 28, borderRadius: 14 }} />
        ))}
      </div>

      {/* Visual Cards Grid */}
      <div className="visual-dashboard-grid">
        {/* Card 1: 9-Box Matrix Mock */}
        <div className="visual-card skeleton-subcard">
          <div className="shimmer-box" style={{ width: '60%', height: 18, borderRadius: 4, marginBottom: 6 }} />
          <div className="shimmer-box" style={{ width: '85%', height: 12, borderRadius: 4, marginBottom: 14 }} />
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 6, height: 130 }}>
            {Array.from({ length: 9 }).map((_, i) => (
              <div key={i} className="shimmer-box" style={{ borderRadius: 6 }} />
            ))}
          </div>
          <div className="shimmer-box" style={{ width: '100%', height: 36, borderRadius: 6, marginTop: 12 }} />
        </div>

        {/* Card 2: Bradford Spectrum Mock */}
        <div className="visual-card skeleton-subcard">
          <div className="shimmer-box" style={{ width: '55%', height: 18, borderRadius: 4, marginBottom: 6 }} />
          <div className="shimmer-box" style={{ width: '75%', height: 12, borderRadius: 4, marginBottom: 14 }} />
          <div style={{ display: 'flex', flexDirection: 'column', gap: 10, height: 130, justifyContent: 'center' }}>
            <div className="shimmer-box" style={{ width: '92%', height: 22, borderRadius: 4 }} />
            <div className="shimmer-box" style={{ width: '78%', height: 22, borderRadius: 4 }} />
            <div className="shimmer-box" style={{ width: '85%', height: 22, borderRadius: 4 }} />
            <div className="shimmer-box" style={{ width: '60%', height: 22, borderRadius: 4 }} />
          </div>
          <div className="shimmer-box" style={{ width: '100%', height: 36, borderRadius: 6, marginTop: 12 }} />
        </div>
      </div>
    </div>
  );
}

/**
 * Shimmering skeleton loader for the Cross-Sheet Relational Story Card.
 */
export function RelationalSkeletonLoader() {
  return (
    <div className="card-panel relational-insight-card skeleton-card" style={{ marginTop: '1.5rem' }}>
      <div className="panel-header">
        <div className="shimmer-box" style={{ width: 220, height: 22, borderRadius: 6, marginBottom: 6 }} />
        <div className="shimmer-box" style={{ width: 340, height: 14, borderRadius: 4 }} />
      </div>

      <div className="skeleton-status-banner" style={{ margin: '1rem 0' }}>
        <span className="spinner-dot" />
        <span>Analyzing cross-sheet employee keys, join intersections & multi-quadrant talent distribution…</span>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '1rem', marginTop: '1rem' }}>
        {Array.from({ length: 4 }).map((_, idx) => (
          <div key={idx} className="shimmer-box" style={{ height: 90, borderRadius: 8 }} />
        ))}
      </div>
    </div>
  );
}
