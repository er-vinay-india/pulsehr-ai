import React, { useEffect, useRef, useState } from 'react';
import {
  ArrowRight,
  ChevronLeft,
  ChevronRight,
  Sparkles,
  Presentation,
  X,
  RefreshCw,
  Search,
  Info,
  Download,
  Database
} from 'lucide-react';
import '../styles/decision-brief.scss';
import { decisionBriefHtml } from '../utils/decisionBriefExport';
import ExecutiveBarComparisonChart from './charts/ExecutiveBarComparisonChart';
import ExecutiveTrendChart from './charts/ExecutiveTrendChart';
import ExecutiveHeatmapChart from './charts/ExecutiveHeatmapChart';
import VoiceoverPlayer from './VoiceoverPlayer';
import EvidenceDrawer from './overview/EvidenceDrawer';

const fmt = (n) => (n == null ? 'Unavailable' : Number(n).toLocaleString(undefined, { maximumFractionDigits: 2 }));

function FindingCard({ finding, index, onInspectEvidence, onExplore }) {
  return (
    <article className={`decision-finding decision-finding--${finding.kind}`}>
      <div className="decision-card-meta">
        <span>{String(index + 1).padStart(2, '0')} / {finding.kind}</span>
        <span>{finding.source.sheet}</span>
      </div>
      <h3>{finding.title}</h3>
      <p className="decision-observation">{finding.observation}</p>
      <p className="decision-implication">{finding.implication}</p>
      <div className="decision-action">
        <span>Proposed next step</span>
        <p>{finding.action}</p>
        <small>{finding.owner} · next operating review</small>
      </div>
      <div className="decision-card-actions" style={{ display: 'flex', justifyContent: 'space-between', marginTop: '1rem' }}>
        <button
          type="button"
          className="btn-slide-inspect"
          onClick={() => onInspectEvidence(finding)}
          style={{ background: 'none', border: 'none', color: '#63cfb3', cursor: 'pointer', fontSize: '0.8rem', fontWeight: 600, display: 'flex', alignItems: 'center', gap: '4px' }}
        >
          <Search size={13} /> Inspect Evidence
        </button>
        <button
          type="button"
          className="decision-link"
          onClick={onExplore}
          style={{ fontSize: '0.8rem' }}
        >
          Data Explorer <ArrowRight size={12} />
        </button>
      </div>
    </article>
  );
}

function BriefPresentation({ data, onClose, onExplore }) {
  const ref = useRef(null);
  const [page, setPage] = useState(0);
  const pages = data.findings;
  useEffect(() => {
    const dialog = ref.current;
    if (dialog) dialog.showModal();
    return () => dialog?.close();
  }, []);
  const f = pages[page];
  return (
    <dialog
      ref={ref}
      className="decision-presentation"
      onCancel={onClose}
      onKeyDown={(e) => {
        if (e.target.tagName === 'SELECT' || e.target.tagName === 'INPUT') return;
        if (e.key === 'ArrowRight') setPage((p) => Math.min(p + 1, pages.length - 1));
        if (e.key === 'ArrowLeft') setPage((p) => Math.max(0, p - 1));
      }}
    >
      <header>
        <span>Leadership briefing · {data.snapshot}</span>
        <button onClick={onClose} aria-label="Close presentation"><X size={22} /></button>
      </header>
      <div className="decision-slide">
        <div className="decision-eyebrow">{f.kind} / {f.source.file}</div>
        <h1>{f.title}</h1>
        <p className="decision-slide-stat">{f.observation}</p>
        <div className="decision-slide-grid">
          <section>
            {f.detail.groups ? (
              <ExecutiveBarComparisonChart
                groups={f.detail.groups}
                metricName={f.metric}
                baseline={f.detail.baseline}
                focusGroup={f.detail.focus_group}
                height={260}
              />
            ) : (
              <>
                <h2>What this means</h2>
                <p>{f.implication}</p>
                <p>{f.method}</p>
              </>
            )}
          </section>
          <aside>
            <span className="decision-eyebrow">Proposed action</span>
            <h2>{f.action}</h2>
            <p>{f.owner} · next operating review</p>
            <hr />
            <p>{f.implication}</p>
          </aside>
        </div>
        <footer>{f.source.sheet} · {f.id} · Source-scale measurements; no causal conclusion</footer>
      </div>
      <nav aria-label="Presentation navigation">
        <button onClick={() => setPage((p) => Math.max(0, p - 1))} disabled={page === 0}>
          <ChevronLeft size={18} /> Previous
        </button>
        <span>{page + 1} / {pages.length}</span>
        <button onClick={() => setPage((p) => Math.min(p + 1, pages.length - 1))} disabled={page === pages.length - 1}>
          Next <ChevronRight size={18} />
        </button>
      </nav>
    </dialog>
  );
}

