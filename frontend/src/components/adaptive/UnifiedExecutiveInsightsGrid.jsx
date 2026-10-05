import React from "react";
import { Sparkles, GitMerge, AlertCircle, ExternalLink, ShieldCheck, Layers } from "lucide-react";
import { useTheme } from "../../context/ThemeContext";
import { getThemeTokens } from "../../theme/tokens";

const SLOT_CONFIG = {
  hero: {
    label: "Executive Hero Insight",
    colorKey: "gold",
    badgeBg: "var(--brand-surface-subtle, rgba(217, 119, 6, 0.12))",
    icon: Sparkles,
  },
  strategic: {
    label: "Strategic Priority",
    colorKey: "brandBlue",
    badgeBg: "var(--brand-surface-subtle, rgba(59, 130, 246, 0.12))",
    icon: Layers,
  },
  diagnostic: {
    label: "Diagnostic Deep-Dive",
    colorKey: "brandBlue",
    badgeBg: "var(--surface-muted, rgba(148, 163, 184, 0.12))",
    icon: Layers,
  },
  risk_foresight: {
    label: "Risk & Foresight",
    colorKey: "statusWarning",
    badgeBg: "var(--warning-surface, rgba(234, 179, 8, 0.12))",
    icon: AlertCircle,
  },
  action_scenario: {
    label: "Decision Scenario",
    colorKey: "statusSuccess",
    badgeBg: "var(--success-surface, rgba(16, 185, 129, 0.12))",
    icon: ShieldCheck,
  },
};

