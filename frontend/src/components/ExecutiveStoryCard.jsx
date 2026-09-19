import React, { useState } from 'react';

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

  // Simple markdown renderer for bolding, bullet points, headers
  const renderMarkdown = (md) => {
    if (!md) return null;
    const lines = md.split('\n');
    return lines.map((line, idx) => {
      const trimmed = line.trim();
      if (!trimmed) return <div key={idx} style={{ height: '8px' }} />;
      if (trimmed.startsWith('### ')) {
        return <h4 key={idx} className="story-heading-3">{trimmed.replace('### ', '')}</h4>;
      }
      if (trimmed.startsWith('## ')) {
        return <h3 key={idx} className="story-heading-2">{trimmed.replace('## ', '')}</h3>;
      }
      if (trimmed.startsWith('# ')) {
        return <h2 key={idx} className="story-heading-1">{trimmed.replace('# ', '')}</h2>;
      }
      if (trimmed.startsWith('- ') || trimmed.startsWith('* ')) {
        const bulletText = trimmed.substring(2);
        return (
          <li key={idx} className="story-bullet">
            <span dangerouslySetInnerHTML={{ __html: formatInlineMarkdown(bulletText) }} />
          </li>
        );
      }
      return (
        <p key={idx} className="story-paragraph" dangerouslySetInnerHTML={{ __html: formatInlineMarkdown(trimmed) }} />
      );
    });
  };

  const formatInlineMarkdown = (str) => {
    return str
      .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
      .replace(/\*(.*?)\*/g, '<em>$1</em>')
      .replace(/`([^`]+)`/g, '<code>$1</code>');
  };

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
            {renderMarkdown(text)}
          </div>
        )}
      </div>
    </div>
  );
}
