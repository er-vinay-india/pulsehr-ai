import React from 'react';
import {
  TrendingUp,
  AlertTriangle,
  Users,
  Target,
  Zap,
  ArrowRight,
  ShieldAlert,
  Award,
  DollarSign
} from 'lucide-react';

const fmt = (n) => (n == null ? 'Unavailable' : Number(n).toLocaleString(undefined, { maximumFractionDigits: 1 }));

export default function SignalCardDeck({
  findings = [],
  onInspectEvidence,
  onExplore
}) {
  if (!findings || findings.length === 0) return null;

  // Pick top 3-4 findings
  const topSignals = findings.slice(0, 4);

  // Dynamic icon selector based on finding characteristics
  const getSignalIcon = (finding) => {
    const kind = (finding.kind || '').toLowerCase();
    const title = (finding.title || '').toLowerCase();

    if (kind === 'risk' || title.includes('risk') || title.includes('alert')) {
      return <AlertTriangle size={18} className="signal-icon-warning" />;
    }
    if (title.includes('retention') || title.includes('employee') || title.includes('headcount')) {
      return <Users size={18} className="signal-icon-info" />;
    }
    if (title.includes('sales') || title.includes('revenue') || title.includes('margin') || title.includes('$')) {
      return <DollarSign size={18} className="signal-icon-success" />;
    }
    if (kind === 'outlier' || title.includes('leader') || title.includes('top')) {
      return <Award size={18} className="signal-icon-accent" />;
    }
    return <Zap size={18} className="signal-icon-primary" />;
  };

  return (
    <div className="signal-card-deck">
      <div className="deck-header-row">
        <div>
          <h2 className="deck-title">Executive Signals & Action Deck</h2>
          <p className="deck-subtitle">
            Synthesized operational anomalies, comparative variances, and primary vectors.
          </p>
        </div>
      </div>

      <div className="deck-grid">
        {topSignals.map((f, idx) => {
          const detail = f.detail || {};
          const isRisk = f.kind === 'risk';

          return (
            <article
              key={f.id || idx}
              className={`signal-card ${isRisk ? 'signal-card--risk' : 'signal-card--standard'}`}
            >
              <div className="signal-card-top">
                <div className="signal-icon-wrap">
                  {getSignalIcon(f)}
                </div>
                <span className={`signal-kind-pill ${isRisk ? 'pill-risk' : 'pill-standard'}`}>
                  {f.kind?.toUpperCase() || 'SIGNAL'}
                </span>
              </div>

              <h3 className="signal-card-title">{f.title}</h3>
              
              <div className="signal-headline-box">
                <p className="signal-observation-text">{f.observation}</p>
              </div>

              {/* Proposed Action Strip */}
              <div className="signal-action-strip">
                <span className="action-tag">Recommended Move</span>
                <p className="action-summary">{f.action}</p>
              </div>

              <div className="signal-card-footer">
                <button
                  type="button"
                  className="btn-inspect-evidence"
                  onClick={() => onInspectEvidence(f)}
                  title="Inspect calculations and row sample in drawer"
                >
                  <span>Inspect Evidence</span>
                  <ArrowRight size={13} />
                </button>
              </div>
            </article>
          );
        })}
      </div>
    </div>
  );
}
