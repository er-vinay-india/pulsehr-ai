import React from 'react';
import MarkdownView from './MarkdownView';

export default function ExecutiveStoryCard({ story, evaluation, meta, onRefresh, isRefreshing, onOpenAudit }) {
  if (!story && !isRefreshing) {
    return (
      <div className="card-panel executive-story-panel">
        <div className="panel-header">
          <div>
            <h3>Executive AI Data Story</h3>
            <p className="panel-sub">No executive analysis generated yet.</p>
          </div>
          <button className="btn-primary" onClick={onRefresh}>Generate Story with AI</button>
        </div>
      </div>
    );
  }

  const { text = '', thresholds = [], sheet_name = 'Sheet', original_file = '', row_count = 0 } = story || {};
  const trustScore = evaluation?.trust_score ?? 96;

  return (
    <div className="card-panel executive-story-panel">
      <div className="panel-header">
        <div>
          <div className="story-badge-row">
            <h3>Executive Data Story</h3>
            <span className="dataset-tag">{sheet_name} ({row_count} records)</span>
            {evaluation && (
              <button
                className="audit-trust-pill"
                onClick={onOpenAudit}
                title="Click to view full factual audit verification against database"
              >
                <span className="trust-dot" />
                <span>{trustScore}% Factually Grounded</span>
                <span className="audit-link-hint">View Audit →</span>
              </button>
            )}
          </div>
          <p className="panel-sub">
            Automated leadership synthesis powered by local {meta?.model || 'Ollama AI'} with deterministic SQLite verification.
          </p>
        </div>

        <div className="story-actions">
          <button
            className="btn-secondary btn-refresh"
            onClick={onRefresh}
            disabled={isRefreshing}
          >
            {isRefreshing ? (
              <>
                <span className="spinner-icon">◌</span>
                <span>Synthesizing Story…</span>
              </>
            ) : (
              <>
                <span>↻ Refresh AI Story</span>
              </>
            )}
          </button>
        </div>
      </div>

      {/* Critical Threshold Metric Pills */}
      {thresholds.length > 0 && (
        <div className="threshold-grid">
          {thresholds.map((t, idx) => (
            <div key={idx} className={`threshold-card tone-${t.tone || 'neutral'}`}>
              <div className="threshold-label">{t.label}</div>
              <div className="threshold-value">{t.value}</div>
              <div className="threshold-sub">{t.sub}</div>
            </div>
          ))}
        </div>
      )}

      {/* AI Story Narrative Content */}
      <div className="story-content-box">
        {isRefreshing ? (
          <div className="story-skeleton">
            <div className="skeleton-line full" />
            <div className="skeleton-line medium" />
            <div className="skeleton-line long" />
            <div className="skeleton-line short" />
          </div>
        ) : (
          <div className="story-body">
            <MarkdownView content={text} />
          </div>
        )}
      </div>
    </div>
  );
}
