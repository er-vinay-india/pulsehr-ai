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
import HighviewSidePanel from "../../design-system/components/HighviewSidePanel";
import Button from "../../design-system/components/Button";
import { formatGovernedNumber, formatExactMeasure, parseGovernedNumber } from "../../utils/numericDisplayFormatter";

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

  const priorityIntents = new Set(["TARGET_VS_ACTUAL", "MATRIX", "COMPOSITION", "RANKING", "GEOSPATIAL"]);
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
      className="unified-executive-insights-grid unified-dataset-insights-section"
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
                border: `1px solid ${themeTokens.colors.gold || "var(--color-gold, var(--color-warning))"}`,
                color: isDark ? "rgba(251, 191, 36, 1)" : "rgba(180, 83, 9, 1)",
                fontSize: "0.80rem",
                marginBottom: "8px",
              }}
            >
              <AlertTriangle size={14} aria-hidden="true" />
              <span>{critical[0]}</span>
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
          data-ai-section="priority_decisions"
          data-analytical-family="LEADERSHIP_FOCUS"
        >
          <SectionHeader
            id="section-priority-heading"
            title="Priority Decisions"
            sectionType="priority_decisions"
            analyticalFamily="LEADERSHIP_FOCUS"
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
          data-ai-section="diagnostic_insights"
          data-analytical-family="DISTRIBUTION_VARIANCE"
        >
          <SectionHeader
            id="section-diagnostics-heading"
            title="Diagnostic Insights"
            sectionType="diagnostic_insights"
            analyticalFamily="DISTRIBUTION_VARIANCE"
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
          data-ai-section="supporting_analysis"
          data-analytical-family="COMPARATIVE_BENCHMARKS"
        >
          <SectionHeader
            id="section-supporting-heading"
            title="Supporting Analysis"
            sectionType="supporting_analysis"
            analyticalFamily="COMPARATIVE_BENCHMARKS"
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
          data-ai-section="scenario_analysis"
          data-analytical-family="DECISION_SIMULATOR"
        >
          <SectionHeader
            id="section-scenario-heading"
            title="Scenario Analysis"
            sectionType="scenario_analysis"
            analyticalFamily="DECISION_SIMULATOR"
          />
          <div className="scenario-summary-wrapper" style={{ marginTop: "4px" }}>
            <ScenarioSummaryCard
              themeTokens={themeTokens}
              isDark={isDark}
              domainProfile={domainProfile}
              onExplain={() => onInspectInsight && onInspectInsight({
                topic_id: "scenario_methodology",
                title: "Policy Scenario Simulation",
                analytical_intent: "SCENARIO_SIMULATION",
                primary_takeaway: "Counterfactual policy replay evaluating organizational compliance and capacity across thresholds."
              })}
            />
          </div>
        </section>
      )}

      {/* Governed KPI Audit Detail Side Panel (Slides in from the RIGHT edge) */}
      <HighviewSidePanel
        isOpen={Boolean(activeKpiEvidence)}
        onClose={() => setActiveKpiEvidence(null)}
        title={activeKpiEvidence ? `${activeKpiEvidence.label} Audit Detail` : "KPI Audit Detail"}
        subtitle="Calculation methodology & verified ground truth evidence"
        icon={ShieldCheck}
        badge="Verified"
        breadcrumbs={["Workspace", "Dashboard", "KPI Audit"]}
        width="520px"
        maxWidth="92vw"
        ariaLabel={activeKpiEvidence ? `${activeKpiEvidence.label} Audit Detail` : "KPI Audit Detail"}
        className="kpi-side-panel"
        footer={
          <div style={{ display: "flex", justifyContent: "flex-end", width: "100%" }}>
            <Button
              variant="GHOST"
              size="sm"
              onClick={() => setActiveKpiEvidence(null)}
              ariaLabel="Close KPI audit panel"
            >
              Close
            </Button>
          </div>
        }
      >
        {activeKpiEvidence && (
          <div style={{ display: "flex", flexDirection: "column", gap: "18px" }}>
            <div>
              <span
                style={{
                  fontSize: "0.74rem",
                  fontWeight: 700,
                  textTransform: "uppercase",
                  letterSpacing: "0.05em",
                  color: "var(--color-text-muted, #3C5059)",
                }}
              >
                Audited Value
              </span>
              {(() => {
                const rawVal = activeKpiEvidence.value;
                const hasRaw = rawVal != null && rawVal !== "" && parseGovernedNumber(rawVal) !== null;
                const semanticOpts = {
                  unit: activeKpiEvidence.unit,
                  metric_id: activeKpiEvidence.kpi_id,
                  label: activeKpiEvidence.label,
                  measure_class: activeKpiEvidence.measure_class,
                  currency: activeKpiEvidence.currency,
                };
                const displayVal = hasRaw
                  ? formatGovernedNumber(rawVal, semanticOpts)
                  : (activeKpiEvidence.formatted_value || "—");
                const exactVal = hasRaw
                  ? formatExactMeasure(rawVal, semanticOpts)
                  : (activeKpiEvidence.exact_value_text || activeKpiEvidence.formatted_value || displayVal);

                return (
                  <div>
                    <div
                      className="quick-inspect-display-value"
                      style={{
                        fontSize: "2rem",
                        fontWeight: 800,
                        color: "var(--color-brand-primary, #183B56)",
                        lineHeight: 1.2,
                        marginTop: "2px",
                      }}
                    >
                      {displayVal}
                    </div>
                    {hasRaw && exactVal !== displayVal && (
                      <div
                        className="quick-inspect-exact-value"
                        style={{
                          fontSize: "0.90rem",
                          fontWeight: 600,
                          color: "var(--color-text-secondary, #334B57)",
                          marginTop: "4px",
                        }}
                      >
                        <span style={{ fontSize: "0.72rem", textTransform: "uppercase", letterSpacing: "0.04em", color: "var(--color-text-muted, #3C5059)", marginRight: "6px" }}>
                          Exact Value:
                        </span>
                        {exactVal}
                      </div>
                    )}
                  </div>
                );
              })()}
              {activeKpiEvidence.subtext && (
                <p
                  style={{
                    margin: "4px 0 0 0",
                    fontSize: "0.85rem",
                    color: "var(--color-text-secondary, #334B57)",
                  }}
                >
                  {activeKpiEvidence.subtext}
                </p>
              )}
            </div>

            {activeKpiEvidence.definition && (
              <div>
                <h4
                  style={{
                    margin: "0 0 4px 0",
                    fontSize: "0.75rem",
                    fontWeight: 700,
                    textTransform: "uppercase",
                    letterSpacing: "0.05em",
                    color: "var(--color-text-muted, #3C5059)",
                  }}
                >
                  Business Definition
                </h4>
                <p
                  style={{
                    margin: 0,
                    fontSize: "0.90rem",
                    color: "var(--color-text-primary, #172B3A)",
                    lineHeight: 1.5,
                  }}
                >
                  {activeKpiEvidence.definition}
                </p>
              </div>
            )}

            {activeKpiEvidence.calculation && (
              <div>
                <h4
                  style={{
                    margin: "0 0 4px 0",
                    fontSize: "0.75rem",
                    fontWeight: 700,
                    textTransform: "uppercase",
                    letterSpacing: "0.05em",
                    color: "var(--color-text-muted, #3C5059)",
                  }}
                >
                  Calculation Formula
                </h4>
                <pre
                  style={{
                    margin: 0,
                    padding: "10px 14px",
                    borderRadius: "8px",
                    backgroundColor: isDark ? "rgba(15, 23, 42, 0.8)" : "rgba(241, 245, 249, 0.8)",
                    border: "1px solid var(--color-border, #D4DDD6)",
                    fontSize: "0.80rem",
                    fontFamily: "monospace",
                    overflowX: "auto",
                    color: "var(--color-text-primary, #172B3A)",
                  }}
                >
                  {activeKpiEvidence.calculation}
                </pre>
              </div>
            )}

            <div
              style={{
                display: "flex",
                flexDirection: "column",
                gap: "8px",
                paddingTop: "14px",
                borderTop: "1px solid var(--color-border, #D4DDD6)",
                fontSize: "0.78rem",
                color: "var(--color-text-muted, #3C5059)",
              }}
            >
              <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                <ShieldCheck size={16} color="var(--color-success, #075443)" aria-hidden="true" />
                <span>Verified single-domain calculation · Zero synthetic data</span>
              </div>
              {activeKpiEvidence.evidence_id && (
                <div style={{ fontFamily: "monospace", fontSize: "0.74rem" }}>
                  Evidence ID: <code>{activeKpiEvidence.evidence_id}</code>
                </div>
              )}
            </div>
          </div>
        )}
      </HighviewSidePanel>
    </div>
  );
}
