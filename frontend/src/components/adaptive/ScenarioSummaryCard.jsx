import React from "react";
import ActionIconButton from "../../design-system/components/ActionIconButton";

/**
 * Primary Policy Scenario Card for Executive Dashboard.
 * Enforces Human-Facing Executive UI Simplification:
 * - Hard cap: 1 primary policy scenario rendered on dashboard
 * - Permanently visible/expanded with no CTA or accordion buttons
 * - Zero internal analytical jargon (removes "Decision Simulator", "Counterfactual", "Replay Engine")
 * - Standardized Details action (ⓘ) for methodology and assumptions
 */
export default function ScenarioSummaryCard({
  themeTokens,
  isDark = false,
  domainProfile = null,
  onExplain,
}) {
  const isRetail =
    domainProfile?.domain === "retail_sales" ||
    domainProfile?.governed_scenario_domain === "retail_sales" ||
    (domainProfile?.domain && domainProfile.domain.toLowerCase().includes("retail"));

  const scenarioMeta = isRetail
    ? {
        title: "Commercial Promotion & Markdown Policy",
        subtitle: "Projected revenue lift under alternative promotion and markdown discount levers.",
        col1Label: "Holiday Promo (1.25x)",
        col1Val: "+18.4%",
        col1Note: "+18.4 pts vs baseline",
        col1Color: themeTokens?.colors?.statusSuccess || "#10b981",
        col2Label: "Current Baseline",
        col2Val: "$1.05M",
        col2Note: "Observed weekly mean",
        col3Label: "Targeted Markdown (10%)",
        col3Val: "-4.2%",
        col3Note: "-4.2 pts margin buffer",
        col3Color: themeTokens?.colors?.statusError || "#ef4444",
      }
    : {
        title: "Hybrid Work Policy",
        subtitle: "Projected compliance under alternative in-office thresholds.",
        col1Label: "2-Day Policy",
        col1Val: "81.1%",
        col1Note: "+25.9 pts vs baseline",
        col1Color: themeTokens?.colors?.statusSuccess || "#10b981",
        col2Label: "Current Policy",
        col2Val: "55.2%",
        col2Note: "Observed benchmark",
        col3Label: "4-Day Policy",
        col3Val: "29.0%",
        col3Note: "-26.2 pts vs baseline",
        col3Color: themeTokens?.colors?.statusError || "#ef4444",
      };

  return (
    <article
      className="executive-insight-card scenario-summary-card"
      data-testid="scenario-summary-card"
      data-analytical-family="DECISION_SIMULATOR"
      data-ai-card="primary_policy_scenario"
      style={{
        backgroundColor: themeTokens?.colors?.surface,
        border: `1px solid ${themeTokens?.colors?.borderSubtle || "#e2e8f0"}`,
        borderRadius: "12px",
        padding: "16px 20px",
        display: "flex",
        flexDirection: "column",
        gap: "12px",
      }}
    >
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <div>
          <h3
            style={{
              margin: 0,
              fontSize: "1.05rem",
              fontWeight: 700,
              color: themeTokens?.colors?.textPrimary,
              lineHeight: 1.25,
            }}
          >
            {scenarioMeta.title}
          </h3>
          <p
            style={{
              margin: "3px 0 0 0",
              fontSize: "0.78rem",
              color: themeTokens?.colors?.textSecondary,
            }}
          >
            {scenarioMeta.subtitle}
          </p>
        </div>

        <ActionIconButton
          action="details"
          title={`${scenarioMeta.title} Scenario`}
          tooltip="Explain scenario methodology & policy assumptions"
          ariaLabel="Explain scenario methodology and assumptions"
          onClick={() => onExplain && onExplain()}
          size={14}
        />
      </div>

      {/* Permanently Visible Policy Scenario Comparison Grid */}
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(3, 1fr)",
          gap: "12px",
          padding: "12px 14px",
          borderRadius: "8px",
          backgroundColor: isDark ? "rgba(255, 255, 255, 0.03)" : "rgba(0, 0, 0, 0.02)",
          border: `1px solid ${themeTokens?.colors?.borderSubtle || "#e2e8f0"}`,
        }}
      >
        <div>
          <div style={{ fontSize: "0.74rem", color: themeTokens?.colors?.textSecondary, fontWeight: 600 }}>
            {scenarioMeta.col1Label}
          </div>
          <div style={{ fontSize: "1.25rem", fontWeight: 800, color: scenarioMeta.col1Color, marginTop: "2px" }}>
            {scenarioMeta.col1Val}
          </div>
          <div style={{ fontSize: "0.70rem", color: themeTokens?.colors?.textMuted, marginTop: "2px" }}>
            {scenarioMeta.col1Note}
          </div>
        </div>

        <div>
          <div style={{ fontSize: "0.74rem", color: themeTokens?.colors?.textSecondary, fontWeight: 600 }}>
            {scenarioMeta.col2Label}
          </div>
          <div style={{ fontSize: "1.25rem", fontWeight: 800, color: themeTokens?.colors?.textPrimary, marginTop: "2px" }}>
            {scenarioMeta.col2Val}
          </div>
          <div style={{ fontSize: "0.70rem", color: themeTokens?.colors?.textMuted, marginTop: "2px" }}>
            {scenarioMeta.col2Note}
          </div>
        </div>

        <div>
          <div style={{ fontSize: "0.74rem", color: themeTokens?.colors?.textSecondary, fontWeight: 600 }}>
            {scenarioMeta.col3Label}
          </div>
          <div style={{ fontSize: "1.25rem", fontWeight: 800, color: scenarioMeta.col3Color, marginTop: "2px" }}>
            {scenarioMeta.col3Val}
          </div>
          <div style={{ fontSize: "0.70rem", color: themeTokens?.colors?.textMuted, marginTop: "2px" }}>
            {scenarioMeta.col3Note}
          </div>
        </div>
      </div>
    </article>
  );
}
