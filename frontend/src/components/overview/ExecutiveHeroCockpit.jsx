import React from 'react';
import {
  Sparkles,
  Presentation,
  Download,
  Volume2,
  FileSpreadsheet,
  Database,
  ArrowUpRight,
  ShieldCheck
} from 'lucide-react';
import ExecutiveGaugeChart from '../charts/ExecutiveGaugeChart';

export default function ExecutiveHeroCockpit({
  baseData,
  selectedSheet,
  findingsCount = 0,
  healthScore = 84,
  onLaunchBriefing,
  onOpenDeckStudio,
  onExportHtml,
  onExplore
}) {
  const sheetName = selectedSheet
    ? (selectedSheet.display_name || selectedSheet.name)
    : 'Consolidated Enterprise View';

  const domain = selectedSheet?.domain || 'Multi-Domain Analytics';
  const rowCount = selectedSheet?.row_count != null ? selectedSheet.row_count : baseData?.stats?.rows || 0;
  const colCount = selectedSheet?.columns?.length || baseData?.stats?.linked_relationships || 0;

  return (
    <section className="executive-hero-cockpit">
      <div className="hero-cockpit-content">
        <div className="hero-status-pill-group">
          <span className="hero-domain-pill">
            <Sparkles size={13} className="hero-icon-pulse" /> {domain}
          </span>
          <span className="hero-security-pill">
            <ShieldCheck size={13} /> Decision-Ready Ledger
          </span>
        </div>

        <h1 className="hero-cockpit-title">{sheetName}</h1>
        <p className="hero-cockpit-subtitle">
          Executive telemetry, domain-adaptive signal detection, and verified leadership action vectors.
        </p>

        <div className="hero-kpi-summary-strip">
          <div className="hero-mini-kpi">
            <span className="mini-kpi-label">Analyzed Records</span>
            <strong className="mini-kpi-value">{Number(rowCount).toLocaleString()}</strong>
          </div>
          <div className="hero-mini-kpi-divider" />
          <div className="hero-mini-kpi">
            <span className="mini-kpi-label">Core Vectors</span>
            <strong className="mini-kpi-value">{colCount} Dimensions</strong>
          </div>
          <div className="hero-mini-kpi-divider" />
          <div className="hero-mini-kpi">
            <span className="mini-kpi-label">Verified Findings</span>
            <strong className="mini-kpi-value">{findingsCount} Actionable</strong>
          </div>
        </div>

        <div className="hero-actions-bar">
          {onLaunchBriefing && (
            <button
              type="button"
              className="btn-hero-primary"
              onClick={onLaunchBriefing}
              title="Launch interactive slide presentation modal"
            >
              <Presentation size={15} />
              <span>Present Briefing</span>
            </button>
          )}

          {onOpenDeckStudio && (
            <button
              type="button"
              className="btn-hero-secondary"
              onClick={onOpenDeckStudio}
              title="Open full slide studio and acoustic presenter"
            >
              <Volume2 size={15} />
              <span>Acoustic Presenter</span>
            </button>
          )}

          {onExportHtml && (
            <button
              type="button"
              className="btn-hero-ghost"
              onClick={onExportHtml}
              title="Download standalone HTML executive briefing"
            >
              <Download size={14} />
              <span>Export Brief</span>
            </button>
          )}

          {onExplore && (
            <button
              type="button"
              className="btn-hero-ghost"
              onClick={onExplore}
              title="Open data explorer workbench"
            >
              <Database size={14} />
              <span>Data Explorer</span>
              <ArrowUpRight size={13} />
            </button>
          )}
        </div>
      </div>

      <div className="hero-cockpit-gauge">
        <ExecutiveGaugeChart
          score={healthScore}
          title="Data Reliability"
          subtitle="Audit Integrity"
          height={175}
        />
      </div>
    </section>
  );
}
