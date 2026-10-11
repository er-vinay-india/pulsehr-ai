import React, { useState, useMemo, useEffect, useRef } from "react";
import ReactDOM from "react-dom";
import { AlertTriangle, X, ShieldCheck } from "lucide-react";
import { useTheme } from "../../context/ThemeContext";
import { getThemeTokens } from "../../theme/tokens";
import ExecutiveKPIGrid from "./ExecutiveKPIGrid";
import ExecutiveVisualCard from "./ExecutiveVisualCard";
import ExecutiveVisualGrid from "./ExecutiveVisualGrid";
import SectionHeader from "./SectionHeader";
import ScenarioSummaryCard from "./ScenarioSummaryCard";

/**
 * Partition executive visual topics into logical decision tiers:
 * Uses server-driven spatial_placement.section_id from SpatialCompositionOptimizer.
 * Falls back to deterministic heuristic if spatial_placement is absent.
 */
function partitionTopics(topics, layoutPlan = null) {
  if (!topics || topics.length === 0) {
    return { priority: [], diagnostic: [], supporting: [] };
  }

  // 1. Authoritative Server-Driven Spatial Partition
  const hasSpatialSections = topics.some((t) => Boolean(t.spatial_placement?.section_id));
  if (hasSpatialSections) {
    const priority = topics
      .filter((t) => t.spatial_placement?.section_id === "priority")
      .sort((a, b) => (a.spatial_placement?.order_index ?? 0) - (b.spatial_placement?.order_index ?? 0));
    const diagnostic = topics
      .filter((t) => t.spatial_placement?.section_id === "diagnostic")
      .sort((a, b) => (a.spatial_placement?.order_index ?? 0) - (b.spatial_placement?.order_index ?? 0));
    const supporting = topics
      .filter((t) => t.spatial_placement?.section_id === "supporting")
      .sort((a, b) => (a.spatial_placement?.order_index ?? 0) - (b.spatial_placement?.order_index ?? 0));
    return { priority, diagnostic, supporting };
  }

  // 2. Fallback Heuristic
  if (topics.length <= 4) {
    return {
      priority: [topics[0]],
      diagnostic: topics.slice(1),
      supporting: [],
    };
  }

  const heroIndex = topics.findIndex((t) => t.slot_type === "hero");
  const hero = heroIndex >= 0 ? topics[heroIndex] : topics[0];
  const remaining = topics.filter((t) => t !== hero);

  const priorityIntents = new Set(["TARGET_VS_ACTUAL", "MATRIX", "COMPOSITION", "RANKING"]);
  const diagnosticIntents = new Set(["DISTRIBUTION", "RELATIONSHIP", "ANOMALY", "VARIANCE"]);

  const priority = [hero];
  const diagnostic = [];
  const supporting = [];

  for (const t of remaining) {
    if (
      priority.length < 3 &&
      (t.layout_hint === "LARGE" || priorityIntents.has(t.analytical_intent))
    ) {
      priority.push(t);
    } else if (
      diagnosticIntents.has(t.analytical_intent) ||
      t.visual_spec?.chart_type === "podium_top_3" ||
      t.visual_spec?.chart_type === "box_plot" ||
      t.visual_spec?.chart_type === "scatter"
    ) {
      diagnostic.push(t);
    } else {
      supporting.push(t);
    }
  }

  if (diagnostic.length === 0 && supporting.length > 0) {
    diagnostic.push(...supporting.splice(0, Math.ceil(supporting.length / 2)));
  }

  return { priority, diagnostic, supporting };
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
  layoutPlan = null,
  onInspectInsight,
  onOpenScenarioExplorer,
}) {
  const { isDark } = useTheme();
  const themeTokens = getThemeTokens(isDark);

  // Active KPI modal evidence inspector state
  const [activeKpiEvidence, setActiveKpiEvidence] = useState(null);
  const kpiModalRef = useRef(null);

  // ESC key for KPI audit modal
  useEffect(() => {
    if (activeKpiEvidence) {
      const handleKeyDown = (e) => {
        if (e.key === "Escape") {
          e.preventDefault();
          setActiveKpiEvidence(null);
        }
      };
      window.addEventListener("keydown", handleKeyDown);
      return () => window.removeEventListener("keydown", handleKeyDown);
    }
  }, [activeKpiEvidence]);

  // Partition topics across decision tiers
  const { priority, diagnostic, supporting } = useMemo(
    () => partitionTopics(executiveTopics, layoutPlan),
    [executiveTopics, layoutPlan]
  );

  return (
    <div
      className="unified-executive-insights-grid"
      style={{ display: "flex", flexDirection: "column", gap: "28px" }}
    >
      {/* 1. KEY METRICS SECTION (Semantic H2 + dl/dt/dd KPI Grid) */}
      <section
        className="dashboard-section dashboard-section--kpis"
        aria-labelledby="section-kpis-heading"
      >
        <h2 id="section-kpis-heading" className="sr-only">
          Key Performance Indicators
        </h2>
        <ExecutiveKPIGrid
          kpis={executiveKpis}
          onSelectKpi={setActiveKpiEvidence}
          themeTokens={themeTokens}
          isDark={isDark}
        />
      </section>

      {/* Governance Status & Critical Coverage Warnings */}
      {(() => {
        if (!coverageWarnings || coverageWarnings.length === 0) return null;
        const isCritical = (w) => {
          const l = (w || "").toLowerCase();
          return (
            l.includes("insufficient evidence") ||
            l.includes("domain conflict") ||
            l.includes("coverage gap") ||
            l.includes("integrity failure") ||
            l.includes("error") ||
            l.includes("unverified")
          );
        };
        const critical = coverageWarnings.filter(isCritical);
        const informational = coverageWarnings.filter((w) => !isCritical(w));

        if (critical.length > 0) {
          return (
            <div
              className="coverage-warning-banner"
              role="alert"
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
                marginBottom: "8px",
              }}
            >
              <AlertTriangle size={14} aria-hidden="true" />
              <span>{critical[0]}</span>
            </div>
          );
        }

        if (informational.length > 0) {
          return (
            <div
              className="governance-status-compact"
              role="status"
              style={{
                display: "flex",
                alignItems: "center",
                gap: "6px",
                padding: "2px 0 8px 4px",
                fontSize: "0.75rem",
                color: "var(--color-text-muted, #78877f)",
              }}
            >
              <ShieldCheck size={13} style={{ color: "var(--color-success, #075443)" }} aria-hidden="true" />
              <span style={{ fontWeight: 600, color: "var(--color-text-secondary, #334b57)" }}>Governance ✓</span>
              <span style={{ opacity: 0.85 }}>Verified Single-Domain Analysis</span>
            </div>
          );
        }

        return null;
      })()}

      {/* 2. PRIORITY DECISIONS SECTION (Hero + Core Decision Anchors) */}
      {priority.length > 0 && (
        <section
          className="dashboard-section dashboard-section--priority"
          aria-labelledby="section-priority-heading"
        >
          <SectionHeader
            id="section-priority-heading"
            title="Priority Decisions"
            badge="Leadership Focus"
            subtitle="Core policy compliance benchmarks, period cross-tabulations, and operational allocations."
          />
          <ExecutiveVisualGrid
            className="priority-visuals-grid"
            data-testid="priority-visuals-grid"
          >
            {priority.map((topic, idx) => (
              <ExecutiveVisualCard
                key={topic.topic_id || idx}
                topic={topic}
                isHero={idx === 0 && (topic.slot_type === "hero" || topic.layout_hint === "HERO")}
                datasetId={datasetId}
                themeTokens={themeTokens}
                isDark={isDark}
                onInspect={onInspectInsight}
              />
            ))}
          </ExecutiveVisualGrid>
        </section>
      )}

      {/* 3. DIAGNOSTIC INSIGHTS SECTION (Distributions, Relationships, Benchmark Leaders) */}
      {diagnostic.length > 0 && (
        <section
          className="dashboard-section dashboard-section--diagnostics"
          aria-labelledby="section-diagnostics-heading"
        >
          <SectionHeader
            id="section-diagnostics-heading"
            title="Diagnostic Insights"
            badge="Distributions & Variance"
            subtitle="Underlying statistical distributions, bivariate associations, and top benchmark performers."
          />
          <ExecutiveVisualGrid
            className="diagnostic-visuals-grid"
            data-testid="diagnostic-visuals-grid"
          >
            {diagnostic.map((topic, idx) => (
              <ExecutiveVisualCard
                key={topic.topic_id || idx}
                topic={topic}
                isHero={false}
                datasetId={datasetId}
                themeTokens={themeTokens}
                isDark={isDark}
                onInspect={onInspectInsight}
              />
            ))}
          </ExecutiveVisualGrid>
        </section>
      )}

      {/* 4. SUPPORTING ANALYSIS SECTION (Comparative Breakdowns & Outliers) */}
      {supporting.length > 0 && (
        <section
          className="dashboard-section dashboard-section--supporting"
          aria-labelledby="section-supporting-heading"
        >
          <SectionHeader
            id="section-supporting-heading"
            title="Supporting Analysis"
            badge="Comparative Benchmarks"
            subtitle="Entity-level comparative breakdowns and anomaly concentration patterns."
          />
          <ExecutiveVisualGrid
            className="supporting-visuals-grid"
            data-testid="supporting-visuals-grid"
          >
            {supporting.map((topic, idx) => (
              <ExecutiveVisualCard
                key={topic.topic_id || idx}
                topic={topic}
                isHero={false}
                datasetId={datasetId}
                themeTokens={themeTokens}
                isDark={isDark}
                onInspect={onInspectInsight}
              />
            ))}
          </ExecutiveVisualGrid>
        </section>
      )}

      {/* 5. SCENARIO ANALYSIS SECTION (Governed by Domain Entitlement) */}
      {(domainProfile?.governed_scenario_domain || domainProfile?.domain === "workforce") && (
        <section
          className="dashboard-section dashboard-section--scenario"
          aria-labelledby="section-scenario-heading"
        >
          <SectionHeader
            id="section-scenario-heading"
            title="Scenario Analysis"
            badge="Decision Simulator"
            subtitle="Interactive policy what-if models and threshold impact forecasting."
          />
          <div className="scenario-summary-wrapper" style={{ marginTop: "4px" }}>
            <ScenarioSummaryCard
              themeTokens={themeTokens}
              isDark={isDark}
              onOpenExplorer={onOpenScenarioExplorer}
            />
          </div>
        </section>
      )}

      {/* Accessible KPI Evidence Drill-down Modal rendered via Portal */}
      {activeKpiEvidence &&
        typeof document !== "undefined" &&
        ReactDOM.createPortal(
          <div
            className="kpi-modal-backdrop"
            onClick={() => setActiveKpiEvidence(null)}
            role="presentation"
            style={{
              position: "fixed",
              top: 0,
              left: 0,
              right: 0,
              bottom: 0,
              backgroundColor: "rgba(0, 0, 0, 0.5)",
              backdropFilter: "blur(4px)",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              zIndex: 9999,
              padding: "16px",
            }}
          >
            <dialog
              open
              ref={kpiModalRef}
              className="kpi-modal-card"
              role="dialog"
              aria-modal="true"
              aria-labelledby="kpi-audit-modal-title"
              onClick={(e) => e.stopPropagation()}
              tabIndex={-1}
              style={{
                margin: 0,
                backgroundColor: themeTokens.colors.surface,
                borderRadius: "12px",
                padding: "20px 24px",
                maxWidth: "460px",
                width: "100%",
                boxShadow: "0 10px 25px rgba(0,0,0,0.2)",
                border: `1px solid ${themeTokens.colors.borderSubtle}`,
                color: themeTokens.colors.textPrimary,
              }}
            >
              <div
                style={{
                  display: "flex",
                  justifyContent: "space-between",
                  alignItems: "center",
                  marginBottom: "12px",
                }}
              >
                <h3
                  id="kpi-audit-modal-title"
                  style={{
                    margin: 0,
                    fontSize: "1.1rem",
                    fontWeight: 700,
                    color: themeTokens.colors.textPrimary,
                  }}
                >
                  {activeKpiEvidence.label} Audit Detail
                </h3>
                <button
                  type="button"
                  onClick={() => setActiveKpiEvidence(null)}
                  aria-label="Close KPI audit modal"
                  style={{
                    background: "transparent",
                    border: "none",
                    cursor: "pointer",
                    color: themeTokens.colors.textMuted,
                    padding: "4px",
                    display: "flex",
                  }}
                >
                  <X size={18} aria-hidden="true" />
                </button>
              </div>

              <div
                style={{
                  display: "flex",
                  flexDirection: "column",
                  gap: "10px",
                  fontSize: "0.84rem",
                }}
              >
                <div>
                  <span style={{ fontWeight: 600, color: themeTokens.colors.textSecondary }}>
                    Value:
                  </span>{" "}
                  <strong style={{ color: themeTokens.colors.textPrimary }}>
                    {activeKpiEvidence.formatted_value || activeKpiEvidence.value}
                  </strong>
                </div>
                {activeKpiEvidence.definition && (
                  <div>
                    <span style={{ fontWeight: 600, color: themeTokens.colors.textSecondary }}>
                      Definition:
                    </span>
                    <p style={{ margin: "3px 0 0 0", color: themeTokens.colors.textPrimary }}>
                      {activeKpiEvidence.definition}
                    </p>
                  </div>
                )}
                {activeKpiEvidence.calculation && (
                  <div>
                    <span style={{ fontWeight: 600, color: themeTokens.colors.textSecondary }}>
                      Formula:
                    </span>
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
                  <div
                    style={{
                      fontSize: "0.76rem",
                      color: themeTokens.colors.textMuted,
                      marginTop: "4px",
                    }}
                  >
                    Evidence ID: <code>{activeKpiEvidence.evidence_id}</code>
                  </div>
                )}
              </div>
            </dialog>
          </div>,
          document.body
        )}
    </div>
  );
}
