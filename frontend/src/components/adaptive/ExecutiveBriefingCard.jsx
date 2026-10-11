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
      <div style={{ display: "flex", alignItems: "center", minWidth: 0, flex: 1 }}>
        <p
          style={{
            margin: 0,
            fontSize: "0.96rem",
            fontWeight: 500,
            color: themeTokens.colors.textPrimary,
            lineHeight: 1.5,
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
