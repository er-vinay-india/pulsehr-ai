import React from "react";
import { Sliders, ArrowRight } from "lucide-react";

export default function ScenarioSummaryCard({
  themeTokens,
  isDark = false,
  onOpenExplorer,
}) {
  return (
    <article
      className="executive-insight-card scenario-summary-card"
      data-testid="scenario-summary-card"
      style={{
        backgroundColor: themeTokens?.colors?.surface,
        border: `1px dashed ${themeTokens?.colors?.borderStrong || "#cbd5e1"}`,
        borderRadius: "12px",
        padding: "16px 20px",
        display: "flex",
        flexDirection: "column",
        justifyContent: "space-between",
        gap: "12px",
      }}
    >
      <div>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "4px" }}>
          <span
            style={{
              padding: "2px 8px",
              borderRadius: "6px",
              fontSize: "0.70rem",
              fontWeight: 700,
              textTransform: "uppercase",
              backgroundColor: "rgba(139, 92, 246, 0.12)",
              color: "#8b5cf6",
              display: "inline-flex",
              alignItems: "center",
              gap: "4px",
            }}
          >
            <Sliders size={11} />
            Decision Simulator
          </span>
          <span style={{ fontSize: "0.72rem", color: themeTokens?.colors?.textMuted }}>Interactive Tool</span>
        </div>

        <h3 style={{ margin: "4px 0 2px 0", fontSize: "1.02rem", fontWeight: 700, color: themeTokens?.colors?.textPrimary }}>
          Policy Scenario Simulator
        </h3>
        <p style={{ margin: "0 0 12px 0", fontSize: "0.78rem", color: themeTokens?.colors?.textSecondary }}>
          Counterfactual policy replay across organizational attendance & coverage baselines.
        </p>

        {/* Compact Scenario Comparison Bar */}
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(3, 1fr)",
            gap: "8px",
            padding: "10px 12px",
            borderRadius: "8px",
            backgroundColor: isDark ? "rgba(255, 255, 255, 0.03)" : "rgba(0, 0, 0, 0.02)",
            border: `1px solid ${themeTokens?.colors?.borderSubtle || "#e2e8f0"}`,
          }}
        >
          <div>
            <div style={{ fontSize: "0.70rem", color: themeTokens?.colors?.textMuted, fontWeight: 600 }}>2-Day Replay</div>
            <div style={{ fontSize: "1.05rem", fontWeight: 700, color: themeTokens?.colors?.statusSuccess || "#10b981" }}>81.1%</div>
          </div>
          <div>
            <div style={{ fontSize: "0.70rem", color: themeTokens?.colors?.textMuted, fontWeight: 600 }}>Baseline Policy</div>
            <div style={{ fontSize: "1.05rem", fontWeight: 700, color: themeTokens?.colors?.textPrimary }}>55.2%</div>
          </div>
          <div>
            <div style={{ fontSize: "0.70rem", color: themeTokens?.colors?.textMuted, fontWeight: 600 }}>4-Day Replay</div>
            <div style={{ fontSize: "1.05rem", fontWeight: 700, color: themeTokens?.colors?.statusError || "#ef4444" }}>29.0%</div>
          </div>
        </div>
      </div>

      <div style={{ display: "flex", justifyContent: "flex-end" }}>
        <button
          type="button"
          onClick={onOpenExplorer}
          style={{
            display: "inline-flex",
            alignItems: "center",
            gap: "6px",
            padding: "7px 14px",
            borderRadius: "6px",
            border: `1px solid ${themeTokens?.colors?.brandBlue || "#2563eb"}`,
            background: "transparent",
            color: themeTokens?.colors?.brandBlue || "#2563eb",
            fontSize: "0.80rem",
            fontWeight: 600,
            cursor: "pointer",
          }}
        >
          <span>Open Scenario Explorer</span>
          <ArrowRight size={13} />
        </button>
      </div>
    </article>
  );
}
