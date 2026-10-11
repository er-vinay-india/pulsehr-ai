import React from "react";
import ActionIconButton from "../../design-system/components/ActionIconButton";
import { useTheme } from "../../context/ThemeContext";
import { getThemeTokens } from "../../theme/tokens";

export default function ExecutiveBriefingCard({ briefing, snapshot, onInspect, onOpenInspect }) {
  const { isDark } = useTheme();
  const themeTokens = getThemeTokens(isDark);

  if (!briefing || briefing.kind === "briefing_unavailable") {
    return null;
  }

  const inspectHandler = onInspect || onOpenInspect;

  return (
    <section
      className="adaptive-compact-summary-banner"
      aria-label="Executive summary"
      style={{
        backgroundColor: themeTokens.colors.surface,
        border: `1px solid ${themeTokens.colors.borderSubtle}`,
        borderRadius: "10px",
        padding: "16px 20px",
        marginBottom: "20px",
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",
        gap: "14px",
      }}
    >
      <div style={{ display: "flex", alignItems: "baseline", gap: "12px", minWidth: 0, flex: 1 }}>
        <span
          style={{
            fontSize: "0.72rem",
            fontWeight: 700,
            textTransform: "uppercase",
            letterSpacing: "0.06em",
            color: themeTokens.colors.gold || "#d97706",
            whiteSpace: "nowrap",
          }}
        >
          Executive Summary
        </span>
        <p
          style={{
            margin: 0,
            fontSize: "0.96rem",
            fontWeight: 600,
            color: themeTokens.colors.textPrimary,
            lineHeight: 1.4,
          }}
        >
          {briefing.headline ||
            briefing.claims?.[1]?.text ||
            briefing.claims?.[0]?.text ||
            briefing.spoken_text ||
            "Executive briefing of validated workbook insights."}
        </p>
      </div>

      {inspectHandler && (
        <ActionIconButton
          action="details"
          title="Executive Summary"
          tooltip="Explain Executive Summary & ground truth lineage"
          ariaLabel="Explain Executive Summary details"
          onClick={() => inspectHandler("briefing", briefing.inspect || briefing)}
          size={14}
        />
      )}
    </section>
  );
}
