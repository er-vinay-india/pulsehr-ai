import React, { useState, useMemo } from "react";
import {
  Sparkles,
  GitMerge,
  AlertCircle,
  ExternalLink,
  ShieldCheck,
  Layers,
  TrendingUp,
  CheckCircle2,
  ArrowRight,
  BarChart3,
  AlertTriangle,
  Info,
  X,
} from "lucide-react";
import { useTheme } from "../../context/ThemeContext";
import { getThemeTokens } from "../../theme/tokens";
import ExecutiveVisualStory from "./ExecutiveVisualStory";
import ScenarioSummaryCard from "./ScenarioSummaryCard";

/**
 * Hard token validator guaranteeing zero unresolved {token} variables reach the UI.
 */
function sanitizeTemplateText(text, fallback = "") {
  if (!text || typeof text !== "string") return fallback;
  const tokenRegex = /\{[a-zA-Z0-9_]+\}/g;
  if (tokenRegex.test(text)) {
    return text.replace(tokenRegex, "").replace(/\s{2,}/g, " ").trim() || fallback;
  }
  return text;
}

export default function UnifiedExecutiveInsightsGrid({
  insights = [],
  executiveTopics = [],
  executiveKpis = [],
  coverageWarnings = [],
  datasetName = "",
  datasetId = null,
  sheetCount = 1,
  domainProfile = null,
  onInspectInsight,
  onOpenScenarioExplorer,
}) {
  const { isDark } = useTheme();
  const themeTokens = getThemeTokens(isDark);

  // Active KPI modal evidence inspector state
  const [activeKpiEvidence, setActiveKpiEvidence] = useState(null);

  // Dynamic Domain Subtitle
  const domainSubtitle = useMemo(() => {
    const rawTpl = domainProfile?.display_subtitle;
    if (rawTpl) {
      return rawTpl
        .replace("{count}", sheetCount)
        .replace("{sources}", sheetCount === 1 ? "source" : "sources");
    }
    const domainName = domainProfile?.display_domain_name;
    if (domainName) {
      return `Synthesized ${domainName.toLowerCase()} insights across ${sheetCount} reconciled ${sheetCount === 1 ? "source" : "sources"}`;
    }
    return `Synthesized business insights across ${sheetCount} reconciled ${sheetCount === 1 ? "source" : "sources"}`;
  }, [domainProfile, sheetCount]);

  // Extract Hero Topic & Supporting Topics
  const heroTopic = useMemo(() => {
    if (!executiveTopics || executiveTopics.length === 0) return null;
    return executiveTopics.find((t) => t.slot_type === "hero") || executiveTopics[0];
  }, [executiveTopics]);

  const supportingTopics = useMemo(() => {
    if (!executiveTopics || executiveTopics.length === 0) return [];
    return executiveTopics.filter((t) => t !== heroTopic);
  }, [executiveTopics, heroTopic]);

  return (
    <section
      className="unified-executive-insights-grid"
      aria-label="Unified Executive Intelligence Dashboard"
      style={{ display: "flex", flexDirection: "column", gap: "20px" }}
    >
      {/* 1. DOMAIN KPI STRIP (Stable, Governed Domain Metrics Layer) */}
      <div
        className="executive-kpi-strip"
        role="region"
        aria-label="Executive KPI Overview"
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))",
          gap: "12px",
        }}
      >
        {executiveKpis.map((kpi, idx) => (
          <article
            key={kpi.kpi_id || idx}
            className="kpi-card"
            data-testid={`kpi-card-${kpi.kpi_id}`}
            onClick={() => setActiveKpiEvidence(kpi)}
            style={{
              backgroundColor: themeTokens.colors.surface,
              border: `1px solid ${themeTokens.colors.borderSubtle}`,
              borderRadius: "10px",
              padding: "14px 16px",
              cursor: "pointer",
              transition: "transform 0.15s ease, box-shadow 0.15s ease",
            }}
          >
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline" }}>
              <span
                style={{
                  fontSize: "0.74rem",
                  fontWeight: 600,
                  color: themeTokens.colors.textSecondary,
                  textTransform: "uppercase",
                  letterSpacing: "0.03em",
                }}
              >
                {kpi.label}
              </span>
              <Info size={12} color={themeTokens.colors.textMuted} />
            </div>

            <div style={{ margin: "6px 0 2px 0", display: "flex", alignItems: "baseline", gap: "6px" }}>
              <span
                style={{
                  fontSize: "1.45rem",
                  fontWeight: 800,
                  color: themeTokens.colors.textPrimary,
                  letterSpacing: "-0.02em",
                }}
              >
                {kpi.formatted_value || `${kpi.value}${kpi.unit || ""}`}
              </span>
              {kpi.variance && (
                <span
                  style={{
                    fontSize: "0.76rem",
                    fontWeight: 600,
                    color: kpi.variance.startsWith("+")
                      ? themeTokens.colors.statusSuccess || "#10b981"
                      : themeTokens.colors.statusError || "#ef4444",
                  }}
                >
                  {kpi.variance}
                </span>
              )}
            </div>

            <div style={{ fontSize: "0.72rem", color: themeTokens.colors.textMuted }}>
              {kpi.subtext || `Audited across ${kpi.population || "all"} records`}
            </div>
          </article>
        ))}
      </div>

      {/* Coverage Warnings Banner if present */}
      {coverageWarnings && coverageWarnings.length > 0 && (
        <div
          className="coverage-warning-banner"
          role="status"
          style={{
            display: "flex",
            alignItems: "center",
            gap: "8px",
            padding: "8px 14px",
            borderRadius: "8px",
            backgroundColor: "rgba(245, 158, 11, 0.10)",
            border: `1px solid ${themeTokens.colors.gold || "#f59e0b"}`,
            color: isDark ? "#fbbf24" : "#b45309",
            fontSize: "0.80rem",
          }}
        >
          <AlertTriangle size={14} />
          <span>{coverageWarnings[0]}</span>
        </div>
      )}

      {/* 2. HERO VISUAL STORY (Dominant Anchor Visual) */}
      {heroTopic && (
        <div className="hero-visual-wrapper" data-testid="hero-visual-wrapper">
          <ExecutiveVisualStory
            topic={heroTopic}
            isHero={true}
            datasetId={datasetId}
            themeTokens={themeTokens}
            isDark={isDark}
            onInspect={onInspectInsight}
          />
        </div>
      )}

      {/* 3. SUPPORTING VISUAL STORIES & TOOL CARDS (Generic Visual Contract) */}
      <div
        className="supporting-visuals-grid"
        data-testid="supporting-visuals-grid"
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fit, minmax(min(100%, 450px), 1fr))",
          gap: "16px",
        }}
      >
        {supportingTopics.map((topic) => (
          <ExecutiveVisualStory
            key={topic.topic_id}
            topic={topic}
            isHero={false}
            datasetId={datasetId}
            themeTokens={themeTokens}
            isDark={isDark}
            onInspect={onInspectInsight}
          />
        ))}

        {/* Compact Scenario Summary Tool Card - Governed by domain entitlement */}
        {(domainProfile?.governed_scenario_domain || domainProfile?.domain === "workforce") && (
          <ScenarioSummaryCard
            themeTokens={themeTokens}
            isDark={isDark}
            onOpenExplorer={onOpenScenarioExplorer}
          />
        )}
      </div>

      {/* Governed KPI Evidence Drill-down Modal */}
      {activeKpiEvidence && (
        <div
          className="kpi-modal-backdrop"
          role="dialog"
          aria-modal="true"
          onClick={() => setActiveKpiEvidence(null)}
          style={{
            position: "fixed",
            top: 0,
            left: 0,
            right: 0,
            bottom: 0,
            backgroundColor: "rgba(0, 0, 0, 0.5)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            zIndex: 1000,
          }}
        >
          <div
            className="kpi-modal-card"
            onClick={(e) => e.stopPropagation()}
            style={{
              backgroundColor: themeTokens.colors.surface,
              borderRadius: "12px",
              padding: "20px 24px",
              maxWidth: "460px",
              width: "90%",
              boxShadow: "0 10px 25px rgba(0,0,0,0.2)",
              border: `1px solid ${themeTokens.colors.borderSubtle}`,
            }}
          >
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "12px" }}>
              <h3 style={{ margin: 0, fontSize: "1.1rem", fontWeight: 700, color: themeTokens.colors.textPrimary }}>
                {activeKpiEvidence.label} Audit Detail
              </h3>
              <button
                type="button"
                onClick={() => setActiveKpiEvidence(null)}
                style={{ background: "transparent", border: "none", cursor: "pointer", color: themeTokens.colors.textMuted }}
              >
                <X size={18} />
              </button>
            </div>

            <div style={{ display: "flex", flexDirection: "column", gap: "10px", fontSize: "0.84rem" }}>
              <div>
                <span style={{ fontWeight: 600, color: themeTokens.colors.textSecondary }}>Value:</span>{" "}
                <strong style={{ color: themeTokens.colors.textPrimary }}>
                  {activeKpiEvidence.formatted_value || activeKpiEvidence.value}
                </strong>
              </div>
              {activeKpiEvidence.definition && (
                <div>
                  <span style={{ fontWeight: 600, color: themeTokens.colors.textSecondary }}>Definition:</span>
                  <p style={{ margin: "3px 0 0 0", color: themeTokens.colors.textPrimary }}>
                    {activeKpiEvidence.definition}
                  </p>
                </div>
              )}
              {activeKpiEvidence.calculation && (
                <div>
                  <span style={{ fontWeight: 600, color: themeTokens.colors.textSecondary }}>Formula:</span>
                  <pre
                    style={{
                      margin: "4px 0 0 0",
                      padding: "6px 8px",
                      borderRadius: "6px",
                      backgroundColor: isDark ? "#0f172a" : "#f1f5f9",
                      fontSize: "0.78rem",
                      overflowX: "auto",
                    }}
                  >
                    {activeKpiEvidence.calculation}
                  </pre>
                </div>
              )}
              {activeKpiEvidence.evidence_id && (
                <div style={{ fontSize: "0.76rem", color: themeTokens.colors.textMuted, marginTop: "4px" }}>
                  Evidence ID: <code>{activeKpiEvidence.evidence_id}</code>
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </section>
  );
}
