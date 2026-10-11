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
  onExplain,
}) {
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
            Hybrid Work Policy
          </h3>
          <p
            style={{
              margin: "3px 0 0 0",
              fontSize: "0.78rem",
              color: themeTokens?.colors?.textSecondary,
            }}
          >
            Projected compliance under alternative in-office thresholds.
          </p>
        </div>

        <ActionIconButton
          action="details"
          title="Hybrid Work Policy Scenario"
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
            2-Day Policy
          </div>
          <div style={{ fontSize: "1.25rem", fontWeight: 800, color: themeTokens?.colors?.statusSuccess || "#10b981", marginTop: "2px" }}>
            81.1%
          </div>
          <div style={{ fontSize: "0.70rem", color: themeTokens?.colors?.textMuted, marginTop: "2px" }}>
            +25.9 pts vs baseline
          </div>
        </div>

        <div>
          <div style={{ fontSize: "0.74rem", color: themeTokens?.colors?.textSecondary, fontWeight: 600 }}>
            Current Policy
          </div>
          <div style={{ fontSize: "1.25rem", fontWeight: 800, color: themeTokens?.colors?.textPrimary, marginTop: "2px" }}>
            55.2%
          </div>
          <div style={{ fontSize: "0.70rem", color: themeTokens?.colors?.textMuted, marginTop: "2px" }}>
            Observed benchmark
          </div>
        </div>

        <div>
          <div style={{ fontSize: "0.74rem", color: themeTokens?.colors?.textSecondary, fontWeight: 600 }}>
            4-Day Policy
          </div>
          <div style={{ fontSize: "1.25rem", fontWeight: 800, color: themeTokens?.colors?.statusError || "#ef4444", marginTop: "2px" }}>
            29.0%
          </div>
          <div style={{ fontSize: "0.70rem", color: themeTokens?.colors?.textMuted, marginTop: "2px" }}>
            -26.2 pts vs baseline
          </div>
        </div>
      </div>
    </article>
  );
}
