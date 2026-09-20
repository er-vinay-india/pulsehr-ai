import React from 'react';
import {
  ShieldAlert,
  Award,
  TrendingUp,
  Sparkles,
  ArrowRight,
  Crosshair,
  Info
} from 'lucide-react';

export default function LinkedFactsColumn({
  facts = [],
  onInvestigate,
  onFocusChart
}) {
  if (!facts || facts.length === 0) {
    return (
      <div className="linked-facts-column empty-facts">
        <div className="facts-header">
          <h3>Key Findings & Evidence</h3>
        </div>
        <div className="facts-empty-notice">
          <Info size={18} />
          <p>Analyzing verified patterns across active sheets...</p>
        </div>
      </div>
    );
  }

  const getBadgeIcon = (badge) => {
    switch (badge) {
      case 'strength':
        return <Award size={14} color="#10b981" />;
      case 'attention':
        return <ShieldAlert size={14} color="#f43f5e" />;
      case 'shift':
        return <TrendingUp size={14} color="#6366f1" />;
      case 'opportunity':
        return <Sparkles size={14} color="#f59e0b" />;
      default:
        return <Info size={14} color="#06b6d4" />;
    }
  };

  const getBadgeClass = (badge) => {
    switch (badge) {
      case 'strength':
        return 'fact-badge-strength';
      case 'attention':
        return 'fact-badge-attention';
      case 'shift':
        return 'fact-badge-shift';
      case 'opportunity':
        return 'fact-badge-opportunity';
      default:
        return 'fact-badge-neutral';
    }
  };

  return (
    <aside className="linked-facts-column" aria-label="Prioritized Findings and Evidence">
      <div className="facts-header">
        <div className="facts-header-left">
          <h3>Prioritized Evidence</h3>
          <span className="facts-count-tag">{facts.length} Key Insights</span>
        </div>
      </div>

      <div className="facts-list">
        {facts.map((fact) => {
          const badgeClass = getBadgeClass(fact.badge);
          const icon = getBadgeIcon(fact.badge);

          return (
            <div key={fact.id} className={`fact-card ${fact.badge || 'neutral'}`}>
              <div className="fact-top-row">
                <span className={`fact-badge ${badgeClass}`}>
                  {icon}
                  <span>{fact.badge_label || fact.badge?.toUpperCase()}</span>
                </span>
                {fact.linked_chart_id && onFocusChart && (
                  <button
                    type="button"
                    className="btn-chart-anchor"
                    onClick={() => onFocusChart(fact.linked_chart_id)}
                    title="Scroll to supporting chart"
                    aria-label={`Scroll to chart for ${fact.headline}`}
                  >
                    <Crosshair size={13} />
                    <span>Focus Chart</span>
                  </button>
                )}
              </div>

              <h4 className="fact-headline">{fact.headline}</h4>

              <div className="fact-metrics-box">
                <span className="fact-primary-val">{fact.value}</span>
                <span className="fact-comparison-text">{fact.comparison}</span>
              </div>

              <p className="fact-impact-desc">{fact.why_it_matters}</p>

              <div className="fact-actions-row">
                <button
                  type="button"
                  className="btn-investigate-fact"
                  onClick={() => onInvestigate && onInvestigate(fact.investigation_target || { targetId: fact.headline })}
                >
                  <span>Investigate Evidence</span>
                  <ArrowRight size={13} />
                </button>
                {fact.evidence_strength && (
                  <span className="fact-strength-note" title="Evidence Basis">
                    {fact.evidence_strength}
                  </span>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </aside>
  );
}