export default function DecisionBrief({ sheetId, onExplore }) {
  const [data, setData] = useState(null);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);
  const [refresh, setRefresh] = useState(0);
  const [profileIndex, setProfileIndex] = useState(0);
  const [comparisonIndex, setComparisonIndex] = useState(0);
  const [prioritizing, setPrioritizing] = useState(false);
  const [present, setPresent] = useState(false);
  const [drawerFinding, setDrawerFinding] = useState(null);
  const request = useRef(0);

  useEffect(() => {
    const controller = new AbortController();
    const id = ++request.current;
    setLoading(true);
    setError('');
    setData(null);
    setProfileIndex(0);
    setComparisonIndex(0);
    setPresent(false);
    setPrioritizing(false);
    fetch(`/api/analytics/decision-brief${sheetId != null ? `?sheet_id=${sheetId}` : ''}`, {
      signal: controller.signal
    })
      .then(async (r) => {
        if (!r.ok) throw new Error('Could not analyze the selected source.');
        return r.json();
      })
      .then((result) => {
        if (id === request.current) setData(result);
      })
      .catch((e) => {
        if (e.name !== 'AbortError' && id === request.current) setError(e.message);
      })
      .finally(() => {
        if (id === request.current) setLoading(false);
      });
    return () => controller.abort();
  }, [sheetId, refresh]);

  const prioritize = async () => {
    const id = request.current;
    setPrioritizing(true);
    try {
      const r = await fetch('/api/analytics/decision-brief/prioritize', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ sheet_id: sheetId, snapshot: data.snapshot })
      });
      if (!r.ok)
        throw new Error(r.status === 409 ? 'Source changed. Refresh the brief.' : 'Could not prioritize this brief.');
      const result = await r.json();
      if (id === request.current) setData(result);
    } catch (e) {
      if (id === request.current) setError(e.message);
    } finally {
      if (id === request.current) setPrioritizing(false);
    }
  };

  const exportBrief = () => {
    const blob = new Blob([decisionBriefHtml(data)], { type: 'text/html;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `executive-brief-${data.snapshot}.html`;
    a.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  };

  const download = () => {
    const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `decision-brief-${data.snapshot}.json`;
    a.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  };

  if (loading)
    return (
      <section className="decision-shell decision-loading" aria-busy="true">
        <Sparkles size={22} />
        <h2>Finding the story in your data</h2>
        <p>Comparing segments, resolving periods, and checking relationships…</p>
      </section>
    );

  if (!data)
    return (
      <section className="decision-shell">
        <p role="alert">{error}</p>
        <button className="decision-button" onClick={() => setRefresh((x) => x + 1)}>
          Retry analysis
        </button>
      </section>
    );

  if (data.empty) return null;

  const profile = data.profiles?.[profileIndex] || data.profiles?.[0] || {};
  const comparison = profile?.comparisons?.[comparisonIndex] || profile?.comparisons?.[0];
  const trends = profile?.trends || [];
  const matrix = profile?.matrix;

  return (
    <section className="decision-shell" aria-label="Executive decision brief">
      <header className="decision-header">
        <div>
          <div className="decision-eyebrow">
            <span className="decision-dot" /> THE DECISION BRIEF
          </div>
          <h2>What deserves your attention</h2>
          <p>Evidence, context, and a next step — from the sheets you selected.</p>
        </div>
        <div className="decision-controls">
          <button onClick={prioritize} disabled={prioritizing || !data.findings.length}>
            <Sparkles size={15} />
            {prioritizing ? 'Prioritizing…' : 'AI prioritize'}
          </button>
          <button onClick={() => setPresent(true)} disabled={!data.findings.length}>
            <Presentation size={15} />
            Present brief
          </button>
          <button onClick={exportBrief} disabled={!data.findings.length}>
            <Download size={15} />
            Export briefing
          </button>
          <button aria-label="Download evidence JSON" title="Download evidence JSON" onClick={download}>
            <Download size={16} />
          </button>
          <button aria-label="Refresh decision brief" onClick={() => setRefresh((x) => x + 1)}>
            <RefreshCw size={16} />
          </button>
        </div>
      </header>

      <VoiceoverPlayer
        identity={data.snapshot}
        text={data.findings.map(f => [f.title, f.observation, f.implication, 'Proposed next step: ' + f.action].filter(Boolean).join('. ')).join('\n\n')}
      />
      <div className="decision-status">
        <span>{data.ai_status}</span>
        <span>
          {data.finding_count} supported findings · {data.profiles.length} sources analyzed separately
        </span>
      </div>

      {error && <p role="alert">{error}</p>}

      {data.findings.length ? (
        <div className="decision-findings">
          {data.findings.map((f, i) => (
            <FindingCard
              key={f.id}
              finding={f}
              index={i}
              onInspectEvidence={(finding) => setDrawerFinding(finding)}
              onExplore={onExplore}
            />
          ))}
        </div>
      ) : (
        <div className="decision-empty">
          <h3>No strong descriptive differences surfaced</h3>
          <p>
            This can reflect similar groups, limited observations, or unresolved fields. Inspect the
            comparisons and coverage below; no issues were invented.
          </p>
        </div>
      )}

      {/* Visual Analytics Sections powered by Apache ECharts */}
      <div className="decision-section-header">
        <div>
          <div className="decision-eyebrow">EXPLORE THE EVIDENCE</div>
          <h3>Compare, connect, investigate</h3>
        </div>
        <label className="decision-select-label">
          Source
          <select
            value={profileIndex}
            onChange={(e) => {
              setProfileIndex(Number(e.target.value));
              setComparisonIndex(0);
            }}
          >
            {data.profiles.map((p, i) => (
              <option key={p.source.sheet_id} value={i}>
                {p.source.file} / {p.source.sheet}
              </option>
            ))}
          </select>
        </label>
      </div>

      <div className="decision-chips">
        <span>{profile.domain || 'Multi-Domain Analytics'}</span>
        <span>{profile.measures_analyzed || 0} measures analyzed</span>
        <span>{Number(profile.row_count || 0).toLocaleString()} source records</span>
        <span>Units: source scale</span>
      </div>

      <div className="decision-analysis-grid">
        {/* Visual Segment Comparison (ECharts Bar) */}
        <section className="decision-panel">
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.75rem' }}>
            <h3>Segment Variance</h3>
            {profile.comparisons?.length > 0 && (
              <label className="decision-select-label" style={{ margin: 0 }}>
                <select
                  value={comparisonIndex}
                  onChange={(e) => setComparisonIndex(Number(e.target.value))}
                >
                  {profile.comparisons.map((c, i) => (
                    <option value={i} key={`${c.metric}:${c.dimension}`}>
                      {c.metric} by {c.dimension}
                    </option>
                  ))}
                </select>
              </label>
            )}
          </div>
          {comparison ? (
            <ExecutiveBarComparisonChart
              groups={comparison.groups || []}
              metricName={comparison.metric || 'Metric'}
              baseline={comparison.baseline}
              focusGroup={comparison.focus_group}
              height={270}
            />
          ) : (
            <p className="decision-empty">No segment comparison available.</p>
          )}
        </section>

        {/* Visual Metric Correlation Heatmap (ECharts Heatmap) */}
        <section className="decision-panel">
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.75rem' }}>
            <h3>Relationship Heatmap</h3>
            <button
              type="button"
              className="decision-link"
              onClick={onExplore}
              style={{ fontSize: '0.75rem' }}
            >
              Full Matrix in Explorer <ArrowRight size={11} />
            </button>
          </div>
          {matrix ? (
            <ExecutiveHeatmapChart
              matrix={matrix}
              onSelectPair={() => onExplore && onExplore()}
              height={270}
            />
          ) : (
            <p className="decision-empty">Insufficient numeric measures for correlation.</p>
          )}
        </section>
      </div>

      {/* Visual Timeline Trend (ECharts Spline Area) */}
      {trends.length > 0 && trends[0]?.points?.length > 0 && (
        <section className="decision-panel decision-monthly" style={{ marginTop: '1.5rem' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.75rem' }}>
            <h3>Monthly Chronological Trajectory</h3>
            <span style={{ fontSize: '0.75rem', color: '#94a3b8' }}>
              {trends[0].metric} · Continuous Monthly Mean
            </span>
          </div>
          <ExecutiveTrendChart
            points={trends[0].points}
            metricName={trends[0].metric}
            height={220}
            accentColor="#63cfb3"
          />
        </section>
      )}

      {/* Governance & Field Interpretation */}
      <details className="decision-governance" style={{ marginTop: '1.5rem' }}>
        <summary>
          <Info size={16} /> Coverage, field interpretation & boundaries
        </summary>
        <ul>
          {(profile.limitations || []).map((l) => (
            <li key={l}>{l}</li>
          ))}
        </ul>
        <div className="decision-field-list">
          {(profile.fields || []).map((f) => (
            <span key={f.column}>
              <strong>{f.column}</strong>
              {(f.role || '').replaceAll('_', ' ')}
            </span>
          ))}
        </div>
        <p>
          {data.prioritization} Snapshot: {data.snapshot}
        </p>
        <button type="button" className="decision-link" onClick={onExplore}>
          <Database size={13} style={{ marginRight: 4 }} />
          Inspect uploaded records & statistics in Data Explorer <ArrowRight size={14} />
        </button>
      </details>

      {/* Brief Presentation Modal */}
      {present && (
        <BriefPresentation data={data} onClose={() => setPresent(false)} onExplore={onExplore} />
      )}

      {/* Slide-Over Evidence Drawer */}
      <EvidenceDrawer
        isOpen={drawerFinding != null}
        onClose={() => setDrawerFinding(null)}
        finding={drawerFinding}
        onNavigateExplorer={onExplore}
      />
    </section>
  );
}