export default function UnifiedExecutiveInsightsGrid({
  insights = [],
  coverageWarnings = [],
  datasetName = "",
  sheetCount = 1,
  onInspectInsight,
}) {
  const { isDark } = useTheme();
  const themeTokens = getThemeTokens(isDark);

  if (!insights || insights.length === 0) {
    return null;
  }

  return (
    <section
      className="unified-dataset-insights-section"
      aria-labelledby="unified-insights-heading"
      style={{
        marginBottom: "28px",
        display: "flex",
        flexDirection: "column",
        gap: "16px",
      }}
    >
      {/* Section Header */}
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "flex-end",
          flexWrap: "wrap",
          gap: "12px",
          borderBottom: `1px solid ${themeTokens.colors.borderSubtle}`,
          paddingBottom: "12px",
        }}
      >
        <div>
          <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
            <span
              style={{
                display: "inline-flex",
                alignItems: "center",
                justifyContent: "center",
                width: "28px",
                height: "28px",
                borderRadius: "6px",
                backgroundColor: themeTokens.colors.softGold || "rgba(217, 119, 6, 0.15)",
                color: themeTokens.colors.gold || "var(--color-gold)",
              }}
            >
              <GitMerge size={16} />
            </span>
            <h2
              id="unified-insights-heading"
              style={{
                margin: 0,
                fontSize: "1.18rem",
                fontWeight: 700,
                color: themeTokens.colors.textPrimary,
                letterSpacing: "-0.01em",
              }}
            >
              Governed Executive Insights
            </h2>
          </div>
          <p
            style={{
              margin: "4px 0 0 36px",
              fontSize: "0.82rem",
              color: themeTokens.colors.textSecondary,
            }}
          >
            Globally ranked across {sheetCount} {sheetCount === 1 ? "sheet" : "unified sheets"} in {datasetName || "workbook"} · Budget-governed meritocratic pool
          </p>
        </div>

        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: "8px",
            fontSize: "0.78rem",
            color: themeTokens.colors.textMuted,
          }}
        >
          <span
            style={{
              padding: "4px 10px",
              borderRadius: "12px",
              backgroundColor: themeTokens.colors.surface,
              border: `1px solid ${themeTokens.colors.borderSubtle}`,
              fontWeight: 600,
            }}
          >
            {insights.length} Allocated Slots / 9 Max
          </span>
        </div>
      </div>

      {/* Coverage / Domain Balancing Advisory */}
      {coverageWarnings && coverageWarnings.length > 0 && (
        <div
          role="status"
          style={{
            display: "flex",
            alignItems: "center",
            gap: "10px",
            padding: "10px 14px",
            borderRadius: "8px",
            backgroundColor: themeTokens.colors.surface,
            border: `1px solid ${themeTokens.colors.statusWarning || "#d97706"}`,
            fontSize: "0.82rem",
            color: themeTokens.colors.textPrimary,
          }}
        >
          <AlertCircle size={16} color={themeTokens.colors.statusWarning || "#d97706"} style={{ flexShrink: 0 }} />
          <span>
            <strong>Domain Balancing Advisory:</strong> {coverageWarnings.join(" • ")}
          </span>
        </div>
      )}

      {/* Grid of GlobalRanker Candidates */}
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fit, minmax(320px, 1fr))",
          gap: "16px",
        }}
      >
        {insights.map((cand, idx) => {
          const slot = SLOT_CONFIG[cand.slot_type] || SLOT_CONFIG.strategic;
          const SlotIcon = slot.icon;
          const isCrossSheet = cand.scope === "CROSS_SHEET";
          const isHero = cand.slot_type === "hero";

          return (
            <article
              key={cand.candidate_id || `cand-${idx}`}
              className="executive-insight-card"
              style={{
                backgroundColor: themeTokens.colors.surface,
                border: `1px solid ${isHero ? themeTokens.colors.gold || "var(--color-gold)" : themeTokens.colors.borderSubtle}`,
                borderRadius: "12px",
                padding: "18px 20px",
                display: "flex",
                flexDirection: "column",
                justifyContent: "space-between",
                gap: "14px",
                boxShadow: isHero ? "0 4px 20px -2px rgba(217, 119, 6, 0.15)" : "none",
                gridColumn: isHero && insights.length > 1 ? "1 / -1" : "auto",
                transition: "transform 0.15s ease, box-shadow 0.15s ease",
              }}
            >
              <div>
                {/* Header Pills */}
                <div
                  style={{
                    display: "flex",
                    justifyContent: "space-between",
                    alignItems: "center",
                    gap: "8px",
                    marginBottom: "10px",
                    flexWrap: "wrap",
                  }}
                >
                  <span
                    style={{
                      display: "inline-flex",
                      alignItems: "center",
                      gap: "6px",
                      padding: "3px 9px",
                      borderRadius: "6px",
                      fontSize: "0.72rem",
                      fontWeight: 700,
                      letterSpacing: "0.02em",
                      textTransform: "uppercase",
                      backgroundColor: slot.badgeBg,
                      color: themeTokens.colors[slot.colorKey] || themeTokens.colors.textPrimary,
                    }}
                  >
                    <SlotIcon size={12} />
                    {slot.label}
                  </span>

                  <span
                    style={{
                      display: "inline-flex",
                      alignItems: "center",
                      gap: "5px",
                      padding: "3px 8px",
                      borderRadius: "12px",
                      fontSize: "0.70rem",
                      fontWeight: 600,
                      backgroundColor: isCrossSheet
                        ? "var(--brand-surface-subtle, rgba(99, 102, 241, 0.12))"
                        : "var(--surface-muted, rgba(148, 163, 184, 0.10))",
                      color: isCrossSheet
                        ? themeTokens.colors.brandBlue || "var(--brand-primary)"
                        : themeTokens.colors.textMuted,
                      border: `1px solid ${isCrossSheet ? "rgba(99, 102, 241, 0.3)" : themeTokens.colors.borderSubtle}`,
                    }}
                  >
                    {isCrossSheet ? <GitMerge size={11} /> : <Layers size={11} />}
                    {isCrossSheet ? "Cross-Sheet Discovery" : "Single-Sheet Scope"}
                  </span>
                </div>

                {/* Title */}
                <h3
                  style={{
                    margin: "0 0 8px 0",
                    fontSize: isHero ? "1.08rem" : "0.96rem",
                    fontWeight: 700,
                    color: themeTokens.colors.textPrimary,
                    lineHeight: 1.35,
                  }}
                >
                  {cand.title}
                </h3>

                {/* Details / Dimension / Population */}
                <div
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: "8px",
                    flexWrap: "wrap",
                    fontSize: "0.75rem",
                    color: themeTokens.colors.textMuted,
                    marginBottom: "12px",
                  }}
                >
                  {cand.dimension_name && (
                    <span style={{ fontWeight: 600, color: themeTokens.colors.textSecondary }}>
                      {cand.dimension_name}
                    </span>
                  )}
                  {cand.dimension_name && cand.metric_name && <span>•</span>}
                  {cand.metric_name && <span>{cand.metric_name}</span>}
                  {cand.population > 0 && (
                    <>
                      <span>•</span>
                      <span>{Number(cand.population).toLocaleString()} observations</span>
                    </>
                  )}
                </div>
              </div>

              {/* Metrics Bar & Evidence Links */}
              <div
                style={{
                  display: "flex",
                  justifyContent: "space-between",
                  alignItems: "center",
                  flexWrap: "wrap",
                  gap: "10px",
                  paddingTop: "12px",
                  borderTop: `1px solid ${themeTokens.colors.borderSubtle}`,
                }}
              >
                <div style={{ display: "flex", alignItems: "center", gap: "12px" }}>
                  <div style={{ display: "flex", flexDirection: "column" }}>
                    <span style={{ fontSize: "0.68rem", textTransform: "uppercase", color: themeTokens.colors.textMuted, fontWeight: 600 }}>
                      Score
                    </span>
                    <span style={{ fontSize: "0.88rem", fontWeight: 700, color: themeTokens.colors.textPrimary }}>
                      {(cand.composite_score * 100).toFixed(0)}%
                    </span>
                  </div>

                  <div style={{ display: "flex", flexDirection: "column" }}>
                    <span style={{ fontSize: "0.68rem", textTransform: "uppercase", color: themeTokens.colors.textMuted, fontWeight: 600 }}>
                      Impact
                    </span>
                    <span style={{ fontSize: "0.88rem", fontWeight: 700, color: themeTokens.colors.gold || "var(--color-gold)" }}>
                      {(cand.business_impact * 100).toFixed(0)}%
                    </span>
                  </div>

                  {cand.confidence !== undefined && (
                    <div style={{ display: "flex", flexDirection: "column" }}>
                      <span style={{ fontSize: "0.68rem", textTransform: "uppercase", color: themeTokens.colors.textMuted, fontWeight: 600 }}>
                        Confidence
                      </span>
                      <span style={{ fontSize: "0.88rem", fontWeight: 700, color: themeTokens.colors.statusSuccess || "#10b981" }}>
                        {(cand.confidence * 100).toFixed(0)}%
                      </span>
                    </div>
                  )}
                </div>

                {onInspectInsight && (
                  <button
                    type="button"
                    onClick={() => onInspectInsight(cand)}
                    style={{
                      display: "inline-flex",
                      alignItems: "center",
                      gap: "5px",
                      background: "none",
                      border: `1px solid ${themeTokens.colors.borderSubtle}`,
                      color: themeTokens.colors.brandBlue || "var(--brand-primary)",
                      fontSize: "0.75rem",
                      fontWeight: 600,
                      padding: "5px 10px",
                      borderRadius: "6px",
                      cursor: "pointer",
                      transition: "background-color 0.15s ease",
                    }}
                    title={`Inspect evidence for ${cand.candidate_id}`}
                  >
                    <span>Inspect</span>
                    <ExternalLink size={12} />
                  </button>
                )}
              </div>
            </article>
          );
        })}
      </div>
    </section>
  );
}
